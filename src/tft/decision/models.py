"""Decision Layer Models."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from tft.domain.actions import Action, ActionType

@dataclass(frozen=True)
class Reason:
    code: str
    summary: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    impact: float = 0.0

@dataclass(frozen=True)
class ActionScore:
    """Action에 대한 평가 점수 및 세부 지표."""
    action: Action
    score: float
    confidence: float
    metrics: Dict[str, float] = field(default_factory=dict)
    reasons: List[Reason] = field(default_factory=list)

@dataclass(frozen=True)
class Recommendation:
    """Decision Engine의 최종 추천 결과 및 대안 Action 목록."""
    recommended_action: Action
    score: float
    confidence: float
    alternatives: List[ActionScore]
    all_scores: List[ActionScore]
    reasons: List[Reason] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
