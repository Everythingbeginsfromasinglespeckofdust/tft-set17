#!/usr/bin/env python3
"""Compare OLD ShopRecognizer v1 vs NEW ShopRecognizer v2 against Ground Truth."""
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

from tft.vision.pipeline import VisionPipeline
from tft.vision.ground_truth import GroundTruthDataset
from tft.vision.shop_metrics import compare_shop_versions


def parse_args():
    parser = argparse.ArgumentParser(description="Compare OLD vs NEW Shop Recognition Versions")
    parser.add_argument(
        "--old",
        type=str,
        default=os.path.join(_HERE, "output", "video_analysis", "10min_audit", "shop_timeline.json"),
        help="Path to OLD shop_timeline.json"
    )
    parser.add_argument(
        "--new",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "new_shop_timeline", "timeline.json"),
        help="Path to NEW timeline.json"
    )
    parser.add_argument(
        "--ground-truth",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "annotations", "gt_session_01.json"),
        help="Path to gt_session_01.json"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "reports", "comparison"),
        help="Output directory for comparison report"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("⚖️ TFT SHOP RECOGNITION -- OLD vs NEW COMPARATIVE AUDIT")
    print("=" * 80)

    pipeline = VisionPipeline()
    old_p = args.old if os.path.isfile(args.old) else os.path.join(args.old, "timeline.json")
    new_p = args.new if os.path.isfile(args.new) else os.path.join(args.new, "timeline.json")

    old_timeline = pipeline.load_from_existing_audit(old_p)
    new_timeline = pipeline.load_from_existing_audit(new_p)
    gt_dataset = GroundTruthDataset.load_from_json(args.ground_truth)

    report = compare_shop_versions(old_timeline, new_timeline, gt_dataset)

    # Save Comparison Report
    os.makedirs(args.output, exist_ok=True)
    out_md = os.path.join(args.output, "shop_version_comparison.md")

    md = ["# ⚖️ Shop Recognition Architecture Comparison (OLD v1 vs NEW v2)\n"]
    md.append("## 1. Slot-by-Slot Accuracy Comparison\n")
    md.append("| Metric | OLD (ShopRecognizer v1) | NEW (ShopRecognizer v2) | Delta (pp) |")
    md.append("|---|---|---|---|")
    md.append(f"| **Overall Champion Accuracy** | `{report.old_metrics.overall_champion_accuracy:.1%}` | `{report.new_metrics.overall_champion_accuracy:.1%}` | **`{report.overall_accuracy_delta:+0.1%}`** |")
    md.append(f"| **Overall Cost Accuracy** | `{report.old_metrics.overall_cost_accuracy:.1%}` | `{report.new_metrics.overall_cost_accuracy:.1%}` | **`{report.cost_accuracy_delta:+0.1%}`** |")
    for s in range(1, 6):
        old_a = report.old_metrics.slot_accuracies.get(s, 0.0)
        new_a = report.new_metrics.slot_accuracies.get(s, 0.0)
        delta = report.slot_deltas.get(s, 0.0)
        md.append(f"| **Slot {s} Accuracy** | `{old_a:.1%}` | `{new_a:.1%}` | **`{delta:+0.1%}`** |")

    md.append("\n## 2. Action Event Extraction Comparison\n")
    md.append("| Action Metric | OLD v1 | NEW v2 | Delta |")
    md.append("|---|---|---|---|")
    md.append(f"| **ROLL Precision** | `{report.old_metrics.roll_metrics.precision:.1%}` | `{report.new_metrics.roll_metrics.precision:.1%}` | **`{report.new_metrics.roll_metrics.precision - report.old_metrics.roll_metrics.precision:+0.1%}`** |")
    md.append(f"| **ROLL Recall** | `{report.old_metrics.roll_metrics.recall:.1%}` | `{report.new_metrics.roll_metrics.recall:.1%}` | **`{report.new_metrics.roll_metrics.recall - report.old_metrics.roll_metrics.recall:+0.1%}`** |")
    md.append(f"| **ROLL F1 Score** | `{report.old_metrics.roll_metrics.f1:.3f}` | `{report.new_metrics.roll_metrics.f1:.3f}` | **`{report.roll_f1_delta:+0.3f}`** |")
    md.append(f"| **BUY Precision** | `{report.old_metrics.buy_metrics.precision:.1%}` | `{report.new_metrics.buy_metrics.precision:.1%}` | **`{report.new_metrics.buy_metrics.precision - report.old_metrics.buy_metrics.precision:+0.1%}`** |")
    md.append(f"| **BUY Recall** | `{report.old_metrics.buy_metrics.recall:.1%}` | `{report.new_metrics.buy_metrics.recall:.1%}` | **`{report.new_metrics.buy_metrics.recall - report.old_metrics.buy_metrics.recall:+0.1%}`** |")
    md.append(f"| **BUY F1 Score** | `{report.old_metrics.buy_metrics.f1:.3f}` | `{report.new_metrics.buy_metrics.f1:.3f}` | **`{report.buy_f1_delta:+0.3f}`** |")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print("\n" + "=" * 80)
    print("📊 COMPARISON SUMMARY (OLD v1 vs NEW v2)")
    print("=" * 80)
    print(f"  • Overall Champion Accuracy : {report.old_metrics.overall_champion_accuracy:.1%} -> {report.new_metrics.overall_champion_accuracy:.1%} ({report.overall_accuracy_delta:+0.1%})")
    print(f"  • Overall Cost Accuracy     : {report.old_metrics.overall_cost_accuracy:.1%} -> {report.new_metrics.overall_cost_accuracy:.1%} ({report.cost_accuracy_delta:+0.1%})")
    print(f"  • ROLL F1 Score             : {report.old_metrics.roll_metrics.f1:.3f} -> {report.new_metrics.roll_metrics.f1:.3f} ({report.roll_f1_delta:+0.3f})")
    print(f"  • BUY  F1 Score             : {report.old_metrics.buy_metrics.f1:.3f} -> {report.new_metrics.buy_metrics.f1:.3f} ({report.buy_f1_delta:+0.3f})")
    print("=" * 80)


if __name__ == "__main__":
    main()
