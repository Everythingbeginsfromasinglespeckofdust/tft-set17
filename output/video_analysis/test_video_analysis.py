#!/usr/bin/env python3
"""test_video_analysis.py — 비디오 분석 및 보드 인식기 단위/통합 테스트."""
import os
import sys
import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from board_recognizer import BoardRecognizer
from timeline_smoother import TimelineSmoother, parse_stage_order, format_stage_order


def test_stage_order_parser():
    """스테이지-라운드 문자열과 정수 순서값 변환 검증."""
    assert parse_stage_order("2-1") == 21
    assert parse_stage_order("2-5") == 25
    assert parse_stage_order("3-1") == 31
    assert parse_stage_order("invalid") is None
    assert parse_stage_order(None) is None

    assert format_stage_order(21) == "2-1"
    assert format_stage_order(35) == "3-5"


def test_timeline_smoother_stage_continuity_and_noise_rejection():
    """시계열 스무더: 빈값 유지 및 역행 노이즈 무시 검증."""
    smoother = TimelineSmoother()

    # 1. 초기 2-1 감지
    s1 = smoother.smooth_stage_round("2-1")
    assert s1 == "2-1"

    # 2. 라운드 전환 중 빈값(None 또는 "") -> 2-1 유지
    assert smoother.smooth_stage_round(None) == "2-1"
    assert smoother.smooth_stage_round("") == "2-1"

    # 3. 2-5로 정상 전진
    s2 = smoother.smooth_stage_round("2-5")
    assert s2 == "2-5"

    # 4. 역행 노이즈(2-5 상태에서 2-1 또는 2-2 감지) -> 2-5 유지
    assert smoother.smooth_stage_round("2-1") == "2-5"
    assert smoother.smooth_stage_round("2-2") == "2-5"

    # 5. 3-1로 정상 전진
    s3 = smoother.smooth_stage_round("3-1")
    assert s3 == "3-1"


def test_timeline_smoother_gold():
    """골드 연속성 및 비정상 스파이크 완화 검증."""
    smoother = TimelineSmoother()

    assert smoother.smooth_gold(30) == 30
    assert smoother.smooth_gold(None) == 30  # 일시적 미인식 시 유지
    assert smoother.smooth_gold(25) == 25
    assert smoother.smooth_gold(-5) == 25   # 음수 무시
    assert smoother.smooth_gold(999) == 25  # 비정상 스파이크 무시


def test_timeline_smoother_batch_step():
    """전체 타임라인 배치 스무딩 검증."""
    smoother = TimelineSmoother()
    raw_stream = [
        {"stage_round": "2-1", "gold": 30, "field_units": [{"champion": "나서스"}]},
        {"stage_round": None, "gold": None, "field_units": []}, # 전환 중 빈값
        {"stage_round": "2-1", "gold": 33, "field_units": [{"champion": "나서스"}]},
        {"stage_round": "2-5", "gold": 12, "field_units": [{"champion": "나서스"}]},
        {"stage_round": "2-1", "gold": 12, "field_units": [{"champion": "나서스"}]}, # 역행 노이즈
    ]

    smoothed = smoother.smooth_timeline(raw_stream)
    assert len(smoothed) == 5

    assert smoothed[0]["stage_round"] == "2-1"
    assert smoothed[1]["stage_round"] == "2-1" # 빈값 보정됨
    assert smoothed[1]["gold"] == 30           # 골드 유지됨
    assert len(smoothed[1]["field_units"]) == 1 # 유닛 가림 보정됨

    assert smoothed[3]["stage_round"] == "2-5"
    assert smoothed[4]["stage_round"] == "2-5" # 역행 노이즈 제거됨


def test_board_recognizer_templates_loaded():
    """DDragon 챔피언 및 아이템 템플릿 로딩 검증."""
    recognizer = BoardRecognizer()
    assert len(recognizer.champion_templates) >= 60
    assert "나서스" in recognizer.champion_templates
    assert "진" in recognizer.champion_templates
    assert len(recognizer.item_templates) > 0


def test_match_slot_champion_unknown_for_empty_slot():
    """빈 슬롯/노이즈 이미지에 대해 임의 추측 없이 (None, None) 반환 검증."""
    recognizer = BoardRecognizer()
    black_img = np.zeros((60, 60, 3), dtype=np.uint8)

    champ, cost, conf = recognizer.match_slot_champion(black_img, min_confidence=0.60)
    assert champ is None
    assert cost is None
    assert conf < 0.60


def test_detect_star_level():
    """성급 인식 헬퍼 함수 검증."""
    recognizer = BoardRecognizer()
    empty_roi = np.zeros((20, 40, 3), dtype=np.uint8)
    assert recognizer.detect_star_level(empty_roi) == 1


def test_match_unit_items():
    """아이템 슬롯 인식 헬퍼 함수 검증."""
    recognizer = BoardRecognizer()
    empty_item_bar = np.zeros((15, 45, 3), dtype=np.uint8)
    items = recognizer.match_unit_items(empty_item_bar)
    assert items == []
