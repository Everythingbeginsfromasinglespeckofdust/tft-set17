"""Unit tests for Simulation layer."""
import pytest
import sys, os

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState, PlayerState
from tft.simulation.future_state import FutureStateSimulator

def test_future_state_simulator():
    simulator = FutureStateSimulator()
    state = GameState(
        stage=3, round=2, stage_round="3-2",
        player=PlayerState(gold=40, level=6, xp=10)
    )

    save_res = simulator.simulate_strategy(state, {"action": "save_interest"}, horizon=3)
    assert save_res.horizon_turns == 3
    assert save_res.final_gold > 40
    assert len(save_res.turn_by_turn) == 3

    lvl_res = simulator.simulate_strategy(state, {"action": "levelup", "target_level": 7}, horizon=2)
    assert lvl_res.final_level >= 6
