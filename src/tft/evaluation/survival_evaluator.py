"""TFT Survival & Risk Evaluator."""
from tft.domain.game_state import GameState
from tft.evaluation.models import EvaluationResult

class SurvivalEvaluator:
    """HP 잔여량 및 라운드별 탈락 위험도 평가기."""

    def evaluate(self, state: GameState) -> EvaluationResult:
        hp = state.player.hp
        stage = state.stage

        # Stage based base damage estimate per loss
        stage_dmg_est = {2: 4, 3: 7, 4: 11, 5: 15, 6: 19, 7: 24}.get(stage, 15)
        losses_remaining = max(1, hp // stage_dmg_est)

        if hp <= 20:
            risk_level = "CRITICAL"
            risk_score = 0.95
        elif hp <= 40:
            risk_level = "HIGH"
            risk_score = 0.70
        elif hp <= 65:
            risk_level = "MODERATE"
            risk_score = 0.40
        else:
            risk_level = "SAFE"
            risk_score = 0.10

        return EvaluationResult(
            score=risk_score,
            metrics={"hp": hp, "stage": stage, "estimated_losses_to_die": losses_remaining},
            details={"risk_level": risk_level, "estimated_loss_damage": stage_dmg_est},
            evidence=[f"HP: {hp} ({risk_level} risk, ~{losses_remaining} losses remaining in Stage {stage})"]
        )
