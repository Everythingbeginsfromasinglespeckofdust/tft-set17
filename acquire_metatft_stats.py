#!/usr/bin/env python3
"""MetaTFT Live Statistics Acquisition & Packaging Pipeline for TFT Set 18."""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
_STATS_DIR = os.path.join(_HERE, "data", "sets", "set18", "stats", "metatft")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://www.metatft.com",
    "Referer": "https://www.metatft.com/"
}

TARGET_ENDPOINTS = [
    ("meta_comps_cluster", "https://api-hc.metatft.com/tft-comps-api/latest_cluster_info", "메타 덱 클러스터 및 티어 정보"),
    ("comp_builds", "https://api-hc.metatft.com/tft-comps-api/comp_builds", "덱별 추천 아이템 빌드 및 배치 통계"),
    ("unit_items_stats", "https://api-hc.metatft.com/tft-comps-api/unit_items", "챔피언별 아이템 장착 시너지 및 등수 변동 통계"),
    ("unit_stats", "https://api-hc.metatft.com/tft-stat-api/units", "챔피언별 평균 등수, 승률, 픽률 통계"),
    ("item_stats", "https://api-hc.metatft.com/tft-stat-api/items", "아이템별 평균 등수, 승률, 픽률 통계"),
    ("augment_tier_stats", "https://api-hc.metatft.com/tft-stat-api/augments_tiers", "증강체 티어 및 평균 등수 통계"),
    ("percentiles", "https://api-hc.metatft.com/tft-stat-api/percentiles", "티어별 MMR 및 순위 백분위 분포")
]


def acquire_metatft_stats(output_dir: str = _STATS_DIR):
    os.makedirs(output_dir, exist_ok=True)
    print("=" * 80)
    print("🌐 METATFT SET 18 LIVE STATISTICAL DATA ACQUISITION")
    print("=" * 80)
    print(f"  • Output Directory : {output_dir}")
    print(f"  • Retrieved At     : {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("=" * 80)

    manifest = {
        "source": "MetaTFT (api-hc.metatft.com)",
        "set_id": 18,
        "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "datasets": {}
    }

    total_bytes = 0
    success = 0

    for name, url, desc in TARGET_ENDPOINTS:
        print(f"[*] Fetching {name} ({desc})...")
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw_bytes = resp.read()
                out_file = os.path.join(output_dir, f"{name}.json")
                with open(out_file, "wb") as f:
                    f.write(raw_bytes)
                
                sha256 = hashlib.sha256(raw_bytes).hexdigest()
                size = len(raw_bytes)
                total_bytes += size
                success += 1

                manifest["datasets"][name] = {
                    "filename": f"{name}.json",
                    "description": desc,
                    "url": url,
                    "size_bytes": size,
                    "sha256": sha256
                }
                print(f"  [+] Saved {name}.json -> {size:,} bytes (SHA: {sha256[:12]}...)")
        except Exception as e:
            print(f"  [!] Failed to download {name}: {e}")

    # Write stats manifest
    manifest_path = os.path.join(output_dir, "metatft_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(f"🏁 MetaTFT Data Acquisition Complete: {success}/{len(TARGET_ENDPOINTS)} Datasets ({total_bytes / 1024 / 1024:.2f} MB)")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Acquire MetaTFT Set 18 Statistics")
    parser.add_argument("--output", type=str, default=_STATS_DIR, help="Output directory")
    args = parser.parse_args()
    acquire_metatft_stats(args.output)
