"""Unit tests for Decision and Explanation layers."""
import pytest
import sys, os

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState, PlayerState
from tft.domain.actions import ActionType
from tft.decision.engine import DecisionEngine

def test_decision_engine_crisis_rolls():
    engine = DecisionEngine()
    # Critical HP state -> Should recommend ROLL to stabilize
    crisis_state = GameState(
        stage=4, round=1, stage_round="4-1",
        player=PlayerState(gold=45, level=7, xp=0, hp=22)
    )
    rec = engine.decide(crisis_state)
    assert rec.recommended_action.action_type == ActionType.ROLL
    assert len(rec.reasons) >= 1

def test_decision_engine_healthy_save():
    engine = DecisionEngine()
    # Healthy state with low gold -> Should recommend SAVE_GOLD
    healthy_state = GameState(
        stage=2, round=3, stage_round="2-3",
        player=PlayerState(gold=28, level=5, xp=0, hp=92)
    )
    rec = engine.decide(healthy_state)
    assert rec.recommended_action.action_type in [ActionType.SAVE_GOLD, ActionType.LEVEL_UP]
