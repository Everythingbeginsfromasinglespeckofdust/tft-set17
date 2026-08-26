"""Backtesting Framework Data Models for TFT Decision Engine."""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
from tft.domain.game_state import GameState
from tft.domain.actions import ActionType

class ActualActionType(str, Enum):
    ROLL = "ROLL"
    LEVEL_UP = "LEVEL_UP"
    SAVE_GOLD = "SAVE_GOLD"
    UNKNOWN = "UNKNOWN"

@dataclass
class ObservedState:
    """T0 시점에 실제 관측된 게임 상태 (Observed Reality at T0)."""
    match_id: str
    participant_id: str
    stage: int
    round_num: int
    stage_round: str
    state: GameState
    actual_action: ActualActionType = ActualActionType.UNKNOWN
    actual_action_evidence: Optional[str] = None
    timestamp_sec: Optional[float] = None

@dataclass
class FutureObservation:
    """T1+ 이후 실제 경기에서 관측된 미래 결과 (Observed Reality at T1+)."""
    final_placement: Optional[int] = None
    top4: Optional[bool] = None
    hp_after_n_rounds: Optional[int] = None
    gold_after_n_rounds: Optional[int] = None
    level_after_n_rounds: Optional[int] = None
    last_round: Optional[int] = None
    time_eliminated: Optional[float] = None
    elimination_stage_round: Optional[str] = None

@dataclass
class BacktestSample:
    """백테스트 데이터셋의 단일 샘플 (Snapshot 단위)."""
    sample_id: str
    match_id: str
    participant_id: str
    data_source: str # e.g. "historical_match_snapshot", "historical_video_audit", "synthetic_simulation"
    observed_state: ObservedState
    future_observation: FutureObservation
    is_synthetic: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BacktestDecision:
    """Decision Engine 또는 Baseline이 샘플에 대해 생성한 판단 결과 (Simulated / Estimated)."""
    sample_id: str
    strategy_name: str # e.g. "DecisionEngine_v1.1", "AlwaysSave", "HPThreshold", "RuleEngine"
    recommended_action: ActionType
    decision_margin: float
    confidence: float
    action_scores: Dict[str, float]
    score_breakdown: Dict[str, Dict[str, Any]]
    simulated_expectations: Dict[str, Dict[str, Any]] # e.g. {"ROLL": {"expected_gold": 16, "expected_power": 23.7}}
    reasons: List[str]
    actual_action: ActualActionType
    agreement: Optional[bool] = None # True if recommended_action == actual_action

@dataclass
class FailureCase:
    """의심스러운 판단 또는 전략적 실패가 발생한 재현 가능한 사례."""
    case_id: str
    match_id: str
    sample_id: str
    failure_type: str # e.g. "AGREEMENT_BUT_BOTTOM4", "HIGH_MARGIN_DISAGREEMENT", "PREDICTION_DIVERGENCE"
    description: str
    state_summary: Dict[str, Any]
    recommended_action: str
    actual_action: str
    actual_placement: Optional[int]
    decision_margin: float
    reproducible_state: Dict[str, Any]

@dataclass
class StratifiedMetricGroup:
    group_name: str
    sample_count: int
    avg_placement: Optional[float]
    top4_rate: Optional[float]
    agreement_rate: Optional[float]

@dataclass
class BacktestReport:
    """백테스트 실행 종합 평가 보고서 데이터 구조."""
    total_samples: int
    total_matches: int
    total_participants: int
    data_source_distribution: Dict[str, int]
    
    # Behavioral agreement metrics
    recommendation_agreement: Dict[str, float]
    action_confusion_matrix: Dict[str, Dict[str, int]]
    unknown_action_rate: float
    coverage: float
    
    # Baseline comparison metrics
    baseline_comparisons: Dict[str, Dict[str, float]]
    
    # Outcome metrics
    outcome_summary: Dict[str, Any]
    stratification_by_hp: List[StratifiedMetricGroup]
    stratification_by_gold: List[StratifiedMetricGroup]
    stratification_by_stage: List[StratifiedMetricGroup]
    stratification_by_level: List[StratifiedMetricGroup]
    
    # Margin analysis
    margin_tier_analysis: List[Dict[str, Any]]
    
    # Simulation errors
    simulation_errors: Dict[str, Any]
    
    # Failure cases
    failure_cases_count: int
    failure_cases_sample: List[FailureCase]
    
    # Limitations and notes
    data_limitations: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
