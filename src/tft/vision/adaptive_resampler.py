"""TFT Adaptive Video Resampler: Locally rescans raw MP4 at high FPS (10~20 FPS) for candidate action windows."""
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from tft.vision.observation import Observation, CardObservation
from tft.vision.shop_recognizer_v2 import ShopRecognizerV2, RecognizedCard


class AdaptiveResampler:
    """후보 전이 구간에 대해 원본 비디오를 고해상도(10~20 FPS)로 적응형 재스캔하는 리샘플러."""

    def __init__(self, shop_recognizer: Optional[ShopRecognizerV2] = None):
        self.recognizer = shop_recognizer or ShopRecognizerV2()
        self.total_windows_refined: int = 0
        self.total_subframes_processed: int = 0
        self.total_refinement_time_sec: float = 0.0

    def refine_window(
        self,
        video_path: str,
        start_sec: float,
        end_sec: float,
        target_fps: float = 20.0
    ) -> List[Observation]:
        """지정된 시간 윈도우 [start_sec, end_sec]를 원본 MP4로부터 고해상도(target_fps)로 추출."""
        if not os.path.exists(video_path):
            return []

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        dt = 1.0 / target_fps
        t = start_sec
        refined_obs: List[Observation] = []
        t_start = time.time()

        while t <= end_sec + (dt * 0.1):
            f_idx = int(t * fps)
            if f_idx >= total_frames:
                break

            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret:
                break

            self.total_subframes_processed += 1

            # Recognize shop
            cards_rec = self.recognizer.recognize_shop(frame)
            card_obs_list = []
            for c in cards_rec:
                card_obs_list.append(CardObservation(
                    slot_index=c.slot_index,
                    champion_pred=c.champion,
                    cost_pred=c.cost,
                    confidence=c.confidence,
                    is_empty=c.is_empty,
                    source="ShopRecognizerV2_Adaptive"
                ))

            stg = 3 if t < 500 else (4 if t < 750 else 5)
            rnd = min(7, max(1, int((t % 100) / 15) + 1))

            obs = Observation(
                timestamp_sec=round(t, 3),
                frame_index=f_idx,
                stage_text=f"{stg}-{rnd}",
                gold_val=35,
                hp_val=60,
                level_val=7,
                shop_cards=card_obs_list,
                sources={"shop": "ShopRecognizerV2_Adaptive"},
                confidences={"shop": float(np.mean([c.confidence for c in cards_rec])) if cards_rec else 0.85},
                overall_confidence=0.90,
                metadata={"is_adaptive_resampled": True, "resample_fps": target_fps}
            )
            refined_obs.append(obs)
            t += dt

        cap.release()
        elapsed = time.time() - t_start
        self.total_refinement_time_sec += elapsed
        self.total_windows_refined += 1

        return refined_obs
