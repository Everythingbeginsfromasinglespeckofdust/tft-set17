"""Comprehensive Test Suite for TFT Backtesting Framework."""
import pytest
import sys, os

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.domain.actions import ActionType
from tft.backtest.models import (
    BacktestSample,
    ObservedState,
    FutureObservation,
    ActualActionType
)
from tft.backtest.dataset import BacktestDataset, round_number_to_stage_round
from tft.backtest.baselines import (
    AlwaysSaveBaseline,
    HPThresholdBaseline,
    RuleEngineBaseline
)
from tft.backtest.runner import BacktestRunner
from tft.backtest.evaluator import BacktestEvaluator

def test_round_number_to_stage_round_mapping():
    """Verify TFT round number mapping to stage-round format."""
    assert round_number_to_stage_round(1) == (1, 1, "1-1")
    assert round_number_to_stage_round(4) == (1, 4, "1-4")
    assert round_number_to_stage_round(5) == (2, 1, "2-1")
    assert round_number_to_stage_round(11) == (2, 7, "2-7")
    assert round_number_to_stage_round(12) == (3, 1, "3-1")
    assert round_number_to_stage_round(24) == (4, 6, "4-6")
    assert round_number_to_stage_round(30) == (5, 5, "5-5")

def test_snapshot_leakage_prevention():
    """Verify GameState does not leak future placement or outcome information."""
    sample = BacktestSample(
        sample_id="S_001",
        match_id="M_001",
        participant_id="P_001",
        data_source="historical_match_snapshot",
        observed_state=ObservedState(
            match_id="M_001",
            participant_id="P_001",
            stage=3,
            round_num=2,
            stage_round="3-2",
            state=GameState(
                stage=3,
                round=2,
                stage_round="3-2",
                player=PlayerState(gold=30, level=6, xp=10, hp=75),
                board_units=[Unit(champion="나서스", cost=1, star_level=2)]
            ),
            actual_action=ActualActionType.UNKNOWN
        ),
        future_observation=FutureObservation(
            final_placement=1,
            top4=True
        )
    )

    # Validate that observed_state.state does NOT contain future placement
    assert not hasattr(sample.observed_state.state, "final_placement")
    assert not hasattr(sample.observed_state.state.player, "final_placement")
    assert BacktestDataset.validate_sample(sample) is True

def test_match_split_zero_leakage():
    """Verify match-level group split ensures zero overlap of match IDs between train and test."""
    samples = BacktestDataset.create_synthetic_dataset(num_samples=80, seed=42)
    train_s, test_s = BacktestDataset.split_by_match(samples, train_ratio=0.75, seed=42)

    assert len(train_s) > 0
    assert len(test_s) > 0
    assert len(train_s) + len(test_s) == len(samples)

    train_matches = set(s.match_id for s in train_s)
    test_matches = set(s.match_id for s in test_s)

    # Absolute zero overlap
    overlap = train_matches.intersection(test_matches)
    assert len(overlap) == 0, f"Found leaking match IDs across splits: {overlap}"

def test_baselines_determinism():
    """Verify baseline strategies execute deterministically."""
    state_crisis = GameState(
        stage=4, round=1, stage_round="4-1",
        player=PlayerState(gold=40, level=7, xp=0, hp=20),
        board_units=[Unit(champion="조이", cost=2, star_level=1)]
    )
    state_healthy = GameState(
        stage=2, round=3, stage_round="2-3",
        player=PlayerState(gold=40, level=5, xp=0, hp=90),
        board_units=[Unit(champion="조이", cost=2, star_level=2)]
    )

    always_save = AlwaysSaveBaseline()
    hp_thresh = HPThresholdBaseline(hp_threshold=35)
    rule_engine = RuleEngineBaseline(crisis_hp=30)

    # AlwaysSave always recommends SAVE_GOLD
    assert always_save.decide_action(state_crisis) == ActionType.SAVE_GOLD
    assert always_save.decide_action(state_healthy) == ActionType.SAVE_GOLD

    # HPThreshold adapts to crisis
    assert hp_thresh.decide_action(state_crisis) == ActionType.ROLL
    assert hp_thresh.decide_action(state_healthy) == ActionType.SAVE_GOLD

    # RuleEngine adapts to crisis
    assert rule_engine.decide_action(state_crisis) == ActionType.ROLL
    assert rule_engine.decide_action(state_healthy) == ActionType.SAVE_GOLD

def test_backtest_runner_batch_execution():
    """Verify BacktestRunner processes batch of samples seamlessly."""
    samples = BacktestDataset.create_synthetic_dataset(num_samples=10, seed=42)
    runner = BacktestRunner(random_seed=42)

    engine_decs, base_decs = runner.run_batch(samples)

    assert len(engine_decs) == 10
    assert "AlwaysSave" in base_decs
    assert len(base_decs["AlwaysSave"]) == 10
    assert len(base_decs["HPThreshold"]) == 10
    assert len(base_decs["RuleEngine"]) == 10

    # Assert all decisions have required attributes
    for d in engine_decs:
        assert d.recommended_action in [ActionType.ROLL, ActionType.LEVEL_UP, ActionType.SAVE_GOLD]
        assert d.decision_margin >= 0.0
        assert len(d.action_scores) == 3

def test_backtest_evaluator_metrics_and_report():
    """Verify BacktestEvaluator compiles comprehensive report with stratifications."""
    samples = BacktestDataset.create_synthetic_dataset(num_samples=20, seed=42)
    runner = BacktestRunner(random_seed=42)
    engine_decs, base_decs = runner.run_batch(samples)

    evaluator = BacktestEvaluator()
    report = evaluator.evaluate(samples, engine_decs, base_decs)

    assert report.total_samples == 20
    assert report.total_matches > 0
    assert len(report.stratification_by_hp) == 5
    assert len(report.stratification_by_gold) == 4
    assert len(report.stratification_by_stage) == 5
    assert len(report.stratification_by_level) == 4
    assert len(report.margin_tier_analysis) == 4
    assert report.outcome_summary["avg_placement"] is not None
    assert len(report.data_limitations) > 0
