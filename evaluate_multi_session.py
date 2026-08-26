#!/usr/bin/env python3
"""Evaluate all multi-session pilot predictions against Ground Truth."""
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

from tft.vision.pilot_models import PilotManifest
from tft.vision.pilot_evaluator import MultiSessionEvaluator


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate Multi-Session Pilot")
    parser.add_argument(
        "--manifest",
        type=str,
        default=os.path.join(_HERE, "data", "backtest", "pilot", "pilot_manifest.json")
    )
    parser.add_argument(
        "--input",
        type=str,
        default=os.path.join(_HERE, "data", "backtest", "pilot"),
        help="Input base directory containing sessions"
    )
    parser.add_argument(
        "--annotations",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "annotations"),
        help="Directory containing ground truth JSON files"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(_HERE, "data", "backtest", "pilot", "reports"),
        help="Output directory for reports"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("🔬 TFT MULTI-SESSION PILOT V1 -- EVALUATION & ACCEPTANCE GATE")
    print("=" * 80)

    if not os.path.exists(args.manifest):
        print(f"[!] Manifest not found at {args.manifest}")
        return

    manifest = PilotManifest.load_from_json(args.manifest)
    evaluator = MultiSessionEvaluator()
    summary = evaluator.evaluate_manifest(
        manifest=manifest,
        output_base_dir=args.input,
        annotations_dir=args.annotations
    )

    os.makedirs(args.output, exist_ok=True)
    md_path = os.path.join(args.output, "multi_session_comparison.md")

    md = ["# 🌐 TFT Multi-Session Pilot v1 — Comprehensive Cross-Session Benchmark\n"]
    md.append(f"**Gate Verdict**: **`{summary.gate_verdict.value}`**\n")
    md.append("| Session | Video Match | Placement | Archetype | ROLL F1 (P/R) | BUY F1 (P/R) | Total FP | Raw Gold Valid | Carried Forward |")
    md.append("|---|---|---|---|---|---|---|---|---|")

    for sid in summary.sessions_evaluated:
        s_metric_path = os.path.join(args.input, "sessions", sid, "session_metrics.json")
        sess_obj = manifest.get_session(sid)
        arch = sess_obj.economic_archetype.value if sess_obj else "UNKNOWN"
        place = sess_obj.final_placement if sess_obj else "?"
        mid = sess_obj.match_id if sess_obj else "?"

        if os.path.exists(s_metric_path):
            with open(s_metric_path, "r", encoding="utf-8") as sf:
                sm = json.load(sf)
            r_f1 = sm["actions"]["ROLL"]["f1"]
            r_p = sm["actions"]["ROLL"]["precision"]
            r_r = sm["actions"]["ROLL"]["recall"]
            b_f1 = sm["actions"]["BUY_UNIT"]["f1"]
            b_p = sm["actions"]["BUY_UNIT"]["precision"]
            b_r = sm["actions"]["BUY_UNIT"]["recall"]
            fp = sm["counts"]["total_fp"]
            raw_g = sm["gold"]["raw_ocr_valid_rate"]
            carr_g = sm["gold"]["carried_forward_rate"]
            md.append(f"| **`{sid}`** | `{mid}` | `{place}th` | `{arch}` | **`{r_f1:.3f}`** (`{r_p:.1%}`/`{r_r:.1%}`) | **`{b_f1:.3f}`** (`{b_p:.1%}`/`{b_r:.1%}`) | `{fp}` | `{raw_g:.1%}` | `{carr_g:.1%}` |")

    md.append("\n## 2. Cross-Session Statistical Summary\n")
    md.append("| Metric | Mean | Median | Min | Max | Std Dev |")
    md.append("|---|---|---|---|---|---|")
    md.append(f"| **ROLL F1** | `{summary.roll_f1_mean:.3f}` | `{summary.roll_f1_median:.3f}` | `{summary.roll_f1_min:.3f}` | `{summary.roll_f1_max:.3f}` | `{summary.roll_f1_std:.3f}` |")
    md.append(f"| **BUY F1** | `{summary.buy_f1_mean:.3f}` | `{summary.buy_f1_median:.3f}` | `{summary.buy_f1_min:.3f}` | `{summary.buy_f1_max:.3f}` | `{summary.buy_f1_std:.3f}` |")
    md.append(f"| **Gold Raw OCR Valid** | `{summary.gold_raw_ocr_valid_mean:.1%}` | - | - | - | - |")
    md.append(f"| **Gold Stabilized Acc** | `{summary.gold_stabilized_acc_mean:.1%}` | - | - | - | - |")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print("\n" + "=" * 80)
    print(f"🏁 EVALUATION SUMMARY (Gate: {summary.gate_verdict.value})")
    print("=" * 80)
    print(f"  • Sessions Evaluated : {len(summary.sessions_evaluated)}")
    print(f"  • Pooled ROLL F1     : {summary.pooled_roll_f1:.3f} (Mean: {summary.roll_f1_mean:.3f}, Std: {summary.roll_f1_std:.3f})")
    print(f"  • Pooled BUY F1      : {summary.pooled_buy_f1:.3f} (Mean: {summary.buy_f1_mean:.3f}, Std: {summary.buy_f1_std:.3f})")
    print(f"  • Total FP Count     : {summary.pooled_fp_count}")
    print(f"[*] Saved Report to    : {md_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
