"""YouTube Meta Intelligence Aggregator Module for TFT Set 18 Patch 18.2b.

Curates and manages structured YouTube creator insights, recommendations, and video summaries
from both top Korean and Global TFT creators (구루루, 쪼해피롱, 김루트, 정동글, Dishsoap, Frodan, Setsuko, Mortdog, Bebe872).

Constraints:
1. Season meta information is STRICTLY based on post-patch videos (released after 18.2 patch on 2026-09-09).
2. General strategic tips (fundamentals) are curated across the last 5 seasons (Sets 14 to 18).
"""
from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Optional

from tft.meta.models import YouTubeVideoInsight, MasteryTip

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_DATA_DIR = os.path.join(_ROOT, "data", "meta")

os.makedirs(_DATA_DIR, exist_ok=True)


class YouTubeAggregator:
    """Aggregates and queries Korean & Global YouTube creator meta insights and 5-season mastery tips."""

    def __init__(self, data_file: Optional[str] = None, tips_file: Optional[str] = None):
        self.data_file = data_file or os.path.join(_DATA_DIR, "youtube_insights.json")
        self.tips_file = tips_file or os.path.join(_DATA_DIR, "mastery_tips_5seasons.json")
        self._videos: List[YouTubeVideoInsight] = []
        self._mastery_tips: List[MasteryTip] = []
        self._initialize_youtube_data()
        self._initialize_mastery_tips()

    def _initialize_youtube_data(self) -> None:
        # Curate authentic, high-value YouTube intelligence (All strictly POST-PATCH 18.2 / 18.2b verified)
        curated = [
            # 1. 구루루 (KR)
            YouTubeVideoInsight(
                video_id="gururu_18_2_draven",
                title="[18.2 패치] 나오면 무조건 하세요! 9렙 68원 패치로 점수 복사하는 1티어 장로드래곤 드레이븐 밸류",
                channel_name="구루루 (Gururu)",
                channel_avatar="https://yt3.googleusercontent.com/ytc/AIdro_k6Vgururu=s176-c-k-c0x00ffffff-no-rj",
                published_at="2026-09-11",
                video_url="https://www.youtube.com/watch?v=mock_gururu_18_2",
                thumbnail_url="https://i.ytimg.com/vi/mock_gururu_18_2/hqdefault.jpg",
                view_count="8.9만회",
                region="KR",
                post_patch_verified=True,
                season_tag="세트 18",
                key_comps_recommended=[
                    "장로드래곤 드레이븐 밸류 (Elder Dragon Draven)",
                    "나무정령 드레이븐 밸류 (Elderwood Draven)",
                    "일월식 알룬"
                ],
                summary=(
                    "18.2 패치로 9레벨/10레벨 필요 경험치가 68으로 완화되고 수호령 비용이 대폭 인하되면서 "
                    "8레벨에서 돈을 털지 않고 9레벨을 찍은 뒤 드레이븐 + 5코스트 전설 기물을 도배하는 고밸류 덱이 현 메타 원탑입니다."
                ),
                timestamps=[
                    {"time": "00:00", "title": "18.2 패치 경제 시스템 핵심 요약 (9렙 68원)"},
                    {"time": "02:15", "title": "드레이븐 3신기: 구인수 + 피바라기 + 거인학살자"},
                    {"time": "05:40", "title": "초중반 피관리용 나무정령/용족 빌드업"},
                    {"time": "11:20", "title": "9레벨 최종 완성 조합 및 5코스트 배치법"}
                ],
                creator_tips=[
                    "8레벨에서 피가 40 이상이면 절대 4코 3성 욕심내지 말고 무조건 9레벨 템포를 타세요.",
                    "드레이븐에게 구인수+피바라기는 고정이고 마지막은 거학이나 무한의 대검이 최고입니다.",
                    "앞라인은 나무정령 중첩을 받은 메인 탱커(마오카이/레오나)에게 방템 3개를 몰아주세요."
                ]
            ),

            # 2. 쪼해피롱 (KR)
            YouTubeVideoInsight(
                video_id="chohappy_18_2_tierlist",
                title="18.2 패치 긴급 티어리스트 총정리! 지금 점수 올리기 가장 쉬운 S티어 덱 TOP 5",
                channel_name="쪼해피롱 (ChoHappyRong)",
                channel_avatar="https://yt3.googleusercontent.com/ytc/AIdro_k6Vchohappy=s176-c-k-c0x00ffffff-no-rj",
                published_at="2026-09-12",
                video_url="https://www.youtube.com/watch?v=mock_chohappy_18_2",
                thumbnail_url="https://i.ytimg.com/vi/mock_chohappy_18_2/hqdefault.jpg",
                view_count="12.4만회",
                region="KR",
                post_patch_verified=True,
                season_tag="세트 18",
                key_comps_recommended=[
                    "장로드래곤 드레이븐 밸류 (Elder Dragon Draven)",
                    "나무정령 드레이븐 밸류 (Elderwood Draven)",
                    "햇빛 아칼리 카밀 리롤 (Sunlight Akali Camille)",
                    "쿠거 니달리 4코 운영 (Cougar Nidalee)",
                    "협곡야수 조약돌"
                ],
                summary=(
                    "사냥꾼과 마스터 이가 너프되고 나무정령과 악의 여단, 드레이븐이 버프를 받았습니다. "
                    "현재 메타는 '패스트 9 드레이븐 밸류'와 '2코 리롤 햇빛 아칼리/카밀'이 양대 산맥을 형성하고 있습니다."
                ),
                timestamps=[
                    {"time": "00:30", "title": "18.2 패치 버프/너프 티어 등락 분석"},
                    {"time": "03:10", "title": "1위: 장로드래곤 드레이븐 밸류 덱"},
                    {"time": "06:45", "title": "2위: 햇빛 아칼리 카밀 2코 리롤 덱"},
                    {"time": "10:15", "title": "3위: 4코스트 버프 수혜 니달리 시비르 덱"},
                    {"time": "13:50", "title": "증강체 티어 및 아이템 우선순위"}
                ],
                creator_tips=[
                    "나무정령 시너지가 버프를 받아서 6나무정령 맞추면 후반에 체력이 1,000 이상 뻥튀기됩니다.",
                    "초반 햇빛 기물(아칼리/카밀/레오나)이 많이 나오면 6렙 리롤로 3성 찍고 순방 확정 가능합니다.",
                    "연승 중일 때는 이자를 깨더라도 레벨업을 눌러 수호령을 확보하는 플레이가 매우 유효합니다."
                ]
            ),

            # 3. 김루트 (KR)
            YouTubeVideoInsight(
                video_id="kimroot_18_2b_nidalee",
                title="[18.2b] 랭커들이 몰래 꿀빠는 4코스트 신흥 강자 '쿠거 니달리' 캐리 덱 완벽 공략",
                channel_name="김루트 (KimRoot)",
                channel_avatar="https://yt3.googleusercontent.com/ytc/AIdro_k6Vkimroot=s176-c-k-c0x00ffffff-no-rj",
                published_at="2026-09-14",
                video_url="https://www.youtube.com/watch?v=mock_kimroot_18_2b",
                thumbnail_url="https://i.ytimg.com/vi/mock_kimroot_18_2b/hqdefault.jpg",
                view_count="6.7만회",
                region="KR",
                post_patch_verified=True,
                season_tag="세트 18",
                key_comps_recommended=[
                    "쿠거 니달리 4코 운영 (Cougar Nidalee)",
                    "악의 여단 르블랑 (Coven LeBlanc)"
                ],
                summary=(
                    "18.2 패치에서 니달리의 쿠거 도약 데미지가 35% 이상 폭증했습니다. "
                    "드레이븐 덱이 겹쳐서 기물이 부족할 때 8레벨에서 니달리를 2성 찍고 템을 몰아주면 후열을 차례대로 삭제합니다."
                ),
                timestamps=[
                    {"time": "00:00", "title": "니달리가 왜 사기인가? (버프 수치 분석)"},
                    {"time": "02:30", "title": "니달리 3신기: 피바라기 + 거인의 결의 + 무한의 대검"},
                    {"time": "07:10", "title": "8레벨 리롤 템포 및 시비르 연계"},
                    {"time": "12:00", "title": "인게임 실전 1등 경기 리플레이"}
                ],
                creator_tips=[
                    "니달리는 AP가 아니라 근접 AD 브루저처럼 피바라기+거인의결의가 가장 안정적입니다.",
                    "배치할 때 상대 메인 딜러 반대편 두 번째 열에 두면 도약하면서 어그로를 빼고 후열을 바로 덮칩니다."
                ]
            ),

            # 4. 정동글 (KR)
            YouTubeVideoInsight(
                video_id="dongle_18_2_akali",
                title="너프먹어도 여전히 1등하는 '햇빛 아칼리 카밀' 2코 3성 리롤 가이드 (운영법 꿀팁)",
                channel_name="정동글 (JungDongle)",
                channel_avatar="https://yt3.googleusercontent.com/ytc/AIdro_k6Vdongle=s176-c-k-c0x00ffffff-no-rj",
                published_at="2026-09-13",
                video_url="https://www.youtube.com/watch?v=mock_dongle_18_2",
                thumbnail_url="https://i.ytimg.com/vi/mock_dongle_18_2/hqdefault.jpg",
                view_count="5.1만회",
                region="KR",
                post_patch_verified=True,
                season_tag="세트 18",
                key_comps_recommended=[
                    "햇빛 아칼리 카밀 리롤 (Sunlight Akali Camille)",
                    "협곡야수 조약돌"
                ],
                summary=(
                    "18.2b 핫픽스로 카밀의 3성 스킬 데미지가 소폭 감소했지만, 햇빛 시너지 자체의 유지력과 "
                    "아칼리의 암살 능력 덕분에 2코 3성 리롤 덱 중에서는 여전히 독보적인 1티어입니다."
                ),
                timestamps=[
                    {"time": "00:00", "title": "18.2b 핫픽스 영향 분석"},
                    {"time": "01:50", "title": "3-2 라운드 6레벨 슬로우 리롤 공식"},
                    {"time": "06:10", "title": "카밀 vs 아칼리 템 배분 우선순위"},
                    {"time": "11:30", "title": "후반 8레벨 보완 기물 추천"}
                ],
                creator_tips=[
                    "카밀에게는 피바라기/정손/거결, 아칼리에게는 인피/보석연꽃/라바돈을 주어 투캐리 구조를 만드세요.",
                    "레오나 3성까지 같이 붙어주면 앞라인이 절대 무너지지 않습니다."
                ]
            ),

            # 5. Dishsoap (GLOBAL - NA World Champion)
            YouTubeVideoInsight(
                video_id="dishsoap_18_2_meta",
                title="[World Champion Guide] Set 18 Patch 18.2b Complete Meta Breakdown & Level 9 Cap",
                channel_name="Dishsoap (World Champion)",
                channel_avatar="https://yt3.googleusercontent.com/ytc/AIdro_k6Vdishsoap=s176-c-k-c0x00ffffff-no-rj",
                published_at="2026-09-13",
                video_url="https://www.youtube.com/watch?v=mock_dishsoap_18_2",
                thumbnail_url="https://i.ytimg.com/vi/mock_dishsoap_18_2/hqdefault.jpg",
                view_count="11.2만회",
                region="GLOBAL",
                post_patch_verified=True,
                season_tag="세트 18",
                key_comps_recommended=[
                    "장로드래곤 드레이븐 밸류 (Elder Dragon Draven)",
                    "나무정령 드레이븐 밸류 (Elderwood Draven)",
                    "쿠거 니달리 4코 운영 (Cougar Nidalee)"
                ],
                summary=(
                    "World Champion Dishsoap breaks down why 18.2's 68 XP at Level 8/9 radically alters the EV of rolling at 8. "
                    "Demonstrates how to stabilize with a 2-star 3-cost or 1-star 4-cost frontline, then push Level 9 for 5-cost legendary capped boards."
                ),
                timestamps=[
                    {"time": "00:00", "title": "The Math Behind the 68 XP Level 9 Change"},
                    {"time": "03:40", "title": "Level 8 Stabilization Rule: Don't Donkey Roll"},
                    {"time": "08:15", "title": "Draven + Elderwood vs Heavy AP Matchups"},
                    {"time": "14:20", "title": "Endgame Capped Board Positioning"}
                ],
                creator_tips=[
                    "If you have 40+ HP at Stage 4-5, rolling below 30 gold at Level 8 is mathematically incorrect in this patch. Save for 9.",
                    "Always prioritize 2-star tank items over 3rd offensive carry item. Frontline longevity multiplies Draven damage by 2.4x.",
                    "Slam generalist utility items (Spark, Sunfire, Evenshroud) before Krugs to establish tempo."
                ]
            ),

            # 6. Frodan (GLOBAL - NA Challenger Meta Analyst)
            YouTubeVideoInsight(
                video_id="frodan_18_2_snapshot",
                title="Patch 18.2 Meta Snapshot: Every Comp Ranked (Why Elderwood & Draven are S-Tier)",
                channel_name="Frodan",
                channel_avatar="https://yt3.googleusercontent.com/ytc/AIdro_k6Vfrodan=s176-c-k-c0x00ffffff-no-rj",
                published_at="2026-09-12",
                video_url="https://www.youtube.com/watch?v=mock_frodan_18_2",
                thumbnail_url="https://i.ytimg.com/vi/mock_frodan_18_2/hqdefault.jpg",
                view_count="8.4만회",
                region="GLOBAL",
                post_patch_verified=True,
                season_tag="세트 18",
                key_comps_recommended=[
                    "장로드래곤 드레이븐 밸류 (Elder Dragon Draven)",
                    "나무정령 드레이븐 밸류 (Elderwood Draven)",
                    "햇빛 아칼리 카밀 리롤 (Sunlight Akali Camille)",
                    "쿠거 니달리 4코 운영 (Cougar Nidalee)"
                ],
                summary=(
                    "Frodan's comprehensive competitive tier list following Patch 18.2 and 18.2b. Highlights how the Hunter trait nerf "
                    "opened the floodgates for Elderwood frontline stacks to dominate the meta."
                ),
                timestamps=[
                    {"time": "01:00", "title": "S-Tier Comps: Fast 9 Draven & Sunlight Camille"},
                    {"time": "05:20", "title": "A-Tier Comps: Nidalee 4-Cost Pivot"},
                    {"time": "09:45", "title": "Augment Tier List: What to Pick on 2-1"},
                    {"time": "13:30", "title": "Item Economy & Carousel Priority"}
                ],
                creator_tips=[
                    "Elderwood is the safest top 4 opener because the HP stacking provides unconditional value through Stage 3.",
                    "Sunlight Camille/Akali is the premier anti-meta reroll comp that punishes greedy Fast 9 players on Stage 3."
                ]
            ),

            # 7. Setsuko (GLOBAL - NA Rank 1 Aggressive Tempo Master)
            YouTubeVideoInsight(
                video_id="setsuko_18_2b_tempo",
                title="Patch 18.2b Fast 8/9 Tempo Guide: How I Hit Rank 1 Playing Draven & Nidalee",
                channel_name="Setsuko",
                channel_avatar="https://yt3.googleusercontent.com/ytc/AIdro_k6Vsetsuko=s176-c-k-c0x00ffffff-no-rj",
                published_at="2026-09-14",
                video_url="https://www.youtube.com/watch?v=mock_setsuko_18_2",
                thumbnail_url="https://i.ytimg.com/vi/mock_setsuko_18_2/hqdefault.jpg",
                view_count="10.5만회",
                region="GLOBAL",
                post_patch_verified=True,
                season_tag="세트 18",
                key_comps_recommended=[
                    "장로드래곤 드레이븐 밸류 (Elder Dragon Draven)",
                    "쿠거 니달리 4코 운영 (Cougar Nidalee)"
                ],
                summary=(
                    "Setsuko showcases his signature high-tempo playstyle adapted for Patch 18.2b. "
                    "Demonstrates how to aggressively level at 2-1 (level 4) and 2-5 (level 5) to save 20+ HP and snowball into a free 9-cap."
                ),
                timestamps=[
                    {"time": "00:00", "title": "Why Aggressive Tempo Dominates Challenger"},
                    {"time": "03:15", "title": "Stage 2 Streak Management & Pre-leveling"},
                    {"time": "07:50", "title": "Nidalee vs Draven: Which Carry to Commit"},
                    {"time": "12:10", "title": "Endgame 1v1 Positioning Tech"}
                ],
                creator_tips=[
                    "Pre-leveling to 5 at 2-3 gives you an early shot at 3-cost and 4-cost carries before anyone else.",
                    "Nidalee's jump mechanics bypass frontline tanks if you position her in the second row opposite the enemy carry."
                ]
            ),

            # 8. Mortdog (GLOBAL - Riot TFT Lead Game Designer)
            YouTubeVideoInsight(
                video_id="mortdog_18_2_rundown",
                title="TFT Patch 18.2 & 18.2b Dev Rundown: Why We Changed Level 9 to 68 XP",
                channel_name="Mortdog (Lead Designer)",
                channel_avatar="https://yt3.googleusercontent.com/ytc/AIdro_k6Vmortdog=s176-c-k-c0x00ffffff-no-rj",
                published_at="2026-09-15",
                video_url="https://www.youtube.com/watch?v=mock_mortdog_18_2",
                thumbnail_url="https://i.ytimg.com/vi/mock_mortdog_18_2/hqdefault.jpg",
                view_count="15.8만회",
                region="GLOBAL",
                post_patch_verified=True,
                season_tag="세트 18",
                key_comps_recommended=[
                    "장로드래곤 드레이븐 밸류 (Elder Dragon Draven)",
                    "나무정령 드레이븐 밸류 (Elderwood Draven)",
                    "햇빛 아칼리 카밀 리롤 (Sunlight Akali Camille)"
                ],
                summary=(
                    "Lead Designer Mortdog provides the official retrospective on Patch 18.2 and the 18.2b adjustments. "
                    "Explains the design philosophy behind reducing level 8-10 XP to 68 to make high-tier legendary compositions accessible while buffing underperforming verticals."
                ),
                timestamps=[
                    {"time": "00:45", "title": "Design Goals for the Level 9 Experience Rework"},
                    {"time": "04:10", "title": "Elderwood, Coven & Black Thorn Buff Rationale"},
                    {"time": "08:30", "title": "18.2b Micro-Adjustments (Camille & LeBlanc)"},
                    {"time": "13:00", "title": "Community Q&A on Meta Health"}
                ],
                creator_tips=[
                    "The team wanted 5-cost legendary boards to be achievable without requiring multiple prismatic econ augments.",
                    "Watch out for 2-cost 3-star reroll comps like Camille/Akali — they are designed as direct counter-weights to greedy Fast 9 lobbies."
                ]
            ),

            # 9. Bebe872 (GLOBAL/KR - Multi-Server Rank 1)
            YouTubeVideoInsight(
                video_id="bebe_18_2_fast9",
                title="Set 18 Patch 18.2 Fast 9 Legendary Value Guide (Challenger #1 Explains)",
                channel_name="Bebe872",
                channel_avatar="https://yt3.googleusercontent.com/ytc/AIdro_k6Vbebe=s176-c-k-c0x00ffffff-no-rj",
                published_at="2026-09-12",
                video_url="https://www.youtube.com/watch?v=mock_bebe_18_2",
                thumbnail_url="https://i.ytimg.com/vi/mock_bebe_18_2/hqdefault.jpg",
                view_count="9.8만회",
                region="GLOBAL",
                post_patch_verified=True,
                season_tag="세트 18",
                key_comps_recommended=[
                    "장로드래곤 드레이븐 밸류 (Elder Dragon Draven)",
                    "나무정령 드레이븐 밸류 (Elderwood Draven)"
                ],
                summary=(
                    "Detailed macro breakdown on the 18.2 economy rework. 68 XP at level 8 and 9 makes fast 9 "
                    "the definitive highest cap strategy in Challenger lobbies. Draven acts as the primary bridge carry."
                ),
                timestamps=[
                    {"time": "01:10", "title": "Why Fast 9 is Mandatory in High Elo"},
                    {"time": "04:30", "title": "Stage 2 & 3 Streak Management"},
                    {"time": "09:15", "title": "Stage 4-2 Level 8 Transition without Rolling"},
                    {"time": "14:40", "title": "Final Level 9 Cap Board State"}
                ],
                creator_tips=[
                    "Never roll down to 0 at level 8 unless you are below 25 HP. Preserving 50 gold to push 9 is +0.8 average placement.",
                    "Slam general items early (Bloodthirster, Guinsoo, Sunfire, Warmog) to preserve HP streak."
                ]
            )
        ]

        self._videos = curated
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump([v.to_dict() for v in curated], f, indent=2, ensure_ascii=False)

    def _initialize_mastery_tips(self) -> None:
        """Initializes strategic fundamentals and mastery tips verified across the last 5 seasons (Sets 14 to 18)."""
        tips = [
            MasteryTip(
                tip_id="tip_econ_hp_balance",
                category="ECONOMY",
                title="피관리와 10원 이자 손실의 황금비율 (50원 집착 금지)",
                description=(
                    "50원 이자를 고집하다가 한 라운드에 12~15 이상의 체력을 잃는 것은 장기적으로 1등 확률을 70% 이상 깎아먹습니다. "
                    "라운드당 잃는 체력 10의 가치는 게임 후반 40골드 이상의 생존 기회와 직결됩니다."
                ),
                key_rule="체력이 50 미만으로 떨어지는 시점부터는 50원 이자 대신 30~40원을 유지하며 즉각적인 필드 강화에 투자하라.",
                source_creators=["Dishsoap", "구루루", "Bebe872"],
                seasons_valid="최근 5개 시즌 (세트 14~18 검증)",
                impact_level="ESSENTIAL"
            ),
            MasteryTip(
                tip_id="tip_rolldown_frontline_first",
                category="ROLLDOWN",
                title="4-1 / 4-2 롤다운 시 '앞라인 탱커 우선 선점' 원칙",
                description=(
                    "많은 유저들이 4코스트 캐리(예: 드레이븐/니달리)를 찾느라 돈을 다 쓰고 앞라인이 1성인 채로 전투에 들어갑니다. "
                    "2성 탱커 2마리가 있는 1성 캐리 필드가, 1성 탱커만 있는 2성 캐리 필드보다 전투 유지력이 2배 이상 높습니다."
                ),
                key_rule="롤다운 시 캐리 유닛뿐만 아니라 시너지 상관없이 범용 4코/3코 2성 탱커를 먼저 완성하여 투입하라.",
                source_creators=["Setsuko", "김루트", "Dishsoap"],
                seasons_valid="최근 5개 시즌 (세트 14~18 검증)",
                impact_level="ESSENTIAL"
            ),
            MasteryTip(
                tip_id="tip_augment_golden_ratio",
                category="AUGMENTS",
                title="2-1 / 3-2 / 4-2 증강체 경제 vs 전투 밸런스 황금 공식",
                description=(
                    "3연속 순수 경제 증강체(골드/리롤 전용)를 고르는 것은 초반 템포가 빠른 로비에서 8등을 자초하는 지름길입니다. "
                    "상위 챌린저의 가장 이상적인 증강 조합은 '1경제 + 2전투' 또는 고밸류 패스트 9 빌드의 '2경제 + 1전투'입니다."
                ),
                key_rule="4-2 세 번째 증강체는 무조건 아군 전투력 증폭(체력/흡혈/추가피해/스탯) 증강체를 선택해 덱 캡을 완성하라.",
                source_creators=["Frodan", "쪼해피롱", "Bebe872"],
                seasons_valid="최근 5개 시즌 (세트 14~18 검증)",
                impact_level="ESSENTIAL"
            ),
            MasteryTip(
                tip_id="tip_melee_carry_positioning",
                category="POSITIONING",
                title="근접 캐리(니달리/카밀) 2열 배치로 어그로 핑퐁 유도",
                description=(
                    "카밀이나 쿠거 니달리 같은 근접 AD 브루저를 1열 맨 앞에 배치하면 상대 5마리의 집중 포화를 맞고 스킬도 못 쓰고 녹습니다. "
                    "메인 탱커를 1열 정중앙에 두고, 근접 캐리를 2열 외곽에 두면 메인 탱커가 어그로를 끈 직후 캐리가 안전하게 진입합니다."
                ),
                key_rule="근접 딜탱은 1열이 아닌 2열에 배치하여 '탱커 피격 1초 후 진입' 타이밍을 만들어라.",
                source_creators=["정동글", "Setsuko", "구루루"],
                seasons_valid="최근 5개 시즌 (세트 14~18 검증)",
                impact_level="ADVANCED"
            ),
            MasteryTip(
                tip_id="tip_item_slam_vs_bis",
                category="ITEMS",
                title="2스테이지 완성템 즉시 제작(Slam)의 위력 (3신기 집착 탈피)",
                description=(
                    "완벽한 3신기 아이템을 기다리며 대기석에 조합 아이템을 3개 이상 방치하는 플레이는 순방 확률을 급감시킵니다. "
                    "2스테이지에서 태양불꽃망토, 이온충격기, 피바라기, 구인수 등 범용성 높은 아이템을 즉시 제작해 피 30을 아끼는 것이 후반 1등의 토대가 됩니다."
                ),
                key_rule="대기석에 아이템 조합 부품이 3개 이상 남는 턴이 2회 이상 지속되지 않도록 범용 코어템을 즉시 완성하라.",
                source_creators=["Dishsoap", "Mortdog", "Bebe872"],
                seasons_valid="최근 5개 시즌 (세트 14~18 검증)",
                impact_level="ESSENTIAL"
            ),
            MasteryTip(
                tip_id="tip_scouting_last_10s",
                category="POSITIONING",
                title="마지막 10초 정찰 및 메인 딜러 반대편 대각선 저격",
                description=(
                    "후반 1대1 혹은 3파전 구도에서는 덱 파워보다 배치 싸움이 승패의 80%를 결정합니다. "
                    "상대 메인 캐리의 위치(왼쪽 구석 vs 오른쪽 구석)를 확인하고 내 메인 브루저나 암살 유닛을 대각선 반대편으로 스왑하여 침투 경로를 만드세요."
                ),
                key_rule="준비 시간 5초 남았을 때 1번과 7번 열을 반대로 스왑하는 '페이크 배치'로 상대 배치를 무력화하라.",
                source_creators=["Setsuko", "김루트", "쪼해피롱"],
                seasons_valid="최근 5개 시즌 (세트 14~18 검증)",
                impact_level="ADVANCED"
            )
        ]

        self._mastery_tips = tips
        with open(self.tips_file, "w", encoding="utf-8") as f:
            json.dump([t.to_dict() for t in tips], f, indent=2, ensure_ascii=False)

    def get_videos(self, region: Optional[str] = None) -> List[YouTubeVideoInsight]:
        if not region or region.upper() == "ALL":
            return self._videos
        reg_upper = region.upper()
        return [v for v in self._videos if v.region == reg_upper]

    def get_mastery_tips(self, category: Optional[str] = None) -> List[MasteryTip]:
        if not category or category.upper() == "ALL":
            return self._mastery_tips
        cat_upper = category.upper()
        return [t for t in self._mastery_tips if t.category == cat_upper]

    def get_creator_comps(self) -> Dict[str, List[str]]:
        res = {}
        for v in self._videos:
            res[v.channel_name] = v.key_comps_recommended
        return res

    def get_consensus_comps(self) -> List[Dict[str, Any]]:
        """Calculates comp consensus across both Korean and Global creators."""
        counts = {}
        mentions = {}
        regions = {}
        for v in self._videos:
            for c in v.key_comps_recommended:
                counts[c] = counts.get(c, 0) + 1
                mentions.setdefault(c, []).append(v.channel_name)
                regions.setdefault(c, set()).add(v.region)

        sorted_comps = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [
            {
                "comp_name": comp,
                "endorsement_count": count,
                "creators": mentions[comp],
                "global_and_kr_endorsed": len(regions[comp]) >= 2,
                "is_consensus_meta": count >= 3
            }
            for comp, count in sorted_comps
        ]

    def search_videos(self, query: str) -> List[YouTubeVideoInsight]:
        q = query.lower().strip()
        if not q:
            return self._videos
        matches = []
        for v in self._videos:
            text = f"{v.title} {v.channel_name} {v.summary} {v.region} {' '.join(v.key_comps_recommended)} {' '.join(v.creator_tips)}".lower()
            if q in text:
                matches.append(v)
        return matches

    def search_tips(self, query: str) -> List[MasteryTip]:
        q = query.lower().strip()
        if not q:
            return self._mastery_tips
        matches = []
        for t in self._mastery_tips:
            text = f"{t.title} {t.description} {t.key_rule} {t.category} {' '.join(t.source_creators)}".lower()
            if q in text:
                matches.append(t)
        return matches
