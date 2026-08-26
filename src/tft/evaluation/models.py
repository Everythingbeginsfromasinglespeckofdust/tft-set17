"""Evaluation Layer Data Models."""
from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass(frozen=True)
class Metric:
    name: str
    value: float
    description: str = ""

@dataclass(frozen=True)
class EvaluationResult:
    score: float
    metrics: Dict[str, float] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
