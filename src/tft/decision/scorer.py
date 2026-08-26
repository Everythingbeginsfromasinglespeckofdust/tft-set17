"""Action Scorer for TFT Decision Engine."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from tft.domain.game_state import GameState
from tft.domain.actions import Action, ActionType
from tft.simulation.models import SimulationResult
from tft.decision.models import ActionScore, MetricBreakdown, Reason

@dataclass(frozen=True)
class DecisionConfig:
    """Decision Engine 및 Action Scorer의 중앙 집중식 가중치 및 설정."""
    horizon: int = 3
    base_survival_weight: float = 0.35
    base_economy_weight: float = 0.25
    base_board_power_weight: float = 0.25
    base_upgrade_weight: float = 0.15
    base_placement_weight: float = 0.0
    
    # Normalization baseline parameters (Tunable parameters, not universal constants)
    gold_norm_target: float = 70.0
    power_norm_target: float = 75.0
    crisis_hp_threshold: int = 35
    safe_hp_threshold: int = 65

DEFAULT_DECISION_CONFIG = DecisionConfig()

class ActionScorer:
    """SimulationResult를 종합하여 ActionScore를 산출하는 스코어러 (Traceable V1.1)."""

    def __init__(self, config: Optional[DecisionConfig] = None):
        self.config = config or DEFAULT_DECISION_CONFIG

    def score(self, state: GameState, sim_res: SimulationResult) -> ActionScore:
        hp = state.player.hp
        gold = state.player.gold
        stage = state.stage

        # 1. Contextual Dynamic Weights
        w_surv, w_econ, w_power, w_upg = self._get_contextual_weights(hp)

        # 2. Normalized Dimension Metrics [0.0, 1.0]
        m_surv = max(0.0, min(1.0, sim_res.survival_score))
        m_econ = max(0.0, min(1.0, sim_res.expected_gold / self.config.gold_norm_target))
        m_power = max(0.0, min(1.0, sim_res.expected_board_power / self.config.power_norm_target))
        m_upg = max(0.0, min(1.0, sim_res.any_upgrade_probability))

        # 3. Contextual Adjustment: In crisis, if eliminated within horizon, saved gold is penalized
        if hp <= self.config.crisis_hp_threshold:
            if m_surv <= 0.0:
                m_econ *= 0.05
            elif sim_res.action.action_type == ActionType.ROLL:
                m_power *= 1.25

        # 4. Infeasibility Penalties (e.g. 0 gold to roll or level up)
        infeasible_penalty = 0.0
        feasibility_desc = "Action is valid and executable"
        if sim_res.action.action_type == ActionType.LEVEL_UP and gold < 4:
            infeasible_penalty = -0.02
            feasibility_desc = "Insufficient gold (<4G) to purchase XP"
        elif sim_res.action.action_type == ActionType.ROLL and gold < 2:
            infeasible_penalty = -0.02
            feasibility_desc = "Insufficient gold (<2G) to roll shop"

        # 5. Detailed Traceability Breakdown
        breakdown = {
            "survival": MetricBreakdown(
                raw_value=sim_res.expected_hp,
                normalized_value=round(m_surv, 4),
                weight=w_surv,
                contribution=round(w_surv * m_surv, 4),
                description=f"Expected HP {sim_res.expected_hp:.1f} (Survival Score: {m_surv:.2f})"
            ),
            "economy": MetricBreakdown(
                raw_value=sim_res.expected_gold,
                normalized_value=round(m_econ, 4),
                weight=w_econ,
                contribution=round(w_econ * m_econ, 4),
                description=f"Expected Gold {sim_res.expected_gold:.1f}G (vs {self.config.gold_norm_target:.0f}G target)"
            ),
            "board_power": MetricBreakdown(
                raw_value=sim_res.expected_board_power,
                normalized_value=round(m_power, 4),
                weight=w_power,
                contribution=round(w_power * m_power, 4),
                description=f"Expected Board Power {sim_res.expected_board_power:.1f} (vs {self.config.power_norm_target:.0f} target)"
            ),
            "upgrade": MetricBreakdown(
                raw_value=sim_res.any_upgrade_probability,
                normalized_value=round(m_upg, 4),
                weight=w_upg,
                contribution=round(w_upg * m_upg, 4),
                description=f"Any Upgrade Probability {m_upg:.1%} (Exp Upgrades: {sim_res.expected_upgrade_count:.2f})"
            ),
            "feasibility": MetricBreakdown(
                raw_value=1.0 if infeasible_penalty == 0.0 else 0.0,
                normalized_value=infeasible_penalty,
                weight=1.0,
                contribution=infeasible_penalty,
                description=feasibility_desc
            )
        }

        # 6. Compute Composite Score (Exactly equals sum of breakdown contributions)
        total_score = sum(b.contribution for b in breakdown.values())
        total_score = round(max(0.0, min(1.0, total_score)), 4)

        # 7. Extract Initial Action Reasons
        reasons = self._generate_action_reasons(state, sim_res, total_score)

        return ActionScore(
            action=sim_res.action,
            score=total_score,
            confidence=0.88,
            metrics={
                "composite_score": total_score,
                "survival_norm": round(m_surv, 4),
                "economy_norm": round(m_econ, 4),
                "power_norm": round(m_power, 4),
                "upgrade_norm": round(m_upg, 4),
                "expected_gold": sim_res.expected_gold,
                "expected_hp": sim_res.expected_hp,
                "expected_board_power": sim_res.expected_board_power,
                "upgrade_prob": sim_res.any_upgrade_probability,
                "survival_score": sim_res.survival_score
            },
            breakdown=breakdown,
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
                summary=f"리롤을 통한 예상 보드 파워 {sim_res.expected_board_power:.1f} 달성 (업그레이드 확률 {sim_res.any_upgrade_probability:.1%})",
                evidence={
                    "any_upgrade_prob": sim_res.any_upgrade_probability,
                    "target_probs": sim_res.target_upgrade_probabilities,
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
