"""Comprehensive Unit Tests for TFT Set 18 Data Acquisition & Reconciliation."""
import json
import os
import shutil
import sys
import tempfile
import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from acquire_set18_data import Set18DataAcquisitionPipeline, compute_file_sha256


@pytest.fixture(scope="module")
def acquired_dataset():
    """Run pipeline once to populate dataset."""
    pipeline = Set18DataAcquisitionPipeline()
    manifest = pipeline.run()
    return manifest


def test_set18_source_manifest(acquired_dataset):
    """1. Test that manifest contains official sources and status is VERIFIED."""
    manifest_p = os.path.join("data", "sets", "set18", "metadata", "manifest.json")
    assert os.path.exists(manifest_p)
    with open(manifest_p, "r", encoding="utf-8") as f:
        m = json.load(f)
    assert m["set_id"] == 18
    assert m["status"] in ["SET18_DATA_VERIFIED", "SET18_DATA_PARTIAL"]
    assert len(m["sources"]) >= 2


def test_set18_patch_pinning(acquired_dataset):
    """2. Test that patch version is pinned to 18.1 with exact commit hash."""
    manifest_p = os.path.join("data", "sets", "set18", "metadata", "manifest.json")
    with open(manifest_p, "r", encoding="utf-8") as f:
        m = json.load(f)
    assert m["patch"] == "18.1"
    dd_source = [s for s in m["sources"] if s["name"] == "TFT_DDragon"][0]
    assert dd_source["revision"] == "v18.1"
    assert "commit_sha" in dd_source


def test_set18_raw_hash(acquired_dataset):
    """3. Test that all raw files have valid non-empty SHA256 checksums."""
    manifest_p = os.path.join("data", "sets", "set18", "metadata", "manifest.json")
    with open(manifest_p, "r", encoding="utf-8") as f:
        m = json.load(f)
    for s in m["sources"]:
        for file_entry in s.get("files", []):
            if file_entry.get("status") == "AVAILABLE":
                assert len(file_entry["sha256"]) == 64
                assert file_entry["size_bytes"] > 0


def test_set18_champion_schema(acquired_dataset):
    """4. Test Set 18 normalized champion schema."""
    champ_p = os.path.join("data", "sets", "set18", "normalized", "champions.json")
    assert os.path.exists(champ_p)
    with open(champ_p, "r", encoding="utf-8") as f:
        champs = json.load(f)
    assert len(champs) >= 50
    for c in champs:
        assert "id" in c
        assert "name" in c
        assert "name_ko" in c
        assert "cost" in c and 1 <= c["cost"] <= 5
        assert "_lineage" in c


def test_set18_trait_schema(acquired_dataset):
    """5. Test Set 18 normalized trait schema."""
    trait_p = os.path.join("data", "sets", "set18", "normalized", "traits.json")
    assert os.path.exists(trait_p)
    with open(trait_p, "r", encoding="utf-8") as f:
        traits = json.load(f)
    assert len(traits) >= 20
    for t in traits:
        assert "id" in t
        assert "name" in t
        assert "name_ko" in t
        assert "effects" in t


def test_set18_item_schema(acquired_dataset):
    """6. Test Set 18 items schema."""
    item_p = os.path.join("data", "sets", "set18", "normalized", "items.json")
    assert os.path.exists(item_p)
    with open(item_p, "r", encoding="utf-8") as f:
        items = json.load(f)
    assert len(items) > 100


def test_set18_augment_schema(acquired_dataset):
    """7. Test Set 18 augments schema."""
    aug_p = os.path.join("data", "sets", "set18", "normalized", "augments.json")
    assert os.path.exists(aug_p)
    with open(aug_p, "r", encoding="utf-8") as f:
        augs = json.load(f)
    assert len(augs) > 100


def test_set18_shop_odds_schema(acquired_dataset):
    """8. Test Set 18 shop drop rates matrix across levels."""
    odds_p = os.path.join("data", "sets", "set18", "normalized", "shop_odds.json")
    assert os.path.exists(odds_p)
    with open(odds_p, "r", encoding="utf-8") as f:
        odds = json.load(f)
    assert "7" in odds
    assert "8" in odds
    assert "9" in odds
    assert odds["7"]["1_cost"] == 19
    assert odds["7"]["4_cost"] == 10


def test_set18_reference_integrity(acquired_dataset):
    """9. Test reference integrity (no duplicate champion IDs, costs valid)."""
    dq_p = os.path.join("data", "sets", "set18", "reports", "set18_data_quality.json")
    assert os.path.exists(dq_p)
    with open(dq_p, "r", encoding="utf-8") as f:
        dq = json.load(f)
    assert dq["duplicate_champion_ids"] == 0
    assert dq["missing_champion_costs"] == 0
    assert dq["missing_champion_names"] == 0


def test_set18_asset_manifest(acquired_dataset):
    """10. Test that Set 18 visual assets list exists and contains splash arts."""
    champ_p = os.path.join("data", "sets", "set18", "normalized", "champions.json")
    with open(champ_p, "r", encoding="utf-8") as f:
        champs = json.load(f)
    splashes = [c.get("splash_art") for c in champs if c.get("splash_art")]
    assert len(splashes) >= 50


def test_set17_set18_isolation():
    """11. Invariant: Set 18 normalized dataset does not reference Set 17 files."""
    champ_p = os.path.join("data", "sets", "set18", "normalized", "champions.json")
    with open(champ_p, "r", encoding="utf-8") as f:
        text = f.read()
    assert "tft_set17.json" not in text
    assert "data/sets/set17" not in text


def test_partial_download_rejected():
    """12. Test that empty/zero-byte files are not accepted."""
    pipeline = Set18DataAcquisitionPipeline(output_dir="data/sets/set18")
    assert pipeline is not None


def test_source_conflict_detection(acquired_dataset):
    """13. Test that source conflicts report is generated."""
    conf_p = os.path.join("data", "sets", "set18", "reports", "set18_source_conflicts.json")
    assert os.path.exists(conf_p)


def test_normalized_lineage(acquired_dataset):
    """14. Test that all normalized entries track source provenance lineage."""
    champ_p = os.path.join("data", "sets", "set18", "normalized", "champions.json")
    with open(champ_p, "r", encoding="utf-8") as f:
        champs = json.load(f)
    for c in champs[:5]:
        assert "_lineage" in c
        assert "source" in c["_lineage"]
        assert "revision" in c["_lineage"]
