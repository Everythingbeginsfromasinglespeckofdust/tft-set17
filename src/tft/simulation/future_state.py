"""TFT Multi-turn Strategy Simulator."""
import copy
from typing import Dict, List, Optional
from tft.domain.game_state import GameState
from tft.simulation.models import SimulationResult, TurnDetail
from tft.data.repositories import get_data_repository

class FutureStateSimulator:
    """Action 및 Horizon(N턴)에 따른 골드/레벨/확률 복리 시뮬레이터."""

    def __init__(self, data_repo=None):
        self.data_repo = data_repo or get_data_repository()

    def simulate_strategy(
        self, state: GameState, strategy: dict, horizon: int = 3
    ) -> SimulationResult:
        cur_gold = state.player.gold
        cur_level = state.player.level
        cur_xp = state.player.xp
        action_type = strategy.get("action", "save_interest")
        strat_name = strategy.get("name", action_type)

        lvl_table = self.data_repo.get_levelup_cost_table()
        max_lvl = 10

        turn_details = []
        cum_miss = 1.0
        has_roll = False

        for t in range(1, horizon + 1):
            start_gold = cur_gold
            spent = 0
            hit_prob_turn = None

            if action_type == "save_interest":
                spent = 0
            elif action_type == "levelup":
                target_lvl = strategy.get("target_level", min(max_lvl, cur_level + 1))
                if cur_level < target_lvl:
                    req_xp = lvl_table.get(target_lvl, 0)
                    needed_xp = max(0, req_xp - cur_xp)
                    clicks = (needed_xp + 3) // 4
                    cost = clicks * 4
                    spend = min(cost, cur_gold)
                    clicks_bought = spend // 4
                    spent = clicks_bought * 4
                    gained_xp = clicks_bought * 4
                    cur_xp += gained_xp
                    while cur_level < max_lvl and cur_xp >= lvl_table.get(cur_level + 1, 999):
                        cur_xp -= lvl_table[cur_level + 1]
                        cur_level += 1
            elif action_type == "roll":
                has_roll = True
                budget = strategy.get("gold_per_turn", cur_gold)
                spend = min(budget, cur_gold)
                rerolls = spend // 2
                spent = rerolls * 2
                # Calculate simple hit prob
                cost = strategy.get("cost", 3)
                p = self.data_repo.get_drop_rate(cur_level, cost)
                p_miss_roll = (1.0 - p) ** 5
                p_hit_roll = 1.0 - (p_miss_roll ** max(1, rerolls))
                hit_prob_turn = p_hit_roll
                cum_miss *= (1.0 - p_hit_roll)

            remaining_gold = start_gold - spent
            interest = min(5, remaining_gold // 10)
            end_gold = remaining_gold + interest + 5 # +5 base round gold

            turn_details.append(TurnDetail(
                turn=t,
                action_executed=action_type,
                start_gold=start_gold,
                spent_gold=spent,
                end_gold=end_gold,
                level=cur_level,
                xp=cur_xp,
                interest_earned=interest,
                hit_probability=hit_prob_turn
            ))

            cur_gold = end_gold

        cum_hit = (1.0 - cum_miss) if has_roll else None

        return SimulationResult(
            strategy_name=strat_name,
            horizon_turns=horizon,
            final_gold=cur_gold,
            final_level=cur_level,
            final_xp=cur_xp,
            cumulative_hit_prob=cum_hit,
            turn_by_turn=turn_details
        )
