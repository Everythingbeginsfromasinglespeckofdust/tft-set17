"""TFT Canonical Scenario Library (5 Core Tactical Situations).

Defines:
- SCENARIO_001: Midgame Stabilization (Stage 4-3, HP 38, Gold 48, 2 Pairs)
- SCENARIO_002: One-Shot Lethal Emergency (Stage 6-3, HP 8, Gold 4, 1 Loss = Dead)
- SCENARIO_003: Late-Game Stage 6 Pressure (Stage 6-1, HP 45, Gold 40, 18HP loss/turn)
- SCENARIO_004: Early Compound Interest Snowball (Stage 2-7, HP 82, Gold 38, +3G interest)
- SCENARIO_005: Low-Cost Tempo Level-Up Breakpoint (Stage 2-1, HP 100, Gold 10, 8G to level)
"""
from typing import Dict, List, Any, Optional
from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.research.candidate_engine.candidate_models import CandidateDecisionEngine, CandidateModelType


class ScenarioLibraryManager:
    """Manages canonical real gameplay scenarios and compares decisions."""

    def __init__(self, engine: Optional[CandidateDecisionEngine] = None):
        self.engine = engine or CandidateDecisionEngine()

    def build_canonical_scenarios(self) -> List[Dict[str, Any]]:
        """Construct the 5 canonical real game state scenarios."""
        scenarios = [
            {
                "scenario_id": "SCENARIO_001",
                "title": "Midgame Stage 4-3 Deficit Stabilization",
                "description": "Player has 38 HP entering late stage 4, holding 2 pairs with 48G. Board is 78% of stage benchmark.",
                "state": GameState(
                    stage=4,
                    round=3,
                    stage_round="4-3",
                    player=PlayerState(gold=48, level=7, xp=16, hp=38),
                    board_units=[
                        Unit(champion="Diana", cost=3, star_level=1),
                        Unit(champion="Zac", cost=2, star_level=2)
                    ],
                    bench_units=[
                        Unit(champion="Diana", cost=3, star_level=1), # Pair 1
                        Unit(champion="Zac", cost=2, star_level=1)     # Pair 2
                    ],
                    shop_units=["Diana", "Vayne", None, "Lux", None]
                ),
                "human_preferred_action": "ROLL",
                "strategic_context": "Stabilize board with 2-stars before stage 5 high combat damage"
            },
            {
                "scenario_id": "SCENARIO_002",
                "title": "One-Shot Lethal Emergency",
                "description": "Player has 8 HP at Stage 6-3 with 4G. Next combat loss results in immediate elimination.",
                "state": GameState(
                    stage=6,
                    round=3,
                    stage_round="6-3",
                    player=PlayerState(gold=4, level=8, xp=40, hp=8),
                    board_units=[Unit(champion="Diana", cost=3, star_level=2)],
                    bench_units=[Unit(champion="Diana", cost=3, star_level=2)],
                    shop_units=["Diana", None, None, None, None]
                ),
                "human_preferred_action": "ROLL",
                "strategic_context": "Immediate roll for 3-star Diana or any unit to survive"
            },
            {
                "scenario_id": "SCENARIO_003",
                "title": "Late-Game Stage 6 Legendary Power Push",
                "description": "Stage 6-1, HP 45, Gold 40. Base damage is 18HP. 2 losses eliminate the player.",
                "state": GameState(
                    stage=6,
                    round=1,
                    stage_round="6-1",
                    player=PlayerState(gold=40, level=8, xp=36, hp=45),
                    board_units=[Unit(champion="Diana", cost=3, star_level=2)],
                    bench_units=[Unit(champion="Lux", cost=4, star_level=1)],
                    shop_units=[None]*5
                ),
                "human_preferred_action": "ROLL",
                "strategic_context": "Transition to 5-cost carries to contend for top 2"
            },
            {
                "scenario_id": "SCENARIO_004",
                "title": "Early Compound Interest Snowball",
                "description": "Stage 2-7, HP 82, Gold 38. Safe HP and board on par with benchmark.",
                "state": GameState(
                    stage=2,
                    round=7,
                    stage_round="2-7",
                    player=PlayerState(gold=38, level=5, xp=4, hp=82),
                    board_units=[Unit(champion="Akali", cost=1, star_level=2)],
                    bench_units=[],
                    shop_units=[None]*5
                ),
                "human_preferred_action": "SAVE_GOLD",
                "strategic_context": "Preserve 30G/40G interest to reach 50G economy breakpoint"
            },
            {
                "scenario_id": "SCENARIO_005",
                "title": "Cheap Tempo Level-Up Breakpoint",
                "description": "Stage 2-1, HP 100, Gold 10. Level 3 with 0 XP. 4 XP (4G) needed for Level 4.",
                "state": GameState(
                    stage=2,
                    round=1,
                    stage_round="2-1",
                    player=PlayerState(gold=10, level=3, xp=2, hp=100),
                    board_units=[Unit(champion="Akali", cost=1, star_level=1)],
                    bench_units=[Unit(champion="Akali", cost=1, star_level=1)],
                    shop_units=[None]*5
                ),
                "human_preferred_action": "SAVE_GOLD",
                "strategic_context": "Save gold on 2-1 or 1-click level up"
            }
        ]
        return scenarios

    def evaluate_all_scenarios(self) -> List[Dict[str, Any]]:
        """Evaluate both baseline and candidate models on canonical scenarios."""
        scenarios = self.build_canonical_scenarios()
        results = []

        for sc in scenarios:
            st = sc["state"]
            sc_id = sc["scenario_id"]

            base_snap = self.engine.baseline.capture_snapshot(st, sample_id=sc_id)
            cand_res = self.engine.evaluate(st, model_type=CandidateModelType.V4_COMBINED, sample_id=sc_id)

            results.append({
                "scenario_id": sc_id,
                "title": sc["title"],
                "description": sc["description"],
                "human_preferred_action": sc["human_preferred_action"],
                "baseline_action": base_snap["recommended_action"],
                "baseline_score": base_snap["recommended_score"],
                "candidate_action": cand_res.candidate_action,
                "candidate_score": cand_res.candidate_score,
                "is_flipped": cand_res.is_flipped,
                "contributions": [
                    {
                        "feature_id": c.feature_id,
                        "delta": c.score_delta,
                        "justification": c.justification
                    }
                    for c in cand_res.feature_contributions
                ],
                "strategic_context": sc["strategic_context"]
            })
        return results
