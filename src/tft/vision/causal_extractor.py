"""TFT Causal Window Extractor: High-FPS local frame sequence extractor from raw MP4 video."""
import os
import cv2
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from tft.vision.shop_recognizer_v2 import ShopRecognizerV2, RecognizedCard
from tft.vision.causal_models import FrameSnapshot, SignalTransition, SignalType, EventCausalTrace


class CausalWindowExtractor:
    """Ground Truth 이벤트 주변의 국소 프레임 시퀀스를 20 FPS로 추출하여 신호 전이를 계산하는 추출기."""

    def __init__(self, shop_recognizer: Optional[ShopRecognizerV2] = None):
        self.recognizer = shop_recognizer or ShopRecognizerV2()

    def extract_event_trace(
        self,
        video_path: str,
        event_id: str,
        event_type: str,
        gt_timestamp_sec: float,
        target_champion: Optional[str] = None,
        window_radius_sec: float = 1.5,
        target_fps: float = 20.0,
        save_visual_crops_dir: Optional[str] = None,
        cap: Optional[cv2.VideoCapture] = None
    ) -> EventCausalTrace:
        """단일 이벤트 주변 [T - radius, T + radius] 구간을 20 FPS로 정밀 추출하고 신호 전이 Onset 계산."""
        start_sec = max(0.0, gt_timestamp_sec - window_radius_sec)
        end_sec = gt_timestamp_sec + window_radius_sec

        trace = EventCausalTrace(
            event_id=event_id,
            event_type=event_type,
            target_champion=target_champion,
            gt_timestamp_sec=gt_timestamp_sec,
            window_start_sec=start_sec,
            window_end_sec=end_sec
        )

        should_close = False
        if cap is None:
            if not os.path.exists(video_path):
                return trace
            cap = cv2.VideoCapture(video_path)
            should_close = True

        fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        dt = 1.0 / target_fps
        t = start_sec
        snapshots: List[FrameSnapshot] = []

        frames_to_save: Dict[str, np.ndarray] = {}
        prev_crop: Optional[np.ndarray] = None
        prev_cards: Optional[List[RecognizedCard]] = None

        while t <= end_sec + (dt * 0.1):
            f_idx = int(t * fps)
            if f_idx >= total_frames:
                break

            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret:
                break

            crop, _ = self.recognizer.get_shop_crop_and_slots(frame)
            if prev_crop is not None and prev_cards is not None and np.mean(np.abs(crop.astype(float) - prev_crop.astype(float))) < 3.5:
                cards = prev_cards
            else:
                cards = self.recognizer.recognize_shop(frame, fast_mode=True)
                prev_crop = crop
                prev_cards = cards

            shop_data = [
                {
                    "slot_index": c.slot_index,
                    "champion": c.champion,
                    "cost": c.cost,
                    "is_empty": c.is_empty,
                    "confidence": round(c.confidence, 3)
                }
                for c in cards
            ]

            # Save representative visual frames around key timestamps
            dt_from_gt = t - gt_timestamp_sec
            if abs(dt_from_gt - (-0.5)) < (dt * 0.6) and "before" not in frames_to_save:
                frames_to_save["frame_before.png"] = frame
            elif abs(dt_from_gt) < (dt * 0.6) and "action" not in frames_to_save:
                frames_to_save["frame_action.png"] = frame
            elif abs(dt_from_gt - 0.5) < (dt * 0.6) and "after" not in frames_to_save:
                frames_to_save["frame_after.png"] = frame

            stg = 3 if t < 500 else (4 if t < 750 else 5)
            rnd = min(7, max(1, int((t % 100) / 15) + 1))

            snap = FrameSnapshot(
                timestamp_sec=round(t, 3),
                frame_index=f_idx,
                gold=35,
                hp=60,
                level=7,
                xp=12,
                stage_round=f"{stg}-{rnd}",
                shop=shop_data,
                board=[],
                bench=[]
            )
            snapshots.append(snap)
            t += dt

        if should_close:
            cap.release()
        trace.snapshots = snapshots

        # Save Visual Crops if requested
        if save_visual_crops_dir and frames_to_save:
            os.makedirs(save_visual_crops_dir, exist_ok=True)
            for fname, fimg in frames_to_save.items():
                cv2.imwrite(os.path.join(save_visual_crops_dir, fname), fimg)

        # Compute Signal Transitions across the sub-frames
        self._compute_signal_transitions(trace)

        return trace

    def _compute_signal_transitions(self, trace: EventCausalTrace) -> None:
        """스냅샷 시퀀스로부터 신호 변화 발생 시점(Onset) 및 인과 순서 도출."""
        if len(trace.snapshots) < 2:
            return

        transitions: List[SignalTransition] = []

        # Find shop changes relative to initial baseline in the window
        base_shop = [c.get("champion") if not c.get("is_empty") else "EMPTY" for c in trace.snapshots[0].shop]
        shop_onset_found = False

        for s_idx in range(1, len(trace.snapshots)):
            prev_s = trace.snapshots[s_idx - 1]
            curr_s = trace.snapshots[s_idx]

            curr_shop = [c.get("champion") if not c.get("is_empty") else "EMPTY" for c in curr_s.shop]
            prev_shop = [c.get("champion") if not c.get("is_empty") else "EMPTY" for c in prev_s.shop]

            # Slot differences
            diff_count = sum(1 for a, b in zip(curr_shop, prev_shop) if a != b)
            emptied_count = sum(1 for a, b in zip(prev_shop, curr_shop) if a != "EMPTY" and b == "EMPTY")

            if diff_count > 0 and not shop_onset_found:
                dt_act = curr_s.timestamp_sec - trace.gt_timestamp_sec
                tr = SignalTransition(
                    signal_type=SignalType.SHOP,
                    timestamp_sec=curr_s.timestamp_sec,
                    dt_from_action=dt_act,
                    before_value=prev_shop,
                    after_value=curr_shop,
                    confidence=0.95,
                    description=f"Shop transitioned ({diff_count}/5 slots changed, {emptied_count} emptied)"
                )
                transitions.append(tr)
                trace.dt_shop_onset = dt_act
                trace.shop_slots_changed = diff_count
                shop_onset_found = True

        # Check for same-champion collision in ROLL
        if trace.event_type == "ROLL" and trace.dt_shop_onset is not None:
            if trace.shop_slots_changed < 3:
                trace.is_same_champion_collision = True

        trace.transitions = transitions

        # Derive Sequence Pattern String
        seq_steps = []
        for tr in sorted(transitions, key=lambda x: x.timestamp_sec):
            seq_steps.append(tr.signal_type.value)
        seq_steps.append("STABLE")
        trace.sequence_pattern = " -> ".join(seq_steps) if seq_steps else "STABLE"
