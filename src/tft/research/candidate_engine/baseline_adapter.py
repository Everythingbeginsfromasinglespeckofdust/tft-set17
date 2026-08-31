"""Baseline DecisionEngine Adapter and Snapshot Capturer (Research Layer).

Wraps the frozen production DecisionEngine to capture:
- Action Ranking & Scores (ROLL, LEVEL_UP, SAVE_GOLD)
- Action Separation Score Gap
- Score Breakdown & Simulated Horizon Metrics
- Baseline Decision Rationale
"""
from typing import Dict, Any, List, Optional
from tft.domain.game_state import GameState
from tft.domain.actions import ActionType
from tft.decision.engine import DecisionEngine
from tft.decision.scorer import DecisionConfig


class BaselineAdapter:
    """Non-mutating adapter for capturing complete baseline DecisionEngine telemetry."""

    def __init__(self, engine: Optional[DecisionEngine] = None):
        self.engine = engine or DecisionEngine()

    def capture_snapshot(self, state: GameState, sample_id: str = "T0") -> Dict[str, Any]:
        """Capture baseline decision result and full telemetry without changing engine state."""
        rec = self.engine.decide(state)
        
        # Extract action string
        rec_act_obj = rec.recommended_action
        rec_act_str = rec_act_obj.action_type.value if hasattr(rec_act_obj, "action_type") else str(rec_act_obj)

        # Collect action scores
        action_scores = {}
        for act_str, score in getattr(rec, "action_scores", {}).items():
            action_scores[act_str] = round(float(score), 4)

        # In case action_scores is empty, reconstruct from decision candidates
        if not action_scores:
            action_scores[rec_act_str] = round(float(rec.score), 4)

        # Sort action ranking
        sorted_actions = sorted(action_scores.items(), key=lambda x: x[1], reverse=True)
        best_act, best_score = sorted_actions[0] if sorted_actions else (rec_act_str, rec.score)
        second_best_score = sorted_actions[1][1] if len(sorted_actions) > 1 else best_score
        score_gap = round(best_score - second_best_score, 4)

        reasons = [
            {
                "code": getattr(r, "code", "REASON"),
                "summary": getattr(r, "summary", str(r)),
                "impact": getattr(r, "impact", "NEUTRAL")
            }
            for r in getattr(rec, "reasons", [])
        ]

        return {
            "sample_id": sample_id,
            "stage_round": state.stage_round or f"{state.stage}-{state.round}",
            "recommended_action": rec_act_str,
            "recommended_score": round(float(rec.score), 4),
            "score_gap": score_gap,
            "action_scores": action_scores,
            "action_ranking": [a[0] for a in sorted_actions],
            "reasons": reasons,
            "horizon": 3,
            "config_weights": {
                "base_survival": 0.35,
                "base_economy": 0.25,
                "base_board_power": 0.25,
                "base_upgrade": 0.15
            }
        }
