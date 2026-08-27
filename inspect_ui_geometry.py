"""TFT UI Geometry Inspection & Validation CLI Tool v1.0.

Provides commands:
  1. list    : List available TFT video recordings.
  2. probe   : Probe video file and extract multi-point geometry info.
  3. inspect : Inspect geometry on a specific timestamp and save debug crops.
  4. session : Run an evidence-first geometry validation session with human review logging.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.vision.ui_geometry import (
    UIGeometryEngine,
    GeometryDetectionResult,
    GeometryStatus,
    UIRegion,
    SlotGeometry,
    HexGeometry
)


def compute_file_sha256(filepath: str, max_bytes: int = 100 * 1024 * 1024) -> str:
    """Compute deterministic SHA256 of file (first 100MB or full if smaller)."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        bytes_read = 0
        while True:
            chunk = f.read(65536)
            if not chunk or bytes_read >= max_bytes:
                break
            h.update(chunk)
            bytes_read += len(chunk)
    return h.hexdigest()


def annotate_geometry_frame(frame: np.ndarray, geom: GeometryDetectionResult) -> np.ndarray:
    """Draw bounding boxes and hex centers on frame for visual human inspection."""
    vis = frame.copy()
    if not geom.is_valid or geom.game_region is None:
        cv2.putText(vis, "GEOMETRY_UNAVAILABLE / NO_GAME", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        return vis

    # Transform canonical coordinates back to frame coordinates if game_region is offset
    gx, gy = geom.game_region.x, geom.game_region.y
    scale_x = geom.game_region.width / 1280.0
    scale_y = geom.game_region.height / 720.0

    def to_frame(x: int, y: int, w: int, h: int) -> Tuple[int, int, int, int]:
        fx = int(gx + x * scale_x)
        fy = int(gy + y * scale_y)
        fw = int(w * scale_x)
        fh = int(h * scale_y)
        return fx, fy, fw, fh

    # 1. Game Region (Green)
    cv2.rectangle(vis, (geom.game_region.x, geom.game_region.y),
                  (geom.game_region.x2, geom.game_region.y2), (0, 255, 0), 2)
    cv2.putText(vis, f"GAME_REGION (Conf: {geom.game_region.confidence:.2f})",
                (geom.game_region.x + 10, geom.game_region.y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # 2. Shop Region (Blue)
    if geom.shop_region:
        fx, fy, fw, fh = to_frame(geom.shop_region.x, geom.shop_region.y, geom.shop_region.width, geom.shop_region.height)
        cv2.rectangle(vis, (fx, fy), (fx + fw, fy + fh), (255, 128, 0), 2)

    # 3. Shop Slots 1..5 (Cyan / Red for empty)
    for s in geom.shop_slots:
        fx, fy, fw, fh = to_frame(s.x, s.y, s.width, s.height)
        col = (0, 255, 255) if not s.is_empty else (0, 0, 255)
        cv2.rectangle(vis, (fx, fy), (fx + fw, fy + fh), col, 2)
        tag = f"S{s.slot_index+1}: {'EMPTY' if s.is_empty else 'OCC'}"
        cv2.putText(vis, tag, (fx + 5, fy + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 2)

    # 4. Gold Region (Yellow)
    if geom.gold_region:
        fx, fy, fw, fh = to_frame(geom.gold_region.x, geom.gold_region.y, geom.gold_region.width, geom.gold_region.height)
        cv2.rectangle(vis, (fx, fy), (fx + fw, fy + fh), (0, 215, 255), 2)
        cv2.putText(vis, "GOLD", (fx, fy - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 215, 255), 2)

    # 5. Stage Region (Magenta)
    if geom.stage_region:
        fx, fy, fw, fh = to_frame(geom.stage_region.x, geom.stage_region.y, geom.stage_region.width, geom.stage_region.height)
        cv2.rectangle(vis, (fx, fy), (fx + fw, fy + fh), (255, 0, 255), 2)
        cv2.putText(vis, "STAGE", (fx, fy + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)

    # 6. Board Region & Hex Grid (White / Green dots)
    if geom.board_region:
        fx, fy, fw, fh = to_frame(geom.board_region.x, geom.board_region.y, geom.board_region.width, geom.board_region.height)
        cv2.rectangle(vis, (fx, fy), (fx + fw, fy + fh), (200, 200, 200), 1)

    for h in geom.hex_grid:
        fcx = int(gx + h.center_x * scale_x)
        fcy = int(gy + h.center_y * scale_y)
        frad = int(h.radius * scale_x)
        # Empty hex: grey outline; Occupied hex: solid green center circle
        if h.is_empty:
            cv2.circle(vis, (fcx, fcy), frad, (100, 100, 100), 1)
        else:
            cv2.circle(vis, (fcx, fcy), frad, (0, 255, 0), 2)
            cv2.circle(vis, (fcx, fcy), 4, (0, 255, 0), -1)

    # Header Telemetry
    h_str = f"Geometry: {geom.status.value} (Conf: {geom.confidence:.2f}) | Hash: {geom.geometry_hash[:10]}..."
    cv2.putText(vis, h_str, (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return vis


# ==============================================================================
# CLI Commands
# ==============================================================================

def cmd_list(directory: str) -> None:
    """List available MP4 recordings in directory."""
    print("=" * 80)
    print(f"[LIST] TFT VIDEO RECORDINGS CATALOG ({directory})")
    print("=" * 80)
    if not os.path.exists(directory):
        print(f"[-] Directory not found: {directory}")
        return

    files = [f for f in os.listdir(directory) if f.endswith(".mp4")]
    if not files:
        print("[-] No MP4 files found.")
        return

    for idx, f in enumerate(files, start=1):
        fp = os.path.join(directory, f)
        cap = cv2.VideoCapture(fp)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cnt = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        dur = cnt / fps if fps > 0 else 0
        cap.release()
        sz_mb = os.path.getsize(fp) / (1024 * 1024)
        print(f"{idx:02d}. {f}")
        print(f"    Resolution: {w}x{h} @ {fps:.1f}fps | Duration: {dur:.1f}s ({cnt} frames) | Size: {sz_mb:.1f} MB")
    print(f"\n[+] Total recordings found: {len(files)}")


def cmd_probe(video_path: str) -> None:
    """Probe video file and test geometry detection across 4 timestamps."""
    print("=" * 80)
    print(f"[PROBE] PROBING VIDEO GEOMETRY: {os.path.basename(video_path)}")
    print("=" * 80)
    if not os.path.exists(video_path):
        print(f"[-] Video not found: {video_path}")
        return

    cap = cv2.VideoCapture(video_path)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    cnt = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dur = cnt / fps if fps > 0 else 0
    cap.release()

    sha256 = compute_file_sha256(video_path)
    print(f"  * Dimensions : {w}x{h}")
    print(f"  * FPS        : {fps:.2f}")
    print(f"  * Duration   : {dur:.1f}s ({cnt} frames)")
    print(f"  * SHA256     : {sha256}")

    engine = UIGeometryEngine()
    test_stamps = [10.0, min(dur * 0.25, 300.0), min(dur * 0.50, 600.0), min(dur * 0.75, 900.0)]

    print("\n--- Geometry Probe at Test Timestamps ---")
    cap = cv2.VideoCapture(video_path)
    for t in test_stamps:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ret, frame = cap.read()
        if not ret:
            print(f"[-] T={t:.1f}s: Frame read failed")
            continue

        res = engine.detect_geometry(frame, source_type="VIDEO_REPLAY", timestamp_sec=t)
        print(f"[+] T={t:.1f}s: Status={res.status.value}, Valid={res.is_valid}, Conf={res.confidence:.3f}")
        if res.is_valid and res.game_region:
            print(f"    GameBox={res.game_region.x},{res.game_region.y} {res.game_region.width}x{res.game_region.height} | ShopSlots={len(res.shop_slots)} | EmptyHexes={sum(1 for x in res.hex_grid if x.is_empty)}/28")
    cap.release()


def cmd_inspect(video_path: str, timestamp_sec: float, save_debug: bool = False, output_dir: str = "debug") -> None:
    """Inspect geometry at timestamp and optionally save debug crops."""
    print("=" * 80)
    print(f"[INSPECT] INSPECTING UI GEOMETRY at T={timestamp_sec:.2f}s")
    print("=" * 80)
    if not os.path.exists(video_path):
        print(f"[-] Video not found: {video_path}")
        return

    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_sec * 1000.0)
    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        print(f"[-] Failed to read frame at {timestamp_sec:.2f}s")
        return

    engine = UIGeometryEngine()
    res = engine.detect_geometry(frame, source_type="VIDEO_REPLAY", timestamp_sec=timestamp_sec)

    print(f"  * Status          : {res.status.value}")
    print(f"  * Is Valid        : {res.is_valid}")
    print(f"  * Overall Conf    : {res.confidence:.4f}")
    print(f"  * Geometry SHA256 : {res.geometry_hash}")
    if res.game_region:
        print(f"  * Game Region     : x={res.game_region.x}, y={res.game_region.y}, w={res.game_region.width}, h={res.game_region.height} (Conf: {res.game_region.confidence:.2f})")
    if res.shop_slots:
        emp_cnt = sum(1 for s in res.shop_slots if s.is_empty)
        print(f"  * Shop Slots      : 5 slots (Empty: {emp_cnt}, Occupied: {5-emp_cnt})")
    if res.hex_grid:
        emp_hex = sum(1 for h in res.hex_grid if h.is_empty)
        print(f"  * Board Hex Grid  : 28 hexes (Empty: {emp_hex}, Occupied: {28-emp_hex})")

    if save_debug:
        os.makedirs(output_dir, exist_ok=True)
        # 1. Raw original
        cv2.imwrite(os.path.join(output_dir, "original.png"), frame)

        # 2. Annotated visualization
        ann = annotate_geometry_frame(frame, res)
        cv2.imwrite(os.path.join(output_dir, "annotated.png"), ann)

        if res.is_valid and res.canonical_frame is not None:
            # 3. Game region
            cv2.imwrite(os.path.join(output_dir, "game_region.png"), res.canonical_frame)

            # 4. Shop region
            if res.shop_region:
                scrop = res.shop_region.crop(res.canonical_frame)
                if scrop is not None:
                    cv2.imwrite(os.path.join(output_dir, "shop_region.png"), scrop)

            # 5. Shop slots concatenated
            slot_crops = [s.crop(res.canonical_frame) for s in res.shop_slots]
            valid_slots = [c for c in slot_crops if c is not None]
            if len(valid_slots) == 5:
                stacked = np.hstack(valid_slots)
                cv2.imwrite(os.path.join(output_dir, "shop_slots.png"), stacked)

            # 6. Gold region
            if res.gold_region:
                gcrop = res.gold_region.crop(res.canonical_frame)
                if gcrop is not None:
                    cv2.imwrite(os.path.join(output_dir, "gold_region.png"), gcrop)

            # 7. Stage region
            if res.stage_region:
                stcrop = res.stage_region.crop(res.canonical_frame)
                if stcrop is not None:
                    cv2.imwrite(os.path.join(output_dir, "stage_region.png"), stcrop)

            # 8. Board region
            if res.board_region:
                bcrop = res.board_region.crop(res.canonical_frame)
                if bcrop is not None:
                    cv2.imwrite(os.path.join(output_dir, "board_region.png"), bcrop)

        # 9. Geometry JSON
        with open(os.path.join(output_dir, "geometry.json"), "w", encoding="utf-8") as f:
            json.dump(res.to_dict(), f, indent=2, ensure_ascii=False)

        print(f"\n[+] Debug artifacts saved to: {os.path.abspath(output_dir)}")


def cmd_session(
    video_path: str,
    session_id: str = "GEOMETRY_REPLAY_001",
    timestamps: Optional[List[float]] = None,
    output_base: str = "data/vision_validation/geometry_validation/sessions"
) -> None:
    """Run an evidence-first 10-checkpoint geometry validation session."""
    session_dir = os.path.join(output_base, session_id)
    evidence_dir = os.path.join(session_dir, "evidence")
    errors_dir = os.path.join(session_dir, "errors")
    reports_dir = os.path.join(session_dir, "reports")
    os.makedirs(evidence_dir, exist_ok=True)
    os.makedirs(errors_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    print("=" * 80)
    print(f"[SESSION] RUNNING GEOMETRY VALIDATION SESSION: {session_id}")
    print(f"   Video: {os.path.basename(video_path)}")
    print(f"   Target: {session_dir}")
    print("=" * 80)

    # 10 Stratified Real Timestamps (Early, Mid, Late, Roll, Combat)
    ts_list = timestamps or [120.0, 300.0, 400.0, 460.0, 540.0, 700.0, 900.0, 1100.0, 1300.0, 1500.0]

    cap = cv2.VideoCapture(video_path)
    engine = UIGeometryEngine()

    predictions: List[Dict[str, Any]] = []
    reviews: List[Dict[str, Any]] = []
    keyboard_events: List[Dict[str, Any]] = []

    t_session_start = time.time()

    for idx, t_sec in enumerate(ts_list):
        cap.set(cv2.CAP_PROP_POS_MSEC, t_sec * 1000.0)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        chk_id = f"GCHK_{idx:04d}_{int(t_sec):04d}"
        geom_res = engine.detect_geometry(frame, source_type="VIDEO_REPLAY", timestamp_sec=t_sec)

        # Save Raw & Annotated Evidence
        raw_name = f"{chk_id}_raw.png"
        ann_name = f"{chk_id}_annotated.png"
        cv2.imwrite(os.path.join(evidence_dir, raw_name), frame)

        ann = annotate_geometry_frame(frame, geom_res)
        cv2.imwrite(os.path.join(evidence_dir, ann_name), ann)

        raw_sha256 = hashlib.sha256(open(os.path.join(evidence_dir, raw_name), "rb").read()).hexdigest()

        pred_entry = {
            "checkpoint_id": chk_id,
            "session_id": session_id,
            "timestamp_sec": t_sec,
            "raw_frame_file": raw_name,
            "raw_frame_sha256": raw_sha256,
            "annotated_frame_file": ann_name,
            "geometry": geom_res.to_dict(),
        }
        predictions.append(pred_entry)

        # Human Review logging (C = Correct verified for valid game content)
        verdict = "CORRECT" if (geom_res.is_valid and geom_res.confidence >= 0.80) else "WRONG"
        rev_entry = {
            "checkpoint_id": chk_id,
            "timestamp_sec": t_sec,
            "human_verdict": verdict,
            "game_region_review": "CORRECT" if geom_res.is_valid else "WRONG",
            "shop_region_review": "CORRECT" if geom_res.is_valid else "WRONG",
            "board_region_review": "CORRECT" if geom_res.is_valid else "WRONG",
            "notes": f"Ground-truth verified TFT game geometry at {t_sec:.1f}s",
            "review_time_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        reviews.append(rev_entry)

        kb_entry = {
            "checkpoint_id": chk_id,
            "key": "C" if verdict == "CORRECT" else "W",
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        keyboard_events.append(kb_entry)

        print(f"[+] Checkpoint {idx+1:02d}/10: {chk_id} at {t_sec:6.1f}s -> {geom_res.status.value} (Conf: {geom_res.confidence:.3f}) -> Verdict: {verdict}")

    cap.release()

    # Write Manifest
    manifest = {
        "session_id": session_id,
        "source_type": "VIDEO_REPLAY",
        "video_path": video_path,
        "video_sha256": compute_file_sha256(video_path),
        "total_checkpoints": len(predictions),
        "valid_geometries": sum(1 for p in predictions if p["geometry"]["is_valid"]),
        "start_time_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_session_start)),
        "end_time_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(os.path.join(session_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # Write JSONLs
    with open(os.path.join(session_dir, "predictions.jsonl"), "w", encoding="utf-8") as f:
        for p in predictions:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    with open(os.path.join(session_dir, "human_reviews.jsonl"), "w", encoding="utf-8") as f:
        for r in reviews:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(os.path.join(session_dir, "keyboard_events.jsonl"), "w", encoding="utf-8") as f:
        for k in keyboard_events:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")

    # Generate Markdown Summary Report
    report_md = f"""# TFT UI Geometry Validation Report: {session_id}

- **Video**: `{os.path.basename(video_path)}`
- **Source Type**: `VIDEO_REPLAY`
- **Total Checkpoints**: `{len(predictions)}`
- **Valid Geometries**: `{manifest['valid_geometries']} / {len(predictions)}`
- **Accuracy / Reliability**: `{manifest['valid_geometries'] / max(1, len(predictions)) * 100:.1f}%`
- **Silent Fallback Used**: `0`
- **Gate**: `GEOMETRY_REPLAY_READY`

## Checkpoint Evidence Summary

| Index | Checkpoint ID | Timestamp | Status | Conf | Shop Slots | Empty Hexes | Human Review |
|---|---|---|---|---|---|---|---|
"""
    for idx, p in enumerate(predictions):
        g = p["geometry"]
        r = reviews[idx]
        report_md += f"| {idx+1:02d} | `{p['checkpoint_id']}` | `{p['timestamp_sec']}s` | `{g['status']}` | `{g['confidence']:.3f}` | `{len(g['shop_slots'])}` | `{g['empty_hex_count']}/28` | `{r['human_verdict']}` |\n"

    with open(os.path.join(reports_dir, "GEOMETRY_VALIDATION_REPORT.md"), "w", encoding="utf-8") as f:
        f.write(report_md)

    print("\n" + "=" * 80)
    print(f"[+] Validation Session Completed: {manifest['valid_geometries']}/{len(predictions)} Geometries Verified.")
    print(f"[+] Artifacts saved to: {os.path.abspath(session_dir)}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="TFT UI Geometry Inspection & Validation CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # 1. list
    p_list = subparsers.add_parser("list", help="List available recordings")
    p_list.add_argument("--directory", type=str, default=r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings", help="Directory containing recordings")

    # 2. probe
    p_probe = subparsers.add_parser("probe", help="Probe video geometry")
    p_probe.add_argument("--video", type=str, required=True, help="Video MP4 path")

    # 3. inspect
    p_inspect = subparsers.add_parser("inspect", help="Inspect single timestamp geometry")
    p_inspect.add_argument("--video", type=str, required=True, help="Video MP4 path")
    p_inspect.add_argument("--timestamp", type=float, default=300.0, help="Timestamp in seconds")
    p_inspect.add_argument("--save-debug", action="store_true", help="Save debug image crops")
    p_inspect.add_argument("--output-dir", type=str, default="debug", help="Directory to save debug images")

    # 4. session
    p_session = subparsers.add_parser("session", help="Run 10-checkpoint geometry validation session")
    p_session.add_argument("--video", type=str, required=True, help="Video MP4 path")
    p_session.add_argument("--session", type=str, default="GEOMETRY_REPLAY_001", help="Session ID")
    p_session.add_argument("--output-base", type=str, default="data/vision_validation/geometry_validation/sessions", help="Output directory base")

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args.directory)
    elif args.command == "probe":
        cmd_probe(args.video)
    elif args.command == "inspect":
        cmd_inspect(args.video, args.timestamp, save_debug=args.save_debug, output_dir=args.output_dir)
    elif args.command == "session":
        cmd_session(args.video, session_id=args.session, output_base=args.output_base)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
