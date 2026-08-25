#!/usr/bin/env python3
"""test_api.py — FastAPI 백엔드 엔드포인트 단위 및 통합 테스트."""
import json
import os
import sys
import pytest
from fastapi.testclient import TestClient

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from main import app

client = TestClient(app)


def test_get_champions_endpoint():
    """GET /api/champions 엔드포인트 검증."""
    res = client.get("/api/champions")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 63
    # 각 챔피언 필수 필드 확인
    sample = data[0]
    assert "name" in sample
    assert "cost" in sample
    assert "traits" in sample
    assert 1 <= sample["cost"] <= 5


def test_get_items_endpoint():
    """GET /api/items 엔드포인트 검증."""
    res = client.get("/api/items")
    assert res.status_code == 200
    data = res.json()
    assert "basic_components" in data
    assert "completed_items" in data
    assert len(data["basic_components"]) > 0
    assert len(data["completed_items"]) > 0
    assert "B.F. 대검" in data["basic_components"]
    assert "무한의 대검" in data["completed_items"]


def test_get_scenarios_endpoint():
    """GET /api/scenarios 엔드포인트 검증."""
    res = client.get("/api/scenarios")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 3


def test_post_report_scenario_1():
    """POST /api/report 시나리오 1 검증 (초반 약한 보드)."""
    scenarios_res = client.get("/api/scenarios")
    s1 = scenarios_res.json()[0]

    res = client.post("/api/report", json=s1)
    assert res.status_code == 200
    data = res.json()

    assert data["state"]["stage_round"] == "2-1"
    assert data["state"]["level"] == 4
    assert data["state"]["gold"] == 30
    assert data["board_power"]["total_power"] == pytest.approx(7.0)
    assert data["economy"]["next_turn_interest"] == 3
    assert len(data["strategies_comparison"]) == 3
    assert "초반 운영" in data["tactical_comment"]


def test_post_report_scenario_2():
    """POST /api/report 시나리오 2 검증 (중반 애매한 보드)."""
    scenarios_res = client.get("/api/scenarios")
    s2 = scenarios_res.json()[1]

    res = client.post("/api/report", json=s2)
    assert res.status_code == 200
    data = res.json()

    assert data["state"]["stage_round"] == "5-2"
    assert data["state"]["level"] == 7
    assert data["state"]["gold"] == 8
    assert data["board_power"]["total_power"] == pytest.approx(48.0)
    assert data["economy"]["next_turn_interest"] == 0


def test_post_report_scenario_3():
    """POST /api/report 시나리오 3 검증 (후반 강한 보드)."""
    scenarios_res = client.get("/api/scenarios")
    s3 = scenarios_res.json()[2]

    res = client.post("/api/report", json=s3)
    assert res.status_code == 200
    data = res.json()

    assert data["state"]["stage_round"] == "7-1"
    assert data["state"]["level"] == 9
    assert data["state"]["gold"] == 54
    assert data["board_power"]["total_power"] == pytest.approx(122.4)
    assert data["economy"]["next_level"] == 10
    assert data["economy"]["gold_to_next_level"] == 8
    assert "10레벨 적기" in data["tactical_comment"]


def test_post_report_invalid_inputs_return_400():
    """도메인 검증 실패 시 400 Bad Request 반환 확인."""
    # 1. 미등록 챔피언
    bad_champ_payload = {
        "gold": 20,
        "level": 5,
        "board": {"units": [{"champion": "가짜챔피언", "star_level": 1, "items": []}]}
    }
    res1 = client.post("/api/report", json=bad_champ_payload)
    assert res1.status_code == 400
    assert "존재하지 않는 챔피언" in res1.json()["detail"]

    # 2. 음수 골드
    bad_gold_payload = {
        "gold": -10,
        "level": 5,
        "board": {"units": []}
    }
    res2 = client.post("/api/report", json=bad_gold_payload)
    assert res2.status_code == 400

    # 3. 잘못된 성급
    bad_star_payload = {
        "gold": 20,
        "level": 5,
        "board": {"units": [{"champion": "나서스", "star_level": 4, "items": []}]}
    }
    res3 = client.post("/api/report", json=bad_star_payload)
    assert res3.status_code == 400
    assert "star_level" in res3.json()["detail"]


def test_serve_frontend_index():
    """GET / 루트 접속 시 HTML 정상 서빙 확인."""
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "TFT Set 17" in res.text
