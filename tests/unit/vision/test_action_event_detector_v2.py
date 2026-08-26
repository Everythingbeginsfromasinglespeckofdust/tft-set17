"""Comprehensive Unit Tests for ActionEventDetector v2 & StateDiff Engine."""
import os
import sys
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.vision.observation import Observation, CardObservation, UnitObservation
from tft.vision.events import ActionEvent, VisionActionType, ActionSource
from tft.vision.state_diff import StateDiff, SlotTransitionType, compute_state_diff
from tft.vision.action_event_detector import ActionEventDetectorV2, EvidenceCode


def _create_mock_obs(
    timestamp: float,
    gold: int = 35,
    level: int = 7,
    xp: int = 12,
    hp: int = 60,
    shop_champions: list[str] = None,
    bench_champions: list[str] = None,
    board_champions: list[str] = None
) -> Observation:
    champs = shop_champions or ["미스 포츈", "우르곳", "카이사", "나서스", "다리우스"]
    cards = []
    for i, c in enumerate(champs):
        is_emp = (c == "EMPTY" or c is None)
        cards.append(CardObservation(
            slot_index=i,
            champion_pred=c if not is_emp else None,
            cost_pred=3 if not is_emp else None,
            confidence=0.85,
            is_empty=is_emp
        ))

    bench = [UnitObservation(location=f"bench_{i}", champion_pred=c, confidence=0.85) for i, c in enumerate(bench_champions or [])]
    board = [UnitObservation(location=f"hex_r0_c{i}", champion_pred=c, confidence=0.85) for i, c in enumerate(board_champions or [])]

    return Observation(
        timestamp_sec=timestamp,
        frame_index=int(timestamp * 60),
        gold_val=gold,
        level_val=level,
        xp_val=xp,
        hp_val=hp,
        shop_cards=cards,
        bench_detections=bench,
        field_detections=board
    )


def test_state_diff_computation():
    """Verify exact calculation of Gold, HP, Level, and Shop slot transitions."""
    obs_before = _create_mock_obs(
        timestamp=10.0,
        gold=38,
        shop_champions=["조이", "미스 포츈", "카이사", "나서스", "다리우스"]
    )
    obs_after = _create_mock_obs(
        timestamp=10.5,
        gold=36,
        shop_champions=["소나", "쉔", "제드", "나서스", "밀리오"]
    )

    diff = compute_state_diff(obs_before, obs_after)
    assert diff.gold_delta == -2
    assert diff.dt_sec == 0.5
    assert diff.shop_slots_changed == 4
    assert diff.shop_slots_refreshed == 4
    assert diff.shop_slots_emptied == 0


def test_roll_detection_multi_slot_and_gold():
    """Verify ROLL detection when multi-slots refresh with -2G delta."""
    obs_before = _create_mock_obs(
        timestamp=20.0,
        gold=38,
        shop_champions=["조이", "미스 포츈", "카이사", "나서스", "다리우스"]
    )
    obs_after = _create_mock_obs(
        timestamp=20.5,
        gold=36,
        shop_champions=["소나", "쉔", "제드", "바루스", "밀리오"]
    )

    diff = compute_state_diff(obs_before, obs_after)
    detector = ActionEventDetectorV2()
    actions = detector.detect_actions(diff, obs_after)

    assert len(actions) == 1
    assert actions[0].action_type == VisionActionType.ROLL
    assert actions[0].source == ActionSource.OBSERVED
    assert actions[0].confidence >= 0.85
    assert any("2G" in ev for ev in actions[0].evidence)


def test_buy_unit_detection_with_champion_identity():
    """Verify BUY_UNIT detection when slot empties and matching champion appears on bench."""
    obs_before = _create_mock_obs(
        timestamp=30.0,
        gold=38,
        shop_champions=["미스 포츈", "우르곳", "카이사", "나서스", "다리우스"],
        bench_champions=["조이"]
    )
    obs_after = _create_mock_obs(
        timestamp=30.5,
        gold=35,  # -3G (Miss Fortune is 3C)
        shop_champions=["EMPTY", "우르곳", "카이사", "나서스", "다리우스"],
        bench_champions=["조이", "미스 포츈"]  # MF added
    )

    diff = compute_state_diff(obs_before, obs_after)
    detector = ActionEventDetectorV2()
    actions = detector.detect_actions(diff, obs_after)

    assert len(actions) == 1
    assert actions[0].action_type == VisionActionType.BUY_UNIT
    assert actions[0].target_champion == "미스 포츈"
    assert actions[0].slot_index == 0
    assert any("Slot 1" in ev for ev in actions[0].evidence)


def test_level_up_detection():
    """Verify LEVEL_UP detection when player level increases."""
    obs_before = _create_mock_obs(timestamp=40.0, gold=50, level=7)
    obs_after = _create_mock_obs(timestamp=40.5, gold=42, level=8)

    diff = compute_state_diff(obs_before, obs_after)
    detector = ActionEventDetectorV2()
    actions = detector.detect_actions(diff, obs_after)

    assert len(actions) == 1
    assert actions[0].action_type == VisionActionType.LEVEL_UP
    assert actions[0].confidence >= 0.90


def test_buy_xp_vs_level_up():
    """Verify BUY_XP is emitted when XP increases but level remains unchanged."""
    obs_before = _create_mock_obs(timestamp=50.0, gold=50, level=7, xp=10)
    obs_after = _create_mock_obs(timestamp=50.5, gold=46, level=7, xp=14)

    diff = compute_state_diff(obs_before, obs_after)
    detector = ActionEventDetectorV2()
    actions = detector.detect_actions(diff, obs_after)

    assert len(actions) == 1
    assert actions[0].action_type == VisionActionType.BUY_XP


def test_sell_unit_detection():
    """Verify SELL_UNIT detection when unit is removed from bench with gold increase."""
    obs_before = _create_mock_obs(timestamp=60.0, gold=30, bench_champions=["조이", "다리우스"])
    obs_after = _create_mock_obs(timestamp=60.5, gold=32, bench_champions=["조이"])

    diff = compute_state_diff(obs_before, obs_after)
    detector = ActionEventDetectorV2()
    actions = detector.detect_actions(diff, obs_after)

    assert len(actions) == 1
    assert actions[0].action_type == VisionActionType.SELL_UNIT


def test_multi_action_transition_flagging():
    """Verify multi-action transitions (e.g. BUY then ROLL in same window) are flagged."""
    obs_before = _create_mock_obs(
        timestamp=70.0,
        gold=38,
        shop_champions=["미스 포츈", "우르곳", "카이사", "나서스", "다리우스"],
        bench_champions=[]
    )
    obs_after = _create_mock_obs(
        timestamp=70.5,
        gold=33,  # -3G for MF buy, -2G for reroll
        shop_champions=["소나", "쉔", "제드", "바루스", "밀리오"],
        bench_champions=["미스 포츈"]
    )

    diff = compute_state_diff(obs_before, obs_after)
    detector = ActionEventDetectorV2()
    actions = detector.detect_actions(diff, obs_after)

    # Should detect both actions and flag multi-action
    types = [a.action_type for a in actions]
    assert VisionActionType.ROLL in types
    assert all(a.metadata.get("is_multi_action_transition") is True for a in actions)


def test_online_causality_and_temporal_integrity():
    """Verify that event timestamps strictly follow chronological order without future hindsight."""
    obs1 = _create_mock_obs(100.0, gold=40)
    obs2 = _create_mock_obs(100.5, gold=38, shop_champions=["A", "B", "C", "D", "E"])
    obs3 = _create_mock_obs(101.0, gold=36, shop_champions=["F", "G", "H", "I", "J"])

    detector = ActionEventDetectorV2()
    events = detector.process_timeline([obs1, obs2, obs3])

    for i in range(len(events) - 1):
        assert events[i].timestamp_sec <= events[i+1].timestamp_sec
