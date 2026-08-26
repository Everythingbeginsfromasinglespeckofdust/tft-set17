#!/usr/bin/env python3
"""Build high-fidelity TFT shop timeline from MP4 video using ShopRecognizerV2."""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from tft.vision.shop_recognizer_v2 import ShopRecognizerV2
from tft.vision.shop_timeline_v2 import ShopTimelineV2Builder


def parse_args():
    parser = argparse.ArgumentParser(description="TFT Shop Timeline V2 Extraction CLI")
    parser.add_argument(
        "--video",
        type=str,
        default=r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4",
        help="Path to .mp4 video file"
    )
    parser.add_argument(
        "--start",
        type=float,
        default=300.0,
        help="Start timestamp in seconds (default: 300.0s)"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=600.0,
        help="Duration in seconds (default: 600.0s)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Sampling interval in seconds (default: 0.5s)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "new_shop_timeline"),
        help="Output directory for new timeline artifacts"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("🎬 TFT SHOP RECOGNITION V2 -- TIMELINE GENERATOR")
    print("=" * 80)

    recognizer = ShopRecognizerV2()
    builder = ShopTimelineV2Builder(recognizer=recognizer)

    timeline = builder.process_video(
        video_path=args.video,
        start_sec=args.start,
        duration_sec=args.duration,
        interval_sec=args.interval,
        output_dir=args.output
    )

    print("\n" + "=" * 80)
    print("✅ TIMELINE EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"  • Total Observations : {len(timeline.observations):,}")
    print(f"  • Total Action Events: {len(timeline.events):,}")
    print(f"  • Artifacts Location : {args.output}")
    print("=" * 80)


if __name__ == "__main__":
    main()
