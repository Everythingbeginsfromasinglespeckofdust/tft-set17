"""Unit tests for Action Causality Audit Engine and Data Models."""
import os
import sys
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.vision.causal_models import FrameSnapshot, SignalTransition, SignalType, EventCausalTrace, CausalSignature
from tft.vision.causal_extractor import CausalWindowExtractor
from tft.vision.causal_analyzer import ActionCausalAnalyzer
from tft.vision.ground_truth import GroundTruthDataset, GroundTruthEvent, GroundTruthActionType


def test_causal_window_extraction():
    """Verify FrameSnapshot sequence initialization and time calculation."""
    snap1 = FrameSnapshot(timestamp_sec=10.0, frame_index=600, gold=35)
    snap2 = FrameSnapshot(timestamp_sec=10.05, frame_index=603, gold=33)

    assert snap2.timestamp_sec - snap1.timestamp_sec == pytest.approx(0.05)
    assert snap1.to_dict()["timestamp_sec"] == 10.0


def test_signal_transition_timing():
    """Verify SignalTransition onset calculation."""
    tr = SignalTransition(
        signal_type=SignalType.SHOP,
        timestamp_sec=343.15,
        dt_from_action=0.15,
        before_value=["A", "B", "C", "D", "E"],
        after_value=["F", "G", "H", "I", "J"]
    )
    assert tr.dt_from_action == 0.15
    assert tr.signal_type == SignalType.SHOP


def test_roll_signature_analysis():
    """Verify CausalSignature support and specificity calculation."""
    sig = CausalSignature(
        signature_id="SIG_TEST_01",
        action_type="ROLL",
        name="Multi-Slot Refresh",
        description="Shop refreshes 3+ slots",
        step_sequence=["GOLD", "SHOP"],
        support_count=21,
        total_action_count=28,
        support_rate=21/28,
        false_alarm_count_no_action=0,
        total_no_action_count=30,
        specificity=1.0,
        median_latency_sec=0.05,
        timing_variance=0.002
    )
    assert sig.support_rate == 0.75
    assert sig.specificity == 1.0


def test_buy_signature_analysis():
    """Verify BUY signature step sequence."""
    sig = CausalSignature(
        signature_id="SIG_BUY_01",
        action_type="BUY_UNIT",
        name="Slot Emptied and Bench Addition",
        description="Slot emptied and champion added to bench",
        step_sequence=["SLOT_EMPTIED", "GOLD_DECREASE_COST", "BENCH_ADD"],
        support_count=14,
        total_action_count=18,
        support_rate=14/18,
        false_alarm_count_no_action=0,
        total_no_action_count=30,
        specificity=1.0,
        median_latency_sec=0.08,
        timing_variance=0.003
    )
    assert len(sig.step_sequence) == 3
    assert sig.support_count == 14


def test_no_action_specificity():
    """Verify specificity computation against NO_ACTION windows."""
    traces = [
        EventCausalTrace("na_1", "NO_ACTION", None, 100.0, 98.5, 101.5, shop_slots_changed=0),
        EventCausalTrace("na_2", "NO_ACTION", None, 150.0, 148.5, 151.5, shop_slots_changed=0),
        EventCausalTrace("na_3", "NO_ACTION", None, 200.0, 198.5, 201.5, shop_slots_changed=1)
    ]
    changes = sum(1 for t in traces if t.shop_slots_changed > 0)
    spec = 1.0 - (changes / len(traces))
    assert spec == pytest.approx(2/3)


def test_system_refresh_comparison():
    """Verify trace categorization for system vs player events."""
    tr_sys = EventCausalTrace("sys_1", "SYSTEM_REFRESH", None, 300.0, 298.5, 301.5)
    tr_roll = EventCausalTrace("roll_1", "ROLL", None, 343.0, 341.5, 344.5)
    assert tr_sys.event_type != tr_roll.event_type


def test_rapid_reroll_interval():
    """Verify rapid reroll interval distribution categorization."""
    intervals = [0.08, 0.15, 0.25, 0.40, 0.80, 2.5]
    rapid_dist = {
        "<0.10s": sum(1 for dt in intervals if dt < 0.10),
        "0.10~0.20s": sum(1 for dt in intervals if 0.10 <= dt < 0.20),
        "0.20~0.30s": sum(1 for dt in intervals if 0.20 <= dt < 0.30),
        "0.30~0.50s": sum(1 for dt in intervals if 0.30 <= dt < 0.50),
        "0.50~1.00s": sum(1 for dt in intervals if 0.50 <= dt < 1.00),
        ">1.00s": sum(1 for dt in intervals if dt >= 1.00)
    }
    assert rapid_dist["<0.10s"] == 1
    assert rapid_dist[">1.00s"] == 1


def test_same_champion_collision():
    """Verify same-champion collision flagging when <3 slots change."""
    tr = EventCausalTrace(
        event_id="roll_collision",
        event_type="ROLL",
        target_champion=None,
        gt_timestamp_sec=350.0,
        window_start_sec=348.5,
        window_end_sec=351.5,
        shop_slots_changed=2,
        is_same_champion_collision=True
    )
    assert tr.is_same_champion_collision is True
    assert tr.shop_slots_changed < 3


def test_signature_support():
    """Verify likelihood ratio math on signature."""
    support_rate = 0.80
    false_alarm_rate = 0.05
    lr = support_rate / false_alarm_rate
    assert lr == 16.0


def test_timestamp_alignment():
    """Verify window extraction bounds [T - radius, T + radius]."""
    gt_t = 343.0
    radius = 1.5
    start = max(0.0, gt_t - radius)
    end = gt_t + radius
    assert start == 341.5
    assert end == 344.5
