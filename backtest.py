#!/usr/bin/env python3
"""TFT Decision Engine Backtesting CLI Tool.

사용법:
    python backtest.py --limit 500 --output data/backtest/reports
    python backtest.py --video --limit 1000
"""
import argparse
import os
import sys

# Ensure src is on python path
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from tft.backtest.dataset import BacktestDataset
from tft.backtest.runner import BacktestRunner
from tft.backtest.evaluator import BacktestEvaluator
from tft.backtest.reporting import ReportGenerator

def parse_args():
    parser = argparse.ArgumentParser(description="TFT Decision Engine Backtesting Framework CLI")
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
        help="Sample limit for backtesting (0 for full dataset)"
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
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic reproducibility"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    print("=" * 80)
    print("🎮 TFT DECISION ENGINE — BACKTESTING & CALIBRATION FRAMEWORK")
    print("=" * 80)

    # 1. Load Samples
    samples = []
    print(f"[*] Loading historical match snapshots from: {args.input}")
    limit_val = args.limit if args.limit > 0 else None
    
    if os.path.exists(args.input):
        match_samples = BacktestDataset.load_from_match_snapshots(args.input, limit=limit_val)
        samples.extend(match_samples)
        print(f"    Loaded {len(match_samples):,} match snapshots.")

    # Load video audit samples
    if args.video:
        video_path = os.path.join(_HERE, "output", "video_analysis", "10min_audit", "shop_timeline.json")
        if os.path.exists(video_path):
            video_samples = BacktestDataset.load_from_video_audit(video_path)
            samples.extend(video_samples)
            print(f"    Loaded {len(video_samples):,} video audit snapshots (with real observed actions).")

    # Load synthetic if requested
    if args.synthetic:
        synth_samples = BacktestDataset.create_synthetic_dataset(num_samples=50, seed=args.seed)
        samples.extend(synth_samples)
        print(f"    Loaded {len(synth_samples):,} synthetic validation samples.")

    print(f"[*] Total Validated Samples for Evaluation: {len(samples):,}")

    if not samples:
        print("[!] No samples loaded. Exiting.")
        return

    # 2. Match-Level Split Check
    train_samples, test_samples = BacktestDataset.split_by_match(samples, train_ratio=0.8, seed=args.seed)
    print(f"[*] Match-Level Group Split: Train={len(train_samples):,} samples, Test={len(test_samples):,} samples (Zero Match Overlap)")

    # 3. Execute Runner
    print("\n[*] Running DecisionEngine and Baseline strategies across dataset...")
    runner = BacktestRunner(random_seed=args.seed)
    engine_decisions, baseline_decisions = runner.run_batch(samples)
    print(f"    Evaluated {len(engine_decisions):,} decisions across {1 + len(baseline_decisions)} strategies.")

    # 4. Evaluate & Compile Metrics
    print("\n[*] Compiling Backtest Metrics, Stratifications, and Failure Cases...")
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

    # 6. Display Summary to Console
    print("\n" + "=" * 80)
    print("📈 BACKTEST SUMMARY RESULTS")
    print("=" * 80)
    print(f"  • Total Samples Evaluated    : {report.total_samples:,}")
    print(f"  • Unique Matches             : {report.total_matches:,}")
    print(f"  • Unique Participants        : {report.total_participants:,}")
    print(f"  • Action Coverage (Known)    : {report.coverage:.1%}")
    print(f"  • Overall Behavioral Agrmnt  : {report.recommendation_agreement.get('OVERALL', 0.0):.1%}")
    print("\n  • Baseline Strategy Comparison:")
    for strat, m in report.baseline_comparisons.items():
        print(f"      - {strat:<20}: Agreement={m['agreement_rate']:.1%} | ROLL={m['pct_roll']:.1%}, UP={m['pct_level_up']:.1%}, SAVE={m['pct_save_gold']:.1%}")

    print(f"\n  • Outcome Summary (Valid Placements: {report.outcome_summary.get('total_with_placement', 0):,}):")
    print(f"      - Average Placement      : {report.outcome_summary.get('avg_placement')}")
    print(f"      - Top 4 Rate             : {report.outcome_summary.get('top4_rate', 0.0):.1%}")
    print(f"  • Failure Cases Detected     : {report.failure_cases_count}")
    print("=" * 80)

if __name__ == "__main__":
    main()
