"""Comprehensive Unit Tests for TFT Shop Recognition v2 Framework."""
import os
import sys
import numpy as np
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.vision.shop_recognizer_v2 import (
    ShopRecognizerV2,
    RecognizedCard,
    SlotStatus,
    CandidateScore
)
from tft.vision.shop_timeline_v2 import ShopTemporalStabilizer, ShopTimelineV2Builder
from tft.vision.shop_metrics import ShopVersionMetrics, ShopComparisonReport, compare_shop_versions
from tft.vision.timeline import ObservationTimeline
from tft.vision.ground_truth import GroundTruthDataset, GroundTruthObservation, GroundTruthCard


def test_shop_geometry_and_resolution_scaling():
    """Verify relative resolution scaling for 720p and 1080p frames."""
    rec = ShopRecognizerV2()

    # 720p frame
    frame_720p = np.zeros((720, 1280, 3), dtype=np.uint8)
    shop_crop, slots = rec.get_shop_crop_and_slots(frame_720p)
    assert len(slots) == 5
    assert slots[0].shape[0] == 124  # 713 - 589
    assert slots[0].shape[1] == 136

    # 1080p frame (1.5x scale)
    frame_1080p = np.zeros((1080, 1920, 3), dtype=np.uint8)
    shop_crop_1080, slots_1080 = rec.get_shop_crop_and_slots(frame_1080p)
    assert len(slots_1080) == 5
    assert slots_1080[0].shape[0] == int(124 * 1.5)
    assert slots_1080[0].shape[1] == int(136 * 1.5)


def test_slot_status_distinction():
    """Verify distinct SlotStatus enum values and empty checks."""
    card_empty = RecognizedCard(slot_index=0, status=SlotStatus.EMPTY)
    card_rec = RecognizedCard(slot_index=1, champion="미스 포츈", cost=3, status=SlotStatus.RECOGNIZED)
    card_low = RecognizedCard(slot_index=2, status=SlotStatus.LOW_CONFIDENCE)
    card_unk = RecognizedCard(slot_index=3, status=SlotStatus.UNKNOWN)
    card_no = RecognizedCard(slot_index=4, status=SlotStatus.NO_DETECTION)

    assert card_empty.is_empty is True
    assert card_rec.is_empty is False
    assert card_low.is_empty is False
    assert card_unk.is_empty is False
    assert card_no.is_empty is False


def test_cost_color_detection_on_known_bands():
    """Verify cost detection from bottom border HSV color bands."""
    rec = ShopRecognizerV2()

    # 1. Cost 1: Low saturation (Gray)
    crop_1c = np.zeros((124, 136, 3), dtype=np.uint8)
    crop_1c[100:120, :] = (120, 120, 120)  # Low saturation
    assert rec.detect_cost_color(crop_1c) == 1

    # 2. Cost 3: Blue band
    crop_3c = np.zeros((124, 136, 3), dtype=np.uint8)
    crop_3c[100:120, :] = (200, 100, 20)  # BGR Blue
    assert rec.detect_cost_color(crop_3c) == 3

    # 3. Cost 4: Purple band
    crop_4c = np.zeros((124, 136, 3), dtype=np.uint8)
    crop_4c[100:120, :] = (180, 20, 180)  # BGR Purple
    assert rec.detect_cost_color(crop_4c) == 4


def test_candidate_fusion_determinism():
    """Verify candidate fusion formula: 60% portrait + 40% OCR text."""
    c1 = CandidateScore(champion="미스 포츈", cost=3, template_score=0.80, ocr_score=0.90, combined_score=0.6*0.80 + 0.4*0.90)
    c2 = CandidateScore(champion="일라오이", cost=3, template_score=0.50, ocr_score=0.10, combined_score=0.6*0.50 + 0.4*0.10)

    assert round(c1.combined_score, 3) == 0.840
    assert round(c2.combined_score, 3) == 0.340
    assert c1.combined_score > c2.combined_score


def test_causal_temporal_stabilization():
    """Verify forward-only temporal debouncing without hindsight."""
    stabilizer = ShopTemporalStabilizer()

    # Frame 1: Stable recognized shop
    f1 = [
        RecognizedCard(slot_index=0, champion="밀리오", cost=2, status=SlotStatus.RECOGNIZED, confidence=0.85),
        RecognizedCard(slot_index=1, champion="우르곳", cost=3, status=SlotStatus.RECOGNIZED, confidence=0.82),
        RecognizedCard(slot_index=2, champion="카이사", cost=3, status=SlotStatus.RECOGNIZED, confidence=0.88),
        RecognizedCard(slot_index=3, champion="나서스", cost=1, status=SlotStatus.RECOGNIZED, confidence=0.90),
        RecognizedCard(slot_index=4, champion="다리우스", cost=1, status=SlotStatus.RECOGNIZED, confidence=0.87),
    ]
    out1 = stabilizer.stabilize(f1, timestamp_sec=10.0)
    assert [c.champion for c in out1] == ["밀리오", "우르곳", "카이사", "나서스", "다리우스"]

    # Frame 2: Slot 2 suffers momentary LOW_CONFIDENCE flicker during static shop
    f2 = [
        RecognizedCard(slot_index=0, champion="밀리오", cost=2, status=SlotStatus.RECOGNIZED, confidence=0.85),
        RecognizedCard(slot_index=1, champion="우르곳", cost=3, status=SlotStatus.RECOGNIZED, confidence=0.82),
        RecognizedCard(slot_index=2, champion=None, cost=None, status=SlotStatus.LOW_CONFIDENCE, confidence=0.10),
        RecognizedCard(slot_index=3, champion="나서스", cost=1, status=SlotStatus.RECOGNIZED, confidence=0.90),
        RecognizedCard(slot_index=4, champion="다리우스", cost=1, status=SlotStatus.RECOGNIZED, confidence=0.87),
    ]
    out2 = stabilizer.stabilize(f2, timestamp_sec=10.5)
    # Forward stabilization should preserve "카이사"
    assert out2[2].champion == "카이사"
    assert out2[2].status == SlotStatus.RECOGNIZED

    # Frame 3: Valid REROLL transition (all 5 slots change)
    f3 = [
        RecognizedCard(slot_index=0, champion="소나", cost=1, status=SlotStatus.RECOGNIZED, confidence=0.85),
        RecognizedCard(slot_index=1, champion="쉔", cost=3, status=SlotStatus.RECOGNIZED, confidence=0.82),
        RecognizedCard(slot_index=2, champion="제드", cost=2, status=SlotStatus.RECOGNIZED, confidence=0.88),
        RecognizedCard(slot_index=3, champion="조이", cost=2, status=SlotStatus.RECOGNIZED, confidence=0.90),
        RecognizedCard(slot_index=4, champion="밀리오", cost=2, status=SlotStatus.RECOGNIZED, confidence=0.87),
    ]
    out3 = stabilizer.stabilize(f3, timestamp_sec=12.0)
    assert [c.champion for c in out3] == ["소나", "쉔", "제드", "조이", "밀리오"]


def test_shop_metrics_delta_computation():
    """Verify delta computation between old and new metrics."""
    old_m = ShopVersionMetrics(version_name="OLD", total_slots=100, champion_correct_slots=4)  # 4%
    new_m = ShopVersionMetrics(version_name="NEW", total_slots=100, champion_correct_slots=92) # 92%

    report = ShopComparisonReport(
        old_metrics=old_m,
        new_metrics=new_m,
        overall_accuracy_delta=round(new_m.overall_champion_accuracy - old_m.overall_champion_accuracy, 4)
    )

    assert report.old_metrics.overall_champion_accuracy == 0.04
    assert report.new_metrics.overall_champion_accuracy == 0.92
    assert report.overall_accuracy_delta == +0.8800  # +88.0 pp gain
