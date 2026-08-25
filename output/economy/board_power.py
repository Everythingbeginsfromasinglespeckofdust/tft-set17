#!/usr/bin/env python3
"""TFT Set 17 보드 가치평가 휴리스틱 v1 (Board Power Evaluator).

공식:
    board_power = unit_power_sum + item_score_sum + synergy_bonus_sum

1. 유닛별 기본 파워:
   unit_power = cost * star_multiplier[star_level]
   star_multiplier = {1: 1.0, 2: 1.8, 3: 3.2}

2. 아이템 점수:
   유닛이 보유한 완성 아이템 개수 * 3.0 + 미완성 부품 개수 * 1.0
   (01_items.json 기준: basic_components -> 부품, standard_items/set17_special_items -> 완성품)

3. 시너지 보너스:
   각 활성화된 시너지에 대해 (도달한 브레이크포인트 단계 인덱스)^1.5 * 2.0 합산
   - 1-indexed: 1번째 단계=1, 2번째 단계=2, 3번째 단계=3 ...
   - 브레이크포인트 미도달 시 비활성화 (보너스 0)
   - "별돌보미" 8종 하위 변형은 베이스 ID/시너지명("별돌보미")으로 통합

데이터 출처:
- 아이템: output/tft_guide/01_items.json
- 챔피언 및 시너지 매핑: tft_set17.json (또는 07_roster.json / TFT_DDragon)
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_OUTPUT = os.path.join(_HERE, "..")
if _OUTPUT not in sys.path:
    sys.path.insert(0, _OUTPUT)
_REPO = os.path.join(_OUTPUT, "..")

from roll_probability import _check_int

# 1. 가중치 상수 (PM 확정값 — 임의 수정 금지)
STAR_MULTIPLIER = {1: 1.0, 2: 1.8, 3: 3.2}
ITEM_SCORE_COMPONENT = 1.0
ITEM_SCORE_COMPLETED = 3.0

# 2. Set 17 시너지 브레이크포인트 정의 (35개 전수)
TRAIT_BREAKPOINTS = {
    "중재자": [2, 3],
    "동물특공대": [3, 5],
    "정령족": [3, 5, 7, 10],
    "파티광": [1],
    "N.O.V.A.": [2, 5],
    "암흑의 별": [2, 4, 6, 9],
    "신성 결투가": [1],
    "최신상": [1],
    "말살자": [1],
    "메카": [3, 4, 6],
    "기동총격여신": [1],
    "어둠의 여인": [1],
    "태고족": [2, 3],
    "초능력": [2, 4],
    "구원자": [1],
    "보루": [1],
    "지휘관": [1],
    "우주 그루브": [1, 3, 5, 7, 10],
    "별돌보미": [3, 4, 5, 6],
    "예언자": [1],
    "시간 균열자": [2, 3, 4],
    "파멸자": [1],
    "은하계 사냥꾼": [1],
    "복제자": [2, 4],
    "도전자": [2, 3, 4, 5],
    "불한당": [2, 3, 4, 5],
    "운명술사": [2, 4],
    "여행자": [2, 3, 4, 5, 6],
    "싸움꾼": [2, 4, 6],
    "전달자": [2, 3, 4, 5],
    "습격자": [2, 4, 6],
    "저격수": [2, 3, 4],
    "요새": [2, 4, 6],
    "선봉대": [2, 4, 6],
    "길잡이": [3, 5, 7],
}

_ITEMS_CACHE = None
_CHAMPIONS_CACHE = None


def _load_items_db():
    global _ITEMS_CACHE
    if _ITEMS_CACHE is not None:
        return _ITEMS_CACHE
    
    items_path = os.path.join(_OUTPUT, "tft_guide", "01_items.json")
    if not os.path.exists(items_path):
        items_path = os.path.join(_REPO, "tft_guide", "01_items.json")
    
    with open(items_path, encoding="utf-8") as f:
        data = json.load(f)
    
    components = set(data.get("basic_components", []))
    completed = set(it["name"] for it in data.get("standard_items", []))
    for cat_items in data.get("set17_special_items", {}).values():
        completed.update(cat_items)
    
    _ITEMS_CACHE = (components, completed)
    return _ITEMS_CACHE


def _load_champions_db():
    global _CHAMPIONS_CACHE
    if _CHAMPIONS_CACHE is not None:
        return _CHAMPIONS_CACHE
    
    set17_path = os.path.join(_REPO, "tft_set17.json")
    if not os.path.exists(set17_path):
        raise FileNotFoundError(f"tft_set17.json을 찾을 수 없습니다: {set17_path}")
    
    with open(set17_path, encoding="utf-8") as f:
        data = json.load(f)
    
    db = {}
    for c in data.get("champions", []):
        db[c["name"]] = {
            "id": c["id"],
            "name": c["name"],
            "cost": c["cost"],
            "traits": c["traits"],
        }
    
    _CHAMPIONS_CACHE = db
    return _CHAMPIONS_CACHE


def calculate_board_power(board: dict) -> dict:
    """보드 상태의 기물 파워, 아이템 점수, 시너지 보너스를 합산해 종합 파워를 산출.

    Args:
        board: {
            "units": [
                {
                    "champion": "진",
                    "cost": 5,
                    "star_level": 2,
                    "items": ["대천사의 지팡이", "쓸데없이 큰 지팡이"]
                },
                ...
            ]
        }

    Returns:
        {
            "total_power": float,
            "breakdown": {
                "unit_power": float,
                "item_score": float,
                "synergy_bonus": float,
                "active_synergies": [
                    {
                        "trait": str,
                        "unit_count": int,
                        "breakpoint_reached": int,
                        "bonus": float
                    },
                    ...
                ]
            }
        }

    Raises:
        ValueError: 잘못된 입력 구조, 존재하지 않는 챔피언/아이템/시너지,
            유효하지 않은 cost/star_level (bool 차단), 유닛당 아이템 3개 초과 등.
    """
    if not isinstance(board, dict):
        raise ValueError(f"board는 dict여야 합니다: {board!r}")
    if "units" not in board or not isinstance(board["units"], list):
        raise ValueError(f"board['units']는 list여야 합니다: {board.get('units')!r}")

    basic_components, completed_items = _load_items_db()
    champions_db = _load_champions_db()

    unit_power_sum = 0.0
    item_score_sum = 0.0
    trait_champions = {}

    for idx, u in enumerate(board["units"]):
        if not isinstance(u, dict):
            raise ValueError(f"units[{idx}]는 dict여야 합니다: {u!r}")
        
        cname = u.get("champion")
        if not isinstance(cname, str) or not cname:
            raise ValueError(f"units[{idx}]에 유효한 'champion' 이름이 필요합니다: {cname!r}")
        if cname not in champions_db:
            raise ValueError(f"존재하지 않는 챔피언입니다: {cname!r}")
        cinfo = champions_db[cname]

        # 코스트 검증
        if "cost" in u:
            cost = _check_int(f"units[{idx}] cost", u["cost"])
            if cost != cinfo["cost"]:
                raise ValueError(
                    f"챔피언 '{cname}'의 코스트가 일치하지 않습니다: 입력값 {cost}, 실제 {cinfo['cost']}"
                )
        else:
            cost = cinfo["cost"]
        
        if cost not in (1, 2, 3, 4, 5):
            raise ValueError(f"코스트는 1~5 사이여야 합니다: {cost}")

        # 성급 검증
        if "star_level" not in u:
            raise ValueError(f"units[{idx}]에 'star_level'이 누락되었습니다")
        star_level = _check_int(f"units[{idx}] star_level", u["star_level"])
        if star_level not in (1, 2, 3):
            raise ValueError(f"star_level은 1, 2, 3 중 하나여야 합니다: {star_level}")

        # 유닛 파워 합산
        unit_power = cost * STAR_MULTIPLIER[star_level]
        unit_power_sum += unit_power

        # 아이템 검증 및 점수 합산
        items = u.get("items", [])
        if not isinstance(items, list):
            raise ValueError(f"units[{idx}] items는 list여야 합니다: {items!r}")
        if len(items) > 3:
            raise ValueError(f"유닛당 아이템은 최대 3개까지만 장착 가능합니다: {len(items)}개 장착됨")

        for it in items:
            if not isinstance(it, str):
                raise ValueError(f"아이템 이름은 문자열이어야 합니다: {it!r}")
            if it in basic_components:
                item_score_sum += ITEM_SCORE_COMPONENT
            elif it in completed_items:
                item_score_sum += ITEM_SCORE_COMPLETED
            else:
                raise ValueError(f"존재하지 않는 아이템입니다: {it!r}")

        # 시너지 기여 (고유 챔피언 단위 집계)
        for tr in cinfo["traits"]:
            trait_champions.setdefault(tr, set()).add(cname)

    # 시너지 보너스 계산
    synergy_bonus_sum = 0.0
    active_synergies = []

    for tr, champs in sorted(trait_champions.items()):
        cnt = len(champs)
        bps = TRAIT_BREAKPOINTS.get(tr)
        if bps is None:
            raise ValueError(f"정의되지 않은 시너지입니다: {tr!r}")

        # 도달한 최고 브레이크포인트 인덱스 (1-indexed)
        reached_idx = 0
        for idx_bp, req in enumerate(bps, start=1):
            if cnt >= req:
                reached_idx = idx_bp
            else:
                break

        if reached_idx > 0:
            bonus = (reached_idx ** 1.5) * 2.0
            synergy_bonus_sum += bonus
            active_synergies.append({
                "trait": tr,
                "unit_count": cnt,
                "breakpoint_reached": reached_idx,
                "bonus": bonus,
            })

    total_power = unit_power_sum + item_score_sum + synergy_bonus_sum

    return {
        "total_power": total_power,
        "breakdown": {
            "unit_power": unit_power_sum,
            "item_score": item_score_sum,
            "synergy_bonus": synergy_bonus_sum,
            "active_synergies": active_synergies,
        },
    }
