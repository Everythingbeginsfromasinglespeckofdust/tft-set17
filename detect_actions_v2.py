#!/usr/bin/env python3
"""Detect high-fidelity ActionEvents from ObservationTimeline using ActionEventDetectorV2."""
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
from tft.vision.action_event_detector import ActionEventDetectorV2


def parse_args():
    parser = argparse.ArgumentParser(description="TFT Action Detection v2 CLI")
    parser.add_argument(
        "--timeline",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "new_shop_timeline", "timeline.json"),
        help="Path to timeline.json"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "action_v2"),
        help="Output directory for action predictions"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("⚡ TFT ACTION EVENT DETECTOR V2 -- PREDICTION GENERATOR")
    print("=" * 80)

    pipeline = VisionPipeline()
    t_path = args.timeline if os.path.isfile(args.timeline) else os.path.join(args.timeline, "timeline.json")
    timeline = pipeline.load_from_existing_audit(t_path)
    print(f"[*] Loaded Timeline: {len(timeline.observations):,} observations from {t_path}")

    detector = ActionEventDetectorV2()
    predicted_events = detector.process_timeline(timeline.observations)
    print(f"[*] Detected Actions: {len(predicted_events):,} action events")

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
                "evidence_data": ev.evidence_data
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
                    "evidence_data": ev.evidence_data
                }
                for ev in predicted_events
            ]
        }, f, indent=2, ensure_ascii=False)

    print(f"[*] Saved Predictions to: {out_jsonl}")
    print("=" * 80)


if __name__ == "__main__":
    main()
