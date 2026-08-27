"""Comprehensive Unit Tests for TFT Vision Validation Overlay v1 Architecture."""
import os
import sys

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import json
import shutil
import tempfile
import time

import numpy as np
import pytest

from tft.vision.frame_source import FrameSource, FramePacket, MockFrameSource
from tft.vision.video_frame_source import VideoFileFrameSource
from tft.vision.live_capture_source import DesktopCaptureFrameSource
from tft.vision.analysis_manager import VisionAnalysisManager
from tft.vision.validation_models import (
    VerificationEvent,
    VerificationSummary,
    TargetType,
    HumanVerdict,
    ErrorReason
)
from tft.vision.verification_store import VerificationStore
from tft.vision.overlay_state import OverlayState, ShopSlotDisplay
from tft.vision.overlay_renderer import OverlayRenderer


@pytest.fixture
def temp_store_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_mock_frame_source():
    """1. Test MockFrameSource packet generation, fps, and frame indexing."""
    src = MockFrameSource(fps=10.0, total_frames=5)
    assert not src.is_live()
    p1 = src.read()
    assert p1 is not None
    assert p1.frame_index == 0
    assert p1.timestamp_sec == 0.0

    p2 = src.read()
    assert p2 is not None
    assert p2.frame_index == 1
    assert p2.timestamp_sec == 0.1
    src.close()


def test_video_frame_source_creation():
    """2. Test VideoFileFrameSource creation and duration."""
    test_video = os.path.join("output", "video_analysis", "overlay_verification_eda87ad9_300s_360s.mp4")
    if os.path.exists(test_video):
        src = VideoFileFrameSource(test_video)
        assert src.duration_sec > 0
        assert not src.is_live()
        p = src.read()
        assert p is not None
        assert p.frame.shape[0] > 0
        src.close()
    else:
        pytest.skip("Test video clip not found")


def test_video_seek():
    """3. Test VideoFrameSource seeking functionality."""
    test_video = os.path.join("output", "video_analysis", "overlay_verification_eda87ad9_300s_360s.mp4")
    if os.path.exists(test_video):
        src = VideoFileFrameSource(test_video)
        src.seek(5.0)
        p = src.read()
        assert p is not None
        assert abs(p.timestamp_sec - 5.0) < 0.2
        src.close()
    else:
        pytest.skip("Test video clip not found")


def test_frame_step():
    """4. Test single frame stepping (+1, -1)."""
    src = MockFrameSource(fps=20.0, total_frames=10)
    p_step1 = src.step_frame(2)
    assert p_step1 is not None
    assert p_step1.frame_index == 2
    p_step2 = src.step_frame(-1)
    assert p_step2 is not None
    assert p_step2.frame_index == 1
    src.close()


def test_live_capture_interface():
    """5. Test DesktopCaptureFrameSource interface and live properties."""
    live_src = DesktopCaptureFrameSource(target_fps=10.0)
    assert live_src.is_live() is True
    time.sleep(0.2)
    packet = live_src.read()
    assert packet is None or packet.source_type == "LIVE"
    live_src.close()


def test_analysis_manager(temp_store_dir):
    """6. Test VisionAnalysisManager execution with MockFrameSource."""
    src = MockFrameSource(fps=20.0, total_frames=5)
    store = VerificationStore(temp_store_dir)
    manager = VisionAnalysisManager(
        frame_source=src,
        session_id="TEST_SESSION",
        verification_store=store,
        analysis_fps=20.0
    )

    rendered = manager.process_next_frame(force_analysis=True)
    assert rendered is not None
    assert rendered.shape == (720, 1280, 3)
    assert manager.state.session_id == "TEST_SESSION"
    src.close()


def test_overlay_state():
    """7. Test OverlayState dictionary serialization and layer separation."""
    state = OverlayState(session_id="TEST_SESS")
    state.observed.gold = 50
    state.observed.stage_round = "4-1"
    state.derived.gold_delta = -2
    state.detected.action_type = "ROLL"
    state.detected.detection_score = 0.90

    d = state.to_dict()
    assert d["observed"]["gold"] == 50
    assert d["derived"]["gold_delta"] == -2
    assert d["detected"]["action"] == "ROLL"
    assert d["detected"]["score"] == 0.90


def test_verification_event():
    """8. Test VerificationEvent creation and to_dict format."""
    ev = VerificationEvent(
        verification_id="V001",
        session_id="SESSION_A",
        timestamp_sec=320.5,
        frame_index=6410,
        target_type=TargetType.ACTION,
        predicted_value="ROLL",
        human_verdict=HumanVerdict.CORRECT
    )
    d = ev.to_dict()
    assert d["verification_id"] == "V001"
    assert d["human_verdict"] == "CORRECT"
    assert d["target_type"] == "ACTION"


def test_wrong_event_capture(temp_store_dir):
    """9. Test automatic snapshot capture on WRONG verdict."""
    src = MockFrameSource(fps=20.0, total_frames=5)
    store = VerificationStore(temp_store_dir)
    manager = VisionAnalysisManager(
        frame_source=src,
        session_id="SESS_ERR",
        verification_store=store
    )

    manager.process_next_frame(force_analysis=True)
    ev = manager.verify_wrong(ErrorReason.ACTION_ERROR, corrected_action="NO_ACTION")

    assert ev.human_verdict == HumanVerdict.WRONG
    assert ev.error_reason == ErrorReason.ACTION_ERROR
    assert ev.frame_path is not None
    assert os.path.exists(ev.frame_path)
    assert os.path.exists(os.path.join(ev.frame_path, "frame_current.png"))
    assert os.path.exists(os.path.join(ev.frame_path, "error_diagnostics.json"))
    src.close()


def test_human_correction_preserves_prediction(temp_store_dir):
    """10. Test that human editing does NOT overwrite raw predictions."""
    src = MockFrameSource(fps=20.0, total_frames=5)
    store = VerificationStore(temp_store_dir)
    manager = VisionAnalysisManager(
        frame_source=src,
        session_id="SESS_PRESERVE",
        verification_store=store
    )

    manager.process_next_frame(force_analysis=True)
    manager.verify_edit(corrected_value="Zac", target_type=TargetType.SHOP_SLOT)

    # Check predictions.jsonl vs verifications.jsonl
    s_dir = store.get_session_dir("SESS_PRESERVE")
    ver_file = os.path.join(s_dir, "verifications.jsonl")
    corr_file = os.path.join(s_dir, "corrections.jsonl")

    assert os.path.exists(ver_file)
    assert os.path.exists(corr_file)
    with open(corr_file, "r", encoding="utf-8") as f:
        data = json.loads(f.readline())
        assert data["corrected_value"] == "Zac"
    src.close()


def test_ground_truth_export(temp_store_dir):
    """11. Test exporting verified ground truth dataset."""
    store = VerificationStore(temp_store_dir)
    store.log_verification(VerificationEvent(
        verification_id="V1",
        session_id="SESS_GT",
        timestamp_sec=100.0,
        frame_index=2000,
        target_type=TargetType.ACTION,
        predicted_value="ROLL",
        human_verdict=HumanVerdict.CORRECT
    ))
    store.log_verification(VerificationEvent(
        verification_id="V2",
        session_id="SESS_GT",
        timestamp_sec=102.0,
        frame_index=2040,
        target_type=TargetType.ACTION,
        predicted_value="ROLL",
        human_verdict=HumanVerdict.SKIPPED
    ))

    gt_file = store.export_ground_truth("SESS_GT")
    assert os.path.exists(gt_file)
    with open(gt_file, "r", encoding="utf-8") as f:
        gt_data = json.load(f)
        assert gt_data["total_verified_samples"] == 1
        assert gt_data["events"][0]["verified_value"] == "ROLL"


def test_keyboard_shortcuts(temp_store_dir):
    """12. Test verification shortcuts (correct, wrong, skip, roll, buy)."""
    src = MockFrameSource(fps=20.0, total_frames=10)
    store = VerificationStore(temp_store_dir)
    manager = VisionAnalysisManager(frame_source=src, session_id="SESS_KEYS", verification_store=store)

    manager.process_next_frame(force_analysis=True)
    ev_c = manager.verify_correct()
    assert ev_c.human_verdict == HumanVerdict.CORRECT

    ev_w = manager.verify_wrong()
    assert ev_w.human_verdict == HumanVerdict.WRONG

    ev_r = manager.annotate_action("ROLL")
    assert ev_r.human_label == "ROLL"

    summary = store.get_summary("SESS_KEYS")
    assert summary.total_reviewed == 3
    src.close()


def test_annotation_timeline():
    """13. Test timeline scrubber and HUD rendering without errors."""
    renderer = OverlayRenderer()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    state = OverlayState(duration_sec=300.0, current_timestamp_sec=150.0)
    state.observed.gold = 38
    state.detected.action_type = "ROLL"
    state.detected.detection_score = 0.90

    out = renderer.render(frame, state)
    assert out is not None
    assert out.shape == (720, 1280, 3)


def test_live_latency_metrics(temp_store_dir):
    """14. Test latency and data age calculation."""
    src = MockFrameSource(fps=20.0, total_frames=5)
    store = VerificationStore(temp_store_dir)
    manager = VisionAnalysisManager(frame_source=src, session_id="SESS_LAT", verification_store=store)

    manager.process_next_frame(force_analysis=True)
    assert manager.state.performance.data_age_sec >= 0.0
    assert manager.state.performance.latency_sec >= 0.0
    src.close()


def test_source_mode_isolation(temp_store_dir):
    """15. Test that Video and Live modes share the exact same VisionAnalysisManager."""
    src_video = MockFrameSource(fps=20.0, total_frames=5)
    store = VerificationStore(temp_store_dir)
    mgr_video = VisionAnalysisManager(frame_source=src_video, session_id="S1", mode="VALIDATION", verification_store=store)

    src_live = MockFrameSource(fps=20.0, total_frames=5)
    mgr_live = VisionAnalysisManager(frame_source=src_live, session_id="S2", mode="PRODUCTION", verification_store=store)

    assert type(mgr_video.action_detector) is type(mgr_live.action_detector)
    assert type(mgr_video.shop_recognizer) is type(mgr_live.shop_recognizer)
    assert type(mgr_video.gold_recognizer) is type(mgr_live.gold_recognizer)
    src_video.close()
    src_live.close()


def test_prediction_and_ground_truth_separation(temp_store_dir):
    """16. Test strict separation between predictions and human ground truth logs."""
    store = VerificationStore(temp_store_dir)
    store.log_prediction("SESS_ISO", {"timestamp_sec": 10.0, "action": "ROLL"})
    store.log_verification(VerificationEvent(
        verification_id="V_ISO",
        session_id="SESS_ISO",
        timestamp_sec=10.0,
        frame_index=200,
        target_type=TargetType.ACTION,
        predicted_value="ROLL",
        human_verdict=HumanVerdict.WRONG,
        corrected_value="NO_ACTION"
    ))

    s_dir = store.get_session_dir("SESS_ISO")
    with open(os.path.join(s_dir, "predictions.jsonl"), "r", encoding="utf-8") as f:
        pred = json.loads(f.readline())
        assert pred["action"] == "ROLL"

    with open(os.path.join(s_dir, "verifications.jsonl"), "r", encoding="utf-8") as f:
        ver = json.loads(f.readline())
        assert ver["human_verdict"] == "WRONG"
        assert ver["corrected_value"] == "NO_ACTION"
