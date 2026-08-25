#!/usr/bin/env python3
"""TFT 매치 상세 데이터 수집 및 M2B 피처/보드 스냅샷 추출기.

기능:
1. /output/data/match_ids.json 에서 매치 ID 목록 로드
2. Riot Match-V1 API로 매치 상세 정보(get_match_detail) 수집
3. 8인 PvP 표준 매치 필터링 (PvE/토커의 시험 등 1인/비표준 모드 제외)
4. 참가자별 최종 등수(final_placement), 레벨, 남은 골드, 보드 상태(board_power.py 입력 형식) 추출
5. /output/data/match_snapshots.jsonl 에 JSON Lines 형식으로 저장
6. Rate limit 및 429 지수 백오프 준수
"""
import json
import logging
import os
import sys
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_OUTPUT = os.path.join(_HERE, "..")
_ECONOMY = os.path.join(_OUTPUT, "economy")
if _ECONOMY not in sys.path:
    sys.path.insert(0, _ECONOMY)
_REPO = os.path.join(_OUTPUT, "..")
_DATA_DIR = os.path.join(_OUTPUT, "data")

from riot_client import RiotClient
import board_power as bp

logger = logging.getLogger("CollectMatchDetails")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _load_mappings():
    """Riot ID -> 한국어 챔피언/아이템 이름 매핑 데이터 로드."""
    # 1. 아이템 매핑
    item_json_path = os.path.join(_REPO, "TFT_DDragon", "data", "ko_KR", "item.json")
    item_id_to_name = {}
    if os.path.exists(item_json_path):
        with open(item_json_path, encoding="utf-8") as f:
            raw_items = json.load(f).get("data", {})
            for k, v in raw_items.items():
                name = v.get("name", "")
                if name:
                    item_id_to_name[k] = name
                    item_id_to_name[k.lower()] = name
                    if "id" in v:
                        item_id_to_name[v["id"]] = name
                        item_id_to_name[v["id"].lower()] = name

    # 2. 챔피언 매핑
    set17_json_path = os.path.join(_REPO, "tft_set17.json")
    champ_id_to_info = {}
    if os.path.exists(set17_json_path):
        with open(set17_json_path, encoding="utf-8") as f:
            raw_champs = json.load(f).get("champions", [])
            for c in raw_champs:
                champ_id_to_info[c["id"]] = c
                champ_id_to_info[c["id"].lower()] = c

    # 3. 유효 아이템 목록 (board_power 기준)
    basic_comps, completed_items = bp._load_items_db()
    valid_items = basic_comps | completed_items

    return item_id_to_name, champ_id_to_info, valid_items


def parse_participant_snapshot(
    participant: dict,
    match_id: str,
    item_id_to_name: dict,
    champ_id_to_info: dict,
    valid_items: set,
) -> dict:
    """단일 참가자 데이터를 M2B 보드 스냅샷 레코드 형태로 변환."""
    placement = participant.get("placement")
    level = participant.get("level")
    gold_left = participant.get("gold_left", 0)
    puuid = participant.get("puuid", "")

    board_units = []
    for u in participant.get("units", []):
        cid = u.get("character_id", "")
        cinfo = champ_id_to_info.get(cid) or champ_id_to_info.get(cid.lower())
        if not cinfo:
            # 훈련용 봇/소환수 등 비상점 기물 제외
            continue

        cname = cinfo["name"]
        cost = cinfo["cost"]
        tier = u.get("tier", 1)
        if tier not in (1, 2, 3):
            tier = min(3, max(1, tier))

        unit_items = []
        for raw_it in u.get("itemNames", []):
            it_name = item_id_to_name.get(raw_it) or item_id_to_name.get(raw_it.lower(), raw_it)
            if it_name in valid_items:
                unit_items.append(it_name)

        unit_items = unit_items[:3]  # 유닛당 최대 3아이템

        board_units.append({
            "champion": cname,
            "cost": cost,
            "star_level": tier,
            "items": unit_items,
        })

    return {
        "match_id": match_id,
        "puuid": puuid,
        "riot_id_name": participant.get("riotIdGameName", ""),
        "riot_id_tag": participant.get("riotIdTagline", ""),
        "final_placement": placement,
        "level": level,
        "gold_left": gold_left,
        "last_round": participant.get("last_round"),
        "time_eliminated": participant.get("time_eliminated"),
        "total_damage_to_players": participant.get("total_damage_to_players"),
        "board": {
            "units": board_units
        },
    }


def collect_match_details(
    match_ids_path: str = None,
    output_path: str = None,
    limit: int = None,
) -> list[dict]:
    """수집된 매치 ID 목록의 상세 정보를 조회하고 참가자별 스냅샷을 JSONL로 저장."""
    if match_ids_path is None:
        match_ids_path = os.path.join(_DATA_DIR, "match_ids.json")
    if output_path is None:
        output_path = os.path.join(_DATA_DIR, "match_snapshots.jsonl")

    if not os.path.exists(match_ids_path):
        raise FileNotFoundError(f"매치 ID 파일이 존재하지 않습니다: {match_ids_path}")

    with open(match_ids_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        match_ids = data.get("match_ids", [])

    if limit:
        match_ids = match_ids[:limit]

    total_matches = len(match_ids)
    logger.info(f"총 {total_matches}개 매치의 상세 데이터 수집을 시작합니다...")

    item_id_to_name, champ_id_to_info, valid_items = _load_mappings()
    client = RiotClient(min_request_interval=1.25)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    snapshots = []
    success_count = 0
    skipped_non_8_count = 0
    fail_count = 0

    with open(output_path, "w", encoding="utf-8") as out_f:
        for idx, mid in enumerate(match_ids, start=1):
            logger.info(f"[{idx}/{total_matches}] 매치 상세 조회 중: {mid}...")
            try:
                detail = client.get_match_detail(mid)
                info = detail.get("info", {})
                participants = info.get("participants", [])
                gtype = info.get("tft_game_type")
                qid = info.get("queueId") or info.get("queue_id")

                # 8인 표준 매치만 필터링 (PvE 1인 모드, 미달 매치 제외)
                if len(participants) != 8 or gtype == "pve" or qid == 1220:
                    logger.warning(
                        f"  -> 비표준 매치 건너뜀 (참가자 {len(participants)}명, queueId={qid}, type={gtype}): {mid}"
                    )
                    skipped_non_8_count += 1
                    continue

                for p in participants:
                    snap = parse_participant_snapshot(
                        p, mid, item_id_to_name, champ_id_to_info, valid_items
                    )
                    snapshots.append(snap)
                    out_f.write(json.dumps(snap, ensure_ascii=False) + "\n")

                out_f.flush()
                success_count += 1
                logger.info(f"  -> 8명 스냅샷 추출 완료 (누적: {len(snapshots)}개)")
            except Exception as e:
                logger.warning(f"  -> 매치 {mid} 수집 실패 건너뜀: {e}")
                fail_count += 1

    total_skipped = skipped_non_8_count + fail_count
    logger.info(
        f"수집 완료! 8인 표준 성공 매치: {success_count}/{total_matches}, "
        f"비표준 모드 제외: {skipped_non_8_count}개, 에러 실패: {fail_count}개, "
        f"총 유효 스냅샷: {len(snapshots)}개"
    )

    return snapshots


if __name__ == "__main__":
    snapshots = collect_match_details()
    print("\n" + "=" * 60)
    print(f"총 수집된 스냅샷 레코드 수: {len(snapshots)}")

    # 1. 1~8등 전수 검증
    invalid_placements = [s for s in snapshots if not (1 <= s.get("final_placement", 0) <= 8)]
    print(f"등수(1~8) 유효성 검증: {'PASS (이상치 0개)' if not invalid_placements else f'FAIL ({len(invalid_placements)}개 이상치)'}")

    # 2. 등수별 인원 분포 검증
    from collections import Counter
    dist = Counter(s["final_placement"] for s in snapshots)
    print("등수별 인원 분포:")
    for rank in sorted(dist.keys()):
        print(f"  - {rank}등: {dist[rank]}명")

    # 3. board_power.py 연동 호환성 검증
    if snapshots:
        sample = snapshots[0]
        power_res = bp.calculate_board_power(sample["board"])
        print(f"\n샘플 레코드 board_power 계산 검증 (Rank {sample['final_placement']}):")
        print(f"  - 챔피언 수: {len(sample['board']['units'])}")
        print(f"  - Total Power: {power_res['total_power']:.2f}")
        print(f"  - Breakdown: {power_res['breakdown']}")
    print("=" * 60)
