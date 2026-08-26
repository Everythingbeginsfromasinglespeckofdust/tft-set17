#!/usr/bin/env python3
"""Execute full batch Action Causality Audit across Ground Truth events and raw MP4 video."""
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


def parse_args():
    parser = argparse.ArgumentParser(description="TFT Action Causality Audit Batch CLI")
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
        "--output",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "causal_audit"),
        help="Output directory for audit report and galleries"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("🔬 TFT ACTION CAUSALITY AUDIT V1 -- FRAME-LEVEL DYNAMICS ANALYZER")
    print("=" * 80)

    gt = GroundTruthDataset.load_from_json(args.ground_truth)
    print(f"[*] Loaded Ground Truth: {len(gt.events):,} events from {args.ground_truth}")
    print(f"[*] Analyzing Raw MP4: {args.video}")

    analyzer = ActionCausalAnalyzer()
    report = analyzer.run_full_causal_audit(
        video_path=args.video,
        ground_truth=gt,
        output_gallery_dir=args.output
    )

    os.makedirs(args.output, exist_ok=True)
    out_json = os.path.join(args.output, "reports", "causal_audit_report.json")
    out_md = os.path.join(args.output, "reports", "causal_audit_report.md")
    os.makedirs(os.path.dirname(out_json), exist_ok=True)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

    md = ["# 🔬 TFT Action Causality Audit v1 Report\n"]
    md.append("## 1. Analyzed Event Population\n")
    md.append(f"- **ROLL Events Analyzed**: `{report.total_roll_events_analyzed}`")
    md.append(f"- **BUY_UNIT Events Analyzed**: `{report.total_buy_events_analyzed}`")
    md.append(f"- **NO_ACTION Windows Analyzed**: `{report.total_no_action_windows_analyzed}`")
    md.append(f"- **SYSTEM_REFRESH Events Analyzed**: `{report.total_system_refresh_events_analyzed}`\n")

    md.append("## 2. ROLL Causal Dynamics & Questions\n")
    md.append(f"- **Shop Onset Latency**: Mean `{report.roll_shop_onset_mean_sec:.3f}s` | Median `{report.roll_shop_onset_median_sec:.3f}s` | P95 `{report.roll_shop_onset_p95_sec:.3f}s`")
    md.append(f"- **Same-Champion Collisions (<3 slots changed)**: `{report.roll_same_champion_collision_count}` / {report.total_roll_events_analyzed} (`{report.roll_same_champion_collision_rate:.1%}`)")
    md.append("\n### Rapid Reroll Interval Distribution:\n")
    md.append("| Inter-Reroll Interval | Count | Percentage |")
    md.append("|---|---|---|")
    total_intervals = sum(report.rapid_reroll_interval_distribution.values())
    for k, v in report.rapid_reroll_interval_distribution.items():
        pct = (v / total_intervals * 100) if total_intervals > 0 else 0
        md.append(f"| `{k}` | {v} | {pct:.1f}% |")

    md.append("\n## 3. Discovered Causal Signatures & Specificity\n")
    md.append("| Signature ID | Action | Name | Support Rate | NO_ACTION Specificity | Likelihood Ratio | Safe Standalone? |")
    md.append("|---|---|---|---|---|---|---|")
    for s in report.roll_signatures:
        md.append(f"| `{s.signature_id}` | `{s.action_type}` | {s.name} | `{s.support_rate:.1%}` ({s.support_count}/{s.total_action_count}) | `{s.specificity:.1%}` | `{s.likelihood_ratio:.1f}x` | {'✅' if s.is_safe_for_standalone_detector else '❌ (Requires Conjunction)'} |")
    for s in report.buy_signatures:
        md.append(f"| `{s.signature_id}` | `{s.action_type}` | {s.name} | `{s.support_rate:.1%}` ({s.support_count}/{s.total_action_count}) | `{s.specificity:.1%}` | `{s.likelihood_ratio:.1f}x` | {'✅' if s.is_safe_for_standalone_detector else '❌ (Requires Conjunction)'} |")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print("\n" + "=" * 80)
    print("📈 CAUSALITY AUDIT SUMMARY")
    print("=" * 80)
    print(f"  • Analyzed Events: {report.total_roll_events_analyzed} ROLL, {report.total_buy_events_analyzed} BUY, {report.total_no_action_windows_analyzed} NO_ACTION")
    print(f"  • ROLL Shop Onset Median: {report.roll_shop_onset_median_sec:.3f}s | Same-Champion Collisions: {report.roll_same_champion_collision_rate:.1%}")
    print(f"  • Rapid Rerolls (<1.0s): {sum(v for k,v in report.rapid_reroll_interval_distribution.items() if k != '>1.00s')} events")
    print(f"  • Report Saved to: {out_md}")
    print("=" * 80)


if __name__ == "__main__":
    main()
