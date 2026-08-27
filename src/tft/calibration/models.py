"""Data Models for TFT Decision Engine Offline Calibration Study v1.

Core Invariant:
  MetaTFT statistics are observational associations, NOT causal treatment effects.
  Calibration evaluates score transformation candidates in an isolated experimental layer.
  Production DecisionEngine is never altered.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TransformationType(str, Enum):
    B0_RAW_BASELINE = "B0_NO_CALIBRATION"
    B1_RAW_METRIC = "B1_RAW_METATFT_METRIC"
    B2_SAMPLE_WEIGHTED = "B2_SAMPLE_WEIGHTED_METRIC"
    B3_EMPIRICAL_SHRUNK = "B3_EMPIRICAL_BAYES_SHRUNK"
    SIGMOID_NORMALIZED = "SIGMOID_NORMALIZED"
    RANK_NORMALIZED = "RANK_NORMALIZED"


class CandidateStatus(str, Enum):
    PROMISING = "PROMISING"
    EXPERIMENTAL = "EXPERIMENTAL"
    UNSTABLE = "UNSTABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DO_NOT_USE = "DO_NOT_USE"


class BiasRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class CalibrationRecord:
    """Single calibrated entity record."""
    entity_id: str
    conditioning_context: Dict[str, Any]
    observed_metric: str
    sample_size: int
    raw_metric_value: float
    place_change: Optional[float] = None
    transformed_score: float = 0.0
    shrinkage_factor: float = 1.0
    is_filtered_out: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CalibrationCandidateResult:
    """Evaluation result of a calibration candidate."""
    candidate_id: str
    dataset_name: str
    transformation: str
    sample_threshold: int
    metric_name: str
    sample_size_evaluated: int
    mean_raw_value: float
    mean_transformed_value: float
    stability_score: float
    bias_risk: str
    status: str
    potential_use: str
    mitigation_strategy: str
    records: List[CalibrationRecord] = field(default_factory=list)


@dataclass
class RecommendationFlipCase:
    """Case where experimental calibration candidate would alter recommended action."""
    case_id: str
    state_summary: Dict[str, Any]
    original_action: str
    experimental_action: str
    original_action_scores: Dict[str, float]
    experimental_action_scores: Dict[str, float]
    metatft_evidence: str
    sample_size: int
    risk_level: str
    would_flip: bool
    description: str


@dataclass
class CalibrationStudyManifest:
    """Manifest of the calibration study execution."""
    experiment_id: str
    experiment_version: str
    retrieved_at: str
    stats_source_dir: str
    sample_thresholds_evaluated: List[int]
    candidates_count: int
    flip_cases_count: int
    final_gate_verdict: str
    production_unchanged_verified: bool
    git_commit_sha: Optional[str] = None
