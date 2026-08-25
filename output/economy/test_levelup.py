#!/usr/bin/env python3
"""levelup.py 테스트 — 레벨업 XP 테이블 로드 + XP 구매 골드 계산.

핵심 회귀 앵커:
- 레벨6 → 레벨7: 필요 XP 60, 2골드=4XP → 15회 구매 → 30골드
- load_levelup_table()이 05_xp_gold.json의 level_up_xp와 1:1 일치
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import levelup  # noqa: E402

GOLD_JSON = levelup.GOLD_JSON

# 05_xp_gold.json 기준값 (2/6/10/20/36/60/68/68/68)
EXPECTED_TABLE = {2: 2, 3: 6, 4: 10, 5: 20, 6: 36, 7: 60, 8: 68, 9: 68, 10: 68}


# ------------------------------------------------------------- 테이블 로드
def test_table_matches_json_1_to_1():
    """load_levelup_table() ↔ 05_xp_gold.json level_up_xp 1:1 일치."""
    table = levelup.load_levelup_table()
    raw = json.load(open(GOLD_JSON, encoding="utf-8"))
    from_json = {row["to_level"]: row["xp_required"] for row in raw["level_up_xp"]}
    assert table == from_json
    # 각 행의 from→to 연속성도 그대로 유지
    for row in raw["level_up_xp"]:
        assert table[row["to_level"]] == row["xp_required"]
        assert row["to_level"] - row["from_level"] == 1


def test_table_expected_values():
    assert levelup.load_levelup_table() == EXPECTED_TABLE


def test_table_covers_2_to_max_level():
    table = levelup.load_levelup_table()
    raw = json.load(open(GOLD_JSON, encoding="utf-8"))
    assert sorted(table) == list(range(2, raw["max_level"] + 1))
    assert max(table) == raw["max_level"]


def test_table_rejects_gap(tmp_path):
    raw = json.load(open(GOLD_JSON, encoding="utf-8"))
    raw["level_up_xp"] = [r for r in raw["level_up_xp"] if r["to_level"] != 5]
    path = tmp_path / "xp_gold.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="연속 체인"):
        levelup.load_levelup_table(str(path))


def test_table_rejects_duplicate(tmp_path):
    raw = json.load(open(GOLD_JSON, encoding="utf-8"))
    raw["level_up_xp"] = raw["level_up_xp"] + [{"from_level": 6, "to_level": 7, "xp_required": 99}]
    path = tmp_path / "xp_gold.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="중복"):
        levelup.load_levelup_table(str(path))


def test_table_rejects_non_consecutive_row(tmp_path):
    raw = json.load(open(GOLD_JSON, encoding="utf-8"))
    raw["level_up_xp"][0] = {"from_level": 1, "to_level": 3, "xp_required": 2}
    path = tmp_path / "xp_gold.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="연속 레벨"):
        levelup.load_levelup_table(str(path))


# ------------------------------------------------------------------ 계산
def test_anchor_level6_to_level7_is_30_gold():
    """회귀 앵커: L6→L7 필요 XP 60, 2골드=4XP → 15회 구매 → 30골드.

    과정: purchases = ceil(60 / 4) = 15, gold = 15 × 2 = 30.
    """
    assert levelup.gold_to_reach_level(6, 0, 7) == 30


def test_anchor_step_by_step():
    """앵커 계산 과정 검증 (buy_xp 로직 재검토용)."""
    xp_needed = EXPECTED_TABLE[7]  # 60
    assert xp_needed == 60
    purchases = -(-xp_needed // 4)  # ceil
    assert purchases == 15
    assert purchases * 2 == 30
    assert levelup.gold_to_reach_level(6, 0, 7) == purchases * 2


@pytest.mark.parametrize(
    ("cl", "cxp", "tl", "expected"),
    [
        # 이미 도달/초과
        (5, 0, 5, 0),
        (9, 68, 10, 0),    # L9 바 꽉 채움(xp=68) → 68−68=0 필요 → 0골드
        (10, 0, 10, 0),
        (10, 68, 10, 0),
        # L1 (current_xp 유효 범위 0~1 — xp>=2는 L2 도달이므로 교차검증으로 차단)
        (1, 0, 2, 2),    # need 2 → ceil(2/4)=1 → 2골드
        (1, 1, 2, 2),    # need 1 → 1 → 2골드
        (1, 0, 3, 4),    # need 8 → 2 → 4골드
        (1, 1, 3, 4),    # need 7 → 2 → 4골드
        (1, 0, 5, 20),   # need 38 → ceil(38/4)=10 → 20골드
        # L2
        (2, 0, 4, 8),    # need 6+10=16 → 4 → 8골드
        (2, 1, 4, 8),    # need 15 → 4 → 8골드
        (2, 2, 4, 8),    # need 14 → 4 → 8골드
        # L3
        (3, 0, 4, 6),    # need 10 → ceil(10/4)=3 → 6골드
        # L6
        (6, 0, 7, 30),   # need 60 → 15 → 30골드 (앵커)
        (6, 0, 8, 64),   # need 60+68=128 → 32 → 64골드
        (6, 0, 10, 132), # need 60+68+68+68=264 → 66 → 132골드
        (6, 36, 7, 12),  # L6 xp=36 → need 60−36=24 → ceil(24/4)=6 → 12골드
        # L7~L10 (68 XP 구간)
        (7, 0, 8, 34),   # need 68 → 17 → 34골드
        (9, 0, 10, 34),  # need 68 → 34골드
    ],
)
def test_gold_to_reach_level_values(cl, cxp, tl, expected):
    assert levelup.gold_to_reach_level(cl, cxp, tl) == expected


def test_level1_to_level5():
    """L1 xp0 → L5: need = 2+6+10+20 = 38 → ceil(38/4)=10 → 20골드."""
    assert levelup.gold_to_reach_level(1, 0, 5) == 20


def test_custom_buy_cost():
    """구매 단가 오버라이드: 3골드=6XP → L6→L7 need 60 → 10회 → 30골드."""
    assert levelup.gold_to_reach_level(6, 0, 7, buy_xp_cost_gold=3, buy_xp_amount=6) == 30


def test_custom_buy_cost_5_gold_20xp():
    """5골드=20XP → L6→L7 need 60 → 3회 → 15골드."""
    assert levelup.gold_to_reach_level(6, 0, 7, buy_xp_cost_gold=5, buy_xp_amount=20) == 15


def test_partial_xp_counts_toward_target():
    """진행 XP가 필요 구매 횟수를 줄인다: L1 xp1→L3 (need 7 → 2회) vs xp0 (need 8 → 2회)."""
    assert levelup.gold_to_reach_level(1, 1, 3) == 4
    assert levelup.gold_to_reach_level(1, 0, 3) == 4
    # L2 xp1→L4: need 15 → 4회; L2 xp2→L4: need 14 → 4회 (같은 8골드)
    assert levelup.gold_to_reach_level(2, 1, 4) == 8
    assert levelup.gold_to_reach_level(2, 2, 4) == 8


# ------------------------------------------------------------------ 검증
@pytest.mark.parametrize("arg_idx", range(3))
@pytest.mark.parametrize("bad", [True, False])
def test_bool_args_rejected(arg_idx, bad):
    """F-R2 패턴: bool은 정수로 묵인하지 않는다."""
    args = [2, 0, 5]
    args[arg_idx] = bad
    with pytest.raises(ValueError):
        levelup.gold_to_reach_level(*args)


@pytest.mark.parametrize("bad", [2.0, "2", None, [2]])
def test_non_int_args_rejected(bad):
    with pytest.raises(ValueError):
        levelup.gold_to_reach_level(bad, 0, 5)
    with pytest.raises(ValueError):
        levelup.gold_to_reach_level(2, bad, 5)
    with pytest.raises(ValueError):
        levelup.gold_to_reach_level(2, 0, bad)


def test_negative_xp_raises():
    with pytest.raises(ValueError, match="음수"):
        levelup.gold_to_reach_level(2, -1, 5)
    with pytest.raises(ValueError, match="음수"):
        levelup.gold_to_reach_level(1, -1, 2)


def test_invalid_levels_raise():
    with pytest.raises(ValueError, match="current_level"):
        levelup.gold_to_reach_level(0, 0, 5)
    with pytest.raises(ValueError, match="target_level"):
        levelup.gold_to_reach_level(2, 0, 11)  # max_level(10) 초과 — 회귀 핵심
    with pytest.raises(ValueError, match="current_level"):
        levelup.gold_to_reach_level(11, 0, 5)


def test_cross_check_xp_exceeds_level_requirement():
    """티켓 예시: L2 도달 필요 XP 2인데 current_level=2, current_xp=5 → ValueError."""
    with pytest.raises(ValueError, match="물리적으로 불가능"):
        levelup.gold_to_reach_level(2, 5, 5)


def test_cross_check_level1_full_bar():
    """L1에서 xp=2(=L2 도달 필요 XP)이면 이미 레벨 2이므로 불가능."""
    with pytest.raises(ValueError, match="물리적으로 불가능"):
        levelup.gold_to_reach_level(1, 2, 5)


def test_cross_check_boundary_is_valid():
    """경계값: current_xp == table[current_level] (바 완전 충전)는 허용."""
    assert levelup.gold_to_reach_level(2, 2, 4) == 8    # need 16−2=14 → 4회
    assert levelup.gold_to_reach_level(6, 36, 7) == 12  # need 60−36=24 → 6회
    assert levelup.gold_to_reach_level(9, 68, 10) == 0  # need 68−68=0 → 도달


def test_invalid_buy_params_raise():
    with pytest.raises(ValueError, match="양의 정수"):
        levelup.gold_to_reach_level(2, 0, 5, buy_xp_cost_gold=0)
    with pytest.raises(ValueError, match="양의 정수"):
        levelup.gold_to_reach_level(2, 0, 5, buy_xp_amount=0)
    with pytest.raises(ValueError):
        levelup.gold_to_reach_level(2, 0, 5, buy_xp_cost_gold=True)
