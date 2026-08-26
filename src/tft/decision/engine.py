"""TFT Core Decision Engine (ROLL / LEVEL_UP / SAVE_GOLD)."""
from typing import Any, Dict, List, Optional
from tft.domain.game_state import GameState
from tft.domain.actions import Action, ActionType
from tft.data.repositories import StaticDataRepository, get_data_repository
from tft.simulation.future_state import FutureStateSimulator
from tft.simulation.models import SimulationResult
from tft.decision.scorer import ActionScorer, DecisionConfig, DEFAULT_DECISION_CONFIG
from tft.decision.models import ActionScore, Recommendation, Reason
from tft.explanation.generator import ExplanationGenerator

class DecisionEngine:
    """GameState를 입력받아 Future State Simulation을 거쳐 최적 Action을 도출하는 의사결정 엔진."""

    def __init__(
        self,
        data_repo: Optional[StaticDataRepository] = None,
        config: Optional[DecisionConfig] = None,
        random_seed: Optional[int] = None
    ):
        self.data_repo = data_repo or get_data_repository()
        self.config = config or DEFAULT_DECISION_CONFIG
        self.simulator = FutureStateSimulator(self.data_repo, random_seed=random_seed)
        self.scorer = ActionScorer(self.config)
        self.explanation_generator = ExplanationGenerator()

    def decide(self, state: GameState, horizon: Optional[int] = None) -> Recommendation:
        """현재 GameState에서 ROLL, LEVEL_UP, SAVE_GOLD의 다중 턴 미래를 시뮬레이션하고 최적안 추천."""
        h = horizon if horizon is not None else self.config.horizon
        gold = state.player.gold
        level = state.player.level
        hp = state.player.hp

        # 1. Instantiate Candidate Actions
        actions = [
            Action(
                action_type=ActionType.ROLL,
                budget_gold=gold if hp <= self.config.crisis_hp_threshold else max(0, gold - 50)
            ),
            Action(
                action_type=ActionType.LEVEL_UP,
                target_level=min(10, level + 1)
            ),
            Action(
                action_type=ActionType.SAVE_GOLD
            ),
        ]

        # 2. Execute Future State Simulation for each candidate action
        sim_results: Dict[ActionType, SimulationResult] = {}
        action_scores: List[ActionScore] = []

        for action in actions:
            sim_res = self.simulator.simulate(state, action, horizon=h)
            sim_results[action.action_type] = sim_res
            score = self.scorer.score(state, sim_res)
            action_scores.append(score)

        # 3. Sort Actions by Score Descending
        action_scores.sort(key=lambda s: s.score, reverse=True)
        best_score = action_scores[0]
        alternatives = action_scores[1:]

        # 4. Generate Comparative Explanation & Evidence
        reasons = self.explanation_generator.generate_comparative_reasons(
            state=state,
            best_score=best_score,
            all_scores=action_scores,
            sim_results=sim_results
        )

        return Recommendation(
            recommended_action=best_score.action,
            score=best_score.score,
            confidence=best_score.confidence,
            alternatives=alternatives,
            all_scores=action_scores,
            reasons=reasons,
            metadata={
                "horizon": h,
                "evaluated_actions": [a.action_type.value for a in actions],
                "simulation_summaries": {
                    a_type.value: {
                        "expected_gold": res.expected_gold,
                        "expected_hp": res.expected_hp,
                        "expected_power": res.expected_board_power,
                        "survival_prob": res.survival_probability,
                        "upgrade_prob": res.upgrade_probability
                    }
                    for a_type, res in sim_results.items()
                }
            }
        )
