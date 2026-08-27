"""Data Models and Error Taxonomy for TFT Production Live Runtime Validation v1."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import json


class RuntimeSourceOrigin(str, Enum):
    REAL_LIVE = "REAL_LIVE"
    VIDEO_REPLAY = "VIDEO_REPLAY"
    FIXTURE = "FIXTURE"


class RuntimeAccuracyCategory(str, Enum):
    SHOP_RECOGNITION = "SHOP_RECOGNITION"
    GOLD_RECOGNITION = "GOLD_RECOGNITION"
    BOARD_RECOGNITION = "BOARD_RECOGNITION"
    ACTION_DETECTION = "ACTION_DETECTION"
    STATE_RECONSTRUCTION = "STATE_RECONSTRUCTION"
    DECISION_PIPELINE = "DECISION_PIPELINE"


class RuntimeErrorType(str, Enum):
    SHOP_RECOGNITION_ERROR = "SHOP_RECOGNITION_ERROR"
    GOLD_RECOGNITION_ERROR = "GOLD_RECOGNITION_ERROR"
    BOARD_RECOGNITION_ERROR = "BOARD_RECOGNITION_ERROR"
    ACTION_DETECTION_ERROR = "ACTION_DETECTION_ERROR"
    STATE_RECONSTRUCTION_ERROR = "STATE_RECONSTRUCTION_ERROR"
    DECISION_ERROR = "DECISION_ERROR"
    CALIBRATION_ERROR = "CALIBRATION_ERROR"
    UI_ERROR = "UI_ERROR"
    PERFORMANCE_ERROR = "PERFORMANCE_ERROR"
    OTHER = "OTHER"


class HumanVerdict(str, Enum):
    CORRECT = "CORRECT"
    WRONG = "WRONG"
    UNKNOWN = "UNKNOWN"
    SKIPPED = "SKIPPED"


@dataclass
class RuntimeCheckpoint:
    """Human verification checkpoint captured during live or video runtime."""
    checkpoint_id: str
    session_id: str
    timestamp_iso: str
    source_origin: str  # REAL_LIVE, VIDEO_REPLAY
    state_hash: str

    # Vision recognitions
    recognized_gold: int
    recognized_hp: int
    recognized_stage: str
    recognized_shop: List[Dict[str, Any]]
    recognized_board_count: int
    detected_action: str
    vision_confidence: float

    # Decision Engine & Calibration
    calibration_mode: str  # OFF, SHADOW, ON
    base_action: str
    final_action: str
    is_calibration_flip: bool
    calibration_evidence: str

    # Human Verification
    human_verdict: str  # CORRECT, WRONG, UNKNOWN
    human_preferred_action: Optional[str] = None
    error_type: Optional[str] = None
    human_notes: Optional[str] = None

    # Performance
    capture_fps: float = 60.0
    analysis_fps: float = 30.0
    decision_latency_ms: float = 0.5
    total_overlay_latency_ms: float = 2.5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeMetrics:
    total_checkpoints: int
    real_live_checkpoints: int
    human_correct_count: int
    human_wrong_count: int
    human_unknown_count: int

    shop_accuracy: float
    gold_accuracy: float
    board_accuracy: float
    action_accuracy: float
    overall_runtime_accuracy: float

    mean_decision_latency_ms: float
    p95_decision_latency_ms: float
    max_decision_latency_ms: float
    mean_overlay_latency_ms: float
    p95_overlay_latency_ms: float

    capture_fps: float
    analysis_fps: float
    dropped_frames_rate: float

    calibration_applied_count: int
    calibration_flip_count: int
    rollback_count: int
    final_gate_status: str
