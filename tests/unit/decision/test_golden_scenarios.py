"""Unit tests for the 8 Golden Scenarios of Decision Engine."""
import pytest
import sys, os

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.decision.engine import DecisionEngine
from tft.evaluation.golden_scenarios import get_golden_scenarios
from tft.domain.actions import ActionType

def test_all_8_golden_scenarios():
    """Verify all 8 golden reference scenarios produce consistent, deterministic decisions."""
    engine = DecisionEngine(random_seed=42)
    scenarios = get_golden_scenarios()

    assert len(scenarios) == 8

    for sc_id, sc_data in scenarios.items():
        state = sc_data["state"]
        rec = engine.decide(state, horizon=3)

        assert rec.recommended_action is not None
        assert len(rec.all_scores) == 3
        assert rec.decision_margin >= 0.0

        expected_best = sc_data.get("expected_best_action")
        if expected_best is not None:
            assert rec.recommended_action.action_type == expected_best, (
                f"{sc_id} expected {expected_best.value} but got {rec.recommended_action.action_type.value}"
            )
            min_margin = sc_data.get("min_margin", 0.0)
            assert rec.decision_margin >= min_margin - 1e-4

        # Verify all breakdown metrics exist and sum to score
        for a_score in rec.all_scores:
            assert "survival" in a_score.breakdown
            assert "economy" in a_score.breakdown
            assert "board_power" in a_score.breakdown
            assert "upgrade" in a_score.breakdown
            contrib_sum = sum(b.contribution for b in a_score.breakdown.values())
            assert abs(contrib_sum - a_score.score) < 1e-3
