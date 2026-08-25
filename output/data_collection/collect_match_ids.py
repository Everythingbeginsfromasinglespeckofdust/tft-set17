#!/usr/bin/env python3
"""TFT 최상위권(챌린저/그랜드마스터/마스터) 랭커 기반 매치 ID 수집 및 병합 스크립트.

기능:
1. 챌린저 + 그랜드마스터 + 마스터 리그의 상위 랭커 PUUID 수집
2. 각 PUUID별 최근 매치 ID 수집 (count=30)
3. 기존 /output/data/match_ids.json 과 병합(중복 제거 및 증분 저장)
4. Rate limit 준수 (1.25s 간격 및 429 지수 백오프)
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
_DATA_DIR = os.path.join(_OUTPUT, "data")

from riot_client import RiotClient

logger = logging.getLogger("CollectMatchIDs")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def collect_match_ids(
    target_count: int = 750,
    region: str = "kr",
    routing: str = "asia",
    matches_per_puuid: int = 30,
    output_path: str = None,
) -> list[str]:
    """상위 랭커들의 매치 ID를 수집하여 기존 데이터와 병합/중복 제거 후 저장.

    Args:
        target_count: 목표 고유 매치 ID 수 (기본 750개)
        region: 리그 지역 코드 (기본 'kr')
        routing: 매치 라우팅 지역 코드 (기본 'asia')
        matches_per_puuid: PUUID당 조회할 매치 수
        output_path: 저장할 JSON 파일 경로

    Returns:
        병합된 고유 매치 ID 리스트
    """
    if output_path is None:
        os.makedirs(_DATA_DIR, exist_ok=True)
        output_path = os.path.join(_DATA_DIR, "match_ids.json")

    # 기존 수집된 매치 ID 로드
    unique_match_ids = []
    seen_matches = set()
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                for mid in existing_data.get("match_ids", []):
                    if mid not in seen_matches:
                        seen_matches.add(mid)
                        unique_match_ids.append(mid)
            logger.info(f"기존 저장된 매치 ID {len(unique_match_ids)}개를 로드했습니다.")
        except Exception as e:
            logger.warning(f"기존 매치 ID 로드 실패, 새로 수집합니다: {e}")

    if len(unique_match_ids) >= target_count:
        logger.info(f"이미 목표 수치({target_count}개) 이상의 매치 ID({len(unique_match_ids)}개)가 확보되어 있습니다.")
        return unique_match_ids

    client = RiotClient(region=region, routing=routing, min_request_interval=1.25)

    # 1. 챌린저, 그랜드마스터, 마스터 순차 수집
    all_puuids = []
    for tier, limit_count in [("challenger", 50), ("grandmaster", 50), ("master", 50)]:
        try:
            t_puuids = client.get_top_puuids(tier=tier, limit=limit_count)
            all_puuids.extend(t_puuids)
        except Exception as e:
            logger.warning(f"[{tier}] 랭커 목록 조회 실패: {e}")

    logger.info(f"총 {len(all_puuids)}명의 상위 랭커 풀을 확보했습니다 (목표 매치: {target_count}개)...")

    for idx, puuid in enumerate(all_puuids, start=1):
        if len(unique_match_ids) >= target_count:
            logger.info(f"목표 수치({target_count}개) 달성 완료! (현재 누적 {len(unique_match_ids)}개)")
            break

        logger.info(f"[{idx}/{len(all_puuids)}] PUUID({puuid[:8]}...) 최근 매치 조회 중...")
        try:
            m_ids = client.get_match_ids_by_puuid(puuid, count=matches_per_puuid)
        except Exception as e:
            logger.warning(f"매치 조회 중 오류 건너뜀: {e}")
            continue

        new_count = 0
        for mid in m_ids:
            if mid not in seen_matches:
                seen_matches.add(mid)
                unique_match_ids.append(mid)
                new_count += 1

        logger.info(f"  -> 신규 매치 {new_count}개 추가 (누적 고유 매치: {len(unique_match_ids)}개)")

        # 점진적 저장 (중간 중단 대비)
        if new_count > 0 and idx % 5 == 0:
            save_data = {
                "region": region,
                "routing": routing,
                "total_matches": len(unique_match_ids),
                "collected_at": datetime.now().isoformat(),
                "match_ids": unique_match_ids,
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)

    # 최종 저장
    save_data = {
        "region": region,
        "routing": routing,
        "total_matches": len(unique_match_ids),
        "collected_at": datetime.now().isoformat(),
        "match_ids": unique_match_ids,
    }
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

    logger.info(f"매치 ID 파일 저장 완료 (총 {len(unique_match_ids)}개): {output_path}")
    return unique_match_ids


if __name__ == "__main__":
    matches = collect_match_ids(target_count=750)
    print("\n" + "=" * 50)
    print(f"수집/병합된 총 고유 매치 ID 수: {len(matches)}")
    print("샘플 매치 ID (최대 5개):")
    for m in matches[:5]:
        print(f"  - {m}")
    print("=" * 50)
