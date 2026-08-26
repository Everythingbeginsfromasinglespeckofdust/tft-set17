"""Unit Tests for TFT Gold Recognizer, Timeline, and Metrics."""
import os
import sys
import numpy as np
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.vision.gold_recognizer import GoldRecognizer, GoldObservation, GoldErrorType
from tft.vision.gold_timeline import GoldTimelineProcessor, GoldDeltaEvent, GoldDeltaType
from tft.vision.gold_metrics import GoldMetricsEvaluator, GoldAccuracyReport
from tft.vision.ground_truth import GroundTruthDataset, GroundTruthEvent, GroundTruthActionType


def test_gold_roi():
    """Verify GoldRecognizer default ROI configuration."""
    recognizer = GoldRecognizer()
    assert recognizer.roi["y1"] == 680
    assert recognizer.roi["y2"] == 720
    assert recognizer.roi["x1"] == 450
    assert recognizer.roi["x2"] == 520


def test_gold_numeric_parsing():
    """Verify numeric domain validation [0, 250]."""
    recognizer = GoldRecognizer(max_valid_gold=250)
    assert recognizer.parse_numeric("35") == 35
    assert recognizer.parse_numeric("Gold: 0") == 0
    assert recognizer.parse_numeric("120G") == 120
    assert recognizer.parse_numeric("999") is None  # Out of range
    assert recognizer.parse_numeric("abc") is None


def test_gold_unknown():
    """Verify invalid/empty crop produces is_valid=False observation."""
    recognizer = GoldRecognizer()
    empty_crop = np.zeros((0, 0, 3), dtype=np.uint8)
    obs = recognizer.recognize_gold(empty_crop, timestamp_sec=10.0)
    assert obs.is_valid is False
    assert obs.parsed_gold is None
    assert obs.error_type == GoldErrorType.HUD_OCCLUSION


def test_gold_online_stabilization():
    """Verify forward-only stabilization carries forward last valid gold without looking ahead."""
    processor = GoldTimelineProcessor()
    raw = [
        GoldObservation(timestamp_sec=1.0, parsed_gold=38, is_valid=True),
        GoldObservation(timestamp_sec=1.5, parsed_gold=38, is_valid=True),
        GoldObservation(timestamp_sec=2.0, parsed_gold=None, is_valid=False),  # Missing
        GoldObservation(timestamp_sec=2.5, parsed_gold=36, is_valid=True),
    ]
    stabilized = processor.stabilize_online(raw)
    assert len(stabilized) == 4
    assert stabilized[2].parsed_gold == 38  # Carried forward
    assert stabilized[3].parsed_gold == 36


def test_gold_delta():
    """Verify GoldDeltaEvent extraction for -2 (ROLL) and -3 (BUY)."""
    processor = GoldTimelineProcessor()
    timeline = [
        GoldObservation(timestamp_sec=10.0, parsed_gold=38, is_valid=True),
        GoldObservation(timestamp_sec=10.5, parsed_gold=36, is_valid=True),  # -2 ROLL
        GoldObservation(timestamp_sec=11.0, parsed_gold=33, is_valid=True),  # -3 BUY
        GoldObservation(timestamp_sec=11.5, parsed_gold=33, is_valid=True),  # 0 UNCHANGED
    ]
    deltas = processor.extract_delta_events(timeline)
    assert len(deltas) == 2
    assert deltas[0].delta == -2
    assert deltas[0].is_roll_delta is True
    assert deltas[1].delta == -3
    assert deltas[1].is_buy_delta is True


def test_gold_delta_timing():
    """Verify delta event timestamps match the transition endpoint."""
    processor = GoldTimelineProcessor()
    timeline = [
        GoldObservation(timestamp_sec=10.0, parsed_gold=30, is_valid=True),
        GoldObservation(timestamp_sec=10.5, parsed_gold=28, is_valid=True),
    ]
    deltas = processor.extract_delta_events(timeline)
    assert len(deltas) == 1
    assert deltas[0].timestamp_sec == 10.5


def test_gold_missing_rate():
    """Verify missing rate calculation in GoldMetricsEvaluator."""
    evaluator = GoldMetricsEvaluator()
    raw = [
        GoldObservation(timestamp_sec=1.0, parsed_gold=30, is_valid=True),
        GoldObservation(timestamp_sec=2.0, parsed_gold=None, is_valid=False),
        GoldObservation(timestamp_sec=3.0, parsed_gold=30, is_valid=True),
        GoldObservation(timestamp_sec=4.0, parsed_gold=None, is_valid=False),
    ]
    gt = GroundTruthDataset("test", "test.mp4", 10.0, ["a1"], [])
    report = evaluator.evaluate(raw, raw, [], gt)
    assert report.total_frames == 4
    assert report.valid_ocr_frames == 2
    assert report.missing_rate == 0.5


def test_gold_checkpoint_evaluation():
    """Verify exact accuracy calculation on stable timeline."""
    evaluator = GoldMetricsEvaluator()
    raw = [GoldObservation(timestamp_sec=float(i), parsed_gold=30, is_valid=True) for i in range(10)]
    gt = GroundTruthDataset("test", "test.mp4", 10.0, ["a1"], [])
    report = evaluator.evaluate(raw, raw, [], gt)
    assert report.exact_accuracy == 1.0
    assert report.missing_rate == 0.0


def test_gold_random_checkpoint():
    """Verify random checkpoint report structure."""
    evaluator = GoldMetricsEvaluator()
    report = GoldAccuracyReport()
    report.random_checkpoints_count = 50
    report.random_checkpoints_accuracy = 0.98
    d = report.to_dict()
    assert d["random_checkpoints"]["count"] == 50
    assert d["random_checkpoints"]["accuracy"] == 0.98


def test_gold_error_gallery():
    """Verify error gallery contains invalid frame entries."""
    evaluator = GoldMetricsEvaluator()
    raw = [
        GoldObservation(timestamp_sec=1.0, parsed_gold=None, is_valid=False, error_type=GoldErrorType.OCR_MISSING),
        GoldObservation(timestamp_sec=2.0, parsed_gold=30, is_valid=True),
    ]
    gt = GroundTruthDataset("test", "test.mp4", 10.0, ["a1"], [])
    report = evaluator.evaluate(raw, raw, [], gt)
    assert len(report.error_gallery) == 1
    assert report.error_gallery[0]["error_type"] == "OCR_MISSING"


def test_full_gold_action_integration():
    """Verify 3-way comparison dictionary has rule_replay and full_gold_production keys."""
    evaluator = GoldMetricsEvaluator()
    raw = [GoldObservation(timestamp_sec=1.0, parsed_gold=30, is_valid=True)]
    gt = GroundTruthDataset("test", "test.mp4", 10.0, ["a1"], [])
    report = evaluator.evaluate(raw, raw, [], gt)
    assert "ROLL" in report.three_way_comparison
    assert "BUY_UNIT" in report.three_way_comparison
    assert "full_gold_production" in report.three_way_comparison["ROLL"]
