#!/usr/bin/env python3
"""interest.py 테스트 — 10골드 단위 테이블 회귀 방지 포함.

핵심 회귀 감지선: 15골드 → 이자 1.
(구 5골드 단위 로직이 재발하면 15골드에서 3이 나와 이 테스트가 실패한다.)
"""
import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import interest  # noqa: E402

GOLD_JSON = interest.GOLD_JSON


@pytest.fixture(scope="module")
def rules():
    return interest.load_interest_rules()


def test_loaded_table_is_10_gold_granularity(rules):
    bands, max_interest = rules
    assert [(lo, hi, iv) for lo, hi, iv in bands] == [
        (0, 9, 0),
        (10, 19, 1),
        (20, 29, 2),
        (30, 39, 3),
        (40, 49, 4),
        (50, None, 5),
    ]
    assert max_interest == 5


@pytest.mark.parametrize(
    ("gold", "expected"),
    [
        (0, 0),
        (9, 0),
        (10, 1),
        (15, 1),   # 회귀 앵커: 5골드 단위 재발 시 3 → FAIL
        (20, 2),
        (25, 2),
        (30, 3),
        (35, 3),   # 30-39 밴드 중간값 하드코딩 앵커 (감사 F-4)
        (39, 3),
        (40, 4),
        (47, 4),
        (49, 4),
        (50, 5),   # 상한 시작
        (52, 5),
        (100, 5),
        (1000, 5),
    ],
)
def test_interest_values(gold, expected):
    assert interest.calculate_interest(gold) == expected


def test_anchor_15_gold_is_one():
    """핵심 회귀 앵커: calculate_interest_trajectory(15, 1) → 이자 1."""
    traj = interest.calculate_interest_trajectory(15, 1)
    assert traj[0]["interest"] == 1


def test_trajectory_15_gold_single_turn():
    traj = interest.calculate_interest_trajectory(15, 1)
    assert traj == [{"turn": 1, "start_gold": 15, "interest": 1, "end_gold": 16}]


def test_trajectory_compounds_on_end_gold():
    # 10 → 11 → 12 → 13 (매 턴 종료 골드 기준 이자, 복리)
    traj = interest.calculate_interest_trajectory(10, 3)
    assert [row["start_gold"] for row in traj] == [10, 11, 12]
    assert [row["interest"] for row in traj] == [1, 1, 1]
    assert [row["end_gold"] for row in traj] == [11, 12, 13]


def test_trajectory_cap_band():
    # 49 → +4 → 53 → +5 → 58 (상한 구간 진입 확인)
    traj = interest.calculate_interest_trajectory(49, 2)
    assert [row["interest"] for row in traj] == [4, 5]
    assert traj[1]["end_gold"] == 58


def test_trajectory_single_turn_is_start():
    traj = interest.calculate_interest_trajectory(7, 1)
    assert traj[0] == {"turn": 1, "start_gold": 7, "interest": 0, "end_gold": 7}


def test_negative_gold_raises():
    with pytest.raises(ValueError):
        interest.calculate_interest(-1)
    with pytest.raises(ValueError):
        interest.calculate_interest_trajectory(-5, 1)


def test_bad_turns_raise():
    with pytest.raises(ValueError):
        interest.calculate_interest_trajectory(15, 0)
    with pytest.raises(ValueError):
        interest.calculate_interest_trajectory(15, -1)
    with pytest.raises(ValueError):
        interest.calculate_interest_trajectory(15, 1.0)


def test_bool_rejected():
    with pytest.raises(ValueError):
        interest.calculate_interest(True)
    with pytest.raises(ValueError):
        interest.calculate_interest_trajectory(True, 1)
    with pytest.raises(ValueError):
        interest.calculate_interest_trajectory(15, True)


def test_rules_follow_updated_json(tmp_path):
    """JSON 테이블이 갱신되면 로직이 테이블을 따른다 (하드코딩 없음 증명).

    10골드 단위 테이블을 "20골드 단위"로 바꿨을 때 값이 같이 바뀜을 확인.
    """
    raw = json.load(open(GOLD_JSON, encoding="utf-8"))
    raw["gold"]["interest_table"] = [
        {"gold": "0-19", "interest": 0},
        {"gold": "20-39", "interest": 1},
        {"gold": "40-59", "interest": 2},
        {"gold": "60-99", "interest": 3},
    ]
    path = tmp_path / "xp_gold.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    bands, max_interest = interest.load_interest_rules(str(path))
    assert max_interest == 3
    # 40-49 구간의 값은 새 테이블 기준
    assert bands[2][2] == 2
    # 15골드는 새 테이블에서 0이 됨 (구 10골드 단위 기준 1이 아님을 증명)
    assert bands[0][2] == 0


def test_formula_field_ignored_if_present(tmp_path):
    """F-3 이력: formula 필드가 있어도 테이블이 단일 진원. formula는 무시."""
    raw = json.load(open(GOLD_JSON, encoding="utf-8"))
    raw["gold"]["formula"] = "floor(gold / 5)"  # 의도적으로 상충하는 값
    path = tmp_path / "xp_gold.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    bands, _ = interest.load_interest_rules(str(path))
    # 테이블(10골드 단위) 기준 그대로: 15 → 1
    assert [iv for _, _, iv in bands][1] == 1


def test_docstring_has_no_5_gold_unit_examples():
    """F-1 재발 방지: docstring에 구 5골드 단위 예시(1-5, 6-10 ...)가 없어야 함."""
    doc = interest.__doc__ or ""
    for stale in ("1-5", "6-10", "11-15", "16-20", "21-50", "/ 5)"):
        assert stale not in doc, f"docstring에 구 5골드 단위 예시 잔존: {stale!r}"


def test_module_has_no_5_gold_interest_literals():
    """exec 경로에 5골드 단위 이자 계산을 재현하는 리터럴 조합이 없음을
    간접 확인: 1..99 골드의 계산 결과가 전부 10골드 단위 테이블과 일치."""
    bands, _ = interest.load_interest_rules()
    for gold in range(100):
        expected = None
        for lo, hi, iv in bands:
            if lo <= gold and (hi is None or gold <= hi):
                expected = iv
                break
        assert interest.calculate_interest(gold) == expected
