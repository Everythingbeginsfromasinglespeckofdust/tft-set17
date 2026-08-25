#!/usr/bin/env python3
"""TFT 매치 상세 데이터 수집 및 M2B 피처/보드 스냅샷 추출기 (체크포인트 & 재개 지원).

기능:
1. /output/data/match_ids.json 에서 매치 ID 목록 로드
2. Riot Match-V1 API로 매치 상세 정보(get_match_detail) 수집
3. 표준 솔로 랭크(queueId == 1100, Set 17, 8인 매치)만 선별 필터링
4. 체크포인트 기반 재개(/output/data/collection_progress.json)로 중복 요청 방지
5. 목표 수치(500개 표준 랭크 매치) 달성 시 자동 종료 및 중단 시 안전한 상태 보존
6. /output/data/match_snapshots.jsonl 에 증분 추가(append)
"""
import json
import logging
import os
import signal
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

    set17_json_path = os.path.join(_REPO, "tft_set17.json")
    champ_id_to_info = {}
    if os.path.exists(set17_json_path):
        with open(set17_json_path, encoding="utf-8") as f:
            raw_champs = json.load(f).get("champions", [])
            for c in raw_champs:
                champ_id_to_info[c["id"]] = c
                champ_id_to_info[c["id"].lower()] = c

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

        unit_items = unit_items[:3]

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


def _save_progress(progress_path: str, progress_data: dict):
    """체크포인트 진행 상황 파일 저장."""
    os.makedirs(os.path.dirname(os.path.abspath(progress_path)), exist_ok=True)
    temp_path = progress_path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(progress_data, f, ensure_ascii=False, indent=2)
    if os.path.exists(progress_path):
        os.replace(temp_path, progress_path)
    else:
        os.rename(temp_path, progress_path)


def collect_match_details(
    match_ids_path: str = None,
    output_path: str = None,
    progress_path: str = None,
    target_ranked_matches: int = 500,
    target_queue_id: int = 1100,
    target_set_number: int = 17,
    limit: int = None,
) -> list[dict]:
    """체크포인트를 기반으로 목표 랭크 매치 수까지 상세 데이터를 수집/병합.

    Args:
        match_ids_path: 매치 ID 목록 JSON 경로
        output_path: 저장할 JSONL 파일 경로
        progress_path: 체크포인트 기록 JSON 경로
        target_ranked_matches: 목표 표준 랭크 매치 수 (기본 500개)
        target_queue_id: 표준 랭크 큐 ID (기본 1100)
        target_set_number: 시즌 번호 (기본 17)
        limit: 1회 실행 시 처리할 최대 매치 수 (None이면 목표 달성 시까지)
    """
    if match_ids_path is None:
        match_ids_path = os.path.join(_DATA_DIR, "match_ids.json")
    if output_path is None:
        output_path = os.path.join(_DATA_DIR, "match_snapshots.jsonl")
    if progress_path is None:
        progress_path = os.path.join(_DATA_DIR, "collection_progress.json")

    if not os.path.exists(match_ids_path):
        raise FileNotFoundError(f"매치 ID 파일이 존재하지 않습니다: {match_ids_path}")

    with open(match_ids_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        all_match_ids = data.get("match_ids", [])

    if limit:
        all_match_ids = all_match_ids[:limit]

    # 1. 기존 체크포인트 및 기존 스냅샷 로드
    processed_match_ids = set()
    ranked_match_ids = set()
    existing_snapshots = []

    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        s = json.loads(line)
                        existing_snapshots.append(s)
                        ranked_match_ids.add(s["match_id"])
                        processed_match_ids.add(s["match_id"])
            logger.info(f"기존 스냅샷 파일에서 {len(ranked_match_ids)}개 매치({len(existing_snapshots)}개 레코드) 로드 완료.")
        except Exception as e:
            logger.warning(f"기존 스냅샷 파일 로드 중 경고: {e}")

    if os.path.exists(progress_path):
        try:
            with open(progress_path, "r", encoding="utf-8") as f:
                p_data = json.load(f)
                processed_match_ids.update(p_data.get("processed_match_ids", []))
                ranked_match_ids.update(p_data.get("ranked_match_ids", []))
        except Exception as e:
            logger.warning(f"진행 상황 파일 로드 중 경고: {e}")

    current_ranked_count = len(ranked_match_ids)
    logger.info(
        f"현재 진행 상태: 누적 표준 랭크 매치 {current_ranked_count}/{target_ranked_matches}개, "
        f"처리 완료된 총 매치 {len(processed_match_ids)}개"
    )

    if current_ranked_count >= target_ranked_matches:
        logger.info(f"이미 목표 수치({target_ranked_matches}개)를 달성했습니다!")
        return existing_snapshots

    # 미처리 매치 선별
    pending_match_ids = [m for m in all_match_ids if m not in processed_match_ids]
    logger.info(f"수집 대기 중인 신규 매치 수: {len(pending_match_ids)}개")

    item_id_to_name, champ_id_to_info, valid_items = _load_mappings()
    client = RiotClient(min_request_interval=1.25)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    progress_state = {
        "target_ranked_matches": target_ranked_matches,
        "total_ranked_matches": current_ranked_count,
        "total_ranked_snapshots": len(existing_snapshots),
        "processed_match_ids": list(processed_match_ids),
        "ranked_match_ids": list(ranked_match_ids),
        "last_updated": datetime.now().isoformat(),
        "status": "in_progress",
    }

    # 인터럽트 핸들러 등록
    interrupted = False
    def _handle_interrupt(sig, frame):
        nonlocal interrupted
        logger.warning("\n[작업 중단 신호 감지] 현재 진행 상황을 안전하게 저장하고 종료합니다...")
        interrupted = True

    prev_sigint = signal.signal(signal.SIGINT, _handle_interrupt)

    try:
        with open(output_path, "a", encoding="utf-8") as out_f:
            for idx, mid in enumerate(pending_match_ids, start=1):
                if interrupted:
                    break
                if len(ranked_match_ids) >= target_ranked_matches:
                    logger.info(f"목표 랭크 매치 수치({target_ranked_matches}개) 달성 완료!")
                    progress_state["status"] = "completed"
                    break

                logger.info(f"[{idx}/{len(pending_match_ids)}] 매치 조회 중: {mid} (현재 랭크 매치: {len(ranked_match_ids)}/{target_ranked_matches})...")
                try:
                    detail = client.get_match_detail(mid)
                    info = detail.get("info", {})
                    participants = info.get("participants", [])
                    gtype = info.get("tft_game_type")
                    qid = info.get("queueId") or info.get("queue_id")
                    set_num = info.get("tft_set_number")

                    processed_match_ids.add(mid)

                    if (
                        len(participants) == 8
                        and qid == target_queue_id
                        and set_num == target_set_number
                    ):
                        new_snaps = []
                        for p in participants:
                            snap = parse_participant_snapshot(
                                p, mid, item_id_to_name, champ_id_to_info, valid_items
                            )
                            new_snaps.append(snap)
                            existing_snapshots.append(snap)
                            out_f.write(json.dumps(snap, ensure_ascii=False) + "\n")

                        out_f.flush()
                        ranked_match_ids.add(mid)
                        logger.info(f"  -> [적합 랭크 매치] 8명 추출 완료 (누적 랭크 매치: {len(ranked_match_ids)}개, 레코드: {len(existing_snapshots)}개)")
                    else:
                        logger.info(f"  -> [비대상 매치 건너뜀] queueId={qid}, set={set_num}, 참가자={len(participants)}명: {mid}")

                except Exception as e:
                    logger.warning(f"  -> 매치 {mid} 수집 중 오류: {e}")
                    # API 키 만료 또는 치명적 에러 시 중단
                    if "401" in str(e) or "403" in str(e):
                        logger.error("API 키가 만료되었거나 유효하지 않습니다. 진행 상황을 저장하고 종료합니다.")
                        break

                # 주기적 체크포인트 저장
                progress_state.update({
                    "total_ranked_matches": len(ranked_match_ids),
                    "total_ranked_snapshots": len(existing_snapshots),
                    "processed_match_ids": list(processed_match_ids),
                    "ranked_match_ids": list(ranked_match_ids),
                    "last_updated": datetime.now().isoformat(),
                })
                _save_progress(progress_path, progress_state)

    finally:
        signal.signal(signal.SIGINT, prev_sigint)
        progress_state.update({
            "total_ranked_matches": len(ranked_match_ids),
            "total_ranked_snapshots": len(existing_snapshots),
            "processed_match_ids": list(processed_match_ids),
            "ranked_match_ids": list(ranked_match_ids),
            "last_updated": datetime.now().isoformat(),
            "status": "completed" if len(ranked_match_ids) >= target_ranked_matches else "in_progress",
        })
        _save_progress(progress_path, progress_state)

    logger.info(
        f"작업 완료/종료. 누적 표준 랭크 매치: {len(ranked_match_ids)}개, "
        f"총 스냅샷: {len(existing_snapshots)}개. 진행 상황 저장 완료 ({progress_path})."
    )
    if len(ranked_match_ids) < target_ranked_matches:
        print("\n" + "=" * 60)
        print("💡 [알림] 목표 매치 수에 아직 도달하지 않았거나 중간 중단되었습니다.")
        print("💡 다음 실행 시 이어서 진행 가능합니다 (기존 수집 데이터 100% 보존).")
        print("=" * 60 + "\n")

    return existing_snapshots


if __name__ == "__main__":
    snapshots = collect_match_details(target_ranked_matches=500)
    print("\n" + "=" * 60)
    print(f"총 수집된 표준 랭크 스냅샷 레코드 수: {len(snapshots)}")

    from collections import Counter
    dist = Counter(s["final_placement"] for s in snapshots)
    print("등수별 인원 분포:")
    for rank in sorted(dist.keys()):
        print(f"  - {rank}등: {dist[rank]}명")
    print("=" * 60)
