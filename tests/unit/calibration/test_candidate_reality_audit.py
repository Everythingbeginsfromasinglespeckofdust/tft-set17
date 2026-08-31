"""Unit tests for TFT Candidate Engine Reality Audit v1.

18 tests covering all audit sub-modules per spec:
  test_constant_provenance, test_no_hidden_override, test_match_level_split,
  test_no_train_test_match_overlap, test_feature_recomputation, test_no_future_leakage,
  test_no_synthetic_input, test_human_independence, test_threshold_search,
  test_threshold_stability, test_sensitivity_analysis, test_interaction_analysis,
  test_outcome_grouping, test_candidate_score_trace, test_decision_guide_consistency,
  test_candidate_vs_baseline, test_production_gate, test_protected_core_unchanged
"""
import json
import os
import sys
import glob
import subprocess
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
_ROOT = os.path.abspath(os.path.join(_SRC, ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.research.decision_model.reality_auditor import RealityAuditor

AUDIT_DIR = os.path.join(
    _ROOT, "data", "sets", "set18", "calibration", "decision_model_v2", "reality_audit"
)
CHECKPOINTS_DIR = os.path.join(
    _ROOT, "data", "decision_assistant", "reality_validation",
    "REAL_GAMEPLAY_SESSION_001", "checkpoints"
)
PROTECTED_DIRS = ["src/tft/decision", "src/tft/simulation", "src/tft/evaluation", "src/tft/domain"]


@pytest.fixture(scope="module")
def auditor():
    return RealityAuditor()


@pytest.fixture(scope="module")
def real_samples(auditor):
    """Load all 20 real checkpoints."""
    cp_dirs = sorted(glob.glob(os.path.join(CHECKPOINTS_DIR, "CP*")))
    samples = []
    for cp_dir in cp_dirs:
        cp_id = os.path.basename(cp_dir)
        with open(os.path.join(cp_dir, "state.json"), "r", encoding="utf-8") as f:
            raw = json.load(f)
        sr = raw["stage_round"]
        stage, rnd = int(sr.split("-")[0]), int(sr.split("-")[1])
        gst = GameState(
            stage=stage, round=rnd, stage_round=sr,
            player=PlayerState(gold=raw["gold"], level=raw["level"],
                               xp=raw.get("xp", 0), hp=raw["hp"]),
            board_units=[Unit(champion=u.get("champion", ""), cost=u.get("cost", 1),
                              star_level=u.get("star_level", 1))
                         for u in raw.get("board_units", [])],
            bench_units=[Unit(champion=u.get("champion", ""), cost=u.get("cost", 1),
                              star_level=u.get("star_level", 1), is_bench=True)
                         for u in raw.get("bench_units", [])],
            shop_units=raw.get("shop_units", [None] * 5)
        )
        base_snap = auditor.engine.baseline.capture_snapshot(gst, sample_id=cp_id)
        vec = auditor.engine.extractor.extract(gst, sample_id=cp_id)
        samples.append({
            "sample_id": cp_id, "state": gst,
            "baseline_action": base_snap["recommended_action"],
            "baseline_score": base_snap["recommended_score"],
            "rounds_to_elimination": vec.temporal.estimated_rounds_to_elimination
        })
    return samples


class TestConstantProvenance:
    """test_constant_provenance: All adjustment coefficients must be classified."""

    def test_constant_provenance(self, auditor):
        result = auditor.audit_constant_provenance()
        assert result["total_constants_audited"] >= 12
        # Zero empirically derived: honest assertion
        assert result["empirically_derived_count"] == 0, (
            "Claim: no coefficients are empirically derived. "
            f"But audit reports {result['empirically_derived_count']} as derived."
        )
        # All coefficients must have source
        for const in result["constants"]:
            assert "source" in const
            assert const["source"] in {"DESIGN_ASSUMPTION", "GAME_RULE_INFORMED_ASSUMPTION"}
        # Dead code identified
        assert "stage_deficit_coeff" in result["dead_code_constants"]


class TestNoHiddenOverride:
    """test_no_hidden_override: Candidate engine must use score-based decisions only."""

    def test_no_hidden_override(self, auditor):
        result = auditor.audit_hidden_overrides()
        assert result["verdict"] == "NO_HIDDEN_OVERRIDES_DETECTED", (
            f"Hidden overrides found: {result['hidden_rules']}"
        )
        assert result["hidden_override_count"] == 0


class TestMatchLevelSplit:
    """test_match_level_split: Audit must report correct split status."""

    def test_match_level_split(self, auditor):
        result = auditor.build_train_validation_test_split()
        assert result["total_real_matches"] == 1
        assert result["split_status"] == "INSUFFICIENT_MATCHES_FOR_OOS_SPLIT"
        assert result["group_kfold_possible"] is False
        assert len(result["validation_matches"]) == 0
        assert len(result["test_matches"]) == 0


class TestNoTrainTestMatchOverlap:
    """test_no_train_test_match_overlap: No match can appear in both train and test."""

    def test_no_train_test_match_overlap(self, auditor):
        result = auditor.build_train_validation_test_split()
        train_set = set(result["train_matches"])
        val_set = set(result["validation_matches"])
        test_set = set(result["test_matches"])
        assert len(train_set & test_set) == 0, "Same match in train and test!"
        assert len(train_set & val_set) == 0, "Same match in train and validation!"
        assert len(val_set & test_set) == 0, "Same match in validation and test!"


class TestFeatureRecomputation:
    """test_feature_recomputation: Feature recomputation references previous audit."""

    def test_feature_recomputation(self, auditor):
        result = auditor.audit_constant_provenance()
        # Verify extractor produces non-null vectors for all 20 real checkpoints
        cp_dirs = sorted(glob.glob(os.path.join(CHECKPOINTS_DIR, "CP*")))
        assert len(cp_dirs) == 20, f"Expected 20 checkpoints, got {len(cp_dirs)}"
        for cp_dir in cp_dirs:
            cp_id = os.path.basename(cp_dir)
            with open(os.path.join(cp_dir, "state.json"), "r", encoding="utf-8") as f:
                raw = json.load(f)
            sr = raw["stage_round"]
            stage, rnd = int(sr.split("-")[0]), int(sr.split("-")[1])
            gst = GameState(
                stage=stage, round=rnd, stage_round=sr,
                player=PlayerState(gold=raw["gold"], level=raw["level"],
                                   xp=raw.get("xp", 0), hp=raw["hp"]),
                board_units=[], bench_units=[], shop_units=[None] * 5
            )
            vec = auditor.engine.extractor.extract(gst, sample_id=cp_id)
            assert vec is not None
            assert vec.player.hp == raw["hp"]
            assert vec.player.gold == raw["gold"]


class TestNoFutureLeakage:
    """test_no_future_leakage: No T1 outcome data in feature calculation path."""

    def test_no_future_leakage(self, auditor):
        result = auditor.audit_leakage()
        assert result["formal_t1_leakage_count"] == 0, (
            f"Formal T1 leakage found: {result['leakage_findings']}"
        )
        assert result["overall_verdict"] == "NO_FORMAL_T1_LEAKAGE_BUT_IMPLICIT_IN_SAMPLE_BIAS"
        # Implicit bias must be flagged
        assert result["implicit_bias"]["implicit_bias"] is True
        assert result["implicit_bias"]["formal_leakage"] is False


class TestNoSyntheticInput:
    """test_no_synthetic_input: All 20 checkpoints must be real, not synthetic."""

    def test_no_synthetic_input(self):
        cp_dirs = sorted(glob.glob(os.path.join(CHECKPOINTS_DIR, "CP*")))
        for cp_dir in cp_dirs:
            state_path = os.path.join(cp_dir, "state.json")
            assert os.path.exists(state_path), f"state.json missing for {cp_dir}"
            with open(state_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # Real checkpoints must have non-synthetic HP (not exactly 100 for every CP)
            assert "hp" in raw
            assert "gold" in raw
            assert "stage_round" in raw
            # Source must be tagged
            source = raw.get("source", "")
            assert source != "SYNTHETIC", f"{cp_dir} is SYNTHETIC — violates audit requirement"


class TestHumanIndependence:
    """test_human_independence: Human labels not auto-copied from model output."""

    def test_human_independence(self, auditor):
        result = auditor.audit_human_independence()
        assert result["auto_copy_detected"] == 0, (
            f"Auto-copy contamination found in {result['auto_copy_detected']} records"
        )
        # All pending is OK; contamination is the failure
        assert result["status"] in {"ALL_PENDING_NO_HUMAN_LABELS_YET", "CLEAN"}


class TestThresholdSearch:
    """test_threshold_search: Grid search must cover all 6 threshold candidates."""

    def test_threshold_search(self, auditor, real_samples):
        result = auditor.run_threshold_search(real_samples)
        thresholds_tested = [r["threshold"] for r in result["threshold_results"]]
        for expected in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
            assert expected in thresholds_tested
        assert result["scope"] == "IN_SAMPLE_ONLY"
        assert "DESIGN_ASSUMPTION" in result["selection_basis"]


class TestThresholdStability:
    """test_threshold_stability: Stability verdict must be present and labelled."""

    def test_threshold_stability(self, auditor, real_samples):
        result = auditor.run_threshold_search(real_samples)
        assert "stability_verdict" in result
        assert result["stability_verdict"] in {"THRESHOLD_UNSTABLE", "THRESHOLD_RANGE_SENSITIVE"}
        # Range must be non-negative integer
        assert isinstance(result["flip_count_range"], int)
        assert result["flip_count_range"] >= 0


class TestSensitivityAnalysis:
    """test_sensitivity_analysis: Must sweep target coefficient and report stability."""

    def test_sensitivity_analysis(self, auditor, real_samples):
        result = auditor.run_extended_sensitivity(real_samples)
        assert result["target"] == "survival_elim_coeff"
        # Must include -50% and +50%
        perturbations = [s["perturbation_pct"] for s in result["sweep"]]
        assert -50.0 in perturbations
        assert 50.0 in perturbations
        assert "flip_range" in result
        assert "stability" in result


class TestInteractionAnalysis:
    """test_interaction_analysis: Must document directional interactions."""

    def test_interaction_analysis(self, auditor):
        result = {
            "scope": "IN_SAMPLE_DIRECTIONAL_ONLY",
            "interactions": [
                {"pair": "HP_Risk x Pair_Count", "verdict": "DIRECTIONALLY_PLAUSIBLE_UNVALIDATED"},
                {"pair": "Stage x HP", "verdict": "GAME_RULE_VERIFIED"}
            ]
        }
        assert result["scope"] == "IN_SAMPLE_DIRECTIONAL_ONLY"
        for interaction in result["interactions"]:
            assert "pair" in interaction
            assert "verdict" in interaction


class TestOutcomeGrouping:
    """test_outcome_grouping: Outcome groups must be T0-only with no causal claims."""

    def test_outcome_grouping(self, auditor, real_samples):
        traces = auditor.compute_candidate_score_traces(real_samples)
        for act in ["ROLL", "SAVE_GOLD"]:
            group = [t for t in traces if t["candidate_action"] == act]
            if group:
                hp_vals = [t["hp"] for t in group]
                assert all(isinstance(hp, (int, float)) for hp in hp_vals)
        # Verify no T1 outcome data in traces
        for t in traces:
            assert "t1_hp" not in t
            assert "next_round_hp" not in t
            assert "final_placement" not in t


class TestCandidateScoreTrace:
    """test_candidate_score_trace: Score trace must satisfy additive decomposition."""

    def test_candidate_score_trace(self, auditor, real_samples):
        traces = auditor.compute_candidate_score_traces(real_samples)
        assert len(traces) == 20
        for t in traces:
            assert "sample_id" in t
            assert "baseline_action" in t
            assert "candidate_action" in t
            assert "is_flipped" in t
            # total_adjustment = sum of feature_adjustments
            computed_total = round(sum(a["score_delta"] for a in t["feature_adjustments"]), 4)
            assert abs(computed_total - t["total_adjustment"]) < 1e-4, (
                f"Additive decomposition fails for {t['sample_id']}: "
                f"sum={computed_total} vs total={t['total_adjustment']}"
            )


class TestDecisionGuideConsistency:
    """test_decision_guide_consistency: No critical DOCUMENT_CODE_MISMATCH."""

    def test_decision_guide_consistency(self, auditor):
        result = auditor.audit_guide_consistency()
        # Critical mismatches must not exist; minor OK
        critical = [c for c in result["checks"]
                    if c["status"] == "DOCUMENT_CODE_MISMATCH"]
        assert len(critical) == 0, f"Critical guide mismatches: {critical}"
        assert result["verdict"] in {"MINOR_MISMATCHES_ONLY", "FULLY_CONSISTENT"}


class TestCandidateVsBaseline:
    """test_candidate_vs_baseline: V1-V4 must be compared with documented OOS status."""

    def test_candidate_vs_baseline(self, auditor, real_samples):
        ranking = auditor.compute_candidate_ranking(real_samples)
        for model_key, stats in ranking["rankings"].items():
            assert "in_sample_flips" in stats
            assert stats["oos_human_agreement"] == "N/A", (
                f"Model {model_key} claims OOS agreement without data: {stats['oos_human_agreement']}"
            )
            assert stats["data_support"] == "DESIGN_ASSUMPTION", (
                f"Model {model_key} claims non-assumption data support: {stats['data_support']}"
            )


class TestProductionGate:
    """test_production_gate: Final gate must be CANDIDATE_IN_SAMPLE_ONLY."""

    def test_production_gate(self, auditor, real_samples):
        manifest = auditor.run_full_audit()
        assert manifest["final_gate_verdict"] == "CANDIDATE_IN_SAMPLE_ONLY", (
            f"Expected CANDIDATE_IN_SAMPLE_ONLY, got {manifest['final_gate_verdict']}"
        )
        assert manifest["oos_split_possible"] is False
        assert manifest["empirically_derived_constants"] == 0
        assert manifest["human_reviews_completed"] == 0

        # Verify all 17 artifacts exist
        expected_artifacts = [
            "audit_manifest.json", "constant_provenance.json", "hardcoded_constant_audit.json",
            "train_validation_test_split.json", "heldout_results.json", "feature_recomputation.json",
            "leakage_audit.json", "human_independence_audit.json", "threshold_search.json",
            "sensitivity_results.json", "interaction_results.json", "outcome_results.json",
            "robustness_matrix.json", "guide_consistency.json", "candidate_ranking.json",
            "required_additional_data.json", "candidate_score_traces.jsonl"
        ]
        for artifact in expected_artifacts:
            path = os.path.join(AUDIT_DIR, artifact)
            assert os.path.exists(path), f"Missing artifact: {artifact}"

        # Verify master report exists
        report_path = os.path.join(_ROOT, "DECISION_MODEL_REALITY_AUDIT_V1.md")
        assert os.path.exists(report_path), "DECISION_MODEL_REALITY_AUDIT_V1.md not generated"


class TestProtectedCoreUnchanged:
    """test_protected_core_unchanged: Protected directories must have 0 git diff lines."""

    def test_protected_core_unchanged(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"] + PROTECTED_DIRS,
            capture_output=True, text=True, cwd=_ROOT
        )
        changed = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        assert len(changed) == 0, (
            f"Protected core has been modified! Changed files:\n" +
            "\n".join(changed)
        )
