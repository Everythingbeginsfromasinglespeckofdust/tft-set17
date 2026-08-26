"""Simulation Layer Data Models."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from tft.domain.actions import Action

@dataclass(frozen=True)
class TurnDetail:
    turn: int
    action_executed: str
    start_gold: int
    spent_gold: int
    end_gold: int
    start_level: int
    end_level: int
    start_xp: int
    end_xp: int
    interest_earned: int
    base_gold_earned: int = 5
    hp_loss: int = 0
    resulting_hp: int = 100
    board_power: float = 0.0
    hit_probability: Optional[float] = None
    notes: str = ""

@dataclass(frozen=True)
class SimulationResult:
    """Action 수행에 따른 N턴 미래 시뮬레이션 집계 결과 (Future State Trajectory)."""
    action: Action
    horizon: int
    expected_gold: float
    expected_hp: float
    expected_board_power: float
    
    # Explicit upgrade probability metrics
    any_upgrade_probability: float
    target_upgrade_probabilities: Dict[str, float] = field(default_factory=dict)
    expected_upgrade_count: float = 0.0
    
    # Heuristic survival score (explicitly distinguished from empirical calibrated probability)
    survival_score: float = 1.0
    
    estimated_placement: Optional[float] = None
    turn_by_turn: List[TurnDetail] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Backwards-compatible aliases
    @property
    def upgrade_probability(self) -> float:
        return self.any_upgrade_probability

    @property
    def survival_probability(self) -> float:
        return self.survival_score

    @property
    def horizon_turns(self) -> int:
        return self.horizon

    @property
    def final_gold(self) -> float:
        return self.expected_gold

    @property
    def final_level(self) -> int:
        return self.metadata.get("final_level", 1)

    @property
    def final_xp(self) -> int:
        return self.metadata.get("final_xp", 0)

    @property
    def cumulative_hit_prob(self) -> Optional[float]:
        return self.any_upgrade_probability
