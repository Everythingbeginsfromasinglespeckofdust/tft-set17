#!/usr/bin/env python3
"""Inspect specific ActionEvent v2.2 candidate evaluation and evidence."""
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
    parser = argparse.ArgumentParser(description="Inspect single action event prediction v2.2")
    parser.add_argument(
        "--predictions",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "action_v22", "predictions.jsonl"),
        help="Path to predictions.jsonl"
    )
    parser.add_argument(
        "--event-id",
        type=str,
        required=True,
        help="Event index (1-based) or substring"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print(f"🔬 INSPECT ACTION EVENT V2.2: {args.event_id}")
    print("=" * 80)

    if not os.path.exists(args.predictions):
        print(f"[!] Predictions file not found: {args.predictions}")
        return

    events = []
    with open(args.predictions, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    try:
        idx = int(args.event_id) - 1
        if 0 <= idx < len(events):
            target = events[idx]
        else:
            target = None
    except ValueError:
        target = next((e for e in events if args.event_id in str(e)), None)

    if not target:
        print(f"[!] Event not found: {args.event_id}")
        return

    print(f"[*] Action Type : {target.get('action_type')}")
    print(f"[*] Timestamp   : {target.get('timestamp_sec'):.2f}s")
    print(f"[*] Source      : {target.get('source')}")
    print(f"[*] Confidence  : {target.get('confidence')} (Score: {target.get('detection_score')})")
    print(f"[*] Target Unit : {target.get('target_champion')} (Slot #{target.get('target_slot')})")

    print("\nEvidence:")
    for ev in target.get("evidence", []):
        print(f"  • {ev}")

    print("\nStructured Evidence Data:")
    print(json.dumps(target.get("evidence_data", {}), indent=2, ensure_ascii=False))
    print("=" * 80)


if __name__ == "__main__":
    main()
