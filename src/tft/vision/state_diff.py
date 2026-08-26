"""TFT Vision State Diff Engine: Computes fine-grained transitions between consecutive Observations."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from tft.vision.observation import Observation, CardObservation, UnitObservation


class SlotTransitionType(str, Enum):
    """상점 단일 슬롯의 상태 변화 유형."""
    UNCHANGED = "UNCHANGED"     # 동일 챔피언 유지
    EMPTIED = "EMPTIED"         # 챔피언 -> EMPTY (구매 발생)
    FILLED = "FILLED"           # EMPTY -> 챔피언 (리롤 후 재생성)
    REFRESHED = "REFRESHED"     # 챔피언 A -> 챔피언 B (리롤 발생)


@dataclass(frozen=True)
class SlotTransition:
    """개별 상점 슬롯의 이전/이후 상태 및 전이 유형."""
    slot_index: int
    before_champion: Optional[str]
    before_cost: Optional[int]
    before_empty: bool
    after_champion: Optional[str]
    after_cost: Optional[int]
    after_empty: bool
    transition_type: SlotTransitionType

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slot_index": self.slot_index,
            "before_champion": self.before_champion,
            "before_cost": self.before_cost,
            "before_empty": self.before_empty,
            "after_champion": self.after_champion,
            "after_cost": self.after_cost,
            "after_empty": self.after_empty,
            "transition_type": self.transition_type.value
        }


@dataclass
class StateDiff:
    """두 시점의 Observation 간의 물리적 상태 차이 컨테이너."""
    timestamp_before: float
    timestamp_after: float
    dt_sec: float

    # Economic and Level deltas
    gold_before: Optional[int] = None
    gold_after: Optional[int] = None
    gold_delta: Optional[int] = None

    hp_before: Optional[int] = None
    hp_after: Optional[int] = None
    hp_delta: Optional[int] = None

    level_before: Optional[int] = None
    level_after: Optional[int] = None
    level_delta: Optional[int] = None

    xp_before: Optional[int] = None
    xp_after: Optional[int] = None
    xp_delta: Optional[int] = None

    # Shop Transitions
    shop_changes: List[SlotTransition] = field(default_factory=list)
    shop_slots_changed: int = 0
    shop_slots_emptied: int = 0
    shop_slots_filled: int = 0
    shop_slots_refreshed: int = 0

    # Board and Bench Transitions
    bench_before: List[str] = field(default_factory=list)
    bench_after: List[str] = field(default_factory=list)
    board_before: List[str] = field(default_factory=list)
    board_after: List[str] = field(default_factory=list)

    units_added_bench: List[str] = field(default_factory=list)
    units_removed_bench: List[str] = field(default_factory=list)
    units_added_board: List[str] = field(default_factory=list)
    units_removed_board: List[str] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_before": self.timestamp_before,
            "timestamp_after": self.timestamp_after,
            "dt_sec": round(self.dt_sec, 3),
            "gold_delta": self.gold_delta,
            "hp_delta": self.hp_delta,
            "level_delta": self.level_delta,
            "xp_delta": self.xp_delta,
            "shop_slots_changed": self.shop_slots_changed,
            "shop_slots_emptied": self.shop_slots_emptied,
            "shop_slots_filled": self.shop_slots_filled,
            "shop_slots_refreshed": self.shop_slots_refreshed,
            "shop_changes": [sc.to_dict() for sc in self.shop_changes],
            "units_added_bench": self.units_added_bench,
            "units_removed_bench": self.units_removed_bench,
            "units_added_board": self.units_added_board,
            "units_removed_board": self.units_removed_board
        }


def compute_state_diff(obs_before: Observation, obs_after: Observation) -> StateDiff:
    """두 연속 Observation으로부터 StateDiff 객체를 순수 계산."""
    t_before = obs_before.timestamp_sec
    t_after = obs_after.timestamp_sec
    dt = max(0.0, t_after - t_before)

    # 1. Delta computations
    gold_delta = None
    if obs_before.gold_val is not None and obs_after.gold_val is not None:
        gold_delta = obs_after.gold_val - obs_before.gold_val

    hp_delta = None
    if obs_before.hp_val is not None and obs_after.hp_val is not None:
        hp_delta = obs_after.hp_val - obs_before.hp_val

    level_delta = None
    if obs_before.level_val is not None and obs_after.level_val is not None:
        level_delta = obs_after.level_val - obs_before.level_val

    xp_delta = None
    if obs_before.xp_val is not None and obs_after.xp_val is not None:
        xp_delta = obs_after.xp_val - obs_before.xp_val

    # 2. Shop transitions
    shop_changes: List[SlotTransition] = []
    slots_changed = 0
    slots_emptied = 0
    slots_filled = 0
    slots_refreshed = 0

    before_cards = {c.slot_index: c for c in obs_before.shop_cards}
    after_cards = {c.slot_index: c for c in obs_after.shop_cards}

    for slot_i in range(5):
        cb = before_cards.get(slot_i)
        ca = after_cards.get(slot_i)

        b_name = cb.champion_pred if cb and not cb.is_empty else None
        b_cost = cb.cost_pred if cb and not cb.is_empty else None
        b_empty = cb.is_empty if cb is not None else True

        a_name = ca.champion_pred if ca and not ca.is_empty else None
        a_cost = ca.cost_pred if ca and not ca.is_empty else None
        a_empty = ca.is_empty if ca is not None else True

        # Determine transition type
        if b_empty and a_empty:
            tt = SlotTransitionType.UNCHANGED
        elif not b_empty and a_empty:
            tt = SlotTransitionType.EMPTIED
            slots_changed += 1
            slots_emptied += 1
        elif b_empty and not a_empty:
            tt = SlotTransitionType.FILLED
            slots_changed += 1
            slots_filled += 1
        else:  # both non-empty
            if b_name == a_name:
                tt = SlotTransitionType.UNCHANGED
            else:
                tt = SlotTransitionType.REFRESHED
                slots_changed += 1
                slots_refreshed += 1

        shop_changes.append(SlotTransition(
            slot_index=slot_i,
            before_champion=b_name,
            before_cost=b_cost,
            before_empty=b_empty,
            after_champion=a_name,
            after_cost=a_cost,
            after_empty=a_empty,
            transition_type=tt
        ))

    # 3. Bench and Board Unit Transitions
    bench_before = [u.champion_pred for u in obs_before.bench_detections if u.champion_pred]
    bench_after = [u.champion_pred for u in obs_after.bench_detections if u.champion_pred]
    board_before = [u.champion_pred for u in obs_before.field_detections if u.champion_pred]
    board_after = [u.champion_pred for u in obs_after.field_detections if u.champion_pred]

    # Simple multiset differences
    bb_copy = list(bench_before)
    units_added_bench = []
    for u in bench_after:
        if u in bb_copy:
            bb_copy.remove(u)
        else:
            units_added_bench.append(u)

    ba_copy = list(bench_after)
    units_removed_bench = []
    for u in bench_before:
        if u in ba_copy:
            ba_copy.remove(u)
        else:
            units_removed_bench.append(u)

    f_copy = list(board_before)
    units_added_board = []
    for u in board_after:
        if u in f_copy:
            f_copy.remove(u)
        else:
            units_added_board.append(u)

    fa_copy = list(board_after)
    units_removed_board = []
    for u in board_before:
        if u in fa_copy:
            fa_copy.remove(u)
        else:
            units_removed_board.append(u)

    return StateDiff(
        timestamp_before=t_before,
        timestamp_after=t_after,
        dt_sec=dt,
        gold_before=obs_before.gold_val,
        gold_after=obs_after.gold_val,
        gold_delta=gold_delta,
        hp_before=obs_before.hp_val,
        hp_after=obs_after.hp_val,
        hp_delta=hp_delta,
        level_before=obs_before.level_val,
        level_after=obs_after.level_val,
        level_delta=level_delta,
        xp_before=obs_before.xp_val,
        xp_after=obs_after.xp_val,
        xp_delta=xp_delta,
        shop_changes=shop_changes,
        shop_slots_changed=slots_changed,
        shop_slots_emptied=slots_emptied,
        shop_slots_filled=slots_filled,
        shop_slots_refreshed=slots_refreshed,
        bench_before=bench_before,
        bench_after=bench_after,
        board_before=board_before,
        board_after=board_after,
        units_added_bench=units_added_bench,
        units_removed_bench=units_removed_bench,
        units_added_board=units_added_board,
        units_removed_board=units_removed_board
    )
