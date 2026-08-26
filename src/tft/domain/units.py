"""TFT Domain Unit & Champion models."""
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass(frozen=True)
class BoardPosition:
    row: int
    col: int

@dataclass(frozen=True)
class Unit:
    champion: str
    cost: int
    star_level: int = 1
    items: List[str] = field(default_factory=list)
    position: Optional[BoardPosition] = None
    slot_index: Optional[int] = None
    is_bench: bool = False

    def to_dict(self) -> dict:
        d = {
            "champion": self.champion,
            "cost": self.cost,
            "star_level": self.star_level,
            "items": list(self.items)
        }
        if self.position is not None:
            d["position"] = {"row": self.position.row, "col": self.position.col}
        if self.slot_index is not None:
            d["slot_index"] = self.slot_index
        return d
