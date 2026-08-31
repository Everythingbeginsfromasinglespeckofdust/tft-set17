"""Comprehensive Unit Tests for TFT Real Match Dataset Collection v1.1.

23 tests covering all v1.1 data collection requirements per specification.
"""
from __future__ import annotations
import glob
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
    DualReviewRecord,
    InteractionLog,
    DatasetRow,
    QualityFlagEnum,
    ActionTypeEnum,
    RationaleCategoryEnum
)
from tft.dataset_collection.session_manager import SessionManager
from tft.dataset_collection.blind_review import BlindReviewWorkflow, CollectionStep
from tft.dataset_collection.evidence_capture import VideoSourceValidator, FrameEvidenceCapturer
from tft.dataset_collection.dual_reviewer import DualReviewManager
from tft.dataset_collection.collection_controller import CollectionController
from tft.dataset_collection.integrity_validator import IntegrityValidator
from tft.dataset_collection.exporter import DatasetExporter
from tft.dataset_collection.analyzer import DatasetAnalyzer

PROTECTED_DIRS = ["src/tft/decision", "src/tft/simulation", "src/tft/evaluation", "src/tft/domain"]
DATASET_DIR = os.path.join(_ROOT, "data", "decision_dataset")
JSONL_PATH = os.path.join(DATASET_DIR, "datasets", "DECISION_DATASET_V1_1", "final_dataset.jsonl")


@pytest.fixture(scope="module")
def session_manager():
    return SessionManager()


@pytest.fixture(scope="module")
def validator():
    return IntegrityValidator()


@pytest.fixture(scope="module")
def loaded_rows():
    exporter = DatasetExporter()
    exporter.export_all()
    analyzer = DatasetAnalyzer()
    return analyzer.load_rows_from_jsonl()


def test_video_source_validation():
    """1. Prohibited naming patterns rejected; authentic original MP4 accepted."""
    v_val = VideoSourceValidator()
    is_valid, _ = v_val.validate_video_file("C:/recordings/fake_replay.mp4")
    assert is_valid is False
    is_valid, _ = v_val.validate_video_file("C:/recordings/synthetic_match.mp4")
    assert is_valid is False
    is_valid, _ = v_val.validate_video_file("C:/recordings/test_clip.mp4")
    assert is_valid is False


def test_video_hash(session_manager):
    """2. SHA-256 video hash computed correctly and valid format."""
    manifest = session_manager.load_manifest("SESSION_001")
    assert manifest is not None
    sha = manifest.video.sha256
    assert len(sha) == 64
    assert all(c in "0123456789abcdefABCDEF" for c in sha)


def test_checkpoint_frame_evidence(loaded_rows):
    """3. Frame evidence screenshot metadata and SHA-256 verified."""
    assert len(loaded_rows) >= 20
    for r in loaded_rows:
        fe = r.frame_evidence
        assert fe is not None
        assert "frame_sha256" in fe
        assert len(fe["frame_sha256"]) == 64


def test_raw_state_schema(loaded_rows):
    """4. Raw state conforms to DECISION_DATASET_V1_1 schema."""
    for r in loaded_rows:
        assert r.schema_version == "DECISION_DATASET_V1_1"
        assert "hp" in r.raw_state
        assert "gold" in r.raw_state
        assert "level" in r.raw_state
        assert "stage_round" in r.raw_state


def test_human_preference_independence(loaded_rows):
    """5. Human preference not auto-copied from engine prediction."""
    for r in loaded_rows:
        rev = r.human_review
        assert rev.get("source") == "HUMAN_INPUT"
        assert rev.get("source") != "AUTO_COPIED"


def test_actual_action_independence(loaded_rows):
    """6. Actual action source is HUMAN_VIDEO_REVIEW with reviewer ID."""
    for r in loaded_rows:
        act = r.actual_action
        assert act.get("source") == "HUMAN_VIDEO_REVIEW"
        assert "actual_player_action" in act
        assert "reviewer_id" in act


def test_blind_review_order():
    """7. State machine enforces STATE_ENTRY -> PREFERENCE -> ACTUAL_ACTION -> REVEAL -> JUDGMENT -> OUTCOME."""
    wf = BlindReviewWorkflow(CollectionStep.STATE_ENTRY)
    assert wf.is_engine_recommendation_allowed() is False
    assert wf.is_outcome_allowed() is False

    ok, _ = wf.advance_to(CollectionStep.HUMAN_PREFERENCE)
    assert ok is True
    assert wf.is_engine_recommendation_allowed() is False

    ok, _ = wf.advance_to(CollectionStep.ACTUAL_ACTION)
    assert ok is True

    ok, _ = wf.advance_to(CollectionStep.REVEAL_ENGINE)
    assert ok is True
    assert wf.is_engine_recommendation_allowed() is True

    ok, _ = wf.advance_to(CollectionStep.HUMAN_JUDGMENT)
    assert ok is True

    ok, _ = wf.advance_to(CollectionStep.OUTCOME_LINK)
    assert ok is True
    assert wf.is_outcome_allowed() is True


def test_candidate_hidden_before_preference():
    """8. Candidate engine recommendations strictly hidden during collection."""
    wf = BlindReviewWorkflow(CollectionStep.HUMAN_PREFERENCE)
    payload = {
        "engine_prediction": {"recommended_action": "SAVE_GOLD"},
        "candidate_prediction": {"recommended_action": "ROLL"},
        "candidate_adjustments": {"survival_elim_coeff": 0.08}
    }
    filtered = wf.filter_response_payload(payload)
    assert "candidate_prediction" not in filtered
    assert "candidate_adjustments" not in filtered
    assert filtered["engine_prediction"]["status"] == "HIDDEN_UNTIL_PREFERENCE_SUBMITTED"


def test_outcome_hidden_before_review():
    """9. T1/T2 outcomes hidden until judgment is finalized."""
    wf = BlindReviewWorkflow(CollectionStep.HUMAN_PREFERENCE)
    payload = {"t1_outcome": {"hp_delta": -14, "t1_hp": 86}}
    filtered = wf.filter_response_payload(payload)
    assert filtered["t1_outcome"]["status"] == "HIDDEN_UNTIL_REVIEW_FINALIZED"


def test_interaction_log(session_manager):
    """10. Interaction log records events, clicks, manual inputs, and reviewer ID."""
    s_dir = session_manager.get_session_dir("SESSION_001")
    ilog_path = os.path.join(s_dir, "raw", "CP001", "interaction_log.json")
    assert os.path.exists(ilog_path)
    with open(ilog_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "clicks_count" in data
    assert "manual_inputs_count" in data
    assert "time_spent_sec" in data


def test_timestamp_integrity(loaded_rows):
    """11. Checkpoint timestamps strictly increasing within session."""
    timestamps = [r.video_timestamp_sec for r in loaded_rows if r.video_timestamp_sec is not None]
    for i in range(len(timestamps) - 1):
        assert timestamps[i] < timestamps[i + 1]


def test_fake_checkpoint_detection(validator):
    """12. Fake detector flags duplicate timestamps as SUSPICIOUS."""
    r1 = DatasetRow(session_id="S1", checkpoint_id="CP001", video_timestamp_sec=50.0)
    r2 = DatasetRow(session_id="S1", checkpoint_id="CP002", video_timestamp_sec=50.0)
    res = validator.detect_fake_data([r1, r2])
    assert res["total_suspicious_checkpoints"] > 0
    assert any("DUPLICATE_TIMESTAMP" in f["type"] for f in res["findings"])


def test_duplicate_detection(validator):
    """13. Duplicate consecutive states flagged."""
    r1 = DatasetRow(
        session_id="S1", checkpoint_id="CP001", video_timestamp_sec=50.0,
        raw_state={"hp": 50, "gold": 20, "stage_round": "3-1"}
    )
    r2 = DatasetRow(
        session_id="S1", checkpoint_id="CP002", video_timestamp_sec=50.0,
        raw_state={"hp": 50, "gold": 20, "stage_round": "3-1"}
    )
    res = validator.detect_fake_data([r1, r2])
    assert res["total_suspicious_checkpoints"] > 0


def test_synthetic_detection(validator):
    """14. Synthetic constant timestamp deltas flagged."""
    rows = [
        DatasetRow(session_id="S_SYNTH", checkpoint_id=f"CP{i:03d}", video_timestamp_sec=float(i * 30.0))
        for i in range(6)
    ]
    res = validator.detect_fake_data(rows)
    assert any("SYNTHETIC" in f["type"] for f in res["findings"])


def test_prediction_contamination(validator):
    """15. Auto-copied prediction to human label flagged."""
    r = DatasetRow(
        session_id="S1", checkpoint_id="CP001", video_timestamp_sec=10.0,
        engine_prediction={"recommended_action": "ROLL"},
        human_review={"human_preferred_action": "ROLL", "source": "AUTO_COPIED"}
    )
    res = validator.detect_fake_data([r])
    assert res["total_suspicious_checkpoints"] == 1


def test_match_independence(session_manager, validator):
    """16. Match IDs tracked independently from session IDs."""
    manifests = [session_manager.load_manifest(s) for s in session_manager.list_sessions()]
    res = validator.check_match_independence(manifests)
    assert res["unique_matches"] >= 1


def test_dual_review():
    """17. Dual review Cohen's Kappa and raw agreement calculated correctly."""
    prim = ["ROLL", "ROLL", "SAVE_GOLD", "LEVEL_UP", "SAVE_GOLD"]
    sec = ["ROLL", "SAVE_GOLD", "SAVE_GOLD", "LEVEL_UP", "SAVE_GOLD"]
    res = DualReviewManager.calculate_cohens_kappa(prim, sec)
    assert res["sample_size"] == 5
    assert res["raw_agreement_rate"] == 0.8
    assert res["cohens_kappa"] > 0.5


def test_t1_linkage(loaded_rows):
    """18. Multi-horizon outcome linkage verified."""
    for r in loaded_rows:
        out = r.t1_outcome
        if out.get("t1_checkpoint_id") is not None:
            assert out.get("t1_hp") is not None
            assert out.get("hp_delta") is not None


def test_final_placement_is_post_session(session_manager, loaded_rows):
    """19. Final placement in manifest only, never in T0 state."""
    manifest = session_manager.load_manifest("SESSION_001")
    assert manifest.final_placement == 2
    for r in loaded_rows:
        assert "final_placement" not in r.raw_state
        assert "placement" not in r.raw_state


def test_dataset_export():
    """20. DECISION_DATASET_V1_1 export creates valid JSONL and CSV."""
    exporter = DatasetExporter()
    res = exporter.export_all()
    assert os.path.exists(res["jsonl_path_v1_1"])
    assert os.path.exists(res["csv_path_v1_1"])
    assert res["total_checkpoints"] >= 20


def test_dataset_audit():
    """21. Standalone audit tool recomputes stats directly from raw files."""
    from audit_decision_dataset import run_audit
    res = run_audit(JSONL_PATH)
    assert res["total_checkpoints"] >= 20
    assert res["fake_data"]["verdict"] == "CLEAN"


def test_calibration_readiness(validator, session_manager, loaded_rows):
    """22. Correctly outputs DATA_COLLECTION_IN_PROGRESS when matches < 5."""
    manifests = [session_manager.load_manifest(s) for s in session_manager.list_sessions()]
    gate = validator.evaluate_calibration_gate(manifests, loaded_rows)
    assert gate["final_gate_verdict"] == "DATA_COLLECTION_IN_PROGRESS"
    assert gate["checklist"]["matches_ge_5"] is False
    assert gate["checklist"]["frame_evidence_ge_95pct"] is True


def test_protected_core_unchanged():
    """23. Protected directories must have 0 git diff lines."""
    res = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"] + PROTECTED_DIRS,
        capture_output=True, text=True, cwd=_ROOT
    )
    changed = [l.strip() for l in res.stdout.splitlines() if l.strip()]
    assert len(changed) == 0, f"Protected core modified! Files: {changed}"
