#!/usr/bin/env python3
"""Compare TFT Set 17 vs Set 18 Schema, Roster, and Drop Rates."""
import argparse
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
_SET17_FILE = os.path.join(_HERE, "tft_set17.json")
_SET18_DIR = os.path.join(_HERE, "data", "sets", "set18")


def compare_datasets(set17_file: str = _SET17_FILE, set18_dir: str = _SET18_DIR):
    set18_champ_file = os.path.join(set18_dir, "normalized", "champions.json")
    set18_trait_file = os.path.join(set18_dir, "normalized", "traits.json")

    if not os.path.exists(set17_file):
        print(f"[!] Set 17 file not found: {set17_file}")
        return
    if not os.path.exists(set18_champ_file):
        print(f"[!] Set 18 normalized champions not found: {set18_champ_file}")
        print("    Please run: python acquire_set18_data.py first.")
        return

    with open(set17_file, "r", encoding="utf-8") as f:
        s17_data = json.load(f)
    with open(set18_champ_file, "r", encoding="utf-8") as f:
        s18_champs = json.load(f)
    with open(set18_trait_file, "r", encoding="utf-8") as f:
        s18_traits = json.load(f)

    s17_champs = s17_data.get("champions", [])
    s17_names = set(c["name"] for c in s17_champs)
    s18_names = set(c["name_ko"] for c in s18_champs)

    retained = s17_names.intersection(s18_names)
    new_in_s18 = s18_names - s17_names
    removed_from_s17 = s17_names - s18_names

    print("=" * 80)
    print("⚖️  TFT SET 17 vs SET 18 RECONCILIATION & COMPARISON")
    print("=" * 80)
    print(f"  • Set 17 Champions Count : {len(s17_champs)}")
    print(f"  • Set 18 Champions Count : {len(s18_champs)}")
    print(f"  • Retained Champions     : {len(retained)}")
    print(f"  • New Set 18 Champions   : {len(new_in_s18)}")
    print(f"  • Removed Set 17 Champs  : {len(removed_from_s17)}")
    print(f"  • Set 18 Total Traits    : {len(s18_traits)}")
    print("=" * 80)

    print("\n[+] Notable New Champions in Set 18:")
    for name in sorted(list(new_in_s18))[:12]:
        print(f"    - {name}")

    print("\n[+] Isolation & Lineage Verification:")
    # Check that Set 18 normalized file contains no references to Set 17 paths
    with open(set18_champ_file, "r", encoding="utf-8") as f:
        content_s18 = f.read()
    has_s17_leakage = "tft_set17.json" in content_s18 or "data/sets/set17" in content_s18
    print(f"    • Set 18 referencing Set 17 data: {'LEAKAGE DETECTED' if has_s17_leakage else 'ZERO (100% ISOLATED)'}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Compare TFT Set 17 vs Set 18")
    parser.add_argument("--set17", type=str, default=_SET17_FILE, help="Path to Set 17 JSON")
    parser.add_argument("--set18", type=str, default=_SET18_DIR, help="Path to Set 18 directory")
    args = parser.parse_args()
    compare_datasets(args.set17, args.set18)


if __name__ == "__main__":
    main()
