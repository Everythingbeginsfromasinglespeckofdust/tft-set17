"""TFT Upgrade & Shop Opportunity Research Module.

Calculates:
- Exact pair counts across Board + Bench
- Copies needed for next star upgrade (2★ and 3★)
- Immediate shop upgrade synergy (units in shop that complete an upgrade right now)
- Expected upgrade frequency under 10G / 20G roll budget using Set 18 shop odds
"""
import math
from typing import Dict, List, Optional, Tuple, Any
from tft.domain.game_state import GameState
from tft.domain.units import Unit
from tft.data.repositories import StaticDataRepository, get_data_repository


class UpgradeOpportunityModel:
    """Rigorous upgrade potential and shop accessibility calculator."""

    def __init__(self, data_repo: Optional[StaticDataRepository] = None):
        self.data_repo = data_repo or get_data_repository()

    def evaluate_upgrades(self, state: GameState) -> Dict[str, Any]:
        """Analyze board, bench, and shop for upgrade opportunities."""
        all_units = state.board_units + state.bench_units
        all_champs = self.data_repo.get_all_champions()

        # 1. Tally copies owned per champion
        # 1★ = 1 copy, 2★ = 3 copies, 3★ = 9 copies
        copies_owned: Dict[str, int] = {}
        champ_costs: Dict[str, int] = {}

        for u in all_units:
            c_name = u.champion
            c_copies = 3 if u.star_level == 2 else (9 if u.star_level >= 3 else 1)
            copies_owned[c_name] = copies_owned.get(c_name, 0) + c_copies
            if c_name not in champ_costs:
                cinfo = all_champs.get(c_name)
                champ_costs[c_name] = cinfo["cost"] if cinfo else u.cost

        # 2. Identify Pairs, 3★ progress, and Missing Copies
        pairs: List[str] = []
        three_star_candidates: List[str] = []
        missing_copies_map: Dict[str, int] = {}

        two_star_count = sum(1 for u in all_units if u.star_level == 2)

        for c_name, count in copies_owned.items():
            if count == 2:
                # Exactly 2 copies -> 1 copy away from 2★
                pairs.append(c_name)
                missing_copies_map[c_name] = 1
            elif 3 <= count < 9:
                # Has a 2★, progress towards 3★
                three_star_candidates.append(c_name)
                missing_copies_map[c_name] = 9 - count
            elif count == 1:
                missing_copies_map[c_name] = 2

        # 3. Analyze Immediate Shop Synergy
        shop_units = [u for u in state.shop_units if u]
        immediate_upgrades = []
        shop_matching_units = []

        for slot_idx, shop_champ in enumerate(shop_units):
            if shop_champ in copies_owned:
                shop_matching_units.append(shop_champ)
                if copies_owned[shop_champ] == 2 or copies_owned[shop_champ] == 8:
                    immediate_upgrades.append({
                        "slot": slot_idx,
                        "champion": shop_champ,
                        "cost": champ_costs.get(shop_champ, 1),
                        "target_star": 2 if copies_owned[shop_champ] == 2 else 3
                    })

        # 4. Expected Upgrade Probability under 10G roll (5 shop rolls = 25 slots)
        cur_level = state.player.level
        
        # Approximate probability of hitting at least 1 upgrade across pairs
        pair_hit_prob_10g = 0.0
        if pairs:
            combined_slot_miss_prob = 1.0
            for p_champ in pairs:
                cost = champ_costs.get(p_champ, 1)
                cost_odd = self.data_repo.get_drop_rate(cur_level, cost)
                # Single slot chance of this specific champion: odd / 13
                p_slot = cost_odd / 13.0
                combined_slot_miss_prob *= (1.0 - p_slot)

            # Across 25 slots (5 rolls of 5 slots):
            pair_hit_prob_10g = round(1.0 - math.pow(combined_slot_miss_prob, 25), 4)

        return {
            "pair_count": len(pairs),
            "pairs_list": pairs,
            "two_star_count": two_star_count,
            "three_star_candidate_count": len(three_star_candidates),
            "three_star_candidates": three_star_candidates,
            "missing_copies_summary": missing_copies_map,
            "immediate_shop_upgrades_count": len(immediate_upgrades),
            "immediate_shop_upgrades": immediate_upgrades,
            "shop_matching_units_count": len(shop_matching_units),
            "expected_roll_upgrade_prob_10g": pair_hit_prob_10g,
            "has_immediate_upgrade_in_shop": len(immediate_upgrades) > 0
        }
