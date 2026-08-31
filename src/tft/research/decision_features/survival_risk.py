"""TFT Contextual Survival Risk Model Research Module.

Integrates:
- Current HP
- Current Stage / Round
- Stage Base Combat Damage Expectations
- Recent HP Loss Velocity (Trend / Slope)
- Board Strength Benchmark Deficit
"""
import math
from typing import Dict, Optional, Tuple, Any

STAGE_BASE_LOSS_DAMAGE = {
    1: 2,
    2: 4,
    3: 7,
    4: 10,
    5: 14,
    6: 18,
    7: 24
}


class SurvivalRiskModel:
    """Evaluates contextual lethal risk beyond arbitrary static HP thresholds."""

    @staticmethod
    def evaluate_risk(
        hp: int,
        stage: int,
        round_num: int,
        recent_hp_delta: Optional[int] = None,
        stage_benchmark_ratio: float = 1.0
    ) -> Dict[str, Any]:
        """Compute multidimensional survival risk metrics."""
        base_dmg = STAGE_BASE_LOSS_DAMAGE.get(stage, 14)
        
        # Dynamic expected loss damage adjusted for board weakness
        # If board is below benchmark (<1.0), expect heavier round loss damage (more surviving enemy units)
        if stage_benchmark_ratio < 0.75:
            expected_loss_dmg = int(round(base_dmg * 1.35))
        elif stage_benchmark_ratio < 0.90:
            expected_loss_dmg = int(round(base_dmg * 1.15))
        elif stage_benchmark_ratio > 1.25:
            expected_loss_dmg = max(2, int(round(base_dmg * 0.70)))
        else:
            expected_loss_dmg = base_dmg

        # Rounds to lethal elimination under continuous loss
        rounds_to_elim = max(0.1, hp / max(1, expected_loss_dmg))
        
        # Acceleration from recent velocity
        trend_penalty = 0.0
        if recent_hp_delta is not None and recent_hp_delta < -12:
            # Player lost heavy combat last turn
            trend_penalty = min(0.20, abs(recent_hp_delta) * 0.01)

        # Composite Continuous Risk Score [0.0 (safest) to 1.0 (deadly crisis)]
        if hp <= 0:
            risk_score = 1.0
            risk_category = "ELIMINATED"
        elif rounds_to_elim <= 1.0 or hp <= expected_loss_dmg:
            risk_score = min(1.0, 0.92 + trend_penalty)
            risk_category = "ONE_SHOT_LETHAL"
        elif rounds_to_elim <= 2.0 or hp <= 28:
            risk_score = min(0.95, 0.75 + trend_penalty)
            risk_category = "CRITICAL"
        elif rounds_to_elim <= 3.5 or hp <= 50:
            risk_score = min(0.75, 0.45 + trend_penalty)
            risk_category = "HIGH"
        elif hp <= 70:
            risk_score = max(0.15, 0.25 - (0.05 if stage_benchmark_ratio > 1.1 else 0.0))
            risk_category = "MODERATE"
        else:
            risk_score = max(0.02, 0.08 - (0.04 if stage_benchmark_ratio > 1.1 else 0.0))
            risk_category = "SAFE"

        return {
            "hp": hp,
            "stage": stage,
            "stage_base_damage": base_dmg,
            "expected_loss_damage": expected_loss_dmg,
            "rounds_to_elimination": round(rounds_to_elim, 2),
            "risk_score": round(risk_score, 4),
            "risk_category": risk_category,
            "is_lethal_next_round": (hp <= expected_loss_dmg),
            "trend_penalty_applied": round(trend_penalty, 3)
        }
