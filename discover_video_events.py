#!/usr/bin/env python
"""TFT Coarse Video Event Discovery CLI v1.1"""
import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from tft.vision.video_replay.coarse_discovery import discover_video_events


def main():
    parser = argparse.ArgumentParser(description="Discover candidate events from TFT video")
    parser.add_argument("--video", required=True, help="Video MP4 path")
    parser.add_argument("--output", default="data/vision_validation/video_replay/candidates", help="Output directory")
    parser.add_argument("--step", type=float, default=0.5, help="Scan interval seconds")
    parser.add_argument("--max-candidates", type=int, default=120, help="Max candidates")
    args = parser.parse_args()

    print("=" * 80)
    print("COARSE VIDEO EVENT DISCOVERY v1.1")
    print("=" * 80)
    summary = discover_video_events(
        video_path=args.video,
        output_dir=args.output,
        scan_step_sec=args.step,
        max_candidates=args.max_candidates,
    )
    print("\nDiscovery Summary:")
    for k, v in summary.items():
        if k != "candidates_jsonl":
            print(f"  {k}: {v}")
    print(f"  Output saved: {summary['candidates_jsonl']}")


if __name__ == "__main__":
    main()
