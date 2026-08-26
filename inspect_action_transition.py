#!/usr/bin/env python3
"""Inspect StateDiff and Action Candidates at a specific timestamp."""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from tft.vision.pipeline import VisionPipeline
from tft.vision.state_diff import compute_state_diff
from tft.vision.action_event_detector import ActionEventDetectorV2


def parse_args():
    parser = argparse.ArgumentParser(description="Inspect StateDiff and Action Candidates at Timestamp")
    parser.add_argument(
        "--timeline",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "new_shop_timeline", "timeline.json"),
        help="Path to timeline.json"
    )
    parser.add_argument(
        "--timestamp",
        type=float,
        required=True,
        help="Target timestamp in seconds (e.g. 343.0)"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print(f"🔬 INSPECT ACTION TRANSITION AT {args.timestamp:.1f}s")
    print("=" * 80)

    pipeline = VisionPipeline()
    t_path = args.timeline if os.path.isfile(args.timeline) else os.path.join(args.timeline, "timeline.json")
    timeline = pipeline.load_from_existing_audit(t_path)

    # Find observation pair around target timestamp
    target_idx = None
    min_dt = 999.0
    for idx, o in enumerate(timeline.observations):
        dt = abs(o.timestamp_sec - args.timestamp)
        if dt < min_dt:
            min_dt = dt
            target_idx = idx

    if target_idx is None or target_idx == 0:
        print(f"[-] No valid observation pair found near {args.timestamp:.1f}s")
        return

    obs_before = timeline.observations[target_idx - 1]
    obs_after = timeline.observations[target_idx]

    diff = compute_state_diff(obs_before, obs_after)
    detector = ActionEventDetectorV2()
    candidates = detector.detect_candidates(diff)
    actions = detector.detect_actions(diff, obs_after)

    print(f"T0 ({obs_before.timestamp_sec:.1f}s):")
    print(f"  Gold : {obs_before.gold_val}G | Level: {obs_before.level_val} | HP: {obs_before.hp_val}")
    print(f"  Shop : {[c.champion_pred if not c.is_empty else 'EMPTY' for c in obs_before.shop_cards]}")

    print(f"\nT1 ({obs_after.timestamp_sec:.1f}s):")
    print(f"  Gold : {obs_after.gold_val}G | Level: {obs_after.level_val} | HP: {obs_after.hp_val}")
    print(f"  Shop : {[c.champion_pred if not c.is_empty else 'EMPTY' for c in obs_after.shop_cards]}")

    print(f"\nStateDiff:")
    print(f"  Gold Delta  : {diff.gold_delta}")
    print(f"  Shop Changes: {diff.shop_slots_changed} slots (Emptied: {diff.shop_slots_emptied}, Refreshed: {diff.shop_slots_refreshed})")
    print(f"  Bench Added : {diff.units_added_bench}")
    print(f"  Board Added : {diff.units_added_board}")

    print(f"\nAction Candidates:")
    for c in candidates:
        print(f"  • {c.action_type.value:<12} (Score: {c.score:.2f}) -> {[e.description for e in c.evidence_list]}")

    print(f"\nEmitted Actions:")
    for a in actions:
        print(f"  ✅ {a.action_type.value} (Conf: {a.confidence:.2f}, Target: {a.target_champion})")
    if not actions:
        print("  (None / NO_OBSERVED_ECONOMIC_ACTION)")
    print("=" * 80)


if __name__ == "__main__":
    main()
