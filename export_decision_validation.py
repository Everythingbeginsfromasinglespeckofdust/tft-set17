#!/usr/bin/env python3
"""Export human-reviewed decision labels into dataset."""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from tft.decision.validation_store import DecisionValidationStore


def parse_args():
    parser = argparse.ArgumentParser(description="Export Human Decision Labels")
    parser.add_argument("--session", type=str, default=None, help="Session ID filter")
    parser.add_argument("--output", type=str, default="data/decision_validation/ground_truth/human_decision_labels.jsonl", help="Output file path")
    return parser.parse_args()


def main():
    args = parse_args()
    store = DecisionValidationStore()
    out_file = store.export_human_decision_labels(session_id=args.session, output_path=args.output)

    count = 0
    if os.path.exists(out_file):
        with open(out_file, "r", encoding="utf-8") as f:
            count = sum(1 for line in f if line.strip())

    print("=" * 80)
    print(f"📦 EXPORTED HUMAN DECISION LABELS -> {out_file}")
    print("=" * 80)
    print(f"  • Total Decision Label Rows: {count}")
    print("=" * 80)


if __name__ == "__main__":
    main()
