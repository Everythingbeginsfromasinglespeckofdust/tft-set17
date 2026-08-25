#!/usr/bin/env python3
"""TFT Set 17 레벨업 비용 로더.

데이터 출처 (모든 상수는 JSON — 하드코딩 금지)
---------------------------------------------
- 레벨업 XP 테이블: 05_xp_gold.json `level_up_xp`
  (레벨2~10: 2/6/10/20/36/60/68/68/68, {from_level, to_level, xp_required} 행)
- 최대 레벨: 05_xp_gold.json `max_level` (10)
- XP 구매 단가(기본값 2골드=4XP): 05_xp_gold.json에 없는 클라이언트 상수이므로
  함수 기본 인자로 받는다(티켓 지정 시그니처).

모델
----
- cum[L] = 레벨 1에서 레벨 L까지 도달하는 데 필요한 누적 XP
- 현재 누적 투자 = cum[current_level] + current_xp
- target_level 도달 필요 XP = cum[target_level] − 현재 누적 투자
- 필요 골드 = ceil(필요 XP / buy_xp_amount) × buy_xp_cost_gold
  (XP는 buy_xp_amount 단위로만 구매 가능 — 부족분이라도 1회 구매)
- current_level >= target_level (또는 필요 XP가 0)이면 0

교차 검증 (ValueError)
----------------------
- 전 정수 인자: 엄밀한 int (bool 불허 — F-R2 패턴, roll_probability._check_int 재사용)
- current_level < 1 또는 max_level 초과
- target_level < 1 또는 max_level 초과
- current_xp < 0
- current_level >= 2 이고 current_xp가 current_level 도달에 필요한 XP
  (level_up_xp의 xp_required)를 초과 → 물리적으로 불가능
  (예: 레벨2 도달 필요 XP가 2인데 current_level=2, current_xp=5)
- current_level == 1 이고 current_xp >= 레벨2 도달 필요 XP
  (레벨 1에서 레벨 2 바를 꽉 채워 들고 있으면 이미 레벨 2이므로)
"""
import json
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
GOLD_JSON = os.path.join(_HERE, "..", "tft_guide", "05_xp_gold.json")

# 이전 티켓의 정수 검증 헬퍼 재사용 (재구현 금지 — F-R2 bool 차단 패턴)
from roll_probability import _check_int  # noqa: E402


def _load_raw(path: str = GOLD_JSON) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _max_level(raw: dict) -> int:
    max_level = raw.get("max_level")
    if not isinstance(max_level, int) or isinstance(max_level, bool) or max_level < 1:
        raise ValueError(f"max_level은 양의 정수여야 합니다: {max_level!r}")
    return max_level


def load_levelup_table(path: str = GOLD_JSON) -> dict:
    """05_xp_gold.json의 level_up_xp를 {레벨: 해당 레벨 도달에 필요한 XP}로 로드.

    Returns:
        {2: 2, 3: 6, 4: 10, 5: 20, 6: 36, 7: 60, 8: 68, 9: 68, 10: 68}

    Raises:
        ValueError: level_up_xp가 2~max_level 연속 체인을 이루지 않으면
            (누락/중복 레벨, 비연속 행, 잘못된 타입/값).
    """
    raw = _load_raw(path)
    max_level = _max_level(raw)
    rows = raw.get("level_up_xp")
    if not isinstance(rows, list) or not rows:
        raise ValueError("05_xp_gold.json에 level_up_xp가 없습니다")

    table = {}
    for row in rows:
        frm, to, xp = row.get("from_level"), row.get("to_level"), row.get("xp_required")
        if not all(
            isinstance(v, int) and not isinstance(v, bool) and v > 0
            for v in (frm, to, xp)
        ):
            raise ValueError(f"level_up_xp 행이 유효하지 않습니다: {row!r}")
        if to - frm != 1:
            raise ValueError(f"level_up_xp 행은 연속 레벨이어야 합니다: {row!r}")
        if to in table:
            raise ValueError(f"레벨 {to}이/가 level_up_xp에 중복됩니다")
        table[to] = xp

    if sorted(table) != list(range(2, max_level + 1)):
        raise ValueError(
            f"level_up_xp가 2~{max_level} 연속 체인이 아닙니다: {sorted(table)}"
        )
    return table


def _cumulative(table: dict) -> list:
    """cum[i] = 레벨 1 → 레벨 i 누적 필요 XP. (인덱스 = 레벨)"""
    cum = []
    total = 0
    for level in range(0, max(table) + 1):
        if level >= 2:
            total += table[level]
        cum.append(total)
    return cum


def gold_to_reach_level(
    current_level: int,
    current_xp: int,
    target_level: int,
    buy_xp_cost_gold: int = 2,
    buy_xp_amount: int = 4,
) -> int:
    """target_level 도달에 필요한 골드 계산 (XP 구매 기준).

    Args:
        current_level: 현재 레벨 (1 ~ max_level)
        current_xp: 현재 레벨 바의 진행 XP
        target_level: 목표 레벨 (1 ~ max_level)
        buy_xp_cost_gold: 1회 구매 비용 (골드) — 기본 2
        buy_xp_amount: 1회 구매 XP량 — 기본 4

    Returns:
        필요 골드 (int). current_level >= target_level 또는 필요 XP가 0이면 0.

    Raises:
        ValueError: 정수 인자 검증 실패(블록 포함), 레벨 범위 초과,
            current_xp 음수, 또는 current_xp가 물리적으로 불가능할 때.
    """
    raw = _load_raw()
    max_level = _max_level(raw)
    table = load_levelup_table()

    current_level = _check_int("current_level", current_level)
    current_xp = _check_int("current_xp", current_xp)
    target_level = _check_int("target_level", target_level)
    buy_xp_cost_gold = _check_int("buy_xp_cost_gold", buy_xp_cost_gold)
    buy_xp_amount = _check_int("buy_xp_amount", buy_xp_amount)

    if buy_xp_cost_gold <= 0 or buy_xp_amount <= 0:
        raise ValueError(
            f"buy_xp_cost_gold/buy_xp_amount은 양의 정수여야 합니다: "
            f"{buy_xp_cost_gold}, {buy_xp_amount}"
        )
    if not 1 <= current_level <= max_level:
        raise ValueError(
            f"current_level은 1~{max_level} 사이여야 합니다: {current_level}"
        )
    if not 1 <= target_level <= max_level:
        raise ValueError(
            f"target_level은 1~{max_level} 사이여야 합니다 (최대 레벨 {max_level}): "
            f"{target_level}"
        )
    if current_xp < 0:
        raise ValueError(f"current_xp는 음수일 수 없습니다: {current_xp}")

    # 교차 검증: current_level 도달에 필요한 XP를 초과한 current_xp는
    # 물리적으로 불가능 (F-R1 성격의 교차 검증).
    if current_level >= 2:
        if current_xp > table[current_level]:
            raise ValueError(
                f"current_xp={current_xp}가 {current_level}레벨 도달에 필요한 XP"
                f"({table[current_level]})를 초과합니다 — 물리적으로 불가능"
            )
    elif current_xp >= table[2]:
        raise ValueError(
            f"current_xp={current_xp}가 레벨2 도달 필요 XP({table[2]}) 이상인데 "
            f"current_level=1입니다 — 물리적으로 불가능"
        )

    if current_level >= target_level:
        return 0

    cum = _cumulative(table)
    xp_needed = cum[target_level] - (cum[current_level] + current_xp)
    if xp_needed <= 0:
        return 0

    purchases = math.ceil(xp_needed / buy_xp_amount)
    return purchases * buy_xp_cost_gold
