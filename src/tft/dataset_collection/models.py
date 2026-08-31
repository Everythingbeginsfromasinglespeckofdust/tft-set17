"""Data Models for TFT Real Match Decision Dataset Collection v1.

Schema Version: DECISION_DATASET_V1
Strict Invariant: Zero leakage of future outcomes into T0 GameState.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class ActionTypeEnum(str, Enum):
    ROLL = "ROLL"
    BUY_UNIT = "BUY_UNIT"
    LEVEL_UP = "LEVEL_UP"
    SAVE_GOLD = "SAVE_GOLD"
    SELL_UNIT = "SELL_UNIT"
    BUY_XP = "BUY_XP"
    UNKNOWN = "UNKNOWN"


class HumanConfidenceEnum(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class HumanJudgmentEnum(str, Enum):
    GOOD = "GOOD"
    QUESTIONABLE = "QUESTIONABLE"
    WRONG = "WRONG"
    UNKNOWN = "UNKNOWN"


class QualityFlagEnum(str, Enum):
    VALID = "VALID"
    INCOMPLETE = "INCOMPLETE"
    SUSPICIOUS = "SUSPICIOUS"
    UNKNOWN = "UNKNOWN"


@dataclass
class VideoMetadata:
    filename: str
    video_path: Optional[str] = None
    sha256: str = ""
    resolution: str = "1920x1080"
    fps: float = 60.0
    total_frames: Optional[int] = None
    duration_sec: Optional[float] = None


@dataclass
class SessionManifest:
    session_id: str
    match_id: str
    video: VideoMetadata
    patch: str = "14.x_18.1"
    set_num: int = 18
    total_checkpoints: int = 0
    final_placement: Optional[int] = None  # Recorded strictly post-session
    created_at: Optional[float] = None
    last_updated: Optional[float] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionManifest":
        v_data = data.get("video", {})
        video_meta = VideoMetadata(
            filename=v_data.get("filename", ""),
            video_path=v_data.get("video_path"),
            sha256=v_data.get("sha256", ""),
            resolution=v_data.get("resolution", "1920x1080"),
            fps=float(v_data.get("fps", 60.0)),
            total_frames=v_data.get("total_frames"),
            duration_sec=v_data.get("duration_sec")
        )
        return cls(
            session_id=data["session_id"],
            match_id=data.get("match_id", data["session_id"]),
            video=video_meta,
            patch=data.get("patch", "14.x_18.1"),
            set_num=int(data.get("set_num", 18)),
            total_checkpoints=int(data.get("total_checkpoints", 0)),
            final_placement=data.get("final_placement"),
            created_at=data.get("created_at"),
            last_updated=data.get("last_updated"),
            notes=data.get("notes", "")
        )


@dataclass
class UnitState:
    name: str
    cost: int = 1
    star: int = 1
    items: List[str] = field(default_factory=list)
    position_row: Optional[int] = None
    position_col: Optional[int] = None
    is_bench: bool = False


@dataclass
class RawState:
    checkpoint_id: str
    stage_round: str
    stage: int
    round_num: int
    hp: int
    gold: int
    level: int
    xp: int
    streak: int = 0
    board_units: List[UnitState] = field(default_factory=list)
    bench_units: List[UnitState] = field(default_factory=list)
    shop_units: List[Optional[str]] = field(default_factory=lambda: [None] * 5)
    item_bench: List[str] = field(default_factory=list)
    augments: List[str] = field(default_factory=list)
    video_timestamp_sec: Optional[float] = None
    frame_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DerivedFeatures:
    board_power: float = 0.0
    pair_count: int = 0
    immediate_shop_upgrades: int = 0
    estimated_rounds_to_elim: Optional[float] = None
    stage_benchmark_ratio: float = 1.0
    gold_to_next_level: int = 0
    spendable_roll_budget: int = 0
    recent_hp_delta: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EnginePrediction:
    recommended_action: str
    score: float
    action_scores: Dict[str, float] = field(default_factory=dict)
    action_score_gap: float = 0.0
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)
    direction_now: str = ""
    direction_watch: List[str] = field(default_factory=list)
    direction_then: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActualPlayerAction:
    checkpoint_id: str
    actual_player_action: str = ActionTypeEnum.UNKNOWN.value
    source: str = "HUMAN_VIDEO_REVIEW"
    timestamp_sec: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HumanReview:
    checkpoint_id: str
    human_preferred_action: str = ActionTypeEnum.UNKNOWN.value
    human_confidence: str = HumanConfidenceEnum.UNKNOWN.value
    blind_review: bool = False
    human_judgment: str = HumanJudgmentEnum.UNKNOWN.value
    notes: str = ""
    source: str = "HUMAN_INPUT"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class T1Outcome:
    checkpoint_id: str
    t1_checkpoint_id: Optional[str] = None
    t1_stage_round: Optional[str] = None
    t1_hp: Optional[int] = None
    t1_gold: Optional[int] = None
    t1_board_power: Optional[float] = None
    hp_delta: Optional[int] = None
    gold_delta: Optional[int] = None
    t2_checkpoint_id: Optional[str] = None
    t2_hp: Optional[int] = None
    t2_hp_delta: Optional[int] = None
    horizon_rounds: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InteractionLog:
    checkpoint_id: str
    clicks_count: int = 0
    manual_inputs_count: int = 0
    time_spent_sec: float = 0.0
    events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DatasetRow:
    schema_version: str = "DECISION_DATASET_V1"
    session_id: str = ""
    match_id: str = ""
    checkpoint_id: str = ""
    video_timestamp_sec: Optional[float] = None
    frame_index: Optional[int] = None
    quality_flag: str = QualityFlagEnum.VALID.value
    raw_state: Dict[str, Any] = field(default_factory=dict)
    derived_features: Dict[str, Any] = field(default_factory=dict)
    engine_prediction: Dict[str, Any] = field(default_factory=dict)
    actual_action: Dict[str, Any] = field(default_factory=dict)
    human_review: Dict[str, Any] = field(default_factory=dict)
    t1_outcome: Dict[str, Any] = field(default_factory=dict)
    interaction_log: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
