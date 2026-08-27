#!/usr/bin/env python3
"""Inspect captured error snapshots and human verification diagnostics."""
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
    parser = argparse.ArgumentParser(description="Inspect Vision Error Snapshots")
    parser.add_argument("--snapshot-dir", type=str, required=True, help="Path to error snapshot directory")
    return parser.parse_args()


def main():
    args = parse_args()
    if not os.path.exists(args.snapshot_dir):
        print(f"[!] Directory not found: {args.snapshot_dir}")
        sys.exit(1)

    diag_file = os.path.join(args.snapshot_dir, "error_diagnostics.json")
    if not os.path.exists(diag_file):
        print(f"[!] Diagnostics JSON not found in {args.snapshot_dir}")
        sys.exit(1)

    with open(diag_file, "r", encoding="utf-8") as f:
        diag = json.load(f)

    print("=" * 80)
    print(f"🔍 ERROR SNAPSHOT INSPECTOR: {args.snapshot_dir}")
    print("=" * 80)
    print(f"  • Timestamp   : {diag.get('timestamp_sec')}s")
    print(f"  • Error Reason: {diag.get('error_reason')}")
    print("\n[Observation]:")
    print(json.dumps(diag.get("current_observation"), indent=2, ensure_ascii=False))
    print("\n[StateDiff]:")
    print(json.dumps(diag.get("state_diff"), indent=2, ensure_ascii=False))
    print("\n[Action Event]:")
    print(json.dumps(diag.get("action_event"), indent=2, ensure_ascii=False))
    print("=" * 80)


if __name__ == "__main__":
    main()
