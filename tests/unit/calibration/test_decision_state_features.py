"""Unit and Integration Tests for TFT Decision State Features & Calibration Research v1."""
import json
import os
import sys
import subprocess
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
_ROOT = os.path.abspath(os.path.join(_SRC, ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState, PlayerState, LobbyState
from tft.domain.units import Unit
from tft.data.repositories import get_data_repository
from tft.research.decision_features.taxonomy import (
    DecisionStateVector,
    PlayerStateVector,
    EconomyStateVector,
    BoardStateVector,
    UpgradeStateVector,
    OpponentStateVector,
    TemporalStateVector,
    RelativeStateVector,
    FeatureCategory,
    DataTier,
    CandidateGateVerdict
)
from tft.research.decision_features.board_power import BoardPowerModel
from tft.research.decision_features.survival_risk import SurvivalRiskModel
from tft.research.decision_features.economy_reserve import EconomyReserveModel
from tft.research.decision_features.upgrade_opportunity import UpgradeOpportunityModel
from tft.research.decision_features.level_up_cost import LevelUpOpportunityModel
from tft.calibration.state_features.extractor import StateFeatureExtractor
from tft.calibration.state_features.evaluator import FeatureEvaluator
from tft.calibration.state_features.flip_analyzer import FlipAnalyzer
from tft.calibration.state_features.guide_generator import DecisionGuideGenerator


# -----------------------------------------------------------------------------
# 1. Schema & T0 Temporal Safety Tests
# -----------------------------------------------------------------------------

def test_feature_registry_schema():
    """1. Test feature registry contains all 7 categories and 100% valid schema."""
    registry_path = os.path.join(_ROOT, "data", "sets", "set18", "calibration", "state_features", "feature_registry.json")
    assert os.path.exists(registry_path)
    with open(registry_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["set"] == 18
    assert len(data["categories"]) == 7
    assert data["total_registered_features"] >= 15
    for feat in data["features"]:
        assert "feature_code" in feat
        assert "scores" in feat
        assert "gate_verdict" in feat


def test_t0_availability_and_leakage_absence():
    """2. Test all feature vectors are available at T0 and do not contain future outcomes."""
    repo = get_data_repository()
    extractor = StateFeatureExtractor(repo)

    st = GameState(
        stage=4,
        round=2,
        stage_round="4-2",
        player=PlayerState(gold=44, level=7, xp=12, hp=48),
        board_units=[
            Unit(champion="Diana", cost=3, star_level=2),
            Unit(champion="Akali", cost=1, star_level=2)
        ]
    )
    vec = extractor.extract(st, sample_id="T0_TEST")

    # Strict assertion: no placement, future_hp, or outcome fields exist in vector
    assert not hasattr(vec, "final_placement")
    assert not hasattr(vec, "future_hp")
    assert not hasattr(vec, "outcome_damage")
    assert vec.player.hp == 48
    assert vec.player.gold == 44


def test_missing_feature_null_safety():
    """3. Test unobserved opponent / lobby data returns None/null, NEVER 0."""
    repo = get_data_repository()
    extractor = StateFeatureExtractor(repo)

    st = GameState(
        stage=3,
        round=1,
        stage_round="3-1",
        player=PlayerState(gold=50, level=6, xp=0, hp=80),
        opponents=[] # Empty opponents
    )
    vec = extractor.extract(st)
    assert vec.opponent.lobby_mean_board_power is None
    assert vec.opponent.current_opponent_power_gap is None
    assert vec.relative.board_power_percentile is None


# -----------------------------------------------------------------------------
# 2. Research Feature Components Tests
# -----------------------------------------------------------------------------

def test_board_power_decomposition():
    """4. Test board power decomposed into unit power, items, and synergies."""
    repo = get_data_repository()
    model = BoardPowerModel(repo)

    st = GameState(
        stage=4,
        round=1,
        stage_round="4-1",
        player=PlayerState(gold=30, level=6, xp=0, hp=60),
        board_units=[
            Unit(champion="Diana", cost=3, star_level=2),
            Unit(champion="Akali", cost=1, star_level=1)
        ]
    )
    data = model.decompose_board(st)
    assert data["total_power"] > 0
    assert abs(data["unit_power"] - (3 * 2.2 + 1 * 1.0)) < 1e-3
    assert data["unit_count"] == 2
    assert "frontline_power_ratio" in data
    assert "backline_power_ratio" in data


def test_stage_benchmark_power_ratio():
    """5. Test stage benchmark power calculations across stages 1 through 7."""
    model = BoardPowerModel()
    r_par = model.compute_stage_benchmark_ratio(55.0, 4)
    assert r_par == 1.0

    r_weak = model.compute_stage_benchmark_ratio(33.0, 4)
    assert r_weak == 0.60

    r_strong = model.compute_stage_benchmark_ratio(82.5, 4)
    assert r_strong == 1.50


def test_lobby_relative_board_power():
    """6. Test lobby relative mean, median, and percentile ranking."""
    model = BoardPowerModel()
    opps = [
        LobbyState(player_id="P1", hp=90, level=7, estimated_board_power=40.0),
        LobbyState(player_id="P2", hp=80, level=7, estimated_board_power=50.0),
        LobbyState(player_id="P3", hp=70, level=7, estimated_board_power=60.0)
    ]
    res = model.compute_lobby_relative_metrics(my_power=55.0, opponents=opps)
    assert res["known_opponents_count"] == 3
    assert res["lobby_mean_board_power"] == round((40 + 50 + 60 + 55) / 4.0, 2)
    assert res["board_power_percentile"] == 0.75


def test_survival_risk_context():
    """7. Test contextual survival risk modeling."""
    r_lethal = SurvivalRiskModel.evaluate_risk(hp=10, stage=5, round_num=2)
    assert r_lethal["risk_category"] == "ONE_SHOT_LETHAL"
    assert r_lethal["is_lethal_next_round"] is True
    assert r_lethal["risk_score"] >= 0.90

    r_safe = SurvivalRiskModel.evaluate_risk(hp=90, stage=2, round_num=1)
    assert r_safe["risk_category"] == "SAFE"
    assert r_safe["risk_score"] <= 0.15


def test_economy_reserve_and_interest_breakpoints():
    """8. Test discrete interest tiers and dynamic economy reserve targets."""
    table = {6: 20, 7: 36, 8: 60}
    
    e1 = EconomyReserveModel.evaluate_economy(gold=38, hp=80, stage=3, level=6, xp=4, levelup_cost_table=table)
    assert e1["interest_tier"] == 3
    assert e1["gold_to_next_interest"] == 2
    assert e1["economy_reserve_target"] == 50

    e2 = EconomyReserveModel.evaluate_economy(gold=38, hp=20, stage=4, level=7, xp=0, levelup_cost_table=table)
    assert e2["economy_reserve_target"] == 0
    assert e2["spendable_roll_budget"] == 38


def test_upgrade_and_pair_detection():
    """9. Test 2-star pairs detection and missing copies count."""
    repo = get_data_repository()
    model = UpgradeOpportunityModel(repo)

    st = GameState(
        stage=3,
        round=2,
        stage_round="3-2",
        player=PlayerState(gold=30, level=6, xp=0, hp=70),
        board_units=[Unit(champion="Diana", cost=3, star_level=1)],
        bench_units=[
            Unit(champion="Diana", cost=3, star_level=1),
            Unit(champion="Akali", cost=1, star_level=1)
        ],
        shop_units=[None]*5
    )
    upg = model.evaluate_upgrades(st)
    assert upg["pair_count"] == 1
    assert "Diana" in upg["pairs_list"]
    assert upg["missing_copies_summary"]["Diana"] == 1


def test_immediate_shop_upgrade_synergy():
    """10. Test detecting units in shop that immediately complete a star upgrade."""
    repo = get_data_repository()
    model = UpgradeOpportunityModel(repo)

    st = GameState(
        stage=3,
        round=2,
        stage_round="3-2",
        player=PlayerState(gold=30, level=6, xp=0, hp=70),
        board_units=[Unit(champion="Diana", cost=3, star_level=1)],
        bench_units=[Unit(champion="Diana", cost=3, star_level=1)],
        shop_units=["Diana", "Akali", None, "Lux", None]
    )
    upg = model.evaluate_upgrades(st)
    assert upg["has_immediate_upgrade_in_shop"] is True
    assert upg["immediate_shop_upgrades_count"] == 1
    assert upg["immediate_shop_upgrades"][0]["champion"] == "Diana"


def test_level_up_marginal_value():
    """11. Test level-up opportunity cost and shop odds jump calculation."""
    repo = get_data_repository()
    model = LevelUpOpportunityModel(repo)
    lvl_table = repo.get_levelup_cost_table()
    req_8 = lvl_table.get(8, 68)

    st = GameState(
        stage=4,
        round=2,
        stage_round="4-2",
        player=PlayerState(gold=40, level=7, xp=req_8 - 4, hp=60), # Exactly 4 XP needed for Lv 8
        board_units=[Unit(champion="Diana", cost=3, star_level=2)],
        bench_units=[Unit(champion="Lux", cost=2, star_level=2)]
    )
    res = model.evaluate_level_up_tradeoff(st)
    assert res["target_level"] == 8
    assert res["gold_required"] == 4 # 1 click (4G)
    assert res["high_cost_odds_jump"] > 0
    assert res["marginal_level_value_score"] > 0.50


# -----------------------------------------------------------------------------
# 3. Calibration, Flip Analysis & Artifact Validation
# -----------------------------------------------------------------------------

def test_negative_control_benchmarking():
    """12. Test negative control random variable is rejected in quality evaluation."""
    evaluator = FeatureEvaluator()
    repo = get_data_repository()
    extractor = StateFeatureExtractor(repo)

    st = GameState(stage=3, round=1, stage_round="3-1", player=PlayerState(gold=40, level=6, xp=0, hp=70))
    vec = extractor.extract(st)
    res = evaluator.evaluate_feature_quality([vec])
    
    assert "NEGATIVE_CONTROL_RANDOM" in res
    assert res["NEGATIVE_CONTROL_RANDOM"]["gate_verdict"] == CandidateGateVerdict.REJECT.value


def test_recommendation_flip_analysis_and_queue():
    """13. Test flip analyzer captures flips and generates valid review queue entries."""
    analyzer = FlipAnalyzer()
    
    st_crisis = GameState(
        stage=6,
        round=3,
        stage_round="6-3",
        player=PlayerState(gold=4, level=8, xp=0, hp=8),
        board_units=[Unit(champion="Diana", cost=3, star_level=2)]
    )
    samples = [{
        "sample_id": "CP020_TEST",
        "match_id": "M_TEST",
        "state": st_crisis,
        "actual_player_action": "SAVE_GOLD"
    }]
    report = analyzer.run_flip_analysis(samples)
    assert report["total_evaluated_samples"] == 1
    assert report["total_flips"] >= 1
    assert report["sample_flips"][0]["flip_rationale_code"] == "CANDIDATE_LETHAL_EMERGENCY_ROLL"


def test_decision_guide_formatting():
    """14. Test decision guide outputs formatted markdown with current context and roadmap."""
    repo = get_data_repository()
    extractor = StateFeatureExtractor(repo)

    st = GameState(stage=4, round=2, stage_round="4-2", player=PlayerState(gold=44, level=7, xp=12, hp=48))
    vec = extractor.extract(st)
    guide = DecisionGuideGenerator.format_guide(
        state_vec=vec,
        recommended_action="ROLL",
        action_score=0.8850,
        score_gap=0.1420,
        reasons=["[CRISIS] HP below benchmark"]
    )
    assert "# 🧭 TFT Decision State Guide" in guide
    assert "Health (HP)" in guide
    assert "Engine Recommendation" in guide


def test_strategic_qa_reference():
    """15. Test strategic Q&A reference document contains Q1 through Q8."""
    qa = DecisionGuideGenerator.get_strategic_qa_reference()
    for q_idx in range(1, 9):
        assert f"Q{q_idx}." in qa


def test_production_core_unchanged():
    """16. Strict Invariant: assert git diff on protected core is 0 lines."""
    res = subprocess.run(
        ["git", "diff", "src/tft/decision/", "src/tft/simulation/", "src/tft/evaluation/", "src/tft/domain/"],
        cwd=_ROOT,
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert res.stdout.strip() == "", f"Protected core was mutated:\n{res.stdout}"
