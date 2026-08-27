"""Data Models for Human Validation Campaign v1: Manifest, Review Queue, Taxonomy, and Metrics."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
from typing import Any, Dict, List, Optional, Tuple, Union

from tft.vision.pilot_models import EconomicArchetype
from tft.vision.validation_models import TargetType, HumanVerdict, ErrorReason


class ReviewTriggerType(str, Enum):
    """검증 큐(Review Queue) 후보 생성 트리거 유형."""
    ACTION = "ACTION"
    GOLD_CHANGE = "GOLD_CHANGE"
    SHOP_CHANGE = "SHOP_CHANGE"
    STATE_CHANGE = "STATE_CHANGE"
    SYSTEM_REFRESH = "SYSTEM_REFRESH"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    RANDOM_CHECK = "RANDOM_CHECK"
    MANUAL = "MANUAL"


class TemporalStage(str, Enum):
    """게임 시간대 구간 분류."""
    EARLY_GAME = "EARLY_GAME"  # < 400s (Stage 1 ~ 2)
    MID_GAME = "MID_GAME"      # 400s ~ 900s (Stage 3 ~ 4)
    LATE_GAME = "LATE_GAME"    # > 900s (Stage 5+)


class PriorityLevel(str, Enum):
    """개선 백로그 우선순위 레벨."""
    P0 = "P0"  # 치명적 회귀 / 파이프라인 중단
    P1 = "P1"  # 높은 빈도 또는 핵심 경제 행동 오탐
    P2 = "P2"  # 중간 빈도 / 경미한 상태 차분 오차
    P3 = "P3"  # 시각적 지터 / 저빈도 엣지 케이스


class FailureTaxonomy(str, Enum):
    """표준 오류 분류 체계 (Taxonomy)."""
    COARSE_SAMPLING_MERGE = "COARSE_SAMPLING_MERGE"
    GOLD_OCR_ERROR = "GOLD_OCR_ERROR"
    GOLD_DELTA_ERROR = "GOLD_DELTA_ERROR"
    SHOP_RECOGNITION_ERROR = "SHOP_RECOGNITION_ERROR"
    BOARD_RECOGNITION_ERROR = "BOARD_RECOGNITION_ERROR"
    BENCH_RECOGNITION_ERROR = "BENCH_RECOGNITION_ERROR"
    ACTION_EVENT_ERROR = "ACTION_EVENT_ERROR"
    SYSTEM_REFRESH_ERROR = "SYSTEM_REFRESH_ERROR"
    SHOP_ANIMATION_ERROR = "SHOP_ANIMATION_ERROR"
    TIMING_ERROR = "TIMING_ERROR"
    UI_ALIGNMENT_ERROR = "UI_ALIGNMENT_ERROR"
    OTHER = "OTHER"


@dataclass(frozen=True)
class ValidationReviewItem:
    """단일 검증 큐 항목."""
    review_id: str
    session_id: str
    timestamp_sec: float
    frame_index: int
    trigger_type: ReviewTriggerType
    temporal_stage: TemporalStage

    prediction: Dict[str, Any]
    observation: Dict[str, Any]
    state_diff: Dict[str, Any]
    action_event: Optional[Dict[str, Any]] = None

    # Verification state
    reviewed: bool = False
    human_verdict: Optional[HumanVerdict] = None
    human_label: Optional[str] = None
    corrected_value: Optional[Any] = None
    error_reason: Optional[FailureTaxonomy] = None
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[str] = None
    notes: Optional[str] = None
    frame_snapshot_dir: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "session_id": self.session_id,
            "timestamp_sec": round(self.timestamp_sec, 3),
            "frame_index": self.frame_index,
            "trigger_type": self.trigger_type.value,
            "temporal_stage": self.temporal_stage.value,
            "prediction": self.prediction,
            "observation": self.observation,
            "state_diff": self.state_diff,
            "action_event": self.action_event,
            "reviewed": self.reviewed,
            "human_verdict": self.human_verdict.value if self.human_verdict else None,
            "human_label": self.human_label,
            "corrected_value": self.corrected_value,
            "error_reason": self.error_reason.value if self.error_reason else None,
            "reviewer_id": self.reviewer_id,
            "reviewed_at": self.reviewed_at,
            "notes": self.notes,
            "frame_snapshot_dir": self.frame_snapshot_dir
        }


@dataclass
class ImprovementBacklogItem:
    """우선순위화된 엔지니어링 개선 과제 항목."""
    failure_id: str
    session_id: str
    timestamp_sec: float
    failure_type: FailureTaxonomy
    prediction: Any
    human_label: Any
    evidence: List[str]
    priority: PriorityLevel
    frequency: int = 1
    severity: str = "HIGH"
    recommended_fix: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "session_id": self.session_id,
            "timestamp_sec": round(self.timestamp_sec, 3),
            "failure_type": self.failure_type.value,
            "prediction": self.prediction,
            "human_label": self.human_label,
            "evidence": self.evidence,
            "priority": self.priority.value,
            "frequency": self.frequency,
            "severity": self.severity,
            "recommended_fix": self.recommended_fix,
            "created_at": self.created_at
        }


@dataclass
class CampaignSessionInfo:
    """캠페인에 등록된 개별 경기 세션 정보."""
    session_id: str
    video_path: str
    match_id: str
    player_id: str
    final_placement: int
    economic_archetype: EconomicArchetype
    resolution: Tuple[int, int] = (1280, 720)
    fps: float = 60.0
    duration_sec: float = 0.0
    total_frames: int = 0
    registered_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "video_path": self.video_path,
            "match_id": self.match_id,
            "player_id": self.player_id,
            "final_placement": self.final_placement,
            "economic_archetype": self.economic_archetype.value,
            "resolution": list(self.resolution),
            "fps": self.fps,
            "duration_sec": round(self.duration_sec, 1),
            "total_frames": self.total_frames,
            "registered_at": self.registered_at
        }


@dataclass
class CampaignManifest:
    """전체 검증 캠페인의 메타데이터 및 세션 목록 매니페스트."""
    campaign_id: str = "CAMPAIGN_001"
    version: str = "v1.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    random_seed: int = 42
    git_commit_hash: str = "HEAD"
    sessions: List[CampaignSessionInfo] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "version": self.version,
            "created_at": self.created_at,
            "random_seed": self.random_seed,
            "git_commit_hash": self.git_commit_hash,
            "session_count": len(self.sessions),
            "sessions": [s.to_dict() for s in self.sessions]
        }

    def save_to_json(self, output_path: str) -> None:
        import os, json
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load_from_json(cls, path: str) -> "CampaignManifest":
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        sessions = [
            CampaignSessionInfo(
                session_id=s["session_id"],
                video_path=s["video_path"],
                match_id=s["match_id"],
                player_id=s["player_id"],
                final_placement=s["final_placement"],
                economic_archetype=EconomicArchetype(s["economic_archetype"]),
                resolution=tuple(s.get("resolution", (1280, 720))),
                fps=s.get("fps", 60.0),
                duration_sec=s.get("duration_sec", 0.0),
                total_frames=s.get("total_frames", 0),
                registered_at=s.get("registered_at", "")
            )
            for s in data.get("sessions", [])
        ]
        return cls(
            campaign_id=data["campaign_id"],
            version=data.get("version", "v1.0"),
            created_at=data.get("created_at", ""),
            random_seed=data.get("random_seed", 42),
            git_commit_hash=data.get("git_commit_hash", ""),
            sessions=sessions
        )
