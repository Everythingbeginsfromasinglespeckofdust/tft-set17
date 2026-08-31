"""TFT Level-Up Opportunity Cost & Shop Odds Shift Research Module.

Compares:
- Shop probability transition curves (Level N vs Level N+1)
- Board slot expansion value (+1 board unit power gain)
- Total Gold required (XP clicks) vs remaining interest
"""
from typing import Dict, Any, Optional
from tft.domain.game_state import GameState
from tft.data.repositories import StaticDataRepository, get_data_repository


class LevelUpOpportunityModel:
    """Evaluates marginal benefit of leveling up vs rolling or saving."""

    def __init__(self, data_repo: Optional[StaticDataRepository] = None):
        self.data_repo = data_repo or get_data_repository()

    def evaluate_level_up_tradeoff(self, state: GameState) -> Dict[str, Any]:
        """Quantify level-up marginal value versus current state."""
        cur_level = state.player.level
        cur_xp = state.player.xp
        cur_gold = state.player.gold
        levelup_table = self.data_repo.get_levelup_cost_table()

        if cur_level >= 10:
            return {
                "current_level": cur_level,
                "target_level": 10,
                "gold_required": 0,
                "xp_required": 0,
                "is_max_level": True,
                "odds_shift_high_cost": 0.0,
                "marginal_level_value_score": 0.0
            }

        target_level = cur_level + 1
        req_xp = levelup_table.get(target_level, 0)
        needed_xp = max(0, req_xp - cur_xp)
        xp_clicks = (needed_xp + 3) // 4
        gold_required = xp_clicks * 4

        # Odds shift for 4-cost and 5-cost carries
        high_cost_odds_cur = self.data_repo.get_drop_rate(cur_level, 4) + self.data_repo.get_drop_rate(cur_level, 5)
        high_cost_odds_next = self.data_repo.get_drop_rate(target_level, 4) + self.data_repo.get_drop_rate(target_level, 5)
        odds_jump = round(high_cost_odds_next - high_cost_odds_cur, 3)

        # Board power increase from +1 slot
        if state.bench_units:
            promoted = max(state.bench_units, key=lambda u: u.cost * u.star_level)
            slot_power_gain = float(promoted.cost * (2.0 if promoted.star_level == 2 else 1.0))
        else:
            slot_power_gain = float(min(4, target_level // 2))

        can_afford = (cur_gold >= gold_required)
        gold_remaining = max(0, cur_gold - gold_required)
        interest_remaining = min(5, gold_remaining // 10)

        # Marginal value score: high when gold_required is small (e.g. 4G/8G) and high-cost odds jump is large
        if gold_required > 0:
            marginal_score = round(min(1.0, (slot_power_gain * 2.0 + odds_jump * 50.0 + interest_remaining * 2.0) / max(4.0, gold_required)), 3)
        else:
            marginal_score = 1.0

        return {
            "current_level": cur_level,
            "target_level": target_level,
            "gold_required": gold_required,
            "xp_required": needed_xp,
            "can_afford": can_afford,
            "gold_remaining_after_level": gold_remaining,
            "interest_remaining": interest_remaining,
            "current_high_cost_odds": high_cost_odds_cur,
            "target_high_cost_odds": high_cost_odds_next,
            "high_cost_odds_jump": odds_jump,
            "immediate_board_slot_power_gain": slot_power_gain,
            "marginal_level_value_score": marginal_score
        }
