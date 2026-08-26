"""TFT Action Causality Audit Data Models: Frame Snapshots, Signal Transitions, and Causal Signatures."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class SignalType(str, Enum):
    """신호 유형."""
    GOLD = "GOLD"
    SHOP = "SHOP"
    BOARD = "BOARD"
    BENCH = "BENCH"
    LEVEL = "LEVEL"
    XP = "XP"
    ROUND = "ROUND"


@dataclass
class FrameSnapshot:
    """단일 비디오 프레임에서의 정밀 상태 스냅샷."""
    timestamp_sec: float
    frame_index: int
    gold: Optional[int] = None
    hp: Optional[int] = None
    level: Optional[int] = None
    xp: Optional[int] = None
    stage_round: Optional[str] = None
    shop: List[Dict[str, Any]] = field(default_factory=list)
    board: List[str] = field(default_factory=list)
    bench: List[str] = field(default_factory=list)
    shop_visual_change_score: float = 0.0
    is_stable: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_sec": round(self.timestamp_sec, 3),
            "frame_index": self.frame_index,
            "gold": self.gold,
            "hp": self.hp,
            "level": self.level,
            "xp": self.xp,
            "stage_round": self.stage_round,
            "shop": self.shop,
            "board": self.board,
            "bench": self.bench,
            "shop_visual_change_score": round(self.shop_visual_change_score, 3),
            "is_stable": self.is_stable,
            "metadata": self.metadata
        }


@dataclass
class SignalTransition:
    """개별 신호의 상태 전이 및 발생 시점."""
    signal_type: SignalType
    timestamp_sec: float
    dt_from_action: float  # timestamp - T_action (seconds)
    before_value: Any
    after_value: Any
    confidence: float = 1.0
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_type": self.signal_type.value,
            "timestamp_sec": round(self.timestamp_sec, 3),
            "dt_from_action": round(self.dt_from_action, 3),
            "before_value": self.before_value,
            "after_value": self.after_value,
            "confidence": round(self.confidence, 3),
            "description": self.description
        }


@dataclass
class EventCausalTrace:
    """단일 Ground Truth 이벤트의 프레임 레벨 인과 궤적."""
    event_id: str
    event_type: str  # ROLL, BUY_UNIT, NO_ACTION, SYSTEM_REFRESH
    target_champion: Optional[str]
    gt_timestamp_sec: float
    window_start_sec: float
    window_end_sec: float
    snapshots: List[FrameSnapshot] = field(default_factory=list)
    transitions: List[SignalTransition] = field(default_factory=list)
    sequence_pattern: str = ""  # e.g. "GOLD -> SHOP -> STABLE"
    dt_gold_onset: Optional[float] = None
    dt_shop_onset: Optional[float] = None
    dt_board_onset: Optional[float] = None
    dt_bench_onset: Optional[float] = None
    shop_slots_changed: int = 0
    is_same_champion_collision: bool = False
    is_rapid_reroll: bool = False
    inter_reroll_interval_sec: Optional[float] = None
    is_ambiguous: bool = False
    ambiguity_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "target_champion": self.target_champion,
            "gt_timestamp_sec": round(self.gt_timestamp_sec, 3),
            "window_start_sec": round(self.window_start_sec, 3),
            "window_end_sec": round(self.window_end_sec, 3),
            "sequence_pattern": self.sequence_pattern,
            "dt_gold_onset": round(self.dt_gold_onset, 3) if self.dt_gold_onset is not None else None,
            "dt_shop_onset": round(self.dt_shop_onset, 3) if self.dt_shop_onset is not None else None,
            "dt_board_onset": round(self.dt_board_onset, 3) if self.dt_board_onset is not None else None,
            "dt_bench_onset": round(self.dt_bench_onset, 3) if self.dt_bench_onset is not None else None,
            "shop_slots_changed": self.shop_slots_changed,
            "is_same_champion_collision": self.is_same_champion_collision,
            "is_rapid_reroll": self.is_rapid_reroll,
            "inter_reroll_interval_sec": round(self.inter_reroll_interval_sec, 3) if self.inter_reroll_interval_sec is not None else None,
            "is_ambiguous": self.is_ambiguous,
            "ambiguity_reason": self.ambiguity_reason,
            "transitions": [t.to_dict() for t in self.transitions],
            "total_snapshots": len(self.snapshots)
        }


@dataclass
class CausalSignature:
    """실증 데이터로부터 도출된 행동 인과 시그니처."""
    signature_id: str
    action_type: str
    name: str
    description: str
    step_sequence: List[str]
    support_count: int
    total_action_count: int
    support_rate: float
    false_alarm_count_no_action: int
    total_no_action_count: int
    specificity: float  # 1.0 - (false_alarms / total_no_action)
    median_latency_sec: float
    timing_variance: float
    likelihood_ratio: float = 1.0
    is_safe_for_standalone_detector: bool = False
    required_conjunction_signals: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signature_id": self.signature_id,
            "action_type": self.action_type,
            "name": self.name,
            "description": self.description,
            "step_sequence": self.step_sequence,
            "support_count": self.support_count,
            "total_action_count": self.total_action_count,
            "support_rate": round(self.support_rate, 4),
            "false_alarm_count_no_action": self.false_alarm_count_no_action,
            "total_no_action_count": self.total_no_action_count,
            "specificity": round(self.specificity, 4),
            "median_latency_sec": round(self.median_latency_sec, 3),
            "timing_variance": round(self.timing_variance, 4),
            "likelihood_ratio": round(self.likelihood_ratio, 2),
            "is_safe_for_standalone_detector": self.is_safe_for_standalone_detector,
            "required_conjunction_signals": self.required_conjunction_signals
        }
