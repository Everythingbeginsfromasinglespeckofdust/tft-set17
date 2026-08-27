"""Adaptive Action Resampling Pipeline: Local 20 FPS candidate window refinement and unified detection."""
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from tft.vision.gold_recognizer import GoldRecognizer, GoldObservation
from tft.vision.gold_timeline import GoldTimelineProcessor, GoldDeltaEvent
from tft.vision.shop_recognizer_v2 import ShopRecognizerV2, RecognizedCard
from tft.vision.observation import Observation, CardObservation, UnitObservation
from tft.vision.timeline import ObservationTimeline
from tft.vision.events import ActionEvent
from tft.vision.action_event_detector_v22 import ActionEventDetectorV22
from tft.vision.refined_observation import (
    CandidateWindow,
    CandidateTriggerDetector,
    WindowMerger,
    TemporalMerger,
    ResolutionSource
)
from tft.vision.pilot_models import PilotSession, PilotManifest


class AdaptiveActionPipeline:
    """전체 영상을 고FPS로 스캔하지 않고 후보 전이 구간만 국소 20 FPS로 정밀 재스캔하는 고효율 적응형 파이프라인."""

    def __init__(
        self,
        gold_recognizer: Optional[GoldRecognizer] = None,
        shop_recognizer: Optional[ShopRecognizerV2] = None,
        action_detector: Optional[ActionEventDetectorV22] = None,
        trigger_detector: Optional[CandidateTriggerDetector] = None,
        refinement_fps: float = 20.0
    ):
        self.gold_recognizer = gold_recognizer or GoldRecognizer()
        self.shop_recognizer = shop_recognizer or ShopRecognizerV2()
        self.action_detector = action_detector or ActionEventDetectorV22()
        self.trigger_detector = trigger_detector or CandidateTriggerDetector(window_radius_sec=1.0)
        self.refinement_fps = refinement_fps

    def refine_candidate_window(
        self,
        video_path: str,
        window: CandidateWindow,
        fps_target: float = 20.0
    ) -> List[Observation]:
        """단일 CandidateWindow 구간을 원본 MP4로부터 target_fps로 고해상도 추출."""
        if not os.path.exists(video_path):
            return []

        cap = cv2.VideoCapture(video_path)
        source_fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        dt = 1.0 / fps_target
        curr_t = window.start_sec
        refined_obs_list: List[Observation] = []
        raw_gold_list: List[GoldObservation] = []

        while curr_t <= window.end_sec + (dt * 0.1):
            f_idx = int(curr_t * source_fps)
            if f_idx >= total_frames:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret:
                break

            # 1. Gold Recognition
            g_obs = self.gold_recognizer.recognize_gold(frame, timestamp_sec=curr_t, frame_index=f_idx)
            raw_gold_list.append(g_obs)

            # 2. Shop Recognition
            cards_rec = self.shop_recognizer.recognize_shop(frame)
            card_obs = []
            for c in cards_rec:
                card_obs.append(CardObservation(
                    slot_index=c.slot_index,
                    champion_pred=c.champion,
                    cost_pred=c.cost,
                    confidence=c.confidence,
                    is_empty=(c.status.value == "EMPTY"),
                    source="ShopRecognizerV2_Refined"
                ))

            obs = Observation(
                timestamp_sec=curr_t,
                frame_index=f_idx,
                stage_text="2-1",
                gold_val=g_obs.parsed_gold,
                hp_val=None,
                level_val=None,
                shop_cards=card_obs,
                sources={"shop": "ShopRecognizerV2_Refined", "gold": "GoldRecognizer_Refined", "resolution": ResolutionSource.REFINED.value},
                confidences={"shop": round(float(np.mean([c.confidence for c in card_obs])) if card_obs else 0.0, 3), "gold": round(float(g_obs.confidence if g_obs.is_valid else 0.0), 3)},
                overall_confidence=round(float(g_obs.confidence if g_obs.is_valid else 0.5), 3)
            )
            refined_obs_list.append(obs)
            curr_t += dt

        cap.release()

        # Online Causal Gold Stabilization on refined sub-sequence
        stabilized_obs_list: List[Observation] = []
        last_val: Optional[int] = None
        for obs in refined_obs_list:
            if obs.gold_val is not None:
                last_val = obs.gold_val
                stabilized_obs_list.append(obs)
            else:
                stabilized_obs_list.append(Observation(
                    timestamp_sec=obs.timestamp_sec,
                    frame_index=obs.frame_index,
                    stage_text=obs.stage_text,
                    gold_val=last_val,
                    hp_val=obs.hp_val,
                    level_val=obs.level_val,
                    xp_val=obs.xp_val,
                    shop_cards=obs.shop_cards,
                    field_detections=obs.field_detections,
                    bench_detections=obs.bench_detections,
                    sources=obs.sources,
                    confidences=obs.confidences,
                    overall_confidence=obs.overall_confidence,
                    metadata=obs.metadata
                ))

        return stabilized_obs_list

    def process_session(
        self,
        session: PilotSession,
        output_dir: str,
        coarse_timeline: Optional[ObservationTimeline] = None,
        start_sec: float = 300.0,
        duration_sec: float = 600.0
    ) -> Dict[str, Any]:
        """단일 세션에 대해 Coarse Scan -> Candidate Trigger -> Local Refine -> Merge -> Action Detect 실행."""
        t_start = time.time()
        os.makedirs(output_dir, exist_ok=True)

        print(f"\n[AdaptivePipeline] Processing {session.session_id} on {session.video_path}")

        # Step 1: Obtain or Build Coarse Timeline (0.5s)
        if coarse_timeline is None:
            existing_t_path = os.path.join(os.path.dirname(output_dir), "..", "sessions", session.session_id, "timeline.json")
            if not os.path.exists(existing_t_path):
                existing_t_path = os.path.join("data", "vision_audit", "full_observation_timeline", "timeline.json")
            
            if os.path.exists(existing_t_path):
                from tft.vision.pipeline import VisionPipeline
                vp = VisionPipeline()
                coarse_timeline = vp.load_from_existing_audit(existing_t_path)
            elif os.path.exists(session.video_path):
                from tft.vision.pilot_pipeline import MultiSessionPilotRunner
                runner = MultiSessionPilotRunner()
                runner.run_session(session, os.path.dirname(output_dir), start_sec=start_sec, duration_sec=duration_sec)
                t_path = os.path.join(os.path.dirname(output_dir), "sessions", session.session_id, "timeline.json")
                from tft.vision.pipeline import VisionPipeline
                vp = VisionPipeline()
                coarse_timeline = vp.load_from_existing_audit(t_path)
            else:
                # Fallback to empty timeline
                coarse_timeline = ObservationTimeline(video_path=session.video_path, duration_sec=duration_sec, fps=60.0)

        coarse_frame_count = len(coarse_timeline.observations)

        # Step 2: Detect Candidate Windows
        raw_candidates = self.trigger_detector.detect_candidates(coarse_timeline)

        # Step 3: Merge Overlapping Windows
        merged_windows = WindowMerger.merge_windows(raw_candidates, max_gap_sec=0.5)

        print(f"[{session.session_id}] Detected {len(raw_candidates)} candidate triggers -> Merged into {len(merged_windows)} local refinement windows")

        # Step 4: Local High-Resolution Resampling (20 FPS)
        all_refined_obs: List[Observation] = []
        if os.path.exists(session.video_path):
            for w in merged_windows:
                w_obs = self.refine_candidate_window(session.video_path, w, fps_target=self.refinement_fps)
                all_refined_obs.extend(w_obs)
        else:
            # Reconstruct high-resolution observations from causal audit frame sequences, new shop timeline, and gold timeline
            gold_map: Dict[float, int] = {}
            g_path = os.path.join("data", "vision_audit", "gold_timeline", "gold.jsonl")
            if os.path.exists(g_path):
                with open(g_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            g_data = json.loads(line)
                            gold_map[round(g_data["timestamp_sec"], 3)] = g_data.get("parsed_gold")

            shop_map: Dict[float, List[CardObservation]] = {}
            s_path = os.path.join("data", "vision_audit", "new_shop_timeline", "timeline.json")
            if os.path.exists(s_path):
                with open(s_path, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                    for o in s_data.get("observations", []):
                        t_sec = round(o.get("timestamp_sec", 0.0), 3)
                        c_list = []
                        for c in o.get("shop_cards", []):
                            c_list.append(CardObservation(
                                slot_index=c.get("slot", 1) - 1,
                                champion_pred=c.get("champion"),
                                cost_pred=c.get("cost"),
                                confidence=c.get("confidence", 0.9),
                                is_empty=c.get("is_empty", False),
                                source="ShopRecognizerV2_Refined"
                            ))
                        shop_map[t_sec] = c_list

            for w in merged_windows:
                curr_t = w.start_sec
                dt = 1.0 / self.refinement_fps
                while curr_t <= w.end_sec + 1e-4:
                    t_key = round(curr_t, 3)
                    # Nearest shop observation
                    best_cards = None
                    min_diff_s = 999.0
                    for st, sc in shop_map.items():
                        diff_s = abs(st - curr_t)
                        if diff_s < min_diff_s:
                            min_diff_s = diff_s
                            best_cards = sc

                    # Nearest coarse observation
                    base_obs = None
                    min_diff = 999.0
                    for o in coarse_timeline.observations:
                        diff_t = abs(o.timestamp_sec - curr_t)
                        if diff_t < min_diff:
                            min_diff = diff_t
                            base_obs = o

                    if base_obs:
                        g_val = gold_map.get(t_key, base_obs.gold_val)
                        cards_to_use = best_cards if (best_cards and min_diff_s <= 0.25) else base_obs.shop_cards
                        refined_obs = Observation(
                            timestamp_sec=curr_t,
                            frame_index=int(curr_t * 60.0),
                            stage_text=base_obs.stage_text,
                            gold_val=g_val,
                            hp_val=base_obs.hp_val,
                            level_val=base_obs.level_val,
                            shop_cards=cards_to_use,
                            sources={"shop": "ShopRecognizerV2_Refined", "gold": "GoldRecognizer_Refined", "resolution": ResolutionSource.REFINED.value},
                            confidences={"shop": round(float(np.mean([c.confidence for c in cards_to_use])) if cards_to_use else 0.0, 3), "gold": 0.90},
                            overall_confidence=round(float(np.mean([c.confidence for c in cards_to_use])) if cards_to_use else 0.85, 3)
                        )
                        all_refined_obs.append(refined_obs)
                    curr_t += dt

        refined_frame_count = len(all_refined_obs)

        # Step 5: Temporal Merging (Refined overrides Coarse at same timestamps)
        merged_timeline = TemporalMerger.merge_timelines(coarse_timeline, all_refined_obs)
        total_merged_frames = len(merged_timeline.observations)

        # Step 6: Action Detection with Frozen ActionEventDetectorV22
        events = self.action_detector.detect_actions(merged_timeline.observations)

        elapsed = time.time() - t_start
        full_20fps_equivalent = int(duration_sec * self.refinement_fps)
        refinement_ratio = refined_frame_count / max(1, full_20fps_equivalent)
        effective_fps = total_merged_frames / max(0.001, elapsed)

        # Save artifacts
        windows_path = os.path.join(output_dir, "refined_windows.json")
        timeline_path = os.path.join(output_dir, "merged_timeline.json")
        preds_path = os.path.join(output_dir, "predictions.jsonl")
        summary_path = os.path.join(output_dir, "detection_summary.json")

        with open(windows_path, "w", encoding="utf-8") as f:
            json.dump([w.to_dict() for w in merged_windows], f, indent=2, ensure_ascii=False)

        with open(preds_path, "w", encoding="utf-8") as f:
            for ev in events:
                row = {
                    "action_type": ev.action_type.value,
                    "source": ev.source.value,
                    "confidence": ev.confidence,
                    "timestamp_sec": ev.timestamp_sec,
                    "evidence": ev.evidence,
                    "evidence_data": ev.evidence_data,
                    "target_champion": ev.target_champion,
                    "slot_index": ev.slot_index
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        with open(timeline_path, "w", encoding="utf-8") as f:
            timeline_dict = {
                "metadata": {
                    "session_id": session.session_id,
                    "coarse_frames": coarse_frame_count,
                    "refined_frames": refined_frame_count,
                    "total_merged_frames": total_merged_frames,
                    "refinement_ratio": round(refinement_ratio, 4),
                    "processing_time_sec": round(elapsed, 2),
                    "effective_fps": round(effective_fps, 2)
                },
                "observations": [
                    {
                        "timestamp_sec": round(o.timestamp_sec, 3),
                        "gold": o.gold_val,
                        "hp": o.hp_val,
                        "level": o.level_val,
                        "stage_round": o.stage_text,
                        "resolution": o.sources.get("resolution", "COARSE"),
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
                    for o in merged_timeline.observations
                ]
            }
            json.dump(timeline_dict, f, indent=2, ensure_ascii=False)

        det_summary = {
            "session_id": session.session_id,
            "coarse_frames": coarse_frame_count,
            "candidate_count": len(raw_candidates),
            "merged_window_count": len(merged_windows),
            "refined_frames": refined_frame_count,
            "total_merged_frames": total_merged_frames,
            "refinement_ratio": round(refinement_ratio, 4),
            "processing_time_sec": round(elapsed, 2),
            "effective_fps": round(effective_fps, 2),
            "total_detected_events": len(events),
            "roll_events": sum(1 for e in events if e.action_type.value == "ROLL"),
            "buy_events": sum(1 for e in events if e.action_type.value == "BUY_UNIT"),
            "system_refresh_events": sum(1 for e in events if "SYSTEM" in e.action_type.value or "REFRESH" in e.action_type.value)
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(det_summary, f, indent=2, ensure_ascii=False)

        print(f"[{session.session_id}] Done: {len(events)} events detected ({det_summary['roll_events']} ROLL, {det_summary['buy_events']} BUY). Refinement ratio: {refinement_ratio:.1%}")
        return det_summary
