"""Data models for Evidence-First Video Replay Validation v1.

Core Principle:
- SourceType is STRICTLY "VIDEO_REPLAY" (never REAL_LIVE)
- Checkpoint cannot be VERIFIED without frame, prediction, human input, and review
- Human label cannot be auto-copied from prediction
- Independent domain reviews (Shop, Gold, Board, Action, State, Decision, Calibration)
"""
from __future__ import annotations
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class VideoSourceType(str, Enum):
    VIDEO_REPLAY = "VIDEO_REPLAY"


class VideoCheckpointState(str, Enum):
    CAPTURED = "CAPTURED"
    PREDICTED = "PREDICTED"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    REVIEWED = "REVIEWED"
    VERIFIED = "VERIFIED"
    INVALID = "INVALID"


class VideoDomainVerdict(str, Enum):
    CORRECT = "CORRECT"
    WRONG = "WRONG"
    UNKNOWN = "UNKNOWN"
    SKIPPED = "SKIPPED"


class VideoDecisionQuality(str, Enum):
    REASONABLE = "REASONABLE"
    QUESTIONABLE = "QUESTIONABLE"
    WRONG = "WRONG"
    UNKNOWN = "UNKNOWN"


@dataclass
class VideoSourceInfo:
    video_path: str
    video_sha256: str
    duration_sec: float
    fps: float
    resolution_w: int
    resolution_h: int
    total_frames: int
    is_original: bool = True
    overlay_status: str = "NO_OVERLAY_ARTIFACTS"
    file_size_mb: float = 0.0


@dataclass
class VideoFrameEvidence:
    frame_path: str
    frame_sha256: str
    video_path: str
    video_sha256: str
    video_timestamp_sec: float
    frame_index: int
    resolution_w: int
    resolution_h: int

    def is_complete(self) -> bool:
        return bool(
            self.frame_path
            and os.path.exists(self.frame_path)
            and self.frame_sha256
            and self.video_sha256
        )


@dataclass
class VideoPredictionEvidence:
    prediction_id: str
    prediction_timestamp_iso: str
    prediction_monotonic: float
    video_timestamp_sec: float
    frame_index: int
    git_commit: str
    vision_hash: str
    decision_hash: str
    calibration_hash: str
    calibration_source_sha256: str
    # Vision outputs from real recognizers
    recognized_gold: Optional[int] = None
    gold_raw_text: str = ""
    gold_confidence: float = 0.0
    recognized_hp: Optional[int] = None
    recognized_level: Optional[int] = None
    recognized_stage: Optional[str] = None
    recognized_shop: Optional[List[Dict[str, Any]]] = None
    recognized_board_units: Optional[List[Dict[str, Any]]] = None
    recognized_board_count: int = 0
    recognized_action: Optional[str] = None
    action_confidence: float = 0.0
    # Decision outputs from frozen DecisionEngine + CALIB_C
    base_action: Optional[str] = None
    calibrated_action: Optional[str] = None
    final_action: Optional[str] = None
    is_calibration_flip: bool = False
    calibration_delta: float = 0.0
    calibration_evidence: str = ""
    state_hash: Optional[str] = None
    decision_scores: Dict[str, float] = field(default_factory=dict)
    vision_source: str = "VIDEO_FRAME"  # Frame decoded from real video file

    def is_complete(self) -> bool:
        return bool(
            self.prediction_id
            and self.vision_source == "VIDEO_FRAME"
            and self.final_action is not None
        )


@dataclass
class VideoHumanInputEvent:
    """A raw keyboard event from the human reviewer."""
    input_event_id: str
    key_pressed: str  # 'C', 'W', 'E', 'X', 'R', 'B', 'L', 'G'
    timestamp_iso: str
    timestamp_monotonic: float
    checkpoint_id: str
    session_id: str

    def derive_verdict(self) -> str:
        mapping = {
            'C': VideoDomainVerdict.CORRECT.value,
            'W': VideoDomainVerdict.WRONG.value,
            'X': VideoDomainVerdict.UNKNOWN.value,
            'S': VideoDomainVerdict.SKIPPED.value,
        }
        return mapping.get(self.key_pressed.upper(), VideoDomainVerdict.UNKNOWN.value)

    def derive_preferred_action(self) -> Optional[str]:
        mapping = {
            'R': 'ROLL',
            'B': 'BUY',
            'L': 'LEVEL_UP',
            'G': 'SAVE_GOLD',
        }
        return mapping.get(self.key_pressed.upper(), None)


@dataclass
class VideoDomainReview:
    """Independent per-domain human review."""
    shop_verdict: str = VideoDomainVerdict.UNKNOWN.value
    gold_verdict: str = VideoDomainVerdict.UNKNOWN.value
    board_verdict: str = VideoDomainVerdict.UNKNOWN.value
    action_verdict: str = VideoDomainVerdict.UNKNOWN.value
    state_verdict: str = VideoDomainVerdict.UNKNOWN.value
    decision_quality: str = VideoDecisionQuality.UNKNOWN.value
    calibration_quality: str = VideoDecisionQuality.UNKNOWN.value
    human_preferred_action: Optional[str] = None
    human_notes: str = ""
    blind_mode: bool = False
    prediction_was_hidden: bool = False
    human_decision_timestamp_iso: Optional[str] = None
    prediction_reveal_timestamp_iso: Optional[str] = None
    human_decision_monotonic: Optional[float] = None
    prediction_reveal_monotonic: Optional[float] = None

    def blind_order_valid(self) -> bool:
        if not self.blind_mode:
            return True
        if self.human_decision_monotonic is None or self.prediction_reveal_monotonic is None:
            return False
        return self.human_decision_monotonic < self.prediction_reveal_monotonic


@dataclass
class VideoCheckpoint:
    checkpoint_id: str
    session_id: str
    source_type: str = VideoSourceType.VIDEO_REPLAY.value
    state: str = VideoCheckpointState.CAPTURED.value

    capture: Optional[VideoFrameEvidence] = None
    prediction: Optional[VideoPredictionEvidence] = None
    human_input: Optional[VideoHumanInputEvent] = None
    review: Optional[VideoDomainReview] = None

    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    finalized_at: Optional[str] = None
    invalidation_reason: Optional[str] = None

    def evidence_complete(self) -> bool:
        if self.capture is None or not self.capture.is_complete():
            return False
        if self.prediction is None or not self.prediction.is_complete():
            return False
        if self.human_input is None:
            return False
        if self.review is None:
            return False
        return True

    def transition(self, new_state: VideoCheckpointState) -> bool:
        allowed = {
            VideoCheckpointState.CAPTURED: [VideoCheckpointState.PREDICTED, VideoCheckpointState.INVALID],
            VideoCheckpointState.PREDICTED: [VideoCheckpointState.AWAITING_REVIEW, VideoCheckpointState.INVALID],
            VideoCheckpointState.AWAITING_REVIEW: [VideoCheckpointState.REVIEWED, VideoCheckpointState.INVALID],
            VideoCheckpointState.REVIEWED: [VideoCheckpointState.VERIFIED, VideoCheckpointState.INVALID],
            VideoCheckpointState.VERIFIED: [],
            VideoCheckpointState.INVALID: [],
        }
        current = VideoCheckpointState(self.state)
        if new_state not in allowed.get(current, []):
            return False
        if new_state == VideoCheckpointState.VERIFIED and not self.evidence_complete():
            self.state = VideoCheckpointState.INVALID.value
            self.invalidation_reason = "EVIDENCE_INCOMPLETE"
            return False
        self.state = new_state.value
        if new_state == VideoCheckpointState.VERIFIED:
            self.finalized_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "session_id": self.session_id,
            "source_type": self.source_type,
            "state": self.state,
            "evidence_complete": self.evidence_complete(),
            "created_at": self.created_at,
            "finalized_at": self.finalized_at,
            "invalidation_reason": self.invalidation_reason,
            "capture": asdict(self.capture) if self.capture else None,
            "prediction": asdict(self.prediction) if self.prediction else None,
            "human_input": asdict(self.human_input) if self.human_input else None,
            "review": asdict(self.review) if self.review else None,
        }
