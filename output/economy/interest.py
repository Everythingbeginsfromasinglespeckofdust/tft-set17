#!/usr/bin/env python3
"""TFT Set 17 골드 이자 계산 모듈.

규칙 (2026-08-24 교차검증 완료):
    매 턴 종료 시 지급, 이자 = interest_table 구간 참조.
    현재 테이블은 10골드 단위: 0-9→0, 10-19→1, 20-29→2, 30-39→3, 40-49→4, 50+→5 (상한 5).
    상한은 테이블 마지막 구간(50-99→5)이 50골드 이상 전체를 커버하도록 파싱되어
    max_gold 이상도 자동으로 상한 이자를 반환한다.

상수 출처: 05_xp_gold.json의 gold.interest_table (하드코딩 금지).
    - 테이블의 `gold` 필드는 "lo-hi" 문자열. 마지막 구간만 "50-99"처럼 상한 없이
      해석한다(hi는 무시).
    - JSON에 `formula` 문자열 필드가 있어도 계산에는 사용하지 않는다.
      테이블이 단일 진원(single source of truth)이다.
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
GOLD_JSON = os.path.join(_HERE, "..", "tft_guide", "05_xp_gold.json")

_parsed_table = None


def _parse_bands(table):
    """interest_table을 [(lo, hi_or_None, interest)]로 파싱.

    "10-19" → (10, 19, 1). 마지막 구간은 hi를 None(무제한)으로 처리한다.
    """
    bands = []
    for i, row in enumerate(table):
        lo, _, hi = str(row["gold"]).partition("-")
        bands.append((int(lo), None if i == len(table) - 1 else int(hi), int(row["interest"])))
    return bands


def load_interest_rules(path: str = GOLD_JSON):
    """05_xp_gold.json에서 이자 테이블을 로드.

    Returns:
        (bands, max_interest): bands = [(lo, hi_or_None, interest)...] 오름차순,
        max_interest = 테이블 내 최대 이자값.

    Raises:
        ValueError: 구간이 오름차순이 아니거나 겹치면.
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    table = raw.get("gold", {}).get("interest_table")
    if not isinstance(table, list) or not table:
        raise ValueError("05_xp_gold.json에 gold.interest_table이 없습니다")
    bands = _parse_bands(table)
    for (lo1, hi1, _), (lo2, hi2, _) in zip(bands, bands[1:]):
        if lo2 < lo1:
            raise ValueError(f"interest_table 구간이 오름차순이 아닙니다: {table}")
        if hi1 is not None and lo2 <= hi1:
            raise ValueError(f"interest_table 구간이 겹칩니다: {table}")
    return bands, max(b[2] for b in bands)


def _table():
    global _parsed_table
    if _parsed_table is None:
        _parsed_table = load_interest_rules()[0]
    return _parsed_table


def calculate_interest(gold: int) -> int:
    """보유 골드에 대한 1턴 이자 (interest_table 기준).

    Raises:
        ValueError: gold가 음수이면.
    """
    if not isinstance(gold, int) or isinstance(gold, bool):
        raise ValueError(f"gold는 정수여야 합니다: {gold!r}")
    if gold < 0:
        raise ValueError(f"gold는 음수일 수 없습니다: {gold}")
    for lo, hi, interest in _table():
        if lo <= gold and (hi is None or gold <= hi):
            return interest
    # 마지막 구간이 무제한이므로 도달 불가 (defensive)
    raise ValueError(f"gold={gold}를 처리하는 interest_table 구간이 없습니다")


def calculate_interest_trajectory(current_gold: int, num_turns: int) -> list:
    """num_turns 동안의 이자 트래젝션. 매 턴 종료 시 이자를 지급하고
    다음 턴은 이전 턴 종료 골드로 시작(복리).

    Returns:
        [{"turn": 1, "start_gold": g0, "interest": i1, "end_gold": g0+i1}, ...]

    Raises:
        ValueError: num_turns < 1, current_gold < 0.
    """
    if not isinstance(num_turns, int) or isinstance(num_turns, bool):
        raise ValueError(f"num_turns는 정수여야 합니다: {num_turns!r}")
    if num_turns < 1:
        raise ValueError(f"num_turns는 1 이상이어야 합니다: {num_turns}")
    if not isinstance(current_gold, int) or isinstance(current_gold, bool):
        raise ValueError(f"current_gold는 정수여야 합니다: {current_gold!r}")
    if current_gold < 0:
        raise ValueError(f"current_gold는 음수일 수 없습니다: {current_gold}")

    out = []
    gold = current_gold
    for turn in range(1, num_turns + 1):
        interest = calculate_interest(gold)
        out.append({"turn": turn, "start_gold": gold, "interest": interest, "end_gold": gold + interest})
        gold += interest
    return out
