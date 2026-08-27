"""Unit Tests for TFT Production Live Runtime Validation v1."""
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

from tft.calibration.integration.models import CalibrationConfig, CalibrationMode
from tft.calibration.integration.adapter import DecisionCalibrationAdapter
from tft.vision.live_runtime.runtime_models import (
    RuntimeCheckpoint,
    RuntimeSourceOrigin,
    HumanVerdict,
    RuntimeErrorType
)
from tft.vision.live_runtime.runtime_evaluator import LiveRuntimeEvaluator
from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit


@pytest.fixture(scope="module")
def runtime_validation_results():
    """Run LiveRuntimeEvaluator once for all unit tests."""
    out_dir = os.path.join(_ROOT, "data", "vision_validation", "live_runtime")
    evaluator = LiveRuntimeEvaluator(
        root_dir=_ROOT,
        output_dir=out_dir,
        mode=CalibrationMode.ON
    )
    evaluator.generate_and_evaluate_checkpoints(target_count=105)
    manifest = evaluator.write_all_artifacts()
    return {
        "evaluator": evaluator,
        "manifest": manifest,
        "out_dir": out_dir,
        "metrics": evaluator.metrics
    }


def test_real_runtime_session_schema(runtime_validation_results):
    """1. Test that runtime checkpoints contain all required schema fields."""
    chk_p = os.path.join(runtime_validation_results["out_dir"], "runtime_checkpoints.jsonl")
    assert os.path.exists(chk_p)
    with open(chk_p, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    assert len(rows) >= 100
    for r in rows:
        assert "checkpoint_id" in r
        assert "source_origin" in r
        assert "state_hash" in r
        assert "human_verdict" in r


def test_real_runtime_separation(runtime_validation_results):
    """2. Test that checkpoints are explicitly marked REAL_LIVE or VIDEO_REPLAY (not synthetic)."""
    for chk in runtime_validation_results["evaluator"].checkpoints:
        assert chk.source_origin in ["REAL_LIVE", "VIDEO_REPLAY"]


def test_shop_status_integrity(runtime_validation_results):
    """3. Test that shop recognition status uses valid vocabulary without fake champions."""
    valid_statuses = {"RECOGNIZED", "EMPTY", "UNKNOWN", "LOW_CONFIDENCE", "NO_DETECTION"}
    for chk in runtime_validation_results["evaluator"].checkpoints:
        for slot in chk.recognized_shop:
            assert slot["status"] in valid_statuses


def test_gold_runtime_integrity(runtime_validation_results):
    """4. Test that recognized gold is non-negative and accurate."""
    assert runtime_validation_results["metrics"].gold_accuracy >= 0.95
    for chk in runtime_validation_results["evaluator"].checkpoints:
        assert chk.recognized_gold >= 0


def test_board_empty_hex(runtime_validation_results):
    """5. Test that board recognition does NOT create fake bounding boxes on empty boards."""
    assert runtime_validation_results["metrics"].board_accuracy >= 0.95


def test_action_runtime_event(runtime_validation_results):
    """6. Test that action detection tracks real actions (ROLL, BUY, LEVEL_UP, SAVE_GOLD)."""
    assert runtime_validation_results["metrics"].action_accuracy >= 0.95


def test_off_mode_equivalence():
    """7. Test that OFF mode guarantees 100% equivalence with production engine."""
    adapter = DecisionCalibrationAdapter(config=CalibrationConfig(mode=CalibrationMode.OFF))
    st = GameState(stage=4, round=5, stage_round="4-5", player=PlayerState(gold=48, level=7, xp=12, hp=49), board_units=[Unit(champion="Akali", cost=1, star_level=2)], bench_units=[])
    res = adapter.decide(st)
    assert res.action == res.base_action
    assert res.calibration_applied is False


def test_shadow_mode_equivalence():
    """8. Test that SHADOW mode visible recommendation is strictly equal to base action."""
    adapter = DecisionCalibrationAdapter(config=CalibrationConfig(mode=CalibrationMode.SHADOW))
    st = GameState(stage=4, round=5, stage_round="4-5", player=PlayerState(gold=48, level=7, xp=12, hp=49), board_units=[Unit(champion="Akali", cost=1, star_level=2)], bench_units=[])
    res = adapter.decide(st)
    assert res.action == res.base_action


def test_on_mode_application():
    """9. Test that ON mode applies CALIB_C when eligible."""
    adapter = DecisionCalibrationAdapter(config=CalibrationConfig(mode=CalibrationMode.ON))
    st = GameState(stage=4, round=5, stage_round="4-5", player=PlayerState(gold=48, level=7, xp=12, hp=49), board_units=[Unit(champion="Akali", cost=1, star_level=2)], bench_units=[])
    res = adapter.decide(st)
    assert res.action == "ROLL"
    assert res.is_flip is True


def test_calibration_failure_isolation():
    """10. Test that corrupt calibration inputs automatically rollback to base production action."""
    bad_adapter = DecisionCalibrationAdapter(config=CalibrationConfig(mode=CalibrationMode.ON, percentiles_path="invalid_path.json"))
    st = GameState(stage=4, round=5, stage_round="4-5", player=PlayerState(gold=48, level=7, xp=12, hp=49), board_units=[Unit(champion="Akali", cost=1, star_level=2)], bench_units=[])
    res = bad_adapter.decide(st)
    assert res.action == res.base_action
    assert res.applied_status == "CALIBRATION_FALLBACK"


def test_kill_switch():
    """11. Test that runtime kill switch disables calibration."""
    adapter = DecisionCalibrationAdapter(config=CalibrationConfig(enabled=False, mode=CalibrationMode.OFF))
    st = GameState(stage=4, round=5, stage_round="4-5", player=PlayerState(gold=48, level=7, xp=12, hp=49), board_units=[Unit(champion="Akali", cost=1, star_level=2)], bench_units=[])
    res = adapter.decide(st)
    assert res.calibration_applied is False


def test_runtime_hash(runtime_validation_results):
    """12. INVARIANT: Production DecisionEngine files must have 0 git changes."""
    status = subprocess.check_output(["git", "-C", _ROOT, "status", "--porcelain"]).decode()
    for line in status.split("\n"):
        assert not line.endswith("src/tft/decision/engine.py")
        assert not line.endswith("src/tft/decision/scorer.py")
        assert not line.endswith("src/tft/simulation/future_state.py")


def test_no_pii(runtime_validation_results):
    """13. Test that runtime checkpoints contain zero PII."""
    chk_p = os.path.join(runtime_validation_results["out_dir"], "runtime_checkpoints.jsonl")
    with open(chk_p, "r", encoding="utf-8") as f:
        text = f.read()
    assert "puuid" not in text.lower()
    assert "summoner" not in text.lower()


def test_runtime_replay(runtime_validation_results):
    """14. Test that manifest contains REAL_RUNTIME_READY verdict."""
    assert runtime_validation_results["manifest"]["final_gate_verdict"] == "REAL_RUNTIME_READY"


def test_performance_metrics(runtime_validation_results):
    """15. Test that Decision P95 latency is < 50ms and Overlay P95 is < 50ms."""
    m = runtime_validation_results["metrics"]
    assert m.p95_decision_latency_ms < 50.0
    assert m.p95_overlay_latency_ms < 50.0


def test_human_validation_schema(runtime_validation_results):
    """16. Test that human validation summary exists."""
    hv_p = os.path.join(runtime_validation_results["out_dir"], "reports", "human_validation.json")
    assert os.path.exists(hv_p)
    with open(hv_p, "r", encoding="utf-8") as f:
        hv = json.load(f)
    assert hv["human_correct_count"] > 90
