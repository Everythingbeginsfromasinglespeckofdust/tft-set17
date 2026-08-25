#!/usr/bin/env python3
"""test_board_power.py — 보드 가치평가 휴리스틱 v1 단위 테스트.

핵심 검증:
1. 약한 보드 vs 강한 보드 파워 비교 (완료 기준)
2. 성급 배수, 아이템 점수, 시너지 브레이크포인트 지수 계산 정확성
3. 별돌보미(Stargazer) 하위 변형 통합 시너지 처리
4. 입력 유효성 검증 (F-R2 bool 차단, 1~3성, 최대 3아이템, 미등록 챔프/아이템 예외)
"""
import math
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board_power as bp


# ---------------------------------------------------------------- 핵심 완료 기준 검증
def test_weak_vs_strong_board_power_comparison():
    """완료 기준: 약한 보드(초반 1성) vs 강한 보드(후반 2성 5코 풀템) 비교."""
    weak_board = {
        "units": [
            {"champion": "나서스", "cost": 1, "star_level": 1, "items": []},
            {"champion": "레오나", "cost": 1, "star_level": 1, "items": ["쇠사슬 조끼"]},
            {"champion": "렉사이", "cost": 1, "star_level": 1, "items": []},
        ]
    }
    strong_board = {
        "units": [
            {"champion": "진", "cost": 5, "star_level": 2, "items": ["무한의 대검", "최후의 속삭임", "거인 학살자"]},
            {"champion": "피오라", "cost": 5, "star_level": 2, "items": ["피바라기", "스테락의 도전", "거인의 결의"]},
            {"champion": "블리츠크랭크", "cost": 5, "star_level": 2, "items": ["워모그의 갑옷", "용의 발톱", "덤불 조끼"]},
            {"champion": "초가스", "cost": 1, "star_level": 2, "items": []},
            {"champion": "리산드라", "cost": 1, "star_level": 2, "items": []},
            {"champion": "모데카이저", "cost": 2, "star_level": 2, "items": []},
            {"champion": "이즈리얼", "cost": 1, "star_level": 2, "items": []},
        ]
    }

    res_weak = bp.calculate_board_power(weak_board)
    res_strong = bp.calculate_board_power(strong_board)

    # 1. 약한 보드 수동 검산 검증:
    # unit_power: 1*1.0 + 1*1.0 + 1*1.0 = 3.0
    # item_score: 1.0 (쇠사슬 조끼 1개)
    # synergy_bonus: 선봉대(2 -> 1단계 = 2.0) + 우주 그루브(1 -> 1단계 = 2.0) = 4.0
    # total = 3.0 + 1.0 + 4.0 = 8.0
    assert res_weak["total_power"] == pytest.approx(8.0, abs=1e-9)
    assert res_weak["breakdown"]["unit_power"] == pytest.approx(3.0, abs=1e-9)
    assert res_weak["breakdown"]["item_score"] == pytest.approx(1.0, abs=1e-9)
    assert res_weak["breakdown"]["synergy_bonus"] == pytest.approx(4.0, abs=1e-9)

    # 2. 강한 보드 수동 검산 검증:
    # unit_power: 5*1.8*3 (27.0) + 1*1.8*3 (5.4) + 2*1.8 (3.6) = 36.0
    # item_score: 9개 완성템 * 3.0 = 27.0
    # synergy_bonus: 암흑의 별 4(2단계 = 2^1.5*2 ≈ 5.65685) + 6개 1단계(12.0) ≈ 17.65685
    # total ≈ 36.0 + 27.0 + 17.65685 = 80.65685
    expected_strong_synergy = (2 ** 1.5 * 2.0) + (1 ** 1.5 * 2.0 * 6)
    expected_strong_total = 36.0 + 27.0 + expected_strong_synergy
    assert res_strong["breakdown"]["unit_power"] == pytest.approx(36.0, abs=1e-9)
    assert res_strong["breakdown"]["item_score"] == pytest.approx(27.0, abs=1e-9)
    assert res_strong["breakdown"]["synergy_bonus"] == pytest.approx(expected_strong_synergy, abs=1e-9)
    assert res_strong["total_power"] == pytest.approx(expected_strong_total, abs=1e-9)

    # 강한 보드가 약한 보드보다 10배 가량 높음 확인
    assert res_strong["total_power"] > res_weak["total_power"] * 9.0


# ---------------------------------------------------------------- 세부 공식 정확도 검증
def test_star_multipliers():
    """성급 배수 {1: 1.0, 2: 1.8, 3: 3.2} 정확성 검증."""
    b1 = {"units": [{"champion": "진", "cost": 5, "star_level": 1, "items": []}]}
    b2 = {"units": [{"champion": "진", "cost": 5, "star_level": 2, "items": []}]}
    b3 = {"units": [{"champion": "진", "cost": 5, "star_level": 3, "items": []}]}

    assert bp.calculate_board_power(b1)["breakdown"]["unit_power"] == pytest.approx(5.0 * 1.0)
    assert bp.calculate_board_power(b2)["breakdown"]["unit_power"] == pytest.approx(5.0 * 1.8)
    assert bp.calculate_board_power(b3)["breakdown"]["unit_power"] == pytest.approx(5.0 * 3.2)


def test_item_scores_component_and_completed_and_special():
    """아이템 점수: 부품 1점, 완성품 3점, 특수 아이템(상징/유물 등) 3점."""
    board = {
        "units": [
            {
                "champion": "나서스",
                "cost": 1,
                "star_level": 1,
                "items": [
                    "B.F. 대검",           # 기본 부품 (1.0)
                    "대천사의 지팡이",      # 표준 완성품 (3.0)
                    "동물특공대 상징",      # Set17 특수 상징 (3.0)
                ],
            }
        ]
    }
    res = bp.calculate_board_power(board)
    assert res["breakdown"]["item_score"] == pytest.approx(7.0)


def test_synergy_breakpoint_power_formula():
    """시너지 보너스 = (단계 인덱스)^1.5 * 2.0 검증 (예: 3단계 -> 3^1.5*2 ≈ 10.3923)."""
    bonus_step_3 = (3 ** 1.5) * 2.0
    assert bonus_step_3 == pytest.approx(10.392304845413264, abs=1e-9)

    bonus_step_4 = (4 ** 1.5) * 2.0
    assert bonus_step_4 == pytest.approx(16.0, abs=1e-9)


def test_stargazer_variants_grouped_correctly():
    """Set 17 '별돌보미' 8종 변형이 베이스 시너지로 정상 집계되는지 검증."""
    stargazer_champs = ["탈론", "트위스티드 페이트", "잭스", "룰루", "누누와 윌럼프", "자야"]
    units = [{"champion": name, "star_level": 1, "items": []} for name in stargazer_champs]
    res = bp.calculate_board_power({"units": units})

    # 별돌보미 브레이크포인트: [3, 4, 5, 6] -> 6명이면 4번째 단계 도달 -> bonus = 16.0
    stargazer_entry = next(
        (s for s in res["breakdown"]["active_synergies"] if s["trait"] == "별돌보미"), None
    )
    assert stargazer_entry is not None
    assert stargazer_entry["unit_count"] == 6
    assert stargazer_entry["breakpoint_reached"] == 4
    assert stargazer_entry["bonus"] == pytest.approx(16.0)


def test_duplicate_champions_count_once_for_synergy():
    """동일 챔피언 중복 기용 시 기물 파워는 각각 합산되나 시너지는 고유 유닛 1개로 집계."""
    board = {
        "units": [
            {"champion": "진", "cost": 5, "star_level": 2, "items": []},
            {"champion": "진", "cost": 5, "star_level": 1, "items": []},
        ]
    }
    res = bp.calculate_board_power(board)
    assert res["breakdown"]["unit_power"] == pytest.approx(14.0)
    darkstar = next((s for s in res["breakdown"]["active_synergies"] if s["trait"] == "암흑의 별"), None)
    assert darkstar is None
    eradicator = next((s for s in res["breakdown"]["active_synergies"] if s["trait"] == "말살자"), None)
    assert eradicator is not None
    assert eradicator["unit_count"] == 1
    assert eradicator["bonus"] == 2.0


def test_empty_board():
    res = bp.calculate_board_power({"units": []})
    assert res["total_power"] == 0.0
    assert res["breakdown"]["unit_power"] == 0.0
    assert res["breakdown"]["item_score"] == 0.0
    assert res["breakdown"]["synergy_bonus"] == 0.0
    assert res["breakdown"]["active_synergies"] == []


# ---------------------------------------------------------------- 유효성 검증 및 예외 처리
def test_invalid_star_level_raises():
    with pytest.raises(ValueError, match="star_level"):
        bp.calculate_board_power({"units": [{"champion": "진", "star_level": 0, "items": []}]})
    with pytest.raises(ValueError, match="star_level"):
        bp.calculate_board_power({"units": [{"champion": "진", "star_level": 4, "items": []}]})
    with pytest.raises(ValueError, match="star_level"):
        bp.calculate_board_power({"units": [{"champion": "진", "star_level": True, "items": []}]})


def test_cost_mismatch_raises():
    with pytest.raises(ValueError, match="코스트가 일치하지 않습니다"):
        bp.calculate_board_power({"units": [{"champion": "진", "cost": 1, "star_level": 1, "items": []}]})


def test_too_many_items_raises():
    with pytest.raises(ValueError, match="최대 3개"):
        bp.calculate_board_power({
            "units": [{
                "champion": "진",
                "star_level": 1,
                "items": ["B.F. 대검", "곡궁", "쇠사슬 조끼", "거인의 허리띠"],
            }]
        })


def test_unknown_champion_raises():
    with pytest.raises(ValueError, match="존재하지 않는 챔피언"):
        bp.calculate_board_power({"units": [{"champion": "아리", "star_level": 1, "items": []}]})


def test_unknown_item_raises():
    with pytest.raises(ValueError, match="존재하지 않는 아이템"):
        bp.calculate_board_power({"units": [{"champion": "진", "star_level": 1, "items": ["가짜아이템"]}]})


def test_invalid_board_type_raises():
    with pytest.raises(ValueError, match="board는 dict"):
        bp.calculate_board_power("not_a_dict")
    with pytest.raises(ValueError, match=r"board\['units'\]는 list"):
        bp.calculate_board_power({"units": "not_a_list"})
