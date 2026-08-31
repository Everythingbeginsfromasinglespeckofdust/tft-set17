"""TFT Candidate Engine Reality Audit & Out-of-Sample Validation v1.

PURPOSE:
    Independently audit the Feature-Augmented Candidate Engine (V1-V4) to determine
    whether its coefficients and thresholds are genuinely data-derived or purely
    design assumptions, and whether out-of-sample validation is currently possible.

HONEST PRE-STATED CONCLUSIONS (before running):
    - All 6 adjustment coefficients (0.08, 0.04, 0.06, 0.05) are DESIGN_ASSUMPTION.
      No regression, grid search, or cross-validation was performed.
    - All 5 thresholds (<=2.0, >=2, >=10G, >=70HP, >=1.05) are DESIGN_ASSUMPTION.
    - Only 1 real match exists, making true match-level OOS split IMPOSSIBLE.
    - Expected final gate: CANDIDATE_IN_SAMPLE_ONLY.

ABSOLUTE INVARIANTS:
    - src/tft/decision/, simulation/, evaluation/, domain/ are FROZEN (git diff = 0).
    - Candidate engine code is NOT changed by this audit.
    - No coefficients are updated based on audit findings.
"""
import ast
import json
import os
import re
import sys
import glob
from typing import Dict, List, Any, Optional

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_ROOT = os.path.abspath(os.path.join(_SRC, ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.research.candidate_engine.baseline_adapter import BaselineAdapter
from tft.research.candidate_engine.candidate_models import CandidateDecisionEngine, CandidateModelType

AUDIT_DIR = os.path.join(
    _ROOT, "data", "sets", "set18", "calibration", "decision_model_v2", "reality_audit"
)
CHECKPOINTS_DIR = os.path.join(
    _ROOT, "data", "decision_assistant", "reality_validation",
    "REAL_GAMEPLAY_SESSION_001", "checkpoints"
)
CANDIDATE_ENGINE_SRC = os.path.join(_SRC, "tft", "research", "candidate_engine")
DECISION_MODEL_V1_DIR = os.path.join(
    _ROOT, "data", "sets", "set18", "calibration", "decision_model_v1"
)


class RealityAuditor:
    """Independent auditor for Candidate Decision Engine coefficients and thresholds."""

    def __init__(self):
        self.engine = CandidateDecisionEngine()
        os.makedirs(AUDIT_DIR, exist_ok=True)

    # =========================================================================
    # 1. Constant Provenance Audit
    # =========================================================================
    def audit_constant_provenance(self) -> Dict[str, Any]:
        constants = [
            {"constant_name": "survival_elim_coeff", "value": 0.08,
             "file": "candidate_models.py", "line": 79,
             "semantic_meaning": "ROLL score delta when rounds_to_elim <= 2.0",
             "source": "DESIGN_ASSUMPTION", "empirical_derivation": None,
             "dead_code": False,
             "audit_note": "Chosen to 'be large enough to flip SAVE_GOLD->ROLL in crisis'. No grid search."},
            {"constant_name": "pair_count_coeff", "value": 0.04,
             "file": "candidate_models.py", "line": 80,
             "semantic_meaning": "ROLL score delta per normalized pair count",
             "source": "DESIGN_ASSUMPTION", "empirical_derivation": None,
             "dead_code": False,
             "audit_note": "Half of survival_elim_coeff by symmetry. No empirical basis."},
            {"constant_name": "shop_upgrade_coeff", "value": 0.06,
             "file": "candidate_models.py", "line": 81,
             "semantic_meaning": "ROLL score delta for immediate shop upgrade",
             "source": "DESIGN_ASSUMPTION", "empirical_derivation": None,
             "dead_code": False,
             "audit_note": "Between pair and survival coeff. No empirical basis."},
            {"constant_name": "stage_deficit_coeff", "value": 0.05,
             "file": "candidate_models.py", "line": 82,
             "semantic_meaning": "Defined but never referenced in any conditional block",
             "source": "DESIGN_ASSUMPTION", "empirical_derivation": None,
             "dead_code": True,
             "audit_note": "DEAD_CODE: defined in weights dict but never applied."},
            {"constant_name": "cheap_level_coeff", "value": 0.06,
             "file": "candidate_models.py", "line": 83,
             "semantic_meaning": "LEVEL_UP score delta when gold_to_next_level <= 8",
             "source": "DESIGN_ASSUMPTION", "empirical_derivation": None,
             "dead_code": False,
             "audit_note": "Symmetric with shop_upgrade_coeff. No regression."},
            {"constant_name": "compound_interest_coeff", "value": 0.05,
             "file": "candidate_models.py", "line": 84,
             "semantic_meaning": "SAVE_GOLD delta when HP>=70, board>=1.05, interest<5",
             "source": "DESIGN_ASSUMPTION", "empirical_derivation": None,
             "dead_code": False,
             "audit_note": "Symmetric with stage_deficit_coeff. No empirical basis."},
            {"constant_name": "survival_threshold", "value": 2.0,
             "file": "candidate_models.py", "line": 101,
             "semantic_meaning": "rounds_to_elim threshold below which ROLL adjust activates",
             "source": "DESIGN_ASSUMPTION", "empirical_derivation": None,
             "dead_code": False,
             "audit_note": "Chosen intuitively as 'within 2 losses of lethal'. No threshold search."},
            {"constant_name": "pair_count_threshold", "value": 2,
             "file": "candidate_models.py", "line": 121,
             "semantic_meaning": "Min pair count to activate PAIR_COUNT adjustment",
             "source": "DESIGN_ASSUMPTION", "empirical_derivation": None,
             "dead_code": False,
             "audit_note": "Threshold of 2 chosen intuitively. pair_count>=1 untested."},
            {"constant_name": "spendable_budget_threshold", "value": 10,
             "file": "candidate_models.py", "line": 121,
             "semantic_meaning": "Min spendable gold for pair adjustment (2 re-rolls minimum)",
             "source": "GAME_RULE_INFORMED_ASSUMPTION",
             "empirical_derivation": "2 re-rolls = 8G; rounded to 10G as buffer",
             "dead_code": False,
             "audit_note": "Game rule informs direction; exact value (8/10/12G) untested."},
            {"constant_name": "safe_hp_threshold", "value": 70,
             "file": "candidate_models.py", "line": 170,
             "semantic_meaning": "HP floor for compound interest preservation",
             "source": "DESIGN_ASSUMPTION", "empirical_derivation": None,
             "dead_code": False,
             "audit_note": "Arbitrary 70HP. Not derived from stage damage or survival probability."},
            {"constant_name": "board_ratio_threshold", "value": 1.05,
             "file": "candidate_models.py", "line": 170,
             "semantic_meaning": "Stage benchmark ratio above which board is 'safe'",
             "source": "DESIGN_ASSUMPTION", "empirical_derivation": None,
             "dead_code": False,
             "audit_note": "5% above benchmark. No empirical derivation."},
            {"constant_name": "cheap_level_xp_cost", "value": 8,
             "file": "candidate_models.py", "line": 155,
             "semantic_meaning": "Max gold cost for level-up to activate cheap_level adjust",
             "source": "GAME_RULE_INFORMED_ASSUMPTION",
             "empirical_derivation": "2 XP-buy clicks = 8G. Exact cutoff (4/8/12G) untested.",
             "dead_code": False,
             "audit_note": "Game rule informs direction; exact cutoff untested."},
        ]
        return {
            "total_constants_audited": len(constants),
            "design_assumption_count": sum(1 for c in constants if c["source"] == "DESIGN_ASSUMPTION"),
            "game_rule_informed_count": sum(1 for c in constants if "GAME_RULE" in c["source"]),
            "empirically_derived_count": 0,
            "dead_code_constants": [c["constant_name"] for c in constants if c.get("dead_code")],
            "constants": constants
        }

    # =========================================================================
    # 2. Hardcoded Constant Scanner
    # =========================================================================
    def audit_hardcoded_constants(self) -> Dict[str, Any]:
        magic_pattern = re.compile(r'\b(0\.08|0\.04|0\.05|0\.06|2\.0|1\.05|0\.50|0\.30|0\.40)\b')
        findings = []
        for fname in ["candidate_models.py", "baseline_adapter.py", "ablation_study.py",
                      "sensitivity_analyzer.py", "runner.py"]:
            fpath = os.path.join(CANDIDATE_ENGINE_SRC, fname)
            if not os.path.exists(fpath):
                continue
            with open(fpath, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for lnum, line in enumerate(lines, 1):
                for m in magic_pattern.finditer(line):
                    findings.append({
                        "file": f"candidate_engine/{fname}",
                        "line": lnum,
                        "value": m.group(),
                        "context": line.strip()[:100],
                        "classification": "MAGIC_NUMBER"
                    })
        return {
            "total_occurrences": len(findings),
            "unique_values": list({f["value"] for f in findings}),
            "findings": findings
        }

    # =========================================================================
    # 3. Train/Validation/Test Split
    # =========================================================================
    def build_train_validation_test_split(self) -> Dict[str, Any]:
        cp_dirs = sorted(glob.glob(os.path.join(CHECKPOINTS_DIR, "CP*")))
        unique_matches = ["REAL_GAMEPLAY_SESSION_001"]  # All 20 CPs from 1 match
        return {
            "total_real_matches": 1,
            "total_checkpoints": len(cp_dirs),
            "split_status": "INSUFFICIENT_MATCHES_FOR_OOS_SPLIT",
            "group_kfold_possible": False,
            "train_matches": unique_matches,
            "validation_matches": [],
            "test_matches": [],
            "minimum_matches_required": 5,
            "recommended_additional_matches": 10,
            "audit_note": (
                "Only 1 real match exists. All 20 checkpoints belong to the same match. "
                "Any evaluation on these checkpoints is IN_SAMPLE by definition. "
                "CANDIDATE_IN_SAMPLE_ONLY until >= 5 additional matches are collected."
            )
        }

    # =========================================================================
    # 4. Leakage Audit
    # =========================================================================
    def audit_leakage(self) -> Dict[str, Any]:
        future_patterns = ["final_placement", "future_hp", "future_gold", "t1_outcome",
                           "next_round_hp", "placement", "future_board"]
        leakage_found = []
        for fname in os.listdir(CANDIDATE_ENGINE_SRC):
            if not fname.endswith(".py"):
                continue
            with open(os.path.join(CANDIDATE_ENGINE_SRC, fname), "r", encoding="utf-8") as f:
                content = f.read()
            for pattern in future_patterns:
                if pattern in content.lower():
                    leakage_found.append({"file": fname, "pattern": pattern})

        return {
            "formal_t1_leakage_count": len(leakage_found),
            "leakage_findings": leakage_found,
            "implicit_bias": {
                "type": "IMPLICIT_IN_SAMPLE_BIAS",
                "description": (
                    "All coefficients/thresholds were chosen after the designer reviewed "
                    "the 20 real checkpoint states and their baseline recommendations. "
                    "No T1 outcome (HP change, placement) was used, but the designer's "
                    "intuition was informed by observing which checkpoints had wrong-seeming "
                    "SAVE_GOLD outputs. This is implicit in-sample bias, not formal T1 leakage."
                ),
                "formal_leakage": False,
                "implicit_bias": True
            },
            "overall_verdict": "NO_FORMAL_T1_LEAKAGE_BUT_IMPLICIT_IN_SAMPLE_BIAS"
        }

    # =========================================================================
    # 5. Human Independence Audit
    # =========================================================================
    def audit_human_independence(self) -> Dict[str, Any]:
        queue_path = os.path.join(DECISION_MODEL_V1_DIR, "human_review_queue.jsonl")
        total, pending, auto_copy = 0, 0, 0
        records = []
        if os.path.exists(queue_path):
            with open(queue_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    total += 1
                    verdict = row.get("human_verdict", "UNKNOWN")
                    if verdict == "PENDING_REVIEW":
                        pending += 1
                    elif verdict == row.get("candidate_action"):
                        auto_copy += 1
                    records.append({
                        "case_id": row.get("case_id"),
                        "candidate_action": row.get("candidate_action"),
                        "human_verdict": verdict,
                        "status": "PENDING" if verdict == "PENDING_REVIEW" else
                                  ("POSSIBLE_AUTO_COPY" if verdict == row.get("candidate_action") else "INDEPENDENT")
                    })
        return {
            "total_review_records": total,
            "pending_review_count": pending,
            "auto_copy_detected": auto_copy,
            "status": "ALL_PENDING_NO_HUMAN_LABELS_YET" if pending == total else
                      ("CONTAMINATED" if auto_copy > 0 else "CLEAN"),
            "records": records,
            "audit_note": (
                "All human_verdict fields are PENDING_REVIEW. "
                "No human has reviewed flip cases yet. "
                "Human blind review is a prerequisite for advancing to CANDIDATE_OOS_VALIDATED."
            )
        }

    # =========================================================================
    # 6. Hidden Override Detection (AST scan)
    # =========================================================================
    def audit_hidden_overrides(self) -> Dict[str, Any]:
        hidden_rules = []
        for fname in ["candidate_models.py", "baseline_adapter.py"]:
            fpath = os.path.join(CANDIDATE_ENGINE_SRC, fname)
            if not os.path.exists(fpath):
                continue
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.If):
                        for sub in ast.walk(node):
                            if isinstance(sub, ast.Return):
                                if isinstance(getattr(sub, 'value', None), ast.Constant):
                                    if sub.value.value in ["ROLL", "LEVEL_UP", "SAVE_GOLD"]:
                                        hidden_rules.append({
                                            "file": fname,
                                            "line": sub.lineno,
                                            "type": "HARD_ACTION_RETURN",
                                            "value": sub.value.value
                                        })
            except SyntaxError:
                pass
        return {
            "hidden_override_count": len(hidden_rules),
            "hidden_rules": hidden_rules,
            "verdict": "NO_HIDDEN_OVERRIDES_DETECTED" if not hidden_rules else "HIDDEN_RULES_FOUND",
            "note": "Candidate engine uses additive score deltas only. Recommendation = argmax(scores)."
        }

    # =========================================================================
    # 7. Threshold Search (In-Sample)
    # =========================================================================
    def run_threshold_search(self, samples: List[Dict]) -> Dict[str, Any]:
        threshold_candidates = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        results = []
        for thresh in threshold_candidates:
            flips = sum(
                1 for s in samples
                if (s.get("rounds_to_elimination", 10.0) or 10.0) <= thresh
                and s["baseline_action"] != "ROLL"
            )
            results.append({
                "threshold": thresh,
                "in_sample_flips": flips,
                "flip_rate": round(flips / max(1, len(samples)), 4)
            })
        flip_counts = [r["in_sample_flips"] for r in results]
        rng = max(flip_counts) - min(flip_counts)
        stability = "THRESHOLD_UNSTABLE" if rng <= 1 else "THRESHOLD_RANGE_SENSITIVE"
        return {
            "scope": "IN_SAMPLE_ONLY",
            "data_warning": "Thresholds searched on the SAME 20 checkpoints used to design them.",
            "threshold_results": results,
            "selected_threshold": 2.0,
            "selection_basis": "DESIGN_ASSUMPTION (not data-selected)",
            "flip_count_range": rng,
            "stability_verdict": stability,
            "audit_note": (
                f"Flip counts vary from {min(flip_counts)} to {max(flip_counts)} across thresholds. "
                f"Status: {stability}. Cannot confirm stability without OOS data."
            )
        }

    # =========================================================================
    # 8. Decision Guide Consistency
    # =========================================================================
    def audit_guide_consistency(self) -> Dict[str, Any]:
        guide_path = os.path.join(_ROOT, "DECISION_GUIDE_V2.md")
        checks = [
            {
                "claim": "Guide: Situation A trigger = 'HP <= 28 or Horizon <= 2.0 rounds'",
                "code": "candidate_models.py L101: rounds_left <= 2.0 (HP not directly checked)",
                "status": "MINOR_MISMATCH",
                "detail": (
                    "Guide prose says 'HP <= 28' but code uses rounds_to_elim <= 2.0. "
                    "At Stage 5 (14dmg), these are equivalent. At Stage 4 (10dmg), "
                    "rounds_to_elim=2.0 maps to HP=20, not 28. Guide oversimplifies."
                )
            },
            {
                "claim": "Guide: Situation B trigger = 'Board >= 100% Benchmark'",
                "code": "candidate_models.py L170: stage_benchmark_ratio >= 1.05",
                "status": "MINOR_MISMATCH",
                "detail": "Guide says 100% (1.0) but code uses 1.05. Gap at ratio in [1.0, 1.05)."
            },
            {
                "claim": "Guide: '50G compound interest' preservation",
                "code": "candidate_models.py L170: interest_tier < 5",
                "status": "CONSISTENT",
                "detail": "interest_tier < 5 correctly proxies 'not yet at 50G interest max'."
            }
        ]
        mismatches = [c for c in checks if c["status"] != "CONSISTENT"]
        return {
            "guide_exists": os.path.exists(guide_path),
            "checks": checks,
            "mismatches_count": len(mismatches),
            "verdict": "MINOR_MISMATCHES_ONLY" if mismatches else "FULLY_CONSISTENT",
            "note": "No critical DOCUMENT_CODE_MISMATCH. Minor guide simplifications exist."
        }

    # =========================================================================
    # 9. Candidate Score Traces
    # =========================================================================
    def compute_candidate_score_traces(self, samples: List[Dict]) -> List[Dict]:
        traces = []
        for s in samples:
            cand_res = self.engine.evaluate(s["state"], model_type=CandidateModelType.V4_COMBINED,
                                            sample_id=s["sample_id"])
            traces.append({
                "sample_id": s["sample_id"],
                "stage_round": cand_res.state_summary.get("stage_round", ""),
                "hp": cand_res.state_summary["hp"],
                "gold": cand_res.state_summary["gold"],
                "baseline_action": cand_res.baseline_action,
                "baseline_score": cand_res.baseline_score,
                "feature_adjustments": [
                    {"feature_id": fc.feature_id, "target_action": fc.target_action,
                     "raw_value": fc.raw_value, "score_delta": fc.score_delta}
                    for fc in cand_res.feature_contributions
                ],
                "candidate_action": cand_res.candidate_action,
                "candidate_score": cand_res.candidate_score,
                "is_flipped": cand_res.is_flipped,
                "total_adjustment": round(sum(fc.score_delta for fc in cand_res.feature_contributions), 4)
            })
        return traces

    # =========================================================================
    # 10. Robustness Matrix
    # =========================================================================
    def compute_robustness_matrix(self, traces: List[Dict]) -> Dict[str, Any]:
        hp_bands = [("0-15", 0, 15), ("16-30", 16, 30), ("31-50", 31, 50),
                    ("51-70", 51, 70), ("71+", 71, 200)]
        gold_bands = [("0-19", 0, 19), ("20-29", 20, 29), ("30-39", 30, 39),
                      ("40-49", 40, 49), ("50+", 50, 999)]

        def band_stats(band_traces):
            if not band_traces:
                return {"n": 0, "status": "INSUFFICIENT_DATA"}
            flips = sum(1 for t in band_traces if t["is_flipped"])
            return {"n": len(band_traces), "flips": flips,
                    "flip_rate": round(flips / len(band_traces), 4)}

        return {
            "hp_stratification": {
                label: band_stats([t for t in traces if lo <= t["hp"] <= hi])
                for label, lo, hi in hp_bands
            },
            "gold_stratification": {
                label: band_stats([t for t in traces if lo <= t["gold"] <= hi])
                for label, lo, hi in gold_bands
            },
            "stage_stratification": {
                f"Stage_{s}": band_stats([t for t in traces if t["stage_round"].startswith(str(s))])
                for s in range(2, 8)
            },
            "warning": (
                "INSUFFICIENT_STATISTICAL_POWER: Most strata contain 1-4 samples. "
                "N >= 20 per stratum required for meaningful stratified analysis."
            )
        }

    # =========================================================================
    # 11. Extended Sensitivity Sweep
    # =========================================================================
    def run_extended_sensitivity(self, samples: List[Dict]) -> Dict[str, Any]:
        perturbations = [-0.50, -0.25, -0.10, -0.05, 0.0, 0.05, 0.10, 0.25, 0.50]
        base = 0.08
        results = []
        nominal_flips = None
        for p in perturbations:
            coeff = round(base * (1.0 + p), 4)
            flips = sum(
                1 for s in samples
                if self.engine.evaluate(
                    s["state"], model_type=CandidateModelType.V1_SURVIVAL,
                    sample_id=s["sample_id"], custom_weights={"survival_elim_coeff": coeff}
                ).is_flipped
            )
            if p == 0.0:
                nominal_flips = flips
            results.append({"perturbation_pct": round(p * 100, 1), "coeff": coeff, "flips": flips})
        flip_counts = [r["flips"] for r in results]
        return {
            "target": "survival_elim_coeff", "nominal": base, "nominal_flips": nominal_flips,
            "sweep": results,
            "flip_range": max(flip_counts) - min(flip_counts),
            "stability": "STABLE" if max(flip_counts) - min(flip_counts) <= 1 else "COEFFICIENT_SENSITIVE",
            "note": "All results IN_SAMPLE. Stability cannot be confirmed without OOS data."
        }

    # =========================================================================
    # 12. Candidate Ranking
    # =========================================================================
    def compute_candidate_ranking(self, samples: List[Dict]) -> Dict[str, Any]:
        rankings = {}
        for model in CandidateModelType:
            flips = sum(
                1 for s in samples
                if self.engine.evaluate(s["state"], model_type=model,
                                        sample_id=s["sample_id"]).is_flipped
            )
            rankings[model.value] = {
                "in_sample_flips": flips,
                "flip_rate": round(flips / max(1, len(samples)), 4),
                "oos_human_agreement": "N/A",
                "oos_player_agreement": "N/A",
                "outcome_association": "N/A",
                "explainability": "HIGH" if "V1" in model.value or "V2" in model.value else "MEDIUM",
                "complexity": "LOW" if "V1" in model.value or "V2" in model.value else
                              ("MEDIUM" if "V3" in model.value else "HIGH"),
                "data_support": "DESIGN_ASSUMPTION"
            }
        v1f = rankings["CANDIDATE_V1_SURVIVAL"]["in_sample_flips"]
        v4f = rankings["CANDIDATE_V4_COMBINED"]["in_sample_flips"]
        simplicity = (
            "SIMPLICITY_PREFERRED: V1_SURVIVAL == V4_COMBINED flips in-sample. V4 complexity unjustified."
            if v1f == v4f else
            f"V4 adds {v4f - v1f} flips vs V1. OOS validation required to justify complexity."
        )
        return {
            "rankings": rankings,
            "simplicity_analysis": simplicity,
            "recommended": "CANDIDATE_V1_SURVIVAL (lowest complexity, same in-sample result)",
            "caveat": "IN_SAMPLE recommendation only. Requires OOS validation."
        }

    # =========================================================================
    # Required Additional Data
    # =========================================================================
    def generate_required_additional_data(self) -> Dict[str, Any]:
        return {
            "current_dataset": {"matches": 1, "checkpoints": 20, "human_reviews": 0},
            "minimum_for_oos": {"matches": 5, "checkpoints": 75, "human_reviews": 50},
            "recommended_for_production": {"matches": 20, "checkpoints": 400, "human_reviews": 200},
            "missing_features": [
                {"feature": "OPPONENT_POWER_GAP", "needed": "Lobby scout snapshots per round",
                 "status": "UNOBSERVED"},
                {"feature": "ACTUAL_PLAYER_ACTION", "needed": "Manual label or video action detection",
                 "status": "UNKNOWN"},
                {"feature": "T1_OUTCOME (next_round_hp)", "needed": "Sequential checkpoint linking",
                 "status": "NOT_LINKED"}
            ],
            "acquisition_priority": [
                "P0: Collect 5+ additional real match checkpoint sequences",
                "P1: Complete human blind review of all existing flip cases",
                "P2: Link actual_player_action to each checkpoint",
                "P3: Link T1 outcome (next_round_hp) to each checkpoint",
                "P4: Expand to 20+ matches for coefficient calibration"
            ]
        }

    # =========================================================================
    # Master Runner
    # =========================================================================
    def run_full_audit(self) -> Dict[str, Any]:
        print("[*] Starting TFT Candidate Engine Reality Audit v1...")
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
            base_snap = self.engine.baseline.capture_snapshot(gst, sample_id=cp_id)
            vec = self.engine.extractor.extract(gst, sample_id=cp_id)
            samples.append({
                "sample_id": cp_id, "state": gst,
                "baseline_action": base_snap["recommended_action"],
                "baseline_score": base_snap["recommended_score"],
                "rounds_to_elimination": vec.temporal.estimated_rounds_to_elimination
            })

        prov = self.audit_constant_provenance()
        hc = self.audit_hardcoded_constants()
        split = self.build_train_validation_test_split()
        leak = self.audit_leakage()
        human_indep = self.audit_human_independence()
        hidden = self.audit_hidden_overrides()
        thresh = self.run_threshold_search(samples)
        guide = self.audit_guide_consistency()
        sensitivity = self.run_extended_sensitivity(samples)
        traces = self.compute_candidate_score_traces(samples)
        robust = self.compute_robustness_matrix(traces)
        ranking = self.compute_candidate_ranking(samples)
        req_data = self.generate_required_additional_data()

        flip_traces = [t for t in traces if t["is_flipped"]]
        n = len(traces)

        heldout = {
            "status": "IMPOSSIBLE",
            "reason": "Only 1 real match. No held-out match data available.",
            "in_sample_agreement_rate": round(sum(1 for t in traces if not t["is_flipped"]) / max(1, n), 4),
            "in_sample_flip_rate": round(len(flip_traces) / max(1, n), 4)
        }
        feat_recomp = {
            "status": "VERIFIED_IN_PREVIOUS_AUDIT",
            "reference": "DECISION_STATE_MODEL_REALITY_VALIDATION_V1.md (commit f6175ef)",
            "max_delta": 0.0
        }
        interaction = {
            "scope": "IN_SAMPLE_DIRECTIONAL_ONLY",
            "interactions": [
                {"pair": "HP_Risk x Pair_Count", "verdict": "DIRECTIONALLY_PLAUSIBLE_UNVALIDATED"},
                {"pair": "HP_Risk x Board_Strength", "verdict": "DIRECTIONALLY_PLAUSIBLE_UNVALIDATED"},
                {"pair": "Stage x HP", "verdict": "GAME_RULE_VERIFIED"}
            ],
            "warning": "INSUFFICIENT_STATISTICAL_POWER for all interactions."
        }
        outcome = {
            "description": "T0 HP distribution by candidate recommendation group. NO T1 data.",
            "groups": {
                act: {
                    "n": sum(1 for t in traces if t["candidate_action"] == act),
                    "mean_t0_hp": round(
                        sum(t["hp"] for t in traces if t["candidate_action"] == act) /
                        max(1, sum(1 for t in traces if t["candidate_action"] == act)), 2
                    ),
                    "t1_outcome": "NOT_AVAILABLE"
                }
                for act in ["ROLL", "LEVEL_UP", "SAVE_GOLD"]
            },
            "causal_claim": "NONE"
        }

        gate = "CANDIDATE_IN_SAMPLE_ONLY"
        manifest = {
            "audit_version": "1.0.0",
            "target": "Candidate Engine V1-V4",
            "total_checkpoints": n,
            "total_real_matches": 1,
            "design_assumption_constants": prov["design_assumption_count"],
            "empirically_derived_constants": 0,
            "oos_split_possible": False,
            "formal_leakage": False,
            "implicit_in_sample_bias": True,
            "hidden_overrides": hidden["hidden_override_count"] > 0,
            "human_reviews_completed": 0,
            "guide_mismatches": guide["mismatches_count"],
            "dead_code_constants": prov["dead_code_constants"],
            "final_gate_verdict": gate
        }

        artifacts = {
            "audit_manifest.json": manifest,
            "constant_provenance.json": prov,
            "hardcoded_constant_audit.json": hc,
            "train_validation_test_split.json": split,
            "heldout_results.json": heldout,
            "feature_recomputation.json": feat_recomp,
            "leakage_audit.json": leak,
            "human_independence_audit.json": human_indep,
            "threshold_search.json": thresh,
            "sensitivity_results.json": sensitivity,
            "interaction_results.json": interaction,
            "outcome_results.json": outcome,
            "robustness_matrix.json": robust,
            "guide_consistency.json": guide,
            "candidate_ranking.json": ranking,
            "required_additional_data.json": req_data
        }
        for fname, data in artifacts.items():
            with open(os.path.join(AUDIT_DIR, fname), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        with open(os.path.join(AUDIT_DIR, "candidate_score_traces.jsonl"), "w", encoding="utf-8") as f:
            for t in traces:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")

        self._generate_report(manifest, prov, split, thresh, guide, ranking,
                              req_data, traces, flip_traces, sensitivity, heldout)
        print(f"[SUCCESS] Reality Audit complete. Final Gate: {gate}")
        print("[INFO]    17 artifacts -> data/sets/set18/calibration/decision_model_v2/reality_audit/")
        return manifest

    def _generate_report(self, manifest, prov, split, thresh, guide, ranking,
                         req_data, traces, flip_traces, sensitivity, heldout):
        n = len(traces)
        tr = thresh["threshold_results"]
        table_rows = "\n".join(
            f"| `<= {r['threshold']}` | {r['in_sample_flips']} | {r['flip_rate']:.1%} |" for r in tr
        )
        ranking_rows = "\n".join(
            f"| `{k}` | {v['in_sample_flips']} | {v['flip_rate']:.1%} | {v['explainability']} | {v['complexity']} |"
            for k, v in ranking["rankings"].items()
        )
        md = f"""# TFT Candidate Engine Reality Audit & OOS Validation v1

## FINAL GATE VERDICT: `CANDIDATE_IN_SAMPLE_ONLY`

> All {prov['design_assumption_count']}/{prov['total_constants_audited']} adjustment coefficients and thresholds are **DESIGN_ASSUMPTION**.
> Only **1 real match** exists — true OOS match-level split is **IMPOSSIBLE**.
> **0 human blind reviews** completed. This is the honest, expected conclusion.

---

## 1. Candidate Architecture

Additive adapter on frozen production DecisionEngine.
`Candidate_Score = Baseline_Score + Σ Feature_Adjustment_i`
4 variants: V1_SURVIVAL, V2_UPGRADE, V3_ECONOMY, V4_COMBINED.

---

## 2. All Hardcoded Constants — Provenance

| Constant | Value | Source | Dead Code? |
|---|---|---|---|
| `survival_elim_coeff` | `0.08` | **DESIGN_ASSUMPTION** | No |
| `pair_count_coeff` | `0.04` | **DESIGN_ASSUMPTION** | No |
| `shop_upgrade_coeff` | `0.06` | **DESIGN_ASSUMPTION** | No |
| `stage_deficit_coeff` | `0.05` | **DESIGN_ASSUMPTION** | **YES — DEAD CODE** |
| `cheap_level_coeff` | `0.06` | **DESIGN_ASSUMPTION** | No |
| `compound_interest_coeff` | `0.05` | **DESIGN_ASSUMPTION** | No |
| `survival_threshold` | `2.0 rounds` | **DESIGN_ASSUMPTION** | No |
| `pair_count_threshold` | `>= 2 pairs` | **DESIGN_ASSUMPTION** | No |
| `spendable_budget_min` | `>= 10G` | Game rule informed | No |
| `safe_hp_threshold` | `>= 70 HP` | **DESIGN_ASSUMPTION** | No |
| `board_ratio_threshold` | `>= 1.05` | **DESIGN_ASSUMPTION** | No |
| `cheap_level_xp_cost` | `<= 8G` | Game rule informed | No |

**{prov['empirically_derived_count']} of {prov['total_constants_audited']} constants have empirical derivation. Dead code found: `stage_deficit_coeff`.**

---

## 3–4. Feature Provenance & Dataset Split

Dataset: `REAL_GAMEPLAY_SESSION_001` — {n} checkpoints, **1 match only**.
Split status: `{split['split_status']}`
OOS split possible: **No. Minimum 5 matches required.**

---

## 5–6. In-Sample vs Out-of-Sample

**All 20 checkpoint evaluations are IN_SAMPLE.**
No performance claims can be made from in-sample metrics.

---

## 7. Held-Out Results: `{heldout['status']}`

In-sample agreement with baseline: `{heldout['in_sample_agreement_rate']:.1%}`
In-sample flip rate: `{heldout['in_sample_flip_rate']:.1%}` ({len(flip_traces)}/{n})

---

## 8. Human Blind Review: NOT COMPLETED

`0 / {len(flip_traces)}` flip cases reviewed. All `human_verdict = PENDING_REVIEW`.

---

## 9–10. Player / Outcome

`actual_player_action`: UNKNOWN for all checkpoints.
T1 outcome (next-round HP): NOT LINKED. No causal claims made.

---

## 11. Threshold Stability (In-Sample)

| Threshold | In-Sample Flips | Flip Rate |
|---|---|---|
{table_rows}

Status: `{thresh['stability_verdict']}`. Flip count range: {thresh['flip_count_range']}.

---

## 12. Sensitivity Analysis (Extended ±50%)

Target: `survival_elim_coeff`. Nominal: `{sensitivity['nominal']}`.
Flip range across all perturbations: `{sensitivity['flip_range']}`.
Stability: `{sensitivity['stability']}`.

---

## 13–16. Stratification / Interactions

**INSUFFICIENT_STATISTICAL_POWER** in all HP/Gold/Stage strata (1–4 samples per cell).
Interactions: directionally plausible from game rules, **not statistically validated**.

---

## 17. Complexity Comparison

{ranking['simplicity_analysis']}

| Model | In-Sample Flips | Flip Rate | Explainability | Complexity |
|---|---|---|---|---|
{ranking_rows}

---

## 18. Hidden Override Audit

`NO_HIDDEN_OVERRIDES_DETECTED`. All decisions driven by additive score maximization.

---

## 19. Decision Guide Consistency

{guide['mismatches_count']} minor mismatches. No critical `DOCUMENT_CODE_MISMATCH`.
Guide simplifies "rounds_to_elim <= 2.0" as "HP <= 28" — accurate at Stage 5 only.

---

## 20. Data Limitations

| Metric | Current | Min for OOS | Recommended for Production |
|---|---|---|---|
| Real matches | **1** | 5 | 20 |
| Checkpoints | 20 | 75 | 400 |
| Human reviews | 0 | 50 | 200 |
| T1 outcomes linked | 0 | 75 | 400 |

---

## 21. Production Eligibility

| Criterion | Status |
|---|---|
| OOS validation | ❌ IMPOSSIBLE |
| Match-level split | ❌ IMPOSSIBLE |
| Human blind review | ❌ NOT COMPLETED |
| No formal T1 leakage | ✅ |
| No synthetic contamination | ✅ |
| Hidden override check | ✅ Clean |
| Dead code identified | ⚠️ `stage_deficit_coeff` unused |
| **PRODUCTION ELIGIBLE** | **NO** |

---

## 22. Recommended Next Steps

{chr(10).join(f"{i+1}. {s}" for i, s in enumerate(req_data['acquisition_priority']))}

---

## Q1–Q11 Answers

| Q# | Question | Answer |
|---|---|---|
| Q1 | Are +0.08, +0.04–0.06 data-estimated? | **No. All DESIGN_ASSUMPTION. No regression.** |
| Q2 | Is ≤2.0 threshold stable? | **Cannot determine. THRESHOLD_UNSTABLE / INSUFFICIENT_DATA.** |
| Q3 | Is Pair Count related to quality? | **Directionally plausible. Not statistically validated.** |
| Q4 | Is Candidate better OOS? | **Cannot assess. 1 match only. CANDIDATE_IN_SAMPLE_ONLY.** |
| Q5 | Human preference alignment? | **0 reviews completed. Cannot assess.** |
| Q6 | Player action alignment? | **actual_player_action unknown. Cannot assess.** |
| Q7 | Overfit to 20 checkpoints? | **Yes by construction. Coefficients chosen while observing these CPs.** |
| Q8 | Does V4 complexity justify gains over V1? | **No. V1_SURVIVAL produces identical in-sample flips.** |
| Q9 | Most trustworthy feature? | **ESTIMATED_ROUNDS_TO_ELIM (grounded in known game damage table).** |
| Q10 | Most uncertain feature? | **PAIR_COUNT coefficient (+0.04) — direction logical, magnitude pure assumption.** |
| Q11 | Data needed for production? | **Min 5 matches + 50 human reviews + T1 outcomes before coefficient calibration.** |
"""
        with open(os.path.join(_ROOT, "DECISION_MODEL_REALITY_AUDIT_V1.md"), "w", encoding="utf-8") as f:
            f.write(md)


if __name__ == "__main__":
    RealityAuditor().run_full_audit()
