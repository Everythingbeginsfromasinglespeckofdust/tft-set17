#!/usr/bin/env python3
"""Deep frame-level inspection of a single Ground Truth event with ASCII Causal Timeline."""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from tft.vision.ground_truth import GroundTruthDataset
from tft.vision.causal_extractor import CausalWindowExtractor


def parse_args():
    parser = argparse.ArgumentParser(description="Analyze Single Event Causal Timeline")
    parser.add_argument(
        "--video",
        type=str,
        default=r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4",
        help="Path to raw MP4 video file"
    )
    parser.add_argument(
        "--ground-truth",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "annotations", "gt_session_01.json"),
        help="Path to gt_session_01.json"
    )
    parser.add_argument(
        "--event-type",
        type=str,
        default="ROLL",
        choices=["ROLL", "BUY_UNIT"],
        help="Action Event Type (ROLL or BUY_UNIT)"
    )
    parser.add_argument(
        "--event-id",
        type=int,
        default=1,
        help="1-indexed Event sequence number"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "causal_audit", "event"),
        help="Output directory for visual frame crops"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print(f"🔬 SINGLE EVENT CAUSAL TIMELINE INSPECTION: {args.event_type} #{args.event_id}")
    print("=" * 80)

    gt = GroundTruthDataset.load_from_json(args.ground_truth)
    target_events = [e for e in gt.events if e.event_type.value == args.event_type]
    if args.event_id < 1 or args.event_id > len(target_events):
        print(f"[-] Invalid event id {args.event_id} (Must be 1 to {len(target_events)})")
        return

    target_ev = target_events[args.event_id - 1]
    print(f"[*] Target Ground Truth Event: {args.event_type} at {target_ev.timestamp_sec:.2f}s (Notes: {target_ev.notes})")

    extractor = CausalWindowExtractor()
    trace = extractor.extract_event_trace(
        video_path=args.video,
        event_id=f"{args.event_type.lower()}_{args.event_id:03d}",
        event_type=args.event_type,
        gt_timestamp_sec=target_ev.timestamp_sec,
        target_champion=target_ev.target_champion,
        window_radius_sec=1.0,
        target_fps=20.0,
        save_visual_crops_dir=args.output
    )

    print(f"[*] Extracted {len(trace.snapshots)} sub-frames at dt=0.050s across [{trace.window_start_sec:.2f}s -> {trace.window_end_sec:.2f}s]")

    print("\n" + "=" * 80)
    print("📊 ASCII CAUSAL SIGNAL TIMELINE")
    print("=" * 80)
    print(f"Action Ground Truth (T0): {target_ev.timestamp_sec:.2f}s")
    print(f"Sequence Pattern        : {trace.sequence_pattern}")
    print(f"Shop Onset Latency (dt) : {trace.dt_shop_onset:+.3f}s" if trace.dt_shop_onset is not None else "Shop Onset Latency (dt) : None")
    print(f"Shop Slots Changed      : {trace.shop_slots_changed}/5")

    print("\nSignal Transitions:")
    for tr in trace.transitions:
        print(f"  • [T {tr.dt_from_action:+.2f}s] {tr.signal_type.value:<6}: {tr.description}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
