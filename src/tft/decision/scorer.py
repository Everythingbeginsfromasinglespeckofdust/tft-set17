"""Action Scorer for TFT Decision Engine."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from tft.domain.game_state import GameState
from tft.domain.actions import Action, ActionType
from tft.simulation.models import SimulationResult
from tft.decision.models import ActionScore, Reason

@dataclass(frozen=True)
class DecisionConfig:
    """Decision Engine 및 Action Scorer의 중앙 집중식 가중치 및 설정."""
    horizon: int = 3
    base_survival_weight: float = 0.35
    base_economy_weight: float = 0.25
    base_board_power_weight: float = 0.25
    base_upgrade_weight: float = 0.15
    base_placement_weight: float = 0.0
    crisis_hp_threshold: int = 35
    safe_hp_threshold: int = 65

DEFAULT_DECISION_CONFIG = DecisionConfig()

class ActionScorer:
    """SimulationResult를 종합하여 ActionScore를 산출하는 스코어러 (V1 Baseline)."""

    def __init__(self, config: Optional[DecisionConfig] = None):
        self.config = config or DEFAULT_DECISION_CONFIG

    def score(self, state: GameState, sim_res: SimulationResult) -> ActionScore:
        hp = state.player.hp
        stage = state.stage

        # 1. Determine Contextual Dynamic Weights
        w_surv, w_econ, w_power, w_upg = self._get_contextual_weights(hp)

        # 2. Normalize Individual Simulation Metrics into [0.0, 1.0]
        m_surv = sim_res.survival_probability

        # Economy metric (Normalized against 70G target)
        m_econ = min(1.0, max(0.0, sim_res.expected_gold / 70.0))

        # Board power metric (Normalized against 75.0 target)
        m_power = min(1.0, max(0.0, sim_res.expected_board_power / 75.0))

        # Upgrade probability metric
        m_upg = min(1.0, max(0.0, sim_res.upgrade_probability))

        # 3. Contextual Adjustment: In crisis, dead players cannot spend saved gold
        if hp <= self.config.crisis_hp_threshold:
            if m_surv <= 0.0:
                m_econ *= 0.05 # Heavily devalue saved gold if you die within horizon
            elif sim_res.action.action_type == ActionType.ROLL:
                # Bonus for defensive board stabilization in crisis
                m_power *= 1.25

        # 4. Compute Composite Score
        total_score = (
            w_surv * m_surv +
            w_econ * m_econ +
            w_power * m_power +
            w_upg * m_upg
        )
        total_score = round(min(1.0, total_score), 4)

        # 5. Determine Confidence
        confidence = 0.85
        if sim_res.horizon >= 3:
            confidence = 0.88
        if hp <= self.config.crisis_hp_threshold and sim_res.action.action_type == ActionType.ROLL:
            confidence = 0.92

        # 6. Extract Initial Action Reasons
        reasons = self._generate_action_reasons(state, sim_res, total_score)

        return ActionScore(
            action=sim_res.action,
            score=total_score,
            confidence=confidence,
            metrics={
                "composite_score": total_score,
                "survival_norm": round(m_surv, 4),
                "economy_norm": round(m_econ, 4),
                "power_norm": round(m_power, 4),
                "upgrade_norm": round(m_upg, 4),
                "expected_gold": sim_res.expected_gold,
                "expected_hp": sim_res.expected_hp,
                "expected_board_power": sim_res.expected_board_power,
                "upgrade_prob": sim_res.upgrade_probability,
                "survival_prob": sim_res.survival_probability
            },
            reasons=reasons
        )

    def _get_contextual_weights(self, hp: int) -> tuple[float, float, float, float]:
        """체력 상태에 따른 생존 vs 경제 트레이드오프 동적 가중치 산출."""
        if hp <= self.config.crisis_hp_threshold:
            return 0.50, 0.10, 0.25, 0.15
        elif hp >= self.config.safe_hp_threshold:
            return 0.15, 0.40, 0.25, 0.20
        else:
            return (
                self.config.base_survival_weight,
                self.config.base_economy_weight,
                self.config.base_board_power_weight,
                self.config.base_upgrade_weight
            )

    def _generate_action_reasons(self, state: GameState, sim_res: SimulationResult, score: float) -> List[Reason]:
        reasons = []
        action_type = sim_res.action.action_type

        if action_type == ActionType.ROLL:
            reasons.append(Reason(
                code="ROLL_POWER_INCREASE",
                summary=f"리롤을 통한 예상 보드 파워 {sim_res.expected_board_power:.1f} 달성 (2성 완성 확률 {sim_res.upgrade_probability:.1%})",
                evidence={
                    "upgrade_probability": sim_res.upgrade_probability,
                    "expected_power": sim_res.expected_board_power,
                    "rolls_simulated": sim_res.metadata.get("num_rolls", 0)
                },
                impact=score
            ))
        elif action_type == ActionType.SAVE_GOLD:
            reasons.append(Reason(
                code="SAVE_ECON_GROWTH",
                summary=f"골드 저축을 통해 {sim_res.horizon}턴 후 {sim_res.expected_gold:.0f}G 확보 (이자 극대화)",
                evidence={
                    "start_gold": state.player.gold,
                    "expected_gold": sim_res.expected_gold,
                    "horizon": sim_res.horizon
                },
                impact=score
            ))
        elif action_type == ActionType.LEVEL_UP:
            reasons.append(Reason(
                code="LEVEL_UP_TEMPO",
                summary=f"레벨업으로 보드 정원 확대 및 상위 티어 드랍률 확보",
                evidence={
                    "final_level": sim_res.metadata.get("final_level", state.player.level),
                    "expected_power": sim_res.expected_board_power
                },
                impact=score
            ))

        return reasons
