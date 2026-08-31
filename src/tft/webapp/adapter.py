"""TFT Decision Assistant Human Input Adapter & GameState Builder v1.1.

Provides:
- HumanInputDTO & validation rules against Set 18 domain.
- GameStateBuilder: constructs canonical GameState from human input, with completeness calculation.
- DecisionPresenter: formats Frozen DecisionEngine outputs, score breakdowns, explanations, and structured Korean Direction.
- TurnDiffCalculator: computes differences between consecutive game turns.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple, Union
import json
import os
import re

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit, BoardPosition
from tft.domain.actions import ActionType
from tft.decision.models import Recommendation, ActionScore, Reason
from tft.calibration.integration.adapter import DecisionCalibrationAdapter, CalibrationMode, CalibratedDecisionResult
from tft.data.repositories import get_data_repository


# Load Set 18 Champions & Items for Validation
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_SET18_CHAMPIONS_PATH = os.path.join(_REPO, "data", "sets", "set18", "normalized", "champions.json")
_SET18_ITEMS_PATH = os.path.join(_REPO, "data", "sets", "set18", "normalized", "items.json")
_SET18_KOREAN_DATA_PATH = os.path.join(_REPO, "data", "sets", "set18", "raw", "communitydragon", "ko_kr.json")


def load_korean_name_mapping() -> Dict[str, str]:
    """Load English to Korean champion name mapping from CommunityDragon ko_kr.json."""
    if not os.path.exists(_SET18_KOREAN_DATA_PATH):
        return {}
    try:
        with open(_SET18_KOREAN_DATA_PATH, "r", encoding="utf-8") as f:
            ko_data = json.load(f)
        api_to_ko = {}
        for s in ko_data.get("setData", []):
            for c in s.get("champions", []):
                api_name = c.get("apiName", "")
                ko_name = c.get("name", "")
                if api_name and ko_name:
                    api_to_ko[api_name.lower()] = ko_name
                    clean_name = api_name.split("_")[-1]
                    api_to_ko[clean_name.lower()] = ko_name

        for c in ko_data.get("sets", {}).get("18", {}).get("champions", []):
            api_name = c.get("apiName", "")
            ko_name = c.get("name", "")
            if api_name and ko_name:
                api_to_ko[api_name.lower()] = ko_name
                clean_name = api_name.split("_")[-1]
                api_to_ko[clean_name.lower()] = ko_name
        return api_to_ko
    except Exception:
        return {}


_KO_NAME_MAP = load_korean_name_mapping()


def load_set18_champions_roster() -> Dict[str, Dict[str, Any]]:
    """Load normalized Set 18 champions catalog with Korean names."""
    if not os.path.exists(_SET18_CHAMPIONS_PATH):
        return {}
    with open(_SET18_CHAMPIONS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    roster = {}
    for c in data:
        name = c.get("name", "")
        char_id = c.get("character_id", "").lower()
        ko_name = _KO_NAME_MAP.get(char_id) or _KO_NAME_MAP.get(name.lower()) or name
        c_copy = dict(c)
        c_copy["name_ko"] = ko_name

        if name:
            roster[name] = c_copy
            roster[name.lower()] = c_copy
            roster[ko_name] = c_copy
            roster[ko_name.lower()] = c_copy
    return roster


def load_set18_items_roster() -> Dict[str, Dict[str, Any]]:
    """Load normalized Set 18 items catalog."""
    if not os.path.exists(_SET18_ITEMS_PATH):
        return {}
    with open(_SET18_ITEMS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = {}
    for item in data:
        name = item.get("name", "")
        if name:
            items[name] = item
            items[name.lower()] = item
    return items


SET18_CHAMPIONS = load_set18_champions_roster()
SET18_ITEMS = load_set18_items_roster()


@dataclass
class UnitInputDTO:
    champion: str
    cost: Optional[int] = None
    star_level: int = 1
    items: List[str] = field(default_factory=list)
    position_row: Optional[int] = None
    position_col: Optional[int] = None
    slot_index: Optional[int] = None
    is_bench: bool = False


@dataclass
class HumanInputDTO:
    """Turn-by-turn human game state input DTO v1.1."""
    stage_round: str = "2-1"
    hp: int = 100
    gold: int = 0
    level: int = 4
    xp: int = 0
    streak: int = 0
    board_units: List[UnitInputDTO] = field(default_factory=list)
    bench_units: List[UnitInputDTO] = field(default_factory=list)
    shop_units: List[Optional[str]] = field(default_factory=lambda: [None] * 5)
    item_bench: List[str] = field(default_factory=list)
    augments: List[str] = field(default_factory=list)
    calibration_mode: str = "OFF"
    video_timestamp_sec: Optional[float] = None
    actual_player_action: Optional[str] = "UNKNOWN"
    human_preferred_action: Optional[str] = "UNKNOWN"
    human_feedback: Optional[str] = "UNKNOWN"
    human_judgment: Optional[str] = "UNKNOWN"
    notes: str = ""

    def __post_init__(self):
        if self.human_feedback != "UNKNOWN" and self.human_judgment == "UNKNOWN":
            self.human_judgment = self.human_feedback
        elif self.human_judgment != "UNKNOWN" and self.human_feedback == "UNKNOWN":
            self.human_feedback = self.human_judgment

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HumanInputDTO":
        board_raw = data.get("board_units", [])
        bench_raw = data.get("bench_units", [])

        b_units = []
        for u in board_raw:
            if isinstance(u, dict) and u.get("champion"):
                b_units.append(UnitInputDTO(
                    champion=str(u["champion"]).strip(),
                    cost=u.get("cost"),
                    star_level=int(u.get("star_level", 1)),
                    items=list(u.get("items", [])),
                    position_row=u.get("position_row"),
                    position_col=u.get("position_col"),
                    slot_index=u.get("slot_index"),
                    is_bench=False
                ))
            elif isinstance(u, UnitInputDTO):
                b_units.append(u)

        bench_units = []
        for u in bench_raw:
            if isinstance(u, dict) and u.get("champion"):
                bench_units.append(UnitInputDTO(
                    champion=str(u["champion"]).strip(),
                    cost=u.get("cost"),
                    star_level=int(u.get("star_level", 1)),
                    items=list(u.get("items", [])),
                    slot_index=u.get("slot_index"),
                    is_bench=True
                ))
            elif isinstance(u, UnitInputDTO):
                bench_units.append(u)

        shop_raw = data.get("shop_units", [None] * 5)
        cleaned_shop = []
        for s in shop_raw[:5]:
            if s and str(s).strip() and str(s).upper() != "EMPTY":
                cleaned_shop.append(str(s).strip())
            else:
                cleaned_shop.append(None)
        while len(cleaned_shop) < 5:
            cleaned_shop.append(None)

        fb = data.get("human_feedback") or data.get("human_judgment") or "UNKNOWN"

        return cls(
            stage_round=str(data.get("stage_round", "2-1")).strip(),
            hp=int(data.get("hp", 100)),
            gold=int(data.get("gold", 0)),
            level=int(data.get("level", 4)),
            xp=int(data.get("xp", 0)),
            streak=int(data.get("streak", 0)),
            board_units=b_units,
            bench_units=bench_units,
            shop_units=cleaned_shop,
            item_bench=list(data.get("item_bench", [])),
            augments=list(data.get("augments", [])),
            calibration_mode=str(data.get("calibration_mode", "OFF")).upper(),
            video_timestamp_sec=float(data["video_timestamp_sec"]) if data.get("video_timestamp_sec") is not None else None,
            actual_player_action=data.get("actual_player_action", "UNKNOWN"),
            human_preferred_action=data.get("human_preferred_action", "UNKNOWN"),
            human_feedback=fb,
            human_judgment=fb,
            notes=str(data.get("notes", ""))
        )


class GameStateBuilder:
    """Validates HumanInputDTO and builds canonical GameState."""

    @staticmethod
    def validate_input(dto: HumanInputDTO) -> Tuple[bool, List[str]]:
        """Validates all fields against domain constraints."""
        errors: List[str] = []

        # 1. Stage / Round validation
        if not re.match(r"^[1-8]-[1-7]$", dto.stage_round):
            errors.append(f"스테이지 형식 오류: '{dto.stage_round}'. '2-1', '4-2' 형식이어야 합니다.")

        # 2. Player State ranges
        if dto.hp < 0 or dto.hp > 150:
            errors.append(f"체력(HP)은 0~150 사이여야 합니다 (입력값: {dto.hp}).")
        if dto.gold < 0 or dto.gold > 250:
            errors.append(f"골드는 음수이거나 250을 초과할 수 없습니다 (입력값: {dto.gold}).")
        if dto.level < 1 or dto.level > 11:
            errors.append(f"레벨은 1~11 사이여야 합니다 (입력값: {dto.level}).")
        if dto.xp < 0 or dto.xp > 200:
            errors.append(f"경험치(XP)는 음수일 수 없습니다 (입력값: {dto.xp}).")

        # 3. Board Capacity
        if len(dto.board_units) > dto.level + 2:
            errors.append(f"필드 기물 수({len(dto.board_units)})가 레벨 {dto.level}의 최대 허용치를 초과했습니다.")

        # 4. Champion validation against Set 18
        for u in dto.board_units + dto.bench_units:
            champ_name = u.champion.strip() if hasattr(u, "champion") else u.get("champion", "").strip()
            if champ_name not in SET18_CHAMPIONS and champ_name.lower() not in SET18_CHAMPIONS:
                errors.append(f"챔피언 '{champ_name}'은(는) 세트 18 로스터에 존재하지 않습니다.")
            star = u.star_level if hasattr(u, "star_level") else u.get("star_level", 1)
            if star not in (1, 2, 3):
                errors.append(f"챔피언 {champ_name}의 성급({star}성)이 올바르지 않습니다 (1, 2, 3성만 가능).")
            items = u.items if hasattr(u, "items") else u.get("items", [])
            if len(items) > 3:
                errors.append(f"챔피언 {champ_name}의 아이템 수({len(items)}개)가 3개를 초과했습니다.")

        # 5. Shop validation
        for s in dto.shop_units:
            if s is not None and str(s).strip() and str(s).upper() != "EMPTY":
                s_name = str(s).strip()
                if s_name not in SET18_CHAMPIONS and s_name.lower() not in SET18_CHAMPIONS:
                    errors.append(f"상점 챔피언 '{s_name}'은(는) 세트 18 로스터에 존재하지 않습니다.")

        return len(errors) == 0, errors

    @staticmethod
    def calculate_completeness(dto: HumanInputDTO) -> Dict[str, Any]:
        """Calculates state entry completeness metrics."""
        checklist = {
            "stage": bool(dto.stage_round and re.match(r"^[1-8]-[1-7]$", dto.stage_round)),
            "hp": dto.hp > 0,
            "gold": dto.gold >= 0,
            "level": dto.level >= 1,
            "xp": dto.xp >= 0,
            "board": len(dto.board_units) > 0,
            "bench": True,
            "shop": len(dto.shop_units) == 5
        }
        score = sum(1 for v in checklist.values() if v)
        total = len(checklist)
        return {
            "score": score,
            "total": total,
            "percentage": round((score / total) * 100, 1),
            "checklist": checklist
        }

    @staticmethod
    def build_game_state(dto: HumanInputDTO) -> GameState:
        """Constructs canonical GameState from validated HumanInputDTO."""
        parts = dto.stage_round.split("-")
        stage = int(parts[0]) if parts[0].isdigit() else 2
        rnd = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

        player = PlayerState(
            gold=dto.gold,
            level=dto.level,
            xp=dto.xp,
            hp=dto.hp,
            streak=dto.streak
        )

        board_units: List[Unit] = []
        for u in dto.board_units:
            name = u.champion if hasattr(u, "champion") else u.get("champion", "")
            c_meta = SET18_CHAMPIONS.get(name) or SET18_CHAMPIONS.get(name.lower(), {})
            canonical_name = c_meta.get("name", name)
            cost = getattr(u, "cost", None) or c_meta.get("cost", 1)
            star = getattr(u, "star_level", 1)
            items = list(getattr(u, "items", []))
            pos = None
            if hasattr(u, "position_row") and u.position_row is not None:
                pos = BoardPosition(row=u.position_row, col=u.position_col or 0)
            board_units.append(Unit(
                champion=canonical_name,
                cost=cost,
                star_level=star,
                items=items,
                position=pos,
                is_bench=False
            ))

        bench_units: List[Unit] = []
        for u in dto.bench_units:
            name = u.champion if hasattr(u, "champion") else u.get("champion", "")
            c_meta = SET18_CHAMPIONS.get(name) or SET18_CHAMPIONS.get(name.lower(), {})
            canonical_name = c_meta.get("name", name)
            cost = getattr(u, "cost", None) or c_meta.get("cost", 1)
            star = getattr(u, "star_level", 1)
            items = list(getattr(u, "items", []))
            bench_units.append(Unit(
                champion=canonical_name,
                cost=cost,
                star_level=star,
                items=items,
                slot_index=getattr(u, "slot_index", None),
                is_bench=True
            ))

        shop_units: List[Optional[str]] = []
        for s in dto.shop_units[:5]:
            if s and str(s).strip() and str(s).upper() != "EMPTY":
                s_clean = str(s).strip()
                c_meta = SET18_CHAMPIONS.get(s_clean) or SET18_CHAMPIONS.get(s_clean.lower(), {})
                shop_units.append(c_meta.get("name", s_clean))
            else:
                shop_units.append(None)
        while len(shop_units) < 5:
            shop_units.append(None)

        return GameState(
            stage=stage,
            round=rnd,
            stage_round=dto.stage_round,
            player=player,
            board_units=board_units,
            bench_units=bench_units,
            shop_units=shop_units,
            item_bench=list(dto.item_bench),
            augments=list(dto.augments),
            opponents=[]
        )


class DecisionPresenter:
    """Formats DecisionEngine / CalibrationAdapter results for UI display with Korean direction."""

    @staticmethod
    def derive_operational_direction(rec: Recommendation, state: GameState) -> Dict[str, Any]:
        """Derives structured Korean operational roadmap (NOW, WATCH, THEN) from Engine output."""
        act = rec.recommended_action.action_type.value
        hp = state.player.hp
        gold = state.player.gold
        lvl = state.player.level

        now_desc = ""
        watch_list = []
        then_desc = ""

        if act == "ROLL":
            now_desc = f"골드를 사용하여 상점을 적극적으로 리롤(Reroll)하여 보드를 안정화하고 주요 2성/3성 업그레이드를 완성합니다. (보유 예산: {gold}G)"
            watch_list = [
                "2성 페어가 완성되거나 골드가 20G/30G 이자 구간 밑으로 떨어지면 리롤을 멈추세요.",
                "전환용 기물 보관을 위해 대기석(벤치) 여유 공간을 확인하세요."
            ]
            then_desc = "보드 파워가 안정화되면 남은 골드를 아껴 다음 레벨업을 준비합니다."
        elif act == "SAVE_GOLD":
            now_desc = f"현재 골드({gold}G)를 유지하여 이자 복리(+{min(5, gold // 10)}G/라운드)를 극대화하고 경제력을 비축합니다."
            watch_list = [
                f"체력(HP {hp}): 체력이 30 미만으로 떨어지면 즉시 리롤(ROLL) 모드로 전환하세요.",
                f"스테이지: 다음 핵심 레벨업 타이밍({lvl + 1}레벨)을 주시하세요."
            ]
            then_desc = "비축된 골드로 레벨업 비용을 충당하여 상위 레벨로 빠르게 전환(Fast-Level)합니다."
        elif act == "LEVEL_UP":
            now_desc = f"골드를 투자하여 즉시 레벨업(목표: {min(10, lvl + 1)}레벨)하고 필드에 추가 기물을 배치하여 고코스트 유닛 확률을 높입니다."
            watch_list = [
                "레벨업 후 최소 10G~20G의 기본 이자 골드가 남는지 확인하세요.",
                "추가된 보드 슬롯에 가장 강력한 벤치 기물이나 시너지 유닛을 즉시 배치하세요."
            ]
            then_desc = "새로 도달한 레벨에서 보드를 안정화한 뒤 다음 경제 구간으로 진입합니다."

        return {
            "now": {"action": act, "description": now_desc},
            "watch": watch_list,
            "then": {"description": then_desc}
        }

    @classmethod
    def format_decision_response(
        cls,
        state: GameState,
        rec: Recommendation,
        calib_res: Optional[CalibratedDecisionResult] = None,
        calib_mode: str = "OFF"
    ) -> Dict[str, Any]:
        """Builds complete JSON response for Web UI."""
        # Top recommended action
        rec_action = calib_res.action if calib_res else rec.recommended_action.action_type.value
        rec_score = calib_res.scores.get(rec_action, rec.score) if calib_res else rec.score
        rec_margin = calib_res.margin if calib_res else rec.decision_margin

        # Action Scores Breakdown
        all_actions = []
        for asc in rec.all_scores:
            act_name = asc.action.action_type.value
            calib_score = calib_res.scores.get(act_name, asc.score) if calib_res else asc.score
            breakdown_dict = {}
            for k, v in asc.breakdown.items():
                breakdown_dict[k] = {
                    "raw_value": round(v.raw_value, 2),
                    "normalized_value": round(v.normalized_value, 3),
                    "weight": round(v.weight, 2),
                    "contribution": round(v.contribution, 4),
                    "description": v.description
                }
            all_actions.append({
                "action": act_name,
                "score": round(calib_score, 4),
                "confidence": round(asc.confidence, 2),
                "metrics": {mk: round(mv, 3) if isinstance(mv, (int, float)) else mv for mk, mv in asc.metrics.items()},
                "breakdown": breakdown_dict
            })

        all_actions.sort(key=lambda x: x["score"], reverse=True)

        # Reasons list
        reasons_list = [
            {
                "code": r.code,
                "summary": r.summary,
                "evidence": r.evidence,
                "impact": round(r.impact, 4)
            }
            for r in rec.reasons
        ]

        # Operational Direction
        direction = cls.derive_operational_direction(rec, state)

        return {
            "recommended_action": rec_action,
            "score": round(rec_score, 4),
            "action_score_gap": round(rec_margin, 4),
            "confidence": round(rec.confidence, 2),
            "all_scores": all_actions,
            "reasons": reasons_list,
            "current_direction": direction,
            "calibration": {
                "mode": calib_mode,
                "applied": calib_res.calibration_applied if calib_res else False,
                "is_flip": calib_res.is_flip if calib_res else False,
                "flip_direction": calib_res.flip_direction if calib_res else "NO_FLIP",
                "base_action": calib_res.base_action if calib_res else rec.recommended_action.action_type.value,
                "base_scores": calib_res.base_scores if calib_res else {asc.action.action_type.value: asc.score for asc in rec.all_scores}
            },
            "game_state_summary": state.to_dict()
        }


class TurnDiffCalculator:
    """Computes incremental state difference between two turns."""

    @staticmethod
    def _extract_name(u: Any) -> str:
        if isinstance(u, dict):
            return u.get("champion", "")
        return getattr(u, "champion", "")

    @classmethod
    def compute_turn_diff(cls, prev_dto: HumanInputDTO, curr_dto: HumanInputDTO) -> Dict[str, Any]:
        """Calculates delta between previous turn and current turn."""
        hp_diff = curr_dto.hp - prev_dto.hp
        gold_diff = curr_dto.gold - prev_dto.gold
        lvl_diff = curr_dto.level - prev_dto.level
        xp_diff = curr_dto.xp - prev_dto.xp

        prev_board_names = set(cls._extract_name(u) for u in prev_dto.board_units if cls._extract_name(u))
        curr_board_names = set(cls._extract_name(u) for u in curr_dto.board_units if cls._extract_name(u))

        added_units = sorted(list(curr_board_names - prev_board_names))
        removed_units = sorted(list(prev_board_names - curr_board_names))

        return {
            "prev_stage": prev_dto.stage_round,
            "curr_stage": curr_dto.stage_round,
            "hp": {"prev": prev_dto.hp, "curr": curr_dto.hp, "diff": hp_diff},
            "gold": {"prev": prev_dto.gold, "curr": curr_dto.gold, "diff": gold_diff},
            "level": {"prev": prev_dto.level, "curr": curr_dto.level, "diff": lvl_diff},
            "xp": {"prev": prev_dto.xp, "curr": curr_dto.xp, "diff": xp_diff},
            "board": {
                "added_units": added_units,
                "removed_units": removed_units,
                "count_diff": len(curr_dto.board_units) - len(prev_dto.board_units)
            }
        }
