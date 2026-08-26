"""TFT Domain Item models."""
from dataclasses import dataclass
from enum import Enum

class ItemType(Enum):
    COMPONENT = "component"
    COMPLETED = "completed"
    SPECIAL = "special"

@dataclass(frozen=True)
class Item:
    name: str
    item_type: ItemType
