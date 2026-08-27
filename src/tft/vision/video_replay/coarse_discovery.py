"""Coarse Event Discovery for TFT Video Replay Validation v1.1.

Scans video at low-cost intervals (0.5s) to discover candidates for:
- ROLL (Shop cards change)
- BUY_UNIT (Shop slot emptied)
- SYSTEM_REFRESH (Round transition + Shop change)
- LEVEL_UP (Level / XP increase)
- NO_ACTION (Stable planning or combat)
- SHOP_CHANGE, GOLD_CHANGE, BOARD_CHANGE, BENCH_CHANGE
"""
from __future__ import annotations
import hashlib
import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class CoarseCandidateEvent:
    candidate_id: str
    timestamp_sec: float
    frame_index: int
    candidate_types: List[str]
    shop_change_score: float = 0.0
    gold_change_score: float = 0.0
    board_change_score: float = 0.0
    is_planning_phase: bool = True
    estimated_stage: str = "2-1"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CoarseEventScanner:
    """Fast visual ROI difference scanner across MP4 video."""

    def __init__(
        self,
        video_path: str,
        scan_step_sec: float = 0.5,
        start_sec: float = 60.0,
        end_sec: Optional[float] = None,
    ):
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        self.video_path = video_path
        self.scan_step_sec = scan_step_sec
        cap = cv2.VideoCapture(video_path)
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration_sec = self.total_frames / max(1.0, self.fps)
        if self.duration_sec < 70.0:
            self.start_sec = 0.0
            self.end_sec = max(0.1, self.duration_sec - 0.1)
        else:
            self.start_sec = start_sec
            self.end_sec = min(self.duration_sec - 10.0, end_sec) if end_sec is not None else (self.duration_sec - 10.0)
        self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

    def _extract_rois(self, frame: np.ndarray) -> Dict[str, np.ndarray]:
        h, w, _ = frame.shape
        # 1280x720 relative coordinate boxes
        # Shop cards area: bottom center/right
        shop_roi = frame[int(h * 0.77):int(h * 0.98), int(w * 0.28):int(w * 0.76)]
        # Gold HUD area: bottom center-left
        gold_roi = frame[int(h * 0.88):int(h * 0.97), int(w * 0.20):int(w * 0.28)]
        # Board area: center
        board_roi = frame[int(h * 0.25):int(h * 0.70), int(w * 0.20):int(w * 0.80)]
        # Stage indicator: top center
        stage_roi = frame[int(h * 0.01):int(h * 0.08), int(w * 0.40):int(w * 0.60)]

        return {
            "shop": cv2.cvtColor(shop_roi, cv2.COLOR_BGR2GRAY) if shop_roi.size > 0 else np.zeros((10, 10)),
            "gold": cv2.cvtColor(gold_roi, cv2.COLOR_BGR2GRAY) if gold_roi.size > 0 else np.zeros((10, 10)),
            "board": cv2.cvtColor(board_roi, cv2.COLOR_BGR2GRAY) if board_roi.size > 0 else np.zeros((10, 10)),
            "stage": cv2.cvtColor(stage_roi, cv2.COLOR_BGR2GRAY) if stage_roi.size > 0 else np.zeros((10, 10)),
        }

    def scan(self, max_candidates: int = 100) -> List[CoarseCandidateEvent]:
        """Perform fast coarse scan to find candidate event timestamps."""
        cap = cv2.VideoCapture(self.video_path)
        candidates: List[CoarseCandidateEvent] = []

        curr_t = self.start_sec
        prev_rois: Optional[Dict[str, np.ndarray]] = None
        cand_idx = 0

        while curr_t <= self.end_sec and len(candidates) < max_candidates:
            f_idx = int(curr_t * self.fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            rois = self._extract_rois(frame)

            if prev_rois is not None:
                # Compute normalized absolute diffs
                shop_diff = float(np.mean(cv2.absdiff(rois["shop"], prev_rois["shop"])))
                gold_diff = float(np.mean(cv2.absdiff(rois["gold"], prev_rois["gold"])))
                board_diff = float(np.mean(cv2.absdiff(rois["board"], prev_rois["board"])))

                # Estimate stage
                stage_num = 2 + int(curr_t // 240)
                round_num = 1 + int((curr_t % 240) // 40)
                stage_est = f"{min(6, stage_num)}-{min(7, round_num)}"

                types = []
                # Significant shop change
                if shop_diff > 18.0:
                    if gold_diff > 8.0:
                        types.append("ROLL")
                    else:
                        types.append("SYSTEM_REFRESH")
                    types.append("SHOP_CHANGE")
                elif shop_diff > 7.0 and gold_diff > 4.0:
                    types.append("BUY_UNIT")
                    types.append("SHOP_CHANGE")

                if gold_diff > 12.0 and "ROLL" not in types and "BUY_UNIT" not in types:
                    types.append("GOLD_CHANGE")

                if board_diff > 25.0:
                    types.append("BOARD_CHANGE")

                # If no major delta, could be NO_ACTION candidate
                if not types and (curr_t % 60.0 < self.scan_step_sec):
                    types.append("NO_ACTION")

                if types:
                    cand_id = f"CAND_{cand_idx:04d}_{int(curr_t)}S"
                    cand_idx += 1
                    candidates.append(CoarseCandidateEvent(
                        candidate_id=cand_id,
                        timestamp_sec=round(curr_t, 2),
                        frame_index=f_idx,
                        candidate_types=types,
                        shop_change_score=round(shop_diff, 2),
                        gold_change_score=round(gold_diff, 2),
                        board_change_score=round(board_diff, 2),
                        is_planning_phase=(shop_diff > 5.0 or gold_diff > 3.0),
                        estimated_stage=stage_est,
                    ))

            prev_rois = rois
            curr_t += self.scan_step_sec

        cap.release()
        return candidates


def discover_video_events(
    video_path: str,
    output_dir: str,
    scan_step_sec: float = 0.5,
    max_candidates: int = 120
) -> Dict[str, Any]:
    """Run coarse discovery and save candidates.jsonl."""
    os.makedirs(output_dir, exist_ok=True)
    scanner = CoarseEventScanner(video_path, scan_step_sec=scan_step_sec)
    print(f"[COARSE] Scanning video {os.path.basename(video_path)} at {scan_step_sec}s step...")
    t0 = time.time()
    candidates = scanner.scan(max_candidates=max_candidates)
    elapsed = time.time() - t0
    print(f"[COARSE] Discovered {len(candidates)} candidate events in {elapsed:.2f}s")

    # Group by candidate type
    type_counts: Dict[str, int] = {}
    for c in candidates:
        for t in c.candidate_types:
            type_counts[t] = type_counts.get(t, 0) + 1

    # Save candidates.jsonl
    jsonl_path = os.path.join(output_dir, "candidates.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")

    summary = {
        "video_path": video_path,
        "video_duration_sec": scanner.duration_sec,
        "total_scanned_sec": round(scanner.end_sec - scanner.start_sec, 1),
        "total_candidates": len(candidates),
        "type_counts": type_counts,
        "scan_elapsed_sec": round(elapsed, 2),
        "candidates_jsonl": jsonl_path,
    }

    sum_path = os.path.join(output_dir, "candidates_summary.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return summary
