"""TFT Decision State Feature Taxonomy & Schema (Categories A through G).

Core Principles:
1. Pure Immutable Data Structures.
2. Explicit T0 Availability flag on every feature definition.
3. Strict handling of unobserved data as UNKNOWN / None (NEVER imputed with 0).
4. No mutation of production GameState or DecisionEngine contracts.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class FeatureCategory(str, Enum):
    PLAYER = "PLAYER_STATE"
    ECONOMY = "ECONOMY_STATE"
    BOARD = "BOARD_STATE"
    UPGRADE = "UPGRADE_STATE"
    OPPONENT = "OPPONENT_STATE"
    TEMPORAL = "TEMPORAL_STATE"
    RELATIVE = "RELATIVE_STATE"


class FeatureDataType(str, Enum):
    FLOAT = "FLOAT"
    INT = "INT"
    STRING = "STRING"
    BOOLEAN = "BOOLEAN"
    CATEGORICAL = "CATEGORICAL"


class DataTier(str, Enum):
    TIER_A = "A_OBSERVED_DIRECT"
    TIER_B = "B_COMPUTED_FROM_OBSERVED"
    TIER_C = "C_METATFT_AGGREGATE"
    TIER_D = "D_DESIGN_HYPOTHESIS"
    TIER_E = "E_HEURISTIC"


class CandidateGateVerdict(str, Enum):
    KEEP = "KEEP"
    EXPERIMENTAL = "EXPERIMENTAL"
    HUMAN_REVIEW_ONLY = "HUMAN_REVIEW_ONLY"
    REJECT = "REJECT"


class DataSufficiencyLevel(str, Enum):
    READY = "READY"
    LIMITED = "LIMITED"
    INSUFFICIENT = "INSUFFICIENT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FeatureMeta:
    """Metadata specification for a single feature definition."""
    name: str
    category: FeatureCategory
    data_type: FeatureDataType
    description: str
    formula: str
    available_at_t0: bool
    evidence_tier: DataTier
    unit_or_range: str
    default_when_missing: Optional[Any] = None
    gate_verdict: CandidateGateVerdict = CandidateGateVerdict.EXPERIMENTAL
    sufficiency: DataSufficiencyLevel = DataSufficiencyLevel.LIMITED


# -----------------------------------------------------------------------------
# Specific State Sub-Vectors (Categories A ~ G)
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class PlayerStateVector:
    """Category A: Player Core State."""
    hp: int
    gold: int
    level: int
    xp: int
    streak: int
    stage: int
    round_num: int
    stage_round: str


@dataclass(frozen=True)
class EconomyStateVector:
    """Category B: Economy Breakdown & Projections."""
    spendable_gold: int
    interest_tier: int               # 0 ~ 5 (+1G per 10G)
    gold_to_next_interest: int       # e.g., 38G -> 2G to reach 40G
    gold_to_next_level: int          # XP purchasing cost
    spendable_roll_budget: int       # Gold above crisis reserve
    economy_reserve_target: int      # 50G or 30G depending on stage/HP
    interest_opportunity_cost_roll: int   # Interest lost if rolling now
    interest_opportunity_cost_level: int  # Interest lost if leveling now


@dataclass(frozen=True)
class BoardStateVector:
    """Category C: Board Structural Composition."""
    raw_board_power: float
    unit_count: int
    max_units: int
    avg_unit_cost: float
    star_distribution: Dict[int, int]   # {1: count, 2: count, 3: count}
    completed_items_count: int
    component_items_count: int
    active_traits_count: int
    frontline_power_ratio: float        # Tank/Brawler front share
    backline_power_ratio: float         # Carry/Caster rear share


@dataclass(frozen=True)
class UpgradeStateVector:
    """Category D: Upgrade & Shop Opportunities."""
    pair_count: int                     # Number of 2-copy holdings
    two_star_count: int
    three_star_candidate_count: int
    missing_copies_summary: Dict[str, int]  # {champ: copies_needed_for_next_star}
    immediate_shop_upgrades: int        # Upgrades completed directly from current shop
    shop_matching_units_count: int      # Any copy in shop matching board/bench
    expected_roll_upgrade_count_10g: float  # Expected upgrades with 10G roll
    shop_tier_match_score: float        # Odds of hitting target costs at current level


@dataclass(frozen=True)
class OpponentStateVector:
    """Category E: Opponent & Lobby Environment."""
    known_opponents_count: int
    lobby_mean_board_power: Optional[float] = None
    lobby_median_board_power: Optional[float] = None
    lobby_min_board_power: Optional[float] = None
    lobby_max_board_power: Optional[float] = None
    current_opponent_power: Optional[float] = None
    current_opponent_power_gap: Optional[float] = None  # my_power - opp_power (or None)


@dataclass(frozen=True)
class TemporalStateVector:
    """Category F: Trajectory & Recent Trends."""
    stage_numeric: float                # stage + round/10.0
    recent_hp_delta: Optional[int] = None       # e.g., -14 over last turn
    recent_hp_slope_3turns: Optional[float] = None
    recent_board_power_delta: Optional[float] = None
    recent_gold_delta: Optional[int] = None
    estimated_rounds_to_elimination: Optional[float] = None


@dataclass(frozen=True)
class RelativeStateVector:
    """Category G: Relative & Percentile Standing."""
    relative_board_power_to_mean: Optional[float] = None    # my_power / mean
    board_power_percentile: Optional[float] = None          # 0.0 ~ 1.0 (top = 1.0)
    hp_percentile: Optional[float] = None
    economy_percentile: Optional[float] = None
    distance_to_top4_boundary: Optional[float] = None
    stage_benchmark_ratio: float = 1.0                      # my_power / stage_benchmark


# -----------------------------------------------------------------------------
# Unified Decision State Vector
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class DecisionStateVector:
    """Consolidated state feature representation for research and calibration."""
    sample_id: str
    match_id: str
    stage_round: str
    player: PlayerStateVector
    economy: EconomyStateVector
    board: BoardStateVector
    upgrade: UpgradeStateVector
    opponent: OpponentStateVector
    temporal: TemporalStateVector
    relative: RelativeStateVector
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state vector with clean null handling."""
        return {
            "sample_id": self.sample_id,
            "match_id": self.match_id,
            "stage_round": self.stage_round,
            "player": {
                "hp": self.player.hp,
                "gold": self.player.gold,
                "level": self.player.level,
                "xp": self.player.xp,
                "streak": self.player.streak,
                "stage": self.player.stage,
                "round_num": self.player.round_num
            },
            "economy": {
                "spendable_gold": self.economy.spendable_gold,
                "interest_tier": self.economy.interest_tier,
                "gold_to_next_interest": self.economy.gold_to_next_interest,
                "gold_to_next_level": self.economy.gold_to_next_level,
                "spendable_roll_budget": self.economy.spendable_roll_budget,
                "economy_reserve_target": self.economy.economy_reserve_target,
                "interest_opportunity_cost_roll": self.economy.interest_opportunity_cost_roll,
                "interest_opportunity_cost_level": self.economy.interest_opportunity_cost_level
            },
            "board": {
                "raw_board_power": self.board.raw_board_power,
                "unit_count": self.board.unit_count,
                "max_units": self.board.max_units,
                "avg_unit_cost": self.board.avg_unit_cost,
                "star_distribution": self.board.star_distribution,
                "completed_items_count": self.board.completed_items_count,
                "component_items_count": self.board.component_items_count,
                "active_traits_count": self.board.active_traits_count,
                "frontline_power_ratio": self.board.frontline_power_ratio,
                "backline_power_ratio": self.board.backline_power_ratio
            },
            "upgrade": {
                "pair_count": self.upgrade.pair_count,
                "two_star_count": self.upgrade.two_star_count,
                "three_star_candidate_count": self.upgrade.three_star_candidate_count,
                "missing_copies_summary": self.upgrade.missing_copies_summary,
                "immediate_shop_upgrades": self.upgrade.immediate_shop_upgrades,
                "shop_matching_units_count": self.upgrade.shop_matching_units_count,
                "expected_roll_upgrade_count_10g": self.upgrade.expected_roll_upgrade_count_10g,
                "shop_tier_match_score": self.upgrade.shop_tier_match_score
            },
            "opponent": {
                "known_opponents_count": self.opponent.known_opponents_count,
                "lobby_mean_board_power": self.opponent.lobby_mean_board_power,
                "lobby_median_board_power": self.opponent.lobby_median_board_power,
                "lobby_min_board_power": self.opponent.lobby_min_board_power,
                "lobby_max_board_power": self.opponent.lobby_max_board_power,
                "current_opponent_power": self.opponent.current_opponent_power,
                "current_opponent_power_gap": self.opponent.current_opponent_power_gap
            },
            "temporal": {
                "stage_numeric": self.temporal.stage_numeric,
                "recent_hp_delta": self.temporal.recent_hp_delta,
                "recent_hp_slope_3turns": self.temporal.recent_hp_slope_3turns,
                "recent_board_power_delta": self.temporal.recent_board_power_delta,
                "recent_gold_delta": self.temporal.recent_gold_delta,
                "estimated_rounds_to_elimination": self.temporal.estimated_rounds_to_elimination
            },
            "relative": {
                "relative_board_power_to_mean": self.relative.relative_board_power_to_mean,
                "board_power_percentile": self.relative.board_power_percentile,
                "hp_percentile": self.relative.hp_percentile,
                "economy_percentile": self.relative.economy_percentile,
                "distance_to_top4_boundary": self.relative.distance_to_top4_boundary,
                "stage_benchmark_ratio": self.relative.stage_benchmark_ratio
            },
            "metadata": self.metadata
        }
