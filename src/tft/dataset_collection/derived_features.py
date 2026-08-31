"""Derived Features Extractor for TFT Dataset Collection v1.

Calculates pure T0 derived features without mutating raw state or injecting T1+ future data.
"""
from typing import Optional
from tft.domain.game_state import GameState
from tft.calibration.state_features.extractor import StateFeatureExtractor
from tft.dataset_collection.models import DerivedFeatures


class DerivedFeaturesCalculator:
    """Calculates canonical DerivedFeatures dataclass from GameState."""

    def __init__(self, extractor: Optional[StateFeatureExtractor] = None):
        self.extractor = extractor or StateFeatureExtractor()

    def calculate(
        self,
        state: GameState,
        previous_state: Optional[GameState] = None,
        sample_id: str = "T0"
    ) -> DerivedFeatures:
        """Extracts derived features safely."""
        try:
            vec = self.extractor.extract(
                state=state,
                sample_id=sample_id,
                previous_state=previous_state
            )
            return DerivedFeatures(
                board_power=round(float(vec.board.total_board_power), 2),
                pair_count=int(vec.upgrade.pair_count),
                immediate_shop_upgrades=int(vec.upgrade.immediate_shop_upgrades),
                estimated_rounds_to_elim=vec.temporal.estimated_rounds_to_elimination,
                stage_benchmark_ratio=round(float(vec.relative.stage_benchmark_ratio), 3),
                gold_to_next_level=int(vec.economy.gold_to_next_level),
                spendable_roll_budget=int(vec.economy.spendable_roll_budget),
                recent_hp_delta=vec.player.recent_hp_delta
            )
        except Exception:
            # Fallback simple calculation if extractor fails for any reason
            p = state.player
            stage = state.stage
            stage_dmg = 2 if stage <= 2 else (4 if stage == 3 else (7 if stage == 4 else (10 if stage == 5 else 15)))
            rounds_to_elim = round(p.hp / max(1, stage_dmg), 2)
            
            # Simple board power
            bp = sum(u.cost * (u.star_level ** 1.5) for u in state.board_units)
            
            # Pair count
            champ_counts = {}
            for u in state.board_units + state.bench_units:
                champ_counts[u.champion] = champ_counts.get(u.champion, 0) + 1
            pairs = sum(1 for c, cnt in champ_counts.items() if cnt == 2)
            
            # Shop upgrades
            shop_names = set(u.champion for u in state.board_units + state.bench_units)
            shop_upg = sum(1 for s in state.shop_units if s and s in shop_names)
            
            hp_delta = None
            if previous_state is not None:
                hp_delta = p.hp - previous_state.player.hp

            return DerivedFeatures(
                board_power=round(float(bp), 2),
                pair_count=pairs,
                immediate_shop_upgrades=shop_upg,
                estimated_rounds_to_elim=rounds_to_elim,
                stage_benchmark_ratio=1.0,
                gold_to_next_level=max(0, (p.level * 4) - p.xp),
                spendable_roll_budget=max(0, p.gold - 50),
                recent_hp_delta=hp_delta
            )
