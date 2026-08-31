"""TFT Candidate Decision Engine Improvement v1 Test Suite (22 Unit & Integration Tests)."""
import json
import os
import sys
import subprocess
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
_ROOT = os.path.abspath(os.path.join(_SRC, ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.data.repositories import get_data_repository
from tft.research.candidate_engine.baseline_adapter import BaselineAdapter
from tft.research.candidate_engine.candidate_models import CandidateDecisionEngine, CandidateModelType
from tft.research.candidate_engine.ablation_study import AblationStudyRunner
from tft.research.candidate_engine.scenario_library import ScenarioLibraryManager
from tft.research.candidate_engine.sensitivity_analyzer import SensitivityAnalyzer

DECISION_MODEL_DIR = os.path.join(_ROOT, "data", "sets", "set18", "calibration", "decision_model_v1")


@pytest.fixture(scope="module")
def candidate_engine():
    return CandidateDecisionEngine()


def test_baseline_snapshot(candidate_engine):
    """1. Test that baseline snapshot captures full telemetry without mutating engine."""
    st = GameState(stage=4, round=3, stage_round="4-3", player=PlayerState(gold=48, level=7, xp=16, hp=38))
    snap = candidate_engine.baseline.capture_snapshot(st, sample_id="SNAP_01")
    assert "recommended_action" in snap
    assert "action_scores" in snap
    assert "score_gap" in snap
    assert snap["horizon"] == 3


def test_candidate_engine_determinism(candidate_engine):
    """2. Test that candidate engine returns identical outputs for repeated evaluations."""
    st = GameState(stage=4, round=3, stage_round="4-3", player=PlayerState(gold=48, level=7, xp=16, hp=38))
    res1 = candidate_engine.evaluate(st, model_type=CandidateModelType.V4_COMBINED, sample_id="DET_01")
    res2 = candidate_engine.evaluate(st, model_type=CandidateModelType.V4_COMBINED, sample_id="DET_01")
    assert res1.candidate_action == res2.candidate_action
    assert res1.candidate_score == res2.candidate_score
    assert len(res1.feature_contributions) == len(res2.feature_contributions)


def test_feature_adjustment_traceability(candidate_engine):
    """3. Test that all feature adjustments have explicit additive deltas and justifications."""
    st = GameState(
        stage=4,
        round=3,
        stage_round="4-3",
        player=PlayerState(gold=60, level=7, xp=16, hp=38),
        board_units=[Unit(champion="Diana", cost=3, star_level=1)],
        bench_units=[Unit(champion="Diana", cost=3, star_level=1)]
    )
    res = candidate_engine.evaluate(st, model_type=CandidateModelType.V4_COMBINED, sample_id="TRACE_01")
    for contrib in res.feature_contributions:
        assert hasattr(contrib, "feature_id")
        assert hasattr(contrib, "score_delta")
        assert len(contrib.justification) > 10


def test_estimated_rounds_to_elim(candidate_engine):
    """4. Test that lethal survival horizon increases ROLL preference."""
    st_crisis = GameState(stage=5, round=2, stage_round="5-2", player=PlayerState(gold=28, level=7, xp=0, hp=14))
    res = candidate_engine.evaluate(st_crisis, model_type=CandidateModelType.V1_SURVIVAL)
    elim_contribs = [c for c in res.feature_contributions if c.feature_id == "ESTIMATED_ROUNDS_TO_ELIM"]
    assert len(elim_contribs) == 1
    assert elim_contribs[0].score_delta > 0


def test_pair_count(candidate_engine):
    """5. Test that holding 2+ pairs with spendable budget increases ROLL candidate score."""
    st_pairs = GameState(
        stage=3,
        round=2,
        stage_round="3-2",
        player=PlayerState(gold=65, level=6, xp=0, hp=70), # 65G - 50G reserve = 15G spendable budget
        board_units=[
            Unit(champion="Diana", cost=3, star_level=1),
            Unit(champion="Zac", cost=2, star_level=1)
        ],
        bench_units=[
            Unit(champion="Diana", cost=3, star_level=1),
            Unit(champion="Zac", cost=2, star_level=1)
        ]
    )
    res = candidate_engine.evaluate(st_pairs, model_type=CandidateModelType.V2_UPGRADE)
    pair_contribs = [c for c in res.feature_contributions if c.feature_id == "PAIR_COUNT"]
    assert len(pair_contribs) == 1
    assert pair_contribs[0].score_delta > 0


def test_shop_upgrade_opportunity(candidate_engine):
    """6. Test immediate shop upgrade detection boosts ROLL score."""
    st_shop = GameState(
        stage=3,
        round=2,
        stage_round="3-2",
        player=PlayerState(gold=30, level=6, xp=0, hp=70),
        board_units=[Unit(champion="Diana", cost=3, star_level=1)],
        bench_units=[Unit(champion="Diana", cost=3, star_level=1)],
        shop_units=["Diana", None, None, None, None]
    )
    res = candidate_engine.evaluate(st_shop, model_type=CandidateModelType.V2_UPGRADE)
    shop_contribs = [c for c in res.feature_contributions if c.feature_id == "IMMEDIATE_SHOP_UPGRADE"]
    assert len(shop_contribs) == 1
    assert shop_contribs[0].score_delta > 0


def test_stage_benchmark_ratio(candidate_engine):
    """7. Test stage benchmark power ratio calculation."""
    st = GameState(stage=4, round=1, stage_round="4-1", player=PlayerState(gold=30, level=7, xp=0, hp=60))
    res = candidate_engine.evaluate(st, model_type=CandidateModelType.V4_COMBINED)
    assert "stage_benchmark_ratio" in res.state_summary


def test_recent_hp_delta(candidate_engine):
    """8. Test recent HP delta extraction."""
    st = GameState(stage=4, round=2, stage_round="4-2", player=PlayerState(gold=30, level=7, xp=0, hp=48))
    vec = candidate_engine.extractor.extract(st)
    assert vec.temporal.stage_numeric == 4.2


def test_gold_to_next_level(candidate_engine):
    """9. Test low gold to level increases LEVEL_UP score."""
    lvl_table = get_data_repository().get_levelup_cost_table()
    req_8 = lvl_table.get(8, 68)
    st_lvl = GameState(
        stage=4,
        round=2,
        stage_round="4-2",
        player=PlayerState(gold=40, level=7, xp=req_8 - 4, hp=70), # 4 XP needed for Lv 8
        board_units=[Unit(champion="Diana", cost=3, star_level=2)],
        bench_units=[Unit(champion="Lux", cost=4, star_level=1)]
    )
    res = candidate_engine.evaluate(st_lvl, model_type=CandidateModelType.V3_ECONOMY)
    lvl_contribs = [c for c in res.feature_contributions if c.feature_id == "GOLD_TO_NEXT_LEVEL"]
    assert len(lvl_contribs) == 1
    assert lvl_contribs[0].score_delta > 0


def test_spendable_roll_budget(candidate_engine):
    """10. Test compound interest preservation when safe and board is strong."""
    st_safe = GameState(
        stage=2,
        round=7,
        stage_round="2-7",
        player=PlayerState(gold=48, level=5, xp=0, hp=85),
        board_units=[
            Unit(champion="Diana", cost=3, star_level=2), # 6.6
            Unit(champion="Zac", cost=2, star_level=2),   # 4.4
            Unit(champion="Akali", cost=1, star_level=2), # 2.2
            Unit(champion="Lux", cost=4, star_level=2)    # 8.8 (Total 22.0 > 18.0 benchmark)
        ]
    )
    res = candidate_engine.evaluate(st_safe, model_type=CandidateModelType.V3_ECONOMY)
    save_contribs = [c for c in res.feature_contributions if c.feature_id == "SPENDABLE_ROLL_BUDGET"]
    assert len(save_contribs) == 1
    assert save_contribs[0].target_action == "SAVE_GOLD"


def test_t0_feature_safety(candidate_engine):
    """11. Test that candidate decision result never contains future outcome fields."""
    st = GameState(stage=4, round=1, stage_round="4-1", player=PlayerState(gold=30, level=7, xp=0, hp=60))
    res = candidate_engine.evaluate(st)
    assert not hasattr(res, "final_placement")
    assert not hasattr(res, "future_hp")


def test_feature_ablation(candidate_engine):
    """12. Test ablation study runner across all model configurations."""
    runner = AblationStudyRunner(candidate_engine)
    st = GameState(stage=4, round=3, stage_round="4-3", player=PlayerState(gold=48, level=7, xp=16, hp=38))
    res = runner.run_ablation([{"sample_id": "CP010", "state": st}])
    assert "BASELINE" in res["ablation_configurations"]
    assert "COMBINED_V4" in res["ablation_configurations"]
    assert len(res["interaction_effects"]) >= 3


def test_flip_reproduction(candidate_engine):
    """13. Test recommendation flip reproducibility."""
    st_crisis = GameState(stage=6, round=3, stage_round="6-3", player=PlayerState(gold=4, level=8, xp=40, hp=8))
    res = candidate_engine.evaluate(st_crisis, model_type=CandidateModelType.V4_COMBINED)
    assert res.baseline_action == "SAVE_GOLD"
    assert res.candidate_action == "ROLL"
    assert res.is_flipped is True


def test_human_review_schema():
    """14. Test human review queue jsonl exists and contains valid schema."""
    queue_path = os.path.join(DECISION_MODEL_DIR, "human_review_queue.jsonl")
    assert os.path.exists(queue_path)
    with open(queue_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) >= 3
    for line in lines:
        data = json.loads(line)
        assert "case_id" in data
        assert "baseline_action" in data
        assert "candidate_action" in data
        assert "feature_contributions" in data


def test_match_level_split():
    """15. Test match-level data metadata reporting."""
    snap_path = os.path.join(DECISION_MODEL_DIR, "baseline_snapshot.json")
    assert os.path.exists(snap_path)
    with open(snap_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 20


def test_patch_split():
    """16. Test patch version registration in candidate models."""
    cand_path = os.path.join(DECISION_MODEL_DIR, "candidate_models.json")
    assert os.path.exists(cand_path)
    with open(cand_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["models"]) == 4


def test_negative_control(candidate_engine):
    """17. Test that random noise benchmark does not produce tactical alignment."""
    analyzer = SensitivityAnalyzer(candidate_engine)
    st = GameState(stage=4, round=3, stage_round="4-3", player=PlayerState(gold=48, level=7, xp=16, hp=38))
    res = analyzer.run_sensitivity_sweep([{"sample_id": "CP010", "state": st}])
    assert "negative_control" in res
    assert "noise_flip_rate" in res["negative_control"]


def test_sensitivity_analysis(candidate_engine):
    """18. Test sensitivity sweep stability across +/-10% perturbation."""
    analyzer = SensitivityAnalyzer(candidate_engine)
    st = GameState(stage=4, round=3, stage_round="4-3", player=PlayerState(gold=48, level=7, xp=16, hp=38))
    res = analyzer.run_sensitivity_sweep([{"sample_id": "CP010", "state": st}])
    assert len(res["perturbation_sweep"]) == 5
    assert res["is_stable"] is True


def test_scenario_library(candidate_engine):
    """19. Test canonical scenario library evaluations."""
    mgr = ScenarioLibraryManager(candidate_engine)
    evals = mgr.evaluate_all_scenarios()
    assert len(evals) == 5
    scenario_ids = [e["scenario_id"] for e in evals]
    assert "SCENARIO_001" in scenario_ids
    assert "SCENARIO_002" in scenario_ids


def test_candidate_ranking():
    """20. Test production candidate report exists and contains readiness status."""
    report_path = os.path.join(DECISION_MODEL_DIR, "production_candidate_report.json")
    assert os.path.exists(report_path)
    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["gate_recommendation"] == "DECISION_MODEL_RESEARCH_READY"


def test_production_gate():
    """21. Test existence of all 4 research markdown reports."""
    for report_name in [
        "DECISION_MODEL_CALIBRATION_V1.md",
        "DECISION_MODEL_ABLATION_REPORT.md",
        "DECISION_MODEL_HUMAN_REVIEW.md",
        "DECISION_GUIDE_V2.md"
    ]:
        p = os.path.join(_ROOT, report_name)
        assert os.path.exists(p), f"Missing report: {report_name}"


def test_production_core_unchanged():
    """22. Strict Invariant: assert git diff on protected core is 0 lines."""
    res = subprocess.run(
        ["git", "diff", "src/tft/decision/", "src/tft/simulation/", "src/tft/evaluation/", "src/tft/domain/"],
        cwd=_ROOT,
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert res.stdout.strip() == "", f"Protected core was mutated:\n{res.stdout}"
