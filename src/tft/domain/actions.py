"""TFT Decision Actions."""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

class ActionType(Enum):
    SAVE_GOLD = "SAVE_GOLD"
    LEVEL_UP = "LEVEL_UP"
    ROLL = "ROLL"
    BUY_UNIT = "BUY_UNIT"
    SELL_UNIT = "SELL_UNIT"
    SLAM_ITEM = "SLAM_ITEM"
    HOLD_ITEM = "HOLD_ITEM"
    PIVOT = "PIVOT"

@dataclass(frozen=True)
class Action:
    action_type: ActionType
    target: Optional[str] = None
    budget_gold: Optional[int] = None
    target_level: Optional[int] = None
    metadata: Dict[str, Any] = None
