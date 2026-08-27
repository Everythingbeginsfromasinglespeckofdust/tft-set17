#!/usr/bin/env python3
"""Refine a specific time window at arbitrary high FPS (e.g. 20 FPS)."""
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

from tft.vision.adaptive_action_pipeline import AdaptiveActionPipeline
from tft.vision.refined_observation import CandidateWindow, TriggerReason


def parse_args():
    parser = argparse.ArgumentParser(description="Refine Specific Action Time Window")
    parser.add_argument("--video", type=str, required=True, help="Path to raw MP4 video")
    parser.add_argument("--start", type=float, required=True, help="Start time in seconds")
    parser.add_argument("--end", type=float, required=True, help="End time in seconds")
    parser.add_argument("--fps", type=float, default=20.0, help="Target refinement FPS (default: 20)")
    parser.add_argument("--output", type=str, default="data/backtest/pilot/adaptive/window_debug.json")
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("🔬 TFT ADAPTIVE WINDOW REFINER")
    print("=" * 80)
    print(f"[*] Video Path : {args.video}")
    print(f"[*] Window     : [{args.start:.2f}s -> {args.end:.2f}s] @ {args.fps:.1f} FPS")

    window = CandidateWindow(
        window_id="MANUAL_WINDOW",
        start_sec=args.start,
        end_sec=args.end,
        trigger_time_sec=(args.start + args.end) / 2.0,
        trigger_reasons=[TriggerReason.SHOP_SLOTS_CHANGED]
    )

    pipeline = AdaptiveActionPipeline(refinement_fps=args.fps)
    refined_obs = pipeline.refine_candidate_window(args.video, window, fps_target=args.fps)

    print(f"[*] Extracted {len(refined_obs)} high-resolution frames.")
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    out_data = [
        {
            "timestamp_sec": round(o.timestamp_sec, 3),
            "gold": o.gold_val,
            "shop": [c.champion_pred for c in o.shop_cards]
        }
        for o in refined_obs
    ]
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2, ensure_ascii=False)

    print(f"[+] Saved {len(out_data)} refined observations -> {args.output}")
    print("=" * 80)


if __name__ == "__main__":
    main()
