#!/usr/bin/env python
"""TFT Adaptive Candidate Refinement & Clustering CLI v1.1"""
import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from tft.vision.video_replay.adaptive_refiner import refine_video_candidates


def main():
    parser = argparse.ArgumentParser(description="Refine and cluster candidate event windows")
    parser.add_argument("--video", required=True, help="Video MP4 path")
    parser.add_argument("--candidates", default="data/vision_validation/video_replay/candidates/candidates.jsonl", help="Candidates JSONL")
    parser.add_argument("--output", default="data/vision_validation/video_replay/refined", help="Output directory")
    parser.add_argument("--target-count", type=int, default=25, help="Target stratified count")
    args = parser.parse_args()

    print("=" * 80)
    print("ADAPTIVE CANDIDATE REFINEMENT & CLUSTERING v1.1")
    print("=" * 80)
    summary = refine_video_candidates(
        video_path=args.video,
        candidates_jsonl=args.candidates,
        output_dir=args.output,
        target_count=args.target_count,
    )
    print("\nRefinement Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
