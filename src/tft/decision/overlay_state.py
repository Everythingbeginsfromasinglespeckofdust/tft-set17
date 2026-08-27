"""Overlay State representation for TFT Decision Engine Live Validation."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from tft.domain.game_state import GameState, PlayerState
from tft.decision.models import Recommendation, ActionScore
from tft.decision.validation_models import HumanEngineJudgment, HumanPreference


@dataclass
class DecisionPerformanceState:
    """의사결정 파이프라인 단계별 레이턴시 및 FPS 측정값."""
    vision_latency_ms: float = 0.0
    game_state_latency_ms: float = 0.0
    decision_latency_ms: float = 0.0
    render_latency_ms: float = 0.0
    total_overlay_latency_ms: float = 0.0
    capture_fps: float = 30.0
    analysis_fps: float = 20.0
    render_fps: float = 60.0
    dropped_frames: int = 0


@dataclass
class DecisionOverlayState:
    """Decision Validation Overlay의 통합 렌더링 상태 컨테이너."""
    # Session info
    session_id: str = "SESSION_A"
    mode: str = "VALIDATION"  # VALIDATION | PRODUCTION
    timestamp_sec: float = 0.0
    frame_index: int = 0
    is_paused: bool = False
    playback_speed: float = 1.0
    show_rois: bool = True

    # 1. Observed Game State (T0)
    observed_state: Optional[GameState] = None
    actual_player_action: Optional[str] = None
    actual_action_evidence: Optional[str] = None

    # 2. Decision Engine Output (T0)
    recommendation: Optional[Recommendation] = None
    recommended_action: str = "NONE"
    action_scores: Dict[str, float] = field(default_factory=dict)
    action_score_gap: float = 0.0
    score_breakdowns: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)

    # 3. Blind Mode & Human Review
    blind_mode: bool = False
    reveal_recommendation: bool = True
    human_preference: Optional[HumanPreference] = None
    human_judgment: Optional[HumanEngineJudgment] = None
    human_notes: Optional[str] = None

    # 4. Observed Future Outcome (T1+ strictly separated)
    future_outcome: Optional[Dict[str, Any]] = None

    # 5. Performance
    performance: DecisionPerformanceState = field(default_factory=DecisionPerformanceState)

    # 6. Timeline markers (timestamp, label, type)
    timeline_markers: List[Dict[str, Any]] = field(default_factory=list)
