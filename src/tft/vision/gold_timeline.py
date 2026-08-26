"""TFT Gold Timeline Engine: Forward-only Online Causal Stabilization and GoldDeltaEvent extraction."""
from dataclasses import dataclass, field
from enum import Enum
import math
import os
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from tft.vision.gold_recognizer import GoldRecognizer, GoldObservation, GoldErrorType


class GoldDeltaType(str, Enum):
    """골드 변동 이벤트 유형."""
    GOLD_UNCHANGED = "GOLD_UNCHANGED"
    GOLD_DECREASE = "GOLD_DECREASE"
    GOLD_INCREASE = "GOLD_INCREASE"
    GOLD_UNKNOWN = "GOLD_UNKNOWN"


@dataclass(frozen=True)
class GoldDeltaEvent:
    """시간축 상의 유의미한 골드 변동 사건."""
    timestamp_sec: float
    before_gold: int
    after_gold: int
    delta: int
    event_type: GoldDeltaType
    is_roll_delta: bool = False      # ΔG == -2
    is_buy_delta: bool = False       # ΔG in [-1, -2, -3, -4, -5]
    is_levelup_delta: bool = False   # ΔG in [-4, -8, -12, -16]
    is_round_income: bool = False    # ΔG > 0
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_sec": round(self.timestamp_sec, 3),
            "before_gold": self.before_gold,
            "after_gold": self.after_gold,
            "delta": self.delta,
            "event_type": self.event_type.value,
            "is_roll_delta": self.is_roll_delta,
            "is_buy_delta": self.is_buy_delta,
            "is_levelup_delta": self.is_levelup_delta,
            "is_round_income": self.is_round_income,
            "confidence": round(self.confidence, 3)
        }


class GoldTimelineProcessor:
    """순방향 인과성(Online Causality)을 준수하는 골드 타임라인 프로세서."""

    def __init__(self, recognizer: Optional[GoldRecognizer] = None):
        self.recognizer = recognizer or GoldRecognizer()

    def stabilize_online(
        self,
        raw_observations: List[GoldObservation]
    ) -> List[GoldObservation]:
        """미래 프레임 참조 없이 순방향으로만 노이즈를 완화하고 결측을 보정하는 Causal Stabilizer."""
        stabilized: List[GoldObservation] = []
        if not raw_observations:
            return stabilized

        last_valid_gold = raw_observations[0].parsed_gold if raw_observations[0].is_valid else 35

        for obs in raw_observations:
            if obs.is_valid and obs.parsed_gold is not None:
                # Spike filter: sudden massive jump > 60G in single 0.5s frame without income
                g_diff = abs(obs.parsed_gold - last_valid_gold)
                if g_diff <= 60 or last_valid_gold is None:
                    current_gold = obs.parsed_gold
                    last_valid_gold = current_gold
                else:
                    # Treat as outlier, carry forward
                    current_gold = last_valid_gold
            else:
                # Carry forward on temporary OCR missing frame
                current_gold = last_valid_gold

            stab_obs = GoldObservation(
                timestamp_sec=obs.timestamp_sec,
                frame_index=obs.frame_index,
                raw_text=obs.raw_text,
                parsed_gold=current_gold,
                confidence=obs.confidence if obs.is_valid else 0.70,
                source=obs.source,
                is_valid=True,
                error_type=obs.error_type,
                metadata={"carried_forward": not obs.is_valid}
            )
            stabilized.append(stab_obs)

        return stabilized

    def extract_delta_events(
        self,
        stabilized_timeline: List[GoldObservation]
    ) -> List[GoldDeltaEvent]:
        """안정화된 골드 시계열로부터 GoldDeltaEvent 목록 추출."""
        events: List[GoldDeltaEvent] = []
        if len(stabilized_timeline) < 2:
            return events

        for i in range(1, len(stabilized_timeline)):
            obs_before = stabilized_timeline[i - 1]
            obs_after = stabilized_timeline[i]

            g_before = obs_before.parsed_gold
            g_after = obs_after.parsed_gold

            if g_before is None or g_after is None:
                continue

            delta = g_after - g_before
            t_sec = obs_after.timestamp_sec

            if delta == 0:
                continue

            ev_type = GoldDeltaType.GOLD_DECREASE if delta < 0 else GoldDeltaType.GOLD_INCREASE
            is_roll = (delta == -2)
            is_buy = delta in [-1, -2, -3, -4, -5]
            is_lvl = (delta <= -4 and delta % 4 == 0)
            is_income = (delta > 0)

            ev = GoldDeltaEvent(
                timestamp_sec=t_sec,
                before_gold=g_before,
                after_gold=g_after,
                delta=delta,
                event_type=ev_type,
                is_roll_delta=is_roll,
                is_buy_delta=is_buy,
                is_levelup_delta=is_lvl,
                is_round_income=is_income,
                confidence=min(obs_before.confidence, obs_after.confidence)
            )
            events.append(ev)

        return events

    def process_video(
        self,
        video_path: str,
        start_sec: float = 300.0,
        duration_sec: float = 600.0,
        step_sec: float = 0.5
    ) -> Tuple[List[GoldObservation], List[GoldObservation], List[GoldDeltaEvent]]:
        """원본 비디오 파일로부터 전체 Gold Timeline 추출 및 안정화 수행."""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        end_sec = start_sec + duration_sec

        raw_observations: List[GoldObservation] = []
        curr_t = start_sec

        while curr_t <= end_sec:
            f_idx = int(curr_t * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret:
                break

            obs = self.recognizer.recognize_gold(frame, timestamp_sec=curr_t, frame_index=f_idx)
            raw_observations.append(obs)
            curr_t += step_sec

        cap.release()

        stabilized = self.stabilize_online(raw_observations)
        delta_events = self.extract_delta_events(stabilized)

        return raw_observations, stabilized, delta_events
