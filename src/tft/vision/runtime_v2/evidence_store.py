"""Evidence Store and Checkpoint State Machine for Runtime Validation v2.

Core Principle: A validation record CANNOT be created without raw evidence.
If evidence is missing, the checkpoint state remains INVALID.
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


class SourceType(str, Enum):
    REAL_LIVE = "REAL_LIVE"
    VIDEO_REPLAY = "VIDEO_REPLAY"
    FIXTURE = "FIXTURE"


class CheckpointState(str, Enum):
    CAPTURED = "CAPTURED"
    PREDICTED = "PREDICTED"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    REVIEWED = "REVIEWED"
    VERIFIED = "VERIFIED"
    INVALID = "INVALID"


class DomainVerdict(str, Enum):
    CORRECT = "CORRECT"
    WRONG = "WRONG"
    UNKNOWN = "UNKNOWN"
    SKIPPED = "SKIPPED"


class DecisionQuality(str, Enum):
    REASONABLE = "REASONABLE"
    QUESTIONABLE = "QUESTIONABLE"
    WRONG = "WRONG"
    UNKNOWN = "UNKNOWN"


@dataclass
class CaptureEvidence:
    frame_path: str
    frame_sha256: str
    capture_timestamp_iso: str
    capture_monotonic: float
    monitor_index: int
    resolution_w: int
    resolution_h: int
    window_title_sanitized: str
    window_rect: Optional[Dict[str, int]] = None

    def is_complete(self) -> bool:
        return bool(
            self.frame_path
            and os.path.exists(self.frame_path)
            and self.frame_sha256
            and self.capture_timestamp_iso
        )


@dataclass
class PredictionEvidence:
    prediction_id: str
    prediction_timestamp_iso: str
    prediction_monotonic: float
    git_commit: str
    vision_hash: str
    decision_hash: str
    calibration_hash: str
    calibration_source_sha256: str
    # Vision outputs (from real vision, not synthetic)
    recognized_gold: Optional[int] = None
    recognized_hp: Optional[int] = None
    recognized_level: Optional[int] = None
    recognized_stage: Optional[str] = None
    recognized_shop: Optional[List[Dict[str, Any]]] = None
    recognized_board_count: Optional[int] = None
    vision_confidence: float = 0.0
    vision_source: str = "UNKNOWN"  # must be "REAL_FRAME" not "SYNTHETIC"
    # Decision outputs
    base_action: Optional[str] = None
    final_action: Optional[str] = None
    calibration_mode: Optional[str] = None
    is_calibration_flip: bool = False
    calibration_evidence: str = ""
    state_hash: Optional[str] = None

    def is_complete(self) -> bool:
        return bool(
            self.prediction_id
            and self.prediction_timestamp_iso
            and self.vision_source == "REAL_FRAME"
            and self.base_action is not None
        )


@dataclass
class HumanInputEvent:
    """A raw keyboard event from the human reviewer. Cannot be auto-generated."""
    input_event_id: str
    key_pressed: str  # 'C', 'W', 'R', 'B', 'L', 'S', 'X'
    timestamp_iso: str
    timestamp_monotonic: float
    checkpoint_id: str
    session_id: str

    def derive_verdict(self) -> str:
        """Key -> verdict mapping. Does NOT touch prediction."""
        mapping = {
            'C': DomainVerdict.CORRECT.value,
            'W': DomainVerdict.WRONG.value,
            'X': DomainVerdict.UNKNOWN.value,
            'S': DomainVerdict.SKIPPED.value,
        }
        return mapping.get(self.key_pressed.upper(), DomainVerdict.UNKNOWN.value)

    def derive_preferred_action(self) -> Optional[str]:
        """Key -> human-preferred action. Does NOT touch prediction."""
        mapping = {
            'R': 'ROLL',
            'B': 'BUY',
            'L': 'LEVEL_UP',
            'G': 'SAVE_GOLD',
        }
        return mapping.get(self.key_pressed.upper(), None)


@dataclass
class DomainReview:
    """Independent per-domain human review. No shared boolean flag."""
    shop_verdict: str = DomainVerdict.UNKNOWN.value
    gold_verdict: str = DomainVerdict.UNKNOWN.value
    board_verdict: str = DomainVerdict.UNKNOWN.value
    action_verdict: str = DomainVerdict.UNKNOWN.value
    state_verdict: str = DomainVerdict.UNKNOWN.value
    decision_quality: str = DecisionQuality.UNKNOWN.value
    calibration_quality: str = DecisionQuality.UNKNOWN.value
    # Human preferred action (from key event, NOT copied from prediction)
    human_preferred_action: Optional[str] = None
    review_notes: str = ""
    blind_mode: bool = False
    prediction_was_hidden: bool = False
    reveal_timestamp_iso: Optional[str] = None
    reveal_monotonic: Optional[float] = None

    def blind_order_valid(self, input_event: HumanInputEvent) -> bool:
        """Enforces: human_input_time < reveal_time when blind."""
        if not self.blind_mode:
            return True
        if self.reveal_monotonic is None:
            return False
        return input_event.timestamp_monotonic < self.reveal_monotonic


@dataclass
class EvidenceCheckpoint:
    """A validated checkpoint. Cannot be VERIFIED without all evidence."""
    checkpoint_id: str
    session_id: str
    source_type: str  # MUST be SourceType.value
    state: str = CheckpointState.CAPTURED.value

    capture: Optional[CaptureEvidence] = None
    prediction: Optional[PredictionEvidence] = None
    human_input: Optional[HumanInputEvent] = None
    review: Optional[DomainReview] = None

    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    finalized_at: Optional[str] = None
    invalidation_reason: Optional[str] = None

    def evidence_complete(self) -> bool:
        """Checks ALL required evidence is present before allowing VERIFIED state."""
        if self.capture is None or not self.capture.is_complete():
            return False
        if self.prediction is None or not self.prediction.is_complete():
            return False
        if self.human_input is None:
            return False
        if self.review is None:
            return False
        return True

    def transition(self, new_state: CheckpointState) -> bool:
        """Enforce state machine. No jumping from CAPTURED -> VERIFIED."""
        allowed = {
            CheckpointState.CAPTURED: [CheckpointState.PREDICTED, CheckpointState.INVALID],
            CheckpointState.PREDICTED: [CheckpointState.AWAITING_REVIEW, CheckpointState.INVALID],
            CheckpointState.AWAITING_REVIEW: [CheckpointState.REVIEWED, CheckpointState.INVALID],
            CheckpointState.REVIEWED: [CheckpointState.VERIFIED, CheckpointState.INVALID],
            CheckpointState.VERIFIED: [],
            CheckpointState.INVALID: [],
        }
        current = CheckpointState(self.state)
        if new_state not in allowed.get(current, []):
            return False
        if new_state == CheckpointState.VERIFIED and not self.evidence_complete():
            self.state = CheckpointState.INVALID.value
            self.invalidation_reason = "EVIDENCE_INCOMPLETE"
            return False
        self.state = new_state.value
        if new_state == CheckpointState.VERIFIED:
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


class EvidenceStore:
    """Manages evidence collection for a validation session."""

    def __init__(self, session_dir: str, session_id: str, source_type: SourceType):
        self.session_dir = session_dir
        self.session_id = session_id
        self.source_type = source_type
        self.checkpoints: List[EvidenceCheckpoint] = []

        self.raw_frames_dir = os.path.join(session_dir, "raw_frames")
        self.crops_dir = os.path.join(session_dir, "crops")
        self.predictions_dir = os.path.join(session_dir, "predictions")
        self.human_inputs_dir = os.path.join(session_dir, "human_inputs")
        self.reviews_dir = os.path.join(session_dir, "reviews")
        self.checkpoints_dir = os.path.join(session_dir, "checkpoints")
        self.errors_dir = os.path.join(session_dir, "errors")

        for d in [self.raw_frames_dir, self.crops_dir, self.predictions_dir,
                  self.human_inputs_dir, self.reviews_dir, self.checkpoints_dir,
                  self.errors_dir]:
            os.makedirs(d, exist_ok=True)

    def new_checkpoint(self) -> EvidenceCheckpoint:
        chk_id = f"CHK_{len(self.checkpoints):05d}_{uuid.uuid4().hex[:8].upper()}"
        chk = EvidenceCheckpoint(
            checkpoint_id=chk_id,
            session_id=self.session_id,
            source_type=self.source_type.value,
        )
        self.checkpoints.append(chk)
        return chk

    def save_frame(self, frame_bytes: bytes, chk_id: str, label: str = "frame"):
        """Save raw frame, return (path, sha256)."""
        fname = f"{chk_id}_{label}.png"
        path = os.path.join(self.raw_frames_dir, fname)
        with open(path, "wb") as f:
            f.write(frame_bytes)
        sha = hashlib.sha256(frame_bytes).hexdigest()
        return path, sha

    def save_prediction(self, chk_id: str, pred: PredictionEvidence) -> str:
        path = os.path.join(self.predictions_dir, f"{chk_id}_prediction.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(pred), f, indent=2, ensure_ascii=False)
        return path

    def save_human_input(self, event: HumanInputEvent) -> str:
        path = os.path.join(self.human_inputs_dir, f"{event.input_event_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(event), f, indent=2, ensure_ascii=False)
        return path

    def save_review(self, chk_id: str, review: DomainReview) -> str:
        path = os.path.join(self.reviews_dir, f"{chk_id}_review.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(review), f, indent=2, ensure_ascii=False)
        return path

    def finalize_checkpoint(self, chk: EvidenceCheckpoint) -> bool:
        if not chk.transition(CheckpointState.VERIFIED):
            # Force INVALID regardless of current state
            if chk.state not in (CheckpointState.INVALID.value,):
                chk.state = CheckpointState.INVALID.value
                if not chk.invalidation_reason:
                    chk.invalidation_reason = "EVIDENCE_INCOMPLETE_OR_INVALID_TRANSITION"
            path = os.path.join(self.checkpoints_dir, f"{chk.checkpoint_id}_INVALID.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(chk.to_dict(), f, indent=2, ensure_ascii=False)
            return False
        path = os.path.join(self.checkpoints_dir, f"{chk.checkpoint_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(chk.to_dict(), f, indent=2, ensure_ascii=False)
        return True


    def valid_checkpoints(self) -> List[EvidenceCheckpoint]:
        return [c for c in self.checkpoints if c.state == CheckpointState.VERIFIED.value]

    def stats(self) -> Dict[str, Any]:
        valid = self.valid_checkpoints()
        invalid = [c for c in self.checkpoints if c.state == CheckpointState.INVALID.value]
        return {
            "total": len(self.checkpoints),
            "valid": len(valid),
            "invalid": len(invalid),
            "pending": len(self.checkpoints) - len(valid) - len(invalid),
            "source_type": self.source_type.value,
        }
