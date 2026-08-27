#!/usr/bin/env python3
"""Interactive CLI Review Queue for Human Validation Campaign."""
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

from tft.vision.campaign_manager import CampaignManager


def parse_args():
    parser = argparse.ArgumentParser(description="Review Validation Queue")
    parser.add_argument("--campaign", type=str, default="CAMPAIGN_001", help="Campaign ID")
    parser.add_argument("--session", type=str, default=None, help="Optional session filter")
    return parser.parse_args()


def main():
    args = parse_args()
    mgr = CampaignManager()
    c_dir = mgr.get_campaign_dir(args.campaign)
    q_dir = os.path.join(c_dir, "review_queue")

    if not os.path.exists(q_dir):
        print(f"[!] Review queue not found in {q_dir}")
        sys.exit(1)

    files = [f for f in os.listdir(q_dir) if f.endswith(".jsonl")]
    if args.session:
        files = [f for f in files if args.session in f]

    total_pending = 0
    total_items = 0

    print("=" * 80)
    print(f"📋 HUMAN REVIEW QUEUE OVERVIEW: {args.campaign}")
    print("=" * 80)

    for f in sorted(files):
        p = os.path.join(q_dir, f)
        items = []
        with open(p, "r", encoding="utf-8") as in_f:
            for line in in_f:
                if line.strip():
                    items.append(json.loads(line))
        total_items += len(items)
        pending = sum(1 for it in items if not it.get("reviewed", False))
        total_pending += pending
        print(f"  • {f:30s} | Total Items: {len(items):3d} | Pending: {pending:3d}")

    print("=" * 80)
    print(f"  Summary: Total Queue Items = {total_items}, Total Pending = {total_pending}")
    print("=" * 80)


if __name__ == "__main__":
    main()
