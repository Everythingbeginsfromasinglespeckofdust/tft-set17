"""Comprehensive Test Suite for TFT Vision Pipeline and Video Dataset Builder (v1)."""
import os
import sys
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState, PlayerState
from tft.vision.observation import Observation, CardObservation, UnitObservation
from tft.vision.events import ActionEvent, VisionActionType, ActionSource, QualityFlag
from tft.vision.timeline import ObservationTimeline
from tft.vision.game_state_reconstruction import GameStateReconstructor
from tft.backtest.action_inference import ActionInferenceEngine
from tft.backtest.video_dataset import VideoDatasetBuilder
from tft.backtest.models import SnapshotType, ActualActionType


def test_observation_timestamp_monotonicity():
    """Verify that ObservationTimeline enforces strictly monotonic timestamps."""
    timeline = ObservationTimeline()
    timeline.add_observation(Observation(timestamp_sec=10.0))
    timeline.add_observation(Observation(timestamp_sec=10.5))
    timeline.add_observation(Observation(timestamp_sec=10.2))  # Out of order insertion

    is_valid, violations = timeline.validate_temporal_monotonicity()
    assert is_valid is True
    assert len(violations) == 0
    assert [o.timestamp_sec for o in timeline.observations] == [10.0, 10.2, 10.5]


def test_event_ordering_deterministic():
    """Verify that ActionEvents are sorted deterministically by timestamp."""
    timeline = ObservationTimeline()
    ev1 = ActionEvent(action_type=VisionActionType.ROLL, source=ActionSource.OBSERVED, timestamp_sec=12.0)
    ev2 = ActionEvent(action_type=VisionActionType.BUY_UNIT, source=ActionSource.OBSERVED, timestamp_sec=11.5)

    timeline.add_event(ev1)
    timeline.add_event(ev2)

    assert timeline.events[0].timestamp_sec == 11.5
    assert timeline.events[1].timestamp_sec == 12.0


def test_no_future_leakage_in_reconstruction():
    """Verify GameStateReconstructor uses only causal forward observations (no hindsight)."""
    timeline = ObservationTimeline()
    # At t=10.0s, gold is 30G
    timeline.add_observation(Observation(timestamp_sec=10.0, gold_val=30, hp_val=80, level_val=6))
    # At t=15.0s, gold drops to 10G
    timeline.add_observation(Observation(timestamp_sec=15.0, gold_val=10, hp_val=75, level_val=6))

    reconstructor = GameStateReconstructor()
    state_timeline = reconstructor.reconstruct_timeline(timeline)

    state_t10 = reconstructor.get_state_at(state_timeline, 10.0)
    state_t12 = reconstructor.get_state_at(state_timeline, 12.0)
    state_t15 = reconstructor.get_state_at(state_timeline, 15.0)

    # State at t=10 and t=12 must strictly reflect 30G, not 10G from the future
    assert state_t10.player.gold == 30
    assert state_t12.player.gold == 30
    assert state_t15.player.gold == 10


def test_action_sources_distinguished():
    """Verify ActionSource enum distinguishes OBSERVED vs INFERRED vs UNKNOWN."""
    assert ActionSource.OBSERVED.value == "OBSERVED"
    assert ActionSource.INFERRED.value == "INFERRED"
    assert ActionSource.UNKNOWN.value == "UNKNOWN"


def test_save_gold_never_observed():
    """Verify SAVE_GOLD is strictly created as INFERRED and never as OBSERVED."""
    engine = ActionInferenceEngine(decision_window_sec=5.0)
    timeline = ObservationTimeline()
    # 3 observations over 12 seconds with no economic actions
    timeline.add_observation(Observation(timestamp_sec=10.0, gold_val=50))
    timeline.add_observation(Observation(timestamp_sec=15.0, gold_val=50))
    timeline.add_observation(Observation(timestamp_sec=20.0, gold_val=50))

    events = engine.extract_action_events(timeline)
    save_events = [e for e in events if e.action_type == VisionActionType.SAVE_GOLD]

    assert len(save_events) > 0
    for e in save_events:
        assert e.source == ActionSource.INFERRED, "SAVE_GOLD must never be marked as OBSERVED!"


def test_roll_detection_multi_evidence():
    """Verify multi-evidence ROLL detection from shop card changes and gold decrease."""
    engine = ActionInferenceEngine()
    obs_prev = Observation(
        timestamp_sec=30.0,
        gold_val=40,
        shop_cards=[
            CardObservation(slot_index=0, champion_pred="조이", cost_pred=2, confidence=0.9),
            CardObservation(slot_index=1, champion_pred="조이", cost_pred=2, confidence=0.9),
            CardObservation(slot_index=2, champion_pred="나서스", cost_pred=1, confidence=0.9),
            CardObservation(slot_index=3, champion_pred="자르반", cost_pred=1, confidence=0.9),
            CardObservation(slot_index=4, champion_pred="아지르", cost_pred=3, confidence=0.9),
        ]
    )
    obs_curr = Observation(
        timestamp_sec=30.5,
        gold_val=38,  # Decreased by 2G
        shop_cards=[
            CardObservation(slot_index=0, champion_pred="다리우스", cost_pred=1, confidence=0.9),
            CardObservation(slot_index=1, champion_pred="이렐리아", cost_pred=2, confidence=0.9),
            CardObservation(slot_index=2, champion_pred="쉔", cost_pred=3, confidence=0.9),
            CardObservation(slot_index=3, champion_pred="신드라", cost_pred=2, confidence=0.9),
            CardObservation(slot_index=4, champion_pred="아지르", cost_pred=3, confidence=0.9),
        ]
    )
    roll_event = engine._detect_roll(obs_prev, obs_curr)
    assert roll_event is not None
    assert roll_event.action_type == VisionActionType.ROLL
    assert roll_event.source == ActionSource.OBSERVED
    assert roll_event.confidence >= 0.85
    assert len(roll_event.evidence) >= 2


def test_buy_unit_detection():
    """Verify BUY_UNIT detection when a single shop card empties and gold drops by cost."""
    engine = ActionInferenceEngine()
    obs_prev = Observation(
        timestamp_sec=45.0,
        gold_val=30,
        shop_cards=[
            CardObservation(slot_index=0, champion_pred="미스 포츈", cost_pred=3, confidence=0.9),
            CardObservation(slot_index=1, champion_pred="조이", cost_pred=2, confidence=0.9),
            CardObservation(slot_index=2, champion_pred="나서스", cost_pred=1, confidence=0.9),
            CardObservation(slot_index=3, champion_pred="자르반", cost_pred=1, confidence=0.9),
            CardObservation(slot_index=4, champion_pred="아지르", cost_pred=3, confidence=0.9),
        ]
    )
    obs_curr = Observation(
        timestamp_sec=45.5,
        gold_val=27,  # -3G
        shop_cards=[
            CardObservation(slot_index=0, champion_pred=None, cost_pred=None, confidence=1.0, is_empty=True),
            CardObservation(slot_index=1, champion_pred="조이", cost_pred=2, confidence=0.9),
            CardObservation(slot_index=2, champion_pred="나서스", cost_pred=1, confidence=0.9),
            CardObservation(slot_index=3, champion_pred="자르반", cost_pred=1, confidence=0.9),
            CardObservation(slot_index=4, champion_pred="아지르", cost_pred=3, confidence=0.9),
        ]
    )
    buy_event = engine._detect_buy_unit(obs_prev, obs_curr)
    assert buy_event is not None
    assert buy_event.action_type == VisionActionType.BUY_UNIT
    assert buy_event.source == ActionSource.OBSERVED
    assert buy_event.target_champion == "미스 포츈"


def test_level_up_detection():
    """Verify LEVEL_UP detection upon player level increase."""
    engine = ActionInferenceEngine()
    obs_prev = Observation(timestamp_sec=60.0, level_val=6, gold_val=50)
    obs_curr = Observation(timestamp_sec=60.5, level_val=7, gold_val=34)

    lvl_event = engine._detect_level_up(obs_prev, obs_curr)
    assert lvl_event is not None
    assert lvl_event.action_type == VisionActionType.LEVEL_UP
    assert lvl_event.source == ActionSource.OBSERVED


def test_gamestate_reconstruction_deterministic():
    """Verify that GameState reconstruction is 100% deterministic."""
    timeline = ObservationTimeline()
    for t in [10.0, 10.5, 11.0, 11.5]:
        timeline.add_observation(Observation(
            timestamp_sec=t,
            stage_text="3-2",
            gold_val=40,
            level_val=7,
            hp_val=65
        ))

    reconstructor = GameStateReconstructor()
    res1 = reconstructor.reconstruct_timeline(timeline)
    res2 = reconstructor.reconstruct_timeline(timeline)

    assert len(res1) == len(res2) == 4
    for (t1, st1), (t2, st2) in zip(res1, res2):
        assert t1 == t2
        assert st1.player.gold == st2.player.gold
        assert st1.player.level == st2.player.level
        assert st1.stage_round == st2.stage_round


def test_identity_linking_flag():
    """Verify that unverified video sessions are properly flagged as UNVERIFIED without placement."""
    timeline = ObservationTimeline(duration_sec=300.0)
    timeline.add_observation(Observation(timestamp_sec=100.0, gold_val=30, level_val=6, hp_val=70))
    events = [ActionEvent(action_type=VisionActionType.ROLL, source=ActionSource.OBSERVED, timestamp_sec=100.0)]

    builder = VideoDatasetBuilder()
    samples, stats = builder.build_dataset_from_timeline(
        timeline, events, is_verified_identity=False
    )

    assert len(samples) == 1
    sample = samples[0]
    assert sample.future_observation.final_placement is None
    assert sample.metadata["quality_flag"] == "UNVERIFIED"
    assert sample.metadata["identity_link_status"] == "UNVERIFIED"


def test_backtest_sample_temporal_integrity():
    """Verify that generated BacktestSamples satisfy T0 <= T_action <= T1+."""
    timeline = ObservationTimeline(duration_sec=600.0)
    timeline.add_observation(Observation(timestamp_sec=320.0, gold_val=35, level_val=7, hp_val=60))
    events = [ActionEvent(action_type=VisionActionType.ROLL, source=ActionSource.OBSERVED, timestamp_sec=320.0)]

    builder = VideoDatasetBuilder()
    samples, stats = builder.build_dataset_from_timeline(
        timeline, events, known_time_end_sec=1920.0, is_verified_identity=True
    )

    assert len(samples) == 1
    s = samples[0]
    assert s.decision_timestamp_sec == 320.0
    assert s.future_observation.outcome_timestamp_sec == 1920.0
    assert s.decision_timestamp_sec <= s.future_observation.outcome_timestamp_sec
    assert s.snapshot_type == SnapshotType.MIDGAME_DECISION_SNAPSHOT
    assert s.observed_state.actual_action == ActualActionType.ROLL
