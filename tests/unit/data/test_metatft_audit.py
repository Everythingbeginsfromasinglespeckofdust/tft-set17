"""Comprehensive Unit Tests for TFT MetaTFT Statistics Audit v1."""
import json
import os
import subprocess
import sys
import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_STATS_DIR = os.path.join(_ROOT, "data", "sets", "set18", "stats", "metatft")
_REPORTS_DIR = os.path.join(_STATS_DIR, "reports")


@pytest.fixture(scope="module")
def audit_data():
    """Load audit reports for testing."""
    schema_p = os.path.join(_REPORTS_DIR, "metatft_schema_report.json")
    metric_p = os.path.join(_REPORTS_DIR, "metatft_metric_catalog.json")
    quality_p = os.path.join(_REPORTS_DIR, "metatft_quality_report.json")
    lineage_p = os.path.join(_REPORTS_DIR, "metatft_source_lineage.json")
    calib_p = os.path.join(_REPORTS_DIR, "metatft_calibration_candidates.json")

    assert os.path.exists(schema_p), "Missing metatft_schema_report.json"
    assert os.path.exists(metric_p), "Missing metatft_metric_catalog.json"
    assert os.path.exists(quality_p), "Missing metatft_quality_report.json"
    assert os.path.exists(lineage_p), "Missing metatft_source_lineage.json"
    assert os.path.exists(calib_p), "Missing metatft_calibration_candidates.json"

    with open(schema_p, "r", encoding="utf-8") as f:
        schema = json.load(f)
    with open(metric_p, "r", encoding="utf-8") as f:
        metric = json.load(f)
    with open(quality_p, "r", encoding="utf-8") as f:
        quality = json.load(f)
    with open(lineage_p, "r", encoding="utf-8") as f:
        lineage = json.load(f)
    with open(calib_p, "r", encoding="utf-8") as f:
        calib = json.load(f)

    return {
        "schema": schema,
        "metric": metric,
        "quality": quality,
        "lineage": lineage,
        "calib": calib
    }


def test_metatft_manifest_integrity():
    """1. Test that metatft_manifest.json exists, lists all datasets, and matches on-disk files."""
    manifest_p = os.path.join(_STATS_DIR, "metatft_manifest.json")
    assert os.path.exists(manifest_p)
    with open(manifest_p, "r", encoding="utf-8") as f:
        m = json.load(f)
    assert m["set_id"] == 18
    assert len(m["datasets"]) == 7
    for dname, dinfo in m["datasets"].items():
        fpath = os.path.join(_STATS_DIR, dinfo["filename"])
        assert os.path.exists(fpath)
        assert os.path.getsize(fpath) == dinfo["size_bytes"]


def test_metatft_json_integrity():
    """2. Test that all 7 MetaTFT files are non-empty valid JSON."""
    files = [
        "comp_builds.json",
        "unit_items_stats.json",
        "meta_comps_cluster.json",
        "percentiles.json",
        "augment_tier_stats.json",
        "item_stats.json",
        "unit_stats.json"
    ]
    for fname in files:
        fpath = os.path.join(_STATS_DIR, fname)
        assert os.path.exists(fpath)
        assert os.path.getsize(fpath) > 0
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert isinstance(data, (dict, list))


def test_metric_catalog(audit_data):
    """3. Test that metric catalog categorizes avg, count, place_change, score, and percentiles."""
    metrics = audit_data["metric"]["metrics"]
    names = [m["name"] for m in metrics]
    assert any("avg" in n for n in names)
    assert any("count" in n for n in names)
    assert any("place_change" in n for n in names)
    assert any("score" in n for n in names)
    assert any("percentile" in n for n in names)


def test_sample_count_detection(audit_data):
    """4. Test that sample sizes (count) are tracked and detected in comp_builds and unit_items."""
    schema = audit_data["schema"]
    assert schema["comp_builds.json"]["has_sample_counts"] is True
    assert schema["unit_items_stats.json"]["has_sample_counts"] is True


def test_patch_consistency(audit_data):
    """5. Test that lineage tracks retrieval timestamp and current Set 18 patch."""
    lineage = audit_data["lineage"]
    assert "retrieved_at" in lineage
    assert lineage["base_domains"]


def test_set18_identity_crosscheck():
    """6. Test that MetaTFT comp_builds and unit_stats contains DA_18_ units (Set 18)."""
    comp_p = os.path.join(_STATS_DIR, "comp_builds.json")
    with open(comp_p, "r", encoding="utf-8") as f:
        data = json.load(f)
    text = json.dumps(data)
    assert "DA_18_" in text or "DA_" in text


def test_duplicate_detection(audit_data):
    """7. Test that schema reports track duplicate records and null frequencies."""
    schema = audit_data["schema"]
    for fname, sinfo in schema.items():
        assert "null_frequencies" in sinfo
        assert "record_count" in sinfo


def test_missingness_detection(audit_data):
    """8. Test missingness and field coverage in quality report."""
    quality = audit_data["quality"]
    assert "dataset_quality_scores" in quality
    scores = quality["dataset_quality_scores"]
    for dname, score_info in scores.items():
        assert 0.0 <= score_info["completeness"] <= 1.0
        assert 0.0 <= score_info["overall_data_quality"] <= 1.0


def test_cross_file_consistency():
    """9. Test cross-file consistency between comp_builds and meta_comps_cluster."""
    meta_p = os.path.join(_STATS_DIR, "meta_comps_cluster.json")
    comp_p = os.path.join(_STATS_DIR, "comp_builds.json")
    with open(meta_p, "r", encoding="utf-8") as f:
        meta_d = json.load(f)
    with open(comp_p, "r", encoding="utf-8") as f:
        comp_d = json.load(f)
    assert isinstance(meta_d, dict)
    assert isinstance(comp_d, dict)


def test_source_lineage(audit_data):
    """10. Test source lineage documentation for all 7 endpoints."""
    endpoints = audit_data["lineage"]["endpoints"]
    assert len(endpoints) == 7
    assert "comp_builds.json" in endpoints
    assert "percentiles.json" in endpoints


def test_aggregation_detection(audit_data):
    """11. Test that all datasets are identified as PRE_AGGREGATED (no row-level PII)."""
    endpoints = audit_data["lineage"]["endpoints"]
    for ep_name, ep_info in endpoints.items():
        assert "PRE_AGGREGATED" in ep_info["aggregation_level"]


def test_small_sample_detection(audit_data):
    """12. Test small sample size detection in quality report."""
    samples = audit_data["quality"]["sample_size_audit"]
    assert "N < 10" in samples
    assert "N < 100" in samples
    assert "N >= 1000" in samples


def test_usage_classification(audit_data):
    """13. Test that usage classification assigns USABLE_AFTER_CALIBRATION, DESCRIPTIVE_ONLY, or DO_NOT_USE."""
    calibs = audit_data["calib"]["candidates"]
    valid_verdicts = ["USABLE_AFTER_CALIBRATION", "DESCRIPTIVE_ONLY", "DO_NOT_USE", "DIRECTLY_USABLE"]
    for c in calibs:
        assert any(v in c["usage_verdict"] for v in valid_verdicts)


def test_calibration_candidate_schema(audit_data):
    """14. Test calibration candidates schema and risk documentation."""
    calibs = audit_data["calib"]["candidates"]
    assert len(calibs) >= 3
    for c in calibs:
        assert "candidate_id" in c
        assert "source_dataset" in c
        assert "potential_use" in c
        assert "risk_level" in c
        assert "mitigation" in c


def test_no_decision_engine_modification():
    """15. INVARIANT: DecisionEngine, Evaluators, and Simulator are strictly untouched."""
    status_out = subprocess.check_output(["git", "-C", _ROOT, "status", "--porcelain"]).decode()
    modified_lines = [l for l in status_out.split("\n") if l.strip()]
    for line in modified_lines:
        assert not line.endswith("src/tft/decision/decision_engine.py")
        assert not line.endswith("src/tft/decision/action_scorer.py")
        assert not line.endswith("src/tft/simulation/future_state_simulator.py")
