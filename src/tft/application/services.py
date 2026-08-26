"""TFT Application Services."""
from typing import Any, Dict
from tft.domain.game_state import GameState
from tft.evaluation.board_evaluator import BoardEvaluator
from tft.evaluation.economy_evaluator import EconomyEvaluator
from tft.evaluation.survival_evaluator import SurvivalEvaluator
from tft.decision.engine import DecisionEngine
from tft.data.repositories import get_data_repository

class DecisionService:
    """상위 유스케이스 조율 서비스 (UI/API/CLI가 단일 진입점으로 사용)."""

    def __init__(self, data_repo=None):
        self.data_repo = data_repo or get_data_repository()
        self.engine = DecisionEngine(self.data_repo)
        self.board_eval = BoardEvaluator(self.data_repo)
        self.econ_eval = EconomyEvaluator(self.data_repo)
        self.surv_eval = SurvivalEvaluator()

    def analyze_and_recommend(self, state: GameState) -> Dict[str, Any]:
        b_res = self.board_eval.evaluate(state)
        e_res = self.econ_eval.evaluate(state)
        s_res = self.surv_eval.evaluate(state)
        rec = self.engine.decide(state)

        return {
            "stage_round": state.stage_round,
            "board_evaluation": {
                "total_power": b_res.score,
                "metrics": b_res.metrics,
                "active_synergies": b_res.details.get("active_synergies", [])
            },
            "economy_evaluation": {
                "gold": state.player.gold,
                "level": state.player.level,
                "interest": e_res.metrics.get("current_interest", 0),
                "gold_to_next_level": e_res.metrics.get("gold_to_next_level", 0)
            },
            "survival_evaluation": {
                "hp": state.player.hp,
                "risk_level": s_res.details.get("risk_level", "SAFE")
            },
            "recommendation": {
                "action": rec.recommended_action.action_type.value,
                "score": rec.score,
                "confidence": rec.confidence,
                "reasons": [{"summary": r.summary, "evidence": r.evidence} for r in rec.reasons]
            }
        }
