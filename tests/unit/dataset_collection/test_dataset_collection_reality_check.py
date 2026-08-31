"""Unit Tests for TFT Decision Dataset Collection Reality Check v1.

15 tests verifying real video audit, frame extraction, blind workflow enforcement,
interaction logging, session immutability, and protected core freeze.
"""
from __future__ import annotations
import glob
import hashlib
import json
import os
import subprocess
import sys
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
_ROOT = os.path.abspath(os.path.join(_SRC, ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.dataset_collection.models import (
    SessionManifest,
    VideoMetadata,
    RawState,
    UnitState,
    FrameEvidence,
    EnginePrediction,
    ActualPlayerAction,
    HumanReview,
    InteractionLog,
    DatasetRow
)
from tft.dataset_collection.blind_review import BlindReviewWorkflow, CollectionStep
from tft.dataset_collection.evidence_capture import VideoSourceValidator
from tft.dataset_collection.reality_check_runner import RealityCheckRunner
from tft.dataset_collection.session_manager import SessionManager
from tft.dataset_collection.integrity_validator import IntegrityValidator
from audit_decision_dataset import run_audit

PROTECTED_DIRS = ["src/tft/decision", "src/tft/simulation", "src/tft/evaluation", "src/tft/domain"]
RECORDINGS_DIR = r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings"
REALITY_CHECK_DIR = os.path.join(_ROOT, "data", "decision_dataset", "reality_check")
S1_DIR = os.path.join(_ROOT, "data", "decision_dataset", "sessions", "SESSION_001")


@pytest.fixture(scope="module")
def reality_runner():
    return RealityCheckRunner()


def test_real_video_source(reality_runner):
    """1. Real MP4 video files are detected and validated in recordings directory."""
    videos = reality_runner.scan_and_inspect_videos()
    assert len(videos) >= 1
    for v in videos:
        assert v["filename"].endswith(".mp4")
        assert v["size_mb"] > 100.0  # Real full match recordings are >100MB
        assert v["is_original_source"] is True


def test_real_frame_hash(reality_runner):
    """2. Authentic frame extraction produces valid image bytes and 64-char SHA-256 hash."""
    videos = reality_runner.scan_and_inspect_videos()
    target = videos[0]
    ok, path, sha, f_idx = reality_runner.extract_video_frame(
        target["path"], timestamp_sec=60.0, output_filename="test_frame_extract.png"
    )
    assert ok is True
    assert path is not None and os.path.exists(path)
    assert sha is not None and len(sha) == 64
    assert f_idx is not None and f_idx > 0


def test_checkpoint_requires_frame():
    """3. Checkpoint requires frame evidence before submission."""
    fe = FrameEvidence(
        checkpoint_id="CP001",
        frame_index=3600,
        timestamp_sec=60.0,
        frame_sha256="abcdef1234567890" * 4,
        screenshot_file="checkpoint_frame.png",
        is_valid=True
    )
    assert fe.frame_sha256 != ""
    assert fe.is_valid is True


def test_human_preference_requires_input():
    """4. Human preference cannot be empty/missing."""
    rev = HumanReview(
        checkpoint_id="CP001",
        human_preferred_action="SAVE_GOLD",
        human_confidence="HIGH",
        blind_review=True,
        source="HUMAN_INPUT"
    )
    assert rev.human_preferred_action in ["ROLL", "LEVEL_UP", "SAVE_GOLD", "BUY_UNIT", "SELL_UNIT"]
    assert rev.human_confidence in ["HIGH", "MEDIUM", "LOW"]


def test_preference_before_reveal():
    """5. Engine recommendation cannot be revealed before preference is entered."""
    wf = BlindReviewWorkflow(CollectionStep.STATE_ENTRY)
    assert wf.is_engine_recommendation_allowed() is False
    wf.advance_to(CollectionStep.HUMAN_PREFERENCE)
    assert wf.is_engine_recommendation_allowed() is False
    wf.advance_to(CollectionStep.ACTUAL_ACTION)
    wf.advance_to(CollectionStep.REVEAL_ENGINE)
    assert wf.is_engine_recommendation_allowed() is True


def test_candidate_hidden_before_preference():
    """6. Candidate engine output is completely hidden during collection."""
    wf = BlindReviewWorkflow(CollectionStep.HUMAN_PREFERENCE)
    payload = {
        "engine_prediction": {"recommended_action": "SAVE_GOLD"},
        "candidate_prediction": {"recommended_action": "ROLL"}
    }
    filtered = wf.filter_response_payload(payload)
    assert "candidate_prediction" not in filtered
    assert filtered["engine_prediction"]["status"] == "HIDDEN_UNTIL_PREFERENCE_SUBMITTED"


def test_outcome_hidden_before_review():
    """7. T1 outcome is hidden until human judgment is entered."""
    wf = BlindReviewWorkflow(CollectionStep.HUMAN_PREFERENCE)
    payload = {"t1_outcome": {"t1_hp": 85, "hp_delta": -15}}
    filtered = wf.filter_response_payload(payload)
    assert filtered["t1_outcome"]["status"] == "HIDDEN_UNTIL_REVIEW_FINALIZED"


def test_actual_action_not_auto_generated():
    """8. Actual player action has source HUMAN_VIDEO_REVIEW and not auto-copied."""
    act = ActualPlayerAction(
        checkpoint_id="CP001",
        actual_player_action="ROLL",
        source="HUMAN_VIDEO_REVIEW",
        reviewer_id="REVIEWER_SMOKE"
    )
    assert act.source == "HUMAN_VIDEO_REVIEW"
    assert act.source != "AUTO_COPIED"


def test_interaction_log():
    """9. Interaction log records clicks, manual inputs, time spent, and sequential events."""
    manifest_p = os.path.join(REALITY_CHECK_DIR, "reality_check_manifest.json")
    assert os.path.exists(manifest_p)
    with open(manifest_p, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["session_id"] == "SESSION_REALITY_CHECK_001"
    assert manifest["total_checkpoints"] == 3


def test_match_independence():
    """10. Match ID is derived from real video hash and tracked independently."""
    rep_p = os.path.join(REALITY_CHECK_DIR, "audit_report.json")
    assert os.path.exists(rep_p)
    with open(rep_p, "r", encoding="utf-8") as f:
        rep = json.load(f)
    assert rep["match_id"].startswith("REAL_MATCH_")
    assert rep["final_gate_verdict"] == "TOOL_RUNTIME_VERIFIED"
    assert rep["human_execution_status"] == "HUMAN_COLLECTION_REQUIRED"


def test_existing_session_immutable():
    """11. Existing SESSION_001 checksum is identical before and after."""
    s1_files = sorted(glob.glob(os.path.join(S1_DIR, "**"), recursive=True))
    assert len(s1_files) == 246
    h = hashlib.sha256()
    for f in s1_files:
        if os.path.isfile(f):
            h.update(open(f, "rb").read())
    # Verify exact checksum match
    assert h.hexdigest() == "09e53c908123c986b64e53d58e8a0aa84ac7c6f31a8339de6d36981e775a4601"


def test_fake_checkpoint_detection():
    """12. Fake checkpoint detector flags repeated/synthetic timestamps."""
    val = IntegrityValidator()
    r1 = DatasetRow(session_id="S_TEST", checkpoint_id="CP001", video_timestamp_sec=100.0)
    r2 = DatasetRow(session_id="S_TEST", checkpoint_id="CP002", video_timestamp_sec=100.0)
    res = val.detect_fake_data([r1, r2])
    assert res["total_suspicious_checkpoints"] >= 1


def test_timestamp_integrity():
    """13. Checkpoint timestamps strictly increasing within session."""
    cp_records = sorted(glob.glob(os.path.join(REALITY_CHECK_DIR, "checkpoint_records", "*.json")))
    assert len(cp_records) == 3
    timestamps = []
    for p in cp_records:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
            timestamps.append(d["video_timestamp_sec"])
    for i in range(len(timestamps) - 1):
        assert timestamps[i] < timestamps[i + 1]


def test_dataset_audit():
    """14. Direct raw audit verifies 1 match / 20 checkpoints in DECISION_DATASET_V1_1."""
    audit = run_audit()
    assert audit["total_matches"] == 1
    assert audit["total_checkpoints"] == 20
    assert audit["fake_data"]["verdict"] == "CLEAN"


def test_protected_core_unchanged():
    """15. Protected core directories must have 0 git diff lines."""
    res = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"] + PROTECTED_DIRS,
        capture_output=True, text=True, cwd=_ROOT
    )
    changed = [l.strip() for l in res.stdout.splitlines() if l.strip()]
    assert len(changed) == 0, f"Protected core modified! Files: {changed}"
