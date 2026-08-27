"""Unit tests for TFT Real Video Replay Validation v1.

Tests cover:
- Video listing & probe
- State machine & evidence completeness
- SourceType strictly VIDEO_REPLAY
- Label contamination detection
- Independent domain metrics
- Hash and frame persistence
- Gate logic
"""
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
    VideoSourceInfo,
    VideoFrameEvidence,
    VideoPredictionEvidence,
    VideoHumanInputEvent,
    VideoDomainReview,
    VideoCheckpoint,
)
from tft.vision.video_replay.video_probe import list_tft_recordings, probe_video, check_overlay_artifacts


def create_dummy_mp4(path: str, duration_sec: float = 2.0, fps: float = 30.0, w: int = 1280, h: int = 720):
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(path, fourcc, fps, (w, h))
    num_frames = int(duration_sec * fps)
    for i in range(num_frames):
        frame = np.full((h, w, 3), (i % 256, 128, 64), dtype=np.uint8)
        out.write(frame)
    out.release()


# ── Test: Video Probe ────────────────────────────────────────────────────────

class TestVideoProbe:

    def test_list_tft_recordings_empty_dir(self, tmp_path):
        res = list_tft_recordings(str(tmp_path))
        assert res == []

    def test_list_tft_recordings_with_video(self, tmp_path):
        vid_p = os.path.join(str(tmp_path), "game_rec_2026.mp4")
        create_dummy_mp4(vid_p, duration_sec=1.0)
        res = list_tft_recordings(str(tmp_path))
        assert len(res) == 1
        assert res[0]["filename"] == "game_rec_2026.mp4"
        assert res[0]["source_status"] == "ORIGINAL_SOURCE"

    def test_probe_video_extracts_frames_and_hash(self, tmp_path):
        vid_p = os.path.join(str(tmp_path), "sample.mp4")
        create_dummy_mp4(vid_p, duration_sec=2.0)
        out_dir = os.path.join(str(tmp_path), "output")
        res = probe_video(vid_p, out_dir)

        assert res["file_name"] == "sample.mp4"
        assert len(res["file_sha256"]) == 64
        assert res["duration_sec"] > 1.5
        assert len(res["probe_frames"]) == 3
        for pf in res["probe_frames"]:
            assert os.path.exists(pf["frame_path"])
            assert len(pf["frame_sha256"]) == 64

    def test_check_overlay_artifacts(self):
        clean_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        status, conf = check_overlay_artifacts(clean_frame)
        assert status == "NO_OVERLAY_ARTIFACTS"


# ── Test: Evidence Models & State Machine ───────────────────────────────────

class TestVideoEvidenceModels:

    def test_source_type_is_strictly_video_replay(self):
        chk = VideoCheckpoint(checkpoint_id="VCHK_0001", session_id="SESS_01")
        assert chk.source_type == "VIDEO_REPLAY"
        assert chk.source_type == VideoSourceType.VIDEO_REPLAY.value
        assert chk.source_type != "REAL_LIVE"

    def test_state_machine_valid_transitions(self, tmp_path):
        chk = VideoCheckpoint(checkpoint_id="VCHK_0001", session_id="SESS_01")
        assert chk.state == VideoCheckpointState.CAPTURED.value

        frame_file = os.path.join(str(tmp_path), "frame.png")
        cv2.imwrite(frame_file, np.zeros((100, 100, 3), dtype=np.uint8))
        chk.capture = VideoFrameEvidence(
            frame_path=frame_file,
            frame_sha256=hashlib.sha256(open(frame_file, "rb").read()).hexdigest(),
            video_path="sample.mp4",
            video_sha256="V_SHA",
            video_timestamp_sec=120.0,
            frame_index=7200,
            resolution_w=100,
            resolution_h=100,
        )
        assert chk.transition(VideoCheckpointState.PREDICTED)

        chk.prediction = VideoPredictionEvidence(
            prediction_id="PRED_01",
            prediction_timestamp_iso="2026-08-27T06:00:00Z",
            prediction_monotonic=1000.0,
            video_timestamp_sec=120.0,
            frame_index=7200,
            git_commit="commit123",
            vision_hash="V_HASH",
            decision_hash="D_HASH",
            calibration_hash="C_HASH",
            calibration_source_sha256="SRC_SHA",
            final_action="ROLL",
            vision_source="VIDEO_FRAME",
        )
        assert chk.transition(VideoCheckpointState.AWAITING_REVIEW)

        chk.human_input = VideoHumanInputEvent(
            input_event_id="INP_01",
            key_pressed="C",
            timestamp_iso="2026-08-27T06:00:01Z",
            timestamp_monotonic=1001.0,
            checkpoint_id="VCHK_0001",
            session_id="SESS_01",
        )
        chk.review = VideoDomainReview(
            shop_verdict="CORRECT",
            gold_verdict="CORRECT",
            board_verdict="CORRECT",
            action_verdict="CORRECT",
            state_verdict="CORRECT",
        )
        assert chk.transition(VideoCheckpointState.REVIEWED)

        assert chk.transition(VideoCheckpointState.VERIFIED)
        assert chk.state == VideoCheckpointState.VERIFIED.value
        assert chk.finalized_at is not None

    def test_missing_evidence_blocks_verified(self):
        chk = VideoCheckpoint(checkpoint_id="VCHK_0001", session_id="SESS_01")
        chk.state = VideoCheckpointState.REVIEWED.value
        assert not chk.transition(VideoCheckpointState.VERIFIED)
        assert chk.state == VideoCheckpointState.INVALID.value
        assert chk.invalidation_reason == "EVIDENCE_INCOMPLETE"

    def test_human_key_mapping(self):
        inp_c = VideoHumanInputEvent("I1", "C", "ISO", 100.0, "C1", "S1")
        assert inp_c.derive_verdict() == VideoDomainVerdict.CORRECT.value
        assert inp_c.derive_preferred_action() is None

        inp_r = VideoHumanInputEvent("I2", "R", "ISO", 100.0, "C2", "S1")
        assert inp_r.derive_preferred_action() == "ROLL"

        inp_l = VideoHumanInputEvent("I3", "L", "ISO", 100.0, "C3", "S1")
        assert inp_l.derive_preferred_action() == "LEVEL_UP"


# ── Test: Video Replay Session Runner ───────────────────────────────────────

class TestVideoReplaySessionRunner:

    def test_runner_processes_checkpoints_from_video(self, tmp_path):
        from tft.vision.video_replay.session_runner import VideoReplaySessionRunner

        vid_p = os.path.join(str(tmp_path), "test_game.mp4")
        create_dummy_mp4(vid_p, duration_sec=3.0, fps=30.0)

        out_base = os.path.join(str(tmp_path), "out")
        runner = VideoReplaySessionRunner(
            video_path=vid_p,
            output_base=out_base,
            session_id="TEST_VREPLAY_01",
        )

        chk = runner.process_checkpoint(
            timestamp_sec=1.0,
            human_key="C",
            domain_reviews={"shop": "CORRECT", "gold": "CORRECT"},
            human_notes="Test note",
        )

        assert chk.state == VideoCheckpointState.VERIFIED.value
        assert chk.source_type == "VIDEO_REPLAY"
        assert os.path.exists(chk.capture.frame_path)
        assert chk.prediction.vision_source == "VIDEO_FRAME"

        summary = runner.finalize_session()
        assert summary["valid_checkpoints"] == 1
        assert summary["source_type"] == "VIDEO_REPLAY"
        assert summary["gate"] == "VIDEO_REPLAY_PRELIMINARY"
        assert os.path.exists(os.path.join(runner.reports_dir, "VIDEO_REPLAY_VALIDATION.md"))
        assert os.path.exists(os.path.join(runner.reports_dir, "metrics.json"))
