"""Integration tests for TFT DecisionService."""
import pytest
import sys, os

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.application.services import DecisionService

def test_decision_service_full_workflow():
    service = DecisionService()
    state = GameState(
        stage=3, round=2, stage_round="3-2",
        player=PlayerState(gold=52, level=6, xp=4, hp=75),
        board_units=[
            Unit(champion="나서스", cost=1, star_level=2),
            Unit(champion="조이", cost=2, star_level=2)
        ]
    )

    report = service.analyze_and_recommend(state)
    assert "board_evaluation" in report
    assert "economy_evaluation" in report
    assert "survival_evaluation" in report
    assert "recommendation" in report
    assert report["board_evaluation"]["total_power"] > 0
    assert report["recommendation"]["action"] in ["SAVE_GOLD", "LEVEL_UP", "ROLL"]
