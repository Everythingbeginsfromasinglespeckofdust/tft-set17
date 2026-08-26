"""Backtesting Framework Data Models for TFT Decision Engine v1.1.

Core principle:
  T0  = decision_state  (ObservedState, GameState)
  T1+ = future_outcome  (FutureObservation)
  T0 and T1+ must NEVER be mixed.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from tft.domain.game_state import GameState
from tft.domain.actions import ActionType


class ActualActionType(str, Enum):
    ROLL = "ROLL"
    LEVEL_UP = "LEVEL_UP"
    SAVE_GOLD = "SAVE_GOLD"
    UNKNOWN = "UNKNOWN"


class SnapshotType(str, Enum):
    """Game timing classification of a snapshot.

    ENDGAME_SNAPSHOT:
        From Riot Match-V1 API. Final state at player elimination or game end.
        gold_left, level, last_round are endgame values.
        NOT to be used as primary Decision Engine strategy evaluation data.
        Use for: dataset integrity, final outcome linkage, descriptive stats.

    MIDGAME_DECISION_SNAPSHOT:
        Captured during active gameplay at a decision point (2-1, 3-2, 4-1 etc).
        At least 1 more round remains. actual_action may be observable.
        PRIMARY data for Decision Engine strategy evaluation.

    OTHER_HISTORICAL:
        Other historical data not fitting above categories.
    """
    ENDGAME_SNAPSHOT = "ENDGAME_SNAPSHOT"
    MIDGAME_DECISION_SNAPSHOT = "MIDGAME_DECISION_SNAPSHOT"
    OTHER_HISTORICAL = "OTHER_HISTORICAL"


class FailureType(str, Enum):
    """Failure Case diagnostic taxonomy (applied in priority order, mutually exclusive)."""
    DATA_INVALID = "DATA_INVALID"
    FEASIBILITY_ERROR = "FEASIBILITY_ERROR"
    SIMULATION_ERROR = "SIMULATION_ERROR"
    HIGH_MARGIN_BOTTOM4 = "HIGH_MARGIN_BOTTOM4"
    HIGH_MARGIN_TOP4_FAILURE = "HIGH_MARGIN_TOP4_FAILURE"
    HIGH_MARGIN_BAD_OUTCOME = "HIGH_MARGIN_BAD_OUTCOME"
    RECOMMENDATION_DISAGREEMENT = "RECOMMENDATION_DISAGREEMENT"


@dataclass
class ObservedState:
    """T0: Actual observed game state at decision time.

    IMPORTANT: This struct must NEVER contain T1+ information
    (final_placement, future_gold, future_hp, future_level, etc.).
    """
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
    """T1+: Observed future outcome AFTER the decision point.

    horizon_rounds: number of rounds from T0 to this observation.
        0 = ENDGAME (T0 == T1+, no future game state).
        None = unknown.
    outcome_timestamp_sec: absolute time of T1+ observation.
        Must satisfy: decision_timestamp_sec <= outcome_timestamp_sec.
    """
    final_placement: Optional[int] = None
    top4: Optional[bool] = None
    hp_after_n_rounds: Optional[int] = None
    gold_after_n_rounds: Optional[int] = None
    level_after_n_rounds: Optional[int] = None
    last_round: Optional[int] = None
    time_eliminated: Optional[float] = None
    elimination_stage_round: Optional[str] = None
    horizon_rounds: Optional[int] = None
    outcome_timestamp_sec: Optional[float] = None


@dataclass
class BacktestSample:
    """Single backtest dataset sample (one snapshot).

    snapshot_type determines usage:
      - ENDGAME: descriptive stats only, NOT strategy evaluation.
      - MIDGAME: primary evaluation population.
    """
    sample_id: str
    match_id: str
    participant_id: str
    data_source: str
    observed_state: ObservedState
    future_observation: FutureObservation
    snapshot_type: SnapshotType = SnapshotType.OTHER_HISTORICAL
    is_synthetic: bool = False
    decision_timestamp_sec: Optional[float] = None
    horizon_rounds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestDecision:
    """Decision by Engine or Baseline for a sample.

    action_score_gap:
        best_action_score - second_best_action_score.
        This is action SCORE SEPARATION, not a calibrated probability.
        Do NOT interpret as confidence or correctness probability.
    agreement:
        Whether recommended_action == actual_action.
        This is behavioral agreement ONLY, not a performance metric.
    """
    sample_id: str
    strategy_name: str
    recommended_action: ActionType
    action_score_gap: float
    decision_margin: float  # alias for backward compatibility
    confidence: float
    action_scores: Dict[str, float]
    score_breakdown: Dict[str, Dict[str, Any]]
    simulated_expectations: Dict[str, Dict[str, Any]]
    reasons: List[str]
    actual_action: ActualActionType
    agreement: Optional[bool] = None
    snapshot_type: SnapshotType = SnapshotType.OTHER_HISTORICAL


@dataclass
class FailureCase:
    """Reproducible diagnostic case for a suspicious decision or data issue.

    IMPORTANT: This is a DIAGNOSTIC LABEL, not proof that the decision was wrong.
    """
    case_id: str
    match_id: str
    sample_id: str
    failure_type: str
    failure_category: str
    description: str
    state_summary: Dict[str, Any]
    recommended_action: str
    actual_action: str
    actual_placement: Optional[int]
    action_score_gap: float
    decision_margin: float
    snapshot_type: str
    reproducible_state: Dict[str, Any]


@dataclass
class StratifiedMetricGroup:
    group_name: str
    sample_count: int
    snapshot_type_counts: Dict[str, int] = field(default_factory=dict)
    avg_placement: Optional[float] = None
    top4_rate: Optional[float] = None
    agreement_rate: Optional[float] = None
    known_action_count: int = 0
    mean_score_gap: Optional[float] = None
    placement_denominator: int = 0


@dataclass
class TemporalIntegrityResult:
    total_checked: int
    violations: int
    unknown_timestamps: int
    violation_sample_ids: List[str] = field(default_factory=list)


@dataclass
class LeakageValidationResult:
    total_checked: int
    leakage_detected: int
    leakage_types: Dict[str, int] = field(default_factory=dict)
    endgame_in_midgame_report: int = 0
    placement_in_state: int = 0


@dataclass
class ActionObservationCoverage:
    total_samples: int
    known_action_samples: int
    unknown_action_samples: int
    coverage_rate: float
    by_snapshot_type: Dict[str, Dict[str, int]] = field(default_factory=dict)
    by_action_type: Dict[str, int] = field(default_factory=dict)


@dataclass
class ScoreGapDiagnostics:
    """Action Score Gap (formerly Decision Margin) diagnostics.
    Correlation analysis computed ONLY for MIDGAME samples.
    """
    definition: str = (
        "action_score_gap = score(best_action) - score(second_best_action). "
        "This is action score SEPARATION, NOT a calibrated probability of correctness."
    )
    gap_tiers: List[Dict[str, Any]] = field(default_factory=list)
    endgame_mean_gap: Optional[float] = None
    midgame_mean_gap: Optional[float] = None
    gap_by_hp_tier: List[Dict[str, Any]] = field(default_factory=list)
    gap_by_gold_tier: List[Dict[str, Any]] = field(default_factory=list)
    gap_by_stage: List[Dict[str, Any]] = field(default_factory=list)
    gap_by_level: List[Dict[str, Any]] = field(default_factory=list)
    midgame_n: int = 0
    midgame_pearson_gap_placement: Optional[float] = None
    midgame_spearman_gap_placement: Optional[float] = None
    correlation_note: str = ""


@dataclass
class GoldPredictionAnalysis:
    note: str = ""
    horizon_zero_excluded: int = 0
    valid_pairs: int = 0
    by_action: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    overall_mae: Optional[float] = None
    overall_rmse: Optional[float] = None
    overall_bias: Optional[float] = None


@dataclass
class BacktestReport:
    """Backtest evaluation report -- v1.1 redesign (15 sections)."""
    # Section 1: Dataset Composition
    total_samples: int
    total_matches: int
    total_participants: int
    data_source_distribution: Dict[str, int]

    # Section 2: Snapshot Type Distribution
    snapshot_type_distribution: Dict[str, int] = field(default_factory=dict)
    endgame_count: int = 0
    midgame_count: int = 0

    # Section 3: Action Observation Coverage
    action_observation_coverage: Optional[ActionObservationCoverage] = None
    recommendation_agreement: Dict[str, float] = field(default_factory=dict)
    action_confusion_matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)
    unknown_action_rate: float = 0.0
    coverage: float = 0.0

    # Section 4: Temporal Integrity
    temporal_integrity: Optional[TemporalIntegrityResult] = None

    # Section 5: Leakage Validation
    leakage_validation: Optional[LeakageValidationResult] = None

    # Section 6: Midgame Descriptive Statistics
    midgame_statistics: Dict[str, Any] = field(default_factory=dict)
    midgame_stratification_by_hp: List[StratifiedMetricGroup] = field(default_factory=list)
    midgame_stratification_by_gold: List[StratifiedMetricGroup] = field(default_factory=list)
    midgame_stratification_by_stage: List[StratifiedMetricGroup] = field(default_factory=list)
    midgame_stratification_by_level: List[StratifiedMetricGroup] = field(default_factory=list)

    # Section 7: Endgame Descriptive Statistics
    endgame_statistics: Dict[str, Any] = field(default_factory=dict)
    endgame_stratification_by_hp: List[StratifiedMetricGroup] = field(default_factory=list)
    endgame_stratification_by_gold: List[StratifiedMetricGroup] = field(default_factory=list)

    # backward compat
    stratification_by_hp: List[StratifiedMetricGroup] = field(default_factory=list)
    stratification_by_gold: List[StratifiedMetricGroup] = field(default_factory=list)
    stratification_by_stage: List[StratifiedMetricGroup] = field(default_factory=list)
    stratification_by_level: List[StratifiedMetricGroup] = field(default_factory=list)

    # Section 8: Recommendation Agreement
    behavioral_agreement: Dict[str, float] = field(default_factory=dict)
    baseline_comparisons: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Section 9: Action Score Gap Diagnostics
    score_gap_diagnostics: Optional[ScoreGapDiagnostics] = None
    margin_tier_analysis: List[Dict[str, Any]] = field(default_factory=list)

    # Section 10: Simulation Accuracy
    gold_prediction_analysis: Optional[GoldPredictionAnalysis] = None
    simulation_errors: Dict[str, Any] = field(default_factory=dict)

    # Section 11: Failure Diagnostics
    failure_cases_count: int = 0
    failure_cases_by_type: Dict[str, int] = field(default_factory=dict)
    failure_cases_sample: List[FailureCase] = field(default_factory=list)

    # Section 12: Statistical Limitations
    data_limitations: List[str] = field(default_factory=list)

    # Section 13: What Can Be Concluded
    what_can_be_concluded: List[str] = field(default_factory=list)

    # Section 14: What Cannot Be Concluded
    what_cannot_be_concluded: List[str] = field(default_factory=list)

    # Section 15: Next Required Data
    next_required_data: List[str] = field(default_factory=list)

    # Outcome summary (backward compat)
    outcome_summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
