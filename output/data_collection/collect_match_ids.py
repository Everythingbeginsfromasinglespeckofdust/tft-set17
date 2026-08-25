#!/usr/bin/env python3
"""TFT 최상위권 랭커 기반 매치 ID 수집 스크립트.

작업 흐름:
1. KR 챌린저/그랜드마스터 리그의 상위 랭커 PUUID 목록 수집 (League-V1)
2. 각 PUUID별 최근 매치 ID 목록 수집 (Match-V1 by-puuid)
3. Rate limit 준수 (1.25s 간격 및 429 지수 백오프)
4. 중복 제거 후 /output/data/match_ids.json 저장 (100개 이상)
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
    target_count: int = 100,
    region: str = "kr",
    routing: str = "asia",
    output_path: str = None,
) -> list[str]:
    """상위 랭커들의 매치 ID를 수집하여 중복 제거 후 저장.

    Args:
        target_count: 목표 고유 매치 ID 수 (기본 100개 이상)
        region: 리그 지역 코드 (기본 'kr')
        routing: 매치 라우팅 지역 코드 (기본 'asia')
        output_path: 저장할 JSON 파일 경로

    Returns:
        고유 매치 ID 리스트
    """
    if output_path is None:
        os.makedirs(_DATA_DIR, exist_ok=True)
        output_path = os.path.join(_DATA_DIR, "match_ids.json")

    client = RiotClient(region=region, routing=routing, min_request_interval=1.25)

    # 1. 챌린저 상위 랭커 PUUID 수집
    puuids = client.get_top_puuids(tier="challenger", limit=30)
    if len(puuids) < 15:
        # 보충용 그랜드마스터
        gm_puuids = client.get_top_puuids(tier="grandmaster", limit=20)
        puuids.extend(gm_puuids)

    logger.info(f"총 {len(puuids)}명의 상위 랭커로부터 매치 수집을 시작합니다 (목표: {target_count}개)...")

    unique_match_ids = []
    seen_matches = set()

    for idx, puuid in enumerate(puuids, start=1):
        if len(unique_match_ids) >= target_count:
            logger.info(f"목표 수치({target_count}개) 달성 완료!")
            break

        logger.info(f"[{idx}/{len(puuids)}] PUUID({puuid[:8]}...) 최근 매치 조회 중...")
        try:
            m_ids = client.get_match_ids_by_puuid(puuid, count=20)
        except Exception as e:
            logger.warning(f"매치 조회 중 오류 건너뜀: {e}")
            continue

        new_count = 0
        for mid in m_ids:
            if mid not in seen_matches:
                seen_matches.add(mid)
                unique_match_ids.append(mid)
                new_count += 1

        logger.info(f"  -> 신규 매치 {new_count}개 추가 (현재 누적 고유 매치: {len(unique_match_ids)}개)")

    logger.info(f"총 {len(unique_match_ids)}개의 고유 매치 ID 수집 완료.")

    # 저장 데이터 구조화
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

    logger.info(f"매치 ID 파일 저장 완료: {output_path}")
    return unique_match_ids


if __name__ == "__main__":
    matches = collect_match_ids(target_count=100)
    print("\n" + "=" * 50)
    print(f"수집된 총 고유 매치 ID 수: {len(matches)}")
    print("샘플 매치 ID (최대 5개):")
    for m in matches[:5]:
        print(f"  - {m}")
    print("=" * 50)
