"""Data Models and Schema for TFT Multi-Session Pilot v1."""
from dataclasses import dataclass, field
from enum import Enum
import json
import os
from typing import Any, Dict, List, Optional, Tuple


class EconomicArchetype(str, Enum):
    """플레이어 경제 운영 전략 분류."""
    REROLL_HEAVY = "REROLL_HEAVY"
    FAST_LEVELUP = "FAST_LEVELUP"
    BALANCED_STANDARD = "BALANCED_STANDARD"
    HYPER_ROLL = "HYPER_ROLL"
    UNKNOWN = "UNKNOWN"


class PilotGateVerdict(str, Enum):
    """Multi-Session Acceptance Gate 판정."""
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class LineageLossStage(str, Enum):
    """Causal Signal 손실 단계 분류."""
    NONE = "NONE"
    OCR_MISSING = "OCR_MISSING"
    COARSE_SAMPLING_MERGE = "COARSE_SAMPLING_MERGE"
    ANIMATION_BLUR = "ANIMATION_BLUR"
    THRESHOLD_FILTER = "THRESHOLD_FILTER"
    UNKNOWN = "UNKNOWN"


class PilotFailureType(str, Enum):
    """16가지 실패 사례 진단 분류 체계."""
    SHOP_RECOGNITION_ERROR = "SHOP_RECOGNITION_ERROR"
    GOLD_RAW_OCR_ERROR = "GOLD_RAW_OCR_ERROR"
    GOLD_STABILIZATION_ERROR = "GOLD_STABILIZATION_ERROR"
    GOLD_DELTA_ERROR = "GOLD_DELTA_ERROR"
    SYSTEM_REFRESH_ERROR = "SYSTEM_REFRESH_ERROR"
    SHOP_ANIMATION_ERROR = "SHOP_ANIMATION_ERROR"
    ROLL_FP = "ROLL_FP"
    ROLL_FN = "ROLL_FN"
    BUY_FP = "BUY_FP"
    BUY_FN = "BUY_FN"
    LEVEL_UP_ERROR = "LEVEL_UP_ERROR"
    BOARD_RECOGNITION_ERROR = "BOARD_RECOGNITION_ERROR"
    BENCH_RECOGNITION_ERROR = "BENCH_RECOGNITION_ERROR"
    TIMING_ERROR = "TIMING_ERROR"
    MULTI_ACTION = "MULTI_ACTION"
    UNKNOWN = "UNKNOWN"


@dataclass
class PilotSession:
    """단일 파일럿 세션 메타데이터."""
    session_id: str
    video_path: str
    duration: float
    resolution: str = "1280x720"
    source_fps: float = 60.0
    match_id: Optional[str] = None
    participant_id: Optional[str] = None
    identity_verified: bool = False
    final_placement: Optional[int] = None
    economic_archetype: EconomicArchetype = EconomicArchetype.UNKNOWN
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "video_path": self.video_path,
            "duration": round(self.duration, 2),
            "resolution": self.resolution,
            "source_fps": round(self.source_fps, 2),
            "match_id": self.match_id,
            "participant_id": self.participant_id,
            "identity_verified": self.identity_verified,
            "final_placement": self.final_placement,
            "economic_archetype": self.economic_archetype.value,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PilotSession":
        return cls(
            session_id=d["session_id"],
            video_path=d["video_path"],
            duration=float(d.get("duration", 0.0)),
            resolution=d.get("resolution", "1280x720"),
            source_fps=float(d.get("source_fps", 60.0)),
            match_id=d.get("match_id"),
            participant_id=d.get("participant_id"),
            identity_verified=bool(d.get("identity_verified", False)),
            final_placement=d.get("final_placement"),
            economic_archetype=EconomicArchetype(d.get("economic_archetype", "UNKNOWN")),
            metadata=d.get("metadata", {})
        )


@dataclass
class PilotManifest:
    """파일럿 세션 등록 관리자."""
    version: str = "1.0"
    description: str = "TFT Multi-Session Pilot Registry"
    sessions: List[PilotSession] = field(default_factory=list)

    def add_session(self, session: PilotSession) -> None:
        # Check duplicate
        if any(s.session_id == session.session_id for s in self.sessions):
            self.sessions = [s for s in self.sessions if s.session_id != session.session_id]
        self.sessions.append(session)

    def get_session(self, session_id: str) -> Optional[PilotSession]:
        for s in self.sessions:
            if s.session_id == session_id:
                return s
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "description": self.description,
            "total_sessions": len(self.sessions),
            "sessions": [s.to_dict() for s in self.sessions]
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PilotManifest":
        manifest = cls(
            version=d.get("version", "1.0"),
            description=d.get("description", "")
        )
        for s_data in d.get("sessions", []):
            manifest.add_session(PilotSession.from_dict(s_data))
        return manifest

    def save_to_json(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load_from_json(cls, path: str) -> "PilotManifest":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


@dataclass
class LineageRecord:
    """GT Action -> GoldObservation -> GoldDeltaEvent -> ActionEvent 추적 레코드."""
    gt_action_id: str
    gt_timestamp_sec: float
    gt_action_type: str
    gold_before: Optional[int] = None
    gold_after: Optional[int] = None
    gold_delta_val: Optional[int] = None
    gold_delta_observed: bool = False
    gold_delta_timestamp_sec: Optional[float] = None
    action_event_detected: bool = False
    action_event_type: Optional[str] = None
    action_event_timestamp_sec: Optional[float] = None
    loss_stage: LineageLossStage = LineageLossStage.NONE
    loss_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gt_action_id": self.gt_action_id,
            "gt_timestamp_sec": round(self.gt_timestamp_sec, 3),
            "gt_action_type": self.gt_action_type,
            "gold_before": self.gold_before,
            "gold_after": self.gold_after,
            "gold_delta_val": self.gold_delta_val,
            "gold_delta_observed": self.gold_delta_observed,
            "gold_delta_timestamp_sec": round(self.gold_delta_timestamp_sec, 3) if self.gold_delta_timestamp_sec else None,
            "action_event_detected": self.action_event_detected,
            "action_event_type": self.action_event_type,
            "action_event_timestamp_sec": round(self.action_event_timestamp_sec, 3) if self.action_event_timestamp_sec else None,
            "loss_stage": self.loss_stage.value,
            "loss_reason": self.loss_reason
        }


@dataclass
class SessionMetrics:
    """단일 세션의 종합 검증 지표."""
    session_id: str
    total_frames_sampled: int = 0
    duration_sec: float = 0.0

    # 1. Shop Metrics
    shop_champion_accuracy: float = 0.0
    shop_cost_accuracy: float = 0.0
    shop_slot_localization_accuracy: float = 0.0
    shop_unknown_rate: float = 0.0
    shop_no_detection_rate: float = 0.0

    # 2. Gold Metrics (Strictly separated)
    raw_ocr_valid_rate: float = 0.0
    raw_ocr_exact_accuracy: float = 0.0
    carried_forward_rate: float = 0.0
    stabilized_accuracy: float = 0.0
    gold_unknown_rate: float = 0.0
    gold_missing_rate: float = 0.0
    gold_delta_count: int = 0
    gold_delta_precision: float = 0.0
    gold_delta_recall: float = 0.0

    # 3. Action Metrics
    roll_precision: float = 0.0
    roll_recall: float = 0.0
    roll_f1: float = 0.0
    buy_precision: float = 0.0
    buy_recall: float = 0.0
    buy_f1: float = 0.0
    system_refresh_precision: float = 0.0
    system_refresh_recall: float = 0.0
    system_refresh_f1: float = 0.0

    # 4. Action Counts
    gt_roll_count: int = 0
    gt_buy_count: int = 0
    gt_no_action_count: int = 0
    gt_system_refresh_count: int = 0
    gt_levelup_count: int = 0
    detected_roll_count: int = 0
    detected_buy_count: int = 0
    detected_system_refresh_count: int = 0
    total_fp_count: int = 0
    total_fn_count: int = 0

    # 5. Production vs Replay Gap
    rule_replay_roll_f1: float = 0.0
    rule_replay_buy_f1: float = 0.0
    production_roll_f1: float = 0.0
    production_buy_f1: float = 0.0
    replay_production_gap_roll: float = 0.0
    replay_production_gap_buy: float = 0.0

    # 6. Leakage & Stability
    leakage_violations: int = 0
    timing_mae_sec: float = 0.0

    # 7. Processing Performance
    processing_time_sec: float = 0.0
    effective_fps: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "duration_sec": round(self.duration_sec, 2),
            "total_frames_sampled": self.total_frames_sampled,
            "shop": {
                "champion_accuracy": round(self.shop_champion_accuracy, 4),
                "cost_accuracy": round(self.shop_cost_accuracy, 4),
                "slot_localization_accuracy": round(self.shop_slot_localization_accuracy, 4),
                "unknown_rate": round(self.shop_unknown_rate, 4),
                "no_detection_rate": round(self.shop_no_detection_rate, 4)
            },
            "gold": {
                "raw_ocr_valid_rate": round(self.raw_ocr_valid_rate, 4),
                "raw_ocr_exact_accuracy": round(self.raw_ocr_exact_accuracy, 4),
                "carried_forward_rate": round(self.carried_forward_rate, 4),
                "stabilized_accuracy": round(self.stabilized_accuracy, 4),
                "unknown_rate": round(self.gold_unknown_rate, 4),
                "missing_rate": round(self.gold_missing_rate, 4),
                "delta_count": self.gold_delta_count,
                "delta_precision": round(self.gold_delta_precision, 4),
                "delta_recall": round(self.gold_delta_recall, 4)
            },
            "actions": {
                "ROLL": {"precision": round(self.roll_precision, 4), "recall": round(self.roll_recall, 4), "f1": round(self.roll_f1, 4)},
                "BUY_UNIT": {"precision": round(self.buy_precision, 4), "recall": round(self.buy_recall, 4), "f1": round(self.buy_f1, 4)},
                "SYSTEM_REFRESH": {"precision": round(self.system_refresh_precision, 4), "recall": round(self.system_refresh_recall, 4), "f1": round(self.system_refresh_f1, 4)}
            },
            "counts": {
                "gt_roll": self.gt_roll_count,
                "gt_buy": self.gt_buy_count,
                "gt_no_action": self.gt_no_action_count,
                "gt_system_refresh": self.gt_system_refresh_count,
                "detected_roll": self.detected_roll_count,
                "detected_buy": self.detected_buy_count,
                "total_fp": self.total_fp_count,
                "total_fn": self.total_fn_count
            },
            "production_gap": {
                "rule_replay_roll_f1": round(self.rule_replay_roll_f1, 4),
                "production_roll_f1": round(self.production_roll_f1, 4),
                "gap_roll": round(self.replay_production_gap_roll, 4),
                "rule_replay_buy_f1": round(self.rule_replay_buy_f1, 4),
                "production_buy_f1": round(self.production_buy_f1, 4),
                "gap_buy": round(self.replay_production_gap_buy, 4)
            },
            "leakage_violations": self.leakage_violations,
            "timing_mae_sec": round(self.timing_mae_sec, 4),
            "performance": {
                "processing_time_sec": round(self.processing_time_sec, 2),
                "effective_fps": round(self.effective_fps, 2)
            }
        }


@dataclass
class CrossSessionSummary:
    """복수 세션 간의 통계적 집계 및 분산 분석 결과."""
    session_count: int = 0
    gate_verdict: PilotGateVerdict = PilotGateVerdict.INSUFFICIENT_DATA

    # Pooled metrics
    pooled_roll_f1: float = 0.0
    pooled_buy_f1: float = 0.0
    pooled_fp_count: int = 0

    # Cross-session statistics for ROLL F1
    roll_f1_mean: float = 0.0
    roll_f1_median: float = 0.0
    roll_f1_min: float = 0.0
    roll_f1_max: float = 0.0
    roll_f1_std: float = 0.0

    # Cross-session statistics for BUY F1
    buy_f1_mean: float = 0.0
    buy_f1_median: float = 0.0
    buy_f1_min: float = 0.0
    buy_f1_max: float = 0.0
    buy_f1_std: float = 0.0

    # Gold Statistics
    gold_raw_ocr_valid_mean: float = 0.0
    gold_stabilized_acc_mean: float = 0.0

    total_leakage_violations: int = 0
    sessions_evaluated: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_count": self.session_count,
            "gate_verdict": self.gate_verdict.value,
            "sessions_evaluated": self.sessions_evaluated,
            "pooled": {
                "roll_f1": round(self.pooled_roll_f1, 4),
                "buy_f1": round(self.pooled_buy_f1, 4),
                "total_fp": self.pooled_fp_count
            },
            "roll_f1_stats": {
                "mean": round(self.roll_f1_mean, 4),
                "median": round(self.roll_f1_median, 4),
                "min": round(self.roll_f1_min, 4),
                "max": round(self.roll_f1_max, 4),
                "std": round(self.roll_f1_std, 4)
            },
            "buy_f1_stats": {
                "mean": round(self.buy_f1_mean, 4),
                "median": round(self.buy_f1_median, 4),
                "min": round(self.buy_f1_min, 4),
                "max": round(self.buy_f1_max, 4),
                "std": round(self.buy_f1_std, 4)
            },
            "gold_stats": {
                "raw_ocr_valid_mean": round(self.gold_raw_ocr_valid_mean, 4),
                "stabilized_acc_mean": round(self.gold_stabilized_acc_mean, 4)
            },
            "total_leakage_violations": self.total_leakage_violations
        }
