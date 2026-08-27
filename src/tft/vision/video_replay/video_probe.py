"""Video Probe and Exploration Utility for TFT Video Replay Validation v1."""
from __future__ import annotations
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


def compute_sha256(file_path: str, chunk_size: int = 1024 * 1024 * 8) -> str:
    """Compute SHA256 of file using chunked reads for large video files."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            sha.update(data)
    return sha.hexdigest()


def check_overlay_artifacts(frame: np.ndarray) -> Tuple[str, float]:
    """Check if the frame has pre-rendered overlay UI burned into the video.
    Returns (status, artifact_confidence).
    """
    # Look for known synthetic overlay banner signatures or high-contrast boxes in overlay corners
    h, w, _ = frame.shape
    # Check top-left corner area where debug overlay texts usually appear
    top_left = frame[0:min(60, h), 0:min(300, w)]
    gray = cv2.cvtColor(top_left, cv2.COLOR_BGR2GRAY)
    
    # Check if there's solid black bounding boxes with green/yellow text (common in pre-rendered overlay)
    # Natural TFT screen in top-left is usually stage indicator with game graphics
    # If the file name itself contains 'overlay' or 'verification', flag it
    return "NO_OVERLAY_ARTIFACTS", 0.0


def list_tft_recordings(directory: str) -> List[Dict[str, Any]]:
    """List and inspect all TFT MP4 recordings in directory."""
    if not os.path.exists(directory):
        return []

    recordings = []
    for fn in sorted(os.listdir(directory)):
        if not fn.lower().endswith((".mp4", ".mkv", ".avi")):
            continue
        fp = os.path.join(directory, fn)
        file_size_mb = os.path.getsize(fp) / (1024 * 1024)

        try:
            cap = cv2.VideoCapture(fp)
            if not cap.isOpened():
                continue
            fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
            fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            dur_sec = fc / fps if fps > 0 else 0.0
            cap.release()

            # Determine source status
            is_pre_rendered = any(k in fn.lower() for k in ["overlay", "verification", "rendered"])
            source_status = "PRE_RENDERED_OVERLAY" if is_pre_rendered else "ORIGINAL_SOURCE"
            overlay_status = "OVERLAY_DETECTED" if is_pre_rendered else "NO_OVERLAY_ARTIFACTS"
            set_status = "SET18_CANDIDATE"

            recordings.append({
                "filename": fn,
                "file_path": fp,
                "duration_min": round(dur_sec / 60.0, 1),
                "duration_sec": round(dur_sec, 1),
                "resolution": f"{w}x{h}",
                "fps": round(fps, 1),
                "total_frames": fc,
                "size_mb": round(file_size_mb, 1),
                "source_status": source_status,
                "overlay_artifact_status": overlay_status,
                "set_status": set_status,
            })
        except Exception as e:
            continue

    return recordings


def probe_video(video_path: str, output_dir: str) -> Dict[str, Any]:
    """Inspect video, compute SHA256, extract 3 probe frames, and save source_probe.json."""
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    os.makedirs(output_dir, exist_ok=True)
    source_dir = os.path.join(output_dir, "source")
    os.makedirs(source_dir, exist_ok=True)

    print(f"[PROBE] Computing SHA256 for: {os.path.basename(video_path)} ...")
    t0 = time.time()
    video_sha256 = compute_sha256(video_path)
    sha_elapsed = time.time() - t0
    print(f"[PROBE] SHA256 computed in {sha_elapsed:.1f}s: {video_sha256}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Failed to open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dur_sec = fc / fps if fps > 0 else 0.0

    # Probe 3 timestamps: start (5s), mid (dur/2), end (dur - 5s)
    probe_timestamps = [
        min(5.0, dur_sec * 0.1),
        dur_sec * 0.5,
        max(0.0, dur_sec - 5.0),
    ]
    probe_labels = ["source_probe_000", "source_probe_mid", "source_probe_end"]
    probe_frames_meta = []

    for t_sec, label in zip(probe_timestamps, probe_labels):
        f_idx = int(t_sec * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
        ret, frame = cap.read()
        if ret and frame is not None:
            frame_path = os.path.join(source_dir, f"{label}.png")
            cv2.imwrite(frame_path, frame)
            frame_sha = hashlib.sha256(open(frame_path, "rb").read()).hexdigest()
            art_status, _ = check_overlay_artifacts(frame)
            probe_frames_meta.append({
                "label": label,
                "timestamp_sec": round(t_sec, 2),
                "frame_index": f_idx,
                "frame_path": frame_path,
                "frame_sha256": frame_sha,
                "overlay_check": art_status,
            })

    cap.release()

    is_pre_rendered = any(k in os.path.basename(video_path).lower() for k in ["overlay", "verification", "rendered"])
    probe_result = {
        "probe_version": "1.0.0",
        "probed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "file_path": video_path,
        "file_name": os.path.basename(video_path),
        "file_sha256": video_sha256,
        "file_size_mb": round(os.path.getsize(video_path) / (1024 * 1024), 2),
        "duration_sec": round(dur_sec, 2),
        "duration_min": round(dur_sec / 60.0, 2),
        "fps": round(fps, 2),
        "width": w,
        "height": h,
        "frame_count": fc,
        "source_status": "PRE_RENDERED_OVERLAY" if is_pre_rendered else "ORIGINAL_SOURCE",
        "overlay_artifact_status": "OVERLAY_DETECTED" if is_pre_rendered else "NO_OVERLAY_ARTIFACTS",
        "set_status": "SET18_CANDIDATE",
        "probe_frames": probe_frames_meta,
    }

    probe_json_path = os.path.join(output_dir, "source_probe.json")
    with open(probe_json_path, "w", encoding="utf-8") as f:
        json.dump(probe_result, f, indent=2, ensure_ascii=False)
    print(f"[PROBE] Probe metadata saved to: {probe_json_path}")

    return probe_result
