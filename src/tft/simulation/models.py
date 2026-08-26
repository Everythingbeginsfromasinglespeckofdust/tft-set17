"""Simulation Layer Models."""
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
    level: int
    xp: int
    interest_earned: int
    hit_probability: Optional[float] = None

@dataclass(frozen=True)
class SimulationResult:
    strategy_name: str
    horizon_turns: int
    final_gold: int
    final_level: int
    final_xp: int
    cumulative_hit_prob: Optional[float]
    turn_by_turn: List[TurnDetail] = field(default_factory=list)
