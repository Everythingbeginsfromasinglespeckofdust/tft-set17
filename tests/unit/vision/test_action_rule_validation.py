"""Comprehensive Unit Tests for Action Rule Validation Framework."""
import os
import sys
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.vision.rule_metrics import (
    RuleEvaluationMetrics,
    RuleConflict,
    TimingBreakdown,
    FailureCategory
)
from tft.vision.action_rule_validation import ActionRuleValidator
from tft.vision.causal_models import EventCausalTrace


def test_roll_rule_candidate_a():
    """Verify ROLL_A requires gold -2, shop change, not system, board/bench unchanged."""
    v = ActionRuleValidator()
    # Case 1: Valid ROLL_A
    assert v.eval_roll_a(gold_delta=-2, shop_changed=4, is_system_refresh=False, board_unchanged=True, bench_unchanged=True) is True
    # Case 2: System refresh -> False
    assert v.eval_roll_a(gold_delta=-2, shop_changed=4, is_system_refresh=True, board_unchanged=True, bench_unchanged=True) is False
    # Case 3: Bench changed -> False
    assert v.eval_roll_a(gold_delta=-2, shop_changed=4, is_system_refresh=False, board_unchanged=True, bench_unchanged=False) is False


def test_roll_rule_candidate_b():
    """Verify ROLL_B suppresses when buy evidence exists."""
    v = ActionRuleValidator()
    assert v.eval_roll_b(gold_delta=-2, shop_changed=4, is_system_refresh=False, has_buy_evidence=False) is True
    assert v.eval_roll_b(gold_delta=-2, shop_changed=4, is_system_refresh=False, has_buy_evidence=True) is False


def test_roll_rule_candidate_c():
    """Verify ROLL_C does not check board/bench."""
    v = ActionRuleValidator()
    assert v.eval_roll_c(gold_delta=-2, shop_changed=1, is_system_refresh=False) is True
    assert v.eval_roll_c(gold_delta=0, shop_changed=4, is_system_refresh=False) is False


def test_roll_rule_candidate_d():
    """Verify ROLL_D handles collision transitions."""
    v = ActionRuleValidator()
    assert v.eval_roll_d(gold_delta=-2, shop_transition_detected=True, is_system_refresh=False) is True
    assert v.eval_roll_d(gold_delta=-2, shop_transition_detected=False, is_system_refresh=False) is False


def test_buy_rule_candidate_a():
    """Verify BUY_A checks slot emptied, matching champion, cost, not anim."""
    v = ActionRuleValidator()
    assert v.eval_buy_a(shop_slot_emptied=True, matching_champion_added=True, gold_matches_cost=True, is_shop_animation=False) is True
    # Animation frame -> False
    assert v.eval_buy_a(shop_slot_emptied=True, matching_champion_added=True, gold_matches_cost=True, is_shop_animation=True) is False


def test_buy_rule_candidate_b():
    """Verify BUY_B does not require bench addition."""
    v = ActionRuleValidator()
    assert v.eval_buy_b(shop_slot_emptied=True, gold_matches_cost=True, is_shop_animation=False) is True
    assert v.eval_buy_b(shop_slot_emptied=True, gold_matches_cost=False, is_shop_animation=False) is False


def test_buy_rule_candidate_c():
    """Verify BUY_C does not require gold match."""
    v = ActionRuleValidator()
    assert v.eval_buy_c(shop_slot_emptied=True, matching_champion_added=True, is_shop_animation=False) is True
    assert v.eval_buy_c(shop_slot_emptied=False, matching_champion_added=True, is_shop_animation=False) is False


def test_system_refresh_rule():
    """Verify SYSTEM_REFRESH_A detects free shop changes at round transition."""
    v = ActionRuleValidator()
    assert v.eval_system_refresh_a(shop_changed=5, gold_delta=0, is_round_transition=True) is True
    assert v.eval_system_refresh_a(shop_changed=5, gold_delta=-2, is_round_transition=True) is False


def test_animation_rule():
    """Verify SHOP_ANIMATION detects short duration partial empty states."""
    v = ActionRuleValidator()
    assert v.eval_shop_animation(partial_empty_state=True, duration_sec=0.10, followed_by_stable_shop=True) is True
    # Long duration (>0.15s) -> Not transient animation
    assert v.eval_shop_animation(partial_empty_state=True, duration_sec=0.50, followed_by_stable_shop=True) is False


def test_rule_conflict_detection():
    """Verify RuleConflict correctly records multiple triggering rules."""
    conflict = RuleConflict(
        timestamp_sec=343.0,
        ground_truth_action="ROLL",
        triggered_rules=["ROLL_A", "BUY_C"],
        is_resolved=False
    )
    assert len(conflict.triggered_rules) == 2
    assert "ROLL_A" in conflict.triggered_rules
    assert conflict.to_dict()["ground_truth_action"] == "ROLL"


def test_zero_denominator_likelihood_ratio():
    """Verify Likelihood Ratio handles zero denominator cleanly (Infinity / Laplace)."""
    m = RuleEvaluationMetrics(rule_name="TEST_RULE", target_action_type="ROLL", description="Test")
    m.tp = 10
    m.fp = 0
    m.fn = 0
    m.tn = 30
    m.total_target_events = 10
    m.total_non_target_events = 30

    m.calculate_metrics(laplace_alpha=1.0)
    assert m.likelihood_ratio == float("inf")
    assert m.laplace_smoothed_lr > 1.0
    assert m.to_dict()["likelihood_ratio"] == "Infinity"


def test_timing_definition():
    """Verify explicit separation of latency measurements."""
    tb = TimingBreakdown(
        gt_action_time=100.0,
        gold_onset_time=100.05,
        shop_onset_time=100.12,
        shop_stable_time=100.25,
        bench_onset_time=100.18
    )
    assert tb.latency_gold() == pytest.approx(0.05)
    assert tb.latency_shop() == pytest.approx(0.12)
    assert tb.latency_shop_stable() == pytest.approx(0.25)
    assert tb.latency_bench() == pytest.approx(0.18)


def test_same_champion_collision():
    """Verify same-champion collision detection and recording."""
    t = EventCausalTrace("roll_1", "ROLL", None, 343.0, 341.5, 344.5, shop_slots_changed=2, is_same_champion_collision=True)
    assert t.is_same_champion_collision is True
    assert t.shop_slots_changed < 3


def test_rapid_reroll_distribution():
    """Verify inter-reroll interval math."""
    t1_time = 343.0
    t2_time = 344.2
    dt = t2_time - t1_time
    assert dt == pytest.approx(1.2)
    assert dt > 1.0  # classified as >1.00s
