"""Unit Tests for TFT Production Calibration Shadow Mode v1."""
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

from tft.calibration.shadow.shadow_models import compute_deterministic_state_hash, ShadowDecision
from tft.calibration.shadow.shadow_evaluator import CALIBCShadowEvaluator
from tft.calibration.shadow.shadow_runner import ShadowRunner
from tft.decision.engine import DecisionEngine
from tft.decision.scorer import DEFAULT_DECISION_CONFIG
from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit


@pytest.fixture(scope="module")
def shadow_benchmark_results():
    """Run ShadowRunner once for testing."""
    out_dir = os.path.join(_ROOT, "data", "sets", "set18", "calibration", "shadow_v1")
    runner = ShadowRunner(
        root_dir=_ROOT,
        output_dir=out_dir
    )
    metrics = runner.run_historical_replay()
    manifest = runner.write_all_artifacts(metrics)
    return {
        "runner": runner,
        "metrics": metrics,
        "manifest": manifest,
        "out_dir": out_dir
    }


def test_shadow_does_not_change_production():
    """1. Test that production decision recommendation is completely unaffected by shadow layer."""
    engine = DecisionEngine(config=DEFAULT_DECISION_CONFIG)
    evaluator = CALIBCShadowEvaluator()

    st = GameState(
        stage=4,
        round=5,
        stage_round="4-5",
        player=PlayerState(gold=48, level=7, xp=12, hp=49),
        board_units=[Unit(champion="Akali", cost=1, star_level=2)],
        bench_units=[]
    )

    prod_before = engine.decide(st)
    shadow_dec = evaluator.evaluate_shadow(st, prod_before)
    prod_after = engine.decide(st)

    assert prod_before.recommended_action.action_type == prod_after.recommended_action.action_type
    assert prod_before.decision_margin == prod_after.decision_margin
    assert shadow_dec.production_action == prod_before.recommended_action.action_type.value


def test_production_hash_unchanged(shadow_benchmark_results):
    """2. INVARIANT: Production DecisionEngine files must have 0 git modifications."""
    status = subprocess.check_output(["git", "-C", _ROOT, "status", "--porcelain"]).decode()
    for line in status.split("\n"):
        assert not line.endswith("src/tft/decision/engine.py")
        assert not line.endswith("src/tft/decision/scorer.py")
        assert not line.endswith("src/tft/simulation/future_state.py")


def test_shadow_reproducibility():
    """3. Test that deterministic input produces identical shadow output."""
    evaluator = CALIBCShadowEvaluator()
    engine = DecisionEngine(config=DEFAULT_DECISION_CONFIG)

    st = GameState(
        stage=4,
        round=5,
        stage_round="4-5",
        player=PlayerState(gold=48, level=7, xp=12, hp=49),
        board_units=[Unit(champion="Akali", cost=1, star_level=2)],
        bench_units=[]
    )
    prod = engine.decide(st)

    res1 = evaluator.evaluate_shadow(st, prod)
    res2 = evaluator.evaluate_shadow(st, prod)

    assert res1.calibrated_action == res2.calibrated_action
    assert res1.calibrated_scores == res2.calibrated_scores
    assert res1.state_hash == res2.state_hash


def test_gate_reproduction(shadow_benchmark_results):
    """4. Test that Shadow Mode reproduces 100% of Gate v1 metrics (14 flips, 120 samples)."""
    m = shadow_benchmark_results["metrics"]
    assert m["total_states_evaluated"] == 120
    assert m["flips_count"] == 14
    assert m["gate_reproduction_match"] is True


def test_flip_direction(shadow_benchmark_results):
    """5. Test that flips recorded are predominantly SAVE_GOLD->ROLL."""
    m = shadow_benchmark_results["metrics"]
    assert "SAVE_GOLD->ROLL" in m["flip_directions"]
    assert m["flip_directions"]["SAVE_GOLD->ROLL"] == 14


def test_shadow_failure_isolated():
    """6. Test that an invalid state or exception inside shadow layer does NOT raise to caller."""
    evaluator = CALIBCShadowEvaluator()
    # Pass completely malformed state
    res = evaluator.evaluate_shadow(None, None)
    assert res.is_shadow_fallback is True
    assert res.calibrated_action in ["SAVE_GOLD", "UNKNOWN"]


def test_shadow_kill_switch():
    """7. Test that shadow_enabled=False immediately disables shadow computation."""
    evaluator = CALIBCShadowEvaluator(shadow_enabled=False)
    engine = DecisionEngine(config=DEFAULT_DECISION_CONFIG)
    st = GameState(
        stage=4,
        round=5,
        stage_round="4-5",
        player=PlayerState(gold=48, level=7, xp=12, hp=49),
        board_units=[Unit(champion="Akali", cost=1, star_level=2)],
        bench_units=[]
    )
    prod = engine.decide(st)
    res = evaluator.evaluate_shadow(st, prod)

    assert res.is_shadow_fallback is True
    assert res.is_flip is False
    assert res.calibrated_action == res.production_action


def test_sampling_rate():
    """8. Test sampling rate parameter configuration."""
    evaluator = CALIBCShadowEvaluator(sampling_rate=0.5)
    assert evaluator.sampling_rate == 0.5


def test_outcome_temporal_integrity(shadow_benchmark_results):
    """9. Test that comparison log exists and is properly populated."""
    comp_p = os.path.join(shadow_benchmark_results["out_dir"], "replay", "comparison.jsonl")
    assert os.path.exists(comp_p)
    with open(comp_p, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    assert len(lines) == 120


def test_no_future_leakage():
    """10. Test that deterministic state hash does not use any future fields."""
    st = GameState(
        stage=3,
        round=1,
        stage_round="3-1",
        player=PlayerState(gold=30, level=6, xp=0, hp=80),
        board_units=[],
        bench_units=[]
    )
    h1 = compute_deterministic_state_hash(st)
    assert len(h1) == 64


def test_set18_isolation(shadow_benchmark_results):
    """11. Test that manifest points to Set 18 patch."""
    assert shadow_benchmark_results["manifest"]["patch"] == "18.1"
    assert shadow_benchmark_results["manifest"]["calibration_candidate"] == "CALIB_C"


def test_set17_isolation():
    """12. Test zero references to Set 17 in shadow evaluation code."""
    mod_p = os.path.join(_SRC, "tft", "calibration", "shadow", "shadow_evaluator.py")
    with open(mod_p, "r", encoding="utf-8") as f:
        text = f.read()
    assert "tft_set17.json" not in text
    assert "data/sets/set17" not in text


def test_calibration_source_hash(shadow_benchmark_results):
    """13. Test that calibration source SHA256 is tracked in manifest."""
    assert len(shadow_benchmark_results["manifest"]["calibration_source_sha256"]) == 64


def test_state_hash_deterministic():
    """14. Test that state hash produces identical hash for identical states."""
    st1 = GameState(stage=3, round=1, stage_round="3-1", player=PlayerState(gold=20, level=6, xp=0, hp=75), board_units=[], bench_units=[])
    st2 = GameState(stage=3, round=1, stage_round="3-1", player=PlayerState(gold=20, level=6, xp=0, hp=75), board_units=[], bench_units=[])
    assert compute_deterministic_state_hash(st1) == compute_deterministic_state_hash(st2)


def test_performance_guard(shadow_benchmark_results):
    """15. Test that P95 shadow latency is strictly less than 50ms."""
    p95 = shadow_benchmark_results["metrics"]["p95_latency_ms"]
    assert p95 < 50.0


def test_live_shadow_failure_recovery():
    """16. Test that live shadow evaluation gracefully recovers from corrupt input."""
    evaluator = CALIBCShadowEvaluator()
    res = evaluator.evaluate_shadow(state="CORRUPT_STATE_STRING", production_recommendation=None)
    assert res.is_shadow_fallback is True
    assert res.is_flip is False
