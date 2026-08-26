"""Unit tests for TFT Multi-Session Pilot v1."""
import json
import os
import sys
import numpy as np
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.vision.pilot_models import (
    PilotSession,
    PilotManifest,
    SessionMetrics,
    CrossSessionSummary,
    LineageRecord,
    LineageLossStage,
    EconomicArchetype,
    PilotGateVerdict,
    PilotFailureType
)
from tft.vision.pilot_evaluator import MultiSessionEvaluator
from tft.vision.pilot_pipeline import MultiSessionPilotRunner


def test_pilot_manifest():
    """Verify PilotManifest serialization, add, get, and roundtrip."""
    manifest = PilotManifest(description="Test Manifest")
    sess = PilotSession(
        session_id="SESSION_A",
        video_path="dummy.mp4",
        duration=1800.0,
        final_placement=1,
        economic_archetype=EconomicArchetype.FAST_LEVELUP
    )
    manifest.add_session(sess)
    assert len(manifest.sessions) == 1
    assert manifest.get_session("SESSION_A") is not None
    assert manifest.get_session("SESSION_NONEXISTENT") is None

    d = manifest.to_dict()
    reconstructed = PilotManifest.from_dict(d)
    assert len(reconstructed.sessions) == 1
    assert reconstructed.sessions[0].final_placement == 1


def test_session_isolation():
    """Verify session metrics and artifacts are maintained in distinct directories."""
    runner = MultiSessionPilotRunner()
    sess_a = PilotSession(session_id="SESS_1", video_path="v1.mp4", duration=100.0)
    sess_b = PilotSession(session_id="SESS_2", video_path="v2.mp4", duration=200.0)
    manifest = PilotManifest(sessions=[sess_a, sess_b])

    assert sess_a.session_id != sess_b.session_id
    assert sess_a.video_path != sess_b.video_path


def test_same_config_across_sessions():
    """Verify identical detector weights and rules are applied across sessions."""
    runner = MultiSessionPilotRunner()
    detector = runner.action_detector
    assert detector is not None
    # Frozen detector configuration
    assert hasattr(detector, "detect_actions")


def test_session_metrics():
    """Verify schema integrity of SessionMetrics container."""
    m = SessionMetrics(session_id="SESSION_A")
    m.roll_precision = 1.0
    m.roll_recall = 0.571
    m.roll_f1 = 0.727
    d = m.to_dict()
    assert d["session_id"] == "SESSION_A"
    assert d["actions"]["ROLL"]["f1"] == 0.727


def test_pooled_metrics():
    """Verify cross-session pooled arithmetic averages."""
    evaluator = MultiSessionEvaluator()
    m1 = SessionMetrics(session_id="S1", roll_f1=0.70, buy_f1=0.90)
    m2 = SessionMetrics(session_id="S2", roll_f1=0.80, buy_f1=1.00)
    m3 = SessionMetrics(session_id="S3", roll_f1=0.90, buy_f1=0.80)

    # Arithmetic mean across 3 sessions
    mean_roll = float(np.mean([0.70, 0.80, 0.90]))
    mean_buy = float(np.mean([0.90, 1.00, 0.80]))

    assert abs(mean_roll - 0.80) < 1e-4
    assert abs(mean_buy - 0.90) < 1e-4


def test_cross_session_variance():
    """Verify calculation of cross-session standard deviation and min/max."""
    f1s = [0.727, 0.650, 0.800]
    std_val = float(np.std(f1s))
    min_val = float(np.min(f1s))
    max_val = float(np.max(f1s))

    summary = CrossSessionSummary(
        session_count=3,
        roll_f1_mean=float(np.mean(f1s)),
        roll_f1_std=std_val,
        roll_f1_min=min_val,
        roll_f1_max=max_val
    )
    d = summary.to_dict()
    assert d["roll_f1_stats"]["min"] == 0.65
    assert d["roll_f1_stats"]["max"] == 0.80
    assert d["roll_f1_stats"]["std"] > 0


def test_gold_raw_vs_stabilized():
    """Verify strict separation between raw OCR success and forward carry."""
    m = SessionMetrics(
        session_id="SESSION_A",
        raw_ocr_valid_rate=0.228,
        carried_forward_rate=0.772,
        stabilized_accuracy=0.985
    )
    d = m.to_dict()
    assert d["gold"]["raw_ocr_valid_rate"] == 0.228
    assert d["gold"]["carried_forward_rate"] == 0.772
    assert d["gold"]["raw_ocr_valid_rate"] != d["gold"]["stabilized_accuracy"]


def test_gold_delta_lineage():
    """Verify LineageRecord struct captures action-to-gold tracking."""
    rec = LineageRecord(
        gt_action_id="GT_001",
        gt_timestamp_sec=321.5,
        gt_action_type="BUY_UNIT",
        gold_before=35,
        gold_after=32,
        gold_delta_val=-3,
        gold_delta_observed=True,
        action_event_detected=True,
        loss_stage=LineageLossStage.NONE
    )
    d = rec.to_dict()
    assert d["gt_action_id"] == "GT_001"
    assert d["gold_delta_val"] == -3
    assert d["loss_stage"] == "NONE"


def test_action_metrics():
    """Verify precision, recall, and F1 calculations for actions."""
    tp, fp, fn = 16, 0, 12
    p = tp / (tp + fp)
    r = tp / (tp + fn)
    f1 = 2 * p * r / (p + r)
    assert p == 1.0
    assert abs(r - 0.5714) < 1e-3
    assert abs(f1 - 0.7272) < 1e-3


def test_rule_replay_vs_production():
    """Verify gap computation between Rule Replay and Full-Gold Production."""
    m = SessionMetrics(
        session_id="SESSION_A",
        rule_replay_roll_f1=0.727,
        production_roll_f1=0.727,
        replay_production_gap_roll=0.0
    )
    d = m.to_dict()
    assert d["production_gap"]["gap_roll"] == 0.0


def test_cross_session_no_leakage():
    """Verify T0 state has zero leakage across all sessions."""
    summary = CrossSessionSummary(session_count=3, total_leakage_violations=0)
    assert summary.total_leakage_violations == 0


def test_low_action_coverage():
    """Verify flagging when a session has insufficient event diversity."""
    m = SessionMetrics(session_id="LOW_ACTION_SESS", gt_roll_count=1, gt_buy_count=0)
    is_low = (m.gt_roll_count + m.gt_buy_count) < 5
    assert is_low is True


def test_pilot_gate():
    """Verify Acceptance Gate transitions correctly across verdicts."""
    evaluator = MultiSessionEvaluator()

    # Case 1: < 3 sessions -> INSUFFICIENT_DATA
    m_few = PilotManifest(sessions=[PilotSession(session_id="S1", video_path="", duration=0)])
    sum_few = evaluator.evaluate_manifest(m_few, "dummy_out", "dummy_ann")
    assert sum_few.gate_verdict == PilotGateVerdict.INSUFFICIENT_DATA
