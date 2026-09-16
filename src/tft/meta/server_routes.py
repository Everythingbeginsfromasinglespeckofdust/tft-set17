"""FastAPI Routes for TFT Meta and YouTube Intelligence API."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from tft.meta.patch_analyzer import PatchAnalyzer
from tft.meta.youtube_aggregator import YouTubeAggregator
from tft.meta.meta_synthesizer import MetaSynthesizer

meta_router = APIRouter(prefix="/api/meta", tags=["TFT Meta & YouTube Intelligence"])

_patch_analyzer = PatchAnalyzer()
_youtube_agg = YouTubeAggregator()
_synthesizer = MetaSynthesizer(patch_analyzer=_patch_analyzer, youtube_aggregator=_youtube_agg)


@meta_router.get("/version")
def get_meta_version() -> Dict[str, Any]:
    """Returns current TFT patch version and summary overview."""
    return _patch_analyzer.get_summary_dict()


@meta_router.get("/patch")
def get_patch_notes() -> Dict[str, Any]:
    """Returns full patch notes with buffs, nerfs, and system adjustments."""
    notes = _patch_analyzer.get_patch_notes()
    return notes.to_dict()


@meta_router.get("/youtube")
def get_youtube_insights() -> Dict[str, Any]:
    """Returns curated YouTube creator videos, timestamps, and tips."""
    videos = _youtube_agg.get_videos()
    consensus = _youtube_agg.get_consensus_comps()
    return {
        "total_videos": len(videos),
        "consensus_comps": consensus,
        "videos": [v.to_dict() for v in videos]
    }


@meta_router.get("/decks")
def get_meta_decks(tier: Optional[str] = Query(None, description="Filter by tier: S+, S, A, B")) -> List[Dict[str, Any]]:
    """Returns all 1-tier meta decks or filtered by tier."""
    decks = _synthesizer.get_all_decks()
    if tier:
        t_upper = tier.upper()
        decks = [d for d in decks if d.tier.upper() == t_upper]
    return [d.to_dict() for d in decks]


@meta_router.get("/deck/{deck_id}")
def get_deck_detail(deck_id: str) -> Dict[str, Any]:
    """Returns detailed composition and positioning for a specific meta deck."""
    deck = _synthesizer.get_deck_by_id(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail=f"Deck '{deck_id}' not found")
    return deck.to_dict()


@meta_router.get("/insights")
def get_meta_insights() -> Dict[str, Any]:
    """Returns consolidated meta intelligence (consensus, rising comps, creator opinions)."""
    summary = _synthesizer.get_meta_intelligence_summary()
    tier_list = _synthesizer.get_tier_list()
    consensus = _youtube_agg.get_consensus_comps()
    patch_summary = _patch_analyzer.get_summary_dict()
    return {
        "summary": summary.to_dict(),
        "tier_list": tier_list,
        "consensus": consensus,
        "patch_summary": patch_summary
    }


@meta_router.get("/search")
def search_meta(q: str = Query(..., description="Query champion, trait, item, or creator name")) -> Dict[str, Any]:
    """Searches meta decks, patch balance changes, and YouTube videos matching the query."""
    return _synthesizer.search_meta(q)
