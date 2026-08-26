"""Explanation Generator for TFT Decision Engine."""
from typing import Any, Dict, List, Optional
from tft.domain.game_state import GameState
from tft.domain.actions import ActionType
from tft.decision.models import ActionScore, Reason
from tft.simulation.models import SimulationResult

class ExplanationGenerator:
    """Action 간의 정량적 메트릭 비교(Metric Difference)를 기반으로 동적 근거 생성."""

    def generate_comparative_reasons(
        self,
        state: GameState,
        best_score: ActionScore,
        all_scores: List[ActionScore],
        sim_results: Dict[ActionType, SimulationResult]
    ) -> List[Reason]:
        reasons: List[Reason] = []
        hp = state.player.hp
        gold = state.player.gold
        best_type = best_score.action.action_type
        best_sim = sim_results.get(best_type)

        save_sim = sim_results.get(ActionType.SAVE_GOLD)
        roll_sim = sim_results.get(ActionType.ROLL)
        lvl_sim = sim_results.get(ActionType.LEVEL_UP)

        # 1. Primary Recommendation Reason
        if best_type == ActionType.ROLL and roll_sim and save_sim:
            delta_power = roll_sim.expected_board_power - save_sim.expected_board_power
            delta_surv = (roll_sim.survival_probability - save_sim.survival_probability) * 100.0

            if hp <= 35:
                reasons.append(Reason(
                    code="CRISIS_ROLL_DEFENSE",
                    summary=f"체력 위기(HP {hp}): 즉시 리롤로 2성 기물 완성(확률 {roll_sim.upgrade_probability:.1%}) 및 보드 파워 +{delta_power:.1f} 확보로 탈락 방어",
                    evidence={
                        "current_hp": hp,
                        "upgrade_prob": roll_sim.upgrade_probability,
                        "board_power_gain": delta_power,
                        "roll_expected_hp": roll_sim.expected_hp,
                        "save_expected_hp": save_sim.expected_hp
                    },
                    impact=0.95
                ))
            else:
                reasons.append(Reason(
                    code="UPGRADE_ROLL_OPPORTUNITY",
                    summary=f"기물 2성/3성 업그레이드 기대치 높음 (달성 확률 {roll_sim.upgrade_probability:.1%}, 파워 +{delta_power:.1f})",
                    evidence={
                        "upgrade_probability": roll_sim.upgrade_probability,
                        "board_power_gain": delta_power
                    },
                    impact=0.75
                ))

        elif best_type == ActionType.SAVE_GOLD and save_sim:
            reasons.append(Reason(
                code="ECONOMIC_COMPOUNDING",
                summary=f"체력 안전권(HP {hp}): {save_sim.horizon}턴 후 {save_sim.expected_gold:.0f}G(+{save_sim.expected_gold - gold:.0f}G) 복리 이자 극대화 추천",
                evidence={
                    "start_gold": gold,
                    "final_gold": save_sim.expected_gold,
                    "survival_prob": save_sim.survival_probability
                },
                impact=0.85
            ))

        elif best_type == ActionType.LEVEL_UP and lvl_sim and save_sim:
            delta_power = lvl_sim.expected_board_power - save_sim.expected_board_power
            reasons.append(Reason(
                code="TEMPO_LEVEL_UP",
                summary=f"레벨업 적기: 즉시 {lvl_sim.metadata.get('final_level', state.player.level)}레벨 달성으로 보드 정원 확대(파워 +{delta_power:.1f}) 및 상위 코스트 선점",
                evidence={
                    "new_level": lvl_sim.metadata.get("final_level", state.player.level),
                    "power_gain": delta_power,
                    "final_gold": lvl_sim.expected_gold
                },
                impact=0.80
            ))

        # 2. Add alternative trade-off comparison reasons
        for score in all_scores:
            if score.action.action_type != best_type:
                alt_sim = sim_results.get(score.action.action_type)
                if alt_sim and best_sim:
                    score_diff = best_score.score - score.score
                    reasons.append(Reason(
                        code=f"COMPARE_VS_{score.action.action_type.value}",
                        summary=f"{best_type.value} 선택이 {score.action.action_type.value} 대비 종합 점수 +{score_diff:.3f} 우세",
                        evidence={
                            "best_score": best_score.score,
                            "alt_score": score.score,
                            "score_diff": score_diff,
                            "best_gold": best_sim.expected_gold,
                            "alt_gold": alt_sim.expected_gold
                        },
                        impact=round(score_diff, 3)
                    ))

        return reasons
