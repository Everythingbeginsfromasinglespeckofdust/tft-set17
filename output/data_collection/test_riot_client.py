#!/usr/bin/env python3
"""test_riot_client.py — RiotClient 및 매치/스냅샷 수집기 단위 테스트 (보안/Rate Limit/429/형식 검증)."""
import io
import json
import os
import sys
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ECONOMY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "economy")
if _ECONOMY not in sys.path:
    sys.path.insert(0, _ECONOMY)

from riot_client import RiotClient
from collect_match_ids import collect_match_ids
from collect_match_details import parse_participant_snapshot, collect_match_details
import board_power as bp

DUMMY_KEY = "RGAPI-12345678-abcd-1234-abcd-1234567890ab"


# ---------------------------------------------------------------- 보안 검증
def test_api_key_not_exposed_in_repr():
    client = RiotClient(api_key=DUMMY_KEY, min_request_interval=0.01)
    rep = repr(client)
    assert DUMMY_KEY not in rep
    assert "RGAPI" not in rep


def test_api_key_masked_in_text():
    client = RiotClient(api_key=DUMMY_KEY, min_request_interval=0.01)
    sample_text = f"Error calling https://kr.api.riotgames.com/test?api_key={DUMMY_KEY}"
    masked = client._mask_text(sample_text)
    assert DUMMY_KEY not in masked
    assert "***MASKED_KEY***" in masked


def test_missing_api_key_raises():
    with patch("riot_client._load_env_file"), patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="RIOT_API_KEY"):
            RiotClient(api_key=None)


# ---------------------------------------------------------------- Rate Limit & 429 재시도 검증
def test_retry_on_429_success():
    """429 응답 수신 시 Retry-After 헤더를 읽고 재시도하여 성공하는지 검증."""
    client = RiotClient(api_key=DUMMY_KEY, min_request_interval=0.01, max_retries=3)

    # 1회차 429, 2회차 200 성공 mock
    headers_429 = {"Retry-After": "0.1"}
    http_error_429 = urllib.error.HTTPError(
        url="https://kr.api.riotgames.com/test",
        code=429,
        msg="Rate limit exceeded",
        hdrs=headers_429,
        fp=io.BytesIO(b'{"status":{"message":"Rate limit exceeded","status_code":429}}'),
    )

    success_resp = MagicMock()
    success_resp.__enter__.return_value = success_resp
    success_resp.read.return_value = b'{"result": "ok"}'

    with patch("urllib.request.urlopen", side_effect=[http_error_429, success_resp]):
        res = client.request("https://kr.api.riotgames.com/test")
        assert res == {"result": "ok"}


def test_get_top_puuids_sorted_by_lp():
    client = RiotClient(api_key=DUMMY_KEY, min_request_interval=0.01)
    mock_data = {
        "tier": "CHALLENGER",
        "entries": [
            {"puuid": "p2", "leaguePoints": 500},
            {"puuid": "p1", "leaguePoints": 1500},
            {"puuid": "p3", "leaguePoints": 800},
        ],
    }

    with patch.object(client, "request", return_value=mock_data):
        puuids = client.get_top_puuids(tier="challenger", limit=2)
        assert puuids == ["p1", "p3"]


def test_get_match_detail():
    client = RiotClient(api_key=DUMMY_KEY, min_request_interval=0.01)
    mock_detail = {"metadata": {"match_id": "KR_12345"}, "info": {"participants": []}}
    with patch.object(client, "request", return_value=mock_detail):
        res = client.get_match_detail("KR_12345")
        assert res["metadata"]["match_id"] == "KR_12345"


# ---------------------------------------------------------------- 매치 ID & 스냅샷 수집 검증
def test_collect_match_ids_deduplication(tmp_path):
    """중복 매치 ID가 제거되어 저장되는지 검증."""
    client_mock = MagicMock()
    client_mock.get_top_puuids.return_value = ["puuid_1", "puuid_2"]
    # puuid_1: [M1, M2, M3], puuid_2: [M2, M3, M4] (M2, M3 중복)
    client_mock.get_match_ids_by_puuid.side_effect = [
        ["KR_1001", "KR_1002", "KR_1003"],
        ["KR_1002", "KR_1003", "KR_1004"],
    ]

    out_json = tmp_path / "test_matches.json"

    with patch("collect_match_ids.RiotClient", return_value=client_mock):
        res = collect_match_ids(target_count=4, output_path=str(out_json))
        assert res == ["KR_1001", "KR_1002", "KR_1003", "KR_1004"]
        assert len(res) == 4

        data = json.loads(out_json.read_text(encoding="utf-8"))
        assert data["total_matches"] == 4
        assert data["match_ids"] == ["KR_1001", "KR_1002", "KR_1003", "KR_1004"]


def test_parse_participant_snapshot_and_board_power_compatibility():
    """참가자 데이터가 board_power.py 입력 형식으로 정상 변환되고 에러 없이 파워가 계산되는지 검증."""
    participant_data = {
        "puuid": "test_puuid_123",
        "riotIdGameName": "TFTMaster",
        "riotIdTagline": "KR1",
        "placement": 1,
        "level": 9,
        "gold_left": 45,
        "last_round": 36,
        "time_eliminated": 2100.5,
        "total_damage_to_players": 140,
        "units": [
            {
                "character_id": "TFT17_Jhin",
                "tier": 2,
                "itemNames": ["TFT_Item_InfinityEdge", "TFT_Item_LastWhisper", "TFT_Item_GiantSlayer"],
            },
            {
                "character_id": "TFT17_Fiora",
                "tier": 2,
                "itemNames": ["TFT_Item_Bloodthirster"],
            },
            {
                # 비상점 기물(타겟 더미 등)은 무시되어야 함
                "character_id": "TFT_TargetDummy",
                "tier": 1,
                "itemNames": [],
            },
        ],
    }

    item_id_to_name = {
        "TFT_Item_InfinityEdge": "무한의 대검",
        "TFT_Item_LastWhisper": "최후의 속삭임",
        "TFT_Item_GiantSlayer": "거인 학살자",
        "TFT_Item_Bloodthirster": "피바라기",
    }
    champ_id_to_info = {
        "TFT17_Jhin": {"id": "TFT17_Jhin", "name": "진", "cost": 5, "traits": ["암흑의 별", "말살자", "저격수"]},
        "TFT17_Fiora": {"id": "TFT17_Fiora", "name": "피오라", "cost": 5, "traits": ["신성 결투가", "동물특공대", "습격자"]},
    }
    valid_items = {"무한의 대검", "최후의 속삭임", "거인 학살자", "피바라기"}

    snap = parse_participant_snapshot(
        participant_data, "KR_99999", item_id_to_name, champ_id_to_info, valid_items
    )

    assert snap["match_id"] == "KR_99999"
    assert snap["final_placement"] == 1
    assert snap["level"] == 9
    assert snap["gold_left"] == 45
    assert len(snap["board"]["units"]) == 2  # 타겟 더미 제외됨

    # board_power 계산 호환성 직접 호출 검증
    power_res = bp.calculate_board_power(snap["board"])
    assert power_res["total_power"] > 0.0
    assert "unit_power" in power_res["breakdown"]
    assert "item_score" in power_res["breakdown"]
    assert "synergy_bonus" in power_res["breakdown"]


def test_collect_match_details_mock_filters_pve_matches(tmp_path):
    """collect_match_details가 PvE/비표준 매치를 걸러내고 8인 표준 랭크(1100) 매치만 수집하는지 검증."""
    match_ids_file = tmp_path / "match_ids.json"
    match_ids_file.write_text(json.dumps({"match_ids": ["KR_STD", "KR_PVE"]}), encoding="utf-8")
    out_jsonl = tmp_path / "match_snapshots.jsonl"

    mock_std_detail = {
        "metadata": {"match_id": "KR_STD"},
        "info": {
            "queueId": 1100,
            "tft_set_number": 17,
            "tft_game_type": "standard",
            "participants": [
                {
                    "puuid": f"p_{i}",
                    "placement": i,
                    "level": 8,
                    "gold_left": 10,
                    "units": [{"character_id": "TFT17_Jhin", "tier": 1, "itemNames": []}],
                }
                for i in range(1, 9)
            ]
        },
    }

    mock_pve_detail = {
        "metadata": {"match_id": "KR_PVE"},
        "info": {
            "queueId": 1220,
            "tft_set_number": 17,
            "tft_game_type": "pve",
            "participants": [
                {
                    "puuid": "p_pve",
                    "placement": 1,
                    "level": 9,
                    "gold_left": 5,
                    "units": [{"character_id": "TFT17_Jhin", "tier": 1, "itemNames": []}],
                }
            ]
        },
    }

    client_mock = MagicMock()
    client_mock.get_match_detail.side_effect = lambda mid: mock_std_detail if mid == "KR_STD" else mock_pve_detail

    with patch("collect_match_details.RiotClient", return_value=client_mock):
        snapshots = collect_match_details(
            match_ids_path=str(match_ids_file),
            output_path=str(out_jsonl),
            target_queue_id=1100,
            target_set_number=17,
        )

        assert len(snapshots) == 8  # KR_PVE는 건너뛰고 KR_STD 8명만 수집
        assert all(1 <= s["final_placement"] <= 8 for s in snapshots)
        assert len(set(s["final_placement"] for s in snapshots)) == 8  # 1~8등 각 1명씩 균등
