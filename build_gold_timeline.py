#!/usr/bin/env python3
"""Build Full-Frame Gold Timeline from raw MP4 video."""
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

from tft.vision.gold_recognizer import GoldRecognizer
from tft.vision.gold_timeline import GoldTimelineProcessor


def parse_args():
    parser = argparse.ArgumentParser(description="Build Full-Frame Gold Timeline from MP4 video")
    parser.add_argument(
        "--video",
        type=str,
        default=r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4",
        help="Path to raw MP4 video"
    )
    parser.add_argument(
        "--start",
        type=float,
        default=300.0,
        help="Start time in seconds (default: 300.0)"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=600.0,
        help="Duration in seconds (default: 600.0)"
    )
    parser.add_argument(
        "--step",
        type=float,
        default=0.5,
        help="Time step in seconds (default: 0.5s)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "gold_timeline"),
        help="Output directory for gold timeline"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("💰 TFT FULL-FRAME GOLD TIMELINE V1 -- EXTRACTION PIPELINE")
    print("=" * 80)
    print(f"[*] Video Path : {args.video}")
    print(f"[*] Window     : [{args.start:.1f}s -> {args.start + args.duration:.1f}s] (Duration: {args.duration:.1f}s, Step: {args.step}s)")

    processor = GoldTimelineProcessor()
    raw_obs, stabilized, deltas = processor.process_video(
        video_path=args.video,
        start_sec=args.start,
        duration_sec=args.duration,
        step_sec=args.step
    )

    print(f"[*] Extracted Frames       : {len(raw_obs):,}")
    print(f"[*] Stabilized Frames      : {len(stabilized):,}")
    print(f"[*] Detected Delta Events  : {len(deltas):,}")

    os.makedirs(args.output, exist_ok=True)
    jsonl_path = os.path.join(args.output, "gold.jsonl")
    deltas_path = os.path.join(args.output, "gold_deltas.jsonl")
    summary_path = os.path.join(args.output, "summary.json")

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for obs in stabilized:
            f.write(json.dumps(obs.to_dict(), ensure_ascii=False) + "\n")

    with open(deltas_path, "w", encoding="utf-8") as f:
        for d in deltas:
            f.write(json.dumps(d.to_dict(), ensure_ascii=False) + "\n")

    summary = {
        "total_frames": len(raw_obs),
        "valid_frames": sum(1 for o in raw_obs if o.is_valid),
        "total_deltas": len(deltas),
        "roll_deltas": sum(1 for d in deltas if d.is_roll_delta),
        "buy_deltas": sum(1 for d in deltas if d.is_buy_delta),
        "income_deltas": sum(1 for d in deltas if d.is_round_income)
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("📈 GOLD EXTRACTION SUMMARY")
    print("=" * 80)
    print(f"  • Valid OCR Rate   : {summary['valid_frames'] / max(1, summary['total_frames']):.1%}")
    print(f"  • Total Deltas     : {summary['total_deltas']}")
    print(f"    - ROLL (-2G)     : {summary['roll_deltas']}")
    print(f"    - BUY  (-Cost)   : {summary['buy_deltas']}")
    print(f"    - Income (+G)    : {summary['income_deltas']}")
    print(f"[*] Saved Timeline to: {jsonl_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
