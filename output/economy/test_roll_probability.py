#!/usr/bin/env python3
"""roll_probability.py 테스트 — 2026-08-24 리뷰(F-R1/F-R2) 반영 회귀 포함.

핵심 회귀 앵커:
- unit_hit_probability("진", 5, 9, 0, 0, 1) → prob_at_least_one_per_roll ≈ 8.06%
  (정확식 1-(1-p)^5; 5×p 근사였다면 8.33%로 나와 실패)
- (..., target_copies_taken=0, cost_tier_copies_taken=80, ...) → ValueError (F-R1)
"""
import json
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import roll_probability as rp  # noqa: E402
import pool_sizes  # noqa: E402

EXPECTED = {1: 29, 2: 22, 3: 18, 4: 10, 5: 9}  # K_c (pool_sizes)
N_BY_COST = {1: 14, 2: 13, 3: 13, 4: 14, 5: 9}  # N_c (07_roster)


@pytest.fixture(autouse=True)
def _fresh_cache():
    rp.clear_cache()
    yield
    rp.clear_cache()


# ---------------------------------------------------------------- 드랍률 로드
def test_load_drop_rates_excludes_level_11():
    table = rp.load_drop_rates()
    assert sorted(table) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert 11 not in table


def test_load_drop_rates_are_percent_to_fraction():
    table = rp.load_drop_rates()
    # 03_drop_rates.json 실측: L5 = 45/33/20/2/0, L9 = 10/17/25/33/15
    assert table[5][1] == pytest.approx(0.45)
    assert table[5][2] == pytest.approx(0.33)
    assert table[5][3] == pytest.approx(0.20)
    assert table[9][5] == pytest.approx(0.15)
    # 각 레벨 합계 100% (1.0)
    for level, pct in table.items():
        assert sum(pct.values()) == pytest.approx(1.0)


def test_drop_rates_row_missing_exists_flag_defaults_true(tmp_path):
    raw = json.load(open(rp.DROP_RATES_JSON, encoding="utf-8"))
    raw["shop_drop_rates"] = [
        {"level": 1, "drop_rate_percent": {"1cost": 100, "2cost": 0, "3cost": 0, "4cost": 0, "5cost": 0}},
        {"level": 2, "drop_rate_percent": {"1cost": 50, "2cost": 50, "3cost": 0, "4cost": 0, "5cost": 0}, "exists_in_game": False},
    ]
    path = tmp_path / "drop.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    table = rp.load_drop_rates(str(path))
    assert sorted(table) == [1]  # flag 없는 1레벨만 로드


# ---------------------------------------------------------------------- 로스터
def test_load_roster_counts():
    roster = rp.load_roster()
    assert {c: roster[c]["count"] for c in sorted(roster)} == N_BY_COST
    assert sum(roster[c]["count"] for c in roster) == 63


def test_load_roster_names_match_counts():
    roster = rp.load_roster()
    for c, info in roster.items():
        assert len(info["names"]) == info["count"] == N_BY_COST[c]
        assert "진" in roster[5]["names"]
        assert "나서스" in roster[1]["names"]


def test_ddragon_fallback_extraction_matches_roster_snapshot(tmp_path):
    """07_roster.json 부재 시 폴백: DDragon 직접 추출도 63명·14/13/13/14/9."""
    extracted = rp._extract_from_ddragon()
    counts = {c: len(v) for c, v in sorted(extracted.items())}
    assert counts == N_BY_COST
    assert sum(counts.values()) == 63
    # 07_roster.json과 이름 단위 일치
    snap = json.load(open(rp.ROSTER_JSON, encoding="utf-8"))
    for c, names in extracted.items():
        assert set(names) == set(snap["champion_names_by_cost"][str(c)])


def test_load_roster_falls_back_when_snapshot_missing(tmp_path):
    missing = tmp_path / "no_roster.json"
    roster = rp.load_roster(roster_path=str(missing))
    assert {c: roster[c]["count"] for c in sorted(roster)} == N_BY_COST


def test_load_roster_count_names_mismatch_raises(tmp_path):
    snap = json.load(open(rp.ROSTER_JSON, encoding="utf-8"))
    snap["champion_count_by_cost"]["5"] = 10  # names(9)와 불일치
    path = tmp_path / "roster.json"
    path.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="무결성"):
        rp.load_roster(roster_path=str(path))


# ------------------------------------------------------------------- 앵커 테스트
def test_anchor_jhin_level9_5cost_one_roll():
    """핵심 회귀 앵커: 진 L9/5코스트 1회 리롤.

    p_slot = 0.15 × 9/81, at_least_one = 1-(1-p)^5 = 8.0601% (정확식).
    5×p 근사(8.3333%)였다면 실패.
    """
    result = rp.unit_hit_probability("진", 5, 9, 0, 0, 1)
    p = 0.15 * 9 / 81
    assert result["prob_per_slot"] == pytest.approx(p, abs=1e-12)
    assert result["prob_at_least_one_per_roll"] == pytest.approx(0.0806014673353912, abs=1e-9)
    assert result["prob_at_least_one_per_roll"] == pytest.approx(1 - (1 - p) ** 5, abs=1e-12)
    # 5×p 근사값과는 0.27%p 이상 차이 (근사 미사용 증명)
    assert result["prob_at_least_one_per_roll"] != pytest.approx(5 * p, abs=1e-3)
    assert result["expected_count_over_rolls"] == pytest.approx(5 * p, abs=1e-12)
    assert result["gold_per_expected_unit"] == pytest.approx(24.0, abs=1e-9)


def test_anchor_nasus_level5_1cost_one_roll():
    result = rp.unit_hit_probability("나서스", 1, 5, 0, 0, 1)
    p = 0.45 * 29 / 406
    assert result["prob_per_slot"] == pytest.approx(p, abs=1e-12)
    assert result["prob_at_least_one_per_roll"] == pytest.approx(
        1 - (1 - p) ** 5, abs=1e-12
    )
    assert result["prob_at_least_one_per_roll"] == pytest.approx(0.15070943843211249, abs=1e-9)


def test_at_least_one_uses_exact_formula_not_approximation():
    """p가 큰 경우 정확식과 5×p 근사의 차이가 실제 반환값과 일치."""
    result = rp.unit_hit_probability("피오라", 5, 10, 0, 0, 1)
    p = 0.25 * 9 / 81
    assert result["prob_per_slot"] == pytest.approx(p, abs=1e-12)
    exact = 1 - (1 - p) ** 5
    approx = 5 * p
    assert abs(exact - approx) > 1e-3  # 이 지점에선 근사 오차가 실재
    assert result["prob_at_least_one_per_roll"] == pytest.approx(exact, abs=1e-12)
    assert result["prob_at_least_one_per_roll"] != pytest.approx(approx, abs=1e-4)


def test_num_rolls_scales_expected_and_gold():
    result = rp.unit_hit_probability("진", 5, 9, 0, 0, 2)
    assert result["expected_count_over_rolls"] == pytest.approx(2 * 5 * 0.15 * 9 / 81, abs=1e-12)
    # 골드 효율은 리롤 횟수에 무관 (2×5p 기대 → 4/(10p) = 2/(5p) = 24)
    assert result["gold_per_expected_unit"] == pytest.approx(24.0, abs=1e-9)


def test_taken_target_with_equal_tier_follows_formula():
    """taken_target=taken_tier=4 → p = 0.15 × (9−4)/(81−4) = 0.15 × 5/77."""
    result = rp.unit_hit_probability("진", 5, 9, 4, 4, 1)["prob_per_slot"]
    assert result == pytest.approx(0.15 * 5 / 77, abs=1e-12)


def test_p_slot_linear_in_target_when_denominator_fixed():
    """분모(tier_taken) 고정 시 p_slot이 target_taken에 대해 정확 선형 (리뷰 [2c])."""
    p0 = rp.unit_hit_probability("진", 5, 9, 0, 40, 1)["prob_per_slot"]
    p4 = rp.unit_hit_probability("진", 5, 9, 4, 40, 1)["prob_per_slot"]
    p9 = rp.unit_hit_probability("진", 5, 9, 9, 40, 1)["prob_per_slot"]
    assert p0 == pytest.approx(0.15 * 9 / 41, abs=1e-12)
    assert p4 == pytest.approx(0.15 * 5 / 41, abs=1e-12)
    assert p9 == 0.0
    assert p4 == pytest.approx(p0 * 5 / 9, abs=1e-12)


def test_other_tier_depletion_concentrates_remaining_pool():
    """대상 외 티어 소모 → 남은 풀에서 대상 비중 상승 (무복위 모델, 리뷰 [2c] 해석 A)."""
    result = rp.unit_hit_probability("진", 5, 9, 0, 40, 1)
    assert result["prob_per_slot"] == pytest.approx(0.15 * 9 / 41, abs=1e-12)
    assert result["prob_at_least_one_per_roll"] == pytest.approx(
        1 - (1 - 0.15 * 9 / 41) ** 5, abs=1e-12
    )


def test_fully_depleted_target_gives_zero_probability():
    result = rp.unit_hit_probability("진", 5, 9, 9, 9, 1)
    assert result["prob_per_slot"] == 0.0
    assert result["prob_at_least_one_per_roll"] == 0.0
    assert result["expected_count_over_rolls"] == 0.0
    assert result["gold_per_expected_unit"] == math.inf


# ------------------------------------------------------------- 검증 (F-R1/F-R2)
def test_anchor_impossible_tier_state_raises_valueerror():
    """회귀 앵커 (F-R1): tier_taken=80, target_taken=0 → 대상 외 80 > 9×8=72 → ValueError."""
    with pytest.raises(ValueError, match="물리적으로 불가능"):
        rp.unit_hit_probability("진", 5, 9, 0, 80, 1)


def test_target_cannot_exceed_its_own_copies():
    with pytest.raises(ValueError, match="초과"):
        rp.unit_hit_probability("진", 5, 9, 10, 10, 1)


def test_tier_taken_cannot_exceed_tier_total():
    with pytest.raises(ValueError, match="티어 전체"):
        rp.unit_hit_probability("진", 5, 9, 0, 82, 1)


def test_tier_taken_cannot_be_less_than_target_taken():
    with pytest.raises(ValueError, match="작을 수 없습니다"):
        rp.unit_hit_probability("진", 5, 9, 3, 2, 1)


def test_negative_taken_raises():
    with pytest.raises(ValueError):
        rp.unit_hit_probability("진", 5, 9, -1, 0, 1)
    with pytest.raises(ValueError):
        rp.unit_hit_probability("진", 5, 9, 0, -1, 1)


def test_level_11_raises_with_available_levels():
    with pytest.raises(ValueError, match="exists_in_game=false"):
        rp.unit_hit_probability("진", 5, 11, 0, 0, 1)


def test_unknown_level_raises():
    with pytest.raises(ValueError, match="로드된 드랍률 테이블에 없습니다"):
        rp.unit_hit_probability("진", 5, 0, 0, 0, 1)
    with pytest.raises(ValueError):
        rp.unit_hit_probability("진", 5, 12, 0, 0, 1)


def test_unknown_champion_raises():
    with pytest.raises(ValueError, match="로스터에 없습니다"):
        rp.unit_hit_probability("아리", 5, 9, 0, 0, 1)


def test_champion_cost_mismatch_raises():
    # 진은 5코스트인데 1코스트로 조회
    with pytest.raises(ValueError, match="로스터에 없습니다"):
        rp.unit_hit_probability("진", 1, 5, 0, 0, 1)


@pytest.mark.parametrize("bad", [True, False])
def test_bool_args_rejected(bad):
    """F-R2: bool은 정수로 묵인하지 않는다 (isinstance(True, int) 함정)."""
    with pytest.raises(ValueError):
        rp.unit_hit_probability("진", 5, 9, 0, 0, bad)  # num_rolls=True → 1 묵금
    with pytest.raises(ValueError):
        rp.unit_hit_probability("진", 5, 9, bad, 0, 1)  # target_copies_taken=False → 0 묵금
    with pytest.raises(ValueError):
        rp.unit_hit_probability(bad, 5, 9, 0, 0, 1)


@pytest.mark.parametrize("bad", [1.0, "5", None, [1]])
def test_non_int_args_rejected(bad):
    with pytest.raises(ValueError):
        rp.unit_hit_probability("진", 5, 9, 0, 0, bad)


def test_zero_rolls_raises():
    with pytest.raises(ValueError, match="1 이상"):
        rp.unit_hit_probability("진", 5, 9, 0, 0, 0)


def test_result_keys():
    result = rp.unit_hit_probability("진", 5, 9, 0, 0, 1)
    assert set(result) == {
        "prob_per_slot",
        "prob_at_least_one_per_roll",
        "expected_count_over_rolls",
        "gold_per_expected_unit",
    }
    assert all(isinstance(v, float) for v in result.values())


# ------------------------------------------------- 데이터 무결성 교차 검증
def test_roster_snapshot_matches_ddragon_now():
    """감사 [3] 재확인: 스냅샷 ↔ DDragon 지금 이 순간 일치."""
    snap = json.load(open(rp.ROSTER_JSON, encoding="utf-8"))
    extracted = rp._extract_from_ddragon()
    for c in N_BY_COST:
        assert set(extracted[c]) == set(snap["champion_names_by_cost"][str(c)])


def test_pool_sizes_and_roster_pool_totals():
    """K_c(외부 검증) × N_c(로스터) = 코스트별 풀 전체 장수."""
    k = pool_sizes.load_pool_sizes()
    for c in N_BY_COST:
        assert k[c] * N_BY_COST[c] == {1: 406, 2: 286, 3: 234, 4: 140, 5: 81}[c]
