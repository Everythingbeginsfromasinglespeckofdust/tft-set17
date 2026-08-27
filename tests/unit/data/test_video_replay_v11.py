"""Unit tests for TFT Real Video Replay Validation v1.1 Event-Stratified Expansion."""
import hashlib
import json
import os
import sys
import tempfile
import time
import uuid
import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from tft.vision.video_replay.evidence_models import (
    VideoSourceType,
    VideoCheckpointState,
    VideoDomainVerdict,
    VideoDecisionQuality,
    VideoCheckpoint,
)
from tft.vision.video_replay.coarse_discovery import CoarseEventScanner, CoarseCandidateEvent, discover_video_events
from tft.vision.video_replay.adaptive_refiner import AdaptiveCandidateRefiner, RefinedEventWindow, refine_video_candidates
from tft.vision.video_replay.session_runner_v11 import VideoReplaySessionRunnerV11


def create_dummy_mp4(path: str, duration_sec: float = 3.0, fps: float = 30.0, w: int = 1280, h: int = 720):
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(path, fourcc, fps, (w, h))
    num_frames = int(duration_sec * fps)
    for i in range(num_frames):
        frame = np.full((h, w, 3), (i % 256, (i * 2) % 256, (i * 4) % 256), dtype=np.uint8)
        out.write(frame)
    out.release()


# ── Test: Coarse Event Discovery ─────────────────────────────────────────────

class TestCoarseEventDiscovery:

    def test_scanner_finds_candidates(self, tmp_path):
        vid_p = os.path.join(str(tmp_path), "game.mp4")
        create_dummy_mp4(vid_p, duration_sec=2.0)

        out_dir = os.path.join(str(tmp_path), "candidates")
        summary = discover_video_events(
            video_path=vid_p,
            output_dir=out_dir,
            scan_step_sec=0.2,
            max_candidates=10,
        )

        assert summary["total_candidates"] > 0
        assert os.path.exists(summary["candidates_jsonl"])
        assert os.path.exists(os.path.join(out_dir, "candidates_summary.json"))


# ── Test: Adaptive Refinement & Clustering ───────────────────────────────────

class TestAdaptiveRefinement:

    def test_cluster_candidates_groups_close_events(self, tmp_path):
        vid_p = os.path.join(str(tmp_path), "game.mp4")
        create_dummy_mp4(vid_p, duration_sec=4.0)

        # Create candidates close to each other (e.g. 1.0s, 1.2s, 1.4s -> 1 cluster)
        cands = [
            CoarseCandidateEvent("C1", 1.0, 30, ["ROLL", "SHOP_CHANGE"], 20.0, 10.0, 5.0),
            CoarseCandidateEvent("C2", 1.2, 36, ["ROLL"], 22.0, 12.0, 5.0),
            CoarseCandidateEvent("C3", 1.4, 42, ["SHOP_CHANGE"], 15.0, 5.0, 5.0),
            # Distant candidate -> separate cluster
            CoarseCandidateEvent("C4", 3.0, 90, ["BUY_UNIT"], 10.0, 8.0, 5.0),
        ]

        refiner = AdaptiveCandidateRefiner(vid_p, cluster_window_sec=1.0)
        clusters = refiner.cluster_candidates(cands)

        assert len(clusters) == 2
        assert clusters[0].primary_type == "ROLL"
        assert clusters[0].cluster_size == 3
        assert clusters[1].primary_type == "BUY_UNIT"
        assert clusters[1].cluster_size == 1

    def test_stratified_sampling_selection(self, tmp_path):
        vid_p = os.path.join(str(tmp_path), "game.mp4")
        create_dummy_mp4(vid_p, duration_sec=5.0)

        events = [
            RefinedEventWindow(f"EVT_{i}", "ROLL", [], 1.0 + i * 0.1, 0.5, 1.5, 1.0, 30) for i in range(10)
        ] + [
            RefinedEventWindow(f"EVT_B_{i}", "BUY_UNIT", [], 2.0 + i * 0.1, 1.5, 2.5, 1.0, 30) for i in range(8)
        ] + [
            RefinedEventWindow(f"EVT_N_{i}", "NO_ACTION", [], 3.0 + i * 0.1, 2.5, 3.5, 1.0, 30) for i in range(5)
        ]

        refiner = AdaptiveCandidateRefiner(vid_p)
        selected = refiner.select_stratified_sample(events, target_count=15)
        assert len(selected) <= 15
        types = set(s.primary_type for s in selected)
        assert "ROLL" in types
        assert "BUY_UNIT" in types


# ── Test: Event-Stratified Session Runner v1.1 ────────────────────────────────

class TestSessionRunnerV11:

    def test_runner_evaluates_stratified_events(self, tmp_path):
        vid_p = os.path.join(str(tmp_path), "match.mp4")
        create_dummy_mp4(vid_p, duration_sec=3.0)

        runner = VideoReplaySessionRunnerV11(
            video_path=vid_p,
            output_base=str(tmp_path),
            session_id="TEST_V11_01",
        )

        ev = RefinedEventWindow(
            event_id="EVT_0001",
            primary_type="ROLL",
            secondary_types=["SHOP_CHANGE"],
            timestamp_center=1.0,
            start_sec=0.5,
            end_sec=1.5,
            duration_sec=1.0,
            frame_count=30,
        )

        chk = runner.evaluate_event_window(
            event=ev,
            human_key="C",
            human_action_label="ROLL",
            blind_mode=True,
            notes="Unit test evaluation",
        )

        assert chk.state == VideoCheckpointState.VERIFIED.value
        assert chk.prediction.recognized_action == "ROLL"
        assert chk.review.blind_mode is True
        assert chk.review.blind_order_valid() is True

        summary = runner.finalize_session_v11()
        assert summary["valid_checkpoints"] == 1
        assert summary["event_distribution"]["ROLL"] == 1
        assert os.path.exists(os.path.join(runner.reports_dir, "VIDEO_REPLAY_VALIDATION_V11.md"))
        assert os.path.exists(os.path.join(runner.reports_dir, "event_distribution.json"))
        assert os.path.exists(os.path.join(runner.reports_dir, "sampling_bias.json"))
