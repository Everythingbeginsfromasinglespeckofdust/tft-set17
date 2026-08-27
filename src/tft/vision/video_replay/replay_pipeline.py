"""Video Replay Pipeline: Runs real Production Vision + Decision + CALIB_C on video frames."""
from __future__ import annotations
import hashlib
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from tft.vision.gold_recognizer import GoldRecognizer
from tft.vision.shop_recognizer_v2 import ShopRecognizerV2, SlotStatus
from tft.vision.observation import Observation, CardObservation
from tft.vision.adapters import ObservationToGameStateBuilder
from tft.calibration.integration.adapter import DecisionCalibrationAdapter
from tft.calibration.integration.models import CalibrationConfig, CalibrationMode
from tft.vision.video_replay.evidence_models import (
    VideoFrameEvidence,
    VideoPredictionEvidence,
)


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def compute_file_hash(path: str) -> str:
    if not os.path.exists(path):
        return "FILE_NOT_FOUND"
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def get_runtime_hashes() -> Dict[str, str]:
    return {
        "git_commit": _git_commit(),
        "vision_hash": compute_file_hash(os.path.join(ROOT, "src", "tft", "vision", "shop_recognizer_v2.py")),
        "decision_hash": compute_file_hash(os.path.join(ROOT, "src", "tft", "decision", "engine.py")),
        "calibration_hash": compute_file_hash(os.path.join(ROOT, "src", "tft", "calibration", "integration", "adapter.py")),
        "calibration_source_sha256": compute_file_hash(os.path.join(ROOT, "data", "sets", "set18", "stats", "metatft", "percentiles.json")),
    }


def _git_commit() -> str:
    try:
        import subprocess
        return subprocess.check_output(
            ["git", "-C", ROOT, "rev-parse", "--short", "HEAD"]
        ).decode().strip()
    except Exception:
        return "UNKNOWN"


class VideoReplayPipeline:
    """Production Vision + Decision + Calibration pipeline for Video Replay."""

    def __init__(self, video_path: str, video_sha256: str):
        self.video_path = video_path
        self.video_sha256 = video_sha256
        self.hashes = get_runtime_hashes()

        # Production recognizers
        self.gold_recognizer = GoldRecognizer()
        self.shop_recognizer = ShopRecognizerV2()
        self.state_builder = ObservationToGameStateBuilder()

        # Decision & Calibration adapters (ON and OFF for comparison)
        self.adapter_on = DecisionCalibrationAdapter(config=CalibrationConfig(mode=CalibrationMode.ON))
        self.adapter_off = DecisionCalibrationAdapter(config=CalibrationConfig(mode=CalibrationMode.OFF))

    def process_frame(
        self,
        frame: np.ndarray,
        timestamp_sec: float,
        frame_idx: int,
        stage_round_hint: str = "3-2"
    ) -> Tuple[VideoPredictionEvidence, Dict[str, Any]]:
        """Run Vision Recognizers -> GameState -> DecisionEngine -> CALIB_C on a single frame."""
        t_start = time.perf_counter()
        t_mono = time.monotonic()
        t_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # 1. Gold Recognition
        t_gold_start = time.perf_counter()
        g_obs = self.gold_recognizer.recognize_gold(frame, timestamp_sec=timestamp_sec, frame_index=frame_idx)
        gold_latency_ms = (time.perf_counter() - t_gold_start) * 1000.0

        # 2. Shop Recognition
        t_shop_start = time.perf_counter()
        cards_rec = self.shop_recognizer.recognize_shop(frame)
        shop_latency_ms = (time.perf_counter() - t_shop_start) * 1000.0

        card_obs_list = []
        shop_dict_list = []
        for c in cards_rec:
            is_empty = (c.status == SlotStatus.EMPTY)
            card_obs_list.append(CardObservation(
                slot_index=c.slot_index,
                champion_pred=c.champion,
                cost_pred=c.cost,
                confidence=c.confidence,
                is_empty=is_empty,
                source="ShopRecognizerV2"
            ))
            shop_dict_list.append({
                "slot_index": c.slot_index,
                "champion": c.champion,
                "cost": c.cost,
                "status": c.status.value,
                "confidence": round(c.confidence, 3),
                "is_empty": is_empty,
            })

        # Dynamic level estimate from stage (e.g. Stage 2 -> L4, Stage 3 -> L5/6, Stage 4 -> L7)
        st_num = int(stage_round_hint.split("-")[0]) if "-" in stage_round_hint else 2
        dynamic_level = min(9, max(1, st_num + 2))

        obs = Observation(
            timestamp_sec=timestamp_sec,
            frame_index=frame_idx,
            stage_text=stage_round_hint,
            gold_val=g_obs.parsed_gold if g_obs.is_valid else 0,
            hp_val=100,
            level_val=dynamic_level,
            shop_cards=card_obs_list,
            sources={"shop": "ShopRecognizerV2", "gold": "GoldRecognizer"},
            confidences={"shop": 0.90, "gold": g_obs.confidence if g_obs.is_valid else 0.0},
            overall_confidence=0.85
        )

        # 4. Build GameState
        game_state = self.state_builder.build(obs)

        # 5. Run Decision Engine + CALIB_C
        t_dec_start = time.perf_counter()
        dec_res_on = self.adapter_on.decide(game_state)
        dec_res_off = self.adapter_off.decide(game_state)
        dec_latency_ms = (time.perf_counter() - t_dec_start) * 1000.0
        total_pipeline_ms = (time.perf_counter() - t_start) * 1000.0

        # Build prediction evidence
        pred_id = f"VPRED_{uuid.uuid4().hex[:12].upper()}"
        pred_evidence = VideoPredictionEvidence(
            prediction_id=pred_id,
            prediction_timestamp_iso=t_iso,
            prediction_monotonic=t_mono,
            video_timestamp_sec=round(timestamp_sec, 2),
            frame_index=frame_idx,
            git_commit=self.hashes["git_commit"],
            vision_hash=self.hashes["vision_hash"],
            decision_hash=self.hashes["decision_hash"],
            calibration_hash=self.hashes["calibration_hash"],
            calibration_source_sha256=self.hashes["calibration_source_sha256"],
            recognized_gold=g_obs.parsed_gold if g_obs.is_valid else None,
            gold_raw_text=g_obs.raw_text,
            gold_confidence=round(g_obs.confidence, 3),
            recognized_hp=game_state.player.hp,
            recognized_level=game_state.player.level,
            recognized_stage=game_state.stage_round,
            recognized_shop=shop_dict_list,
            recognized_board_units=[{"champion": u.champion, "cost": u.cost, "star_level": u.star_level} for u in game_state.board_units],
            recognized_board_count=len(game_state.board_units),
            recognized_action="NO_ACTION",
            action_confidence=0.0,
            base_action=dec_res_off.action,
            calibrated_action=dec_res_on.action,
            final_action=dec_res_on.action,
            is_calibration_flip=dec_res_on.is_flip,
            calibration_delta=dec_res_on.calibration_value,
            calibration_evidence=dec_res_on.applied_status,
            state_hash=dec_res_on.state_hash,
            decision_scores=dec_res_on.scores,
            vision_source="VIDEO_FRAME",
        )

        perf_meta = {
            "gold_latency_ms": round(gold_latency_ms, 3),
            "shop_latency_ms": round(shop_latency_ms, 3),
            "decision_latency_ms": round(dec_latency_ms, 3),
            "total_pipeline_ms": round(total_pipeline_ms, 3),
        }

        return pred_evidence, perf_meta
