"""TFT Board Power Evaluator (Set 17 Heuristic v2)."""
import math
from typing import Dict, Any, List
from tft.domain.game_state import GameState
from tft.evaluation.models import EvaluationResult
from tft.data.repositories import get_data_repository

class BoardEvaluator:
    """Set 17 보드 파워 가치평가기 (Source of Truth: board_power_weights_v2)."""

    def __init__(self, data_repo=None):
        self.data_repo = data_repo or get_data_repository()

    def evaluate(self, state: GameState) -> EvaluationResult:
        star_mult = self.data_repo.get_star_multipliers()
        comp_weight, full_weight = self.data_repo.get_item_score_weights()
        all_champs = self.data_repo.get_all_champions()

        unit_power_sum = 0.0
        item_score_sum = 0.0
        trait_champions: Dict[str, List[str]] = {}

        for u in state.board_units:
            cinfo = all_champs.get(u.champion)
            cost = cinfo["cost"] if cinfo else u.cost
            s_mult = star_mult.get(u.star_level, 1.0)

            unit_power_sum += cost * s_mult

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

        return EvaluationResult(
            score=total_power,
            metrics={
                "total_power": total_power,
                "unit_power": round(unit_power_sum, 4),
                "item_score": round(item_score_sum, 4),
                "synergy_bonus": round(synergy_bonus_sum, 4),
                "num_units": len(state.board_units),
                "num_active_synergies": len(active_synergies)
            },
            details={
                "active_synergies": active_synergies,
                "units_evaluated": [u.to_dict() for u in state.board_units]
            },
            evidence=[f"Board Power: {total_power} (Units: {unit_power_sum:.1f}, Items: {item_score_sum:.1f}, Synergies: {synergy_bonus_sum:.1f})"]
        )
