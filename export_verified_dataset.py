#!/usr/bin/env python3
"""Export verified Ground Truth dataset from human verification logs."""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from tft.vision.verification_store import VerificationStore


def parse_args():
    parser = argparse.ArgumentParser(description="Export Verified Ground Truth Dataset")
    parser.add_argument("--session", type=str, default="SESSION_A", help="Session ID to export")
    parser.add_argument("--output", type=str, default=None, help="Output file path (default: data/vision_validation/ground_truth/gt_{session}.json)")
    return parser.parse_args()


def main():
    args = parse_args()
    store = VerificationStore()
    out_path = store.export_ground_truth(args.session, args.output)
    summary = store.get_summary(args.session)

    print("=" * 80)
    print(f"📦 EXPORTED VERIFIED GROUND TRUTH DATASET -> {out_path}")
    print("=" * 80)
    print(f"  • Session ID       : {args.session}")
    print(f"  • Total Reviewed   : {summary.total_reviewed}")
    print(f"  • Verified Correct : {summary.correct_count}")
    print(f"  • Error Count      : {summary.wrong_count}")
    print("=" * 80)


if __name__ == "__main__":
    main()
