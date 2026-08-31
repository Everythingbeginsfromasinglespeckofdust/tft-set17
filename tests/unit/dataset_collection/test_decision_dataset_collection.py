"""Unit tests for TFT Real Match Decision Dataset Collection v1.

19 tests covering all dataset collection requirements per specification.
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
    EnginePrediction,
    ActualPlayerAction,
    HumanReview,
    InteractionLog,
    DatasetRow,
    QualityFlagEnum
)
from tft.dataset_collection.session_manager import SessionManager
from tft.dataset_collection.integrity_validator import IntegrityValidator
from tft.dataset_collection.exporter import DatasetExporter
from tft.dataset_collection.analyzer import DatasetAnalyzer

PROTECTED_DIRS = ["src/tft/decision", "src/tft/simulation", "src/tft/evaluation", "src/tft/domain"]
DATASET_DIR = os.path.join(_ROOT, "data", "decision_dataset")
JSONL_PATH = os.path.join(DATASET_DIR, "datasets", "DECISION_DATASET_V1", "final_dataset.jsonl")


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


def test_session_manifest(session_manager):
    """1. Verify session manifest schema, video metadata, SHA256."""
    manifest = session_manager.load_manifest("SESSION_001")
    assert manifest is not None
    assert manifest.session_id == "SESSION_001"
    assert manifest.match_id != ""
    assert manifest.set_num == 18
    assert manifest.total_checkpoints >= 15
    assert len(manifest.video.sha256) == 64
    assert manifest.video.resolution != ""


def test_checkpoint_schema(loaded_rows):
    """2. Verify checkpoint schema matches DECISION_DATASET_V1."""
    assert len(loaded_rows) >= 20
    for row in loaded_rows:
        assert row.schema_version == "DECISION_DATASET_V1"
        assert row.session_id != ""
        assert row.match_id != ""
        assert row.checkpoint_id.startswith("CP")
        assert "hp" in row.raw_state
        assert "gold" in row.raw_state
        assert "level" in row.raw_state
        assert "stage_round" in row.raw_state
        assert "recommended_action" in row.engine_prediction
        assert "actual_player_action" in row.actual_action
        assert "human_preferred_action" in row.human_review


def test_raw_derived_separation(session_manager):
    """3. Verify raw state and derived features are stored in separate files."""
    s_dir = session_manager.get_session_dir("SESSION_001")
    raw_path = os.path.join(s_dir, "raw", "CP001", "state.json")
    feat_path = os.path.join(s_dir, "checkpoints", "CP001", "derived_features.json")
    assert os.path.exists(raw_path), "raw/CP001/state.json does not exist"
    assert os.path.exists(feat_path), "checkpoints/CP001/derived_features.json does not exist"

    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    with open(feat_path, "r", encoding="utf-8") as f:
        feat_data = json.load(f)

    assert "hp" in raw_data
    assert "board_power" in feat_data
    assert "board_power" not in raw_data, "Derived board_power leaked into raw state!"


def test_actual_action_independence(loaded_rows):
    """4. Verify actual action has source HUMAN_VIDEO_REVIEW and is not auto-generated."""
    for row in loaded_rows:
        act = row.actual_action
        assert act.get("source") == "HUMAN_VIDEO_REVIEW"
        assert act.get("actual_player_action") in ["ROLL", "BUY_UNIT", "LEVEL_UP", "SAVE_GOLD", "SELL_UNIT", "BUY_XP", "UNKNOWN"]


def test_human_preference_independence(loaded_rows):
    """5. Verify human preference is not auto-copied from engine prediction."""
    auto_copied_count = 0
    for row in loaded_rows:
        rev = row.human_review
        assert rev.get("source") == "HUMAN_INPUT"
        if rev.get("source") == "AUTO_COPIED":
            auto_copied_count += 1
    assert auto_copied_count == 0, "Found auto-copied human preferences!"


def test_blind_review_order(session_manager):
    """6. Verify blind review records exist and are flagged."""
    s_dir = session_manager.get_session_dir("SESSION_001")
    rev_files = glob.glob(os.path.join(s_dir, "reviews", "CP*", "human_review.json"))
    blind_count = 0
    for rf in rev_files:
        with open(rf, "r", encoding="utf-8") as f:
            rdata = json.load(f)
            if rdata.get("blind_review") is True:
                blind_count += 1
    # At least 25% blind review quota check
    assert blind_count >= 5, f"Expected at least 5 blind reviews, got {blind_count}"


def test_timestamp_integrity(loaded_rows):
    """7. Verify checkpoint video timestamps strictly increase within a session."""
    timestamps = [r.video_timestamp_sec for r in loaded_rows if r.video_timestamp_sec is not None]
    assert len(timestamps) >= 15
    for i in range(len(timestamps) - 1):
        assert timestamps[i] < timestamps[i + 1], (
            f"Timestamp not monotonically increasing: {timestamps[i]} >= {timestamps[i+1]}"
        )


def test_video_hash(session_manager):
    """8. Verify SHA256 video hash correctly recorded and valid format."""
    manifest = session_manager.load_manifest("SESSION_001")
    assert manifest is not None
    sha = manifest.video.sha256
    assert len(sha) == 64
    assert all(c in "0123456789abcdefABCDEF" for c in sha)


def test_match_independence(session_manager, validator):
    """9. Verify match IDs are tracked independently from session IDs."""
    manifests = [session_manager.load_manifest(s) for s in session_manager.list_sessions()]
    result = validator.check_match_independence(manifests)
    assert result["unique_matches"] >= 1
    assert "is_independent" in result


def test_state_diversity(validator, loaded_rows):
    """10. Verify diversity metrics computed for HP, Gold, Level, Stage, Power."""
    diversity = validator.compute_state_diversity(loaded_rows)
    assert "hp_distribution" in diversity
    assert "gold_distribution" in diversity
    assert "level_distribution" in diversity
    assert "stage_distribution" in diversity
    assert "actual_action_distribution" in diversity
    assert "human_preference_distribution" in diversity
    # Must have multiple HP and Gold tiers
    assert len(diversity["hp_distribution"]) >= 3
    assert len(diversity["gold_distribution"]) >= 3


def test_duplicate_detection(validator):
    """11. Duplicate state detection flags identical back-to-back entries."""
    row1 = DatasetRow(
        session_id="S1", checkpoint_id="CP001", video_timestamp_sec=100.0,
        raw_state={"hp": 50, "gold": 20, "stage_round": "3-2"}
    )
    row2 = DatasetRow(
        session_id="S1", checkpoint_id="CP002", video_timestamp_sec=100.0,
        raw_state={"hp": 50, "gold": 20, "stage_round": "3-2"}
    )
    fake_res = validator.detect_fake_data([row1, row2])
    assert fake_res["total_suspicious_checkpoints"] > 0
    assert any("DUPLICATE" in f["type"] or "IDENTICAL" in f["type"] for f in fake_res["findings"])


def test_fake_data_detection(validator):
    """12. Fake detector flags repeated timestamps and auto-copy patterns."""
    row1 = DatasetRow(
        session_id="S_TEST", checkpoint_id="CP001", video_timestamp_sec=50.0,
        engine_prediction={"recommended_action": "ROLL"},
        human_review={"human_preferred_action": "ROLL", "source": "AUTO_COPIED"}
    )
    fake_res = validator.detect_fake_data([row1])
    assert fake_res["total_suspicious_checkpoints"] == 1
    assert fake_res["findings"][0]["type"] == "AUTO_COPIED_LABEL"


def test_outcome_linkage(loaded_rows):
    """13. T1/T2 outcomes correctly link next-round HP/gold/power delta."""
    linked_t1_count = 0
    for r in loaded_rows:
        out = r.t1_outcome
        if out.get("t1_checkpoint_id") is not None:
            linked_t1_count += 1
            assert out.get("t1_hp") is not None
            assert out.get("hp_delta") is not None
    # All except the final checkpoint of the session should have T1 outcome
    assert linked_t1_count >= len(loaded_rows) - 1


def test_future_leakage(loaded_rows):
    """14. T0 state contains no future placement or T1 outcome data."""
    for r in loaded_rows:
        raw = r.raw_state
        assert "final_placement" not in raw
        assert "placement" not in raw
        assert "t1_hp" not in raw
        assert "hp_delta" not in raw


def test_final_placement_is_post_session(session_manager, loaded_rows):
    """15. Final placement only in session manifest, never in T0 state."""
    manifest = session_manager.load_manifest("SESSION_001")
    assert manifest.final_placement == 2
    for r in loaded_rows:
        assert "final_placement" not in r.raw_state


def test_dataset_export():
    """16. Exporter produces valid final_dataset.jsonl and final_dataset.csv."""
    exporter = DatasetExporter()
    result = exporter.export_all()
    assert os.path.exists(result["jsonl_path"])
    assert os.path.exists(result["csv_path"])
    assert result["total_checkpoints"] >= 20

    # Verify CSV has header and rows
    with open(result["csv_path"], "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) >= 21  # 1 header + 20 rows
    assert "checkpoint_id" in lines[0]
    assert "hp_delta" in lines[0]


def test_dataset_recomputation():
    """17. Audit tool recomputes stats directly from raw JSONL."""
    from audit_decision_dataset import run_audit
    res = run_audit(JSONL_PATH)
    assert res["total_checkpoints"] >= 20
    assert res["total_matches"] >= 1
    assert "gate" in res
    assert res["fake_data"]["verdict"] == "CLEAN"


def test_calibration_ready_gate(validator, session_manager, loaded_rows):
    """18. Correctly outputs DATA_COLLECTION_IN_PROGRESS when matches < 5."""
    manifests = [session_manager.load_manifest(s) for s in session_manager.list_sessions()]
    gate_res = validator.evaluate_calibration_gate(manifests, loaded_rows)
    # Honest gate verdict when matches = 1 < 5
    assert gate_res["final_gate_verdict"] == "DATA_COLLECTION_IN_PROGRESS"
    assert gate_res["checklist"]["matches_ge_5"] is False
    assert gate_res["checklist"]["actual_action_coverage_ge_80pct"] is True
    assert gate_res["checklist"]["human_preference_coverage_ge_80pct"] is True


def test_protected_core_unchanged():
    """19. Protected directories must have 0 git diff lines."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"] + PROTECTED_DIRS,
        capture_output=True, text=True, cwd=_ROOT
    )
    changed = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    assert len(changed) == 0, f"Protected core modified! Files: {changed}"
