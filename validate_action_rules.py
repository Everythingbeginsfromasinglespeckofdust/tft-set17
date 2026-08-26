#!/usr/bin/env python3
"""Validate empirical Action Rule Candidates against Ground Truth and Causal Traces."""
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

from tft.vision.ground_truth import GroundTruthDataset
from tft.vision.causal_analyzer import ActionCausalAnalyzer
from tft.vision.causal_models import EventCausalTrace
from tft.vision.action_rule_validation import ActionRuleValidator


def parse_args():
    parser = argparse.ArgumentParser(description="TFT Action Rule Validation CLI")
    parser.add_argument(
        "--video",
        type=str,
        default=r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4",
        help="Path to raw MP4 video file"
    )
    parser.add_argument(
        "--ground-truth",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "annotations", "gt_session_01.json"),
        help="Path to gt_session_01.json"
    )
    parser.add_argument(
        "--causal-report",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "causal_audit", "reports", "causal_audit_report.json"),
        help="Path to causal_audit_report.json"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "rule_validation"),
        help="Output directory for rule validation results"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("🔬 TFT ACTION RULE VALIDATION V1 -- CANDIDATE REPLAY & EVALUATOR")
    print("=" * 80)

    gt = GroundTruthDataset.load_from_json(args.ground_truth)
    print(f"[*] Loaded Ground Truth: {len(gt.events):,} events from {args.ground_truth}")

    # 1. Load or Generate Causal Traces
    traces = []
    if os.path.exists(args.causal_report):
        print(f"[*] Loading pre-extracted traces from {args.causal_report}...")
        with open(args.causal_report, "r", encoding="utf-8") as f:
            cdata = json.load(f)
        for tr_dict in cdata.get("traces", []):
            tr = EventCausalTrace(
                event_id=tr_dict.get("event_id", ""),
                event_type=tr_dict.get("event_type", ""),
                target_champion=tr_dict.get("target_champion"),
                gt_timestamp_sec=tr_dict.get("gt_timestamp_sec", 0.0),
                window_start_sec=tr_dict.get("window_start_sec", 0.0),
                window_end_sec=tr_dict.get("window_end_sec", 0.0),
                sequence_pattern=tr_dict.get("sequence_pattern", "STABLE"),
                dt_gold_onset=tr_dict.get("dt_gold_onset"),
                dt_shop_onset=tr_dict.get("dt_shop_onset"),
                dt_board_onset=tr_dict.get("dt_board_onset"),
                dt_bench_onset=tr_dict.get("dt_bench_onset"),
                shop_slots_changed=tr_dict.get("shop_slots_changed", 0),
                is_same_champion_collision=tr_dict.get("is_same_champion_collision", False),
                is_rapid_reroll=tr_dict.get("is_rapid_reroll", False),
                inter_reroll_interval_sec=tr_dict.get("inter_reroll_interval_sec"),
                is_ambiguous=tr_dict.get("is_ambiguous", False),
                ambiguity_reason=tr_dict.get("ambiguity_reason", "")
            )
            traces.append(tr)
    else:
        print("[*] Running Causal Extractor / Analyzer...")
        analyzer = ActionCausalAnalyzer()
        causal_report = analyzer.run_full_causal_audit(video_path=args.video, ground_truth=gt)
        traces = causal_report.event_traces

    print(f"[*] Loaded {len(traces)} frame-level causal traces")

    # 2. Validate Candidate Rules
    validator = ActionRuleValidator()
    rule_metrics, cov_matrix, conflicts = validator.validate_rules(traces, gt)

    # 3. Export Artifacts
    os.makedirs(args.output, exist_ok=True)
    rep_dir = os.path.join(args.output, "reports")
    os.makedirs(rep_dir, exist_ok=True)

    out_results = os.path.join(args.output, "rule_results.json")
    out_cov = os.path.join(args.output, "coverage_matrix.json")
    out_conflicts = os.path.join(args.output, "conflict_cases.json")
    out_md = os.path.join(rep_dir, "rule_validation_report.md")

    with open(out_results, "w", encoding="utf-8") as f:
        json.dump({k: v.to_dict() for k, v in rule_metrics.items()}, f, indent=2, ensure_ascii=False)

    with open(out_cov, "w", encoding="utf-8") as f:
        json.dump(cov_matrix, f, indent=2, ensure_ascii=False)

    with open(out_conflicts, "w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in conflicts], f, indent=2, ensure_ascii=False)

    # Build Markdown Report
    md = ["# 🔬 TFT Action Rule Validation v1 Report\n"]
    md.append("## 1. Candidate Rule Performance Summary\n")
    md.append("| Rule Name | Action | Description | TP | FP | FN | Precision | Recall (Coverage) | F1 | Specificity | Likelihood Ratio | Laplace LR (α=1.0) |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r_name, m in rule_metrics.items():
        lr_str = f"{m.likelihood_ratio:.2f}x" if m.likelihood_ratio is not None and m.likelihood_ratio != float("inf") else ("∞" if m.likelihood_ratio == float("inf") else "Undefined")
        md.append(f"| **`{m.rule_name}`** | `{m.target_action_type}` | {m.description} | {m.tp} | {m.fp} | {m.fn} | `{m.precision:.1%}` | `{m.recall:.1%}` | **`{m.f1:.3f}`** | `{m.specificity:.1%}` | `{lr_str}` | `{m.laplace_smoothed_lr:.2f}x` |")

    md.append("\n## 2. Same-Champion Collision Breakdown\n")
    collision_count = sum(1 for t in traces if t.is_same_champion_collision)
    total_rolls = sum(1 for t in traces if t.event_type == "ROLL")
    md.append(f"- **Total Collision ROLL Events**: `{collision_count}` / {total_rolls} (`{collision_count/max(1, total_rolls):.1%}`)")
    md.append("- **Impact on Rule Candidates**:")
    md.append(f"  • `ROLL_A` (requires shop >= 1 & board/bench unchanged): TP={rule_metrics['ROLL_A'].tp}, FN={rule_metrics['ROLL_A'].fn}")
    md.append(f"  • `ROLL_D` (collision-aware shop transition): TP={rule_metrics['ROLL_D'].tp}, FN={rule_metrics['ROLL_D'].fn}\n")

    md.append("## 3. Rule Conflicts Summary\n")
    md.append(f"- **Total Multi-Rule Conflict Events**: `{len(conflicts)}`\n")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print("\n" + "=" * 80)
    print("📈 RULE VALIDATION SUMMARY")
    print("=" * 80)
    for r_name in ["ROLL_A", "ROLL_B", "ROLL_C", "ROLL_D", "BUY_A", "BUY_B", "BUY_C"]:
        m = rule_metrics[r_name]
        print(f"  • {m.rule_name:<8} ({m.target_action_type:<8}) -> Precision: {m.precision:.1%}, Recall: {m.recall:.1%}, F1: {m.f1:.3f}, Likelihood Ratio: {m.laplace_smoothed_lr:.2f}x")
    print("=" * 80)
    print(f"[*] Saved Report to: {out_md}")
    print("=" * 80)


if __name__ == "__main__":
    main()
