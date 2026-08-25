#!/usr/bin/env python3
"""test_riot_client.py — RiotClient 및 매치 수집기 단위 테스트 (보안/Rate Limit/429 검증)."""
import io
import json
import os
import sys
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from riot_client import RiotClient
from collect_match_ids import collect_match_ids

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
