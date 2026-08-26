#!/usr/bin/env python3
"""Inspect Timeline CLI Tool (TFT Vision-to-Backtest Pipeline v1).

Usage:
    python inspect_timeline.py --input data/backtest/video_dataset/timeline.json
    python inspect_timeline.py --input data/backtest/video_dataset/samples.jsonl --limit 20
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


def parse_args():
    parser = argparse.ArgumentParser(description="TFT Timeline and Event Inspector CLI")
    parser.add_argument(
        "--input",
        type=str,
        default=os.path.join(_HERE, "data", "backtest", "video_dataset", "timeline.json"),
        help="Path to timeline.json or samples.jsonl"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum entries to display"
    )
    return parser.parse_args()


def inspect_timeline_json(data: dict, limit: int):
    print("=" * 80)
    print("📋 TIMELINE INSPECTION OVERVIEW")
    print("=" * 80)
    print(f"  • Source File         : {data.get('video_path')}")
    print(f"  • Total Duration      : {data.get('duration_sec', 0.0):.1f}s")
    print(f"  • Observations Count  : {data.get('observations_count', 0):,}")
    print(f"  • Events Count        : {data.get('events_count', 0):,}")

    events = data.get("events", [])
    print(f"\n--- ACTION EVENTS STREAM (First {min(limit, len(events))} of {len(events)}) ---")
    for idx, ev in enumerate(events[:limit], 1):
        t_sec = ev.get("timestamp_sec", 0.0)
        act = ev.get("action_type")
        src = ev.get("source")
        conf = ev.get("confidence", 1.0)
        evidence = ev.get("evidence", [])
        ev_str = "; ".join(evidence) if evidence else "None"
        print(f"  [{t_sec:6.1f}s] {act:<10} (Source: {src:<8}, Conf: {conf:.2f}) -> {ev_str}")


def inspect_samples_jsonl(file_path: str, limit: int):
    print("=" * 80)
    print("📋 BACKTEST SAMPLES INSPECTION")
    print("=" * 80)
    samples = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line.strip()))

    print(f"  • Total Samples Loaded : {len(samples):,}")
    print(f"\n--- SAMPLE SNAPSHOTS (First {min(limit, len(samples))} of {len(samples)}) ---")
    for idx, s in enumerate(samples[:limit], 1):
        obs = s.get("observed_state", {})
        fut = s.get("future_observation", {})
        meta = s.get("metadata", {})
        t_sec = obs.get("timestamp_sec", 0.0)
        stg = obs.get("stage_round", "?")
        gold = obs.get("gold", 0)
        act = obs.get("actual_action", "UNKNOWN")
        src = meta.get("action_source", "UNKNOWN")
        place = fut.get("final_placement", "-")

        print(f"  #{idx:02d} [{t_sec:6.1f}s] Stage {stg:<4} | Gold: {gold:2d}G | Action: {act:<10} ({src:<8}) | Placement: #{place}")


def main():
    args = parse_args()
    if not os.path.exists(args.input):
        print(f"[!] File not found: {args.input}")
        return

    if args.input.endswith(".json"):
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
        inspect_timeline_json(data, args.limit)
    elif args.input.endswith(".jsonl"):
        inspect_samples_jsonl(args.input, args.limit)
    else:
        print(f"[!] Unsupported file extension for {args.input}")


if __name__ == "__main__":
    main()
