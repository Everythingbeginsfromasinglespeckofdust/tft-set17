"""TFT Action Rule Validation Metrics: Statistical Evaluation, Likelihood Ratios, and Conflict Detection."""
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Tuple


class FailureCategory(str, Enum):
    """실패 모드 분류."""
    # False Positives
    FP_SYSTEM_REFRESH = "SYSTEM_REFRESH"
    FP_NO_ACTION = "NO_ACTION"
    FP_BUY_CONFUSION = "BUY_CONFUSION"
    FP_SHOP_ANIMATION = "SHOP_ANIMATION"
    FP_ROUND_TRANSITION = "ROUND_TRANSITION"
    FP_UNKNOWN = "UNKNOWN"

    # False Negatives
    FN_SAME_CHAMPION_COLLISION = "SAME_CHAMPION_COLLISION"
    FN_MISSING_GOLD = "MISSING_GOLD"
    FN_MISSING_SHOP = "MISSING_SHOP"
    FN_MULTI_ACTION = "MULTI_ACTION"
    FN_TIMING_ALIGNMENT = "TIMING_ALIGNMENT"
    FN_BOARD_BENCH_MISSING = "BOARD_BENCH_MISSING"
    FN_UNKNOWN = "UNKNOWN"


@dataclass
class TimingBreakdown:
    """명시적으로 분리된 시간 측정 메트릭."""
    gt_action_time: float
    gold_onset_time: Optional[float] = None
    shop_onset_time: Optional[float] = None
    shop_stable_time: Optional[float] = None
    board_onset_time: Optional[float] = None
    bench_onset_time: Optional[float] = None
    round_transition_time: Optional[float] = None

    def latency_gold(self) -> Optional[float]:
        return (self.gold_onset_time - self.gt_action_time) if self.gold_onset_time is not None else None

    def latency_shop(self) -> Optional[float]:
        return (self.shop_onset_time - self.gt_action_time) if self.shop_onset_time is not None else None

    def latency_shop_stable(self) -> Optional[float]:
        return (self.shop_stable_time - self.gt_action_time) if self.shop_stable_time is not None else None

    def latency_bench(self) -> Optional[float]:
        return (self.bench_onset_time - self.gt_action_time) if self.bench_onset_time is not None else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gt_action_time": round(self.gt_action_time, 3),
            "gold_onset_time": round(self.gold_onset_time, 3) if self.gold_onset_time is not None else None,
            "shop_onset_time": round(self.shop_onset_time, 3) if self.shop_onset_time is not None else None,
            "shop_stable_time": round(self.shop_stable_time, 3) if self.shop_stable_time is not None else None,
            "board_onset_time": round(self.board_onset_time, 3) if self.board_onset_time is not None else None,
            "bench_onset_time": round(self.bench_onset_time, 3) if self.bench_onset_time is not None else None,
            "round_transition_time": round(self.round_transition_time, 3) if self.round_transition_time is not None else None,
            "latency_gold_sec": round(self.latency_gold(), 3) if self.latency_gold() is not None else None,
            "latency_shop_sec": round(self.latency_shop(), 3) if self.latency_shop() is not None else None,
            "latency_bench_sec": round(self.latency_bench(), 3) if self.latency_bench() is not None else None
        }


@dataclass
class RuleConflict:
    """단일 전이에서 복수의 규칙이 동시 발화(Trigger)된 충돌 사례."""
    timestamp_sec: float
    ground_truth_action: str
    triggered_rules: List[str]
    is_resolved: bool = False
    resolution_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_sec": round(self.timestamp_sec, 3),
            "ground_truth_action": self.ground_truth_action,
            "triggered_rules": self.triggered_rules,
            "is_resolved": self.is_resolved,
            "resolution_notes": self.resolution_notes
        }


@dataclass
class RuleEvaluationMetrics:
    """단일 Rule Candidate에 대한 완전한 통계적 평가 결과."""
    rule_name: str
    target_action_type: str
    description: str

    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    total_target_events: int = 0
    total_non_target_events: int = 0

    # Probabilities
    p_rule_given_target: float = 0.0      # P(rule | target) == Recall == TP / total_target
    p_rule_given_non_target: float = 0.0  # P(rule | non_target) == FPR == FP / total_non_target

    likelihood_ratio: Optional[float] = None
    laplace_smoothed_lr: float = 1.0
    laplace_alpha: float = 1.0

    failure_modes_fp: Dict[str, int] = field(default_factory=dict)
    failure_modes_fn: Dict[str, int] = field(default_factory=dict)

    def calculate_metrics(self, laplace_alpha: float = 1.0) -> None:
        """Precision, Recall, F1, Likelihood Ratio 계산."""
        self.laplace_alpha = laplace_alpha
        self.p_rule_given_target = (self.tp / max(1, self.total_target_events)) if self.total_target_events > 0 else 0.0
        self.p_rule_given_non_target = (self.fp / max(1, self.total_non_target_events)) if self.total_non_target_events > 0 else 0.0

        # Exact Likelihood Ratio
        if self.p_rule_given_non_target == 0.0:
            if self.p_rule_given_target > 0.0:
                self.likelihood_ratio = float("inf")
            else:
                self.likelihood_ratio = None
        else:
            self.likelihood_ratio = self.p_rule_given_target / self.p_rule_given_non_target

        # Laplace-smoothed Likelihood Ratio
        # P_smoothed(rule | target) = (TP + alpha) / (total_target + 2*alpha)
        # P_smoothed(rule | non_target) = (FP + alpha) / (total_non_target + 2*alpha)
        p_smooth_tgt = (self.tp + laplace_alpha) / (self.total_target_events + 2 * laplace_alpha)
        p_smooth_non = (self.fp + laplace_alpha) / (self.total_non_target_events + 2 * laplace_alpha)
        self.laplace_smoothed_lr = p_smooth_tgt / p_smooth_non

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return (self.tp / denom) if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return (self.tp / denom) if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p = self.precision
        r = self.recall
        return (2 * p * r / (p + r)) if (p + r) > 0 else 0.0

    @property
    def coverage(self) -> float:
        """전체 대상 이벤트 중 규칙이 발화된 비율."""
        return self.recall

    @property
    def specificity(self) -> float:
        """비대상 이벤트 중 규칙이 발화하지 않은 비율 (1 - FPR)."""
        return 1.0 - self.p_rule_given_non_target

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "target_action_type": self.target_action_type,
            "description": self.description,
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "tn": self.tn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "coverage": round(self.coverage, 4),
            "specificity": round(self.specificity, 4),
            "p_rule_given_target": round(self.p_rule_given_target, 4),
            "p_rule_given_non_target": round(self.p_rule_given_non_target, 4),
            "likelihood_ratio": "Infinity" if self.likelihood_ratio == float("inf") else (round(self.likelihood_ratio, 2) if self.likelihood_ratio is not None else "Undefined"),
            "laplace_smoothed_lr": round(self.laplace_smoothed_lr, 2),
            "laplace_alpha": self.laplace_alpha,
            "failure_modes_fp": self.failure_modes_fp,
            "failure_modes_fn": self.failure_modes_fn
        }
