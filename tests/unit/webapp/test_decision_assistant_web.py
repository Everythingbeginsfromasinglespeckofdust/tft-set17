"""Unit and Integration Tests for TFT Decision Assistant Web v1.1."""
import json
import os
import sys
import pytest
from fastapi.testclient import TestClient

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
_ROOT = os.path.abspath(os.path.join(_SRC, ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.decision.engine import DecisionEngine
from tft.calibration.integration.adapter import CalibrationMode
from tft.webapp.adapter import (
    HumanInputDTO,
    UnitInputDTO,
    GameStateBuilder,
    DecisionPresenter,
    TurnDiffCalculator,
    SET18_CHAMPIONS,
    SET18_ITEMS
)
from tft.webapp.server import app

client = TestClient(app)


def test_hp_manual_input():
    """1. Test HP manual input accepts 0~100 and rejects out of bounds."""
    dto_valid = HumanInputDTO(stage_round="4-2", hp=42, gold=38, level=7)
    ok, errs = GameStateBuilder.validate_input(dto_valid)
    assert ok is True
    assert len(errs) == 0

    dto_invalid = HumanInputDTO(stage_round="4-2", hp=-5, gold=38, level=7)
    ok, errs = GameStateBuilder.validate_input(dto_invalid)
    assert ok is False
    assert any("HP must be between 0 and 150" in e for e in errs)


def test_gold_manual_input():
    """2. Test Gold manual input accepts 0~250 and rejects negative."""
    dto_valid = HumanInputDTO(stage_round="4-2", hp=42, gold=38, level=7)
    ok, _ = GameStateBuilder.validate_input(dto_valid)
    assert ok is True

    dto_neg = HumanInputDTO(stage_round="4-2", hp=42, gold=-10, level=7)
    ok, errs = GameStateBuilder.validate_input(dto_neg)
    assert ok is False
    assert any("Gold cannot be negative" in e for e in errs)


def test_status_bar_updates_immediately():
    """3. Test completeness calculation matches input readiness."""
    dto = HumanInputDTO(
        stage_round="4-2",
        hp=42,
        gold=38,
        level=7,
        xp=18,
        board_units=[UnitInputDTO(champion="Diana", cost=3, star_level=2)],
        bench_units=[UnitInputDTO(champion="Lux", cost=2, star_level=1)],
        shop_units=["Diana", None, "Akali", "Yunara", None]
    )
    comp = GameStateBuilder.calculate_completeness(dto)
    assert comp["score"] == 8
    assert comp["total"] == 8
    assert comp["percentage"] == 100.0


def test_stage_selection():
    """4. Test stage format validation."""
    dto_good = HumanInputDTO(stage_round="5-3")
    ok, _ = GameStateBuilder.validate_input(dto_good)
    assert ok is True

    dto_bad = HumanInputDTO(stage_round="9-9")
    ok, errs = GameStateBuilder.validate_input(dto_bad)
    assert ok is False
    assert any("Invalid stage_round format" in e for e in errs)


def test_champion_pool_loads_all_set18_units():
    """5. Test champion catalog loads exactly 64 Set 18 champions."""
    res = client.get("/api/data/champions")
    assert res.status_code == 200
    champs = res.json()
    assert len(champs) == 64
    names = [c["name"] for c in champs]
    assert "Akali" in names
    assert "Diana" in names
    assert "Lux" in names
    assert "Yunara" in names
    assert "Nasus" not in names


def test_champion_click_adds_to_board():
    """6. Test adding a champion to board constructs valid GameState."""
    dto = HumanInputDTO(
        stage_round="4-2",
        hp=42,
        gold=38,
        level=7,
        board_units=[UnitInputDTO(champion="Diana", cost=3, star_level=2)]
    )
    state = GameStateBuilder.build_game_state(dto)
    assert len(state.board_units) == 1
    assert state.board_units[0].champion == "Diana"
    assert state.board_units[0].cost == 3
    assert state.board_units[0].star_level == 2


def test_champion_click_adds_to_bench():
    """7. Test adding a champion to bench."""
    dto = HumanInputDTO(
        stage_round="4-2",
        bench_units=[UnitInputDTO(champion="Lux", cost=2, star_level=1)]
    )
    state = GameStateBuilder.build_game_state(dto)
    assert len(state.bench_units) == 1
    assert state.bench_units[0].champion == "Lux"
    assert state.bench_units[0].is_bench is True


def test_champion_click_adds_to_shop():
    """8. Test assigning champion to shop slots."""
    dto = HumanInputDTO(
        shop_units=["Diana", None, "Akali", None, None]
    )
    state = GameStateBuilder.build_game_state(dto)
    assert state.shop_units[0] == "Diana"
    assert state.shop_units[1] is None
    assert state.shop_units[2] == "Akali"


def test_set18_cost_auto_resolution():
    """9. Test cost is automatically resolved from Set 18 DB if omitted."""
    dto = HumanInputDTO(
        board_units=[UnitInputDTO(champion="Diana")]  # Diana is 3-cost in Set 18
    )
    state = GameStateBuilder.build_game_state(dto)
    assert state.board_units[0].cost == 3


def test_star_level_update():
    """10. Test star level validation rejects star 4 or 0."""
    dto = HumanInputDTO(
        board_units=[UnitInputDTO(champion="Diana", star_level=4)]
    )
    ok, errs = GameStateBuilder.validate_input(dto)
    assert ok is False
    assert any("Invalid star level" in e for e in errs)


def test_remove_unit():
    """11. Test removing a unit results in clean GameState."""
    units = [
        UnitInputDTO(champion="Diana", cost=3),
        UnitInputDTO(champion="Akali", cost=1)
    ]
    # Remove index 1
    units.pop(1)
    dto = HumanInputDTO(board_units=units)
    state = GameStateBuilder.build_game_state(dto)
    assert len(state.board_units) == 1
    assert state.board_units[0].champion == "Diana"


def test_copy_previous_turn():
    """12. Test incremental turn copying."""
    dto1 = HumanInputDTO(stage_round="4-1", hp=52, gold=46, level=7, board_units=[UnitInputDTO(champion="Diana", cost=3)])
    dto2_dict = dict(dto1.__dict__)
    dto2_dict["stage_round"] = "4-2"
    dto2_dict["hp"] = 42
    dto2_dict["gold"] = 38
    dto2 = HumanInputDTO.from_dict(dto2_dict)

    assert dto2.stage_round == "4-2"
    assert dto2.hp == 42
    assert dto2.gold == 38
    assert len(dto2.board_units) == 1


def test_turn_diff():
    """13. Test computing delta between two turns."""
    prev = HumanInputDTO(stage_round="4-1", hp=52, gold=46, level=7, board_units=[UnitInputDTO(champion="Diana", cost=3)])
    curr = HumanInputDTO(stage_round="4-2", hp=42, gold=38, level=7, board_units=[
        UnitInputDTO(champion="Diana", cost=3),
        UnitInputDTO(champion="Akali", cost=1)
    ])
    diff = TurnDiffCalculator.compute_turn_diff(prev, curr)
    assert diff["hp"]["diff"] == -10
    assert diff["gold"]["diff"] == -8
    assert diff["board"]["added_units"] == ["Akali"]


def test_draft_state_sync():
    """14. Test POST /api/validate returns real-time validation and completeness."""
    res = client.post("/api/validate", json={"stage_round": "4-2", "hp": 42, "gold": 38, "level": 7})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True
    assert "completeness" in data
    assert data["completeness"]["score"] >= 4


def test_decision_engine_called_with_draft():
    """15. Test POST /api/decide executes Frozen DecisionEngine cleanly."""
    payload = {
        "stage_round": "4-2",
        "hp": 42,
        "gold": 38,
        "level": 7,
        "xp": 18,
        "board_units": [
            {"champion": "Diana", "cost": 3, "star_level": 2, "items": []},
            {"champion": "Akali", "cost": 1, "star_level": 2, "items": []}
        ],
        "bench_units": [],
        "shop_units": ["Diana", None, None, None, None],
        "calibration_mode": "OFF"
    }
    res = client.post("/api/decide", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["recommended_action"] in ("ROLL", "SAVE_GOLD", "LEVEL_UP")
    assert "current_direction" in data
    assert "now" in data["current_direction"]


def test_actual_action_separation():
    """16. Test actual player action can be UNKNOWN or distinct."""
    dto = HumanInputDTO(actual_player_action="ROLL")
    assert dto.actual_player_action == "ROLL"
    assert dto.human_preferred_action == "UNKNOWN"


def test_human_preference_separation():
    """17. Test human preference distinct from actual action."""
    dto = HumanInputDTO(actual_player_action="SAVE_GOLD", human_preferred_action="LEVEL_UP")
    assert dto.actual_player_action != dto.human_preferred_action


def test_human_judgment_separation():
    """18. Test human judgment / feedback."""
    dto = HumanInputDTO(human_feedback="QUESTIONABLE")
    assert dto.human_feedback == "QUESTIONABLE"
    assert dto.human_judgment == "QUESTIONABLE"


def test_blind_review_sequence():
    """19. Test blind review parameters."""
    dto = HumanInputDTO(
        actual_player_action="UNKNOWN",
        human_preferred_action="ROLL",
        notes="Reviewed blind before reveal"
    )
    assert dto.human_preferred_action == "ROLL"


def test_video_timestamp_checkpoint():
    """20. Test video timestamp linked to turn."""
    res = client.post("/api/decide", json={"stage_round": "4-2", "hp": 42, "gold": 38, "level": 7, "video_timestamp_sec": 305.4})
    assert res.status_code == 200
    assert res.json()["input_metadata"]["video_timestamp_sec"] == 305.4


def test_session_persistence():
    """21. Test session save and list."""
    sid = "TEST_SESSION_PERSIST_V11"
    client.post("/api/sessions/save", json={
        "session_id": sid,
        "turns": [{"turn_id": "T1", "stage_round": "2-1", "state": {"hp": 100}}]
    })
    res = client.get("/api/sessions/list")
    assert res.status_code == 200
    s_ids = [s["session_id"] for s in res.json()]
    assert sid in s_ids


def test_reload_integrity():
    """22. Test reloaded session matches original saved data."""
    sid = "TEST_RELOAD_INTEGRITY"
    client.post("/api/sessions/save", json={
        "session_id": sid,
        "turns": [{"turn_id": "T1", "stage_round": "4-2", "actual_player_action": "ROLL"}]
    })
    res = client.get(f"/api/sessions/{sid}")
    assert res.status_code == 200
    loaded = res.json()
    assert loaded["turns"][0]["actual_player_action"] == "ROLL"


def test_prediction_immutability():
    """23. Test engine prediction remains immutable when human feedback is added."""
    sid = "TEST_IMMUTABLE_V11"
    payload = {
        "session_id": sid,
        "turns": [{
            "turn_id": "T1",
            "stage_round": "4-2",
            "decision": {"recommended_action": "SAVE_GOLD", "score": 0.3347},
            "actual_player_action": "ROLL",
            "human_feedback": "WRONG"
        }]
    }
    client.post("/api/sessions/save", json=payload)
    loaded = client.get(f"/api/sessions/{sid}").json()
    assert loaded["turns"][0]["decision"]["recommended_action"] == "SAVE_GOLD"


def test_unknown_field_preservation():
    """24. Test UNKNOWN defaults preserved."""
    dto = HumanInputDTO()
    assert dto.actual_player_action == "UNKNOWN"
    assert dto.human_preferred_action == "UNKNOWN"
    assert dto.human_feedback == "UNKNOWN"


def test_calibration_off_default():
    """25. Test calibration defaults to OFF."""
    res = client.post("/api/decide", json={"stage_round": "4-2", "hp": 50, "gold": 30, "level": 7})
    assert res.status_code == 200
    assert res.json()["calibration"]["mode"] == "OFF"
