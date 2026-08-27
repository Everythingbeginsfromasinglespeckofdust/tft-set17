"""4-Layer Information State Container for TFT Vision Validation Overlay."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from tft.vision.validation_models import HumanVerdict, TargetType


@dataclass
class ShopSlotDisplay:
    slot_index: int
    champion: Optional[str] = None
    cost: Optional[int] = None
    status: str = "UNKNOWN"  # RECOGNIZED, EMPTY, LOW_CONFIDENCE, UNKNOWN, NO_DETECTION
    confidence: float = 0.0
    is_empty: bool = False


@dataclass
class ObservedStateSummary:
    """Layer A: 실제로 비전 모델이 인식한 원본 관측 상태."""
    gold: Optional[int] = None
    raw_gold: Optional[str] = None
    gold_carried: bool = False
    hp: Optional[int] = None
    level: Optional[int] = None
    stage_round: str = "1-1"
    shop_slots: List[ShopSlotDisplay] = field(default_factory=list)
    board_unit_count: int = 0
    bench_unit_count: int = 0
    board_units: List[str] = field(default_factory=list)
    bench_units: List[str] = field(default_factory=list)


@dataclass
class DerivedStateSummary:
    """Layer B: 시계열 차분(StateDiff) 기반 파생 상태."""
    gold_delta: Optional[int] = None
    shop_slots_changed: int = 0
    shop_slots_emptied: int = 0
    board_changed: bool = False
    bench_changed: bool = False
    is_quiescent: bool = True
    is_shop_animating: bool = False


@dataclass
class DetectedActionSummary:
    """Layer C: 인과 규칙 평가 결과 (확률이 아닌 신호 체크리스트 형태)."""
    action_type: Optional[str] = None
    matched_rules: List[str] = field(default_factory=list)
    signals_checklist: List[Tuple[str, bool]] = field(default_factory=list)
    rule_match_fraction: str = "0/0"
    detection_score: float = 0.0
    target_champion: Optional[str] = None
    target_slot: Optional[int] = None
    is_multi_action: bool = False


@dataclass
class VerificationStateSummary:
    """Layer D: 사람의 검증 상태 및 세션 집계."""
    last_verdict: Optional[HumanVerdict] = None
    last_human_label: Optional[str] = None
    total_reviewed: int = 0
    correct_count: int = 0
    wrong_count: int = 0
    unknown_count: int = 0
    skipped_count: int = 0


@dataclass
class PerformanceSummary:
    """실시간 레이턴시 및 성능 지표."""
    capture_fps: float = 30.0
    analysis_fps: float = 20.0
    render_fps: float = 60.0
    data_age_sec: float = 0.0
    latency_sec: float = 0.0
    queue_length: int = 0
    dropped_frames: int = 0


@dataclass
class OverlayState:
    """Validation Overlay 전체 상태 모델."""
    observed: ObservedStateSummary = field(default_factory=ObservedStateSummary)
    derived: DerivedStateSummary = field(default_factory=DerivedStateSummary)
    detected: DetectedActionSummary = field(default_factory=DetectedActionSummary)
    verification: VerificationStateSummary = field(default_factory=VerificationStateSummary)
    performance: PerformanceSummary = field(default_factory=PerformanceSummary)

    # Playback & View Controls
    current_timestamp_sec: float = 0.0
    frame_index: int = 0
    duration_sec: float = 0.0
    playback_speed: float = 1.0
    is_paused: bool = False
    is_live: bool = False
    mode: str = "VALIDATION"  # "VALIDATION", "PRODUCTION"
    show_rois: bool = True
    session_id: str = "SESSION_A"

    timeline_events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_sec": round(self.current_timestamp_sec, 3),
            "frame_index": self.frame_index,
            "mode": self.mode,
            "is_live": self.is_live,
            "observed": {
                "gold": self.observed.gold,
                "hp": self.observed.hp,
                "level": self.observed.level,
                "stage": self.observed.stage_round,
                "shop": [c.champion for c in self.observed.shop_slots]
            },
            "derived": {
                "gold_delta": self.derived.gold_delta,
                "shop_changed": self.derived.shop_slots_changed
            },
            "detected": {
                "action": self.detected.action_type,
                "score": self.detected.detection_score,
                "rules": self.detected.matched_rules
            },
            "verification": {
                "reviewed": self.verification.total_reviewed,
                "correct": self.verification.correct_count,
                "wrong": self.verification.wrong_count
            },
            "performance": {
                "latency_sec": round(self.performance.latency_sec, 3),
                "data_age_sec": round(self.performance.data_age_sec, 3)
            }
        }
