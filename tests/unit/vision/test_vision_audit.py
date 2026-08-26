"""Comprehensive Test Suite for TFT Vision Ground Truth Audit Framework (v1.0)."""
import os
import sys
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.vision.observation import Observation, CardObservation
from tft.vision.events import ActionEvent, VisionActionType, ActionSource
from tft.vision.timeline import ObservationTimeline
from tft.vision.ground_truth import (
    GroundTruthDataset,
    GroundTruthEvent,
    GroundTruthActionType,
    GroundTruthObservation,
    GroundTruthCard
)
from tft.vision.metrics import (
    BinaryClassificationMetrics,
    TimingMetrics,
    FieldAccuracyMetrics,
    AnnotationAgreement,
    DatasetReadiness,
    evaluate_dataset_readiness
)
from tft.vision.audit import VisionAuditor


def test_ground_truth_dataset_loading_and_validation():
    """Verify GroundTruthDataset validates duration and timestamp ranges."""
    ds = GroundTruthDataset(
        session_id="S_01",
        video_path="mock.mp4",
        duration_sec=300.0,
        events=[
            GroundTruthEvent(session_id="S_01", timestamp_sec=10.0, event_type=GroundTruthActionType.ROLL),
            GroundTruthEvent(session_id="S_01", timestamp_sec=25.0, event_type=GroundTruthActionType.BUY_UNIT)
        ]
    )
    ok, issues = ds.validate_integrity()
    assert ok is True
    assert len(issues) == 0

    # Test out of bounds rejection
    invalid_ds = GroundTruthDataset(
        session_id="S_02",
        video_path="mock.mp4",
        duration_sec=100.0,
        events=[
            GroundTruthEvent(session_id="S_02", timestamp_sec=150.0, event_type=GroundTruthActionType.ROLL)  # > 100.0s
        ]
    )
    ok, issues = invalid_ds.validate_integrity()
    assert ok is False
    assert len(issues) > 0


def test_action_metrics_precision_recall_f1():
    """Verify precision, recall, F1, FPR, FNR formulas."""
    m = BinaryClassificationMetrics(action_name="ROLL", tp=18, fp=2, fn=2, tn=78)
    assert m.precision == 0.90  # 18 / 20
    assert m.recall == 0.90     # 18 / 20
    assert m.f1 == 0.90
    assert m.false_positive_rate == round(2 / 80, 4)
    assert m.false_negative_rate == 0.10


def test_timing_metrics_calculation():
    """Verify timing error MAE, median, P95, and max calculations."""
    errors = [0.1, 0.2, 0.2, 0.3, 0.5, 0.8, 1.0]
    tm = TimingMetrics(errors_sec=errors)

    assert tm.sample_count == 7
    assert tm.mae == round(sum(errors) / 7.0, 3)
    assert tm.median == 0.3
    assert tm.max_error == 1.0


def test_field_accuracy_metrics():
    """Verify exact match accuracy and MAE for numerical fields."""
    fm = FieldAccuracyMetrics(
        field_name="gold",
        total_evaluated=10,
        exact_matches=8,
        numerical_errors=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0, -2.0]
    )
    assert fm.exact_accuracy == 0.80
    assert fm.mae == 0.40
    assert fm.max_error == 2.0


def test_inferred_save_gold_evaluation():
    """Verify evaluation of Inferred SAVE_GOLD against NO_OBSERVED_ECONOMIC_ACTION."""
    auditor = VisionAuditor(time_tolerance_sec=1.0)
    timeline = ObservationTimeline(duration_sec=300.0)
    gt_dataset = GroundTruthDataset(session_id="S_01", video_path="mock.mp4", duration_sec=300.0)

    # GT has 2 no-action windows
    gt_dataset.events.append(GroundTruthEvent(session_id="S_01", timestamp_sec=50.0, event_type=GroundTruthActionType.NO_OBSERVED_ECONOMIC_ACTION))
    gt_dataset.events.append(GroundTruthEvent(session_id="S_01", timestamp_sec=100.0, event_type=GroundTruthActionType.NO_OBSERVED_ECONOMIC_ACTION))

    # CV inferred SAVE_GOLD at 52.0s
    timeline.add_event(ActionEvent(action_type=VisionActionType.SAVE_GOLD, source=ActionSource.INFERRED, timestamp_sec=52.0))

    result = auditor.audit(timeline, gt_dataset)
    sg = result.save_gold_inference_metrics

    assert sg.tp == 1  # 50.0 matched with 52.0
    assert sg.fn == 1  # 100.0 missed
    assert sg.fp == 0


def test_cohens_kappa_calculation():
    """Verify Cohen's Kappa metric computation for double annotations."""
    # 100% agreement
    matrix_perfect = {
        "ROLL": {"ROLL": 20, "BUY": 0},
        "BUY": {"ROLL": 0, "BUY": 10}
    }
    agree_perfect = AnnotationAgreement(total_compared=30, agreement_count=30, matrix=matrix_perfect)
    assert agree_perfect.cohens_kappa == 1.0

    # Discordant agreement
    matrix_discordant = {
        "ROLL": {"ROLL": 15, "BUY": 5},
        "BUY": {"ROLL": 5, "BUY": 15}
    }
    agree_disc = AnnotationAgreement(total_compared=40, agreement_count=30, matrix=matrix_discordant)
    assert 0.40 <= agree_disc.cohens_kappa <= 0.60


def test_dataset_readiness_rules():
    """Verify GREEN, YELLOW, and RED readiness gate decisions."""
    # High fidelity -> GREEN
    green_roll = BinaryClassificationMetrics(action_name="ROLL", tp=92, fp=8, fn=5, tn=100)
    green_timing = TimingMetrics(errors_sec=[0.2, 0.3, 0.4])
    green_gold = FieldAccuracyMetrics(field_name="gold", total_evaluated=10, exact_matches=10, numerical_errors=[0.0]*10)
    green_shop = FieldAccuracyMetrics(field_name="shop", total_evaluated=100, exact_matches=98)

    verdict_g, _, _ = evaluate_dataset_readiness(green_roll, green_timing, green_gold, green_shop)
    assert verdict_g == DatasetReadiness.GREEN

    # Low recall -> RED
    red_roll = BinaryClassificationMetrics(action_name="ROLL", tp=50, fp=10, fn=50, tn=100)  # Recall 50%
    verdict_r, _, _ = evaluate_dataset_readiness(red_roll, green_timing, green_gold, green_shop)
    assert verdict_r == DatasetReadiness.RED


def test_session_independence_metadata():
    """Verify single session audit explicitly states non-independence of samples."""
    auditor = VisionAuditor()
    timeline = ObservationTimeline(duration_sec=100.0)
    gt_dataset = GroundTruthDataset(session_id="S_01", video_path="mock.mp4", duration_sec=100.0)

    result = auditor.audit(timeline, gt_dataset)
    assert result.metadata["session_count"] == 1
    assert result.metadata["participant_count"] == 1
    assert "single" in result.metadata["sample_independence_note"].lower()


def test_vision_auditor_end_to_end():
    """Verify full end-to-end execution of VisionAuditor."""
    timeline = ObservationTimeline(duration_sec=200.0)
    timeline.add_observation(Observation(timestamp_sec=10.0, gold_val=35, hp_val=60, stage_text="3-2"))
    timeline.add_event(ActionEvent(action_type=VisionActionType.ROLL, source=ActionSource.OBSERVED, timestamp_sec=10.0))

    gt = GroundTruthDataset(session_id="S_TEST", video_path="mock.mp4", duration_sec=200.0)
    gt.events.append(GroundTruthEvent(session_id="S_TEST", timestamp_sec=10.2, event_type=GroundTruthActionType.ROLL))
    gt.observations.append(GroundTruthObservation(timestamp_sec=10.0, gold=35, hp=60, stage_round="3-2"))

    auditor = VisionAuditor(time_tolerance_sec=1.0)
    result = auditor.audit(timeline, gt)

    assert result.action_metrics["ROLL"].tp == 1
    assert result.timing_metrics.sample_count == 1
    assert abs(result.timing_metrics.mae - 0.2) < 1e-3
    assert result.gold_metrics.exact_matches == 1
    assert result.stage_metrics.exact_matches == 1
