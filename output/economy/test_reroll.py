#!/usr/bin/env python3
"""reroll.py 테스트 — 고정 2골드 규칙 + 제거된 메커니즘 재발 방지.
"""
import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reroll  # noqa: E402

GOLD_JSON = reroll.GOLD_JSON


@pytest.fixture(scope="module")
def rules():
    return reroll.load_reroll_rules()


def test_reroll_cost_is_2(rules):
    assert rules == {"reroll_cost": 2}


@pytest.mark.parametrize(
    ("gold", "expected"),
    [
        (0, 0),
        (1, 0),
        (2, 1),
        (3, 1),
        (4, 2),
        (19, 9),
        (20, 10),   # 회귀 앵커: reroll_count(20) → 10
        (100, 50),
    ],
)
def test_reroll_count(gold, expected):
    assert reroll.reroll_count(gold) == expected


def test_anchor_20_gold_is_10():
    assert reroll.reroll_count(20) == 10


def test_trajectory_linear_decrement():
    traj = reroll.reroll_trajectory(20, 5)
    assert [row["gold_after"] for row in traj] == [18, 16, 14, 12, 10]
    assert all(row["cost"] == 2 for row in traj)
    assert [row["reroll"] for row in traj] == [1, 2, 3, 4, 5]


def test_trajectory_exhausts_exactly():
    traj = reroll.reroll_trajectory(6, 3)
    assert traj[-1]["gold_after"] == 0


def test_trajectory_over_spend_raises():
    with pytest.raises(ValueError):
        reroll.reroll_trajectory(5, 3)  # floor(5/2)=2 < 3


def test_negative_gold_raises():
    with pytest.raises(ValueError):
        reroll.reroll_count(-1)
    with pytest.raises(ValueError):
        reroll.reroll_trajectory(-2, 1)


def test_bad_num_rerolls_raises():
    with pytest.raises(ValueError):
        reroll.reroll_trajectory(20, 0)
    with pytest.raises(ValueError):
        reroll.reroll_trajectory(20, -1)
    with pytest.raises(ValueError):
        reroll.reroll_trajectory(20, 2.0)


def test_bool_rejected():
    with pytest.raises(ValueError):
        reroll.reroll_count(True)
    with pytest.raises(ValueError):
        reroll.reroll_trajectory(20, True)
    with pytest.raises(ValueError):
        reroll.reroll_trajectory(False, 1)


def test_removed_mechanism_field_is_rejected(tmp_path):
    """구간별 유지율 필드가 JSON에 재발하면 로드 시 즉시 ValueError.

    (제거된 메커니즘이 조용히 무시되는 것보다 실패하는 것이 안전.)
    """
    raw = json.load(open(GOLD_JSON, encoding="utf-8"))
    raw["reroll_discount"] = {"1": 100, "2": 75}
    path = tmp_path / "xp_gold.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="재발"):
        reroll.load_reroll_rules(str(path))


def test_nested_removed_field_also_detected(tmp_path):
    raw = json.load(open(GOLD_JSON, encoding="utf-8"))
    raw["gold"]["reroll_retention_table"] = {}
    path = tmp_path / "xp_gold.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="재발"):
        reroll.load_reroll_rules(str(path))


def test_real_json_has_no_removed_mechanism_keys():
    """실제 05_xp_gold.json에 제거된 메커니즘 키가 없어야 함."""
    raw = json.load(open(GOLD_JSON, encoding="utf-8"))
    assert reroll._forbidden_keys(raw) == []


def test_custom_rules_argument():
    """rules 인자로 비용 오버라이드 가능 (테스트/타입 모드를 위한 확장점)."""
    custom = {"reroll_cost": 3}
    assert reroll.reroll_count(10, rules=custom) == 3
    traj = reroll.reroll_trajectory(9, 2, rules=custom)
    assert [row["gold_after"] for row in traj] == [6, 3]
