#!/usr/bin/env python3
"""Inspect TFT Set 18 Dataset: Roster, Traits, Odds, and Quality Metrics."""
import argparse
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_HERE, "data", "sets", "set18")


def inspect_dataset(data_dir: str = _DATA_DIR):
    norm_dir = os.path.join(data_dir, "normalized")
    meta_dir = os.path.join(data_dir, "metadata")
    rep_dir = os.path.join(data_dir, "reports")

    manifest_path = os.path.join(meta_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        print(f"[!] Set 18 Manifest not found at: {manifest_path}")
        print("    Please run: python acquire_set18_data.py first.")
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print("=" * 80)
    print(f"🔍 TFT SET 18 DATASET INSPECTION (Patch {manifest.get('patch')})")
    print("=" * 80)
    print(f"  • Status       : {manifest.get('status')}")
    print(f"  • Retrieved At : {manifest.get('retrieved_at')}")
    print(f"  • Sources      : {[s.get('name') for s in manifest.get('sources', [])]}")
    print("=" * 80)

    # 1. Champions
    champ_p = os.path.join(norm_dir, "champions.json")
    if os.path.exists(champ_p):
        with open(champ_p, "r", encoding="utf-8") as f:
            champs = json.load(f)
        cost_map = {}
        for c in champs:
            cost = c["cost"]
            cost_map[cost] = cost_map.get(cost, 0) + 1

        print(f"\n[1] Champions: {len(champs)} Total")
        print(f"    Cost Distribution: {sorted(cost_map.items())}")
        print("    Sample 10 Champions:")
        for c in champs[:10]:
            traits_str = ", ".join(c.get("traits", [])) or "None"
            print(f"      - {c['name']} ({c['name_ko']}) | {c['cost']}G | Traits: [{traits_str}] | Splash: {c['splash_art']}")

    # 2. Traits
    trait_p = os.path.join(norm_dir, "traits.json")
    if os.path.exists(trait_p):
        with open(trait_p, "r", encoding="utf-8") as f:
            traits = json.load(f)
        print(f"\n[2] Traits: {len(traits)} Total")
        print("    Sample 10 Traits:")
        for t in traits[:10]:
            bp_str = "/".join(str(b) for b in t.get("breakpoints", [])) or "N/A"
            print(f"      - {t['name']} ({t['name_ko']}) | Breakpoints: [{bp_str}]")

    # 3. Shop Odds Matrix
    odds_p = os.path.join(norm_dir, "shop_odds.json")
    if os.path.exists(odds_p):
        with open(odds_p, "r", encoding="utf-8") as f:
            odds = json.load(f)
        print(f"\n[3] Shop Drop Rates Matrix (Levels 1 to 11):")
        print(f"    {'Level':<8} | {'1-Cost':<8} | {'2-Cost':<8} | {'3-Cost':<8} | {'4-Cost':<8} | {'5-Cost':<8}")
        print("    " + "-" * 55)
        for lvl in range(1, 12):
            row = odds.get(str(lvl), {})
            print(f"    Lvl {lvl:<4} | {row.get('1_cost', 0):>6}% | {row.get('2_cost', 0):>6}% | {row.get('3_cost', 0):>6}% | {row.get('4_cost', 0):>6}% | {row.get('5_cost', 0):>6}%")

    # 4. Data Quality Summary
    dq_p = os.path.join(rep_dir, "set18_data_quality.json")
    if os.path.exists(dq_p):
        with open(dq_p, "r", encoding="utf-8") as f:
            dq = json.load(f)
        print(f"\n[4] Data Quality & Integrity Summary:")
        print(f"    • Duplicate IDs        : {dq.get('duplicate_champion_ids', 0)}")
        print(f"    • Missing Costs        : {dq.get('missing_champion_costs', 0)}")
        print(f"    • Broken References    : {dq.get('broken_recipe_references', 0)}")
        print(f"    • Source Conflicts     : {dq.get('source_conflicts_count', 0)}")
        print(f"    • Economy Data Gaps    : {dq.get('economy_gap_status')}")

    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Inspect TFT Set 18 Dataset")
    parser.add_argument("--data-dir", type=str, default=_DATA_DIR, help="Set 18 data directory")
    args = parser.parse_args()
    inspect_dataset(args.data_dir)


if __name__ == "__main__":
    main()
