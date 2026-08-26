"""TFT Domain Augment models."""
from dataclasses import dataclass
from enum import Enum

class AugmentTier(Enum):
    SILVER = 1
    GOLD = 2
    PRISMATIC = 3

@dataclass(frozen=True)
class Augment:
    name: str
    tier: AugmentTier
