#!/usr/bin/env python3
"""Run frozen TFT Vision-to-Action pipeline across all pilot sessions."""
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
from tft.vision.pilot_pipeline import MultiSessionPilotRunner


def parse_args():
    parser = argparse.ArgumentParser(description="Run Multi-Session Pilot Pipeline")
    parser.add_argument(
        "--config",
        type=str,
        default=os.path.join(_HERE, "data", "backtest", "pilot", "pilot_manifest.json"),
        help="Path to pilot_manifest.json"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(_HERE, "data", "backtest", "pilot"),
        help="Output base directory"
    )
    parser.add_argument(
        "--start",
        type=float,
        default=300.0,
        help="Start time in seconds (default: 300.0s)"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=600.0,
        help="Duration in seconds (default: 600.0s)"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("🚀 TFT MULTI-SESSION PILOT V1 -- BATCH PIPELINE EXECUTION")
    print("=" * 80)

    if not os.path.exists(args.config):
        print(f"[!] Manifest not found at {args.config}. Initializing default manifest...")
        from register_pilot_session import main as reg_main
        sys.argv = ["register_pilot_session.py", "--init-default", "--manifest", args.config]
        reg_main()

    manifest = PilotManifest.load_from_json(args.config)
    print(f"[*] Loaded Manifest: {len(manifest.sessions)} sessions")

    runner = MultiSessionPilotRunner()
    for session in manifest.sessions:
        runner.run_session(
            session=session,
            output_base_dir=args.output,
            start_sec=args.start,
            duration_sec=args.duration
        )

    print("\n" + "=" * 80)
    print(f"✅ BATCH EXECUTION COMPLETE for {len(manifest.sessions)} sessions.")
    print(f"[*] Artifacts stored under: {args.output}/sessions/")
    print("=" * 80)


if __name__ == "__main__":
    main()
