"""Statistical Metrics, Error Taxonomy, and Dataset Readiness Gate for TFT Vision Audit."""
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ErrorCategory(str, Enum):
    """비전 감사 오류 분류 체계 (Error Taxonomy)."""
    FALSE_POSITIVE = "FALSE_POSITIVE"                   # CV가 감지했으나 실제 화면에는 없음
    FALSE_NEGATIVE = "FALSE_NEGATIVE"                   # 실제 발생했으나 CV가 놓침
    WRONG_ACTION = "WRONG_ACTION"                       # 다른 행동으로 오분류 (e.g. BUY를 ROLL로)
    TIMING_ERROR = "TIMING_ERROR"                       # 발생 시각 오차가 허용치(>1.0s)를 초과
    OCR_ERROR = "OCR_ERROR"                             # 골드/체력/스테이지 OCR 수치 오류
    SHOP_RECOGNITION_ERROR = "SHOP_RECOGNITION_ERROR"   # 상점 챔피언명 또는 코스트 오인식
    MISSING_OBSERVATION = "MISSING_OBSERVATION"         # 해당 시점의 관측값이 누락됨
    IDENTITY_ERROR = "IDENTITY_ERROR"                   # 경기/플레이어 매칭 오류


class DatasetReadiness(str, Enum):
    """다중 영상 데이터셋 확장 게이트 판정 (Readiness Gate)."""
    GREEN = "GREEN"    # 신뢰도 충족 -> 다중 영상 대규모 확장 가능
    YELLOW = "YELLOW"  # 제한적 신뢰도 -> 한계점 명시 하에 조건부 사용 (특정 모듈 개선 권고)
    RED = "RED"        # 신뢰도 미달 -> 다중 영상 확장 불가 (CV 파이프라인 전면 재점검 필요)


@dataclass
class BinaryClassificationMetrics:
    """단일 행동에 대한 정량적 분류 메트릭."""
    action_name: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return round(self.tp / denom, 4) if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return round(self.tp / denom, 4) if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        denom = p + r
        return round(2 * p * r / denom, 4) if denom > 0 else 0.0

    @property
    def false_positive_rate(self) -> float:
        denom = self.fp + self.tn
        return round(self.fp / denom, 4) if denom > 0 else 0.0

    @property
    def false_negative_rate(self) -> float:
        denom = self.fn + self.tp
        return round(self.fn / denom, 4) if denom > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action_name,
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "tn": self.tn,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "fpr": self.false_positive_rate,
            "fnr": self.false_negative_rate,
            "total_ground_truth": self.tp + self.fn,
            "total_detected": self.tp + self.fp
        }


@dataclass
class TimingMetrics:
    """이벤트 발생 시점 인식 오차 메트릭 (초 단위)."""
    errors_sec: List[float] = field(default_factory=list)

    @property
    def sample_count(self) -> int:
        return len(self.errors_sec)

    @property
    def mae(self) -> Optional[float]:
        return round(sum(self.errors_sec) / len(self.errors_sec), 3) if self.errors_sec else None

    @property
    def median(self) -> Optional[float]:
        if not self.errors_sec:
            return None
        sorted_e = sorted(self.errors_sec)
        n = len(sorted_e)
        return round(sorted_e[n // 2] if n % 2 == 1 else (sorted_e[n // 2 - 1] + sorted_e[n // 2]) / 2.0, 3)

    @property
    def p95(self) -> Optional[float]:
        if not self.errors_sec:
            return None
        sorted_e = sorted(self.errors_sec)
        idx = int(math.ceil(0.95 * len(sorted_e))) - 1
        return round(sorted_e[max(0, min(idx, len(sorted_e) - 1))], 3)

    @property
    def max_error(self) -> Optional[float]:
        return round(max(self.errors_sec), 3) if self.errors_sec else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "mae_sec": self.mae,
            "median_sec": self.median,
            "p95_sec": self.p95,
            "max_error_sec": self.max_error
        }


@dataclass
class FieldAccuracyMetrics:
    """개별 관측 필드(Gold, HP, Stage, Shop)에 대한 정확도 메트릭."""
    field_name: str
    total_evaluated: int = 0
    exact_matches: int = 0
    numerical_errors: List[float] = field(default_factory=list)
    missing_count: int = 0

    @property
    def exact_accuracy(self) -> float:
        return round(self.exact_matches / max(1, self.total_evaluated), 4)

    @property
    def missing_rate(self) -> float:
        return round(self.missing_count / max(1, self.total_evaluated), 4)

    @property
    def mae(self) -> Optional[float]:
        return round(sum(abs(e) for e in self.numerical_errors) / len(self.numerical_errors), 2) if self.numerical_errors else None

    @property
    def max_error(self) -> Optional[float]:
        return round(max(abs(e) for e in self.numerical_errors), 2) if self.numerical_errors else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field_name,
            "total_evaluated": self.total_evaluated,
            "exact_matches": self.exact_matches,
            "exact_accuracy": self.exact_accuracy,
            "missing_count": self.missing_count,
            "missing_rate": self.missing_rate,
            "mae": self.mae,
            "max_error": self.max_error
        }


@dataclass
class AnnotationAgreement:
    """두 인간 검증자 간의 라벨 일치율 및 Cohen's Kappa."""
    total_compared: int = 0
    agreement_count: int = 0
    matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)

    @property
    def raw_agreement_rate(self) -> float:
        return round(self.agreement_count / max(1, self.total_compared), 4)

    @property
    def cohens_kappa(self) -> float:
        if self.total_compared == 0 or not self.matrix:
            return 1.0

        p0 = self.agreement_count / self.total_compared
        categories = sorted(list(self.matrix.keys()))
        row_totals = {c: sum(self.matrix[c].values()) for c in categories}
        col_totals = {c: sum(self.matrix[r][c] for r in categories) for c in categories}

        pe = sum((row_totals[c] / self.total_compared) * (col_totals[c] / self.total_compared) for c in categories)
        if pe == 1.0:
            return 1.0
        return round((p0 - pe) / (1.0 - pe), 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_compared": self.total_compared,
            "agreement_count": self.agreement_count,
            "raw_agreement_rate": self.raw_agreement_rate,
            "cohens_kappa": self.cohens_kappa
        }


def evaluate_dataset_readiness(
    roll_metrics: BinaryClassificationMetrics,
    timing_metrics: TimingMetrics,
    gold_metrics: FieldAccuracyMetrics,
    shop_metrics: FieldAccuracyMetrics
) -> Tuple[DatasetReadiness, List[str], List[str]]:
    """정량적 메트릭 임계값 기반 DATASET_READINESS 판정."""
    green_criteria_met = []
    issues_found = []

    # 1. ROLL Detection Gate
    if roll_metrics.recall >= 0.85 and roll_metrics.precision >= 0.90:
        green_criteria_met.append(f"ROLL detection meets high fidelity (Precision={roll_metrics.precision:.1%}, Recall={roll_metrics.recall:.1%})")
    elif roll_metrics.recall >= 0.70 and roll_metrics.precision >= 0.75:
        issues_found.append(f"ROLL detection acceptable with limitations (Precision={roll_metrics.precision:.1%}, Recall={roll_metrics.recall:.1%})")
    else:
        issues_found.append(f"ROLL detection fidelity LOW (Precision={roll_metrics.precision:.1%}, Recall={roll_metrics.recall:.1%})")

    # 2. Timing Error Gate
    t_mae = timing_metrics.mae or 0.0
    if t_mae <= 0.5:
        green_criteria_met.append(f"Timing error excellent (MAE={t_mae:.2f}s <= 0.5s)")
    elif t_mae <= 1.0:
        issues_found.append(f"Timing error moderate (MAE={t_mae:.2f}s <= 1.0s)")
    else:
        issues_found.append(f"Timing error HIGH (MAE={t_mae:.2f}s > 1.0s)")

    # 3. Shop Accuracy Gate
    if shop_metrics.exact_accuracy >= 0.95:
        green_criteria_met.append(f"Shop recognition highly accurate ({shop_metrics.exact_accuracy:.1%})")
    elif shop_metrics.exact_accuracy >= 0.85:
        issues_found.append(f"Shop recognition acceptable ({shop_metrics.exact_accuracy:.1%})")
    else:
        issues_found.append(f"Shop recognition accuracy LOW ({shop_metrics.exact_accuracy:.1%})")

    # 4. Gold OCR Gate
    g_mae = gold_metrics.mae or 0.0
    if g_mae <= 1.5:
        green_criteria_met.append(f"Gold OCR error low (MAE={g_mae:.1f}G <= 1.5G)")
    elif g_mae <= 4.0:
        issues_found.append(f"Gold OCR error moderate (MAE={g_mae:.1f}G)")
    else:
        issues_found.append(f"Gold OCR error HIGH (MAE={g_mae:.1f}G > 4.0G)")

    # Final Verdict Logic
    if roll_metrics.recall < 0.70 or roll_metrics.precision < 0.70 or t_mae > 1.2 or g_mae > 5.0:
        readiness = DatasetReadiness.RED
    elif len(issues_found) == 0:
        readiness = DatasetReadiness.GREEN
    else:
        readiness = DatasetReadiness.YELLOW

    return readiness, green_criteria_met, issues_found
