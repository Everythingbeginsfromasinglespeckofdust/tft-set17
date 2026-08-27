"""Data Models for TFT Decision Engine Live Validation & Review Overlay."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from tft.domain.actions import ActionType
from tft.domain.game_state import GameState
from tft.decision.models import Recommendation, ActionScore, Reason
from tft.backtest.models import FutureObservation


class HumanEngineJudgment(str, Enum):
    """인간 평가자의 DecisionEngine 판단에 대한 정성적 평가 (정답 행동 판정이 아님)."""
    REASONABLE = "REASONABLE"
    QUESTIONABLE = "QUESTIONABLE"
    WRONG = "WRONG"
    UNKNOWN = "UNKNOWN"


class HumanPreference(str, Enum):
    """Blind Mode에서 인간이 독립적으로 선호한 행동 (최적 행동 Ground Truth가 아님)."""
    ROLL = "ROLL"
    LEVEL_UP = "LEVEL_UP"
    SAVE_GOLD = "SAVE_GOLD"
    BUY_XP = "BUY_XP"
    SELL_UNIT = "SELL_UNIT"
    UNKNOWN = "UNKNOWN"


class DecisionFailureReason(str, Enum):
    """Decision Engine 평가 실패 분류 체계 (Failure Taxonomy)."""
    BAD_STATE = "BAD_STATE"
    BAD_ECONOMIC_EVALUATION = "BAD_ECONOMIC_EVALUATION"
    BAD_BOARD_EVALUATION = "BAD_BOARD_EVALUATION"
    BAD_UPGRADE_EVALUATION = "BAD_UPGRADE_EVALUATION"
    FEASIBILITY_ERROR = "FEASIBILITY_ERROR"
    SIMULATION_ERROR = "SIMULATION_ERROR"
    WEIGHTING_QUESTION = "WEIGHTING_QUESTION"
    EXPLANATION_ERROR = "EXPLANATION_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DecisionValidationRecord:
    """단일 의사결정 시점의 종합 검증 레코드 (T0 State, 추천, 실제 행동, 인간 판단, T1+ Outcome 분리)."""
    record_id: str
    session_id: str
    timestamp_sec: float
    frame_index: int

    # T0 Observed State
    observed_state: GameState

    # Actual Observed Player Action (at or around T0)
    actual_player_action: Optional[str] = None

    # T0 DecisionEngine Computation
    recommended_action: str = "UNKNOWN"
    action_score_gap: float = 0.0
    action_scores: Dict[str, float] = field(default_factory=dict)
    score_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)

    # Human Review & Blind Preference
    human_judgment: Optional[HumanEngineJudgment] = None
    human_preference: Optional[HumanPreference] = None
    human_notes: Optional[str] = None
    failure_reason: Optional[DecisionFailureReason] = None
    reviewer_id: Optional[str] = None
    blind_mode: bool = False
    reviewed_at: Optional[str] = None

    # Future Outcome (T1+ strictly separated from T0 decision state)
    future_outcome: Optional[Dict[str, Any]] = None

    # Pipeline Performance
    pipeline_latency_ms: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "session_id": self.session_id,
            "timestamp_sec": round(self.timestamp_sec, 3),
            "frame_index": self.frame_index,
            "observed_state": {
                "stage": self.observed_state.stage,
                "round": self.observed_state.round,
                "stage_round": self.observed_state.stage_round,
                "gold": self.observed_state.player.gold,
                "hp": self.observed_state.player.hp,
                "level": self.observed_state.player.level,
                "xp": self.observed_state.player.xp,
                "board_units": len(self.observed_state.board_units),
                "bench_units": len(self.observed_state.bench_units),
                "shop_units": [u.champion for u in self.observed_state.shop_units] if self.observed_state.shop_units else []
            },
            "actual_player_action": self.actual_player_action,
            "recommendation": {
                "recommended_action": self.recommended_action,
                "action_score_gap": round(self.action_score_gap, 4),
                "action_scores": {k: round(v, 4) for k, v in self.action_scores.items()},
                "score_breakdown": self.score_breakdown,
                "reasons": self.reasons
            },
            "human_review": {
                "human_judgment": self.human_judgment.value if self.human_judgment else None,
                "human_preference": self.human_preference.value if self.human_preference else None,
                "human_notes": self.human_notes,
                "failure_reason": self.failure_reason.value if self.failure_reason else None,
                "reviewer_id": self.reviewer_id,
                "blind_mode": self.blind_mode,
                "reviewed_at": self.reviewed_at
            },
            "future_outcome": self.future_outcome,
            "pipeline_latency_ms": {k: round(v, 2) for k, v in self.pipeline_latency_ms.items()}
        }


@dataclass
class DecisionFailureCase:
    """재현 가능한 의사결정 결함 진단 케이스."""
    failure_id: str
    session_id: str
    timestamp_sec: float
    observed_state_summary: Dict[str, Any]
    engine_recommendation: str
    actual_player_action: Optional[str]
    human_preference: Optional[str]
    human_judgment: str
    failure_type: DecisionFailureReason
    evidence: List[str]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "session_id": self.session_id,
            "timestamp_sec": round(self.timestamp_sec, 3),
            "observed_state_summary": self.observed_state_summary,
            "engine_recommendation": self.engine_recommendation,
            "actual_player_action": self.actual_player_action,
            "human_preference": self.human_preference,
            "human_judgment": self.human_judgment,
            "failure_type": self.failure_type.value,
            "evidence": self.evidence,
            "created_at": self.created_at
        }
