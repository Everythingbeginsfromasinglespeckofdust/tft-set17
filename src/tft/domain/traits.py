"""TFT Domain Trait models."""
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class TraitBreakpoint:
    tier: int
    required_count: int

@dataclass(frozen=True)
class Trait:
    name: str
    active_count: int
    tier: int
    breakpoints: List[int]
