"""TFT Action Metrics & Benchmark Module: Evaluates ActionEventDetector performance against Ground Truth."""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from tft.vision.events import ActionEvent, VisionActionType, ActionSource
from tft.vision.ground_truth import GroundTruthDataset, GroundTruthEvent, GroundTruthActionType
from tft.vision.metrics import BinaryClassificationMetrics, TimingMetrics


@dataclass
class ActionEvaluationSummary:
    """단일 실행의 행동 검출 종합 평가 지표."""
    version_name: str
    total_predicted_events: int
    total_ground_truth_events: int
    roll_metrics: BinaryClassificationMetrics
    buy_metrics: BinaryClassificationMetrics
    levelup_metrics: BinaryClassificationMetrics
    timing_metrics: TimingMetrics
    status_distribution: Dict[str, int] = field(default_factory=dict)
    false_positive_types: Dict[str, int] = field(default_factory=dict)
    false_negative_types: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_name": self.version_name,
            "total_predicted_events": self.total_predicted_events,
            "total_ground_truth_events": self.total_ground_truth_events,
            "roll": self.roll_metrics.to_dict(),
            "buy_unit": self.buy_metrics.to_dict(),
            "level_up": self.levelup_metrics.to_dict(),
            "timing_mae_sec": self.timing_metrics.mae,
            "timing_median_sec": self.timing_metrics.median,
            "timing_p95_sec": self.timing_metrics.p95,
            "timing_max_sec": self.timing_metrics.max_error,
            "status_distribution": self.status_distribution,
            "false_positive_types": self.false_positive_types,
            "false_negative_types": self.false_negative_types
        }


def evaluate_action_events(
    predicted_events: List[ActionEvent],
    ground_truth: GroundTruthDataset,
    tolerance_sec: float = 1.0,
    version_name: str = "v2"
) -> Tuple[ActionEvaluationSummary, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """예측된 ActionEvent 목록을 Ground Truth와 엄밀 매칭(시간 허용오차 ±1.0s)하여 평가."""
    roll_m = BinaryClassificationMetrics(action_name="ROLL")
    buy_m = BinaryClassificationMetrics(action_name="BUY_UNIT")
    lvl_m = BinaryClassificationMetrics(action_name="LEVEL_UP")

    timing_errors: List[float] = []
    status_counts = defaultdict(int)
    for p in predicted_events:
        status_counts[p.source.value] += 1

    # Map GT target events
    gt_roll = [e for e in ground_truth.events if e.event_type == GroundTruthActionType.ROLL]
    gt_buy = [e for e in ground_truth.events if e.event_type == GroundTruthActionType.BUY_UNIT]
    gt_lvl = [e for e in ground_truth.events if e.event_type == GroundTruthActionType.LEVEL_UP]

    matched_gt_indices = set()
    matched_pred_indices = set()

    fp_cases: List[Dict[str, Any]] = []
    fn_cases: List[Dict[str, Any]] = []

    # 1. Match Predictions to Ground Truth Events
    for p_idx, pred in enumerate(predicted_events):
        p_type = pred.action_type.value
        p_time = pred.timestamp_sec

        best_gt_idx = None
        min_dt = 999.0

        for g_idx, gt in enumerate(ground_truth.events):
            if g_idx in matched_gt_indices:
                continue
            g_type = gt.event_type.value
            if g_type == GroundTruthActionType.NO_OBSERVED_ECONOMIC_ACTION.value:
                continue

            dt = abs(gt.timestamp_sec - p_time)
            if dt <= tolerance_sec and dt < min_dt:
                min_dt = dt
                best_gt_idx = g_idx

        if best_gt_idx is not None:
            gt_ev = ground_truth.events[best_gt_idx]
            gt_type = gt_ev.event_type.value
            timing_errors.append(min_dt)

            if p_type == gt_type:
                matched_gt_indices.add(best_gt_idx)
                matched_pred_indices.add(p_idx)
                if p_type == "ROLL":
                    roll_m.tp += 1
                elif p_type == "BUY_UNIT":
                    buy_m.tp += 1
                elif p_type == "LEVEL_UP":
                    lvl_m.tp += 1
            else:
                # Type mismatch (Cross-Action False Positive)
                if p_type == "ROLL":
                    roll_m.fp += 1
                elif p_type == "BUY_UNIT":
                    buy_m.fp += 1
                elif p_type == "LEVEL_UP":
                    lvl_m.fp += 1

                fp_cases.append({
                    "timestamp_sec": p_time,
                    "predicted_action": p_type,
                    "ground_truth_action": gt_type,
                    "confidence": pred.confidence,
                    "evidence": pred.evidence,
                    "reason": f"Type Mismatch (predicted {p_type}, actual {gt_type})"
                })
        else:
            # Unmatched Prediction -> False Positive
            if p_type == "ROLL":
                roll_m.fp += 1
            elif p_type == "BUY_UNIT":
                buy_m.fp += 1
            elif p_type == "LEVEL_UP":
                lvl_m.fp += 1

            fp_cases.append({
                "timestamp_sec": p_time,
                "predicted_action": p_type,
                "ground_truth_action": "NO_ACTION",
                "confidence": pred.confidence,
                "evidence": pred.evidence,
                "reason": "Spurious Detection (No GT action within tolerance)"
            })

    # 2. Identify Unmatched Ground Truth Events -> False Negatives
    for g_idx, gt in enumerate(ground_truth.events):
        if g_idx in matched_gt_indices:
            continue
        g_type = gt.event_type.value
        if g_type == "ROLL":
            roll_m.fn += 1
            fn_cases.append({
                "timestamp_sec": gt.timestamp_sec,
                "ground_truth_action": "ROLL",
                "notes": gt.notes,
                "evidence_observed": gt.evidence_observed,
                "reason": "Missed ROLL Event"
            })
        elif g_type == "BUY_UNIT":
            buy_m.fn += 1
            fn_cases.append({
                "timestamp_sec": gt.timestamp_sec,
                "ground_truth_action": "BUY_UNIT",
                "target_champion": gt.target_champion,
                "notes": gt.notes,
                "evidence_observed": gt.evidence_observed,
                "reason": f"Missed BUY_UNIT Event ({gt.target_champion})"
            })
        elif g_type == "LEVEL_UP":
            lvl_m.fn += 1
            fn_cases.append({
                "timestamp_sec": gt.timestamp_sec,
                "ground_truth_action": "LEVEL_UP",
                "notes": gt.notes,
                "reason": "Missed LEVEL_UP Event"
            })

    fp_types = defaultdict(int)
    for c in fp_cases:
        fp_types[c["reason"]] += 1

    fn_types = defaultdict(int)
    for c in fn_cases:
        fn_types[c["reason"]] += 1

    summary = ActionEvaluationSummary(
        version_name=version_name,
        total_predicted_events=len(predicted_events),
        total_ground_truth_events=len(ground_truth.events),
        roll_metrics=roll_m,
        buy_metrics=buy_m,
        levelup_metrics=lvl_m,
        timing_metrics=TimingMetrics(errors_sec=timing_errors),
        status_distribution=dict(status_counts),
        false_positive_types=dict(fp_types),
        false_negative_types=dict(fn_types)
    )

    return summary, fp_cases, fn_cases
