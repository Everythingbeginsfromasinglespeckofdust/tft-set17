"""Comprehensive Unit Tests for DecisionEngine v1 and ActionScorer."""
import pytest
import sys, os

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.domain.actions import ActionType
from tft.decision.engine import DecisionEngine
from tft.decision.scorer import DecisionConfig

def test_decision_engine_crisis_mode_recommends_roll():
    """In crisis (HP <= 30), DecisionEngine should prioritize ROLL to prevent defeat."""
    engine = DecisionEngine(random_seed=42)
    crisis_state = GameState(
        stage=4,
        round=1,
        stage_round="4-1",
        player=PlayerState(gold=42, level=7, xp=0, hp=24),
        board_units=[
            Unit(champion="소나", cost=5, star_level=1),
            Unit(champion="조이", cost=2, star_level=1),
            Unit(champion="나서스", cost=1, star_level=2),
        ],
        bench_units=[
            Unit(champion="조이", cost=2, star_level=1), # Pair looking for 2★
            Unit(champion="벨베스", cost=4, star_level=1),
        ]
    )

    rec = engine.decide(crisis_state, horizon=3)

    assert rec.recommended_action.action_type == ActionType.ROLL
    assert len(rec.alternatives) == 2
    assert len(rec.all_scores) == 3
    # Check that reasons contain structured evidence
    assert any(r.code in ["CRISIS_ROLL_DEFENSE", "CRISIS_ROLL_SURVIVAL", "ROLL_POWER_INCREASE"] for r in rec.reasons)
    # Check top score is highest
    assert rec.score >= rec.alternatives[0].score

def test_decision_engine_healthy_economy_recommends_save():
    """In healthy state (HP >= 80, Gold < 50), DecisionEngine should prioritize SAVE_GOLD for compound interest."""
    engine = DecisionEngine(random_seed=42)
    healthy_state = GameState(
        stage=2,
        round=3,
        stage_round="2-3",
        player=PlayerState(gold=28, level=5, xp=0, hp=92),
        board_units=[
            Unit(champion="나서스", cost=1, star_level=2),
            Unit(champion="조이", cost=2, star_level=2),
        ]
    )

    rec = engine.decide(healthy_state, horizon=3)

    assert rec.recommended_action.action_type == ActionType.SAVE_GOLD
    assert any("SAVE" in r.code or "ECONOMIC" in r.code for r in rec.reasons)

def test_decision_engine_level_up_timing():
    """When gold is abundant and near level-up breakpoint, LEVEL_UP should be highly scored."""
    engine = DecisionEngine(random_seed=42)
    lvl_state = GameState(
        stage=3,
        round=5,
        stage_round="3-5",
        player=PlayerState(gold=54, level=6, xp=56, hp=70), # 4 XP away from Lv.7 (1 click = 4G)
        board_units=[
            Unit(champion="나서스", cost=1, star_level=2),
            Unit(champion="소나", cost=5, star_level=1),
        ],
        bench_units=[
            Unit(champion="벨베스", cost=4, star_level=2), # Strong unit ready to be fielded
        ]
    )

    rec = engine.decide(lvl_state, horizon=3)

    assert rec.recommended_action.action_type in [ActionType.LEVEL_UP, ActionType.SAVE_GOLD, ActionType.ROLL]
    # LEVEL_UP score should be very competitive (> 0.50)
    lvl_score = next(s for s in rec.all_scores if s.action.action_type == ActionType.LEVEL_UP)
    assert lvl_score.score > 0.45

def test_edge_cases_empty_board_and_zero_resources():
    """Verify engine handles edge cases gracefully without throwing exceptions."""
    engine = DecisionEngine(random_seed=42)
    zero_state = GameState(
        stage=1,
        round=1,
        stage_round="1-1",
        player=PlayerState(gold=0, level=1, xp=0, hp=0),
        board_units=[],
        bench_units=[]
    )

    rec = engine.decide(zero_state, horizon=1)
    assert rec.recommended_action is not None
    assert len(rec.all_scores) == 3
