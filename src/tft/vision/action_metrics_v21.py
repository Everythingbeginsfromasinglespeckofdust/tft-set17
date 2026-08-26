"""TFT Action Metrics v2.1 -- Distinct System Refresh Evaluation & 6x6 Confusion Matrix."""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from tft.vision.events import ActionEvent, VisionActionType, ActionSource
from tft.vision.ground_truth import GroundTruthDataset, GroundTruthEvent, GroundTruthActionType
from tft.vision.metrics import BinaryClassificationMetrics, TimingMetrics


@dataclass
class ActionEvaluationSummaryV21:
    """Action Detection v2.1 종합 평가 결과."""
    version_name: str
    total_predicted_events: int
    total_ground_truth_events: int
    player_roll_metrics: BinaryClassificationMetrics
    buy_unit_metrics: BinaryClassificationMetrics
    level_up_metrics: BinaryClassificationMetrics
    system_refresh_count: int
    timing_metrics: TimingMetrics
    confusion_matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)
    false_positives_count: int = 0
    false_negatives_count: int = 0
    fp_reduction_vs_v2: int = 0
    fn_reduction_vs_v2: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_name": self.version_name,
            "total_predicted_events": self.total_predicted_events,
            "total_ground_truth_events": self.total_ground_truth_events,
            "player_roll": self.player_roll_metrics.to_dict(),
            "buy_unit": self.buy_unit_metrics.to_dict(),
            "level_up": self.level_up_metrics.to_dict(),
            "system_refresh_count": self.system_refresh_count,
            "timing_mae_sec": self.timing_metrics.mae,
            "timing_median_sec": self.timing_metrics.median,
            "timing_p95_sec": self.timing_metrics.p95,
            "timing_max_sec": self.timing_metrics.max_error,
            "confusion_matrix": self.confusion_matrix,
            "false_positives_count": self.false_positives_count,
            "false_negatives_count": self.false_negatives_count
        }


def evaluate_action_events_v21(
    predicted_events: List[ActionEvent],
    ground_truth: GroundTruthDataset,
    tolerance_sec: float = 1.0,
    version_name: str = "v2.1"
) -> Tuple[ActionEvaluationSummaryV21, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """ActionEvent 목록을 Ground Truth와 엄밀 매칭(시간 허용오차 ±1.0s)하여 6x6 오차행렬 및 메트릭 생성."""
    roll_m = BinaryClassificationMetrics(action_name="PLAYER_ROLL")
    buy_m = BinaryClassificationMetrics(action_name="BUY_UNIT")
    lvl_m = BinaryClassificationMetrics(action_name="LEVEL_UP")

    timing_errors: List[float] = []
    system_refresh_count = sum(
        1 for p in predicted_events
        if p.metadata.get("system_event_type") == "SYSTEM_SHOP_REFRESH"
    )

    # Confusion matrix classes: ROLL, BUY_UNIT, LEVEL_UP, NO_ACTION, SYSTEM_REFRESH, UNKNOWN
    classes = ["ROLL", "BUY_UNIT", "LEVEL_UP", "NO_ACTION", "SYSTEM_REFRESH", "UNKNOWN"]
    confusion = {gt_cls: {pred_cls: 0 for pred_cls in classes} for gt_cls in classes}

    # Filter player actions vs system events for action matching
    player_pred_events = [
        (idx, p) for idx, p in enumerate(predicted_events)
        if p.action_type in [VisionActionType.ROLL, VisionActionType.BUY_UNIT, VisionActionType.LEVEL_UP, VisionActionType.BUY_XP, VisionActionType.SELL_UNIT]
    ]

    matched_gt_indices = set()
    matched_pred_indices = set()

    fp_cases: List[Dict[str, Any]] = []
    fn_cases: List[Dict[str, Any]] = []

    # 1. Match Player Action Predictions to Ground Truth
    for orig_idx, pred in player_pred_events:
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

            # Record in confusion matrix
            pred_cls_key = p_type if p_type in classes else "UNKNOWN"
            gt_cls_key = gt_type if gt_type in classes else "UNKNOWN"
            confusion[gt_cls_key][pred_cls_key] += 1

            if p_type == gt_type:
                matched_gt_indices.add(best_gt_idx)
                matched_pred_indices.add(orig_idx)
                if p_type == "ROLL":
                    roll_m.tp += 1
                elif p_type == "BUY_UNIT":
                    buy_m.tp += 1
                elif p_type == "LEVEL_UP":
                    lvl_m.tp += 1
            else:
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

            pred_cls_key = p_type if p_type in classes else "UNKNOWN"
            confusion["NO_ACTION"][pred_cls_key] += 1

            fp_cases.append({
                "timestamp_sec": p_time,
                "predicted_action": p_type,
                "ground_truth_action": "NO_ACTION",
                "confidence": pred.confidence,
                "evidence": pred.evidence,
                "reason": "Spurious Detection (No GT action within tolerance)"
            })

    # 2. Identify Missed Ground Truth Events -> False Negatives
    for g_idx, gt in enumerate(ground_truth.events):
        if g_idx in matched_gt_indices:
            continue
        g_type = gt.event_type.value
        gt_cls_key = g_type if g_type in classes else "UNKNOWN"
        if gt_type == "NO_OBSERVED_ECONOMIC_ACTION":
            continue

        confusion[gt_cls_key]["NO_ACTION"] += 1

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

    summary = ActionEvaluationSummaryV21(
        version_name=version_name,
        total_predicted_events=len(player_pred_events),
        total_ground_truth_events=len(ground_truth.events),
        player_roll_metrics=roll_m,
        buy_unit_metrics=buy_m,
        level_up_metrics=lvl_m,
        system_refresh_count=system_refresh_count,
        timing_metrics=TimingMetrics(errors_sec=timing_errors),
        confusion_matrix=confusion,
        false_positives_count=len(fp_cases),
        false_negatives_count=len(fn_cases)
    )

    return summary, fp_cases, fn_cases
