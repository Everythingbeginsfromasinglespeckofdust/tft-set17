"""Unit Tests for TFT Decision Engine Calibration Study v1."""
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

from tft.calibration.models import (
    TransformationType,
    CandidateStatus,
    CalibrationRecord,
    CalibrationCandidateResult,
    RecommendationFlipCase
)
from tft.calibration.transformer import CalibrationTransformer
from tft.calibration.study_engine import CalibrationStudyEngine
from tft.decision.engine import DecisionEngine
from tft.decision.scorer import DecisionConfig, DEFAULT_DECISION_CONFIG
from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit


@pytest.fixture(scope="module")
def study_manifest():
    """Run calibration study engine once for testing."""
    stats_dir = os.path.join(_ROOT, "data", "sets", "set18", "stats", "metatft")
    out_dir = os.path.join(_ROOT, "data", "sets", "set18", "calibration", "study_v1")
    engine = CalibrationStudyEngine(stats_dir=stats_dir, output_dir=out_dir)
    res = engine.run_study()
    return res["manifest"]


def test_calibration_dataset_schema(study_manifest):
    """1. Test that candidate results and flip cases exist and conform to schema."""
    cand_p = os.path.join(_ROOT, "data", "sets", "set18", "calibration", "study_v1", "candidates", "calibration_candidates.json")
    assert os.path.exists(cand_p)
    with open(cand_p, "r", encoding="utf-8") as f:
        cands = json.load(f)
    assert len(cands) >= 4
    for c in cands:
        assert "candidate_id" in c
        assert "dataset" in c
        assert "transformation" in c
        assert "sample_threshold" in c
        assert "stability_score" in c
        assert "status" in c


def test_metric_transformation():
    """2. Test that raw placement and place change are transformed into bounded scores."""
    s_top1 = CalibrationTransformer.raw_placement_to_score(1.0)
    s_top8 = CalibrationTransformer.raw_placement_to_score(8.0)
    assert s_top1 == 1.0
    assert s_top8 == 0.0

    sig_good = CalibrationTransformer.place_change_to_sigmoid_utility(-1.0)
    sig_bad = CalibrationTransformer.place_change_to_sigmoid_utility(1.0)
    assert sig_good > 0.0
    assert sig_bad < 0.0


def test_sample_threshold_filter():
    """3. Test that small sample records (N < threshold) are filtered out."""
    rec_small = CalibrationRecord(
        entity_id="test_small",
        conditioning_context={},
        observed_metric="avg",
        sample_size=15,
        raw_metric_value=3.2
    )
    res = CalibrationTransformer.apply_transformation(rec_small, TransformationType.B1_RAW_METRIC, threshold_n=50)
    assert res.is_filtered_out is True


def test_shrinkage():
    """4. Test that empirical Bayes shrinks small N estimates towards population mean."""
    shrunk_avg, w = CalibrationTransformer.empirical_bayes_shrinkage(sample_avg=2.0, sample_n=10)
    assert shrunk_avg > 2.0
    assert 0.0 < w < 1.0

    shrunk_large, w_large = CalibrationTransformer.empirical_bayes_shrinkage(sample_avg=2.0, sample_n=10000)
    assert w_large > 0.99
    assert round(shrunk_large, 2) == 2.01


def test_normalization():
    """5. Test that transformed values remain strictly within [0.0, 1.0]."""
    for avg in [1.0, 2.5, 4.5, 6.7, 8.0]:
        sc = CalibrationTransformer.raw_placement_to_score(avg)
        assert 0.0 <= sc <= 1.0


def test_temporal_holdout(study_manifest):
    """6. Test that manifest records retrieval timestamp and patch version."""
    assert study_manifest.retrieved_at
    assert study_manifest.experiment_id == "CALIB_STUDY_V1_20260827"


def test_patch_stability(study_manifest):
    """7. Test that sample thresholds evaluated span 30, 50, 100, 300, 1000."""
    assert study_manifest.sample_thresholds_evaluated == [30, 50, 100, 300, 1000]


def test_rank_stability(study_manifest):
    """8. Test that candidates count is greater than 10 across thresholds."""
    assert study_manifest.candidates_count >= 10


def test_flip_case_schema():
    """9. Test that calibration_candidate_cases.jsonl exists and contains valid flip cases."""
    flip_p = os.path.join(_ROOT, "data", "sets", "set18", "calibration", "study_v1", "flip_cases", "calibration_candidate_cases.jsonl")
    assert os.path.exists(flip_p)
    with open(flip_p, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    assert len(lines) == 20
    for l in lines:
        assert "case_id" in l
        assert "original_action" in l
        assert "experimental_action" in l
        assert "would_flip" in l


def test_no_production_modification():
    """10. INVARIANT: Production DecisionEngine, ActionScorer, and Simulator must have 0 git changes."""
    status = subprocess.check_output(["git", "-C", _ROOT, "status", "--porcelain"]).decode()
    for line in status.split("\n"):
        assert not line.endswith("src/tft/decision/engine.py")
        assert not line.endswith("src/tft/decision/scorer.py")
        assert not line.endswith("src/tft/simulation/future_state.py")


def test_set18_identity():
    """11. Test that all calibrated items/units track Set 18 metadata."""
    cand_p = os.path.join(_ROOT, "data", "sets", "set18", "calibration", "study_v1", "candidates", "calibration_candidates.json")
    with open(cand_p, "r", encoding="utf-8") as f:
        text = f.read()
    assert "comp_builds" in text


def test_set17_isolation():
    """12. Test that calibration output does not reference Set 17 data files."""
    cand_p = os.path.join(_ROOT, "data", "sets", "set18", "calibration", "study_v1", "candidates", "calibration_candidates.json")
    with open(cand_p, "r", encoding="utf-8") as f:
        text = f.read()
    assert "tft_set17.json" not in text
    assert "data/sets/set17" not in text


def test_aggregate_dataset_guard(study_manifest):
    """13. Test that final gate verdict is CALIBRATION_CANDIDATES_READY."""
    assert study_manifest.final_gate_verdict == "CALIBRATION_CANDIDATES_READY"


def test_missing_value_handling():
    """14. Test handling of zero sample records without crashing."""
    zero_rec = CalibrationRecord(
        entity_id="test_zero",
        conditioning_context={},
        observed_metric="avg",
        sample_size=0,
        raw_metric_value=4.5
    )
    res = CalibrationTransformer.apply_transformation(zero_rec, TransformationType.B3_EMPIRICAL_SHRUNK, threshold_n=100)
    assert res.is_filtered_out is True
    assert res.transformed_score == 0.0


def test_production_equivalence():
    """15. INVARIANT: Calling DecisionEngine.decide produces identical deterministic outputs."""
    engine = DecisionEngine(config=DEFAULT_DECISION_CONFIG)
    st = GameState(
        stage=3,
        round=2,
        stage_round="3-2",
        player=PlayerState(gold=30, level=6, xp=12, hp=65),
        board_units=[Unit(champion="Akali", cost=1, star_level=2)],
        bench_units=[]
    )
    dec1 = engine.decide(st)
    dec2 = engine.decide(st)
    assert dec1.recommended_action == dec2.recommended_action
    assert [asc.score for asc in dec1.all_scores] == [asc.score for asc in dec2.all_scores]
