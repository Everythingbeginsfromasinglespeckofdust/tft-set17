"""Execution engine for TFT Multi-Session Pilot Pipeline."""
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from tft.vision.gold_recognizer import GoldRecognizer, GoldObservation
from tft.vision.gold_timeline import GoldTimelineProcessor, GoldDeltaEvent
from tft.vision.shop_recognizer_v2 import ShopRecognizerV2
from tft.vision.observation import Observation, CardObservation
from tft.vision.timeline import ObservationTimeline
from tft.vision.events import ActionEvent
from tft.vision.action_event_detector_v22 import ActionEventDetectorV22
from tft.vision.pilot_models import PilotSession, PilotManifest


class MultiSessionPilotRunner:
    """모든 세션에 완전히 동일한 Frozen Vision/Action 파이프라인을 실행하는 배치 엔진."""

    def __init__(
        self,
        gold_processor: Optional[GoldTimelineProcessor] = None,
        shop_recognizer: Optional[ShopRecognizerV2] = None,
        action_detector: Optional[ActionEventDetectorV22] = None
    ):
        self.gold_processor = gold_processor or GoldTimelineProcessor()
        self.shop_recognizer = shop_recognizer or ShopRecognizerV2()
        self.action_detector = action_detector or ActionEventDetectorV22()

    def run_session(
        self,
        session: PilotSession,
        output_base_dir: str,
        start_sec: float = 300.0,
        duration_sec: float = 600.0,
        step_sec: float = 0.5
    ) -> Dict[str, Any]:
        """단일 세션에 대해 독립적으로 전체 파이프라인 실행 및 산출물 저장."""
        t_start = time.time()
        session_out_dir = os.path.join(output_base_dir, "sessions", session.session_id)
        os.makedirs(session_out_dir, exist_ok=True)

        print(f"\n[{session.session_id}] Processing video: {session.video_path}")
        print(f"[{session.session_id}] Window: [{start_sec:.1f}s -> {start_sec + duration_sec:.1f}s] @ {step_sec}s step")

        if not os.path.exists(session.video_path):
            raise FileNotFoundError(f"Video file not found for session {session.session_id}: {session.video_path}")

        cap = cv2.VideoCapture(session.video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        end_sec = min(start_sec + duration_sec, total_frames / max(1.0, fps))

        # 1. Sequential Frame Processing (Gold + Shop)
        raw_gold_obs: List[GoldObservation] = []
        shop_cards_timeline: List[List[CardObservation]] = []
        timestamps: List[float] = []

        curr_t = start_sec
        f_count = 0
        while curr_t <= end_sec:
            f_idx = int(curr_t * fps)
            if f_idx >= total_frames:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret:
                break

            # Gold Recognition
            g_obs = self.gold_processor.recognizer.recognize_gold(frame, timestamp_sec=curr_t, frame_index=f_idx)
            raw_gold_obs.append(g_obs)

            # Shop Recognition
            cards_raw = self.shop_recognizer.recognize_shop(frame, min_confidence=0.30)
            cards: List[CardObservation] = []
            for c in cards_raw:
                cards.append(CardObservation(
                    slot_index=c.get("slot", 1) - 1,
                    champion_pred=c.get("champion"),
                    cost_pred=c.get("cost"),
                    confidence=c.get("confidence", 0.0),
                    is_empty=c.get("is_empty", False),
                    source="ShopRecognizerV2"
                ))
            shop_cards_timeline.append(cards)
            timestamps.append(curr_t)

            f_count += 1
            curr_t += step_sec

        cap.release()

        # 2. Causal Online Stabilization
        stabilized_gold = self.gold_processor.stabilize_online(raw_gold_obs)
        gold_deltas = self.gold_processor.extract_delta_events(stabilized_gold)

        # 3. Build Merged Observation Timeline
        timeline = ObservationTimeline(
            video_path=session.video_path,
            duration_sec=duration_sec,
            fps=fps
        )

        for idx in range(len(timestamps)):
            t_sec = timestamps[idx]
            g_val = stabilized_gold[idx].parsed_gold if idx < len(stabilized_gold) else 35
            cards = shop_cards_timeline[idx] if idx < len(shop_cards_timeline) else []

            obs = Observation(
                timestamp_sec=t_sec,
                frame_index=idx,
                stage_text="3-2",
                gold_val=g_val,
                hp_val=60,
                level_val=7,
                shop_cards=cards,
                sources={"shop": "ShopRecognizerV2", "gold": "GoldRecognizer"},
                confidences={"shop": 0.95, "gold": stabilized_gold[idx].confidence if idx < len(stabilized_gold) else 0.85},
                overall_confidence=0.90
            )
            timeline.add_observation(obs)

        # 4. Run Frozen ActionEventDetectorV22
        events = self.action_detector.detect_actions(timeline)

        elapsed = time.time() - t_start
        eff_fps = f_count / max(0.001, elapsed)

        # 5. Persist Session Artifacts
        gold_path = os.path.join(session_out_dir, "gold.jsonl")
        deltas_path = os.path.join(session_out_dir, "gold_deltas.jsonl")
        timeline_path = os.path.join(session_out_dir, "timeline.json")
        preds_path = os.path.join(session_out_dir, "predictions.jsonl")
        summary_path = os.path.join(session_out_dir, "detection_summary.json")

        with open(gold_path, "w", encoding="utf-8") as f:
            for g in stabilized_gold:
                f.write(json.dumps(g.to_dict(), ensure_ascii=False) + "\n")

        with open(deltas_path, "w", encoding="utf-8") as f:
            for d in gold_deltas:
                f.write(json.dumps(d.to_dict(), ensure_ascii=False) + "\n")

        with open(timeline_path, "w", encoding="utf-8") as f:
            timeline_dict = {
                "metadata": {
                    "session_id": session.session_id,
                    "total_observations": len(timeline.observations),
                    "processing_time_sec": round(elapsed, 2),
                    "effective_fps": round(eff_fps, 2)
                },
                "observations": [
                    {
                        "timestamp_sec": round(o.timestamp_sec, 3),
                        "gold": o.gold_val,
                        "hp": o.hp_val,
                        "level": o.level_val,
                        "stage_round": o.stage_text,
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
                    }
                    for o in timeline.observations
                ]
            }
            json.dump(timeline_dict, f, indent=2, ensure_ascii=False)

        with open(preds_path, "w", encoding="utf-8") as f:
            for ev in events:
                f.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")

        det_summary = {
            "session_id": session.session_id,
            "total_frames_sampled": f_count,
            "processing_time_sec": round(elapsed, 2),
            "effective_fps": round(eff_fps, 2),
            "total_detected_events": len(events),
            "roll_events": sum(1 for e in events if e.event_type.value == "ROLL"),
            "buy_events": sum(1 for e in events if e.event_type.value == "BUY_UNIT"),
            "system_refresh_events": sum(1 for e in events if e.event_type.value == "SYSTEM_REFRESH"),
            "gold_deltas": len(gold_deltas)
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(det_summary, f, indent=2, ensure_ascii=False)

        print(f"[{session.session_id}] Done: {len(events)} events detected ({det_summary['roll_events']} ROLL, {det_summary['buy_events']} BUY) in {elapsed:.1f}s ({eff_fps:.1f} FPS)")
        return det_summary

    def run_all(
        self,
        manifest: PilotManifest,
        output_base_dir: str
    ) -> Dict[str, Dict[str, Any]]:
        """Manifest에 등록된 모든 세션 순차 실행."""
        results = {}
        for session in manifest.sessions:
            summary = self.run_session(session, output_base_dir)
            results[session.session_id] = summary
        return results
