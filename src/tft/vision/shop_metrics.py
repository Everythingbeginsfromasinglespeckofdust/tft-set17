"""TFT Shop Recognition Comparison & Metrics Module -- OLD vs NEW Evaluator."""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from tft.vision.ground_truth import GroundTruthDataset, GroundTruthObservation, GroundTruthActionType
from tft.vision.timeline import ObservationTimeline
from tft.vision.events import VisionActionType
from tft.vision.metrics import BinaryClassificationMetrics, TimingMetrics


@dataclass
class ShopVersionMetrics:
    """단일 상점 인식기 버전의 종합 성능 평가 메트릭."""
    version_name: str
    total_slots: int = 0
    champion_correct_slots: int = 0
    cost_correct_slots: int = 0
    empty_correct_slots: int = 0
    unknown_slots: int = 0
    missing_slots: int = 0
    slot_accuracies: Dict[int, float] = field(default_factory=dict)
    roll_metrics: BinaryClassificationMetrics = field(default_factory=lambda: BinaryClassificationMetrics(action_name="ROLL"))
    buy_metrics: BinaryClassificationMetrics = field(default_factory=lambda: BinaryClassificationMetrics(action_name="BUY_UNIT"))
    timing_metrics: TimingMetrics = field(default_factory=TimingMetrics)

    @property
    def overall_champion_accuracy(self) -> float:
        return round(self.champion_correct_slots / max(1, self.total_slots), 4)

    @property
    def overall_cost_accuracy(self) -> float:
        return round(self.cost_correct_slots / max(1, self.total_slots), 4)

    @property
    def unknown_rate(self) -> float:
        return round(self.unknown_slots / max(1, self.total_slots), 4)

    @property
    def missing_rate(self) -> float:
        return round(self.missing_slots / max(1, self.total_slots), 4)


@dataclass
class ShopComparisonReport:
    """OLD vs NEW 상점 인식기 비교 리포트."""
    old_metrics: ShopVersionMetrics
    new_metrics: ShopVersionMetrics
    slot_deltas: Dict[int, float] = field(default_factory=dict)
    overall_accuracy_delta: float = 0.0
    cost_accuracy_delta: float = 0.0
    roll_f1_delta: float = 0.0
    buy_f1_delta: float = 0.0


def evaluate_shop_timeline_against_gt(
    timeline: ObservationTimeline,
    gt_dataset: GroundTruthDataset,
    version_name: str = "v2"
) -> ShopVersionMetrics:
    """특정 상점 타임라인을 Ground Truth에 대해 정량 평가."""
    m = ShopVersionMetrics(version_name=version_name)
    slot_totals = defaultdict(int)
    slot_corrects = defaultdict(int)

    # 1. Evaluate Shop Slots (200 ground truth slots)
    for gt_obs in gt_dataset.observations:
        cv_obs = timeline.get_latest_observation_at(gt_obs.timestamp_sec)
        if not cv_obs or abs(cv_obs.timestamp_sec - gt_obs.timestamp_sec) > 1.5:
            for gt_c in gt_obs.shop_cards:
                m.total_slots += 1
                m.missing_slots += 1
                slot_totals[gt_c.slot_index + 1] += 1
            continue

        for gt_c in gt_obs.shop_cards:
            s_idx = gt_c.slot_index
            slot_num = s_idx + 1
            m.total_slots += 1
            slot_totals[slot_num] += 1

            cv_c = next((c for c in cv_obs.shop_cards if c.slot_index == s_idx), None)
            if not cv_c:
                m.missing_slots += 1
                continue

            gt_name = gt_c.champion_name if not gt_c.is_empty else "EMPTY"
            cv_name = cv_c.champion_pred if not cv_c.is_empty else "EMPTY"

            if cv_name in ["UNKNOWN", None] and not cv_c.is_empty:
                m.unknown_slots += 1

            if gt_name == cv_name:
                m.champion_correct_slots += 1
                slot_corrects[slot_num] += 1

            gt_cost = gt_c.cost if not gt_c.is_empty else 0
            cv_cost = cv_c.cost_pred if not cv_c.is_empty else 0
            if gt_cost == cv_cost:
                m.cost_correct_slots += 1

            if gt_c.is_empty and cv_c.is_empty:
                m.empty_correct_slots += 1

    for s_num in range(1, 6):
        tot = slot_totals[s_num]
        cor = slot_corrects[s_num]
        m.slot_accuracies[s_num] = round(cor / max(1, tot), 4)

    # 2. Evaluate Action Events (ROLL and BUY_UNIT)
    timing_errors = []
    matched_cv_indices = set()

    for gt_ev in gt_dataset.events:
        gt_t = gt_ev.timestamp_sec
        gt_type = gt_ev.event_type.value

        best_idx = None
        min_dt = 999.0
        for cv_i, cv_ev in enumerate(timeline.events):
            if cv_i in matched_cv_indices: continue
            dt = abs(cv_ev.timestamp_sec - gt_t)
            if dt <= 1.0 and dt < min_dt:
                min_dt = dt
                best_idx = cv_i

        if best_idx is not None:
            matched_cv_indices.add(best_idx)
            cv_ev = timeline.events[best_idx]
            cv_type = cv_ev.action_type.value
            timing_errors.append(min_dt)

            if gt_type == "ROLL":
                if cv_type == "ROLL": m.roll_metrics.tp += 1
                else: m.roll_metrics.fn += 1
            elif gt_type == "BUY_UNIT":
                if cv_type == "BUY_UNIT": m.buy_metrics.tp += 1
                else: m.buy_metrics.fn += 1
        else:
            if gt_type == "ROLL": m.roll_metrics.fn += 1
            elif gt_type == "BUY_UNIT": m.buy_metrics.fn += 1

    for cv_i, cv_ev in enumerate(timeline.events):
        if cv_i not in matched_cv_indices:
            if cv_ev.action_type == VisionActionType.ROLL: m.roll_metrics.fp += 1
            elif cv_ev.action_type == VisionActionType.BUY_UNIT: m.buy_metrics.fp += 1

    m.timing_metrics = TimingMetrics(errors_sec=timing_errors)
    return m


def compare_shop_versions(
    old_timeline: ObservationTimeline,
    new_timeline: ObservationTimeline,
    gt_dataset: GroundTruthDataset
) -> ShopComparisonReport:
    """OLD vs NEW 상점 인식기 타임라인 비교 분석."""
    old_m = evaluate_shop_timeline_against_gt(old_timeline, gt_dataset, version_name="OLD (ShopRecognizer v1)")
    new_m = evaluate_shop_timeline_against_gt(new_timeline, gt_dataset, version_name="NEW (ShopRecognizer v2)")

    slot_deltas = {}
    for s in range(1, 6):
        old_acc = old_m.slot_accuracies.get(s, 0.0)
        new_acc = new_m.slot_accuracies.get(s, 0.0)
        slot_deltas[s] = round(new_acc - old_acc, 4)

    return ShopComparisonReport(
        old_metrics=old_m,
        new_metrics=new_m,
        slot_deltas=slot_deltas,
        overall_accuracy_delta=round(new_m.overall_champion_accuracy - old_m.overall_champion_accuracy, 4),
        cost_accuracy_delta=round(new_m.overall_cost_accuracy - old_m.overall_cost_accuracy, 4),
        roll_f1_delta=round(new_m.roll_metrics.f1 - old_m.roll_metrics.f1, 4),
        buy_f1_delta=round(new_m.buy_metrics.f1 - old_m.buy_metrics.f1, 4)
    )
