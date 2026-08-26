"""Unit tests for Domain models and GameState."""
import pytest
import sys, os

# Ensure src is on path
_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit, BoardPosition
from tft.domain.actions import Action, ActionType

def test_game_state_creation_and_serialization():
    player = PlayerState(gold=45, level=7, xp=12, hp=78, streak=3)
    unit1 = Unit(champion="소나", cost=5, star_level=2, items=["대천사의 지팡이"], position=BoardPosition(row=0, col=2))
    unit2 = Unit(champion="나서스", cost=1, star_level=3, items=["워모그의 갑옷"], slot_index=0, is_bench=True)

    state = GameState(
        stage=3,
        round=2,
        stage_round="3-2",
        player=player,
        board_units=[unit1],
        bench_units=[unit2],
        shop_units=["밀리오", "조이", None, None, None]
    )

    assert state.stage_round == "3-2"
    assert state.player.gold == 45
    assert len(state.board_units) == 1
    assert len(state.bench_units) == 1
    assert state.board_units[0].champion == "소나"
    assert state.board_units[0].star_level == 2

    # Serialization roundtrip
    d = state.to_dict()
    reconstructed = GameState.from_dict(d)

    assert reconstructed.stage_round == "3-2"
    assert reconstructed.player.gold == 45
    assert len(reconstructed.board_units) == 1
    assert reconstructed.board_units[0].champion == "소나"
