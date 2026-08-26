"""Comprehensive Unit Tests for FutureStateSimulator."""
import pytest
import sys, os

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit, BoardPosition
from tft.domain.actions import Action, ActionType
from tft.simulation.future_state import FutureStateSimulator

def create_sample_state(gold=40, level=6, xp=8, hp=75, stage=3, round_num=2):
    return GameState(
        stage=stage,
        round=round_num,
        stage_round=f"{stage}-{round_num}",
        player=PlayerState(gold=gold, level=level, xp=xp, hp=hp),
        board_units=[
            Unit(champion="소나", cost=5, star_level=1),
            Unit(champion="나서스", cost=1, star_level=2),
            Unit(champion="조이", cost=2, star_level=1),
        ],
        bench_units=[
            Unit(champion="조이", cost=2, star_level=1), # Pair with board Zoe (2 copies -> needs 1 more)
            Unit(champion="벨베스", cost=4, star_level=1),
        ]
    )

def test_game_state_immutability():
    """Verify simulation does not mutate the original GameState."""
    simulator = FutureStateSimulator()
    state = create_sample_state(gold=40, level=6, xp=8, hp=75)

    original_gold = state.player.gold
    original_level = state.player.level
    original_hp = state.player.hp
    original_units_len = len(state.board_units)

    # Run simulations
    simulator.simulate(state, Action(ActionType.SAVE_GOLD), horizon=3)
    simulator.simulate(state, Action(ActionType.LEVEL_UP), horizon=3)
    simulator.simulate(state, Action(ActionType.ROLL, budget_gold=20), horizon=3)

    # Assert original state remains pristine
    assert state.player.gold == original_gold
    assert state.player.level == original_level
    assert state.player.hp == original_hp
    assert len(state.board_units) == original_units_len

def test_save_gold_simulation_compounding():
    """Verify SAVE_GOLD calculates compounding interest and passive XP."""
    simulator = FutureStateSimulator()
    state = create_sample_state(gold=40, level=6, xp=8, hp=80)

    res = simulator.simulate(state, Action(ActionType.SAVE_GOLD), horizon=3)

    assert res.horizon == 3
    assert res.expected_gold >= 65.0
    assert len(res.turn_by_turn) == 3
    assert res.turn_by_turn[0].interest_earned == 4
    assert res.turn_by_turn[2].interest_earned == 5
    assert res.turn_by_turn[2].end_xp == 8 + 6 # +2 XP per turn * 3

def test_level_up_simulation_capacity():
    """Verify LEVEL_UP purchases XP, increases level and board capacity power."""
    simulator = FutureStateSimulator()
    # Level 7 requires 60 XP total from Lv.6. If current XP=40, needed=20 XP (5 clicks = 20G).
    state = create_sample_state(gold=36, level=6, xp=40, hp=80)

    res = simulator.simulate(state, Action(ActionType.LEVEL_UP, target_level=7), horizon=3)

    assert res.turn_by_turn[0].end_level == 7
    assert res.turn_by_turn[0].spent_gold == 20
    assert res.turn_by_turn[0].end_gold == 22 # 36 - 20 + 1 (interest) + 5 = 22
    assert res.expected_board_power > res.turn_by_turn[0].board_power or res.expected_board_power > 15.0
    # Expected gold after 3 turns should be much less than SAVE_GOLD (which would reach ~60G+)
    assert res.expected_gold < 45.0

def test_roll_simulation_upgrades():
    """Verify ROLL detects candidate pairs and calculates upgrade probability & power gain."""
    simulator = FutureStateSimulator()
    state = create_sample_state(gold=30, level=6, xp=0, hp=28)

    res = simulator.simulate(state, Action(ActionType.ROLL, budget_gold=20), horizon=3)

    assert res.upgrade_probability > 0.0
    assert res.metadata["num_rolls"] == 10
    assert res.expected_board_power > 0
    assert res.survival_probability >= 0.0

def test_deterministic_simulation_seed():
    """Verify same random seed produces identical simulation outcomes."""
    state = create_sample_state(gold=30, level=6, xp=0, hp=50)

    sim1 = FutureStateSimulator(random_seed=42)
    sim2 = FutureStateSimulator(random_seed=42)

    res1 = sim1.simulate(state, Action(ActionType.ROLL, budget_gold=20), horizon=3)
    res2 = sim2.simulate(state, Action(ActionType.ROLL, budget_gold=20), horizon=3)

    assert res1.expected_gold == res2.expected_gold
    assert res1.expected_hp == res2.expected_hp
    assert res1.expected_board_power == res2.expected_board_power
    assert res1.upgrade_probability == res2.upgrade_probability
