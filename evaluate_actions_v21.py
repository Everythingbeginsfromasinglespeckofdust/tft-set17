#!/usr/bin/env python3
"""Evaluate ActionEventDetector v2.1 predictions against Ground Truth annotations with Confusion Matrix."""
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

from tft.vision.events import ActionEvent, VisionActionType, ActionSource, QualityFlag
from tft.vision.ground_truth import GroundTruthDataset
from tft.vision.action_metrics_v21 import evaluate_action_events_v21
from tft.vision.action_debug import ActionDebugGallery


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate Action Event Predictions v2.1 against Ground Truth")
    parser.add_argument(
        "--predictions",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "action_v21", "predictions.jsonl"),
        help="Path to predictions.jsonl or predictions.json"
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
        default=os.path.join(_HERE, "data", "vision_audit", "action_v21", "reports"),
        help="Output directory for reports"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("🎯 TFT ACTION EVENT DETECTOR V2.1 -- GROUND TRUTH EVALUATION & CONFUSION MATRIX")
    print("=" * 80)

    # 1. Load Predictions
    events: list[ActionEvent] = []
    p_path = args.predictions
    if p_path.endswith(".jsonl"):
        with open(p_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                d = json.loads(line)
                events.append(ActionEvent(
                    action_type=VisionActionType(d["action_type"]),
                    source=ActionSource(d.get("source", "OBSERVED")),
                    timestamp_sec=d["timestamp_sec"],
                    confidence=d.get("confidence", 1.0),
                    evidence=d.get("evidence", []),
                    evidence_data=d.get("evidence_data", {}),
                    quality_flag=QualityFlag.VALID,
                    target_champion=d.get("target_champion"),
                    slot_index=d.get("slot_index"),
                    metadata=d.get("metadata", {})
                ))
    else:
        with open(p_path, "r", encoding="utf-8") as f:
            d = json.load(f)
            for ev in d.get("events", []):
                events.append(ActionEvent(
                    action_type=VisionActionType(ev["action_type"]),
                    source=ActionSource(ev.get("source", "OBSERVED")),
                    timestamp_sec=ev["timestamp_sec"],
                    confidence=ev.get("confidence", 1.0),
                    evidence=ev.get("evidence", []),
                    evidence_data=ev.get("evidence_data", {}),
                    quality_flag=QualityFlag.VALID,
                    target_champion=ev.get("target_champion"),
                    slot_index=ev.get("slot_index"),
                    metadata=ev.get("metadata", {})
                ))

    print(f"[*] Loaded Predictions: {len(events):,} total events from {p_path}")

    # 2. Load Ground Truth
    gt_dataset = GroundTruthDataset.load_from_json(args.ground_truth)
    print(f"[*] Loaded Ground Truth: {len(gt_dataset.events):,} events from {args.ground_truth}")

    # 3. Evaluate Metrics
    summary, fp_cases, fn_cases = evaluate_action_events_v21(events, gt_dataset, tolerance_sec=1.0, version_name="ActionEventDetectorV21")

    # 4. Save Debug Gallery
    os.makedirs(args.output, exist_ok=True)
    gallery = ActionDebugGallery(output_dir=os.path.join(args.output, "debug_gallery"))
    for c in fp_cases:
        gallery.add_case(
            case_type="FALSE_POSITIVE",
            timestamp_sec=c["timestamp_sec"],
            predicted_action=c.get("predicted_action"),
            ground_truth_action=c.get("ground_truth_action"),
            confidence=c.get("confidence"),
            evidence=c.get("evidence", []),
            reason=c.get("reason", "False Positive")
        )
    for c in fn_cases:
        gallery.add_case(
            case_type="FALSE_NEGATIVE",
            timestamp_sec=c["timestamp_sec"],
            predicted_action=None,
            ground_truth_action=c.get("ground_truth_action"),
            confidence=None,
            evidence=c.get("evidence_observed", []),
            reason=c.get("reason", "False Negative")
        )
    gallery.save_gallery()

    # 5. Save Summary JSON & Markdown
    out_json = os.path.join(args.output, "action_v21_metrics.json")
    out_md = os.path.join(args.output, "action_v21_report.md")

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary.to_dict(), f, indent=2, ensure_ascii=False)

    md = ["# 🎯 TFT Action Event Detection v2.1 Evaluation Report\n"]
    md.append(f"- **Evaluated Model**: `{summary.version_name}`")
    md.append(f"- **Total Predicted Actions**: `{summary.total_predicted_events}`")
    md.append(f"- **Total System Free Refreshes Isolated**: `{summary.system_refresh_count}`")
    md.append(f"- **Total Ground Truth Target Actions**: `{summary.total_ground_truth_events}`\n")

    md.append("## 1. Action-by-Action Classification Performance\n")
    md.append("| Action Type | Precision | Recall | F1 Score | TP | FP | FN |")
    md.append("|---|---|---|---|---|---|---|")
    md.append(f"| **PLAYER_ROLL** | `{summary.player_roll_metrics.precision:.1%}` | `{summary.player_roll_metrics.recall:.1%}` | **`{summary.player_roll_metrics.f1:.3f}`** | {summary.player_roll_metrics.tp} | {summary.player_roll_metrics.fp} | {summary.player_roll_metrics.fn} |")
    md.append(f"| **BUY_UNIT** | `{summary.buy_unit_metrics.precision:.1%}` | `{summary.buy_unit_metrics.recall:.1%}` | **`{summary.buy_unit_metrics.f1:.3f}`** | {summary.buy_unit_metrics.tp} | {summary.buy_unit_metrics.fp} | {summary.buy_unit_metrics.fn} |")
    md.append(f"| **LEVEL_UP** | `{summary.level_up_metrics.precision:.1%}` | `{summary.level_up_metrics.recall:.1%}` | **`{summary.level_up_metrics.f1:.3f}`** | {summary.level_up_metrics.tp} | {summary.level_up_metrics.fp} | {summary.level_up_metrics.fn} |")

    md.append("\n## 2. 6x6 Confusion Matrix (Ground Truth vs Prediction)\n")
    md.append("| Ground Truth \\ Prediction | ROLL | BUY_UNIT | LEVEL_UP | NO_ACTION | SYSTEM_REFRESH | UNKNOWN |")
    md.append("|---|---|---|---|---|---|---|")
    for gt_k in ["ROLL", "BUY_UNIT", "LEVEL_UP", "NO_ACTION"]:
        row = summary.confusion_matrix.get(gt_k, {})
        md.append(f"| **{gt_k}** | {row.get('ROLL', 0)} | {row.get('BUY_UNIT', 0)} | {row.get('LEVEL_UP', 0)} | {row.get('NO_ACTION', 0)} | {row.get('SYSTEM_REFRESH', 0)} | {row.get('UNKNOWN', 0)} |")

    md.append("\n## 3. Timing Error Distribution\n")
    t_mae = summary.timing_metrics.mae or 0.0
    t_med = summary.timing_metrics.median or 0.0
    t_p95 = summary.timing_metrics.p95 or 0.0
    md.append(f"- **MAE**: `{t_mae:.3f}s` | **Median**: `{t_med:.3f}s` | **P95**: `{t_p95:.3f}s` | **Max Error**: `{summary.timing_metrics.max_error or 0.0:.3f}s`\n")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print("\n" + "=" * 80)
    print("📈 EVALUATION RESULTS (v2.1)")
    print("=" * 80)
    print(f"  • PLAYER_ROLL Precision / Recall / F1: {summary.player_roll_metrics.precision:.1%} / {summary.player_roll_metrics.recall:.1%} / {summary.player_roll_metrics.f1:.3f}")
    print(f"  • BUY_UNIT   Precision / Recall / F1: {summary.buy_unit_metrics.precision:.1%} / {summary.buy_unit_metrics.recall:.1%} / {summary.buy_unit_metrics.f1:.3f}")
    print(f"  • System Free Refreshes Isolated    : {summary.system_refresh_count}")
    print(f"  • Timing MAE / Median / P95         : {t_mae:.3f}s / {t_med:.3f}s / {t_p95:.3f}s")
    print(f"  • False Positives / False Negatives: {summary.false_positives_count} / {summary.false_negatives_count}")
    print("=" * 80)


if __name__ == "__main__":
    main()
