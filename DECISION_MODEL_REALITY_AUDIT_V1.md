# TFT Candidate Engine Reality Audit & OOS Validation v1

## FINAL GATE VERDICT: `CANDIDATE_IN_SAMPLE_ONLY`

> All 10/12 adjustment coefficients and thresholds are **DESIGN_ASSUMPTION**.
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

**0 of 12 constants have empirical derivation. Dead code found: `stage_deficit_coeff`.**

---

## 3–4. Feature Provenance & Dataset Split

Dataset: `REAL_GAMEPLAY_SESSION_001` — 20 checkpoints, **1 match only**.
Split status: `INSUFFICIENT_MATCHES_FOR_OOS_SPLIT`
OOS split possible: **No. Minimum 5 matches required.**

---

## 5–6. In-Sample vs Out-of-Sample

**All 20 checkpoint evaluations are IN_SAMPLE.**
No performance claims can be made from in-sample metrics.

---

## 7. Held-Out Results: `IMPOSSIBLE`

In-sample agreement with baseline: `50.0%`
In-sample flip rate: `50.0%` (10/20)

---

## 8. Human Blind Review: NOT COMPLETED

`0 / 10` flip cases reviewed. All `human_verdict = PENDING_REVIEW`.

---

## 9–10. Player / Outcome

`actual_player_action`: UNKNOWN for all checkpoints.
T1 outcome (next-round HP): NOT LINKED. No causal claims made.

---

## 11. Threshold Stability (In-Sample)

| Threshold | In-Sample Flips | Flip Rate |
|---|---|---|
| `<= 0.5` | 1 | 5.0% |
| `<= 1.0` | 1 | 5.0% |
| `<= 1.5` | 1 | 5.0% |
| `<= 2.0` | 2 | 10.0% |
| `<= 2.5` | 3 | 15.0% |
| `<= 3.0` | 4 | 20.0% |

Status: `THRESHOLD_RANGE_SENSITIVE`. Flip count range: 3.

---

## 12. Sensitivity Analysis (Extended ±50%)

Target: `survival_elim_coeff`. Nominal: `0.08`.
Flip range across all perturbations: `1`.
Stability: `STABLE`.

---

## 13–16. Stratification / Interactions

**INSUFFICIENT_STATISTICAL_POWER** in all HP/Gold/Stage strata (1–4 samples per cell).
Interactions: directionally plausible from game rules, **not statistically validated**.

---

## 17. Complexity Comparison

SIMPLICITY_PREFERRED: V1_SURVIVAL == V4_COMBINED flips in-sample. V4 complexity unjustified.

| Model | In-Sample Flips | Flip Rate | Explainability | Complexity |
|---|---|---|---|---|
| `CANDIDATE_V1_SURVIVAL` | 10 | 50.0% | HIGH | LOW |
| `CANDIDATE_V2_UPGRADE` | 10 | 50.0% | HIGH | LOW |
| `CANDIDATE_V3_ECONOMY` | 10 | 50.0% | MEDIUM | MEDIUM |
| `CANDIDATE_V4_COMBINED` | 10 | 50.0% | MEDIUM | HIGH |

---

## 18. Hidden Override Audit

`NO_HIDDEN_OVERRIDES_DETECTED`. All decisions driven by additive score maximization.

---

## 19. Decision Guide Consistency

2 minor mismatches. No critical `DOCUMENT_CODE_MISMATCH`.
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

1. P0: Collect 5+ additional real match checkpoint sequences
2. P1: Complete human blind review of all existing flip cases
3. P2: Link actual_player_action to each checkpoint
4. P3: Link T1 outcome (next_round_hp) to each checkpoint
5. P4: Expand to 20+ matches for coefficient calibration

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
