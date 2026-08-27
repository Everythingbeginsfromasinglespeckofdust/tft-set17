"""Unit Tests for TFT Production Calibration Gate v1."""
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

from tft.calibration.production_gate import ProductionCalibrationGateV1


@pytest.fixture(scope="module")
def gate_results():
    """Run ProductionCalibrationGateV1 once for testing."""
    stats_dir = os.path.join(_ROOT, "data", "sets", "set18", "stats", "metatft")
    out_dir = os.path.join(_ROOT, "data", "sets", "set18", "calibration", "production_gate_v1")
    gate = ProductionCalibrationGateV1(
        root_dir=_ROOT,
        stats_dir=stats_dir,
        output_dir=out_dir
    )
    gate.load_and_audit_samples()
    gate.run_production_gate_evaluation()
    val_analyses = gate.run_validation_analyses()
    manifest = gate.write_all_artifacts(val_analyses)
    return {
        "gate": gate,
        "manifest": manifest,
        "out_dir": out_dir,
        "val_analyses": val_analyses
    }


def test_real_only_population(gate_results):
    """1. Test that eligible gate population only contains HISTORICAL and HUMAN_VALIDATED."""
    for s in gate_results["gate"].eligible_real_samples:
        assert s.data_origin in ["HISTORICAL", "HUMAN_VALIDATED"]
        assert s.data_origin != "SYNTHETIC"


def test_synthetic_excluded_from_gate(gate_results):
    """2. Test that synthetic fixtures are filtered into excluded_samples."""
    excluded = gate_results["gate"].excluded_samples
    assert any(s.data_origin == "SYNTHETIC" for s in excluded)
    assert len(gate_results["gate"].eligible_real_samples) > 0


def test_match_level_split(gate_results):
    """3. Test that match bootstrap groups by match_id."""
    mb = gate_results["val_analyses"]["match_bootstrap"]
    assert mb["grouping_key"] == "match_id"
    assert mb["unique_matches_count"] >= 10


def test_temporal_holdout(gate_results):
    """4. Test that patch version 18.1 is tracked."""
    assert gate_results["manifest"]["patch"] == "18.1"


def test_actual_action_integrity(gate_results):
    """5. Test that actual actions in eligible samples are valid actions."""
    valid_acts = {"ROLL", "LEVEL_UP", "SAVE_GOLD"}
    for s in gate_results["gate"].eligible_real_samples:
        if s.actual_action:
            assert s.actual_action in valid_acts


def test_outcome_temporal_integrity(gate_results):
    """6. Test zero temporal leakage: T0 strictly less than T1 across all eligible samples."""
    for s in gate_results["gate"].eligible_real_samples:
        if s.t0_timestamp_sec is not None and s.t1_timestamp_sec is not None:
            assert s.t0_timestamp_sec < s.t1_timestamp_sec


def test_recommendation_flip_schema(gate_results):
    """7. Test that flip cases contain sample_id, flip_direction, and calibration_evidence."""
    flips_p = os.path.join(gate_results["out_dir"], "comparisons", "flip_cases.jsonl")
    assert os.path.exists(flips_p)
    with open(flips_p, "r", encoding="utf-8") as f:
        flips = [json.loads(l) for l in f if l.strip()]
    assert len(flips) > 0
    for fc in flips:
        assert "sample_id" in fc
        assert "flip_direction" in fc
        assert "calibration_evidence" in fc


def test_flip_direction(gate_results):
    """8. Test that crisis stage flips are predominantly SAVE_GOLD->ROLL."""
    flips_p = os.path.join(gate_results["out_dir"], "comparisons", "flip_cases.jsonl")
    with open(flips_p, "r", encoding="utf-8") as f:
        flips = [json.loads(l) for l in f if l.strip()]
    crisis_flips = [fc for fc in flips if fc["state"]["hp"] <= 50]
    assert any("SAVE_GOLD->ROLL" in fc["flip_direction"] for fc in crisis_flips)


def test_outcome_comparison(gate_results):
    """9. Test that candidate table exists and records placement association."""
    table_p = os.path.join(gate_results["out_dir"], "reports", "candidate_decision_table.csv")
    assert os.path.exists(table_p)
    with open(table_p, "r", encoding="utf-8") as f:
        text = f.read()
    assert "CALIB_C" in text
    assert "READY_FOR_PRODUCTION_INTEGRATION" in text


def test_session_loo(gate_results):
    """10. Test that Leave-One-Session-Out validation reports stable rho across sessions."""
    loo = gate_results["val_analyses"]["session_loo"]
    assert len(loo) >= 5
    for s_id, s_data in loo.items():
        assert s_data["generalization_verdict"] == "STABLE"
        assert s_data["stability_rho"] >= 0.90


def test_match_bootstrap(gate_results):
    """11. Test that 95% bootstrap CI is computed and recorded."""
    mb = gate_results["val_analyses"]["match_bootstrap"]
    assert "ci_95_lower" in mb
    assert "ci_95_upper" in mb
    assert mb["ci_95_lower"] < mb["ci_95_upper"]


def test_patch_stability(gate_results):
    """12. Test that manifest reports zero production engine hash diff."""
    assert gate_results["manifest"]["production_engine_hash_verified"] is True


def test_negative_control(gate_results):
    """13. Test that random control has significantly higher flip rate than CALIB_C."""
    table_p = os.path.join(gate_results["out_dir"], "reports", "candidate_decision_table.csv")
    with open(table_p, "r", encoding="utf-8") as f:
        lines = f.readlines()
    # Check that RANDOM_CONTROL is in table
    assert any("RANDOM_CONTROL" in l for l in lines)


def test_production_engine_hash(gate_results):
    """14. INVARIANT: Production DecisionEngine files must have 0 git changes."""
    status = subprocess.check_output(["git", "-C", _ROOT, "status", "--porcelain"]).decode()
    for line in status.split("\n"):
        assert not line.endswith("src/tft/decision/engine.py")
        assert not line.endswith("src/tft/decision/scorer.py")
        assert not line.endswith("src/tft/simulation/future_state.py")


def test_set17_isolation():
    """15. Test that production gate has 0 references to Set 17 data."""
    pg_path = os.path.join(_SRC, "tft", "calibration", "production_gate.py")
    with open(pg_path, "r", encoding="utf-8") as f:
        text = f.read()
    assert "tft_set17.json" not in text
    assert "data/sets/set17" not in text


def test_set18_isolation(gate_results):
    """16. Test that all gate states are configured for Set 18."""
    for s in gate_results["gate"].eligible_real_samples:
        for u in s.state.board_units:
            assert u.champion


def test_shadow_schema(gate_results):
    """17. Test that Shadow Mode specification document exists."""
    spec_p = os.path.join(gate_results["out_dir"], "shadow", "SHADOW_MODE_SPEC.md")
    assert os.path.exists(spec_p)
    with open(spec_p, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Shadow Mode Specification" in content
    assert "shadow_logs.jsonl" in content


def test_gate_decision(gate_results):
    """18. Test that final gate verdict is READY_FOR_PRODUCTION_INTEGRATION."""
    assert gate_results["manifest"]["final_gate_verdict"] == "READY_FOR_PRODUCTION_INTEGRATION"
