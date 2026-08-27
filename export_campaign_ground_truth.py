#!/usr/bin/env python3
"""Export verified Ground Truth dataset from Human Validation Campaign."""
import argparse
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
    parser = argparse.ArgumentParser(description="Export Campaign Ground Truth")
    parser.add_argument("--campaign", type=str, default="CAMPAIGN_001", help="Campaign ID")
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    return parser.parse_args()


def main():
    args = parse_args()
    mgr = CampaignManager()
    out_file = mgr.export_campaign_ground_truth(args.campaign, args.output)

    count = 0
    if os.path.exists(out_file):
        with open(out_file, "r", encoding="utf-8") as f:
            count = sum(1 for line in f if line.strip())

    print("=" * 80)
    print(f"📦 EXPORTED CAMPAIGN GROUND TRUTH -> {out_file}")
    print("=" * 80)
    print(f"  • Campaign ID      : {args.campaign}")
    print(f"  • Ground Truth Rows: {count}")
    print("=" * 80)


if __name__ == "__main__":
    main()
