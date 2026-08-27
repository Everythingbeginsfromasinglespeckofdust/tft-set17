"""Unit Tests for TFT Production Calibration Integration v1."""
import hashlib
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

from tft.calibration.integration.models import (
    CalibrationConfig,
    CalibrationMode,
    CalibrationAppliedStatus,
    compute_deterministic_state_hash
)
from tft.calibration.integration.adapter import DecisionCalibrationAdapter
from tft.calibration.integration.runner import CalibrationIntegrationRunner
from tft.decision.engine import DecisionEngine
from tft.decision.scorer import DEFAULT_DECISION_CONFIG
from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit


@pytest.fixture(scope="module")
def integration_benchmark_results():
    """Run CalibrationIntegrationRunner once for testing."""
    out_dir = os.path.join(_ROOT, "data", "sets", "set18", "calibration", "production_v1")
    runner = CalibrationIntegrationRunner(
        root_dir=_ROOT,
        output_dir=out_dir
    )
    metrics = runner.run_multi_mode_replay()
    manifest = runner.write_all_artifacts(metrics)
    return {
        "runner": runner,
        "metrics": metrics,
        "manifest": manifest,
        "out_dir": out_dir
    }


def test_calibration_disabled_by_default():
    """1. Test that default configuration has enabled=False and mode=OFF."""
    cfg = CalibrationConfig()
    assert cfg.enabled is False
    assert cfg.mode == CalibrationMode.OFF


def test_off_mode_preserves_existing_decision():
    """2. Test that OFF mode produces identical result to direct DecisionEngine decide()."""
    engine = DecisionEngine(config=DEFAULT_DECISION_CONFIG)
    adapter = DecisionCalibrationAdapter(engine=engine, config=CalibrationConfig(mode=CalibrationMode.OFF))

    st = GameState(stage=4, round=5, stage_round="4-5", player=PlayerState(gold=48, level=7, xp=12, hp=49), board_units=[Unit(champion="Akali", cost=1, star_level=2)], bench_units=[])
    direct = engine.decide(st)
    adapted = adapter.decide(st)

    assert adapted.action == direct.recommended_action.action_type.value
    assert adapted.calibration_applied is False
    assert adapted.applied_status == "CALIBRATION_SKIPPED"


def test_shadow_mode_never_changes_decision():
    """3. Test that SHADOW mode returns the Base action to caller."""
    adapter = DecisionCalibrationAdapter(config=CalibrationConfig(mode=CalibrationMode.SHADOW))
    st = GameState(stage=4, round=5, stage_round="4-5", player=PlayerState(gold=48, level=7, xp=12, hp=49), board_units=[Unit(champion="Akali", cost=1, star_level=2)], bench_units=[])
    res = adapter.decide(st)

    assert res.action == res.base_action
    assert res.calibration_applied is False


def test_on_mode_applies_calibration():
    """4. Test that ON mode applies CALIB_C adjustment when eligible."""
    adapter = DecisionCalibrationAdapter(config=CalibrationConfig(mode=CalibrationMode.ON))
    st = GameState(stage=4, round=5, stage_round="4-5", player=PlayerState(gold=48, level=7, xp=12, hp=49), board_units=[Unit(champion="Akali", cost=1, star_level=2)], bench_units=[])
    res = adapter.decide(st)

    assert res.is_flip is True
    assert res.action == "ROLL"
    assert res.base_action == "SAVE_GOLD"
    assert res.calibration_applied is True
    assert res.applied_status == "CALIBRATION_APPLIED"


def test_on_mode_reproduces_gate_results(integration_benchmark_results):
    """5. Test that ON mode reproduces 100% of Gate v1 flip statistics (14 flips / 120 samples)."""
    m = integration_benchmark_results["metrics"]
    assert m["total_samples"] == 120
    assert m["on_mode_flips"] == 14
    assert m["gate_reproduction_100_percent"] is True


def test_calibration_source_hash(integration_benchmark_results):
    """6. Test that calibration source SHA256 is tracked and valid."""
    assert len(integration_benchmark_results["manifest"]["calibration_source_sha256"]) == 64


def test_calibration_version_lock(integration_benchmark_results):
    """7. Test that candidate version is locked to CALIB_C_PROD_V1."""
    assert integration_benchmark_results["manifest"]["candidate_version"] == "CALIB_C_PROD_V1"


def test_calibration_failure_fallback():
    """8. Test automatic rollback to base recommendation if source is missing or invalid."""
    bad_cfg = CalibrationConfig(mode=CalibrationMode.ON, percentiles_path="nonexistent/path/percentiles.json")
    adapter = DecisionCalibrationAdapter(config=bad_cfg)
    st = GameState(stage=4, round=5, stage_round="4-5", player=PlayerState(gold=48, level=7, xp=12, hp=49), board_units=[Unit(champion="Akali", cost=1, star_level=2)], bench_units=[])
    res = adapter.decide(st)

    assert res.action == res.base_action
    assert res.applied_status == "CALIBRATION_FALLBACK"


def test_invalid_state_fallback():
    """9. Test that low vision confidence safely skips calibration."""
    adapter = DecisionCalibrationAdapter(config=CalibrationConfig(mode=CalibrationMode.ON, min_vision_confidence=0.85))
    st = GameState(stage=4, round=5, stage_round="4-5", player=PlayerState(gold=48, level=7, xp=12, hp=49), board_units=[Unit(champion="Akali", cost=1, star_level=2)], bench_units=[])
    res = adapter.decide(st, vision_confidence=0.70)

    assert res.action == res.base_action
    assert res.applied_status == "CALIBRATION_SKIPPED"


def test_calibration_determinism():
    """10. Test that identical states produce identical calibrated decisions."""
    adapter = DecisionCalibrationAdapter(config=CalibrationConfig(mode=CalibrationMode.ON))
    st = GameState(stage=4, round=5, stage_round="4-5", player=PlayerState(gold=48, level=7, xp=12, hp=49), board_units=[Unit(champion="Akali", cost=1, star_level=2)], bench_units=[])
    res1 = adapter.decide(st)
    res2 = adapter.decide(st)

    assert res1.action == res2.action
    assert res1.scores == res2.scores
    assert res1.state_hash == res2.state_hash


def test_recommendation_flip_logging(integration_benchmark_results):
    """11. Test that applied flips are recorded into applied_flips.jsonl."""
    flips_p = os.path.join(integration_benchmark_results["out_dir"], "flips", "applied_flips.jsonl")
    assert os.path.exists(flips_p)
    with open(flips_p, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    assert len(lines) == 14


def test_flip_direction(integration_benchmark_results):
    """12. Test recommendation matrix tracks SAVE_GOLD->ROLL flips."""
    mat = integration_benchmark_results["metrics"]["recommendation_matrix"]
    assert mat["SAVE_GOLD->ROLL"] == 14


def test_production_equivalence(integration_benchmark_results):
    """13. INVARIANT: Production DecisionEngine files must have 0 git changes."""
    status = subprocess.check_output(["git", "-C", _ROOT, "status", "--porcelain"]).decode()
    for line in status.split("\n"):
        assert not line.endswith("src/tft/decision/engine.py")
        assert not line.endswith("src/tft/decision/scorer.py")
        assert not line.endswith("src/tft/simulation/future_state.py")


def test_state_hash():
    """14. Test deterministic state hash generation."""
    st = GameState(stage=3, round=1, stage_round="3-1", player=PlayerState(gold=20, level=6, xp=0, hp=75), board_units=[], bench_units=[])
    h = compute_deterministic_state_hash(st)
    assert len(h) == 64


def test_session_stability(integration_benchmark_results):
    """15. Test that manifest reports valid verdict PRODUCTION_CALIBRATION_READY."""
    assert integration_benchmark_results["manifest"]["final_gate_verdict"] == "PRODUCTION_CALIBRATION_READY"


def test_patch_stability(integration_benchmark_results):
    """16. Test patch version in manifest."""
    assert integration_benchmark_results["runner"].patch == "18.1"


def test_privacy_filter(integration_benchmark_results):
    """17. Test that logged records contain NO PUUID or PII."""
    on_p = os.path.join(integration_benchmark_results["out_dir"], "replay", "on.jsonl")
    with open(on_p, "r", encoding="utf-8") as f:
        text = f.read()
    assert "puuid" not in text.lower()
    assert "summoner" not in text.lower()


def test_config_validation():
    """18. Test config post-init auto-normalization."""
    cfg = CalibrationConfig(enabled=True, mode=CalibrationMode.OFF)
    assert cfg.mode == CalibrationMode.ON


def test_kill_switch():
    """19. Test that mode=OFF acts as a full kill-switch."""
    adapter = DecisionCalibrationAdapter(config=CalibrationConfig(enabled=False, mode=CalibrationMode.OFF))
    st = GameState(stage=4, round=5, stage_round="4-5", player=PlayerState(gold=48, level=7, xp=12, hp=49), board_units=[Unit(champion="Akali", cost=1, star_level=2)], bench_units=[])
    res = adapter.decide(st)
    assert res.action == res.base_action
    assert res.calibration_applied is False


def test_performance_budget(integration_benchmark_results):
    """20. Test that additional P95 latency is strictly less than 1.0ms."""
    p95 = integration_benchmark_results["metrics"]["p95_latency_ms"]
    assert p95 < 1.0
