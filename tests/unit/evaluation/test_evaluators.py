"""Unit tests for Evaluation layer."""
import pytest
import sys, os

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.evaluation.board_evaluator import BoardEvaluator
from tft.evaluation.economy_evaluator import EconomyEvaluator
from tft.evaluation.survival_evaluator import SurvivalEvaluator

def test_board_evaluator():
    evaluator = BoardEvaluator()
    # 2-star Sona (cost 5, 2★ -> 5 * 2.2 = 11.0) with completed item (+3.0) -> 14.0
    sona = Unit(champion="소나", cost=5, star_level=2, items=["대천사의 지팡이"])
    state = GameState(
        stage=3, round=5, stage_round="3-5",
        player=PlayerState(gold=30, level=6, xp=0),
        board_units=[sona]
    )

    res = evaluator.evaluate(state)
    assert res.score >= 14.0
    assert "unit_power" in res.metrics
    assert "item_score" in res.metrics

def test_economy_evaluator():
    evaluator = EconomyEvaluator()
    state = GameState(
        stage=2, round=1, stage_round="2-1",
        player=PlayerState(gold=38, level=4, xp=2)
    )
    res = evaluator.evaluate(state)
    assert res.metrics["current_interest"] == 3 # 38 // 10 = 3
    assert res.metrics["gold_to_next_level"] > 0

def test_survival_evaluator():
    evaluator = SurvivalEvaluator()
    safe_state = GameState(stage=2, round=1, stage_round="2-1", player=PlayerState(gold=10, level=4, xp=0, hp=95))
    crisis_state = GameState(stage=5, round=1, stage_round="5-1", player=PlayerState(gold=10, level=8, xp=0, hp=15))

    safe_res = evaluator.evaluate(safe_state)
    crisis_res = evaluator.evaluate(crisis_state)

    assert safe_res.details["risk_level"] == "SAFE"
    assert crisis_res.details["risk_level"] == "CRITICAL"
    assert crisis_res.score > safe_res.score
