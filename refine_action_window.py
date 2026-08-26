#!/usr/bin/env python3
"""Refine and inspect a specific action window from raw MP4 video at custom FPS."""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from tft.vision.adaptive_resampler import AdaptiveResampler
from tft.vision.state_diff import compute_state_diff
from tft.vision.action_event_detector_v21 import ActionEventDetectorV21


def parse_args():
    parser = argparse.ArgumentParser(description="Refine Local Video Window for High-Speed Action Inspection")
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
        help="Start timestamp in seconds (e.g. 342.0)"
    )
    parser.add_argument(
        "--end",
        type=float,
        required=True,
        help="End timestamp in seconds (e.g. 344.5)"
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=20.0,
        help="Sampling FPS for local window (default: 20.0 FPS)"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print(f"🔬 LOCAL ADAPTIVE RESAMPLING WINDOW: {args.start:.2f}s -> {args.end:.2f}s ({args.fps} FPS)")
    print("=" * 80)

    if not os.path.exists(args.video):
        print(f"[-] Video not found: {args.video}")
        return

    resampler = AdaptiveResampler()
    detector = ActionEventDetectorV21(enable_adaptive_resampling=False)

    obs_list = resampler.refine_window(
        video_path=args.video,
        start_sec=args.start,
        end_sec=args.end,
        target_fps=args.fps
    )

    print(f"[*] Processed {len(obs_list)} sub-frames at dt={1.0/args.fps:.3f}s")

    for i in range(1, len(obs_list)):
        o_prev = obs_list[i - 1]
        o_curr = obs_list[i]
        diff = compute_state_diff(o_prev, o_curr)
        events = detector.detect_actions_from_diff(diff, o_prev, o_curr)

        if diff.shop_slots_changed > 0 or events:
            shop_str = [c.champion_pred if not c.is_empty else "EMPTY" for c in o_curr.shop_cards]
            print(f"\n[+{o_curr.timestamp_sec:.2f}s | dt={diff.dt_sec:.3f}s] Shop Changed: {diff.shop_slots_changed} slots -> {shop_str}")
            for ev in events:
                print(f"   ⚡ Emitted: {ev.action_type.value} ({ev.metadata.get('system_event_type', ev.action_type.value)}) | Conf: {ev.confidence:.2f} | Ev: {ev.evidence[0] if ev.evidence else '-'}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
