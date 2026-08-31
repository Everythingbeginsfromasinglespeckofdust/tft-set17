"""TFT Board Power Decomposition & Lobby Relative Power Research Module.

Decomposes board strength into:
- Base Unit Cost * Star Multiplier
- Item Value (Components vs Completed)
- Trait Tier Synergy
- Frontline vs Backline Balance
- Stage Benchmark Comparison
- Lobby Relative Mean / Median / Percentile (with strict UNKNOWN handling)
"""
import math
from typing import Dict, List, Optional, Tuple, Any
from tft.domain.game_state import GameState, LobbyState
from tft.domain.units import Unit
from tft.data.repositories import StaticDataRepository, get_data_repository

# Standard Stage Benchmark Board Power Table (Observed Median baselines)
STAGE_POWER_BENCHMARKS = {
    1: 8.0,
    2: 18.0,
    3: 35.0,
    4: 55.0,
    5: 75.0,
    6: 95.0,
    7: 120.0
}

FRONTLINE_TRAIT_KEYWORDS = {"vanguard", "brawler", "bruiser", "warden", "juggernaut", "tank", "bastion", "colossus", "defender", "sentinel", "guardian", "knight", "bruiser", "heavy"}


class BoardPowerModel:
    """Rigorous decomposition and relative normalization for board power."""

    def __init__(self, data_repo: Optional[StaticDataRepository] = None):
        self.data_repo = data_repo or get_data_repository()

    def decompose_board(self, state: GameState) -> Dict[str, Any]:
        """Decompose board units into granular sub-scores."""
        star_mult = self.data_repo.get_star_multipliers()
        comp_weight, full_weight = self.data_repo.get_item_score_weights()
        all_champs = self.data_repo.get_all_champions()

        unit_power_sum = 0.0
        item_score_sum = 0.0
        trait_champions: Dict[str, List[str]] = {}
        star_dist = {1: 0, 2: 0, 3: 0}
        total_cost = 0

        frontline_power = 0.0
        backline_power = 0.0

        for u in state.board_units:
            cinfo = all_champs.get(u.champion)
            cost = cinfo["cost"] if cinfo else u.cost
            s_mult = star_mult.get(u.star_level, 1.0)
            u_pwr = cost * s_mult
            unit_power_sum += u_pwr
            total_cost += cost

            star_dist[u.star_level] = star_dist.get(u.star_level, 0) + 1

            # Frontline vs Backline classification
            traits = [t.lower() for t in (cinfo.get("traits", []) if cinfo else [])]
            is_front = any(any(kw in t for kw in FRONTLINE_TRAIT_KEYWORDS) for t in traits)
            if is_front:
                frontline_power += u_pwr
            else:
                backline_power += u_pwr

            # Items
            for it in u.items:
                if self.data_repo.is_completed_item(it):
                    item_score_sum += full_weight
                elif self.data_repo.is_basic_component(it):
                    item_score_sum += comp_weight

            # Traits
            if cinfo:
                for t in cinfo.get("traits", []):
                    trait_champions.setdefault(t, []).append(u.champion)

        # Synergy bonus
        synergy_bonus_sum = 0.0
        active_synergies = []
        for t_name, champs in trait_champions.items():
            unique_champs = list(set(champs))
            unique_count = len(unique_champs)
            bps = self.data_repo._trait_breakpoints.get(t_name, [])
            reached_tier = 0
            for idx, req in enumerate(bps):
                if unique_count >= req:
                    reached_tier = idx + 1
            if reached_tier > 0:
                bonus = round(math.pow(reached_tier, 1.5) * 2.0, 4)
                synergy_bonus_sum += bonus
                active_synergies.append({"trait": t_name, "count": unique_count, "tier": reached_tier, "bonus": bonus})

        total_power = round(unit_power_sum + item_score_sum + synergy_bonus_sum, 4)
        n_units = len(state.board_units)
        avg_cost = round(total_cost / max(1, n_units), 2)

        tot_p = max(0.1, frontline_power + backline_power)
        f_ratio = round(frontline_power / tot_p, 3)
        b_ratio = round(backline_power / tot_p, 3)

        return {
            "total_power": total_power,
            "unit_power": round(unit_power_sum, 4),
            "item_score": round(item_score_sum, 4),
            "synergy_bonus": round(synergy_bonus_sum, 4),
            "star_distribution": star_dist,
            "unit_count": n_units,
            "avg_unit_cost": avg_cost,
            "active_traits_count": len(active_synergies),
            "frontline_power_ratio": f_ratio,
            "backline_power_ratio": b_ratio,
            "active_synergies": active_synergies
        }

    def compute_stage_benchmark_ratio(self, my_power: float, stage: int) -> float:
        """Ratio of my board power against standard stage baseline."""
        benchmark = STAGE_POWER_BENCHMARKS.get(stage, 55.0)
        return round(my_power / max(1.0, benchmark), 3)

    def compute_lobby_relative_metrics(
        self, my_power: float, opponents: List[LobbyState]
    ) -> Dict[str, Optional[float]]:
        """Calculate lobby relative position if opponents are observed."""
        if not opponents:
            return {
                "known_opponents_count": 0,
                "lobby_mean_board_power": None,
                "lobby_median_board_power": None,
                "lobby_min_board_power": None,
                "lobby_max_board_power": None,
                "relative_board_power_to_mean": None,
                "board_power_percentile": None,
                "distance_to_top4_boundary": None
            }

        valid_powers = [op.estimated_board_power for op in opponents if op.estimated_board_power > 0]
        if not valid_powers:
            return {
                "known_opponents_count": len(opponents),
                "lobby_mean_board_power": None,
                "lobby_median_board_power": None,
                "lobby_min_board_power": None,
                "lobby_max_board_power": None,
                "relative_board_power_to_mean": None,
                "board_power_percentile": None,
                "distance_to_top4_boundary": None
            }

        all_lobby_powers = sorted(valid_powers + [my_power])
        n = len(all_lobby_powers)
        mean_pwr = round(sum(all_lobby_powers) / n, 2)
        
        # Median
        mid = n // 2
        median_pwr = round((all_lobby_powers[mid] if n % 2 == 1 else (all_lobby_powers[mid - 1] + all_lobby_powers[mid]) / 2.0), 2)
        min_pwr = round(all_lobby_powers[0], 2)
        max_pwr = round(all_lobby_powers[-1], 2)

        # Percentile rank of my board (0.0 = weakest, 1.0 = strongest)
        rank = sum(1 for p in all_lobby_powers if p <= my_power)
        percentile = round(rank / n, 3)

        # Relative ratio to mean
        rel_mean = round(my_power / max(1.0, mean_pwr), 3)

        # Top 4 boundary distance (4th highest power in 8-player lobby)
        top4_idx = max(0, n - 4)
        top4_cut = all_lobby_powers[top4_idx]
        dist_top4 = round(my_power - top4_cut, 2)

        return {
            "known_opponents_count": len(opponents),
            "lobby_mean_board_power": mean_pwr,
            "lobby_median_board_power": median_pwr,
            "lobby_min_board_power": min_pwr,
            "lobby_max_board_power": max_pwr,
            "relative_board_power_to_mean": rel_mean,
            "board_power_percentile": percentile,
            "distance_to_top4_boundary": dist_top4
        }
