#!/usr/bin/env python3
"""Run Production ActionEventDetector v2.2 on video timeline."""
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
from tft.vision.action_event_detector_v22 import ActionEventDetectorV22


def parse_args():
    parser = argparse.ArgumentParser(description="Run ActionEventDetector v2.2 on video observations")
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
        help="Path to shop timeline JSON"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "action_v22"),
        help="Output directory for predictions"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("🚀 TFT ACTION EVENT DETECTOR V2.2 -- PRODUCTION PIPELINE")
    print("=" * 80)

    # 1. Load Timeline Observations via VisionPipeline
    pipeline = VisionPipeline()
    t_path = args.timeline if os.path.isfile(args.timeline) else os.path.join(args.timeline, "timeline.json")
    timeline = pipeline.load_from_existing_audit(t_path)
    observations = timeline.observations
    print(f"[*] Loaded Coarse Timeline: {len(observations):,} observations from {t_path}")

    # 2. Run ActionEventDetector v2.2
    detector = ActionEventDetectorV22()
    events = detector.detect_actions(observations, video_path=args.video)

    # 3. Export Predictions
    os.makedirs(args.output, exist_ok=True)
    pred_path = os.path.join(args.output, "predictions.jsonl")
    summary_path = os.path.join(args.output, "detection_summary.json")

    with open(pred_path, "w", encoding="utf-8") as f:
        for ev in events:
            row = {
                "action_type": ev.action_type.value,
                "source": ev.source.value,
                "confidence": ev.confidence,
                "timestamp_sec": ev.timestamp_sec,
                "evidence": ev.evidence,
                "evidence_data": ev.evidence_data,
                "target_champion": ev.target_champion,
                "slot_index": ev.slot_index
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "total_observations": len(observations),
        "total_predicted_events": len(events),
        "events_by_type": {}
    }
    for ev in events:
        t = ev.action_type.value
        summary["events_by_type"][t] = summary["events_by_type"].get(t, 0) + 1

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("📈 DETECTION SUMMARY (v2.2)")
    print("=" * 80)
    print(f"  • Total Detected Events: {len(events)}")
    for t, c in summary["events_by_type"].items():
        print(f"    - {t:<12}: {c}")
    print(f"[*] Saved Predictions to: {pred_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
