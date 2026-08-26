"""Decision Layer Models."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from tft.domain.actions import Action, ActionType

@dataclass(frozen=True)
class ActionScore:
    action: Action
    score: float
    confidence: float
    projected_gold: int
    projected_power_delta: float

@dataclass(frozen=True)
class Reason:
    summary: str
    evidence: str
    impact: float

@dataclass(frozen=True)
class Recommendation:
    recommended_action: Action
    score: float
    confidence: float
    all_scores: List[ActionScore]
    reasons: List[Reason] = field(default_factory=list)
