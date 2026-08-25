#!/usr/bin/env python3
"""TFT Set 17 리롤(상점) 시 특정 챔피언이 나오는 확률 계산.

모델 (무복위, 무교차 검증 포함 — 2026-08-24 리뷰 반영)
-------------------------------------------------------
코스트 c 드랍풀은 K_c(종당 카피 수, pool_sizes.json) × N_c(코스트 c의 서로
다른 챔피언 종류 수, 로스터) 장으로 구성된다. 1슬롯 드랍은 풀에서 무복위로
1장 뽑는 것으로 모델링하며, 특정 대상 챔피언의 슬롯당 확률은

    p_slot = dropRate[level][cost] × (K_c − taken_target) / (K_c·N_c − taken_tier)

여기서 taken_target은 대상 챔피언이 이미 소모된 장수, taken_tier는 같은
코스트 티어 전체 소모 장수(대상 포함)이다.

5슬롯 상점에서 최소 1개 이상 나오는 확률은 정확식 사용(5×p 근사 금지):

    P(≥1) = 1 − (1 − p_slot)^SHOP_SLOTS

기대 개수는 슬롯 독립을 가정하지 않아도 성립(기댓값의 선형성):

    E = num_rolls × SHOP_SLOTS × p_slot

    골드/기대 1장 = num_rolls × reroll_cost / E   (E=0이면 inf)

데이터 출처 (모든 상수는 JSON — 하드코딩 금지)
----------------------------------------------
- 드랍률:   tft_guide/03_drop_rates.json `shop_drop_rates`
  (레벨 11은 `exists_in_game: false` — Set 14 잔재이므로 로드 시 제외)
- 로스터 N_c: tft_guide/07_roster.json (존재 시), 없으면
  TFT_DDragon/data/ko_KR/champion.json에서 직접 추출
  (TFT17_ prefix + `_TraitClone` 클론 제외 + cost 1~5만)
- 리롤 비용: tft_guide/05_xp_gold.json `reroll_cost`
- K_c:      pool_sizes.json (pool_sizes.load_pool_sizes)

예외
----
- 로스터에 없는 챔피언 이름, 로드되지 않은 레벨(11 포함), 음수/범위 밖
  taken, `tier_taken − target_taken > K_c×(N_c−1)` (대상 외 소모가 대상 외
  전체 장수를 초과 — 물리적으로 불가능) 등 모두 ValueError.
- 정수 검증은 `isinstance(x, int) and not isinstance(x, bool)` (bool 오인 금지).
"""
import json
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUIDE = os.path.join(_HERE, "..", "tft_guide")
DROP_RATES_JSON = os.path.join(_GUIDE, "03_drop_rates.json")
ROSTER_JSON = os.path.join(_GUIDE, "07_roster.json")
GOLD_JSON = os.path.join(_GUIDE, "05_xp_gold.json")
DDRAGON_CHAMPION_JSON = os.path.join(
    _HERE, "..", "..", "TFT_DDragon", "data", "ko_KR", "champion.json"
)

# 상점 슬롯 수. 어떤 데이터 파일(DDragon/CDN/가이드 JSON)에도 존재하지 않는
# 클라이언트 구조 상수이며 추가할 소스도 없으므로 하드코딩 허용
# (2026-08-24 감사 F-6, 구조상 사실 — 데이터가 아닌 규칙).
SHOP_SLOTS = 5

_cache = {}


def _is_int(value):
    """정수 검증 (bool은 정수로 취급하지 않음 — isinstance(True, int)가 True이므로)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _check_int(name, value):
    if not _is_int(value):
        raise ValueError(f"{name}는 정수여야 합니다: {value!r}")
    return value


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _set_number():
    return _load_json(DROP_RATES_JSON).get("set")


def _costs():
    """드랍률 JSON에서 사용 가능한 코스트 목록(정수, 오름차순)."""
    pct = _load_json(DROP_RATES_JSON)["shop_drop_rates"][0]["drop_rate_percent"]
    return sorted(int(k[:-len("cost")]) for k in pct if k.endswith("cost"))


def load_drop_rates(path: str = DROP_RATES_JSON) -> dict:
    """03_drop_rates.json의 shop_drop_rates를 {level: {cost: 확률(0~1 소수)}}로 로드.

    `exists_in_game: false` 행(레벨 11 — Set 14 잔재)은 게임에 존재하지 않아
    로드 시 제외한다.

    Raises:
        ValueError: 레벨이 중복되거나 드랍률 행이 없으면.
    """
    raw = _load_json(path)
    rows = raw.get("shop_drop_rates")
    if not isinstance(rows, list) or not rows:
        raise ValueError("03_drop_rates.json에 shop_drop_rates가 없습니다")
    table = {}
    for row in rows:
        if row.get("exists_in_game", True) is False:
            continue
        level = row["level"]
        if level in table:
            raise ValueError(f"레벨 {level} 드랍률 행이 중복됩니다")
        pct = row["drop_rate_percent"]
        table[level] = {
            int(k[:-len("cost")]): pct[k] / 100.0
            for k in pct
            if k.endswith("cost")
        }
    if not table:
        raise ValueError("exists_in_game=true 드랍률 행이 하나도 없습니다")
    return table


def _extract_from_ddragon(ddragon_path: str = DDRAGON_CHAMPION_JSON) -> dict:
    """champion.json에서 Set 17 상점 챔피언 직접 추출 (07_roster.json 부재 시 폴백).

    TFT<set>_ prefix 필터 + `_TraitClone`(트레잇 표시용 클론) 제외 +
    cost 1~5만 유지(cost 0의 가짜 유닛·적 유닛 제외).
    """
    prefix = f"TFT{_set_number()}_"
    costs = _costs()
    data = _load_json(ddragon_path).get("data", {})
    names_by_cost = {c: [] for c in costs}
    for entry in data.values():
        cid = entry.get("id", "")
        if not cid.startswith(prefix):
            continue
        if "_TraitClone" in cid:
            continue
        cost = entry.get("cost")
        if cost not in costs:
            continue
        names_by_cost[cost].append(entry["name"])
    return names_by_cost


def load_roster(roster_path: str = ROSTER_JSON, ddragon_path: str = DDRAGON_CHAMPION_JSON) -> dict:
    """코스트별 서로 다른 상점 챔피언 종류 수(N_c) + 이름 목록을 로드.

    07_roster.json이 있으면 그 스냅샷을 사용(스냅샷 ↔ names 길이 무결성 검증).
    없으면 champion.json에서 직접 추출(위 폴백).

    Returns:
        {cost: {"count": N_c, "names": [한국어 이름, ...]}}
    """
    costs = _costs()
    if os.path.exists(roster_path):
        raw = _load_json(roster_path)
        names_by_cost = {
            int(k): list(v) for k, v in raw["champion_names_by_cost"].items()
        }
        counts = {int(k): v for k, v in raw["champion_count_by_cost"].items()}
    else:
        names_by_cost = _extract_from_ddragon(ddragon_path)
        counts = {c: len(names_by_cost.get(c, [])) for c in costs}

    out = {}
    for cost in costs:
        names = names_by_cost.get(cost, [])
        count = counts.get(cost)
        if count != len(names):
            raise ValueError(
                f"{cost}코스트 로스터 무결성 오류: count={count}, names 길이={len(names)}"
            )
        if count <= 0:
            raise ValueError(f"{cost}코스트 상점 챔피언이 0종입니다 — 로스터/필터링 재검토 필요")
        out[cost] = {"count": count, "names": names}
    return out


def load_reroll_cost(path: str = GOLD_JSON) -> int:
    """05_xp_gold.json의 reroll_cost 로드."""
    cost = _load_json(path).get("reroll_cost")
    if not _is_int(cost) or cost <= 0:
        raise ValueError(f"reroll_cost는 양의 정수여야 합니다: {cost!r}")
    return cost


def _get(name, loader):
    if name not in _cache:
        _cache[name] = loader()
    return _cache[name]


def clear_cache() -> None:
    """JSON 재로드 테스트용 캐시 초기화."""
    _cache.clear()


def unit_hit_probability(
    target_champion: str,
    target_cost: int,
    level: int,
    target_copies_taken: int,
    cost_tier_copies_taken: int,
    num_rolls: int,
) -> dict:
    """리롤 num_rolls회 중 대상 챔피언이 나오는 확률 지표 반환.

    Args:
        target_champion: Set 17 챔피언 한국어 이름 (로스터 기준)
        target_cost: 1~5
        level: 로드된 드랍률 테이블에 존재하는 레벨 (1~10, 11 제외)
        target_copies_taken: 대상 챔피언이 이미 소모된 장수 (0 이상)
        cost_tier_copies_taken: 같은 코스트 티어 전체 소모 장수 (대상 포함)
        num_rolls: 리롤 횟수 (1 이상)

    Returns:
        {
            "prob_per_slot": float,               # 0~1
            "prob_at_least_one_per_roll": float,  # 1-(1-p)^SHOP_SLOTS 정확식
            "expected_count_over_rolls": float,
            "gold_per_expected_unit": float,      # 기대 0이면 inf
        }

    Raises:
        ValueError: 인자 검증 실패 (타입/범위/로스터 불일치/레벨 미로드/
            대상 외 소모가 대상 외 전체 장수 초과 등).
    """
    if not isinstance(target_champion, str) or not target_champion:
        raise ValueError(f"target_champion은 비어있지 않은 문자열이어야 합니다: {target_champion!r}")
    target_cost = _check_int("target_cost", target_cost)
    level = _check_int("level", level)
    target_copies_taken = _check_int("target_copies_taken", target_copies_taken)
    cost_tier_copies_taken = _check_int("cost_tier_copies_taken", cost_tier_copies_taken)
    num_rolls = _check_int("num_rolls", num_rolls)

    drop_rates = _get("drop_rates", load_drop_rates)
    if level not in drop_rates:
        raise ValueError(
            f"레벨 {level}은/는 로드된 드랍률 테이블에 없습니다. "
            f"exists_in_game=false 레벨(예: 11)은 게임에 존재하지 않아 로드 시 제외됩니다. "
            f"사용 가능한 레벨: {sorted(drop_rates)}"
        )
    if target_cost not in drop_rates[level]:
        raise ValueError(f"{level}레벨 {target_cost}코스트 드랍률이 없습니다")
    if num_rolls < 1:
        raise ValueError(f"num_rolls는 1 이상이어야 합니다: {num_rolls}")

    roster = _get("roster", load_roster)
    if target_cost not in roster:
        raise ValueError(f"{target_cost}코스트가 로스터에 없습니다: {sorted(roster)}")
    cost_info = roster[target_cost]
    n_varieties = cost_info["count"]
    if target_champion not in cost_info["names"]:
        raise ValueError(
            f"챔피언 '{target_champion}'은/는 {target_cost}코스트 로스터에 없습니다. "
            f"코스트별 종류 수: { {c: roster[c]['count'] for c in sorted(roster)} }"
        )

    pool_sizes = _get("pool_sizes", _pool_sizes_loader)
    k_copies = pool_sizes[target_cost]

    if target_copies_taken < 0:
        raise ValueError(f"target_copies_taken은 0 이상이어야 합니다: {target_copies_taken}")
    if target_copies_taken > k_copies:
        raise ValueError(
            f"target_copies_taken={target_copies_taken}이/가 {target_cost}코스트 "
            f"1종 카피 수({k_copies})를 초과합니다"
        )
    tier_total = k_copies * n_varieties
    if cost_tier_copies_taken < 0:
        raise ValueError(f"cost_tier_copies_taken은 0 이상이어야 합니다: {cost_tier_copies_taken}")
    if cost_tier_copies_taken < target_copies_taken:
        raise ValueError(
            f"cost_tier_copies_taken={cost_tier_copies_taken}은/는 대상 소모 "
            f"({target_copies_taken})보다 작을 수 없습니다"
        )
    if cost_tier_copies_taken > tier_total:
        raise ValueError(
            f"cost_tier_copies_taken={cost_tier_copies_taken}이/가 {target_cost}코스트 "
            f"티어 전체 장수({tier_total})를 초과합니다"
        )
    # 교차 검증 (리뷰 F-R1): 대상 외 소모는 대상 외 전체 장수 K_c×(N_c−1) 초과 불가.
    if cost_tier_copies_taken - target_copies_taken > k_copies * (n_varieties - 1):
        raise ValueError(
            f"cost_tier_copies_taken={cost_tier_copies_taken}, target_copies_taken="
            f"{target_copies_taken}은 물리적으로 불가능합니다: 대상 외 소모 "
            f"({cost_tier_copies_taken - target_copies_taken})가 대상 외 전체 장수 "
            f"({k_copies}×{n_varieties - 1}={k_copies * (n_varieties - 1)})를 초과합니다"
        )

    drop_rate = drop_rates[level][target_cost]
    remaining_target = k_copies - target_copies_taken
    remaining_tier = tier_total - cost_tier_copies_taken
    p_slot = drop_rate * remaining_target / remaining_tier

    p_at_least_one = 1.0 - (1.0 - p_slot) ** SHOP_SLOTS
    expected = num_rolls * SHOP_SLOTS * p_slot
    reroll_cost = _get("reroll_cost", load_reroll_cost)
    gold_per_unit = (
        math.inf if expected == 0 else num_rolls * reroll_cost / expected
    )

    return {
        "prob_per_slot": p_slot,
        "prob_at_least_one_per_roll": p_at_least_one,
        "expected_count_over_rolls": expected,
        "gold_per_expected_unit": gold_per_unit,
    }


def _pool_sizes_loader():
    from pool_sizes import load_pool_sizes

    return load_pool_sizes()


if __name__ == "__main__":
    # 회귀 앵커: 진(L9/5코스트) 1회 리롤
    result = unit_hit_probability("진", 5, 9, 0, 0, 1)
    for key, value in result.items():
        print(f"{key}: {value}")
