"""Data Models for TFT Meta and YouTube Intelligence App.

Covers Patch Notes, YouTube Creator Insights, Consolidated Meta Decks, and Search Models.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class TierEnum(str, Enum):
    S_PLUS = "S+"
    S = "S"
    A = "A"
    B = "B"


class PlaystyleEnum(str, Enum):
    FAST_9 = "FAST_9"
    FAST_8 = "FAST_8"
    REROLL_1 = "REROLL_1"
    REROLL_2 = "REROLL_2"
    REROLL_3 = "REROLL_3"
    FLEX = "FLEX"


class ChangeTypeEnum(str, Enum):
    BUFF = "BUFF"
    NERF = "NERF"
    ADJUST = "ADJUST"
    REWORK = "REWORK"
    NEW = "NEW"


@dataclass
class PatchItemChange:
    name: str
    target_type: str  # CHAMPION, TRAIT, ITEM, AUGMENT, SYSTEM
    change_type: str  # BUFF, NERF, ADJUST, REWORK
    summary: str
    details: List[str] = field(default_factory=list)
    impact_rating: int = 3  # 1 to 5 scale

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PatchNoteData:
    version: str = "18.2"
    sub_version: str = "18.2b"
    title: str = "신비의 숲 18.2 / 18.2b 밸런스 패치"
    release_date: str = "2026-09-09"
    hotfix_date: Optional[str] = "2026-09-15"
    theme: str = "신비의 숲 (Mystic Forest)"
    summary: str = (
        "8~10레벨 레벨업 경험치 인하 및 수호령 비용 대폭 완화로 고밸류 운영이 급부상했으며, "
        "나무정령/악의여단/검은가시 버프와 저코스트 리롤 및 4코스트 캐리 유닛 밸런스가 재편되었습니다."
    )
    system_changes: List[str] = field(default_factory=list)
    changes: List[PatchItemChange] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class YouTubeVideoInsight:
    video_id: str
    title: str
    channel_name: str
    channel_avatar: str = ""
    published_at: str = "2026-09-12"
    video_url: str = ""
    thumbnail_url: str = ""
    view_count: str = "5.4만회"
    region: str = "KR"  # "KR" or "GLOBAL"
    post_patch_verified: bool = True  # Verified to be post 18.2 / 18.2b patch
    season_tag: str = "세트 18"
    key_comps_recommended: List[str] = field(default_factory=list)
    summary: str = ""
    timestamps: List[Dict[str, str]] = field(default_factory=list)
    creator_tips: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MasteryTip:
    tip_id: str
    category: str  # ECONOMY, ROLLDOWN, POSITIONING, AUGMENTS, ITEMS
    title: str
    description: str
    key_rule: str
    source_creators: List[str] = field(default_factory=list)
    seasons_valid: str = "최근 5개 시즌 (세트 14~18 검증)"
    impact_level: str = "ESSENTIAL"  # ESSENTIAL, ADVANCED, SITUATIONAL

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MetaUnitPlacement:
    name: str
    cost: int
    star: int
    items: List[str] = field(default_factory=list)
    row: int = 1  # 1 (front) to 4 (back)
    col: int = 1  # 1 to 7
    is_main_carry: bool = False
    is_main_tank: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MetaDeck:
    deck_id: str
    name: str
    name_en: str = ""
    tier: str = TierEnum.S.value
    difficulty: str = "보통"  # 쉬움, 보통, 어려움
    playstyle: str = PlaystyleEnum.FAST_9.value
    win_rate: str = "54.8%"
    top4_rate: str = "62.4%"
    avg_rank: str = "3.8"
    summary: str = ""
    core_champions: List[MetaUnitPlacement] = field(default_factory=list)
    active_traits: List[Dict[str, Any]] = field(default_factory=list)
    carry_units: List[str] = field(default_factory=list)
    tank_units: List[str] = field(default_factory=list)
    bis_items: Dict[str, List[str]] = field(default_factory=dict)
    level_up_guide: Dict[str, str] = field(default_factory=dict)
    recommended_augments: List[str] = field(default_factory=list)
    counters: List[str] = field(default_factory=list)
    strong_against: List[str] = field(default_factory=list)
    youtube_mentions: List[str] = field(default_factory=list)  # channel names
    patch_status: str = "BUFF_BENEFICIARY"  # BUFF_BENEFICIARY, STABLE, NERFED_VIABLE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MetaIntelligenceSummary:
    patch_version: str = "18.2b"
    set_name: str = "세트 18: 신비의 숲"
    last_updated: str = "2026-09-16"
    tier_list: Dict[str, List[MetaDeck]] = field(default_factory=dict)
    trending_comps: List[str] = field(default_factory=list)
    patch_beneficiaries: List[str] = field(default_factory=list)
    creators_analyzed: List[str] = field(default_factory=list)
    total_videos_analyzed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
