#!/usr/bin/env python3
"""TFT Decision Engine Backtesting CLI Tool -- v1.1.

Usage:
    python backtest.py --limit 500 --output data/backtest/reports
    python backtest.py --snapshot-type midgame --output data/backtest/reports
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from tft.backtest.models import SnapshotType
from tft.backtest.dataset import BacktestDataset
from tft.backtest.runner import BacktestRunner
from tft.backtest.evaluator import BacktestEvaluator
from tft.backtest.reporting import ReportGenerator


def parse_args():
    parser = argparse.ArgumentParser(description="TFT Decision Engine Backtesting Framework CLI (v1.1)")
    parser.add_argument(
        "--input",
        type=str,
        default=os.path.join(_HERE, "output", "data", "match_snapshots.jsonl"),
        help="Path to match snapshots JSONL"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(_HERE, "data", "backtest", "reports"),
        help="Directory to save output reports"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Sample limit for match snapshots (0 for all)"
    )
    parser.add_argument(
        "--video",
        action="store_true",
        default=True,
        help="Include historical video audit samples"
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        default=False,
        help="Include synthetic validation samples"
    )
    parser.add_argument(
        "--snapshot-type",
        type=str,
        default="all",
        choices=["all", "midgame", "endgame"],
        help="Filter evaluation to specific snapshot type"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic reproducibility"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("🎮 TFT DECISION ENGINE -- BACKTESTING & STATISTICAL VALIDITY (v1.1)")
    print("=" * 80)

    # 1. Load Samples
    samples = []
    limit_val = args.limit if args.limit > 0 else None

    if os.path.exists(args.input):
        print(f"[*] Loading historical match snapshots from: {args.input}")
        match_samples = BacktestDataset.load_from_match_snapshots(args.input, limit=limit_val)
        samples.extend(match_samples)
        print(f"    Loaded {len(match_samples):,} ENDGAME snapshots.")

    if args.video:
        video_path = os.path.join(_HERE, "output", "video_analysis", "10min_audit", "shop_timeline.json")
        if os.path.exists(video_path):
            video_samples = BacktestDataset.load_from_video_audit(video_path)
            samples.extend(video_samples)
            print(f"    Loaded {len(video_samples):,} MIDGAME video snapshots (with observed actions).")

    if args.synthetic:
        synth_samples = BacktestDataset.create_synthetic_dataset(num_samples=50, seed=args.seed)
        samples.extend(synth_samples)
        print(f"    Loaded {len(synth_samples):,} synthetic validation samples.")

    # Filter by snapshot type if requested
    if args.snapshot_type == "midgame":
        samples = [s for s in samples if s.snapshot_type == SnapshotType.MIDGAME_DECISION_SNAPSHOT]
        print(f"[*] Filtered to MIDGAME snapshots only: {len(samples):,} samples")
    elif args.snapshot_type == "endgame":
        samples = [s for s in samples if s.snapshot_type == SnapshotType.ENDGAME_SNAPSHOT]
        print(f"[*] Filtered to ENDGAME snapshots only: {len(samples):,} samples")

    print(f"[*] Total Validated Samples for Evaluation: {len(samples):,}")
    if not samples:
        print("[!] No samples loaded. Exiting.")
        return

    # 2. Match-Level Split Check
    train_samples, test_samples = BacktestDataset.split_by_match(samples, train_ratio=0.8, seed=args.seed)
    print(f"[*] Match-Level Group Split: Train={len(train_samples):,} samples, Test={len(test_samples):,} samples (Zero Overlap)")

    # 3. Execute Runner
    print("\n[*] Running DecisionEngine and Baseline strategies across dataset...")
    runner = BacktestRunner(random_seed=args.seed)
    engine_decisions, baseline_decisions = runner.run_batch(samples)
    print(f"    Evaluated {len(engine_decisions):,} decisions across {1 + len(baseline_decisions)} strategies.")

    # 4. Evaluate & Compile Metrics
    print("\n[*] Compiling 15-Section Backtest Metrics, Stratifications, and Failure Cases...")
    evaluator = BacktestEvaluator()
    report = evaluator.evaluate(samples, engine_decisions, baseline_decisions)

    # 5. Generate Reports
    os.makedirs(args.output, exist_ok=True)
    json_path = os.path.join(args.output, "backtest_report.json")
    md_path = os.path.join(args.output, "backtest_report.md")

    ReportGenerator.save_json(report, json_path)
    ReportGenerator.save_markdown(report, md_path)

    print(f"[*] Saved JSON Report: {json_path}")
    print(f"[*] Saved Markdown Report: {md_path}")

    # 6. Generate Plots (if matplotlib available)
    try:
        from generate_plots import generate_all_plots
        plot_paths = generate_all_plots(samples, engine_decisions, report, args.output)
        print(f"[*] Generated {len(plot_paths)} visualization plots in {args.output}")
    except Exception as e:
        print(f"[*] Note on plots: {e}")

    # 7. Display Summary to Console
    print("\n" + "=" * 80)
    print("📈 BACKTEST v1.1 VALIDITY SUMMARY")
    print("=" * 80)
    print(f"  • Total Samples Evaluated    : {report.total_samples:,}")
    print(f"      - ENDGAME Snapshots      : {report.endgame_count:,} (Descriptive / Integrity only)")
    print(f"      - MIDGAME Snapshots      : {report.midgame_count:,} (Strategy Evaluation)")
    print(f"  • Action Coverage (Known)    : {report.coverage:.1%} ({report.action_observation_coverage.known_action_samples if report.action_observation_coverage else 0} / {report.total_samples})")
    print(f"  • Behavioral Agreement       : {report.recommendation_agreement.get('OVERALL', 0.0):.1%} (Note: Behavioral imitation, not performance)")
    print(f"  • Temporal Violations        : {report.temporal_integrity.violations if report.temporal_integrity else 0}")
    print(f"  • Data Leakage Detected      : {report.leakage_validation.leakage_detected if report.leakage_validation else 0}")
    print(f"  • Failure Cases Diagnosed    : {report.failure_cases_count}")
    print("=" * 80)


if __name__ == "__main__":
    main()
