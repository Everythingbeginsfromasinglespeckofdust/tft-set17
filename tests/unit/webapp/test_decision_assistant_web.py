"""Unit and Integration Tests for TFT Decision Assistant Web v1."""
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
from tft.domain.actions import ActionType
from tft.decision.engine import DecisionEngine
from tft.calibration.integration.adapter import CalibrationMode
from tft.webapp.adapter import (
    HumanInputDTO,
    GameStateBuilder,
    DecisionPresenter,
    TurnDiffCalculator,
    SET18_CHAMPIONS,
    SET18_ITEMS
)
from tft.webapp.server import app

client = TestClient(app)


def test_gamestate_form_validation():
    """1. Test validation rejects invalid stage, negative gold, and accepts valid input."""
    valid_dto = HumanInputDTO(
        stage_round="4-2",
        hp=42,
        gold=38,
        level=7,
        xp=18,
        board_units=[]
    )
    ok, errs = GameStateBuilder.validate_input(valid_dto)
    assert ok is True
    assert len(errs) == 0

    invalid_dto = HumanInputDTO(
        stage_round="invalid-stage",
        hp=-10,
        gold=-5,
        level=15
    )
    ok, errs = GameStateBuilder.validate_input(invalid_dto)
    assert ok is False
    assert len(errs) >= 4


def test_champion_picker_uses_set18_data():
    """2. Test champion catalog loads strictly Set 18 normalized data."""
    res = client.get("/api/data/champions")
    assert res.status_code == 200
    champs = res.json()
    assert len(champs) == 64
    names = [c["name"] for c in champs]
    assert "Akali" in names
    assert "Diana" in names
    assert "Lux" in names
    assert "Nasus" not in names  # Set 17 champion must NOT be present


def test_item_picker_uses_set18_data():
    """3. Test items catalog loads Set 18 items."""
    res = client.get("/api/data/items")
    assert res.status_code == 200
    items = res.json()
    assert len(items) > 0


def test_state_builder():
    """4. Test building canonical GameState from HumanInputDTO."""
    dto = HumanInputDTO(
        stage_round="4-2",
        hp=42,
        gold=38,
        level=7,
        xp=18,
        board_units=[
            {"champion": "Diana", "cost": 3, "star_level": 2, "items": []},
            {"champion": "Akali", "cost": 1, "star_level": 2, "items": []}
        ],
        bench_units=[
            {"champion": "Zoe", "cost": 2, "star_level": 1, "items": []}
        ],
        shop_units=["Diana", None, "Akali", None, None]
    )
    dto_obj = HumanInputDTO.from_dict(dto.__dict__)
    state = GameStateBuilder.build_game_state(dto_obj)

    assert isinstance(state, GameState)
    assert state.stage == 4
    assert state.round == 2
    assert state.stage_round == "4-2"
    assert state.player.hp == 42
    assert state.player.gold == 38
    assert state.player.level == 7
    assert len(state.board_units) == 2
    assert len(state.bench_units) == 1
    assert state.shop_units[0] == "Diana"
    assert state.shop_units[1] is None


def test_incremental_turn_copy():
    """5. Test turn copy logic preserves board/bench state."""
    dto1 = HumanInputDTO(
        stage_round="4-1",
        hp=52,
        gold=46,
        level=7,
        board_units=[{"champion": "Diana", "cost": 3, "star_level": 2, "items": []}]
    )
    # Simulate turn copy and advance stage
    dto2_dict = dict(dto1.__dict__)
    dto2_dict["stage_round"] = "4-2"
    dto2_dict["hp"] = 42
    dto2_dict["gold"] = 38
    dto2 = HumanInputDTO.from_dict(dto2_dict)

    assert dto2.stage_round == "4-2"
    assert dto2.hp == 42
    assert dto2.gold == 38
    assert len(dto2.board_units) == 1
    assert dto2.board_units[0].champion == "Diana"


def test_turn_diff():
    """6. Test computing diff metrics between two consecutive turns."""
    prev = HumanInputDTO(stage_round="4-1", hp=52, gold=46, level=7, board_units=[{"champion": "Diana", "cost": 3}])
    curr = HumanInputDTO(stage_round="4-2", hp=42, gold=38, level=7, board_units=[
        {"champion": "Diana", "cost": 3},
        {"champion": "Akali", "cost": 1}
    ])
    diff = TurnDiffCalculator.compute_turn_diff(prev, curr)

    assert diff["hp"]["diff"] == -10
    assert diff["gold"]["diff"] == -8
    assert diff["level"]["diff"] == 0
    assert diff["board"]["added_units"] == ["Akali"]


def test_decision_engine_integration():
    """7. Test POST /api/decide executes Frozen DecisionEngine cleanly."""
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
    assert "recommended_action" in data
    assert data["recommended_action"] in ("ROLL", "SAVE_GOLD", "LEVEL_UP")
    assert "score" in data
    assert "action_score_gap" in data
    assert "all_scores" in data
    assert len(data["all_scores"]) == 3
    assert "current_direction" in data
    assert "now" in data["current_direction"]
    assert "watch" in data["current_direction"]
    assert "then" in data["current_direction"]


def test_recommendation_display_model():
    """8. Test DecisionPresenter output schema contains all required fields."""
    engine = DecisionEngine()
    state = GameState(
        stage=4,
        round=2,
        stage_round="4-2",
        player=PlayerState(gold=38, level=7, xp=18, hp=42)
    )
    rec = engine.decide(state)
    resp = DecisionPresenter.format_decision_response(state, rec)

    assert "recommended_action" in resp
    assert "all_scores" in resp
    for asc in resp["all_scores"]:
        assert "action" in asc
        assert "score" in asc
        assert "breakdown" in asc
        assert "survival" in asc["breakdown"]
        assert "economy" in asc["breakdown"]
        assert "board_power" in asc["breakdown"]
        assert "upgrade" in asc["breakdown"]


def test_prediction_immutability():
    """9. Test engine prediction remains immutable when saving human review."""
    session_id = "TEST_SESSION_IMMUTABLE"
    payload = {
        "session_id": session_id,
        "turns": [
            {
                "turn_id": "T1",
                "stage_round": "4-2",
                "state": {"hp": 42, "gold": 38},
                "decision": {
                    "recommended_action": "SAVE_GOLD",
                    "score": 0.3478,
                    "action_score_gap": 0.0164,
                    "all_scores": [{"action": "SAVE_GOLD", "score": 0.3478}],
                    "reasons": []
                },
                "actual_player_action": "ROLL",
                "human_preferred_action": "ROLL",
                "human_feedback": "QUESTIONABLE",
                "notes": "Player wanted to roll for Diana 3"
            }
        ]
    }
    res = client.post("/api/sessions/save", json=payload)
    assert res.status_code == 200

    # Load session
    load_res = client.get(f"/api/sessions/{session_id}")
    assert load_res.status_code == 200
    loaded = load_res.json()
    t0 = loaded["turns"][0]
    assert t0["decision"]["recommended_action"] == "SAVE_GOLD"  # Untouched
    assert t0["human_feedback"] == "QUESTIONABLE"
    assert t0["actual_player_action"] == "ROLL"


def test_human_feedback_separation():
    """10. Test explicit separation of actual action, human preference, and engine recommendation."""
    payload = {
        "session_id": "TEST_SEPARATION",
        "turns": [
            {
                "turn_id": "T1",
                "stage_round": "3-2",
                "decision": {"recommended_action": "SAVE_GOLD"},
                "actual_player_action": "LEVEL_UP",
                "human_preferred_action": "ROLL",
                "human_feedback": "WRONG"
            }
        ]
    }
    client.post("/api/sessions/save", json=payload)
    res = client.get("/api/sessions/TEST_SEPARATION")
    turn = res.json()["turns"][0]

    assert turn["decision"]["recommended_action"] == "SAVE_GOLD"
    assert turn["actual_player_action"] == "LEVEL_UP"
    assert turn["human_preferred_action"] == "ROLL"
    assert turn["human_feedback"] == "WRONG"


def test_actual_action_separation():
    """11. Test actual player action can be UNKNOWN or distinct."""
    dto = HumanInputDTO(actual_player_action="ROLL")
    assert dto.actual_player_action == "ROLL"
    assert dto.human_preferred_action == "UNKNOWN"


def test_human_preference_separation():
    """12. Test human preference can be distinct from actual action."""
    dto = HumanInputDTO(actual_player_action="SAVE_GOLD", human_preferred_action="LEVEL_UP")
    assert dto.actual_player_action != dto.human_preferred_action


def test_blind_review_order():
    """13. Test blind review parameters in input DTO."""
    dto = HumanInputDTO(
        actual_player_action="UNKNOWN",
        human_preferred_action="ROLL",
        notes="Reviewed blind before reveal"
    )
    assert dto.human_preferred_action == "ROLL"


def test_session_persistence():
    """14. Test session listing and full detail retrieval."""
    sid = "TEST_SESSION_PERSIST"
    client.post("/api/sessions/save", json={
        "session_id": sid,
        "turns": [{"turn_id": "T1", "stage_round": "2-1", "state": {"hp": 100}}]
    })
    list_res = client.get("/api/sessions/list")
    assert list_res.status_code == 200
    s_ids = [s["session_id"] for s in list_res.json()]
    assert sid in s_ids


def test_video_timestamp_persistence():
    """15. Test video timestamp is saved with turn checkpoint."""
    payload = {
        "stage_round": "4-2",
        "hp": 42,
        "gold": 38,
        "level": 7,
        "video_timestamp_sec": 305.4
    }
    res = client.post("/api/decide", json=payload)
    assert res.status_code == 200
    meta = res.json()["input_metadata"]
    assert meta["video_timestamp_sec"] == 305.4


def test_dataset_export():
    """16. Test POST /api/export/dataset creates valid dataset."""
    res = client.post("/api/export/dataset")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert "exported_records" in data
    assert os.path.exists(data["export_path"])


def test_missing_required_state():
    """17. Test missing or malformed payload returns 400."""
    res = client.post("/api/decide", json={"stage_round": "invalid"})
    assert res.status_code == 422


def test_invalid_champion_rejected():
    """18. Test invalid/non-Set 18 champion throws 422 with error list."""
    payload = {
        "stage_round": "4-2",
        "hp": 50,
        "gold": 30,
        "level": 7,
        "board_units": [{"champion": "NonExistentChampion999"}]
    }
    res = client.post("/api/decide", json=payload)
    assert res.status_code == 422
    err_detail = res.json()["detail"]
    assert any("not in Set 18 roster" in e for e in err_detail.get("errors", []))


def test_invalid_item_rejected():
    """19. Test excess item count throws error."""
    payload = {
        "stage_round": "4-2",
        "hp": 50,
        "gold": 30,
        "level": 7,
        "board_units": [{
            "champion": "Diana",
            "items": ["Item1", "Item2", "Item3", "Item4"]  # Max 3 allowed
        }]
    }
    res = client.post("/api/decide", json=payload)
    assert res.status_code == 422


def test_calibration_off_by_default():
    """20. Test calibration mode defaults to OFF."""
    payload = {
        "stage_round": "4-2",
        "hp": 50,
        "gold": 30,
        "level": 7
    }
    res = client.post("/api/decide", json=payload)
    assert res.status_code == 200
    calib = res.json()["calibration"]
    assert calib["mode"] == "OFF"
    assert calib["applied"] is False
