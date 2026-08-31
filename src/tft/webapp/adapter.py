"""TFT Decision Assistant Human Input Adapter & GameState Builder v1.

Provides:
- HumanInputDTO & validation rules against Set 18 domain.
- GameStateBuilder: constructs canonical GameState from human input.
- DecisionPresenter: formats Frozen DecisionEngine outputs, score breakdowns, explanations, and structured Direction.
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


def load_set18_champions_roster() -> Dict[str, Dict[str, Any]]:
    """Load normalized Set 18 champions catalog."""
    if not os.path.exists(_SET18_CHAMPIONS_PATH):
        return {}
    with open(_SET18_CHAMPIONS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    roster = {}
    for c in data:
        name = c.get("name", "")
        if name:
            roster[name] = c
            # Also allow lowercase / clean lookup
            roster[name.lower()] = c
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
    """Turn-by-turn human game state input DTO."""
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
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HumanInputDTO":
        board_raw = data.get("board_units", [])
        bench_raw = data.get("bench_units", [])

        b_units = [
            UnitInputDTO(
                champion=u.get("champion", ""),
                cost=u.get("cost"),
                star_level=int(u.get("star_level", 1)),
                items=list(u.get("items", [])),
                position_row=u.get("position_row"),
                position_col=u.get("position_col"),
                slot_index=u.get("slot_index"),
                is_bench=False
            )
            for u in board_raw if u.get("champion")
        ]

        bench_units = [
            UnitInputDTO(
                champion=u.get("champion", ""),
                cost=u.get("cost"),
                star_level=int(u.get("star_level", 1)),
                items=list(u.get("items", [])),
                slot_index=u.get("slot_index"),
                is_bench=True
            )
            for u in bench_raw if u.get("champion")
        ]

        shop_raw = data.get("shop_units", [None] * 5)
        cleaned_shop = []
        for s in shop_raw[:5]:
            if s and str(s).strip() and str(s).upper() != "EMPTY":
                cleaned_shop.append(str(s).strip())
            else:
                cleaned_shop.append(None)
        while len(cleaned_shop) < 5:
            cleaned_shop.append(None)

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
            errors.append(f"Invalid stage_round format: '{dto.stage_round}'. Expected format like '2-1', '4-2'.")

        # 2. Player State ranges
        if dto.hp < 0 or dto.hp > 150:
            errors.append(f"HP must be between 0 and 150 (got {dto.hp}).")
        if dto.gold < 0 or dto.gold > 250:
            errors.append(f"Gold cannot be negative or exceed 250 (got {dto.gold}).")
        if dto.level < 1 or dto.level > 11:
            errors.append(f"Level must be between 1 and 11 (got {dto.level}).")
        if dto.xp < 0 or dto.xp > 200:
            errors.append(f"XP cannot be negative (got {dto.xp}).")

        # 3. Board Capacity
        if len(dto.board_units) > dto.level + 2:
            errors.append(f"Board units count ({len(dto.board_units)}) exceeds max allowed for Level {dto.level}.")

        # 4. Champion validation against Set 18
        for u in dto.board_units + dto.bench_units:
            champ_key = u.champion.strip()
            if champ_key not in SET18_CHAMPIONS and champ_key.lower() not in SET18_CHAMPIONS:
                errors.append(f"Champion '{u.champion}' is not in Set 18 roster.")
            if u.star_level not in (1, 2, 3):
                errors.append(f"Invalid star level {u.star_level} for {u.champion} (must be 1, 2, or 3).")
            if len(u.items) > 3:
                errors.append(f"Champion {u.champion} has {len(u.items)} items (max 3 allowed).")

        # 5. Shop validation
        for s in dto.shop_units:
            if s is not None and s.strip():
                if s.strip() not in SET18_CHAMPIONS and s.strip().lower() not in SET18_CHAMPIONS:
                    errors.append(f"Shop champion '{s}' is not in Set 18 roster.")

        return len(errors) == 0, errors

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
            c_meta = SET18_CHAMPIONS.get(u.champion) or SET18_CHAMPIONS.get(u.champion.lower(), {})
            cost = u.cost or c_meta.get("cost", 1)
            pos = None
            if u.position_row is not None and u.position_col is not None:
                pos = BoardPosition(row=u.position_row, col=u.position_col)
            board_units.append(Unit(
                champion=c_meta.get("name", u.champion),
                cost=cost,
                star_level=u.star_level,
                items=list(u.items),
                position=pos,
                is_bench=False
            ))

        bench_units: List[Unit] = []
        for u in dto.bench_units:
            c_meta = SET18_CHAMPIONS.get(u.champion) or SET18_CHAMPIONS.get(u.champion.lower(), {})
            cost = u.cost or c_meta.get("cost", 1)
            bench_units.append(Unit(
                champion=c_meta.get("name", u.champion),
                cost=cost,
                star_level=u.star_level,
                items=list(u.items),
                slot_index=u.slot_index,
                is_bench=True
            ))

        shop_units: List[Optional[str]] = []
        for s in dto.shop_units[:5]:
            if s:
                c_meta = SET18_CHAMPIONS.get(s) or SET18_CHAMPIONS.get(s.lower(), {})
                shop_units.append(c_meta.get("name", s))
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
    """Formats DecisionEngine / CalibrationAdapter results for UI display."""

    @staticmethod
    def derive_operational_direction(rec: Recommendation, state: GameState) -> Dict[str, Any]:
        """Derives structured operational roadmap (NOW, WATCH, THEN) from Engine output."""
        act = rec.recommended_action.action_type.value
        hp = state.player.hp
        gold = state.player.gold
        lvl = state.player.level

        now_desc = ""
        watch_list = []
        then_desc = ""

        if act == "ROLL":
            now_desc = f"Reroll shop aggressively (Budget: {gold}G) to stabilize board and hit key unit upgrades."
            watch_list = [
                "Stop rolling immediately if 2-star pairs hit or gold drops below 20G/30G interest threshold.",
                "Check bench space for holding transition copies."
            ]
            then_desc = "Preserve remaining economy for leveling once board power stabilizes."
        elif act == "SAVE_GOLD":
            now_desc = f"Hold current gold ({gold}G) to maximize interest compound (+{min(5, gold // 10)}G/round)."
            watch_list = [
                f"Watch HP ({hp}): If HP drops below 30, prepare immediate transition to ROLL.",
                f"Watch Stage: Next key level breakpoint at Level {lvl + 1}."
            ]
            then_desc = "Fast-level to next breakpoint once compound gold exceeds upgrade cost."
        elif act == "LEVEL_UP":
            now_desc = f"Invest gold to level up (Target: Level {min(10, lvl + 1)}) to field an extra unit and increase high-tier odds."
            watch_list = [
                "Ensure at least 10G~20G remains after leveling to preserve interest.",
                "Immediately place strongest bench unit or high-cost synergy on the extra board slot."
            ]
            then_desc = "Stabilize board on newly reached level before next economy phase."

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
            metrics_dict = {}
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
