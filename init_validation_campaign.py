#!/usr/bin/env python3
"""Initialize a new Human Validation Campaign with systematic directory structure."""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from tft.vision.campaign_manager import CampaignManager


def parse_args():
    parser = argparse.ArgumentParser(description="Initialize Human Validation Campaign")
    parser.add_argument("--campaign-id", type=str, default="CAMPAIGN_001", help="Unique Campaign ID")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for spot checks")
    return parser.parse_args()


def main():
    args = parse_args()
    mgr = CampaignManager()
    manifest = mgr.init_campaign(args.campaign_id, seed=args.seed)

    print("=" * 80)
    print(f"📋 INITIALIZED HUMAN VALIDATION CAMPAIGN: {manifest.campaign_id}")
    print("=" * 80)
    print(f"  • Campaign ID     : {manifest.campaign_id}")
    print(f"  • Version         : {manifest.version}")
    print(f"  • Random Seed     : {manifest.random_seed}")
    print(f"  • Git Commit Hash : {manifest.git_commit_hash}")
    print(f"  • Created At      : {manifest.created_at}")
    print(f"  • Directory       : data/vision_validation/campaign/campaigns/{manifest.campaign_id}")
    print("=" * 80)


if __name__ == "__main__":
    main()
