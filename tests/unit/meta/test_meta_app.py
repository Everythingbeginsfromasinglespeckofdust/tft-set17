"""Unit tests for TFT Meta & YouTube Intelligence App."""
import os
import sys
_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest
from fastapi.testclient import TestClient

from tft.meta.patch_analyzer import PatchAnalyzer
from tft.meta.youtube_aggregator import YouTubeAggregator
from tft.meta.meta_synthesizer import MetaSynthesizer
from tft.webapp.server import app


@pytest.fixture
def patch_analyzer():
    return PatchAnalyzer()


@pytest.fixture
def youtube_aggregator():
    return YouTubeAggregator()


@pytest.fixture
def meta_synthesizer(patch_analyzer, youtube_aggregator):
    return MetaSynthesizer(patch_analyzer=patch_analyzer, youtube_aggregator=youtube_aggregator)


@pytest.fixture
def client():
    return TestClient(app)


def test_patch_analyzer_load(patch_analyzer):
    notes = patch_analyzer.get_patch_notes()
    assert notes.version == "18.2"
    assert notes.sub_version == "18.2b"
    assert len(notes.system_changes) > 0
    assert any("68" in sc for sc in notes.system_changes)
    assert len(notes.changes) > 10


def test_patch_analyzer_buffs_and_nerfs(patch_analyzer):
    buffs = patch_analyzer.get_buffs()
    nerfs = patch_analyzer.get_nerfs()
    buff_names = [b.name for b in buffs]
    nerf_names = [n.name for n in nerfs]

    assert any("나무정령" in name for name in buff_names)
    assert any("드레이븐" in name for name in buff_names)
    assert any("사냥꾼" in name for name in nerf_names)
    assert any("마스터 이" in name for name in nerf_names)


def test_youtube_aggregator_videos(youtube_aggregator):
    videos = youtube_aggregator.get_videos()
    assert len(videos) >= 4
    creators = [v.channel_name for v in videos]
    assert any("구루루" in c for c in creators)
    assert any("쪼해피롱" in c for c in creators)

    for v in videos:
        assert len(v.timestamps) > 0
        assert len(v.creator_tips) > 0
        assert len(v.key_comps_recommended) > 0


def test_youtube_aggregator_consensus(youtube_aggregator):
    consensus = youtube_aggregator.get_consensus_comps()
    assert len(consensus) > 0
    # Check that high frequency comps have multiple creator endorsements
    top_comp = consensus[0]
    assert top_comp["endorsement_count"] >= 2
    assert len(top_comp["creators"]) >= 2


def test_youtube_aggregator_search(youtube_aggregator):
    res_draven = youtube_aggregator.search_videos("드레이븐")
    assert len(res_draven) >= 1

    res_creator = youtube_aggregator.search_videos("구루루")
    assert len(res_creator) >= 1


def test_meta_synthesizer_decks(meta_synthesizer):
    decks = meta_synthesizer.get_all_decks()
    assert len(decks) >= 4

    tiers = [d.tier for d in decks]
    assert "S+" in tiers or "S" in tiers

    for d in decks:
        assert len(d.core_champions) > 0
        assert len(d.carry_units) > 0
        assert len(d.tank_units) > 0
        assert len(d.bis_items) > 0
        assert len(d.level_up_guide) > 0
        # Check board placement limits
        for unit in d.core_champions:
            assert 1 <= unit.row <= 4
            assert 1 <= unit.col <= 7


def test_meta_synthesizer_search(meta_synthesizer):
    search_res = meta_synthesizer.search_meta("드레이븐")
    assert search_res["matched_decks_count"] >= 1
    assert search_res["matched_videos_count"] >= 1
    assert search_res["matched_patch_changes_count"] >= 1

    search_camille = meta_synthesizer.search_meta("카밀")
    assert search_camille["matched_decks_count"] >= 1


def test_api_meta_version(client):
    res = client.get("/api/meta/version")
    assert res.status_code == 200
    data = res.json()
    assert data["version"] == "18.2"
    assert "total_changes" in data


def test_api_meta_patch(client):
    res = client.get("/api/meta/patch")
    assert res.status_code == 200
    data = res.json()
    assert "changes" in data
    assert "system_changes" in data


def test_api_meta_youtube(client):
    res = client.get("/api/meta/youtube")
    assert res.status_code == 200
    data = res.json()
    assert "videos" in data
    assert "consensus_comps" in data
    assert data["total_videos"] >= 4


def test_api_meta_decks(client):
    res = client.get("/api/meta/decks")
    assert res.status_code == 200
    decks = res.json()
    assert len(decks) >= 4

    # Test filtering by tier
    res_s = client.get("/api/meta/decks?tier=S")
    assert res_s.status_code == 200
    for d in res_s.json():
        assert d["tier"] == "S"


def test_api_meta_deck_detail(client):
    res = client.get("/api/meta/deck/elder_dragon_draven_fast9")
    assert res.status_code == 200
    deck = res.json()
    assert deck["deck_id"] == "elder_dragon_draven_fast9"
    assert "드레이븐" in deck["name"]

    res_404 = client.get("/api/meta/deck/non_existent_deck")
    assert res_404.status_code == 404


def test_api_meta_insights(client):
    res = client.get("/api/meta/insights")
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data
    assert "tier_list" in data
    assert "consensus" in data


def test_api_meta_search(client):
    res = client.get("/api/meta/search?q=나무정령")
    assert res.status_code == 200
    data = res.json()
    assert data["matched_decks_count"] >= 1
    assert data["matched_patch_changes_count"] >= 1


def test_frontend_home_serves_meta_dashboard(client):
    res = client.get("/")
    assert res.status_code == 200
    content = res.text
    assert "롤토체스 메타 & 유튜브 인텔리전스" in content
    assert "18.2" in content
