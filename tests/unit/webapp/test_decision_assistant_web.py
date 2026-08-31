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
    assert any("HP" in e or "체력" in e for e in errs)


def test_gold_manual_input():
    """2. Test Gold manual input accepts 0~250 and rejects negative."""
    dto_valid = HumanInputDTO(stage_round="4-2", hp=42, gold=38, level=7)
    ok, _ = GameStateBuilder.validate_input(dto_valid)
    assert ok is True

    dto_neg = HumanInputDTO(stage_round="4-2", hp=42, gold=-10, level=7)
    ok, errs = GameStateBuilder.validate_input(dto_neg)
    assert ok is False
    assert any("Gold" in e or "골드" in e for e in errs)


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
    assert any("stage" in e.lower() or "스테이지" in e for e in errs)


def test_champion_pool_loads_all_set18_units():
    """5. Test champion catalog loads exactly 64 Set 18 champions with Korean names."""
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
    assert any(c.get("name_ko") == "아칼리" for c in champs)
    assert any(c.get("name_ko") == "다이애나" for c in champs)


def test_champion_click_adds_to_board():
    """6. Test adding unit to board via DTO."""
    dto = HumanInputDTO(
        board_units=[
            UnitInputDTO(champion="Akali", cost=1, star_level=2),
            UnitInputDTO(champion="Diana", cost=3, star_level=1)
        ]
    )
    st = GameStateBuilder.build_game_state(dto)
    assert len(st.board_units) == 2
    assert st.board_units[0].champion == "Akali"
    assert st.board_units[0].star_level == 2
    assert st.board_units[1].champion == "Diana"


def test_champion_click_adds_to_bench():
    """7. Test adding unit to bench via DTO."""
    dto = HumanInputDTO(
        bench_units=[
            UnitInputDTO(champion="Lux", cost=2, star_level=1, is_bench=True)
        ]
    )
    st = GameStateBuilder.build_game_state(dto)
    assert len(st.bench_units) == 1
    assert st.bench_units[0].champion == "Lux"
    assert st.bench_units[0].is_bench is True


def test_champion_click_adds_to_shop():
    """8. Test 5-slot shop configuration."""
    dto = HumanInputDTO(
        shop_units=["Akali", "Diana", None, "Lux", "Yunara"]
    )
    st = GameStateBuilder.build_game_state(dto)
    assert len(st.shop_units) == 5
    assert st.shop_units[0] == "Akali"
    assert st.shop_units[1] == "Diana"
    assert st.shop_units[2] is None
    assert st.shop_units[3] == "Lux"
    assert st.shop_units[4] == "Yunara"


def test_cost_filters():
    """9. Test filtering champions by cost."""
    champs = [c for c in SET18_CHAMPIONS.values() if isinstance(c, dict) and "cost" in c]
    unique_map = {c["name"]: c for c in champs}
    one_costs = [c for c in unique_map.values() if c.get("cost") == 1]
    five_costs = [c for c in unique_map.values() if c.get("cost") == 5]
    assert len(one_costs) > 0
    assert len(five_costs) > 0


def test_star_level_update():
    """10. Test star level validation rejects star 4 or 0."""
    dto = HumanInputDTO(
        board_units=[UnitInputDTO(champion="Diana", star_level=4)]
    )
    ok, errs = GameStateBuilder.validate_input(dto)
    assert ok is False
    assert any("star" in e.lower() or "성급" in e for e in errs)


def test_board_unit_deletion():
    """11. Test removing a unit from board."""
    dto = HumanInputDTO(
        board_units=[
            UnitInputDTO(champion="Akali", star_level=1),
            UnitInputDTO(champion="Diana", star_level=2)
        ]
    )
    dto.board_units.pop(0)
    st = GameStateBuilder.build_game_state(dto)
    assert len(st.board_units) == 1
    assert st.board_units[0].champion == "Diana"


def test_clear_shop():
    """12. Test emptying the shop."""
    dto = HumanInputDTO(shop_units=[None] * 5)
    st = GameStateBuilder.build_game_state(dto)
    assert st.shop_units == [None, None, None, None, None]


def test_analyze_button_executes_decision():
    """13. Test /api/decide endpoint executes DecisionEngine."""
    payload = {
        "stage_round": "4-2",
        "hp": 42,
        "gold": 38,
        "level": 7,
        "xp": 12,
        "board_units": [{"champion": "Diana", "cost": 3, "star_level": 2}],
        "bench_units": [{"champion": "Lux", "cost": 2, "star_level": 1}],
        "shop_units": ["Diana", None, "Akali", None, None]
    }
    res = client.post("/api/decide", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "recommended_action" in data
    assert data["recommended_action"] in ["ROLL", "SAVE_GOLD", "LEVEL_UP"]
    assert "action_score_gap" in data
    assert "current_direction" in data
    assert "now" in data["current_direction"]


def test_recommendation_display():
    """14. Test recommendation output structure."""
    payload = {"stage_round": "4-2", "hp": 42, "gold": 38, "level": 7}
    res = client.post("/api/decide", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["action_score_gap"] >= 0.0
    assert "all_scores" in data
    assert len(data["all_scores"]) == 3


def test_operational_direction_generation():
    """15. Test NOW / WATCH / THEN structured operational direction in Korean."""
    payload = {"stage_round": "4-2", "hp": 42, "gold": 38, "level": 7}
    res = client.post("/api/decide", json=payload)
    assert res.status_code == 200
    dir_info = res.json()["current_direction"]
    assert "now" in dir_info
    assert "watch" in dir_info
    assert "then" in dir_info
    assert len(dir_info["watch"]) >= 1
    assert any(k in dir_info["now"]["description"] for k in ["골드", "리롤", "레벨"])


def test_decision_rationale_reasons():
    """16. Test reason explanations generated."""
    payload = {"stage_round": "4-2", "hp": 42, "gold": 38, "level": 7}
    res = client.post("/api/decide", json=payload)
    assert res.status_code == 200
    reasons = res.json()["reasons"]
    assert isinstance(reasons, list)


def test_score_breakdown_table():
    """17. Test 4-metric score breakdown."""
    payload = {"stage_round": "4-2", "hp": 42, "gold": 38, "level": 7}
    res = client.post("/api/decide", json=payload)
    assert res.status_code == 200
    scores = res.json()["all_scores"]
    for s in scores:
        assert "breakdown" in s
        assert "survival" in s["breakdown"]
        assert "economy" in s["breakdown"]
        assert "board_power" in s["breakdown"]
        assert "upgrade" in s["breakdown"]


def test_human_review_logging():
    """18. Test actual player action and human feedback logging."""
    dto = HumanInputDTO(
        actual_player_action="ROLL",
        human_preferred_action="SAVE_GOLD",
        human_feedback="QUESTIONABLE",
        notes="Player rolled down on 4-2"
    )
    assert dto.actual_player_action == "ROLL"
    assert dto.human_preferred_action == "SAVE_GOLD"
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
    dto = HumanInputDTO(stage_round="4-2", hp=42, gold=38, level=7, video_timestamp_sec=305.4)
    st = GameStateBuilder.build_game_state(dto)
    assert dto.video_timestamp_sec == 305.4


def test_session_persistence():
    """21. Test session save and list."""
    sid = "TEST_SESSION_PERSIST_V11"
    res = client.post(f"/api/sessions/{sid}/turns", json={
        "turn_id": "T1", "stage_round": "2-1", "state": {"hp": 100}
    })
    assert res.status_code == 200
    sessions = client.get("/api/sessions").json()
    assert sid in sessions


def test_reload_integrity():
    """22. Test reloaded session matches original saved data."""
    sid = "TEST_RELOAD_INTEGRITY"
    client.post(f"/api/sessions/{sid}/turns", json={
        "turn_id": "T1", "stage_round": "4-2", "actual_player_action": "ROLL"
    })
    res = client.get(f"/api/sessions/{sid}")
    assert res.status_code == 200
    loaded = res.json()
    assert loaded["turns"][0]["actual_player_action"] == "ROLL"


def test_prediction_immutability():
    """23. Test engine prediction remains immutable when human feedback is added."""
    sid = "TEST_IMMUTABLE_V11"
    payload = {
        "turn_id": "T1",
        "stage_round": "4-2",
        "decision": {"recommended_action": "SAVE_GOLD", "score": 0.3347},
        "actual_player_action": "ROLL",
        "human_feedback": "WRONG"
    }
    client.post(f"/api/sessions/{sid}/turns", json=payload)
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
