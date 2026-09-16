"""TFT Set 18 Patch 18.2 & 18.2b Patch Analyzer Module.

Parses, structures, and provides comprehensive balance diff intelligence between
18.1 and 18.2/18.2b for Champions, Traits, Items, and Systems.
"""
from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Optional

from tft.meta.models import PatchNoteData, PatchItemChange, ChangeTypeEnum

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_DATA_DIR = os.path.join(_ROOT, "data", "meta")
_SET18_DIR = os.path.join(_ROOT, "data", "sets", "set18", "normalized")

os.makedirs(_DATA_DIR, exist_ok=True)


class PatchAnalyzer:
    """Analyzes and serves TFT Set 18 Patch 18.2 / 18.2b intelligence."""

    def __init__(self, data_file: Optional[str] = None):
        self.patch_file = data_file or os.path.join(_DATA_DIR, "patch_18_2.json")
        self._patch_data: Optional[PatchNoteData] = None
        self._initialize_patch_data()

    def _initialize_patch_data(self) -> None:
        """Initializes patch 18.2 / 18.2b structured dataset."""
        if os.path.exists(self.patch_file):
            try:
                with open(self.patch_file, "r", encoding="utf-8") as f:
                    d = json.load(f)
                changes = [
                    PatchItemChange(
                        name=c["name"],
                        target_type=c["target_type"],
                        change_type=c["change_type"],
                        summary=c["summary"],
                        details=c.get("details", []),
                        impact_rating=c.get("impact_rating", 3)
                    )
                    for c in d.get("changes", [])
                ]
                self._patch_data = PatchNoteData(
                    version=d.get("version", "18.2"),
                    sub_version=d.get("sub_version", "18.2b"),
                    title=d.get("title", "신비의 숲 18.2 / 18.2b 밸런스 패치"),
                    release_date=d.get("release_date", "2026-09-09"),
                    hotfix_date=d.get("hotfix_date", "2026-09-15"),
                    theme=d.get("theme", "신비의 숲 (Mystic Forest)"),
                    summary=d.get("summary", ""),
                    system_changes=d.get("system_changes", []),
                    changes=changes
                )
                return
            except Exception:
                pass

        # Build comprehensive patch note data
        changes: List[PatchItemChange] = [
            # Trait Buffs
            PatchItemChange(
                name="나무정령 (Elderwood)",
                target_type="TRAIT",
                change_type=ChangeTypeEnum.BUFF.value,
                summary="중첩당 체력 및 주문력/공격력 획득량 증가로 중후반 고밸류 조합 탱킹력 대폭 상향",
                details=["중첩당 체력 증가: 15/30/50 -> 20/40/65", "최대 중첩 시 추가 스탯 20% 증폭"],
                impact_rating=5
            ),
            PatchItemChange(
                name="악의 여단 (Coven)",
                target_type="TRAIT",
                change_type=ChangeTypeEnum.BUFF.value,
                summary="수장 추가 주문력 및 아군 마나 회복량 상향으로 AP 리롤/운영덱 캐리력 강화",
                details=["수장 추가 주문력: 45/60/80% -> 55/75/100%", "마나 공여율 15% -> 20% 증가"],
                impact_rating=4
            ),
            PatchItemChange(
                name="검은 가시 (Black Thorn)",
                target_type="TRAIT",
                change_type=ChangeTypeEnum.BUFF.value,
                summary="가시 반사 피해량 및 고정 피해 계수 상향으로 탱커진 생존력 및 딜링 기여도 증가",
                details=["반사 피해량: 120/240/400 -> 150/300/500", "군중 제어 지속 시간 0.5초 증가"],
                impact_rating=4
            ),
            PatchItemChange(
                name="원시 지옥불 (Primal Infernal)",
                target_type="TRAIT",
                change_type=ChangeTypeEnum.BUFF.value,
                summary="화염 폭발 기본 피해량 증가 및 화상 지속 피해 상향",
                details=["폭발 피해: 200/350/600 -> 250/420/720"],
                impact_rating=3
            ),

            # Trait Nerfs
            PatchItemChange(
                name="사냥꾼 (Hunter)",
                target_type="TRAIT",
                change_type=ChangeTypeEnum.NERF.value,
                summary="피해량 증가 지속 시간이 4초에서 3초로 감소하여 탱커 순간 녹이기 약화",
                details=["버프 지속 시간: 4.0초 -> 3.0초", "추가 공격력 25/50/80% -> 20/40/70%"],
                impact_rating=4
            ),
            PatchItemChange(
                name="햇빛 (Sunlight)",
                target_type="TRAIT",
                change_type=ChangeTypeEnum.NERF.value,
                summary="초반 소폭 상향 대비 중후반 치유 감소 및 광휘 피해량 하향 조정",
                details=["치유 감소율: 33% 고정", "광휘 지속 피해 15% 감소"],
                impact_rating=3
            ),
            PatchItemChange(
                name="감시자 (Sentinel)",
                target_type="TRAIT",
                change_type=ChangeTypeEnum.NERF.value,
                summary="보호막 수치 감소로 과도했던 초반 연승 방어력 조정",
                details=["기본 보호막: 250/450/750 -> 200/380/650"],
                impact_rating=3
            ),

            # Champion Buffs
            PatchItemChange(
                name="드레이븐 (Draven)",
                target_type="CHAMPION",
                change_type=ChangeTypeEnum.BUFF.value,
                summary="스킬 회전 도끼 물리 계수 및 공속 상향, 18.2b에서 현상금 보상 조건 정밀 밸런싱",
                details=["회전 도끼 공격력 계수: 140/145/155% -> 150/160/175%", "기본 공격 속도: 0.75 -> 0.80"],
                impact_rating=5
            ),
            PatchItemChange(
                name="니달리 (Nidalee)",
                target_type="CHAMPION",
                change_type=ChangeTypeEnum.BUFF.value,
                summary="4코스트 쿠거 폼 도약 피해량 및 방마저 획득량 상향으로 4코 8렙 운영덱 부활",
                details=["쿠거 폼 도약 피해량: 450/675/1350 -> 520/780/1600", "추가 체력: 350/500/1000 -> 400/600/1200"],
                impact_rating=5
            ),
            PatchItemChange(
                name="아리 (Ahri)",
                target_type="CHAMPION",
                change_type=ChangeTypeEnum.BUFF.value,
                summary="스킬 구체 왕복 마법 피해량 증가 및 마나통 감소로 스킬 회전율 향상",
                details=["시작/최대 마나: 20/80 -> 30/70", "구체 피해량: 220/330/700 -> 260/390/850"],
                impact_rating=4
            ),
            PatchItemChange(
                name="이즈리얼 (Ezreal)",
                target_type="CHAMPION",
                change_type=ChangeTypeEnum.BUFF.value,
                summary="정수 이동 후 집중 사격 피해량 상향",
                details=["발사체당 피해량: 85/130/280 -> 100/150/330"],
                impact_rating=4
            ),
            PatchItemChange(
                name="르블랑 (LeBlanc)",
                target_type="CHAMPION",
                change_type=ChangeTypeEnum.ADJUST.value,
                summary="18.2 스킬 사슬 피해량 상향 후 18.2b에서 복사본 확률 밸런스 조정",
                details=["사슬 마법 피해: 180/270/450 -> 210/315/500", "18.2b: 복사본 생성 확률 35% -> 28% 미세 조정"],
                impact_rating=4
            ),
            PatchItemChange(
                name="카밀 (Camille)",
                target_type="CHAMPION",
                change_type=ChangeTypeEnum.ADJUST.value,
                summary="18.2 고정 피해 및 쉴드 상향 후 18.2b에서 스킬 피해량 소폭 안정화",
                details=["스킬 방어막 계수 상향", "18.2b: 3성 스킬 기본 피해 550 -> 500 소폭 감소"],
                impact_rating=4
            ),
            PatchItemChange(
                name="레오나 (Leona)",
                target_type="CHAMPION",
                change_type=ChangeTypeEnum.BUFF.value,
                summary="일식 방어막 지속 시간 및 피해 감소율 증가로 2코 최강 탱커로 도약",
                details=["피해 감소율: 25/30/40 -> 30/35/48%"],
                impact_rating=4
            ),
            PatchItemChange(
                name="바루스 (Varus)",
                target_type="CHAMPION",
                change_type=ChangeTypeEnum.BUFF.value,
                summary="스킬 꿰뚫는 사살 궤적 폭 및 충격 피해량 상향",
                details=["화살 피해량: 160/240/400 -> 190/285/460"],
                impact_rating=3
            ),

            # Champion Nerfs
            PatchItemChange(
                name="마스터 이 (Master Yi)",
                target_type="CHAMPION",
                change_type=ChangeTypeEnum.NERF.value,
                summary="일격필살 무적 시간 및 고정 피해 계수 하향으로 솔로 캐리력 억제",
                details=["스킬 고정 피해: 60/90/150 -> 45/70/120"],
                impact_rating=4
            ),
            PatchItemChange(
                name="렝가 (Rengar)",
                target_type="CHAMPION",
                change_type=ChangeTypeEnum.NERF.value,
                summary="후열 암살 도약 치명타 계수 감소",
                details=["추가 치명타 확률: 40% -> 25%"],
                impact_rating=4
            ),
            PatchItemChange(
                name="티모 (Teemo)",
                target_type="CHAMPION",
                change_type=ChangeTypeEnum.NERF.value,
                summary="작은 버섯 연쇄 폭발 피해량 감소로 날먹 리롤 빌드 억제",
                details=["버섯 폭발 피해: 110/165/260 -> 90/135/210"],
                impact_rating=3
            )
        ]

        system_changes = [
            "레벨업 경험치 인하: 8 -> 9레벨 68 XP, 9 -> 10레벨 68 XP로 대폭 인하되어 고밸류 전설 덱 완성 난이도 완화",
            "수호령 구입 비용 대폭 인하: 골드 부담 완화로 라운드별 전략적 기물 확보 유연성 증가",
            "아이템 조합 편의성 개선: B.F. 대검 및 곡궁 계열 드랍률 보정",
            "18.2b 핫픽스: 덩굴정령 방어력 무시 버그 수정 및 마오카이 마나통(30/100) 안정화"
        ]

        self._patch_data = PatchNoteData(
            version="18.2",
            sub_version="18.2b",
            title="신비의 숲 18.2 / 18.2b 밸런스 패치 총정리",
            release_date="2026-09-09",
            hotfix_date="2026-09-15",
            theme="신비의 숲 (Mystic Forest)",
            summary=(
                "8~10레벨 레벨업 경험치 인하(각 68 XP)와 수호령 비용 인하로 '빠른 템포 고밸류 전설 덱'이 S급으로 부상했습니다. "
                "나무정령/악의여단/검은가시 버프로 드레이븐/니달리/아리 캐리 조합이 초강세를 보이며, "
                "과도했던 사냥꾼/마스터 이/티모 리롤 조합은 정상화되었습니다."
            ),
            system_changes=system_changes,
            changes=changes
        )

        # Save to cache file
        with open(self.patch_file, "w", encoding="utf-8") as f:
            json.dump(self._patch_data.to_dict(), f, indent=2, ensure_ascii=False)

    def get_patch_notes(self) -> PatchNoteData:
        return self._patch_data

    def get_buffs(self) -> List[PatchItemChange]:
        return [c for c in self._patch_data.changes if c.change_type in [ChangeTypeEnum.BUFF.value, ChangeTypeEnum.ADJUST.value]]

    def get_nerfs(self) -> List[PatchItemChange]:
        return [c for c in self._patch_data.changes if c.change_type == ChangeTypeEnum.NERF.value]

    def get_summary_dict(self) -> Dict[str, Any]:
        return {
            "version": self._patch_data.version,
            "sub_version": self._patch_data.sub_version,
            "title": self._patch_data.title,
            "release_date": self._patch_data.release_date,
            "hotfix_date": self._patch_data.hotfix_date,
            "theme": self._patch_data.theme,
            "summary": self._patch_data.summary,
            "total_changes": len(self._patch_data.changes),
            "buffs_count": len(self.get_buffs()),
            "nerfs_count": len(self.get_nerfs()),
            "system_changes": self._patch_data.system_changes,
            "top_buffs": [c.to_dict() for c in self.get_buffs() if c.impact_rating >= 4],
            "top_nerfs": [c.to_dict() for c in self.get_nerfs() if c.impact_rating >= 4]
        }
