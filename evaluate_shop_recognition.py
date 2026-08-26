#!/usr/bin/env python3
"""Evaluate a shop timeline against Ground Truth annotations."""
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
from tft.vision.shop_metrics import evaluate_shop_timeline_against_gt


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate Shop Recognition Timeline against Ground Truth")
    parser.add_argument(
        "--timeline",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "new_shop_timeline", "timeline.json"),
        help="Path to timeline.json or directory containing timeline.json"
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
        default=os.path.join(_HERE, "data", "vision_audit", "reports", "shop_v2"),
        help="Directory to save evaluation report"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("📊 TFT SHOP RECOGNITION V2 -- INDEPENDENT GROUND TRUTH EVALUATION")
    print("=" * 80)

    # 1. Load Timeline
    pipeline = VisionPipeline()
    t_path = args.timeline
    if os.path.isdir(t_path):
        t_path = os.path.join(t_path, "timeline.json")

    timeline = pipeline.load_from_existing_audit(t_path)
    print(f"[*] Loaded Timeline from: {t_path} ({len(timeline.observations):,} observations, {len(timeline.events):,} events)")

    # 2. Load Ground Truth
    gt_dataset = GroundTruthDataset.load_from_json(args.ground_truth)
    print(f"[*] Loaded Ground Truth from: {args.ground_truth} ({len(gt_dataset.observations):,} checkpoints, {len(gt_dataset.events):,} events)")

    # 3. Evaluate Metrics
    m = evaluate_shop_timeline_against_gt(timeline, gt_dataset, version_name="ShopRecognizerV2")

    # 4. Save Markdown & JSON Report
    os.makedirs(args.output, exist_ok=True)
    report_json_path = os.path.join(args.output, "shop_v2_metrics.json")
    report_md_path = os.path.join(args.output, "shop_v2_report.md")

    report_data = {
        "version": m.version_name,
        "total_slots_evaluated": m.total_slots,
        "overall_champion_accuracy": m.overall_champion_accuracy,
        "overall_cost_accuracy": m.overall_cost_accuracy,
        "slot_accuracies": m.slot_accuracies,
        "unknown_rate": m.unknown_rate,
        "missing_rate": m.missing_rate,
        "roll_precision": m.roll_metrics.precision,
        "roll_recall": m.roll_metrics.recall,
        "roll_f1": m.roll_metrics.f1,
        "buy_precision": m.buy_metrics.precision,
        "buy_recall": m.buy_metrics.recall,
        "buy_f1": m.buy_metrics.f1,
        "timing_mae_sec": m.timing_metrics.mae
    }

    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    md = ["# 🛒 Shop Recognition v2 Independent Evaluation Report\n"]
    md.append(f"- **Evaluated Version**: `{m.version_name}`")
    md.append(f"- **Total Evaluated Slots**: `{m.total_slots}`")
    md.append(f"- **Overall Champion Accuracy**: `{m.overall_champion_accuracy:.1%}`")
    md.append(f"- **Overall Cost Accuracy**: `{m.overall_cost_accuracy:.1%}`")
    md.append(f"- **Unknown / Low Confidence Rate**: `{m.unknown_rate:.1%}`\n")
    md.append("### Slot-by-Slot Accuracy\n")
    md.append("| Slot | Accuracy |")
    md.append("|---|---|")
    for s in range(1, 6):
        md.append(f"| **Slot {s}** | `{m.slot_accuracies.get(s, 0.0):.1%}` |")
    md.append("\n### Action Event Extraction Performance\n")
    md.append(f"- **ROLL F1**: `{m.roll_metrics.f1:.3f}` (Precision: `{m.roll_metrics.precision:.1%}`, Recall: `{m.roll_metrics.recall:.1%}`)")
    md.append(f"- **BUY_UNIT F1**: `{m.buy_metrics.f1:.3f}` (Precision: `{m.buy_metrics.precision:.1%}`, Recall: `{m.buy_metrics.recall:.1%}`)")
    t_mae = m.timing_metrics.mae or 0.0
    md.append(f"- **Timing MAE**: `{t_mae:.3f}s`\n")

    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print("\n" + "=" * 80)
    print("📈 EVALUATION RESULTS")
    print("=" * 80)
    print(f"  • Overall Shop Accuracy      : {m.overall_champion_accuracy:.1%}")
    print(f"  • Overall Cost Accuracy      : {m.overall_cost_accuracy:.1%}")
    for s in range(1, 6):
        print(f"      - Slot {s:<22}: {m.slot_accuracies.get(s, 0.0):.1%}")
    print(f"  • ROLL Precision / Recall / F1: {m.roll_metrics.precision:.1%} / {m.roll_metrics.recall:.1%} / {m.roll_metrics.f1:.3f}")
    print(f"  • BUY  Precision / Recall / F1: {m.buy_metrics.precision:.1%} / {m.buy_metrics.recall:.1%} / {m.buy_metrics.f1:.3f}")
    print(f"  • Timing MAE                 : {t_mae:.3f}s")
    print("=" * 80)


if __name__ == "__main__":
    main()
