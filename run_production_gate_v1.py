#!/usr/bin/env python3
"""CLI Runner for TFT Production Calibration Gate v1."""
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

from tft.calibration.production_gate import ProductionCalibrationGateV1


def main():
    parser = argparse.ArgumentParser(description="Run TFT Production Calibration Gate v1")
    parser.add_argument("--set", type=str, default="18", help="TFT Set ID")
    parser.add_argument("--stats", type=str, default=os.path.join(_HERE, "data", "sets", "set18", "stats", "metatft"), help="Stats directory")
    parser.add_argument("--output", type=str, default=os.path.join(_HERE, "data", "sets", "set18", "calibration", "production_gate_v1"), help="Output directory")
    parser.add_argument("--patch", type=str, default="18.1", help="Target patch version")
    args = parser.parse_args()

    gate = ProductionCalibrationGateV1(
        root_dir=_HERE,
        stats_dir=args.stats,
        output_dir=args.output,
        patch=args.patch
    )
    gate.load_and_audit_samples()
    gate.run_production_gate_evaluation()
    val_analyses = gate.run_validation_analyses()
    gate.write_all_artifacts(val_analyses)


if __name__ == "__main__":
    main()
