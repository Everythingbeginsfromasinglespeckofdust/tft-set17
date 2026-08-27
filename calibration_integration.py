#!/usr/bin/env python3
"""CLI Runner for TFT Production Calibration Integration v1."""
import argparse
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from tft.calibration.integration.runner import CalibrationIntegrationRunner


def main():
    parser = argparse.ArgumentParser(description="TFT Production Calibration Integration v1")
    parser.add_argument("--mode", type=str, default="on", choices=["off", "shadow", "on"], help="Calibration mode")
    parser.add_argument("--input", type=str, default=None, help="Input samples JSONL")
    parser.add_argument("--live", action="store_true", help="Live desktop capture mode")
    parser.add_argument("--output", type=str, default=os.path.join(_HERE, "data", "sets", "set18", "calibration", "production_v1"), help="Output directory")
    args = parser.parse_args()

    runner = CalibrationIntegrationRunner(
        root_dir=_HERE,
        output_dir=args.output
    )

    metrics = runner.run_multi_mode_replay()
    runner.write_all_artifacts(metrics)


if __name__ == "__main__":
    main()
