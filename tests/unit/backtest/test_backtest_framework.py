"""Comprehensive Test Suite for TFT Backtesting Framework -- v1.1."""
import os
import sys
import pytest

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
    ActualActionType,
    SnapshotType,
    FailureType,
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
        snapshot_type=SnapshotType.ENDGAME_SNAPSHOT,
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

    assert always_save.decide_action(state_crisis) == ActionType.SAVE_GOLD
    assert always_save.decide_action(state_healthy) == ActionType.SAVE_GOLD
    assert hp_thresh.decide_action(state_crisis) == ActionType.ROLL
    assert hp_thresh.decide_action(state_healthy) == ActionType.SAVE_GOLD
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

    for d in engine_decs:
        assert d.recommended_action in [ActionType.ROLL, ActionType.LEVEL_UP, ActionType.SAVE_GOLD]
        assert d.decision_margin >= 0.0
        assert d.action_score_gap >= 0.0
        assert len(d.action_scores) == 3


def test_backtest_evaluator_metrics_and_report():
    """Verify BacktestEvaluator compiles comprehensive report with 15 sections."""
    samples = BacktestDataset.create_synthetic_dataset(num_samples=20, seed=42)
    runner = BacktestRunner(random_seed=42)
    engine_decs, base_decs = runner.run_batch(samples)

    evaluator = BacktestEvaluator()
    report = evaluator.evaluate(samples, engine_decs, base_decs)

    assert report.total_samples == 20
    assert report.total_matches > 0
    assert report.snapshot_type_distribution is not None
    assert len(report.stratification_by_hp) == 5
    assert len(report.stratification_by_gold) == 4
    assert len(report.stratification_by_stage) == 5
    assert len(report.stratification_by_level) == 4
    assert report.score_gap_diagnostics is not None
    assert len(report.what_can_be_concluded) > 0
    assert len(report.what_cannot_be_concluded) > 0
    assert len(report.next_required_data) > 0


def test_endgame_not_in_midgame_report():
    """Verify ENDGAME snapshots are separated and not included in MIDGAME statistics."""
    synth_midgame = BacktestDataset.create_synthetic_dataset(num_samples=10, seed=42)
    for s in synth_midgame:
        assert s.snapshot_type == SnapshotType.MIDGAME_DECISION_SNAPSHOT

    runner = BacktestRunner(random_seed=42)
    engine_decs, base_decs = runner.run_batch(synth_midgame)

    evaluator = BacktestEvaluator()
    report = evaluator.evaluate(synth_midgame, engine_decs, base_decs)

    assert report.endgame_count == 0
    assert report.midgame_count == 10
    assert report.leakage_validation.endgame_in_midgame_report == 0


def test_midgame_no_placement_leakage():
    """Verify MIDGAME samples do not contain placement inside GameState."""
    samples = BacktestDataset.create_synthetic_dataset(num_samples=15, seed=42)
    for s in samples:
        assert not hasattr(s.observed_state.state, "final_placement")
        assert not hasattr(s.observed_state.state.player, "final_placement")
        assert s.observed_state.state.player.gold >= 0
        assert s.observed_state.state.player.hp >= 0


def test_temporal_direction_maintained():
    """Verify decision_timestamp_sec <= outcome_timestamp_sec for all valid samples."""
    samples = BacktestDataset.create_synthetic_dataset(num_samples=25, seed=42)
    for s in samples:
        t0 = s.decision_timestamp_sec
        t1 = s.future_observation.outcome_timestamp_sec
        if t0 is not None and t1 is not None:
            assert t0 <= t1, f"Temporal violation: T0({t0}) > T1({t1})"


def test_known_action_coverage_denominator():
    """Verify coverage denominator and rate are mathematically consistent."""
    samples = BacktestDataset.create_synthetic_dataset(num_samples=30, seed=42)
    evaluator = BacktestEvaluator()
    runner = BacktestRunner(random_seed=42)
    e_decs, b_decs = runner.run_batch(samples)
    report = evaluator.evaluate(samples, e_decs, b_decs)

    cov = report.action_observation_coverage
    assert cov.total_samples == 30
    assert cov.known_action_samples + cov.unknown_action_samples == cov.total_samples
    assert abs(cov.coverage_rate - (cov.known_action_samples / 30.0)) < 1e-4


def test_metric_denominators_explicit():
    """Verify that every stratified group and metric explicitly tracks sample counts and denominators."""
    samples = BacktestDataset.create_synthetic_dataset(num_samples=20, seed=42)
    evaluator = BacktestEvaluator()
    runner = BacktestRunner(random_seed=42)
    e_decs, b_decs = runner.run_batch(samples)
    report = evaluator.evaluate(samples, e_decs, b_decs)

    for g in report.stratification_by_hp:
        assert g.sample_count >= 0
        assert g.placement_denominator >= 0
        assert g.placement_denominator <= g.sample_count


def test_failure_taxonomy_cases():
    """Verify failure case detection categorizes failures using the FailureType taxonomy."""
    sample = BacktestSample(
        sample_id="FAIL_TEST_01",
        match_id="M_FAIL",
        participant_id="P_FAIL",
        data_source="synthetic_simulation",
        snapshot_type=SnapshotType.MIDGAME_DECISION_SNAPSHOT,
        observed_state=ObservedState(
            match_id="M_FAIL",
            participant_id="P_FAIL",
            stage=4, round_num=1, stage_round="4-1",
            state=GameState(
                stage=4, round=1, stage_round="4-1",
                player=PlayerState(gold=40, level=7, xp=0, hp=15),
                board_units=[Unit(champion="조이", cost=2, star_level=1)],
                bench_units=[Unit(champion="조이", cost=2, star_level=1)]
            ),
            actual_action=ActualActionType.ROLL
        ),
        future_observation=FutureObservation(
            final_placement=8,
            top4=False,
            horizon_rounds=5,
            outcome_timestamp_sec=900.0
        ),
        decision_timestamp_sec=300.0,
        horizon_rounds=5
    )

    runner = BacktestRunner(random_seed=42)
    e_decs, b_decs = runner.run_batch([sample])
    evaluator = BacktestEvaluator()
    report = evaluator.evaluate([sample], e_decs, b_decs)

    assert report.total_samples == 1
    # Check that any diagnosed failure case uses a valid FailureType value
    for fc in report.failure_cases_sample:
        assert fc.failure_category in [e.value for e in FailureType]


def test_all_riot_snapshots_classified_endgame():
    """Verify that match snapshots loaded from historical data are classified as ENDGAME_SNAPSHOT."""
    fixture_path = os.path.join(_SRC, "..", "output", "data", "match_snapshots.jsonl")
    if os.path.exists(fixture_path):
        samples = BacktestDataset.load_from_match_snapshots(fixture_path, limit=20)
        assert len(samples) > 0
        for s in samples:
            assert s.snapshot_type == SnapshotType.ENDGAME_SNAPSHOT
            assert s.horizon_rounds == 0
            assert s.observed_state.state.player.hp == 0  # Leakage fixed (not 100 for 1st)
            assert s.observed_state.actual_action == ActualActionType.UNKNOWN
