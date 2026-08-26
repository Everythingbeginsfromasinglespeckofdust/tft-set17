#!/usr/bin/env python3
"""Detect high-fidelity ActionEvents using ActionEventDetector v2.1 with System Event Separation & Adaptive Resampling."""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from tft.vision.pipeline import VisionPipeline
from tft.vision.action_event_detector_v21 import ActionEventDetectorV21


def parse_args():
    parser = argparse.ArgumentParser(description="TFT Action Detection v2.1 CLI")
    parser.add_argument(
        "--video",
        type=str,
        default=r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4",
        help="Path to raw MP4 video file"
    )
    parser.add_argument(
        "--timeline",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "new_shop_timeline", "timeline.json"),
        help="Path to coarse timeline.json"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "action_v21"),
        help="Output directory for predictions"
    )
    parser.add_argument(
        "--target-fps",
        type=float,
        default=20.0,
        help="Adaptive local rescan target FPS (default: 20.0 FPS)"
    )
    parser.add_argument(
        "--no-resampling",
        action="store_true",
        help="Disable adaptive raw video resampling (coarse scan only)"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("⚡ TFT ACTION EVENT DETECTOR V2.1 -- ADAPTIVE PREDICTION GENERATOR")
    print("=" * 80)

    pipeline = VisionPipeline()
    t_path = args.timeline if os.path.isfile(args.timeline) else os.path.join(args.timeline, "timeline.json")
    timeline = pipeline.load_from_existing_audit(t_path)
    print(f"[*] Loaded Coarse Timeline: {len(timeline.observations):,} observations from {t_path}")

    detector = ActionEventDetectorV21(
        enable_adaptive_resampling=(not args.no_resampling),
        adaptive_target_fps=args.target_fps
    )

    vid_path = args.video if os.path.exists(args.video) and not args.no_resampling else None
    if vid_path:
        print(f"[*] Adaptive Resampling ENABLED on raw video: {vid_path} ({args.target_fps} FPS local rescan)")
    else:
        print("[*] Adaptive Resampling DISABLED (using timeline state diffs)")

    predicted_events = detector.process_timeline(timeline.observations, video_path=vid_path)
    print(f"[*] Detected Action & System Events: {len(predicted_events):,} total events")

    os.makedirs(args.output, exist_ok=True)
    out_jsonl = os.path.join(args.output, "predictions.jsonl")
    out_json = os.path.join(args.output, "predictions.json")

    with open(out_jsonl, "w", encoding="utf-8") as f:
        for ev in predicted_events:
            row = {
                "action_type": ev.action_type.value,
                "source": ev.source.value,
                "timestamp_sec": ev.timestamp_sec,
                "confidence": round(ev.confidence, 3),
                "evidence": ev.evidence,
                "target_champion": ev.target_champion,
                "slot_index": ev.slot_index,
                "evidence_data": ev.evidence_data,
                "metadata": ev.metadata
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "total_events": len(predicted_events),
            "events": [
                {
                    "action_type": ev.action_type.value,
                    "source": ev.source.value,
                    "timestamp_sec": ev.timestamp_sec,
                    "confidence": round(ev.confidence, 3),
                    "evidence": ev.evidence,
                    "target_champion": ev.target_champion,
                    "slot_index": ev.slot_index,
                    "evidence_data": ev.evidence_data,
                    "metadata": ev.metadata
                }
                for ev in predicted_events
            ]
        }, f, indent=2, ensure_ascii=False)

    print(f"[*] Saved Predictions to: {out_jsonl}")
    print("=" * 80)


if __name__ == "__main__":
    main()
