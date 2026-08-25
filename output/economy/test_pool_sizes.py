#!/usr/bin/env python3
"""pool_sizes.py 테스트 — 외부 검증 확정값 {1:29, 2:22, 3:18, 4:10, 5:9}.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pool_sizes  # noqa: E402

EXPECTED = {1: 29, 2: 22, 3: 18, 4: 10, 5: 9}


def test_load_returns_verified_values():
    assert pool_sizes.load_pool_sizes() == EXPECTED


def test_keys_are_int_costs_1_to_5():
    sizes = pool_sizes.load_pool_sizes()
    assert sorted(sizes) == [1, 2, 3, 4, 5]
    assert all(isinstance(k, int) and not isinstance(k, bool) for k in sizes)
    assert all(isinstance(v, int) and v > 0 for v in sizes.values())


def test_json_file_matches_module(tmp_path):
    """pool_sizes.json과 load_pool_sizes()가 지금 이 순간 일치 (감사 A-3 재확인)."""
    raw = json.load(open(pool_sizes.POOL_SIZES_JSON, encoding="utf-8"))
    as_int = {int(k): v for k, v in raw["copies_per_champion_by_cost"].items()}
    assert pool_sizes.load_pool_sizes() == as_int == EXPECTED


def test_missing_cost_raises(tmp_path):
    raw = json.load(open(pool_sizes.POOL_SIZES_JSON, encoding="utf-8"))
    del raw["copies_per_champion_by_cost"]["5"]
    path = tmp_path / "pool_sizes.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="5코스트"):
        pool_sizes.load_pool_sizes(str(path))


def test_non_positive_value_raises(tmp_path):
    raw = json.load(open(pool_sizes.POOL_SIZES_JSON, encoding="utf-8"))
    raw["copies_per_champion_by_cost"]["1"] = 0
    path = tmp_path / "pool_sizes.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="양의 정수"):
        pool_sizes.load_pool_sizes(str(path))


def test_bool_value_rejected(tmp_path):
    raw = json.load(open(pool_sizes.POOL_SIZES_JSON, encoding="utf-8"))
    raw["copies_per_champion_by_cost"]["1"] = True
    path = tmp_path / "pool_sizes.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="양의 정수"):
        pool_sizes.load_pool_sizes(str(path))


def test_known_pool_totals():
    """코스트별 풀 전체 장수 (K_c × N_c, N_c=14/13/13/14/9) 참고 검증."""
    n = {1: 14, 2: 13, 3: 13, 4: 14, 5: 9}
    sizes = pool_sizes.load_pool_sizes()
    totals = {c: sizes[c] * n[c] for c in n}
    assert totals == {1: 406, 2: 286, 3: 234, 4: 140, 5: 81}
    assert sum(totals.values()) == 1147
