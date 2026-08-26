"""Comprehensive Unit Tests for ActionEventDetector v2.1, SystemEventDetector, and StateStability."""
import os
import sys
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.vision.observation import Observation, CardObservation, UnitObservation
from tft.vision.events import ActionEvent, VisionActionType, ActionSource
from tft.vision.state_diff import StateDiff, SlotTransitionType, compute_state_diff
from tft.vision.state_stability import StateStabilityAnalyzer, StabilityStatus
from tft.vision.system_event_detector import SystemEventDetector, SystemEventType
from tft.vision.adaptive_resampler import AdaptiveResampler
from tft.vision.action_event_detector_v21 import ActionEventDetectorV21


def _mock_obs(
    timestamp: float,
    gold: int = 35,
    stage: str = "3-2",
    champions: list[str] = None,
    bench: list[str] = None
) -> Observation:
    champs = champions or ["미스 포츈", "우르곳", "카이사", "나서스", "다리우스"]
    cards = []
    for i, c in enumerate(champs):
        is_emp = (c == "EMPTY" or c is None)
        cards.append(CardObservation(
            slot_index=i,
            champion_pred=c if not is_emp else None,
            cost_pred=3 if not is_emp else None,
            confidence=0.85 if not is_emp else 1.0,
            is_empty=is_emp
        ))
    bench_objs = [UnitObservation(location=f"bench_{i}", champion_pred=c, confidence=0.85) for i, c in enumerate(bench or [])]
    return Observation(
        timestamp_sec=timestamp,
        stage_text=stage,
        gold_val=gold,
        shop_cards=cards,
        bench_detections=bench_objs
    )


def test_system_refresh_not_roll():
    """Verify free shop refresh on round transition is classified as SYSTEM_SHOP_REFRESH, NOT PLAYER_ROLL."""
    obs1 = _mock_obs(300.0, stage="3-1", champions=["A", "B", "C", "D", "E"], gold=35)
    obs2 = _mock_obs(300.5, stage="3-2", champions=["F", "G", "H", "I", "J"], gold=35)  # Round changed, gold unchanged

    diff = compute_state_diff(obs1, obs2)
    detector = ActionEventDetectorV21(enable_adaptive_resampling=False)
    events = detector.detect_actions_from_diff(diff, obs1, obs2)

    # Should have SYSTEM_SHOP_REFRESH, and NO player ROLL
    sys_types = [e.metadata.get("system_event_type") for e in events]
    player_types = [e.action_type for e in events if "system_event_type" not in e.metadata or e.metadata["system_event_type"] is None]

    assert SystemEventType.SYSTEM_SHOP_REFRESH.value in sys_types
    assert VisionActionType.ROLL not in player_types


def test_round_start_refresh():
    """Verify stage-round text change emits ROUND_START."""
    obs1 = _mock_obs(100.0, stage="2-5")
    obs2 = _mock_obs(100.5, stage="2-6")

    diff = compute_state_diff(obs1, obs2)
    sys_detector = SystemEventDetector()
    events = sys_detector.detect_system_events(diff, obs1, obs2)

    sys_types = [e.metadata.get("system_event_type") for e in events]
    assert SystemEventType.ROUND_START.value in sys_types


def test_buy_unit_with_champion_identity():
    """Verify BUY_UNIT is detected when slot empties and matching champion appears on bench."""
    obs1 = _mock_obs(200.0, champions=["미스 포츈", "우르곳", "카이사", "나서스", "다리우스"], bench=[])
    obs2 = _mock_obs(200.5, champions=["EMPTY", "우르곳", "카이사", "나서스", "다리우스"], bench=["미스 포츈"], gold=32)

    diff = compute_state_diff(obs1, obs2)
    detector = ActionEventDetectorV21(enable_adaptive_resampling=False)
    events = detector.detect_actions_from_diff(diff, obs1, obs2)

    buys = [e for e in events if e.action_type == VisionActionType.BUY_UNIT]
    assert len(buys) == 1
    assert buys[0].target_champion == "미스 포츈"
    assert buys[0].slot_index == 0


def test_roll_with_gold_and_refresh():
    """Verify PLAYER_ROLL is detected when shop refreshes during same round with gold expenditure."""
    obs1 = _mock_obs(250.0, stage="3-2", champions=["A", "B", "C", "D", "E"], gold=38)
    obs2 = _mock_obs(250.5, stage="3-2", champions=["F", "G", "H", "I", "J"], gold=36)

    diff = compute_state_diff(obs1, obs2)
    detector = ActionEventDetectorV21(enable_adaptive_resampling=False)
    events = detector.detect_actions_from_diff(diff, obs1, obs2)

    rolls = [e for e in events if e.action_type == VisionActionType.ROLL]
    assert len(rolls) == 1
    assert rolls[0].confidence >= 0.80


def test_animation_transition_not_buy():
    """Verify transient animation frames with multiple empty slots suppress spurious BUYs."""
    obs1 = _mock_obs(350.0, champions=["A", "B", "C", "D", "E"], bench=[])
    # Transient animation frame: 3 slots empty midway through reroll wipe
    obs2 = _mock_obs(350.5, champions=["EMPTY", "EMPTY", "EMPTY", "D", "E"], bench=[])

    diff = compute_state_diff(obs1, obs2)
    detector = ActionEventDetectorV21(enable_adaptive_resampling=False)
    events = detector.detect_actions_from_diff(diff, obs1, obs2)

    buys = [e for e in events if e.action_type == VisionActionType.BUY_UNIT]
    assert len(buys) == 0  # Spurious BUY suppressed by stability analyzer


def test_state_stability():
    """Verify StateStabilityAnalyzer correctly diagnoses stable vs unstable states."""
    analyzer = StateStabilityAnalyzer()
    obs_stable = _mock_obs(400.0, champions=["A", "B", "C", "D", "E"])
    res_stable = analyzer.assess_observation(obs_stable)
    assert res_stable.is_stable is True

    # Empty transient wipe
    obs_prev = _mock_obs(400.0, champions=["A", "B", "C", "D", "E"])
    obs_wipe = _mock_obs(400.5, champions=["EMPTY", "EMPTY", "EMPTY", "D", "E"])
    res_wipe = analyzer.assess_observation(obs_wipe, prev_obs=obs_prev)
    assert res_wipe.is_shop_animation is True
    assert res_wipe.is_stable is False


def test_multi_action_resolution():
    """Verify compound BUY + ROLL emits both events with multi-action flag."""
    obs1 = _mock_obs(500.0, stage="3-2", champions=["미스 포츈", "우르곳", "카이사", "나서스", "다리우스"], bench=[], gold=38)
    obs2 = _mock_obs(500.5, stage="3-2", champions=["소나", "쉔", "제드", "바루스", "밀리오"], bench=["미스 포츈"], gold=33)

    diff = compute_state_diff(obs1, obs2)
    detector = ActionEventDetectorV21(enable_adaptive_resampling=False)
    events = detector.detect_actions_from_diff(diff, obs1, obs2)

    types = [e.action_type for e in events]
    assert VisionActionType.ROLL in types
    assert VisionActionType.BUY_UNIT in types
    assert all(e.metadata.get("is_multi_action_transition") is True for e in events if e.action_type != VisionActionType.UNKNOWN)


def test_adaptive_resampling_causal():
    """Verify timeline processing maintains strictly monotonic timestamps."""
    obs1 = _mock_obs(10.0)
    obs2 = _mock_obs(10.5, champions=["F", "G", "H", "I", "J"], gold=33)
    obs3 = _mock_obs(11.0, champions=["K", "L", "M", "N", "O"], gold=31)

    detector = ActionEventDetectorV21(enable_adaptive_resampling=False)
    events = detector.process_timeline([obs1, obs2, obs3])

    for i in range(len(events) - 1):
        assert events[i].timestamp_sec <= events[i+1].timestamp_sec
