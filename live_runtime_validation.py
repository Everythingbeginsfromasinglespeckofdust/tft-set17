#!/usr/bin/env python3
"""CLI Runner for TFT Production Live Runtime Validation v1."""
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

from tft.calibration.integration.models import CalibrationMode
from tft.vision.live_runtime.runtime_evaluator import LiveRuntimeEvaluator


def main():
    parser = argparse.ArgumentParser(description="TFT Production Live Runtime Validation v1")
    parser.add_argument("--mode", type=str, default="on", choices=["off", "shadow", "on"], help="Calibration mode")
    parser.add_argument("--checkpoints", type=int, default=105, help="Number of checkpoints to evaluate")
    parser.add_argument("--output", type=str, default=os.path.join(_HERE, "data", "vision_validation", "live_runtime"), help="Output directory")
    args = parser.parse_args()

    mode_enum = CalibrationMode(args.mode.upper())
    evaluator = LiveRuntimeEvaluator(
        root_dir=_HERE,
        output_dir=args.output,
        mode=mode_enum
    )

    evaluator.generate_and_evaluate_checkpoints(target_count=args.checkpoints)
    evaluator.write_all_artifacts()


if __name__ == "__main__":
    main()
