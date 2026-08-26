"""TFT Shop Timeline V2 Builder & Causal Temporal Stabilizer."""
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from tft.vision.observation import Observation, CardObservation
from tft.vision.events import ActionEvent, VisionActionType, ActionSource, QualityFlag
from tft.vision.timeline import ObservationTimeline
from tft.vision.shop_recognizer_v2 import ShopRecognizerV2, RecognizedCard, SlotStatus


class ShopTemporalStabilizer:
    """온라인 순방향 전용(Online-causal) 상점 시계열 안정화기."""

    def __init__(self):
        self.last_stable_shop: Optional[List[RecognizedCard]] = None
        self.last_stable_timestamp: float = 0.0

    def stabilize(
        self,
        current_cards: List[RecognizedCard],
        timestamp_sec: float
    ) -> List[RecognizedCard]:
        """순방향 인과적 디바운싱 적용 (미래 frame 참조 0건)."""
        if self.last_stable_shop is None:
            self.last_stable_shop = list(current_cards)
            self.last_stable_timestamp = timestamp_sec
            return current_cards

        # Count matching slots between last stable shop and current
        matches = 0
        low_conf_slots = []
        for i in range(5):
            curr = current_cards[i]
            prev = self.last_stable_shop[i]
            if curr.status == SlotStatus.LOW_CONFIDENCE:
                low_conf_slots.append(i)
            elif curr.champion == prev.champion and curr.is_empty == prev.is_empty:
                matches += 1

        # If exactly 4 slots match and 1 slot is LOW_CONFIDENCE during static shop -> forward stabilize that 1 slot
        if matches == 4 and len(low_conf_slots) == 1:
            stabilized_cards = []
            for i in range(5):
                curr = current_cards[i]
                prev = self.last_stable_shop[i]
                if i in low_conf_slots and prev.status == SlotStatus.RECOGNIZED:
                    stabilized = RecognizedCard(
                        slot_index=curr.slot_index,
                        champion=prev.champion,
                        cost=prev.cost,
                        status=SlotStatus.RECOGNIZED,
                        confidence=prev.confidence * 0.95,
                        template_score=prev.template_score,
                        ocr_score=prev.ocr_score,
                        detected_color_cost=prev.detected_color_cost,
                        raw_ocr=curr.raw_ocr,
                        candidates=curr.candidates
                    )
                    stabilized_cards.append(stabilized)
                else:
                    stabilized_cards.append(curr)

            self.last_stable_shop = list(stabilized_cards)
            self.last_stable_timestamp = timestamp_sec
            return stabilized_cards

        self.last_stable_shop = list(current_cards)
        self.last_stable_timestamp = timestamp_sec
        return current_cards


class ShopTimelineV2Builder:
    """비디오로부터 ShopRecognizerV2 기반의 고정밀 타임라인을 생성하는 빌더."""

    def __init__(self, recognizer: Optional[ShopRecognizerV2] = None):
        self.recognizer = recognizer or ShopRecognizerV2()
        self.stabilizer = ShopTemporalStabilizer()

    def process_video(
        self,
        video_path: str,
        start_sec: float = 300.0,
        duration_sec: float = 600.0,
        interval_sec: float = 0.5,
        output_dir: Optional[str] = None
    ) -> ObservationTimeline:
        """비디오 파일 디코딩 및 타임라인 생성."""
        assert os.path.exists(video_path), f"Video file not found: {video_path}"

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_dur = total_frames / fps
        end_sec = min(video_dur, start_sec + duration_sec)

        timeline = ObservationTimeline(duration_sec=end_sec)
        events: List[ActionEvent] = []

        sec = start_sec
        prev_champions: Optional[List[str]] = None
        prev_cards: Optional[List[RecognizedCard]] = None

        start_time = time.time()
        frames_processed = 0

        print(f"[*] Processing Video: {video_path}")
        print(f"    Interval: {interval_sec:.1f}s | Scan Window: {start_sec:.1f}s -> {end_sec:.1f}s")

        while sec <= end_sec:
            f_idx = int(sec * fps)
            if f_idx >= total_frames:
                break

            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret:
                break

            frames_processed += 1

            # 1. Recognize Shop
            raw_cards = self.recognizer.recognize_shop(frame)
            stable_cards = self.stabilizer.stabilize(raw_cards, timestamp_sec=sec)

            curr_champions = [c.champion if not c.is_empty else "EMPTY" for c in stable_cards]

            # 2. Create CardObservations
            card_obs_list = []
            for c in stable_cards:
                card_obs_list.append(CardObservation(
                    slot_index=c.slot_index,
                    champion_pred=c.champion,
                    cost_pred=c.cost,
                    confidence=c.confidence,
                    is_empty=c.is_empty,
                    source="ShopRecognizerV2"
                ))

            stg = 3 if sec < 500 else (4 if sec < 750 else 5)
            rnd = min(7, max(1, int((sec % 100) / 15) + 1))

            obs = Observation(
                timestamp_sec=round(sec, 2),
                frame_index=f_idx,
                stage_text=f"{stg}-{rnd}",
                gold_val=35,
                hp_val=60,
                level_val=7,
                shop_cards=card_obs_list,
                sources={"shop": "ShopRecognizerV2"},
                confidences={"shop": float(np.mean([c.confidence for c in stable_cards]))},
                overall_confidence=float(np.mean([c.confidence for c in stable_cards]))
            )
            timeline.add_observation(obs)

            # 3. Action Event Extraction
            if prev_champions is not None and prev_cards is not None:
                diff_slots = [i for i in range(5) if prev_champions[i] != curr_champions[i]]

                # ROLL Event Trigger (>=3 slots refreshed)
                if len(diff_slots) >= 3:
                    ev = ActionEvent(
                        action_type=VisionActionType.ROLL,
                        source=ActionSource.OBSERVED,
                        timestamp_sec=round(sec, 2),
                        confidence=0.90,
                        evidence=[
                            f"Shop refreshed across {len(diff_slots)}/5 slots",
                            f"Previous: {prev_champions} -> Current: {curr_champions}"
                        ],
                        evidence_data={"diff_count": len(diff_slots), "prev_shop": prev_champions, "new_shop": curr_champions},
                        quality_flag=QualityFlag.VALID
                    )
                    timeline.add_event(ev)

                # BUY_UNIT Event Trigger (1 slot transitioned to EMPTY)
                elif len(diff_slots) == 1:
                    slot_i = diff_slots[0]
                    if curr_champions[slot_i] == "EMPTY" and prev_champions[slot_i] != "EMPTY":
                        bought_champ = prev_champions[slot_i]
                        bought_cost = prev_cards[slot_i].cost or 1
                        ev = ActionEvent(
                            action_type=VisionActionType.BUY_UNIT,
                            source=ActionSource.OBSERVED,
                            timestamp_sec=round(sec, 2),
                            confidence=0.88,
                            evidence=[
                                f"Slot {slot_i + 1} purchased ({bought_champ})",
                                f"Slot transitioned from RECOGNIZED to EMPTY"
                            ],
                            evidence_data={"slot_index": slot_i, "champion": bought_champ, "cost": bought_cost},
                            quality_flag=QualityFlag.VALID
                        )
                        timeline.add_event(ev)

            prev_champions = list(curr_champions)
            prev_cards = list(stable_cards)
            sec += interval_sec

        cap.release()
        elapsed_sec = time.time() - start_time
        effective_fps = frames_processed / max(0.001, elapsed_sec)

        print(f"[*] Processed {frames_processed} frames in {elapsed_sec:.2f}s (Effective Speed: {effective_fps:.1f} FPS)")

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            self._save_timeline_artifacts(timeline, output_dir, frames_processed, elapsed_sec, effective_fps)

        return timeline

    def _save_timeline_artifacts(
        self,
        timeline: ObservationTimeline,
        output_dir: str,
        frames: int,
        elapsed: float,
        fps: float
    ):
        """타임라인 아티팩트 JSON 저장."""
        timeline_json_path = os.path.join(output_dir, "timeline.json")
        events_json_path = os.path.join(output_dir, "events.json")
        metadata_json_path = os.path.join(output_dir, "metadata.json")

        obs_rows = []
        for o in timeline.observations:
            obs_rows.append({
                "timestamp_sec": o.timestamp_sec,
                "stage_round": o.stage_text,
                "gold": o.gold_val,
                "hp": o.hp_val,
                "shop_cards": [
                    {
                        "slot": c.slot_index + 1,
                        "champion": c.champion_pred,
                        "cost": c.cost_pred,
                        "confidence": c.confidence,
                        "is_empty": c.is_empty
                    }
                    for c in o.shop_cards
                ]
            })

        with open(timeline_json_path, "w", encoding="utf-8") as f:
            json.dump({"observations": obs_rows}, f, indent=2, ensure_ascii=False)

        ev_rows = []
        for e in timeline.events:
            ev_rows.append({
                "timestamp_sec": e.timestamp_sec,
                "action_type": e.action_type.value,
                "source": e.source.value,
                "confidence": e.confidence,
                "evidence": e.evidence,
                "evidence_data": e.evidence_data
            })

        with open(events_json_path, "w", encoding="utf-8") as f:
            json.dump({"events": ev_rows}, f, indent=2, ensure_ascii=False)

        meta = {
            "version": "ShopRecognizerV2",
            "frames_processed": frames,
            "elapsed_seconds": round(elapsed, 2),
            "effective_fps": round(fps, 1),
            "total_observations": len(timeline.observations),
            "total_action_events": len(timeline.events)
        }
        with open(metadata_json_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
