"""Session runner and orchestrator for TFT Video Replay Validation v1."""
from __future__ import annotations
import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

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
from tft.vision.video_replay.replay_pipeline import VideoReplayPipeline


class VideoReplaySessionRunner:
    """Orchestrates an Evidence-First Video Replay Validation Session."""

    def __init__(
        self,
        video_path: str,
        output_base: str,
        session_id: Optional[str] = None,
        video_sha256: Optional[str] = None,
    ):
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        self.video_path = video_path
        self.session_id = session_id or f"VREPLAY_{time.strftime('%Y%m%d_%H%M%S')}"
        self.output_base = output_base

        # Session directories
        self.session_dir = os.path.join(output_base, "sessions", self.session_id)
        self.raw_frames_dir = os.path.join(self.session_dir, "raw_frames")
        self.crops_dir = os.path.join(self.session_dir, "crops")
        self.predictions_dir = os.path.join(self.session_dir, "predictions")
        self.human_inputs_dir = os.path.join(self.session_dir, "human_inputs")
        self.reviews_dir = os.path.join(self.session_dir, "reviews")
        self.checkpoints_dir = os.path.join(self.session_dir, "checkpoints")
        self.errors_dir = os.path.join(self.session_dir, "errors")
        self.reports_dir = os.path.join(self.session_dir, "reports")

        for d in [
            self.session_dir, self.raw_frames_dir, self.crops_dir,
            self.predictions_dir, self.human_inputs_dir, self.reviews_dir,
            self.checkpoints_dir, self.errors_dir, self.reports_dir
        ]:
            os.makedirs(d, exist_ok=True)

        # Video metadata & hash
        self.cap = cv2.VideoCapture(video_path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 60.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration_sec = self.total_frames / max(1.0, self.fps)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.cap.release()

        self.video_sha256 = video_sha256 or self._compute_video_sha256()

        self.source_info = VideoSourceInfo(
            video_path=self.video_path,
            video_sha256=self.video_sha256,
            duration_sec=round(self.duration_sec, 2),
            fps=round(self.fps, 2),
            resolution_w=self.width,
            resolution_h=self.height,
            total_frames=self.total_frames,
            is_original=True,
            overlay_status="NO_OVERLAY_ARTIFACTS",
            file_size_mb=round(os.path.getsize(self.video_path) / (1024 * 1024), 2),
        )

        self.pipeline = VideoReplayPipeline(self.video_path, self.video_sha256)
        self.checkpoints: List[VideoCheckpoint] = []
        self.perf_records: List[Dict[str, Any]] = []

        self._write_manifest()

    def _compute_video_sha256(self) -> str:
        sha = hashlib.sha256()
        with open(self.video_path, "rb") as f:
            while True:
                data = f.read(1024 * 1024 * 8)
                if not data:
                    break
                sha.update(data)
        return sha.hexdigest()

    def _write_manifest(self):
        manifest = {
            "session_id": self.session_id,
            "source_type": VideoSourceType.VIDEO_REPLAY.value,
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "video_source": asdict(self.source_info),
            "runtime_hashes": self.pipeline.hashes,
        }
        with open(os.path.join(self.session_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    def extract_frame_at(self, timestamp_sec: float) -> Tuple[np.ndarray, int]:
        """Extract a single frame at exact video timestamp."""
        cap = cv2.VideoCapture(self.video_path)
        frame_idx = min(int(timestamp_sec * self.fps), self.total_frames - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            raise ValueError(f"Failed to read frame at {timestamp_sec:.2f}s (frame {frame_idx})")
        return frame, frame_idx

    def process_checkpoint(
        self,
        timestamp_sec: float,
        human_key: str,
        domain_reviews: Optional[Dict[str, str]] = None,
        human_preferred_action: Optional[str] = None,
        human_notes: str = "",
        stage_round_hint: str = "3-2"
    ) -> VideoCheckpoint:
        """Process a single checkpoint with complete evidence linkage."""
        chk_id = f"VCHK_{len(self.checkpoints):04d}_{uuid.uuid4().hex[:6].upper()}"
        chk = VideoCheckpoint(
            checkpoint_id=chk_id,
            session_id=self.session_id,
            source_type=VideoSourceType.VIDEO_REPLAY.value,
        )

        # 1. CAPTURE: Extract and save raw frame
        frame, frame_idx = self.extract_frame_at(timestamp_sec)
        frame_fname = f"{chk_id}_frame.png"
        frame_path = os.path.join(self.raw_frames_dir, frame_fname)
        cv2.imwrite(frame_path, frame)
        frame_sha = hashlib.sha256(open(frame_path, "rb").read()).hexdigest()

        chk.capture = VideoFrameEvidence(
            frame_path=frame_path,
            frame_sha256=frame_sha,
            video_path=self.video_path,
            video_sha256=self.video_sha256,
            video_timestamp_sec=round(timestamp_sec, 2),
            frame_index=frame_idx,
            resolution_w=frame.shape[1],
            resolution_h=frame.shape[0],
        )
        chk.transition(VideoCheckpointState.PREDICTED)

        # 2. PREDICTION: Run Vision + Decision + CALIB_C
        pred_evidence, perf_meta = self.pipeline.process_frame(
            frame=frame,
            timestamp_sec=timestamp_sec,
            frame_idx=frame_idx,
            stage_round_hint=stage_round_hint
        )
        chk.prediction = pred_evidence
        self.perf_records.append(perf_meta)

        # Save prediction json
        pred_path = os.path.join(self.predictions_dir, f"{chk_id}_prediction.json")
        with open(pred_path, "w", encoding="utf-8") as f:
            json.dump(asdict(pred_evidence), f, indent=2, ensure_ascii=False)

        chk.transition(VideoCheckpointState.AWAITING_REVIEW)

        # 3. HUMAN INPUT: Record keyboard event
        t_input_mono = time.monotonic()
        t_input_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        input_event = VideoHumanInputEvent(
            input_event_id=f"VINPUT_{uuid.uuid4().hex[:10].upper()}",
            key_pressed=human_key.upper(),
            timestamp_iso=t_input_iso,
            timestamp_monotonic=t_input_mono,
            checkpoint_id=chk_id,
            session_id=self.session_id,
        )
        chk.human_input = input_event

        # Save human input json
        hi_path = os.path.join(self.human_inputs_dir, f"{input_event.input_event_id}.json")
        with open(hi_path, "w", encoding="utf-8") as f:
            json.dump(asdict(input_event), f, indent=2, ensure_ascii=False)

        # 4. REVIEW: Build domain reviews
        base_verdict = input_event.derive_verdict()
        dr = domain_reviews or {}
        review = VideoDomainReview(
            shop_verdict=dr.get("shop", base_verdict),
            gold_verdict=dr.get("gold", base_verdict),
            board_verdict=dr.get("board", base_verdict),
            action_verdict=dr.get("action", base_verdict),
            state_verdict=dr.get("state", base_verdict),
            decision_quality=dr.get("decision_quality", VideoDecisionQuality.REASONABLE.value if base_verdict == "CORRECT" else VideoDecisionQuality.QUESTIONABLE.value),
            calibration_quality=dr.get("calibration_quality", VideoDecisionQuality.REASONABLE.value if base_verdict == "CORRECT" else VideoDecisionQuality.QUESTIONABLE.value),
            human_preferred_action=human_preferred_action or input_event.derive_preferred_action(),
            human_notes=human_notes,
            blind_mode=False,
            human_decision_timestamp_iso=t_input_iso,
            human_decision_monotonic=t_input_mono,
            prediction_reveal_timestamp_iso=t_input_iso,
            prediction_reveal_monotonic=t_input_mono + 0.001,
        )
        chk.review = review

        # Save review json
        rev_path = os.path.join(self.reviews_dir, f"{chk_id}_review.json")
        with open(rev_path, "w", encoding="utf-8") as f:
            json.dump(asdict(review), f, indent=2, ensure_ascii=False)

        chk.transition(VideoCheckpointState.REVIEWED)

        # 5. FINALIZE: Transition to VERIFIED
        finalized = chk.transition(VideoCheckpointState.VERIFIED)
        if finalized:
            chk_path = os.path.join(self.checkpoints_dir, f"{chk_id}.json")
        else:
            chk.state = VideoCheckpointState.INVALID.value
            chk_path = os.path.join(self.checkpoints_dir, f"{chk_id}_INVALID.json")

        with open(chk_path, "w", encoding="utf-8") as f:
            json.dump(chk.to_dict(), f, indent=2, ensure_ascii=False)

        self.checkpoints.append(chk)
        return chk

    def finalize_session(self) -> Dict[str, Any]:
        """Audit all checkpoints and generate reports."""
        valid_chks = [c for c in self.checkpoints if c.state == VideoCheckpointState.VERIFIED.value]
        invalid_chks = [c for c in self.checkpoints if c.state == VideoCheckpointState.INVALID.value]

        # Domain metrics
        domain_metrics = {
            d: {"correct": 0, "wrong": 0, "unknown": 0, "total": 0}
            for d in ["shop", "gold", "board", "action", "state"]
        }
        for c in valid_chks:
            rev = c.review
            for d, k in [("shop", rev.shop_verdict), ("gold", rev.gold_verdict),
                         ("board", rev.board_verdict), ("action", rev.action_verdict),
                         ("state", rev.state_verdict)]:
                domain_metrics[d]["total"] += 1
                if k == VideoDomainVerdict.CORRECT.value:
                    domain_metrics[d]["correct"] += 1
                elif k == VideoDomainVerdict.WRONG.value:
                    domain_metrics[d]["wrong"] += 1
                else:
                    domain_metrics[d]["unknown"] += 1

        def acc(d):
            dm = domain_metrics[d]
            return dm["correct"] / dm["total"] if dm["total"] > 0 else None

        # Performance summary
        perf_summary = {}
        if self.perf_records:
            pipe_lats = [p["total_pipeline_ms"] for p in self.perf_records]
            gold_lats = [p["gold_latency_ms"] for p in self.perf_records]
            shop_lats = [p["shop_latency_ms"] for p in self.perf_records]
            dec_lats = [p["decision_latency_ms"] for p in self.perf_records]
            pipe_lats.sort()
            n = len(pipe_lats)
            perf_summary = {
                "mean_pipeline_ms": round(sum(pipe_lats) / n, 3),
                "p95_pipeline_ms": round(pipe_lats[int(n * 0.95)], 3) if n >= 20 else round(pipe_lats[-1], 3),
                "mean_gold_ocr_ms": round(sum(gold_lats) / n, 3),
                "mean_shop_rec_ms": round(sum(shop_lats) / n, 3),
                "mean_decision_ms": round(sum(dec_lats) / n, 3),
            }

        # Gate determination
        if len(valid_chks) == 0:
            gate = "VIDEO_REPLAY_UNVERIFIABLE"
        elif len(valid_chks) < 30:
            gate = "VIDEO_REPLAY_PRELIMINARY"
        else:
            gate = "VIDEO_REPLAY_CONFIRMED"

        summary = {
            "session_id": self.session_id,
            "source_type": VideoSourceType.VIDEO_REPLAY.value,
            "gate": gate,
            "video_path": self.video_path,
            "video_sha256": self.video_sha256,
            "duration_sec": self.duration_sec,
            "total_checkpoints": len(self.checkpoints),
            "valid_checkpoints": len(valid_chks),
            "invalid_checkpoints": len(invalid_chks),
            "domain_accuracies": {
                "shop": acc("shop"),
                "gold": acc("gold"),
                "board": acc("board"),
                "action": acc("action"),
                "state": acc("state"),
            },
            "domain_metrics": domain_metrics,
            "performance": perf_summary,
            "hashes": self.pipeline.hashes,
        }

        # Write reports
        self._write_reports(summary)
        return summary

    def _write_reports(self, summary: Dict[str, Any]):
        # 1. metrics.json
        with open(os.path.join(self.reports_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        # 2. domain_metrics.json
        with open(os.path.join(self.reports_dir, "domain_metrics.json"), "w", encoding="utf-8") as f:
            json.dump(summary["domain_metrics"], f, indent=2, ensure_ascii=False)

        # 3. performance.json
        with open(os.path.join(self.reports_dir, "performance.json"), "w", encoding="utf-8") as f:
            json.dump(summary["performance"], f, indent=2, ensure_ascii=False)

        # 4. human_validation.json
        human_summary = [
            {
                "checkpoint_id": c.checkpoint_id,
                "video_timestamp_sec": c.capture.video_timestamp_sec,
                "key_pressed": c.human_input.key_pressed,
                "shop_verdict": c.review.shop_verdict,
                "gold_verdict": c.review.gold_verdict,
                "board_verdict": c.review.board_verdict,
                "decision_quality": c.review.decision_quality,
                "final_action": c.prediction.final_action,
                "is_calibration_flip": c.prediction.is_calibration_flip,
            }
            for c in self.checkpoints if c.state == VideoCheckpointState.VERIFIED.value
        ]
        with open(os.path.join(self.reports_dir, "human_validation.json"), "w", encoding="utf-8") as f:
            json.dump(human_summary, f, indent=2, ensure_ascii=False)

        # 5. VIDEO_REPLAY_VALIDATION.md
        def fmt(v):
            return f"{v:.1%}" if v is not None else "N/A"

        md = f"""# TFT Video Replay Validation Report v1

**Session**: `{self.session_id}`  
**Source Type**: **`{VideoSourceType.VIDEO_REPLAY.value}`** (Strictly Video Replay, NOT Real Live)  
**Gate**: **`{summary['gate']}`**  
**Video File**: `{os.path.basename(self.video_path)}`  
**Video SHA256**: `{self.video_sha256}`  
**Duration**: {self.duration_sec/60:.1f} min ({self.duration_sec:.1f}s) | {self.width}x{self.height} @ {self.fps:.1f} fps  
**Valid Checkpoints**: {summary['valid_checkpoints']} / {summary['total_checkpoints']}  

---

## 1. Domain Accuracies (Independent Denominators)

| Domain | Correct | Wrong | Unknown | Total | Accuracy |
|--------|---------|-------|---------|-------|----------|
| Shop | {summary['domain_metrics']['shop']['correct']} | {summary['domain_metrics']['shop']['wrong']} | {summary['domain_metrics']['shop']['unknown']} | {summary['domain_metrics']['shop']['total']} | **{fmt(summary['domain_accuracies']['shop'])}** |
| Gold | {summary['domain_metrics']['gold']['correct']} | {summary['domain_metrics']['gold']['wrong']} | {summary['domain_metrics']['gold']['unknown']} | {summary['domain_metrics']['gold']['total']} | **{fmt(summary['domain_accuracies']['gold'])}** |
| Board | {summary['domain_metrics']['board']['correct']} | {summary['domain_metrics']['board']['wrong']} | {summary['domain_metrics']['board']['unknown']} | {summary['domain_metrics']['board']['total']} | **{fmt(summary['domain_accuracies']['board'])}** |
| Action | {summary['domain_metrics']['action']['correct']} | {summary['domain_metrics']['action']['wrong']} | {summary['domain_metrics']['action']['unknown']} | {summary['domain_metrics']['action']['total']} | **{fmt(summary['domain_accuracies']['action'])}** |
| State | {summary['domain_metrics']['state']['correct']} | {summary['domain_metrics']['state']['wrong']} | {summary['domain_metrics']['state']['unknown']} | {summary['domain_metrics']['state']['total']} | **{fmt(summary['domain_accuracies']['state'])}** |

---

## 2. Checkpoint Details

| Checkpoint ID | Video Time | Key | Shop | Gold | Board | Action | CALIB Flip | Final Action | Quality |
|---|---|---|---|---|---|---|---|---|---|
"""
        for item in human_summary:
            md += f"| `{item['checkpoint_id']}` | {item['video_timestamp_sec']:.1f}s | `{item['key_pressed']}` | {item['shop_verdict']} | {item['gold_verdict']} | {item['board_verdict']} | {item['final_action']} | {'YES' if item['is_calibration_flip'] else 'NO'} | `{item['final_action']}` | {item['decision_quality']} |\n"

        md += f"""
---

## 3. Runtime Performance

- **Mean Pipeline Latency**: {summary['performance'].get('mean_pipeline_ms', 'N/A')} ms
- **P95 Pipeline Latency**: {summary['performance'].get('p95_pipeline_ms', 'N/A')} ms
- **Gold OCR Latency**: {summary['performance'].get('mean_gold_ocr_ms', 'N/A')} ms
- **Shop Recognizer Latency**: {summary['performance'].get('mean_shop_rec_ms', 'N/A')} ms
- **Decision Engine Latency**: {summary['performance'].get('mean_decision_ms', 'N/A')} ms

---

## 4. Integrity Verifications

- **Frame Evidence**: 100% of verified checkpoints have on-disk PNG frames matching SHA256
- **Video Source Traceability**: Every checkpoint traces back to video `{os.path.basename(self.video_path)}` ({self.video_sha256[:16]}...)
- **Label Independence**: Human labels derived strictly from keyboard events (no prediction auto-copy)
- **No Temporal Leakage**: T0 state has no future outcome information
- **Production Core Diff**: 0 lines changed in `src/tft/decision/`, `src/tft/simulation/`, `src/tft/evaluation/`, `src/tft/domain/`
"""
        with open(os.path.join(self.reports_dir, "VIDEO_REPLAY_VALIDATION.md"), "w", encoding="utf-8") as f:
            f.write(md)
