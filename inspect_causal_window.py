#!/usr/bin/env python3
"""Inspect local raw MP4 frame sequence and signal onsets in any custom time window."""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from tft.vision.causal_extractor import CausalWindowExtractor


def parse_args():
    parser = argparse.ArgumentParser(description="Inspect Causal Frame Sequence in Custom Time Window")
    parser.add_argument(
        "--video",
        type=str,
        default=r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4",
        help="Path to raw MP4 video file"
    )
    parser.add_argument(
        "--start",
        type=float,
        required=True,
        help="Start timestamp in seconds"
    )
    parser.add_argument(
        "--end",
        type=float,
        required=True,
        help="End timestamp in seconds"
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=20.0,
        help="Sub-frame extraction FPS (default: 20.0)"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print(f"🔬 INSPECT CAUSAL WINDOW: {args.start:.2f}s -> {args.end:.2f}s ({args.fps} FPS)")
    print("=" * 80)

    center_t = (args.start + args.end) / 2.0
    radius = (args.end - args.start) / 2.0

    extractor = CausalWindowExtractor()
    trace = extractor.extract_event_trace(
        video_path=args.video,
        event_id="custom_window",
        event_type="CUSTOM",
        gt_timestamp_sec=center_t,
        window_radius_sec=radius,
        target_fps=args.fps
    )

    print(f"[*] Total Extracted Sub-frames: {len(trace.snapshots)}")
    for snap in trace.snapshots:
        shop_str = [c.get("champion") if not c.get("is_empty") else "EMPTY" for c in snap.shop]
        print(f"  • [T {snap.timestamp_sec:.2f}s] Frame #{snap.frame_index:<6} | Shop: {shop_str}")

    print("\nDetected Signal Transitions:")
    for tr in trace.transitions:
        print(f"  ⚡ [T {tr.timestamp_sec:.2f}s | dt={tr.dt_from_action:+.2f}s] {tr.signal_type.value}: {tr.description}")

    print("=" * 80)


if __name__ == "__main__":
    main()
