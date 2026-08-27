#!/usr/bin/env python3
"""Run Adaptive Action Resampling Pipeline on a single designated session."""
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
from tft.vision.adaptive_action_pipeline import AdaptiveActionPipeline
from tft.vision.refinement_metrics import AdaptiveMetricsEvaluator


def parse_args():
    parser = argparse.ArgumentParser(description="Run Adaptive Pipeline for Single Session")
    parser.add_argument("--session", type=str, default="SESSION_A", help="Session ID (e.g. SESSION_A)")
    parser.add_argument("--manifest", type=str, default=os.path.join(_HERE, "data", "backtest", "pilot", "pilot_manifest.json"))
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--annotations", type=str, default=os.path.join(_HERE, "data", "vision_audit", "annotations"))
    return parser.parse_args()


def main():
    args = parse_args()
    manifest = PilotManifest.load_from_json(args.manifest)
    session = manifest.get_session(args.session)
    if not session:
        print(f"[!] Session {args.session} not found in manifest.")
        return

    out_dir = args.output or os.path.join(_HERE, "data", "backtest", "pilot", "adaptive", args.session)
    pipeline = AdaptiveActionPipeline()
    det_summary = pipeline.process_session(session, out_dir)

    gt_path = os.path.join(args.annotations, f"gt_{args.session.lower()}.json")
    if not os.path.exists(gt_path):
        gt_path = os.path.join(args.annotations, "gt_session_01.json")

    evaluator = AdaptiveMetricsEvaluator()
    report = evaluator.evaluate_session(
        session_id=args.session,
        adaptive_preds_path=os.path.join(out_dir, "predictions.jsonl"),
        gt_path=gt_path,
        det_summary=det_summary
    )

    print("\n" + "=" * 80)
    print(f"📈 SESSION {args.session} ADAPTIVE RESAMPLING RESULTS")
    print("=" * 80)
    print(f"  • ROLL F1: {report.adaptive_roll_f1:.3f} (Precision: {report.adaptive_roll_precision:.1%}, Recall: {report.adaptive_roll_recall:.1%})")
    print(f"  • BUY  F1: {report.adaptive_buy_f1:.3f} (Precision: {report.adaptive_buy_precision:.1%}, Recall: {report.adaptive_buy_recall:.1%})")
    print(f"  • FP Count: {report.adaptive_fp} (Reduced by {report.fp_reduction})")
    print(f"  • Refinement Ratio: {report.refinement_ratio:.1%}")
    print("=" * 80)


if __name__ == "__main__":
    main()
