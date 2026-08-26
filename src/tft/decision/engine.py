"""TFT Core Decision Engine."""
from typing import List
from tft.domain.game_state import GameState
from tft.domain.actions import Action, ActionType
from tft.evaluation.board_evaluator import BoardEvaluator
from tft.evaluation.economy_evaluator import EconomyEvaluator
from tft.evaluation.survival_evaluator import SurvivalEvaluator
from tft.simulation.future_state import FutureStateSimulator
from tft.decision.models import ActionScore, Recommendation, Reason

class DecisionEngine:
    """GameState를 입력받아 다각도 평가 및 시뮬레이션을 통해 최적 Recommendation 도출."""

    def __init__(self, data_repo=None):
        self.board_eval = BoardEvaluator(data_repo)
        self.econ_eval = EconomyEvaluator(data_repo)
        self.surv_eval = SurvivalEvaluator()
        self.simulator = FutureStateSimulator(data_repo)

    def decide(self, state: GameState) -> Recommendation:
        b_res = self.board_eval.evaluate(state)
        e_res = self.econ_eval.evaluate(state)
        s_res = self.surv_eval.evaluate(state)

        hp = state.player.hp
        gold = state.player.gold
        level = state.player.level
        power = b_res.score
        gold_needed = e_res.metrics.get("gold_to_next_level", 0)

        scores: List[ActionScore] = []
        reasons: List[Reason] = []

        # 1. Evaluate LEVEL_UP
        if level < 10 and gold >= gold_needed and gold_needed > 0:
            lvl_score = 0.85 if hp > 30 else 0.70
            scores.append(ActionScore(
                action=Action(ActionType.LEVEL_UP, target_level=level+1, budget_gold=int(gold_needed)),
                score=lvl_score,
                confidence=0.90,
                projected_gold=int(gold - gold_needed),
                projected_power_delta=10.0
            ))

        # 2. Evaluate ROLL
        if hp <= 35: # Crisis -> Roll to stabilize
            roll_score = 0.90
            scores.append(ActionScore(
                action=Action(ActionType.ROLL, budget_gold=min(gold, 30)),
                score=roll_score,
                confidence=0.88,
                projected_gold=max(0, int(gold - 30)),
                projected_power_delta=15.0
            ))
            reasons.append(Reason(
                summary="체력 위기 상태로 즉각적인 리롤 2성작 필요",
                evidence=f"현재 HP={hp} (위험 수준), 2성작으로 라운드 패배 데미지 방어 시급",
                impact=0.90
            ))
        else:
            roll_score = 0.40 if gold >= 50 else 0.20
            scores.append(ActionScore(
                action=Action(ActionType.ROLL, budget_gold=max(0, int(gold - 50))),
                score=roll_score,
                confidence=0.75,
                projected_gold=50,
                projected_power_delta=5.0
            ))

        # 3. Evaluate SAVE_GOLD
        if hp > 40 and gold < 50:
            save_score = 0.80
            reasons.append(Reason(
                summary="50골드 복리 이자 확보를 위한 골드 저축 추천",
                evidence=f"현재 HP {hp}로 안전권이며, 현재 {gold}G에서 이자 극대화가 장기 승률에 유리",
                impact=0.80
            ))
        else:
            save_score = 0.50

        scores.append(ActionScore(
            action=Action(ActionType.SAVE_GOLD),
            score=save_score,
            confidence=0.85,
            projected_gold=min(70, gold + 10),
            projected_power_delta=0.0
        ))

        # Sort actions by score descending
        scores.sort(key=lambda s: s.score, reverse=True)
        best = scores[0]

        if not reasons:
            reasons.append(Reason(
                summary=f"{best.action.action_type.value} 행동의 기대 점수가 가장 높음",
                evidence=f"현재 보드 파워={power}, 골드={gold}G 기반 최적 효용 평가",
                impact=best.score
            ))

        return Recommendation(
            recommended_action=best.action,
            score=best.score,
            confidence=best.confidence,
            all_scores=scores,
            reasons=reasons
        )
