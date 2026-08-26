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
    upgrade_probability: float
    survival_probability: float
    estimated_placement: Optional[float] = None
    turn_by_turn: List[TurnDetail] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

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
        return self.upgrade_probability
