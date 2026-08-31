"""TFT Economy Reserve & Opportunity Cost Research Module.

Models:
- Discrete interest breakpoints (10G ~ 50G)
- Marginal gold distance to interest tiers
- Dynamic economy reserve targets (50G vs 30G vs 0G in crisis)
- Action-specific interest loss opportunity costs
"""
from typing import Dict, Any, Tuple


class EconomyReserveModel:
    """Quantitative economy reserve and action opportunity cost analyzer."""

    @staticmethod
    def evaluate_economy(
        gold: int,
        hp: int,
        stage: int,
        level: int,
        xp: int,
        levelup_cost_table: Dict[int, int]
    ) -> Dict[str, Any]:
        """Compute full discrete economy parameters."""
        # 1. Interest Breakpoints
        interest_tier = min(5, gold // 10)
        gold_to_next_interest = (10 - (gold % 10)) if interest_tier < 5 else 0
        excess_gold_above_current_tier = gold % 10

        # 2. Dynamic Reserve Target
        if hp <= 25:
            reserve_target = 0
        elif hp <= 40 or stage >= 5:
            reserve_target = 30
        else:
            reserve_target = 50

        spendable_roll_budget = max(0, gold - reserve_target)

        # 3. Level-up Cost Calculation
        next_level = min(10, level + 1)
        if level >= 10:
            gold_needed_to_level = 0
            xp_needed = 0
        else:
            req_xp = levelup_cost_table.get(next_level, 0)
            xp_needed = max(0, req_xp - xp)
            xp_buy_clicks = (xp_needed + 3) // 4
            gold_needed_to_level = xp_buy_clicks * 4

        can_level_now = (gold >= gold_needed_to_level and gold_needed_to_level > 0)
        gold_after_level = max(0, gold - gold_needed_to_level)
        interest_after_level = min(5, gold_after_level // 10)
        interest_loss_level = max(0, interest_tier - interest_after_level)

        # 4. Opportunity Cost for 1 Roll (2G) and Standard Roll Down (10G)
        gold_after_1_roll = max(0, gold - 2)
        interest_loss_1_roll = interest_tier - min(5, gold_after_1_roll // 10)

        gold_after_10g_roll = max(0, gold - 10)
        interest_loss_10g_roll = interest_tier - min(5, gold_after_10g_roll // 10)

        return {
            "gold": gold,
            "interest_tier": interest_tier,
            "gold_to_next_interest": gold_to_next_interest,
            "excess_gold_above_tier": excess_gold_above_current_tier,
            "is_free_roll_safe": (excess_gold_above_current_tier >= 2),  # Can buy 1 roll without dropping tier
            "economy_reserve_target": reserve_target,
            "spendable_roll_budget": spendable_roll_budget,
            "gold_to_next_level": gold_needed_to_level,
            "xp_needed": xp_needed,
            "can_level_now": can_level_now,
            "gold_after_level": gold_after_level,
            "interest_loss_level": interest_loss_level,
            "interest_loss_1_roll": interest_loss_1_roll,
            "interest_loss_10g_roll": interest_loss_10g_roll
        }
