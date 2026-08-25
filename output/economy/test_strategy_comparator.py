#!/usr/bin/env python3
"""strategy_comparator.py 테스트 — 다중 턴 경제·레벨업·리롤 전략 비교 검증.

핵심 회귀 앵커 및 완료 기준:
- 골드 50, 레벨6, xp0 상태에서 3턴 동안 [save_interest, levelup(Lv7), roll(20G/턴, 5코 진)]
  세 전략 비교 시 서로 다른 최종 상태 확인
- F-7 1턴 순서(지출 결정 → 액션/차감 → 잔여 골드 이자) turn_by_turn 로그 검증
"""
import math
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import strategy_comparator as sc
import interest
import reroll
import levelup
import roll_probability as rp


# ---------------------------------------------------------------- 핵심 완료 기준 검증
def test_acceptance_criteria_three_strategies_at_level6():
    """완료 기준: 골드 50, 레벨6, xp0, 3턴 시뮬레이션."""
    strats = [
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
    results = sc.compare_strategies(50, 6, 0, 3, strats)
    assert len(results) == 3

    res_save, res_lvl, res_roll = results[0], results[1], results[2]

    # 1. save_interest
    assert res_save["final_gold"] == 65.0
    assert res_save["final_level"] == 6
    assert res_save["target_hit_prob_cumulative"] is None
    assert [row["end_gold"] for row in res_save["turn_by_turn"]] == [55, 60, 65]

    # 2. levelup (target 7, need 60 XP -> 15 purchases * 2G = 30G)
    assert res_lvl["final_gold"] == 26.0
    assert res_lvl["final_level"] == 7
    assert res_lvl["target_hit_prob_cumulative"] is None
    # Turn 1: 50 - 30 = 20 -> interest 2 -> 22, level=7, xp=0
    # Turn 2: 22 - 0 = 22 -> interest 2 -> 24
    # Turn 3: 24 - 0 = 24 -> interest 2 -> 26
    assert [row["end_gold"] for row in res_lvl["turn_by_turn"]] == [22, 24, 26]
    assert [row["end_level"] for row in res_lvl["turn_by_turn"]] == [7, 7, 7]
    assert res_lvl["turn_by_turn"][0]["gold_spent"] == 30
    assert res_lvl["turn_by_turn"][0]["xp_bought"] == 60

    # 3. roll (20G/turn for 5-cost Jin at Lv6)
    assert res_roll["final_gold"] == 0.0
    assert res_roll["final_level"] == 6
    assert res_roll["target_hit_prob_cumulative"] == 0.0
    # Turn 1: budget 20 -> 10 rolls (20G) -> rem 30 -> interest 3 -> 33
    # Turn 2: budget 20 -> 10 rolls (20G) -> rem 13 -> interest 1 -> 14
    # Turn 3: budget min(14, 20)=14 -> 7 rolls (14G) -> rem 0 -> interest 0 -> 0
    assert [row["end_gold"] for row in res_roll["turn_by_turn"]] == [33, 14, 0]
    assert [row["num_rolls"] for row in res_roll["turn_by_turn"]] == [10, 10, 7]
    assert [row["gold_spent"] for row in res_roll["turn_by_turn"]] == [20, 20, 14]

    # 세 전략의 최종 상태가 모두 다름 확인
    assert res_save["final_gold"] != res_lvl["final_gold"] != res_roll["final_gold"]
    assert res_lvl["final_level"] != res_save["final_level"]


def test_f7_turn_order_invariant_across_all_turns():
    """F-7 불변식: 모든 턴에서 (시작골드 - 지출 = 잔여골드) -> (잔여골드 이자) -> (종료골드) 검증."""
    strats = [
        {"type": "save_interest"},
        {"type": "levelup", "target_level": 8},
        {
            "type": "roll",
            "gold_per_turn": 15,
            "target_champion": "다이애나",
            "target_cost": 3,
            "target_copies_taken": 0,
            "cost_tier_copies_taken": 0,
        },
    ]
    results = sc.compare_strategies(60, 6, 10, 4, strats)

    for res in results:
        for row in res["turn_by_turn"]:
            # (a) & (b): 지출 후 잔여 골드 확인
            assert row["gold_before_interest"] == row["start_gold"] - row["gold_spent"]
            # (c): 잔여 골드 기준 이자 산출 확인
            assert row["interest"] == interest.calculate_interest(row["gold_before_interest"])
            # (c): 종료 골드 = 잔여 골드 + 이자
            assert row["end_gold"] == row["gold_before_interest"] + row["interest"]


# ---------------------------------------------------------------- 전략별 상세 검증
def test_save_interest_compounding():
    strats = [{"type": "save_interest"}]
    res = sc.compare_strategies(15, 6, 0, 3, strats)[0]
    # 15 -> +1 -> 16 -> +1 -> 17 -> +1 -> 18
    assert res["final_gold"] == 18.0
    assert [row["end_gold"] for row in res["turn_by_turn"]] == [16, 17, 18]


def test_levelup_incremental_across_turns():
    """골드가 부족해 여러 턴에 걸쳐 레벨업하는 시나리오."""
    # Lv6 xp0 -> Lv7 (need 60 XP = 30G)
    # 시작 골드 18:
    # Turn 1: 18G -> 9회 구매(18G=36XP) -> Lv6 xp36 -> rem 0 -> int 0 -> end 0G
    # Turn 2: 0G -> need 12G -> buy 0 -> end 0G
    strats = [{"type": "levelup", "target_level": 7}]
    res = sc.compare_strategies(18, 6, 0, 2, strats)[0]

    t1 = res["turn_by_turn"][0]
    assert t1["gold_spent"] == 18
    assert t1["xp_bought"] == 36
    assert t1["end_level"] == 6
    assert t1["end_xp"] == 36
    assert t1["end_gold"] == 0

    t2 = res["turn_by_turn"][1]
    assert t2["gold_spent"] == 0
    assert t2["end_level"] == 6
    assert t2["end_xp"] == 36
    assert t2["end_gold"] == 0


def test_levelup_already_at_or_above_target():
    strats = [{"type": "levelup", "target_level": 6}]
    res = sc.compare_strategies(30, 7, 0, 2, strats)[0]
    assert res["final_gold"] == 36.0 # 30 -> 33 -> 36
    assert res["final_level"] == 7
    assert all(row["gold_spent"] == 0 for row in res["turn_by_turn"])


def test_roll_probability_positive_hit_cumulative():
    """3코스트 다이애나(Lv7 드랍률 35%) 롤 전략 시 누적 확률 증가 검증."""
    strats = [{
        "type": "roll",
        "gold_per_turn": 10,
        "target_champion": "다이애나",
        "target_cost": 3,
        "target_copies_taken": 0,
        "cost_tier_copies_taken": 0,
    }]
    # 7레벨, 30골드, 2턴 (각 턴 10골드=5롤)
    res = sc.compare_strategies(30, 7, 0, 2, strats)[0]

    # Turn 1: 5 rolls
    p_info = rp.unit_hit_probability("다이애나", 3, 7, 0, 0, 5)
    p_slot = p_info["prob_per_slot"]
    p_1turn = 1.0 - (1.0 - p_slot) ** 25
    p_2turns = 1.0 - (1.0 - p_slot) ** 50

    t1 = res["turn_by_turn"][0]
    t2 = res["turn_by_turn"][1]
    assert t1["turn_hit_prob"] == pytest.approx(p_1turn, abs=1e-9)
    assert t1["cumulative_hit_prob"] == pytest.approx(p_1turn, abs=1e-9)
    assert t2["turn_hit_prob"] == pytest.approx(p_1turn, abs=1e-9)
    assert t2["cumulative_hit_prob"] == pytest.approx(p_2turns, abs=1e-9)
    assert res["target_hit_prob_cumulative"] == pytest.approx(p_2turns, abs=1e-9)


def test_roll_gold_per_turn_exceeds_available_gold_natural_limit():
    """gold_per_turn이 보유 골드보다 크면 에러 없이 보유 골드 한도 내에서만 소모."""
    strats = [{
        "type": "roll",
        "gold_per_turn": 100, # 보유 골드(15) 초과
        "target_champion": "나서스",
        "target_cost": 1,
        "target_copies_taken": 0,
        "cost_tier_copies_taken": 0,
    }]
    res = sc.compare_strategies(15, 5, 0, 1, strats)[0]
    t1 = res["turn_by_turn"][0]
    assert t1["num_rolls"] == 7 # floor(15/2) = 7
    assert t1["gold_spent"] == 14
    assert t1["end_gold"] == 1 # 15 - 14 = 1 (+0 이자)


# ---------------------------------------------------------------- 유효성 검증 (F-R1 / F-R2)
@pytest.mark.parametrize("bad_turns", [0, -1, -5])
def test_invalid_num_turns_raises(bad_turns):
    with pytest.raises(ValueError, match="num_turns"):
        sc.compare_strategies(50, 6, 0, bad_turns, [{"type": "save_interest"}])


def test_negative_gold_raises():
    with pytest.raises(ValueError, match="current_gold"):
        sc.compare_strategies(-1, 6, 0, 1, [{"type": "save_interest"}])


def test_negative_xp_raises():
    with pytest.raises(ValueError, match="current_xp"):
        sc.compare_strategies(50, 6, -1, 1, [{"type": "save_interest"}])


def test_invalid_level_raises():
    with pytest.raises(ValueError, match="current_level"):
        sc.compare_strategies(50, 0, 0, 1, [{"type": "save_interest"}])
    with pytest.raises(ValueError, match="current_level"):
        sc.compare_strategies(50, 11, 0, 1, [{"type": "save_interest"}])


def test_physically_impossible_xp_raises():
    with pytest.raises(ValueError, match="물리적으로 불가능"):
        sc.compare_strategies(50, 2, 5, 1, [{"type": "save_interest"}])


@pytest.mark.parametrize("bad_bool", [True, False])
def test_bool_rejected(bad_bool):
    with pytest.raises(ValueError):
        sc.compare_strategies(bad_bool, 6, 0, 1, [{"type": "save_interest"}])
    with pytest.raises(ValueError):
        sc.compare_strategies(50, bad_bool, 0, 1, [{"type": "save_interest"}])
    with pytest.raises(ValueError):
        sc.compare_strategies(50, 6, bad_bool, 1, [{"type": "save_interest"}])
    with pytest.raises(ValueError):
        sc.compare_strategies(50, 6, 0, bad_bool, [{"type": "save_interest"}])


def test_empty_strategies_raises():
    with pytest.raises(ValueError, match="strategies"):
        sc.compare_strategies(50, 6, 0, 1, [])
    with pytest.raises(ValueError, match="strategies"):
        sc.compare_strategies(50, 6, 0, 1, "not_a_list")


def test_unknown_strategy_type_raises():
    with pytest.raises(ValueError, match="전략 타입"):
        sc.compare_strategies(50, 6, 0, 1, [{"type": "invalid_type"}])


def test_missing_strategy_params_raises():
    with pytest.raises(ValueError, match="target_level"):
        sc.compare_strategies(50, 6, 0, 1, [{"type": "levelup"}])
    with pytest.raises(ValueError, match="gold_per_turn"):
        sc.compare_strategies(50, 6, 0, 1, [{"type": "roll"}])
