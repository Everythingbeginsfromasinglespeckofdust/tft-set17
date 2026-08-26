"""Unit Tests for Production ActionEventDetector v2.2."""
import os
import sys
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.vision.events import ActionEvent, VisionActionType, ActionSource, QualityFlag
from tft.vision.observation import Observation, CardObservation, UnitObservation
from tft.vision.state_diff import StateDiff, SlotTransition, SlotTransitionType
from tft.vision.system_event_detector import SystemEventType
from tft.vision.state_stability import StabilityAssessment, StabilityStatus
from tft.vision.action_event_detector_v22 import (
    ActionEventDetectorV22,
    ActionCandidate,
    RuleName
)


def _create_mock_obs(timestamp: float, gold: int = 35, shop_empty: bool = False) -> Observation:
    cards = [
        CardObservation(slot_index=i, champion_pred=f"Champ_{i}", cost_pred=1, confidence=1.0, is_empty=(shop_empty and i == 0))
        for i in range(5)
    ]
    return Observation(
        timestamp_sec=timestamp,
        frame_index=int(timestamp * 60),
        stage_text="3-2",
        gold_val=gold,
        hp_val=60,
        level_val=7,
        xp_val=12,
        shop_cards=cards
    )


def test_v22_roll_baseline_rule():
    """Verify ROLL_BASELINE rule evaluates correctly with gold -2 and shop transition."""
    detector = ActionEventDetectorV22()
    diff = StateDiff(
        timestamp_before=10.0,
        timestamp_after=10.5,
        dt_sec=0.5,
        gold_delta=-2,
        shop_slots_changed=4,
        shop_changes=[SlotTransition(0, "A", 1, False, "B", 1, False, SlotTransitionType.REFRESHED)]
    )
    obs = _create_mock_obs(10.5, gold=33)
    stab = StabilityAssessment(status=StabilityStatus.STABLE, is_stable=True, confidence_mean=0.9, empty_slot_count=0, unrecognized_slot_count=0, is_shop_animation=False)

    candidates = detector.evaluate_candidates(diff, obs, [], stab)
    assert len(candidates) == 1
    assert candidates[0].action_type == VisionActionType.ROLL
    assert RuleName.ROLL_BASELINE in candidates[0].matched_rules


def test_v22_buy_baseline_rule():
    """Verify BUY_BASELINE rule evaluates correctly on emptied slot with matching cost."""
    detector = ActionEventDetectorV22()
    diff = StateDiff(
        timestamp_before=20.0,
        timestamp_after=20.5,
        dt_sec=0.5,
        gold_delta=-2,
        shop_slots_emptied=1,
        shop_changes=[SlotTransition(1, "Zoe", 2, False, None, None, True, SlotTransitionType.EMPTIED)],
        units_added_bench=["Zoe"]
    )
    obs = _create_mock_obs(20.5, gold=33, shop_empty=True)
    stab = StabilityAssessment(status=StabilityStatus.STABLE, is_stable=True, confidence_mean=0.9, empty_slot_count=1, unrecognized_slot_count=0, is_shop_animation=False)

    candidates = detector.evaluate_candidates(diff, obs, [], stab)
    assert len(candidates) == 1
    assert candidates[0].action_type == VisionActionType.BUY_UNIT
    assert candidates[0].target_champion == "Zoe"


def test_v22_system_refresh():
    """Verify system shop refresh suppresses false ROLL candidate."""
    detector = ActionEventDetectorV22()
    diff = StateDiff(
        timestamp_before=30.0,
        timestamp_after=30.5,
        dt_sec=0.5,
        gold_delta=-2,
        shop_slots_changed=5
    )
    obs = _create_mock_obs(30.5, gold=33)
    stab = StabilityAssessment(status=StabilityStatus.STABLE, is_stable=True, confidence_mean=0.9, empty_slot_count=0, unrecognized_slot_count=0, is_shop_animation=False)
    sys_event = ActionEvent(
        action_type=VisionActionType.UNKNOWN,
        source=ActionSource.OBSERVED,
        timestamp_sec=30.2,
        confidence=1.0,
        evidence=["System Free Refresh"],
        evidence_data={"system_event": SystemEventType.SYSTEM_SHOP_REFRESH.value}
    )

    candidates = detector.evaluate_candidates(diff, obs, [sys_event], stab)
    assert len(candidates) == 0


def test_v22_animation_filter():
    """Verify transient shop animation suppresses false BUY candidate."""
    detector = ActionEventDetectorV22()
    diff = StateDiff(
        timestamp_before=40.0,
        timestamp_after=40.5,
        dt_sec=0.5,
        gold_delta=-2,
        shop_slots_emptied=1,
        shop_changes=[SlotTransition(0, "Zoe", 2, False, None, None, True, SlotTransitionType.EMPTIED)]
    )
    obs = _create_mock_obs(40.5, gold=33)
    stab = StabilityAssessment(status=StabilityStatus.UNSTABLE_ANIMATION, is_stable=False, confidence_mean=0.2, empty_slot_count=3, unrecognized_slot_count=2, is_shop_animation=True)

    candidates = detector.evaluate_candidates(diff, obs, [], stab)
    assert len(candidates) == 0


def test_v22_same_champion_collision():
    """Verify same-champion collision (shop_changed < 3) triggers ROLL candidate."""
    detector = ActionEventDetectorV22()
    diff = StateDiff(
        timestamp_before=50.0,
        timestamp_after=50.5,
        dt_sec=0.5,
        gold_delta=-2,
        shop_slots_changed=1,  # Only 1 slot changed due to collision
        shop_changes=[SlotTransition(0, "A", 1, False, "B", 1, False, SlotTransitionType.REFRESHED)]
    )
    obs = _create_mock_obs(50.5, gold=33)
    stab = StabilityAssessment(status=StabilityStatus.STABLE, is_stable=True, confidence_mean=0.9, empty_slot_count=0, unrecognized_slot_count=0, is_shop_animation=False)

    candidates = detector.evaluate_candidates(diff, obs, [], stab)
    assert len(candidates) == 1
    assert candidates[0].action_type == VisionActionType.ROLL
    assert candidates[0].evidence_data["is_same_champion_collision"] is True


def test_v22_multiaction():
    """Verify resolution of multi-action when BUY and ROLL candidates exist in same window."""
    detector = ActionEventDetectorV22()
    diff = StateDiff(timestamp_before=60.0, timestamp_after=60.5, dt_sec=0.5)
    candidates = [
        ActionCandidate(
            action_type=VisionActionType.BUY_UNIT,
            matched_rules=[RuleName.BUY_BASELINE],
            detection_score=0.95,
            evidence=["BUY evidence"],
            evidence_data={"cost": 2},
            target_champion="Zoe"
        ),
        ActionCandidate(
            action_type=VisionActionType.ROLL,
            matched_rules=[RuleName.ROLL_BASELINE],
            detection_score=0.90,
            evidence=["ROLL evidence"],
            evidence_data={"gold_delta": -2}
        )
    ]
    resolved = detector.resolve_candidates(candidates, diff, timestamp_sec=60.5)
    assert resolved is not None
    assert resolved.action_type == VisionActionType.BUY_UNIT
    assert resolved.evidence_data["multi_action"] is True


def test_v22_ambiguous():
    """Verify resolution takes best candidate when multiple candidates of same type exist."""
    detector = ActionEventDetectorV22()
    diff = StateDiff(timestamp_before=70.0, timestamp_after=70.5, dt_sec=0.5)
    candidates = [
        ActionCandidate(action_type=VisionActionType.ROLL, matched_rules=[RuleName.ROLL_BASELINE], detection_score=0.70, evidence=["E1"], evidence_data={}),
        ActionCandidate(action_type=VisionActionType.ROLL, matched_rules=[RuleName.ROLL_BASELINE], detection_score=0.92, evidence=["E2"], evidence_data={})
    ]
    resolved = detector.resolve_candidates(candidates, diff, timestamp_sec=70.5)
    assert resolved is not None
    assert resolved.confidence == 0.92


def test_v22_adaptive_refinement():
    """Verify enable_adaptive_refinement initialization flag."""
    detector = ActionEventDetectorV22(enable_adaptive_refinement=True)
    assert detector.enable_adaptive_refinement is True


def test_v22_online_causality():
    """Verify detector processes sequentially without future frame dependency."""
    detector = ActionEventDetectorV22()
    obs1 = _create_mock_obs(80.0, gold=35)
    obs2 = _create_mock_obs(80.5, gold=33)
    events = detector.detect_actions([obs1, obs2])
    assert isinstance(events, list)


def test_v22_evidence_traceability():
    """Verify evidence_data dictionary is structured and non-empty."""
    detector = ActionEventDetectorV22()
    diff = StateDiff(
        timestamp_before=90.0,
        timestamp_after=90.5,
        dt_sec=0.5,
        gold_delta=-2,
        shop_slots_changed=2,
        shop_changes=[SlotTransition(0, "A", 1, False, "B", 1, False, SlotTransitionType.REFRESHED)]
    )
    obs = _create_mock_obs(90.5, gold=33)
    stab = StabilityAssessment(status=StabilityStatus.STABLE, is_stable=True, confidence_mean=0.9, empty_slot_count=0, unrecognized_slot_count=0, is_shop_animation=False)
    candidates = detector.evaluate_candidates(diff, obs, [], stab)
    event = detector.resolve_candidates(candidates, diff, timestamp_sec=90.5)
    assert event is not None
    assert "gold_delta" in event.evidence_data
    assert "system_refresh" in event.evidence_data


def test_v22_observed_action_status():
    """Verify emitted action events have OBSERVED status."""
    detector = ActionEventDetectorV22()
    diff = StateDiff(
        timestamp_before=100.0,
        timestamp_after=100.5,
        dt_sec=0.5,
        gold_delta=-2,
        shop_slots_changed=4,
        shop_changes=[SlotTransition(0, "A", 1, False, "B", 1, False, SlotTransitionType.REFRESHED)]
    )
    obs = _create_mock_obs(100.5, gold=33)
    stab = StabilityAssessment(status=StabilityStatus.STABLE, is_stable=True, confidence_mean=0.9, empty_slot_count=0, unrecognized_slot_count=0, is_shop_animation=False)
    candidates = detector.evaluate_candidates(diff, obs, [], stab)
    event = detector.resolve_candidates(candidates, diff, timestamp_sec=100.5)
    assert event is not None
    assert event.source == ActionSource.OBSERVED


def test_v22_no_save_gold_inference():
    """Verify NO action event is emitted on static/saving frames (no economic action)."""
    detector = ActionEventDetectorV22()
    diff = StateDiff(
        timestamp_before=110.0,
        timestamp_after=110.5,
        dt_sec=0.5,
        gold_delta=0,
        shop_slots_changed=0
    )
    obs = _create_mock_obs(110.5, gold=35)
    stab = StabilityAssessment(status=StabilityStatus.STABLE, is_stable=True, confidence_mean=0.9, empty_slot_count=0, unrecognized_slot_count=0, is_shop_animation=False)
    candidates = detector.evaluate_candidates(diff, obs, [], stab)
    event = detector.resolve_candidates(candidates, diff, timestamp_sec=110.5)
    assert event is None
