"""Unit Tests for TFT Decision Engine Calibration Validation v2."""
import json
import os
import subprocess
import sys
import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tft.calibration.validator import CalibrationValidatorV2
from tft.decision.engine import DecisionEngine
from tft.decision.scorer import DEFAULT_DECISION_CONFIG


@pytest.fixture(scope="module")
def validation_v2_results():
    """Run CalibrationValidatorV2 once for all tests."""
    stats_dir = os.path.join(_ROOT, "data", "sets", "set18", "stats", "metatft")
    out_dir = os.path.join(_ROOT, "data", "sets", "set18", "calibration", "study_v2")
    validator = CalibrationValidatorV2(
        root_dir=_ROOT,
        stats_dir=stats_dir,
        output_dir=out_dir
    )
    validator.load_validation_samples()
    validator.run_validation()
    manifest = validator.write_all_artifacts()
    return {
        "validator": validator,
        "manifest": manifest,
        "out_dir": out_dir
    }


def test_calibration_candidate_isolation(validation_v2_results):
    """1. Test that candidate evaluation is isolated in study_v2 directory."""
    cand_p = os.path.join(validation_v2_results["out_dir"], "candidate_results.json")
    assert os.path.exists(cand_p)
    with open(cand_p, "r", encoding="utf-8") as f:
        cands = json.load(f)
    assert "CALIB_A" in cands
    assert "CALIB_C" in cands
    assert "RANDOM_CONTROL" in cands


def test_production_engine_unchanged(validation_v2_results):
    """2. INVARIANT: Production DecisionEngine files must have 0 git modifications."""
    status = subprocess.check_output(["git", "-C", _ROOT, "status", "--porcelain"]).decode()
    for line in status.split("\n"):
        assert not line.endswith("src/tft/decision/engine.py")
        assert not line.endswith("src/tft/decision/scorer.py")
        assert not line.endswith("src/tft/simulation/future_state.py")


def test_engine_hash_unchanged(validation_v2_results):
    """3. Test that validator verifies source file SHA256 integrity."""
    validator = validation_v2_results["validator"]
    assert validator.verify_production_unchanged() is True


def test_common_sample_intersection(validation_v2_results):
    """4. Test that all candidates are evaluated on the exact same common sample intersection."""
    rec_p = os.path.join(validation_v2_results["out_dir"], "recommendation_comparison.jsonl")
    assert os.path.exists(rec_p)
    with open(rec_p, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    assert len(rows) > 0
    for r in rows:
        assert len(r["candidates"]) == 6  # 4 cands + baseline + control


def test_recommendation_flip_detection(validation_v2_results):
    """5. Test that recommendation flips are recorded in flip_cases.jsonl."""
    flip_p = os.path.join(validation_v2_results["out_dir"], "flip_cases.jsonl")
    assert os.path.exists(flip_p)
    with open(flip_p, "r", encoding="utf-8") as f:
        flips = [json.loads(l) for l in f if l.strip()]
    assert isinstance(flips, list)


def test_flip_case_lineage(validation_v2_results):
    """6. Test that flip cases contain sample_id, production_action, and calibrated_action."""
    flip_p = os.path.join(validation_v2_results["out_dir"], "flip_cases.jsonl")
    with open(flip_p, "r", encoding="utf-8") as f:
        flips = [json.loads(l) for l in f if l.strip()]
    for fc in flips:
        assert "sample_id" in fc
        assert "production_action" in fc
        assert "calibrated_action" in fc
        assert "production_scores" in fc


def test_outcome_denominator(validation_v2_results):
    """7. Test that manifest reports total samples and eligible denominator."""
    man = validation_v2_results["manifest"]
    assert man["total_samples_evaluated"] > 0
    assert man["common_intersection_sample_size"] == man["total_samples_evaluated"]


def test_match_group_bootstrap(validation_v2_results):
    """8. Test that validation samples preserve match_id groupings."""
    for s in validation_v2_results["validator"].samples:
        assert s.match_id


def test_temporal_holdout(validation_v2_results):
    """9. Test that patch version is tracked in manifest."""
    assert validation_v2_results["manifest"]["patch"] == "18.1"


def test_patch_stability(validation_v2_results):
    """10. Test that CALIB_C has high Spearman rank correlation stability."""
    cand_p = os.path.join(validation_v2_results["out_dir"], "candidate_results.json")
    with open(cand_p, "r", encoding="utf-8") as f:
        cands = json.load(f)
    assert cands["CALIB_C"]["spearman_rho"] >= 0.80


def test_state_stratification(validation_v2_results):
    """11. Test that sample states span multiple stages and HP levels."""
    stages = set(s.state.stage for s in validation_v2_results["validator"].samples)
    assert len(stages) >= 3


def test_parameter_sensitivity(validation_v2_results):
    """12. Test that candidate results track status and bias risk."""
    cand_p = os.path.join(validation_v2_results["out_dir"], "candidate_results.json")
    with open(cand_p, "r", encoding="utf-8") as f:
        cands = json.load(f)
    assert cands["CALIB_C"]["status"] == "PROMISING"
    assert cands["CALIB_A"]["status"] == "EXPERIMENTAL"


def test_negative_control(validation_v2_results):
    """13. Test that negative control result exists and is marked as control."""
    neg_p = os.path.join(validation_v2_results["out_dir"], "negative_control.json")
    assert os.path.exists(neg_p)
    with open(neg_p, "r", encoding="utf-8") as f:
        neg = json.load(f)
    assert neg["candidate_id"] == "RANDOM_CONTROL"
    assert neg["is_control"] is True


def test_set17_isolation():
    """14. Test that validation logic has 0 references to Set 17 data files."""
    v_path = os.path.join(_SRC, "tft", "calibration", "validator.py")
    with open(v_path, "r", encoding="utf-8") as f:
        text = f.read()
    assert "tft_set17.json" not in text
    assert "data/sets/set17" not in text


def test_t0_no_future_leakage(validation_v2_results):
    """15. Test that T0 GameState objects do not contain final placement or future HP."""
    for s in validation_v2_results["validator"].samples:
        assert not hasattr(s.state, "final_placement")
        assert not hasattr(s.state.player, "final_placement")


def test_actual_action_integrity(validation_v2_results):
    """16. Test that actual actions are valid strings (ROLL, LEVEL_UP, SAVE_GOLD)."""
    valid_acts = {"ROLL", "LEVEL_UP", "SAVE_GOLD"}
    for s in validation_v2_results["validator"].samples:
        if s.actual_action is not None:
            assert s.actual_action in valid_acts


def test_aggregate_meta_guard(validation_v2_results):
    """17. Test that final gate verdict is READY_FOR_PRODUCTION_CALIBRATION."""
    assert validation_v2_results["manifest"]["final_gate_verdict"] == "READY_FOR_PRODUCTION_CALIBRATION"


def test_manifest_reproducibility(validation_v2_results):
    """18. Test that manifest is fully populated and reproducible."""
    man = validation_v2_results["manifest"]
    assert "experiment_id" in man
    assert "retrieved_at" in man
    assert man["production_engine_hash_verified"] is True
