"""TFT Economy Evaluator."""
from tft.domain.game_state import GameState
from tft.evaluation.models import EvaluationResult
from tft.data.repositories import get_data_repository

class EconomyEvaluator:
    """이자 수익, 레벨업 잔여 비용 및 골드 건전성 평가기."""

    def __init__(self, data_repo=None):
        self.data_repo = data_repo or get_data_repository()

    def evaluate(self, state: GameState) -> EvaluationResult:
        gold = state.player.gold
        level = state.player.level
        xp = state.player.xp

        # 1. Interest
        interest = min(5, gold // 10)

        # 2. Levelup cost to next level
        levelup_table = self.data_repo.get_levelup_cost_table()
        next_level = min(10, level + 1)
        if level >= 10:
            gold_needed = 0
        else:
            req_xp = levelup_table.get(next_level, 0)
            needed_xp = max(0, req_xp - xp)
            xp_buy_clicks = (needed_xp + 3) // 4
            gold_needed = xp_buy_clicks * 4

        can_levelup = (gold >= gold_needed and gold_needed > 0)
        tempo_score = min(1.0, gold / 50.0)

        return EvaluationResult(
            score=tempo_score,
            metrics={
                "current_gold": gold,
                "current_interest": interest,
                "gold_to_next_level": gold_needed,
                "can_levelup_now": 1.0 if can_levelup else 0.0,
                "is_max_interest": 1.0 if gold >= 50 else 0.0
            },
            details={"next_level": next_level, "xp_needed": max(0, levelup_table.get(next_level, 0) - xp)},
            evidence=[f"Gold: {gold}G (Interest: +{interest}G, Needed for Lv.{next_level}: {gold_needed}G)"]
        )
