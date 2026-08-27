"""TFT Vision Observation models -- with source tracking and per-field confidence."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ObservedField:
    """단일 관측 필드의 값, 추출 출처 및 신뢰도 컨테이너."""
    value: Any
    source: str  # e.g. "ocr", "template_matching", "hsv_color", "heuristic"
    confidence: float = 1.0
    raw_text: Optional[str] = None


@dataclass(frozen=True)
class CardObservation:
    """상점 단일 슬롯 관측 결과."""
    slot_index: int
    champion_pred: Optional[str]
    cost_pred: Optional[int]
    confidence: float
    raw_ocr: str = ""
    is_empty: bool = False
    source: str = "hybrid_shop_recognizer"


@dataclass(frozen=True)
class UnitObservation:
    """필드 또는 벤치 단일 슬롯 유닛 관측 결과."""
    location: str  # "hex_r0_c1" or "bench_0"
    champion_pred: Optional[str]
    star_level_pred: int = 1
    items_pred: List[str] = field(default_factory=list)
    confidence: float = 0.0
    source: str = "board_recognizer"


@dataclass(frozen=True)
class Observation:
    """비전 파이프라인의 물리적 관측값 컨테이너 (화면 인식 원시 결과).

    주의: Observation은 화면에서 관측된 '인식값'이며,
    도메인 정규화 상태인 GameState와 구분된다.
    """
    timestamp_sec: float
    frame_index: int = 0
    stage_text: Optional[str] = None
    gold_val: Optional[int] = None
    hp_val: Optional[int] = None
    level_val: Optional[int] = None
    xp_val: Optional[int] = None
    shop_cards: List[CardObservation] = field(default_factory=list)
    field_detections: List[UnitObservation] = field(default_factory=list)
    bench_detections: List[UnitObservation] = field(default_factory=list)
    sources: Dict[str, str] = field(default_factory=dict)
    confidences: Dict[str, float] = field(default_factory=dict)
    overall_confidence: float = 1.0
    geometry_source: Optional[str] = None
    geometry_confidence: Optional[float] = None
    game_region: Optional[Dict[str, Any]] = None
    shop_region: Optional[Dict[str, Any]] = None
    shop_slot_regions: List[Dict[str, Any]] = field(default_factory=list)
    gold_region: Optional[Dict[str, Any]] = None
    board_region: Optional[Dict[str, Any]] = None
    stage_region: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
