#!/usr/bin/env python3
"""CLI Runner for TFT Production Calibration Shadow Mode v1."""
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

from tft.calibration.shadow.shadow_runner import ShadowRunner


def main():
    parser = argparse.ArgumentParser(description="TFT Production Calibration Shadow Mode v1")
    parser.add_argument("--mode", type=str, default="replay", choices=["replay", "live", "video"], help="Execution mode")
    parser.add_argument("--session", type=str, default="SESSION_SHADOW_01", help="Session ID")
    parser.add_argument("--video", type=str, default=None, help="Video path if mode is video")
    parser.add_argument("--output", type=str, default=os.path.join(_HERE, "data", "sets", "set18", "calibration", "shadow_v1"), help="Output directory")
    parser.add_argument("--sampling", type=float, default=1.0, help="Sampling rate (0.1 to 1.0)")
    parser.add_argument("--disable-shadow", action="store_true", help="Kill switch to disable shadow layer")
    args = parser.parse_args()

    runner = ShadowRunner(
        root_dir=_HERE,
        output_dir=args.output,
        shadow_enabled=(not args.disable_shadow),
        sampling_rate=args.sampling
    )

    metrics = runner.run_historical_replay()
    runner.write_all_artifacts(metrics)


if __name__ == "__main__":
    main()
