#!/usr/bin/env python3
"""TFT Set 17 다중 턴 경제·레벨업·리롤 전략 비교기 (Strategy Comparator).

1턴의 정의 (F-7 이중계산/누락 방지 골드 흐름 표준 순서):
------------------------------------------------------------
하나의 턴(라운드) 내 골드 및 상태 변화는 반드시 아래 3단계를 순서대로 거친다:
  (a) 시작 골드/레벨/XP 확인 및 전략별 턴당 지출 예산 결정
  (b) 액션 실행:
      - save_interest: 지출 0
      - levelup: 목표 레벨 도달에 필요한 만큼(또는 보유 골드 한도 내) XP 구매 및 골드 차감
      - roll: 지정된 gold_per_turn 한도(또는 보유 골드 한도) 내에서 리롤 실행, 골드 차감 및 해당 턴 등장 확률 계산
  (c) 턴 종료: 액션 후 '남은 골드(잔여 골드)'를 기준으로 1턴 이자(calculate_interest)를
      지급받아 다음 턴 시작 골드로 복리 이월

데이터/상수 출처:
- 이자: interest.calculate_interest
- 리롤: reroll.reroll_count, reroll.load_reroll_rules
- 레벨업: levelup.gold_to_reach_level, levelup.load_levelup_table
- 롤 확률: roll_probability.unit_hit_probability, roll_probability._check_int
(기존 4개 모듈 재사용 — 재구현 금지)
"""
import copy
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_OUTPUT = os.path.join(_HERE, "..")
if _OUTPUT not in sys.path:
    sys.path.insert(0, _OUTPUT)

from interest import calculate_interest
from reroll import reroll_count, load_reroll_rules
from levelup import gold_to_reach_level, load_levelup_table
from roll_probability import unit_hit_probability, _check_int


def _apply_xp(level: int, xp: int, xp_gained: int, max_level: int, table: dict) -> tuple[int, int]:
    """XP 획득에 따른 레벨업 및 잔여 XP 계산 헬퍼."""
    total_xp = xp + xp_gained
    cur_lvl = level
    while cur_lvl < max_level:
        req = table[cur_lvl + 1]
        if total_xp >= req:
            total_xp -= req
            cur_lvl += 1
        else:
            break
    if cur_lvl >= max_level:
        total_xp = min(total_xp, table[max_level])
    return cur_lvl, total_xp


def compare_strategies(
    current_gold: int,
    current_level: int,
    current_xp: int,
    num_turns: int,
    strategies: list[dict],
) -> list[dict]:
    """현재 골드/레벨/XP 상태에서 여러 전략을 택했을 때 N턴 뒤의 기대 결과를 비교.

    Args:
        current_gold: 현재 보유 골드 (0 이상 정수)
        current_level: 현재 레벨 (1 ~ max_level)
        current_xp: 현재 레벨 바의 진행 XP (0 이상 정수)
        num_turns: 시뮬레이션할 턴 수 (1 이상 정수)
        strategies: 비교할 전략 딕셔너리의 리스트

    Returns:
        각 전략별 시뮬레이션 결과 리스트:
        [
            {
                "strategy": dict,                       # 원본 전략 복사본
                "final_gold": float,                    # N턴 후 최종 골드
                "final_level": int,                     # N턴 후 최종 레벨
                "target_hit_prob_cumulative": float|None,# roll 전략만 누적 확률(0~1), 그 외 None
                "turn_by_turn": list[dict],             # 턴별 상세 실행 내역
            },
            ...
        ]

    Raises:
        ValueError: 정수 검증 실패(bool 포함), 음수 골드/XP, 물리적으로 불가능한 XP,
            num_turns <= 0, 레벨 범위 초과, 유효하지 않은 전략 dict 구조 등.
    """
    # 1. 공통 인자 정수 및 범위 검증
    current_gold = _check_int("current_gold", current_gold)
    current_level = _check_int("current_level", current_level)
    current_xp = _check_int("current_xp", current_xp)
    num_turns = _check_int("num_turns", num_turns)

    if current_gold < 0:
        raise ValueError(f"current_gold는 음수일 수 없습니다: {current_gold}")
    if num_turns <= 0:
        raise ValueError(f"num_turns는 1 이상이어야 합니다: {num_turns}")

    levelup_table = load_levelup_table()
    max_level = max(levelup_table)

    if not 1 <= current_level <= max_level:
        raise ValueError(f"current_level은 1~{max_level} 사이여야 합니다: {current_level}")
    if current_xp < 0:
        raise ValueError(f"current_xp는 음수일 수 없습니다: {current_xp}")

    # 물리적 불가능 상태 교차 검증 (levelup.py 규칙)
    if current_level >= 2:
        if current_xp > levelup_table[current_level]:
            raise ValueError(
                f"current_xp={current_xp}가 {current_level}레벨 도달에 필요한 XP"
                f"({levelup_table[current_level]})를 초과합니다 — 물리적으로 불가능"
            )
    elif current_xp >= levelup_table[2]:
        raise ValueError(
            f"current_xp={current_xp}가 레벨2 도달 필요 XP({levelup_table[2]}) 이상인데 "
            f"current_level=1입니다 — 물리적으로 불가능"
        )

    if not isinstance(strategies, list) or len(strategies) == 0:
        raise ValueError("strategies는 비어있지 않은 list여야 합니다")

    reroll_rules = load_reroll_rules()
    reroll_cost = reroll_rules["reroll_cost"]

    results = []

    # 2. 각 전략별 시뮬레이션
    for strat_raw in strategies:
        if not isinstance(strat_raw, dict):
            raise ValueError(f"각 전략은 dict여야 합니다: {strat_raw!r}")

        strat = copy.deepcopy(strat_raw)
        st_type = strat.get("type")
        if st_type not in ("save_interest", "levelup", "roll"):
            raise ValueError(f"지원하지 않는 전략 타입입니다: {st_type!r}")

        # 전략별 인자 유효성 검증
        if st_type == "levelup":
            if "target_level" not in strat:
                raise ValueError("levelup 전략은 'target_level'이 필요합니다")
            target_level = _check_int("target_level", strat["target_level"])
            if not 1 <= target_level <= max_level:
                raise ValueError(f"target_level은 1~{max_level} 사이여야 합니다: {target_level}")
            buy_cost = _check_int("buy_xp_cost_gold", strat.get("buy_xp_cost_gold", 2))
            buy_amount = _check_int("buy_xp_amount", strat.get("buy_xp_amount", 4))
            if buy_cost <= 0 or buy_amount <= 0:
                raise ValueError("buy_xp_cost_gold와 buy_xp_amount는 양의 정수여야 합니다")

        elif st_type == "roll":
            for req in ("gold_per_turn", "target_champion", "target_cost", "target_copies_taken", "cost_tier_copies_taken"):
                if req not in strat:
                    raise ValueError(f"roll 전략에 필수 항목 '{req}'가 누락되었습니다")
            gold_per_turn = _check_int("gold_per_turn", strat["gold_per_turn"])
            if gold_per_turn < 0:
                raise ValueError(f"gold_per_turn은 0 이상이어야 합니다: {gold_per_turn}")
            target_champ = strat["target_champion"]
            if not isinstance(target_champ, str) or not target_champ:
                raise ValueError(f"target_champion은 비어있지 않은 문자열이어야 합니다: {target_champ!r}")
            target_cost = _check_int("target_cost", strat["target_cost"])
            target_taken = _check_int("target_copies_taken", strat["target_copies_taken"])
            tier_taken = _check_int("cost_tier_copies_taken", strat["cost_tier_copies_taken"])

        # 시뮬레이션 상태 초기화
        gold = current_gold
        level = current_level
        xp = current_xp
        turn_logs = []
        prob_not_hit_total = 1.0

        for turn in range(1, num_turns + 1):
            start_gold = gold
            start_level = level
            start_xp = xp

            if st_type == "save_interest":
                gold_spent = 0
                gold_before_interest = gold
                interest_val = calculate_interest(gold_before_interest)
                end_gold = gold_before_interest + interest_val
                gold = end_gold

                turn_logs.append({
                    "turn": turn,
                    "start_gold": start_gold,
                    "start_level": start_level,
                    "start_xp": start_xp,
                    "action": "save_interest",
                    "gold_spent": 0,
                    "gold_before_interest": gold_before_interest,
                    "interest": interest_val,
                    "end_gold": end_gold,
                    "end_level": level,
                    "end_xp": xp,
                })

            elif st_type == "levelup":
                if level >= target_level:
                    gold_spent = 0
                    xp_bought = 0
                else:
                    needed_gold = gold_to_reach_level(level, xp, target_level, buy_cost, buy_amount)
                    if gold >= needed_gold:
                        gold_spent = needed_gold
                        purchases = needed_gold // buy_cost
                        xp_bought = purchases * buy_amount
                    else:
                        purchases = gold // buy_cost
                        gold_spent = purchases * buy_cost
                        xp_bought = purchases * buy_amount
                    level, xp = _apply_xp(level, xp, xp_bought, max_level, levelup_table)

                gold_before_interest = gold - gold_spent
                interest_val = calculate_interest(gold_before_interest)
                end_gold = gold_before_interest + interest_val
                gold = end_gold

                turn_logs.append({
                    "turn": turn,
                    "start_gold": start_gold,
                    "start_level": start_level,
                    "start_xp": start_xp,
                    "action": "levelup",
                    "gold_spent": gold_spent,
                    "xp_bought": xp_bought,
                    "gold_before_interest": gold_before_interest,
                    "interest": interest_val,
                    "end_gold": end_gold,
                    "end_level": level,
                    "end_xp": xp,
                })

            elif st_type == "roll":
                budget = min(gold, gold_per_turn)
                rolls = reroll_count(budget)
                gold_spent = rolls * reroll_cost

                if rolls > 0:
                    prob_info = unit_hit_probability(
                        target_champ, target_cost, level, target_taken, tier_taken, rolls
                    )
                    p_slot = prob_info["prob_per_slot"]
                    # 1턴(5 * rolls 슬롯) 동안 한 번도 안 나올 확률
                    p_turn_not_hit = (1.0 - p_slot) ** (5 * rolls)
                    p_turn_hit = 1.0 - p_turn_not_hit
                    prob_not_hit_total *= p_turn_not_hit
                else:
                    p_turn_hit = 0.0

                cum_hit_prob = 1.0 - prob_not_hit_total
                gold_before_interest = gold - gold_spent
                interest_val = calculate_interest(gold_before_interest)
                end_gold = gold_before_interest + interest_val
                gold = end_gold

                turn_logs.append({
                    "turn": turn,
                    "start_gold": start_gold,
                    "start_level": start_level,
                    "start_xp": start_xp,
                    "action": "roll",
                    "gold_spent": gold_spent,
                    "num_rolls": rolls,
                    "turn_hit_prob": p_turn_hit,
                    "cumulative_hit_prob": cum_hit_prob,
                    "gold_before_interest": gold_before_interest,
                    "interest": interest_val,
                    "end_gold": end_gold,
                    "end_level": level,
                    "end_xp": xp,
                })

        final_cum_prob = (1.0 - prob_not_hit_total) if st_type == "roll" else None

        results.append({
            "strategy": strat,
            "final_gold": float(gold),
            "final_level": level,
            "target_hit_prob_cumulative": final_cum_prob,
            "turn_by_turn": turn_logs,
        })

    return results


if __name__ == "__main__":
    test_strats = [
        {"type": "save_interest"},
        {"type": "levelup", "target_level": 7},
        {
            "type": "roll",
            "gold_per_turn": 20,
            "target_champion": "진",
            "target_cost": 5,
            "target_copies_taken": 0,
            "cost_tier_copies_taken": 0,
        },
    ]
    res = compare_strategies(50, 6, 0, 3, test_strats)
    import pprint
    pprint.pprint(res)
