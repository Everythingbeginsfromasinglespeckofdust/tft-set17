"""TFT Vision Observation models."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class CardObservation:
    slot_index: int
    champion_pred: Optional[str]
    cost_pred: Optional[int]
    confidence: float
    raw_ocr: str = ""
    is_empty: bool = False

@dataclass(frozen=True)
class UnitObservation:
    location: str # "hex_r0_c1" or "bench_0"
    champion_pred: Optional[str]
    star_level_pred: int = 1
    items_pred: List[str] = field(default_factory=list)
    confidence: float = 0.0

@dataclass(frozen=True)
class Observation:
    """비전 파이프라인의 물리적 관측값 컨테이너 (화면 인식 결과)."""
    timestamp_sec: float
    stage_text: Optional[str] = None
    gold_val: Optional[int] = None
    hp_val: Optional[int] = None
    level_val: Optional[int] = None
    xp_val: Optional[int] = None
    shop_cards: List[CardObservation] = field(default_factory=list)
    field_detections: List[UnitObservation] = field(default_factory=list)
    bench_detections: List[UnitObservation] = field(default_factory=list)
    overall_confidence: float = 1.0
