#!/usr/bin/env python3
"""Build Video Dataset CLI Tool (TFT Vision-to-Backtest Pipeline v1).

Usage:
    python build_video_dataset.py --video output/video_analysis/10min_audit/shop_timeline.json --output data/backtest/video_dataset
    python build_video_dataset.py --video path/to/game.mp4 --interval 0.5 --output data/backtest/video_dataset
"""
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
from tft.backtest.action_inference import ActionInferenceEngine
from tft.backtest.video_dataset import VideoDatasetBuilder
from tft.backtest.dataset import BacktestDataset


def parse_args():
    parser = argparse.ArgumentParser(description="TFT Video-to-Backtest Dataset Builder CLI")
    parser.add_argument(
        "--video",
        type=str,
        default=os.path.join(_HERE, "output", "video_analysis", "10min_audit", "shop_timeline.json"),
        help="Path to .mp4 video file or existing shop_timeline.json"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(_HERE, "data", "backtest", "video_dataset"),
        help="Directory to save generated dataset"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Frame sampling interval in seconds"
    )
    parser.add_argument(
        "--start-sec",
        type=float,
        default=300.0,
        help="Start timestamp in seconds"
    )
    parser.add_argument(
        "--max-sec",
        type=float,
        default=600.0,
        help="Max duration in seconds"
    )
    parser.add_argument(
        "--unverified-identity",
        action="store_true",
        default=False,
        help="Mark video player identity as unverified with Riot match history"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("🎬 TFT VISION-TO-BACKTEST PIPELINE (v1)")
    print("=" * 80)

    pipeline = VisionPipeline()
    inference_engine = ActionInferenceEngine(decision_window_sec=15.0)
    dataset_builder = VideoDatasetBuilder()

    # 1. Process Video or Load Existing Audit
    if args.video.endswith(".json"):
        print(f"[*] Loading ObservationTimeline from audit timeline: {args.video}")
        timeline = pipeline.load_from_existing_audit(args.video)
    else:
        print(f"[*] Processing video frames with VisionPipeline: {args.video}")
        timeline = pipeline.process_video(
            args.video,
            interval_sec=args.interval,
            start_sec=args.start_sec,
            max_duration_sec=args.max_sec
        )

    print(f"    Loaded {len(timeline.observations):,} observations (Duration: {timeline.duration_sec:.1f}s)")

    # 2. Extract and Infer Action Events
    print("\n[*] Extracting Action Events (Multi-signal OBSERVED & Window-based INFERRED)...")
    events = inference_engine.extract_action_events(timeline)
    print(f"    Extracted {len(events):,} total action events.")

    # 3. Build MIDGAME Backtest Samples
    print("\n[*] Reconstructing Causal GameState and Building Backtest Samples...")
    is_verified = not args.unverified_identity
    samples, stats = dataset_builder.build_dataset_from_timeline(
        timeline,
        events,
        is_verified_identity=is_verified
    )
    print(f"    Constructed {len(samples):,} verified MIDGAME Backtest Samples.")

    # 4. Save Outputs
    os.makedirs(args.output, exist_ok=True)
    timeline_path = os.path.join(args.output, "timeline.json")
    samples_path = os.path.join(args.output, "samples.jsonl")
    report_path = os.path.join(args.output, "dataset_report.json")
    md_report_path = os.path.join(args.output, "dataset_report.md")

    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump(timeline.to_dict(), f, indent=2, ensure_ascii=False)

    BacktestDataset.save_to_jsonl(samples, samples_path)

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    # Markdown report
    md = [
        "# 🎬 TFT Video Dataset Quality & Coverage Report\n",
        f"- **Source File**: `{args.video}`",
        f"- **Total Observations**: `{stats['observations_count']:,}`",
        f"- **Total Events Detected**: `{stats['events_count']:,}`",
        f"- **Total Backtest Samples**: `{stats['total_samples']:,}`",
        f"- **Identity Linking Status**: `{stats['identity_link_status']}`",
        f"- **Temporal Violations**: `{stats['temporal_violations_count']}`\n",
        "## Action Coverage by Source\n",
        "| Action Type | OBSERVED | INFERRED | UNKNOWN | Total |",
        "|---|---|---|---|---|"
    ]
    for act, src_dict in stats["action_coverage_by_source"].items():
        obs_c = src_dict.get("OBSERVED", 0)
        inf_c = src_dict.get("INFERRED", 0)
        unk_c = src_dict.get("UNKNOWN", 0)
        tot_c = obs_c + inf_c + unk_c
        md.append(f"| **{act}** | `{obs_c}` | `{inf_c}` | `{unk_c}` | `{tot_c}` |")

    with open(md_report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"\n[*] Artifacts saved to: {args.output}")
    print(f"    - Timeline JSON : {timeline_path}")
    print(f"    - Samples JSONL : {samples_path}")
    print(f"    - Quality Report: {md_report_path}")

    # 5. Display Console Summary
    print("\n" + "=" * 80)
    print("📊 DATASET COVERAGE SUMMARY")
    print("=" * 80)
    for act, src_dict in stats["action_coverage_by_source"].items():
        print(f"  • {act:<12}: OBSERVED={src_dict.get('OBSERVED', 0):<3} | INFERRED={src_dict.get('INFERRED', 0):<3} | UNKNOWN={src_dict.get('UNKNOWN', 0):<3}")
    print(f"  • Temporal Violations: {stats['temporal_violations_count']}")
    print("=" * 80)


if __name__ == "__main__":
    main()
