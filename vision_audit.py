#!/usr/bin/env python3
"""TFT Vision Ground Truth Audit CLI Tool (v1.0).

Usage:
    python vision_audit.py --timeline output/video_analysis/10min_audit/shop_timeline.json --annotations data/vision_audit/annotations/gt_session_01.json --output data/vision_audit/reports
"""
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
from tft.vision.audit import VisionAuditor
from tft.vision.audit_report import AuditReportGenerator


def parse_args():
    parser = argparse.ArgumentParser(description="TFT Vision Ground Truth Audit & Fidelity Validation CLI")
    parser.add_argument(
        "--video",
        type=str,
        default=None,
        help="Path to .mp4 video file (optional if --timeline provided)"
    )
    parser.add_argument(
        "--timeline",
        type=str,
        default=os.path.join(_HERE, "output", "video_analysis", "10min_audit", "shop_timeline.json"),
        help="Path to shop_timeline.json or timeline.json"
    )
    parser.add_argument(
        "--annotations",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "annotations", "gt_session_01.json"),
        help="Path to ground truth annotations JSON"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(_HERE, "data", "vision_audit", "reports"),
        help="Directory to save audit reports and diagnostic plots"
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1.0,
        help="Action event timestamp matching tolerance in seconds (default: 1.0s)"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        default=False,
        help="Re-generate report and plots from existing audit result"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("🔍 TFT VISION GROUND TRUTH AUDIT & FIDELITY VALIDATION (v1.0)")
    print("=" * 80)

    # 1. Load Timeline
    pipeline = VisionPipeline()
    if args.video and os.path.exists(args.video):
        print(f"[*] Processing video frames with VisionPipeline: {args.video}")
        timeline = pipeline.process_video(args.video, interval_sec=0.5)
    elif args.timeline and os.path.exists(args.timeline):
        print(f"[*] Loading ObservationTimeline from: {args.timeline}")
        timeline = pipeline.load_from_existing_audit(args.timeline)
    else:
        print(f"[!] Neither video nor timeline found. Please check paths.")
        return

    print(f"    Loaded {len(timeline.observations):,} observations, {len(timeline.events):,} CV action events.")

    # 2. Load Ground Truth Dataset
    if not os.path.exists(args.annotations):
        print(f"[!] Ground Truth annotations file not found: {args.annotations}")
        return

    print(f"[*] Loading Ground Truth Dataset from: {args.annotations}")
    gt_dataset = GroundTruthDataset.load_from_json(args.annotations)
    print(f"    Loaded {len(gt_dataset.events):,} Ground Truth Events, {len(gt_dataset.observations):,} Ground Truth Observation checkpoints.")

    # 3. Execute Audit
    print(f"\n[*] Executing VisionAuditor (Timestamp tolerance: ±{args.tolerance:.1f}s)...")
    auditor = VisionAuditor(time_tolerance_sec=args.tolerance)
    result = auditor.audit(timeline, gt_dataset)

    # 4. Save Artifacts & Reports
    os.makedirs(args.output, exist_ok=True)
    json_path = os.path.join(args.output, "vision_audit_report.json")
    md_path = os.path.join(args.output, "vision_audit_report.md")

    AuditReportGenerator.save_json(result, json_path)
    AuditReportGenerator.save_markdown(result, md_path)
    print(f"[*] Saved JSON Report: {json_path}")
    print(f"[*] Saved Markdown Report: {md_path}")

    # 5. Generate 5 Diagnostic Plots
    plot_paths = AuditReportGenerator.generate_audit_plots(result, timeline, gt_dataset, args.output)
    print(f"[*] Generated {len(plot_paths)} diagnostic visualization charts in: {args.output}")

    # 6. Display Summary to Terminal
    print("\n" + "=" * 80)
    print("📊 AUDIT & FIDELITY SUMMARY")
    print("=" * 80)
    print(f"  • DATASET_READINESS Verdict  : {result.readiness_status.value}")
    print(f"  • Session Independence       : 1 Session, 1 Participant (Non-independent game context)")
    print(f"  • Action Precision / Recall / F1:")
    for act_name, m in result.action_metrics.items():
        print(f"      - {act_name:<10}: Precision={m.precision:<6.1%} | Recall={m.recall:<6.1%} | F1={m.f1:.3f}")
    sg = result.save_gold_inference_metrics
    print(f"      - {'SAVE_GOLD':<10}: Precision={sg.precision:<6.1%} | Recall={sg.recall:<6.1%} | F1={sg.f1:.3f} (INFERRED vs NO_ACTION)")
    print(f"  • Timing MAE                 : {result.timing_metrics.mae if result.timing_metrics.mae is not None else 0.0:.3f}s (P95: {result.timing_metrics.p95 if result.timing_metrics.p95 is not None else 0.0:.3f}s)")
    print(f"  • Gold OCR MAE               : {result.gold_metrics.mae if result.gold_metrics.mae is not None else 0.0:.2f}G (Exact Acc: {result.gold_metrics.exact_accuracy:.1%})")
    print(f"  • Overall Shop Accuracy      : {result.overall_shop_accuracy:.1%}")
    if result.human_agreement:
        print(f"  • Inter-Annotator Kappa (κ)  : {result.human_agreement.cohens_kappa:.3f} (Agreement: {result.human_agreement.raw_agreement_rate:.1%})")
    print("=" * 80)


if __name__ == "__main__":
    main()
