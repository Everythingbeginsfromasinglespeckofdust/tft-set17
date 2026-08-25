#!/usr/bin/env python3
"""TFT Set 17 상점 리롤(shop reroll) 계산 모듈.

규칙 (2026-08-24 교차검증 완료):
    상점 리롤은 항상 고정 2골드.
    가능한 리롤 횟수 = floor(보유 골드 / reroll_cost).
    "구간별 유지율" 메커니즘은 실제 게임에 존재하지 않는다(제거됨).

상수 출처: 05_xp_gold.json의 `reroll_cost` (하드코딩 금지).
    JSON에 구간별 유지율 필드(예: `reroll_discount`)가 다시 등장하면
    이전 오류의 재발이므로 이 모듈은 계산에 사용하지 않고 ValueError로
    즉시 알린다(침묵 금지).
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
GOLD_JSON = os.path.join(_HERE, "..", "tft_guide", "05_xp_gold.json")

# 구간별 유지율 메커니즘을 암시하는 키 토큰(소문자). 이런 키가 JSON에 있으면
# 제거됐어야 할 메커니즘의 재발로 간주한다.
_FORBIDDEN_KEY_TOKENS = ("discount", "retention")


def _forbidden_keys(obj, prefix=""):
    """JSON 객체를 재귀 탐색해 금지 토큰을 포함한 모든 키 경로 반환."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            lk = str(k).lower()
            if any(tok in lk for tok in _FORBIDDEN_KEY_TOKENS):
                found.append(path)
            found.extend(_forbidden_keys(v, path))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found.extend(_forbidden_keys(v, f"{prefix}[{i}]"))
    return found


def load_reroll_rules(path: str = GOLD_JSON) -> dict:
    """05_xp_gold.json에서 리롤 규칙을 로드.

    Returns:
        {"reroll_cost": int}

    Raises:
        ValueError: reroll_cost가 양의 정수가 아니거나,
            구간별 유지율 필드(제거된 메커니즘)가 JSON에 재발하면.
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    bad = _forbidden_keys(raw)
    if bad:
        raise ValueError(
            "구간별 유지율 필드가 05_xp_gold.json에 재발했습니다(제거된 메커니즘): "
            f"{bad}. 리롤은 고정 2골드로만 계산하며 이 필드는 무시/사용 금지입니다."
        )

    cost = raw.get("reroll_cost")
    if not isinstance(cost, int) or isinstance(cost, bool) or cost <= 0:
        raise ValueError(f"reroll_cost는 양의 정수여야 합니다: {cost!r}")
    return {"reroll_cost": cost}


def _rules(rules):
    return load_reroll_rules() if rules is None else rules


def reroll_count(gold: int, rules=None) -> int:
    """보유 골드로 가능한 리롤 횟수 = floor(gold / reroll_cost).

    Raises:
        ValueError: gold가 음수 또는 정수가 아니면.
    """
    if not isinstance(gold, int) or isinstance(gold, bool):
        raise ValueError(f"gold는 정수여야 합니다: {gold!r}")
    if gold < 0:
        raise ValueError(f"gold는 음수일 수 없습니다: {gold}")
    return gold // _rules(rules)["reroll_cost"]


def reroll_trajectory(gold: int, num_rerolls: int, rules=None) -> list:
    """num_rerolls만큼 리롤했을 때의 골드 트래젝션 (고정 비용 선형 차감).

    Returns:
        [{"reroll": 1, "cost": 2, "gold_after": g0-cost}, ...]

    Raises:
        ValueError: num_rerolls < 1, gold < 0, 또는 num_rerolls이
            가능한 횟수(reroll_count(gold))를 초과하면.
    """
    if not isinstance(num_rerolls, int) or isinstance(num_rerolls, bool):
        raise ValueError(f"num_rerolls는 정수여야 합니다: {num_rerolls!r}")
    if num_rerolls < 1:
        raise ValueError(f"num_rerolls는 1 이상이어야 합니다: {num_rerolls}")
    if not isinstance(gold, int) or isinstance(gold, bool):
        raise ValueError(f"gold는 정수여야 합니다: {gold!r}")
    if gold < 0:
        raise ValueError(f"gold는 음수일 수 없습니다: {gold}")

    cost = _rules(rules)["reroll_cost"]
    possible = gold // cost
    if num_rerolls > possible:
        raise ValueError(
            f"num_rerolls={num_rerolls}이/가 가능한 횟수({possible})를 초과합니다 "
            f"(gold={gold}, cost={cost})"
        )

    out = []
    g = gold
    for i in range(1, num_rerolls + 1):
        g -= cost
        out.append({"reroll": i, "cost": cost, "gold_after": g})
    return out
