"""Data Models for Human Verification, Error Diagnostic Snapshots, and Ground Truth Logging."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class TargetType(str, Enum):
    """검증 대상 인식 컴포넌트 유형."""
    ACTION = "ACTION"
    SHOP_SLOT = "SHOP_SLOT"
    GOLD = "GOLD"
    HP = "HP"
    STAGE = "STAGE"
    LEVEL = "LEVEL"
    BOARD = "BOARD"
    BENCH = "BENCH"


class HumanVerdict(str, Enum):
    """사람의 평가 판정."""
    CORRECT = "CORRECT"
    WRONG = "WRONG"
    UNKNOWN = "UNKNOWN"
    EDITED = "EDITED"
    SKIPPED = "SKIPPED"


class ErrorReason(str, Enum):
    """오류 진단 사유 카테고리."""
    SHOP_ERROR = "SHOP_ERROR"
    GOLD_ERROR = "GOLD_ERROR"
    BOARD_ERROR = "BOARD_ERROR"
    BENCH_ERROR = "BENCH_ERROR"
    ACTION_ERROR = "ACTION_ERROR"
    TIMING_ERROR = "TIMING_ERROR"
    SYSTEM_EVENT = "SYSTEM_EVENT"
    ANIMATION_BLUR = "ANIMATION_BLUR"
    OTHER = "OTHER"


@dataclass(frozen=True)
class VerificationEvent:
    """사람이 화면을 보고 기록한 단일 검증 및 레이블 이벤트."""
    verification_id: str
    session_id: str
    timestamp_sec: float
    frame_index: int

    target_type: TargetType
    predicted_value: Any

    human_verdict: HumanVerdict
    human_label: Optional[str] = None
    corrected_value: Optional[Any] = None

    error_reason: Optional[ErrorReason] = None
    notes: Optional[str] = None

    frame_path: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "session_id": self.session_id,
            "timestamp_sec": round(self.timestamp_sec, 3),
            "frame_index": self.frame_index,
            "target_type": self.target_type.value,
            "predicted_value": self.predicted_value,
            "human_verdict": self.human_verdict.value,
            "human_label": self.human_label,
            "corrected_value": self.corrected_value,
            "error_reason": self.error_reason.value if self.error_reason else None,
            "notes": self.notes,
            "frame_path": self.frame_path,
            "created_at": self.created_at
        }


@dataclass
class VerificationSummary:
    """세션 단위 검증 집계 및 정확도 통계."""
    session_id: str
    total_reviewed: int = 0
    correct_count: int = 0
    wrong_count: int = 0
    unknown_count: int = 0
    skipped_count: int = 0
    errors_by_reason: Dict[str, int] = field(default_factory=dict)
    errors_by_target: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "total_reviewed": self.total_reviewed,
            "correct_count": self.correct_count,
            "wrong_count": self.wrong_count,
            "unknown_count": self.unknown_count,
            "skipped_count": self.skipped_count,
            "accuracy": round(self.correct_count / max(1, self.total_reviewed - self.skipped_count), 4) if (self.total_reviewed - self.skipped_count) > 0 else 0.0,
            "errors_by_reason": self.errors_by_reason,
            "errors_by_target": self.errors_by_target
        }
