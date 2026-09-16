"""Unit tests for TFT Meta & YouTube Intelligence App.

Covers Patch Notes, Korean & Global YouTube Creator Insights (post-patch verified),
5-Season Mastery Fundamentals, Consolidated Decks, and REST API Endpoints.
"""
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
    assert len(videos) >= 18
    creators = [v.channel_name for v in videos]
    assert any("구루루" in c for c in creators)
    assert any("쪼해피롱" in c for c in creators)
    assert any("김루트" in c for c in creators)
    assert any("정동글" in c for c in creators)
    assert any("두니주니" in c for c in creators)
    assert any("승상싱" in c for c in creators)
    assert any("쌍칼" in c for c in creators)
    assert any("오박사" in c for c in creators)

    for v in videos:
        assert len(v.timestamps) > 0
        assert len(v.creator_tips) > 0
        assert len(v.key_comps_recommended) > 0


def test_youtube_aggregator_global_creators(youtube_aggregator):
    global_videos = youtube_aggregator.get_videos(region="GLOBAL")
    kr_videos = youtube_aggregator.get_videos(region="KR")

    assert len(global_videos) >= 10
    assert len(kr_videos) >= 8

    global_creators = [v.channel_name for v in global_videos]
    assert any("Dishsoap" in c for c in global_creators)
    assert any("Frodan" in c for c in global_creators)
    assert any("Setsuko" in c for c in global_creators)
    assert any("k3soju" in c for c in global_creators)
    assert any("RobinSongz" in c for c in global_creators)
    assert any("Mortdog" in c for c in global_creators)
    assert any("Bebe872" in c for c in global_creators)
    assert any("Deisik" in c for c in global_creators)
    assert any("Sologesang" in c for c in global_creators)
    assert any("Subzeroark" in c for c in global_creators)


def test_youtube_post_patch_verified(youtube_aggregator):
    """Enforces requirement: Season meta info must be based strictly on post-patch videos."""
    videos = youtube_aggregator.get_videos()
    for v in videos:
        assert v.post_patch_verified is True
        # Published at must be after 2026-09-09 (18.2 patch release date)
        assert v.published_at >= "2026-09-09"
        assert v.season_tag == "세트 18"


def test_mastery_tips_5seasons(youtube_aggregator):
    """Enforces requirement: Strategic tips collected from within the last 5 seasons."""
    tips = youtube_aggregator.get_mastery_tips()
    assert len(tips) >= 9

    categories = set(t.category for t in tips)
    assert "ECONOMY" in categories
    assert "ROLLDOWN" in categories
    assert "POSITIONING" in categories
    assert "AUGMENTS" in categories
    assert "ITEMS" in categories

    # Verify strategic breadth across the 9 tips
    tip_ids = [t.tip_id for t in tips]
    assert "tip_econ_hp_balance" in tip_ids
    assert "tip_rolldown_frontline_first" in tip_ids
    assert "tip_augment_golden_ratio" in tip_ids
    assert "tip_melee_carry_positioning" in tip_ids
    assert "tip_item_slam_vs_bis" in tip_ids
    assert "tip_scouting_last_10s" in tip_ids
    assert "tip_loss_streak_rebound" in tip_ids
    assert "tip_top4_vs_first_mindset" in tip_ids
    assert "tip_carousel_component_priority" in tip_ids

    for tip in tips:
        assert "최근 5개 시즌" in tip.seasons_valid
        assert len(tip.key_rule) > 10
        assert len(tip.source_creators) > 0


def test_youtube_aggregator_consensus(youtube_aggregator):
    consensus = youtube_aggregator.get_consensus_comps()
    assert len(consensus) > 0
    top_comp = consensus[0]
    assert top_comp["endorsement_count"] >= 3
    assert len(top_comp["creators"]) >= 3


def test_youtube_aggregator_search(youtube_aggregator):
    res_draven = youtube_aggregator.search_videos("드레이븐")
    assert len(res_draven) >= 1

    res_creator = youtube_aggregator.search_videos("Dishsoap")
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
        for unit in d.core_champions:
            assert 1 <= unit.row <= 4
            assert 1 <= unit.col <= 7


def test_meta_synthesizer_search(meta_synthesizer):
    search_res = meta_synthesizer.search_meta("드레이븐")
    assert search_res["matched_decks_count"] >= 1
    assert search_res["matched_videos_count"] >= 1
    assert search_res["matched_patch_changes_count"] >= 1

    # Search tip
    search_tip = meta_synthesizer.search_meta("롤다운")
    assert search_tip["matched_tips_count"] >= 1


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


def test_api_meta_youtube_and_regions(client):
    res = client.get("/api/meta/youtube")
    assert res.status_code == 200
    data = res.json()
    assert data["total_videos"] >= 18

    res_global = client.get("/api/meta/youtube?region=GLOBAL")
    assert res_global.status_code == 200
    assert res_global.json()["total_videos"] >= 10

    res_kr = client.get("/api/meta/youtube?region=KR")
    assert res_kr.status_code == 200
    assert res_kr.json()["total_videos"] >= 8


def test_api_meta_tips(client):
    res = client.get("/api/meta/tips")
    assert res.status_code == 200
    data = res.json()
    assert data["total_tips"] >= 9
    assert "최근 5개 시즌" in data["scope"]

    res_econ = client.get("/api/meta/tips?category=ECONOMY")
    assert res_econ.status_code == 200
    assert len(res_econ.json()["tips"]) >= 1


def test_api_meta_decks(client):
    res = client.get("/api/meta/decks")
    assert res.status_code == 200
    decks = res.json()
    assert len(decks) >= 4


def test_api_meta_deck_detail(client):
    res = client.get("/api/meta/deck/elder_dragon_draven_fast9")
    assert res.status_code == 200
    deck = res.json()
    assert deck["deck_id"] == "elder_dragon_draven_fast9"
    assert "드레이븐" in deck["name"]


def test_api_meta_insights(client):
    res = client.get("/api/meta/insights")
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data
    assert "tier_list" in data
    assert "consensus" in data
    assert "mastery_tips" in data
    assert len(data["mastery_tips"]) >= 5


def test_frontend_home_serves_meta_dashboard(client):
    res = client.get("/")
    assert res.status_code == 200
    content = res.text
    assert "롤토체스 메타 & 글로벌 유튜브 인텔리전스" in content
    assert "5시즌 누적 마스터 팁" in content
