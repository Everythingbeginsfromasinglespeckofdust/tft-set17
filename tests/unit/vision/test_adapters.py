"""Unit tests for Vision Observation and Adapters."""
import pytest
import sys, os

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.vision.observation import Observation, CardObservation, UnitObservation
from tft.vision.adapters import ObservationToGameStateBuilder

def test_observation_to_game_state_builder():
    builder = ObservationToGameStateBuilder()

    obs = Observation(
        timestamp_sec=350.5,
        stage_text="3-2",
        gold_val=42,
        hp_val=85,
        level_val=6,
        xp_val=10,
        shop_cards=[
            CardObservation(slot_index=1, champion_pred="나서스", cost_pred=1, confidence=0.98, raw_ocr="나서스"),
            CardObservation(slot_index=2, champion_pred="조이", cost_pred=2, confidence=0.95, raw_ocr="조이"),
            CardObservation(slot_index=3, champion_pred=None, cost_pred=None, confidence=0.0, is_empty=True),
            CardObservation(slot_index=4, champion_pred=None, cost_pred=None, confidence=0.0, is_empty=True),
            CardObservation(slot_index=5, champion_pred=None, cost_pred=None, confidence=0.0, is_empty=True),
        ],
        field_detections=[
            UnitObservation(location="hex_r3_c3", champion_pred="소나", star_level_pred=2, items_pred=["대천사의 지팡이"])
        ],
        bench_detections=[
            UnitObservation(location="bench_0", champion_pred="나서스", star_level_pred=1)
        ]
    )

    state = builder.build(obs)

    assert state.stage == 3
    assert state.round == 2
    assert state.stage_round == "3-2"
    assert state.player.gold == 42
    assert state.player.level == 6
    assert state.player.hp == 85
    assert len(state.board_units) == 1
    assert state.board_units[0].champion == "소나"
    assert state.board_units[0].star_level == 2
    assert len(state.bench_units) == 1
    assert state.bench_units[0].champion == "나서스"
    assert state.shop_units[0] == "나서스"
    assert state.shop_units[1] == "조이"
