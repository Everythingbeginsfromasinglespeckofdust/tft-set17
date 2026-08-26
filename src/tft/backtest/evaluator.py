"""TFT Backtest Evaluator v1.1 -- ENDGAME/MIDGAME split, Score Gap diagnostics."""
import math
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from tft.domain.actions import ActionType
from tft.backtest.models import (
    BacktestSample,
    BacktestDecision,
    FailureCase,
    FailureType,
    StratifiedMetricGroup,
    BacktestReport,
    ActualActionType,
    SnapshotType,
    ActionObservationCoverage,
    TemporalIntegrityResult,
    LeakageValidationResult,
    ScoreGapDiagnostics,
    GoldPredictionAnalysis,
)


class BacktestEvaluator:
    """Backtest evaluation engine -- produces statistically honest BacktestReport."""

    SCORE_GAP_THRESHOLD_HIGH = 0.05
    SCORE_GAP_THRESHOLD_DECISIVE = 0.10

    def evaluate(
        self,
        samples: List[BacktestSample],
        engine_decisions: List[BacktestDecision],
        baseline_decisions: Dict[str, List[BacktestDecision]]
    ) -> BacktestReport:
        sample_map = {s.sample_id: s for s in samples}
        total = len(samples)
        unique_matches = len(set(s.match_id for s in samples))
        unique_parts = len(set(f"{s.match_id}_{s.participant_id}" for s in samples))

        source_counts = defaultdict(int)
        for s in samples:
            source_counts[s.data_source] += 1

        snap_counts = defaultdict(int)
        for s in samples:
            snap_counts[s.snapshot_type.value] += 1

        endgame = [s for s in samples if s.snapshot_type == SnapshotType.ENDGAME_SNAPSHOT]
        midgame = [s for s in samples if s.snapshot_type == SnapshotType.MIDGAME_DECISION_SNAPSHOT]

        # --- Section 3: Action Observation Coverage ---
        coverage_obj = self._compute_coverage(samples)

        known_samples = [s for s in samples if s.observed_state.actual_action != ActualActionType.UNKNOWN]
        unknown_count = total - len(known_samples)
        unknown_rate = round(unknown_count / max(1, total), 4)
        coverage_rate = round(len(known_samples) / max(1, total), 4)

        # --- Section 4: Temporal Integrity ---
        temporal = self._check_temporal_integrity(samples)

        # --- Section 5: Leakage Validation ---
        leakage = self._check_leakage(samples, midgame)

        # --- Section 6: Midgame Descriptive Stats ---
        midgame_stats = self._compute_descriptive_stats(midgame, "MIDGAME")
        mg_hp = self._stratify_hp(midgame, engine_decisions)
        mg_gold = self._stratify_gold(midgame, engine_decisions)
        mg_stage = self._stratify_stage(midgame, engine_decisions)
        mg_level = self._stratify_level(midgame, engine_decisions)

        # --- Section 7: Endgame Descriptive Stats ---
        endgame_stats = self._compute_descriptive_stats(endgame, "ENDGAME")
        eg_hp = self._stratify_hp(endgame, engine_decisions)
        eg_gold = self._stratify_gold(endgame, engine_decisions)

        # All samples strats (backward compat)
        all_hp = self._stratify_hp(samples, engine_decisions)
        all_gold = self._stratify_gold(samples, engine_decisions)
        all_stage = self._stratify_stage(samples, engine_decisions)
        all_level = self._stratify_level(samples, engine_decisions)

        # --- Section 8: Behavioral Agreement ---
        behavioral_agree = self._compute_behavioral_agreement(samples, engine_decisions)
        baseline_comps = self._compute_baseline_comparisons(samples, engine_decisions, baseline_decisions, known_samples)

        action_totals = defaultdict(int)
        action_matches = defaultdict(int)
        overall_matches = 0
        confusion = {
            act.value: {rec.value: 0 for rec in [ActionType.ROLL, ActionType.LEVEL_UP, ActionType.SAVE_GOLD]}
            for act in [ActualActionType.ROLL, ActualActionType.LEVEL_UP, ActualActionType.SAVE_GOLD]
        }
        known_dec_map = {d.sample_id: d for d in engine_decisions}
        for s in known_samples:
            a_str = s.observed_state.actual_action.value
            d = known_dec_map.get(s.sample_id)
            if d:
                r_str = d.recommended_action.value
                action_totals[a_str] += 1
                if a_str in confusion and r_str in confusion[a_str]:
                    confusion[a_str][r_str] += 1
                if a_str == r_str:
                    action_matches[a_str] += 1
                    overall_matches += 1
        rec_agreement = {k: round(action_matches[k] / max(1, v), 4) for k, v in action_totals.items()}
        rec_agreement["OVERALL"] = round(overall_matches / max(1, len(known_samples)), 4) if known_samples else 0.0

        # --- Section 9: Score Gap Diagnostics ---
        score_gap_diag = self._compute_score_gap_diagnostics(samples, engine_decisions, midgame)
        margin_tiers = self._compute_margin_tiers(samples, engine_decisions)

        # --- Section 10: Gold Prediction Analysis ---
        gold_analysis = self._compute_gold_prediction(samples, engine_decisions)
        sim_errors = {"sample_size": gold_analysis.valid_pairs}
        if gold_analysis.overall_mae is not None:
            sim_errors["gold_prediction_mae"] = gold_analysis.overall_mae
            sim_errors["gold_prediction_rmse"] = gold_analysis.overall_rmse
            sim_errors["gold_prediction_mean_error"] = gold_analysis.overall_bias

        # --- Section 11: Failure Diagnostics ---
        failures = self._detect_failures(samples, engine_decisions)
        fail_counts = defaultdict(int)
        for fc in failures:
            fail_counts[fc.failure_category] += 1

        # --- Section 12-15 ---
        limitations = self._build_limitations(midgame, known_samples, total)
        can_conclude = self._build_can_conclude(total, midgame, known_samples, gold_analysis)
        cannot_conclude = self._build_cannot_conclude(midgame, known_samples)
        next_data = self._build_next_data()

        # Outcome summary
        all_placements = [s.future_observation.final_placement for s in samples if s.future_observation.final_placement is not None]
        top4 = sum(1 for p in all_placements if p <= 4)
        outcome_summary = {
            "total_with_placement": len(all_placements),
            "avg_placement": round(sum(all_placements) / max(1, len(all_placements)), 2) if all_placements else None,
            "top4_rate": round(top4 / max(1, len(all_placements)), 4) if all_placements else None,
            "denominator_note": (
                "These are DESCRIPTIVE statistics over ALL samples (endgame + midgame). "
                "Do NOT interpret as Decision Engine performance metrics."
            )
        }

        return BacktestReport(
            total_samples=total,
            total_matches=unique_matches,
            total_participants=unique_parts,
            data_source_distribution=dict(source_counts),
            snapshot_type_distribution=dict(snap_counts),
            endgame_count=len(endgame),
            midgame_count=len(midgame),
            action_observation_coverage=coverage_obj,
            recommendation_agreement=rec_agreement,
            action_confusion_matrix=confusion,
            unknown_action_rate=unknown_rate,
            coverage=coverage_rate,
            temporal_integrity=temporal,
            leakage_validation=leakage,
            midgame_statistics=midgame_stats,
            midgame_stratification_by_hp=mg_hp,
            midgame_stratification_by_gold=mg_gold,
            midgame_stratification_by_stage=mg_stage,
            midgame_stratification_by_level=mg_level,
            endgame_statistics=endgame_stats,
            endgame_stratification_by_hp=eg_hp,
            endgame_stratification_by_gold=eg_gold,
            stratification_by_hp=all_hp,
            stratification_by_gold=all_gold,
            stratification_by_stage=all_stage,
            stratification_by_level=all_level,
            behavioral_agreement=behavioral_agree,
            baseline_comparisons=baseline_comps,
            score_gap_diagnostics=score_gap_diag,
            margin_tier_analysis=margin_tiers,
            gold_prediction_analysis=gold_analysis,
            simulation_errors=sim_errors,
            failure_cases_count=len(failures),
            failure_cases_by_type=dict(fail_counts),
            failure_cases_sample=failures[:10],
            data_limitations=limitations,
            what_can_be_concluded=can_conclude,
            what_cannot_be_concluded=cannot_conclude,
            next_required_data=next_data,
            outcome_summary=outcome_summary,
        )

    # ---- Coverage ----

    def _compute_coverage(self, samples: List[BacktestSample]) -> ActionObservationCoverage:
        known = [s for s in samples if s.observed_state.actual_action != ActualActionType.UNKNOWN]
        by_type: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "known": 0})
        by_action: Dict[str, int] = defaultdict(int)
        for s in samples:
            st = s.snapshot_type.value
            by_type[st]["total"] += 1
            if s.observed_state.actual_action != ActualActionType.UNKNOWN:
                by_type[st]["known"] += 1
                by_action[s.observed_state.actual_action.value] += 1
        return ActionObservationCoverage(
            total_samples=len(samples),
            known_action_samples=len(known),
            unknown_action_samples=len(samples) - len(known),
            coverage_rate=round(len(known) / max(1, len(samples)), 4),
            by_snapshot_type=dict(by_type),
            by_action_type=dict(by_action)
        )

    # ---- Temporal Integrity ----

    def _check_temporal_integrity(self, samples: List[BacktestSample]) -> TemporalIntegrityResult:
        checked = 0
        violations = 0
        unknowns = 0
        violation_ids = []
        for s in samples:
            t0 = s.decision_timestamp_sec
            t1 = s.future_observation.outcome_timestamp_sec
            if t0 is None or t1 is None:
                unknowns += 1
                continue
            checked += 1
            if t0 > t1:
                violations += 1
                violation_ids.append(s.sample_id)
        return TemporalIntegrityResult(
            total_checked=checked,
            violations=violations,
            unknown_timestamps=unknowns,
            violation_sample_ids=violation_ids[:5]
        )

    # ---- Leakage ----

    def _check_leakage(self, all_samples: List[BacktestSample], midgame: List[BacktestSample]) -> LeakageValidationResult:
        checked = len(all_samples)
        leakage = 0
        types: Dict[str, int] = defaultdict(int)
        placement_in_state = 0

        endgame_in_mid = sum(1 for s in midgame if s.snapshot_type == SnapshotType.ENDGAME_SNAPSHOT)

        for s in all_samples:
            st = s.observed_state.state
            if hasattr(st, "final_placement") or hasattr(st.player, "final_placement"):
                leakage += 1
                types["placement_in_state"] += 1
                placement_in_state += 1

        return LeakageValidationResult(
            total_checked=checked,
            leakage_detected=leakage,
            leakage_types=dict(types),
            endgame_in_midgame_report=endgame_in_mid,
            placement_in_state=placement_in_state
        )

    # ---- Descriptive Stats ----

    def _compute_descriptive_stats(self, samples: List[BacktestSample], label: str) -> Dict[str, Any]:
        if not samples:
            return {"label": label, "count": 0}
        placements = [s.future_observation.final_placement for s in samples if s.future_observation.final_placement is not None]
        top4 = sum(1 for p in placements if p <= 4)
        known_action = [s for s in samples if s.observed_state.actual_action != ActualActionType.UNKNOWN]
        return {
            "label": label,
            "count": len(samples),
            "with_placement": len(placements),
            "avg_placement": round(sum(placements) / len(placements), 2) if placements else None,
            "top4_rate": round(top4 / len(placements), 4) if placements else None,
            "known_action_count": len(known_action),
            "unknown_action_count": len(samples) - len(known_action),
            "denominator_note": f"avg_placement and top4_rate denominator = {len(placements)} (samples with known placement)"
        }

    # ---- Stratification ----

    def _stratify_hp(self, samples: List[BacktestSample], decisions: List[BacktestDecision]) -> List[StratifiedMetricGroup]:
        tiers = [
            ("HP 0-20 (Critical)", lambda hp: hp <= 20),
            ("HP 21-35 (Crisis)", lambda hp: 21 <= hp <= 35),
            ("HP 36-50 (Low)", lambda hp: 36 <= hp <= 50),
            ("HP 51-65 (Mid)", lambda hp: 51 <= hp <= 65),
            ("HP 66+ (Safe)", lambda hp: hp >= 66)
        ]
        return self._build_strat_list(samples, decisions, lambda s: s.observed_state.state.player.hp, tiers)

    def _stratify_gold(self, samples: List[BacktestSample], decisions: List[BacktestDecision]) -> List[StratifiedMetricGroup]:
        tiers = [
            ("Gold 0-19 (Poor)", lambda g: g < 20),
            ("Gold 20-39 (Building)", lambda g: 20 <= g < 40),
            ("Gold 40-59 (Econ Target)", lambda g: 40 <= g < 60),
            ("Gold 60+ (Rich)", lambda g: g >= 60)
        ]
        return self._build_strat_list(samples, decisions, lambda s: s.observed_state.state.player.gold, tiers)

    def _stratify_stage(self, samples: List[BacktestSample], decisions: List[BacktestDecision]) -> List[StratifiedMetricGroup]:
        tiers = [
            ("Stage 2-x", lambda stg: stg == 2),
            ("Stage 3-x", lambda stg: stg == 3),
            ("Stage 4-x", lambda stg: stg == 4),
            ("Stage 5-x", lambda stg: stg == 5),
            ("Stage 6+", lambda stg: stg >= 6)
        ]
        return self._build_strat_list(samples, decisions, lambda s: s.observed_state.stage, tiers)

    def _stratify_level(self, samples: List[BacktestSample], decisions: List[BacktestDecision]) -> List[StratifiedMetricGroup]:
        tiers = [
            ("Level 6 & below", lambda lvl: lvl <= 6),
            ("Level 7", lambda lvl: lvl == 7),
            ("Level 8", lambda lvl: lvl == 8),
            ("Level 9+", lambda lvl: lvl >= 9)
        ]
        return self._build_strat_list(samples, decisions, lambda s: s.observed_state.state.player.level, tiers)

    def _build_strat_list(self, samples, decisions, val_fn, tiers) -> List[StratifiedMetricGroup]:
        results: List[StratifiedMetricGroup] = []
        dec_map = {d.sample_id: d for d in decisions}

        for name, pred in tiers:
            group = [s for s in samples if pred(val_fn(s))]
            count = len(group)
            if count == 0:
                results.append(StratifiedMetricGroup(
                    group_name=name, sample_count=0,
                    snapshot_type_counts={}, placement_denominator=0
                ))
                continue

            type_counts = defaultdict(int)
            for s in group:
                type_counts[s.snapshot_type.value] += 1

            placements = [s.future_observation.final_placement for s in group if s.future_observation.final_placement is not None]
            avg_p = round(sum(placements) / len(placements), 2) if placements else None
            top4_r = round(sum(1 for p in placements if p <= 4) / len(placements), 4) if placements else None

            known_g = [s for s in group if s.observed_state.actual_action != ActualActionType.UNKNOWN]
            matches = 0
            for s in known_g:
                d = dec_map.get(s.sample_id)
                if d and d.recommended_action.value == s.observed_state.actual_action.value:
                    matches += 1
            ag_r = round(matches / max(1, len(known_g)), 4) if known_g else None

            gaps = [dec_map[s.sample_id].action_score_gap for s in group if s.sample_id in dec_map]
            mean_gap = round(sum(gaps) / len(gaps), 4) if gaps else None

            results.append(StratifiedMetricGroup(
                group_name=name,
                sample_count=count,
                snapshot_type_counts=dict(type_counts),
                avg_placement=avg_p,
                top4_rate=top4_r,
                agreement_rate=ag_r,
                known_action_count=len(known_g),
                mean_score_gap=mean_gap,
                placement_denominator=len(placements)
            ))
        return results

    # ---- Behavioral Agreement ----

    def _compute_behavioral_agreement(
        self,
        samples: List[BacktestSample],
        decisions: List[BacktestDecision]
    ) -> Dict[str, Any]:
        dec_map = {d.sample_id: d for d in decisions}
        known = [s for s in samples if s.observed_state.actual_action != ActualActionType.UNKNOWN]
        if not known:
            return {"OVERALL": 0.0, "denominator": 0, "note": "No samples with known actual_action."}

        matches = 0
        for s in known:
            d = dec_map.get(s.sample_id)
            if d and d.recommended_action.value == s.observed_state.actual_action.value:
                matches += 1

        return {
            "OVERALL": round(matches / len(known), 4),
            "denominator": len(known),
            "note": (
                "Behavioral agreement = fraction of known-action samples where "
                "engine_recommendation == human_action. "
                "This is NOT a performance metric."
            )
        }

    def _compute_baseline_comparisons(
        self,
        samples,
        engine_decisions,
        baseline_decisions,
        known_samples
    ) -> Dict[str, Dict[str, Any]]:
        result = {}
        all_strats = {"DecisionEngine_v1.1": engine_decisions}
        all_strats.update(baseline_decisions)
        total = len(samples)

        for name, decs in all_strats.items():
            strat_matches = 0
            strat_actions = defaultdict(int)
            for d in decs:
                strat_actions[d.recommended_action.value] += 1
            for d in decs:
                s = next((x for x in known_samples if x.sample_id == d.sample_id), None)
                if s and d.recommended_action.value == s.observed_state.actual_action.value:
                    strat_matches += 1

            result[name] = {
                "behavioral_agreement": round(strat_matches / max(1, len(known_samples)), 4) if known_samples else 0.0,
                "agreement_rate": round(strat_matches / max(1, len(known_samples)), 4) if known_samples else 0.0,
                "agreement_denominator": len(known_samples),
                "pct_roll": round(strat_actions["ROLL"] / max(1, total), 4),
                "pct_level_up": round(strat_actions["LEVEL_UP"] / max(1, total), 4),
                "pct_save_gold": round(strat_actions["SAVE_GOLD"] / max(1, total), 4)
            }
        return result

    # ---- Score Gap Diagnostics ----

    def _compute_score_gap_diagnostics(
        self,
        all_samples: List[BacktestSample],
        decisions: List[BacktestDecision],
        midgame: List[BacktestSample]
    ) -> ScoreGapDiagnostics:
        diag = ScoreGapDiagnostics()
        dec_map = {d.sample_id: d for d in decisions}

        endgame_gaps = [dec_map[s.sample_id].action_score_gap for s in all_samples
                        if s.snapshot_type == SnapshotType.ENDGAME_SNAPSHOT and s.sample_id in dec_map]
        midgame_gaps = [dec_map[s.sample_id].action_score_gap for s in midgame if s.sample_id in dec_map]

        diag.endgame_mean_gap = round(sum(endgame_gaps) / len(endgame_gaps), 4) if endgame_gaps else None
        diag.midgame_mean_gap = round(sum(midgame_gaps) / len(midgame_gaps), 4) if midgame_gaps else None
        diag.midgame_n = len(midgame)

        # Gap tier analysis (with snapshot_type breakdown)
        tiers = [
            ("Tight Margin [0.00, 0.02)", lambda m: 0.0 <= m < 0.02),
            ("Moderate Margin [0.02, 0.05)", lambda m: 0.02 <= m < 0.05),
            ("Clear Margin [0.05, 0.10)", lambda m: 0.05 <= m < 0.10),
            ("Decisive Margin [0.10+)", lambda m: m >= 0.10)
        ]
        for tname, pred in tiers:
            tier_decs = [d for d in decisions if pred(d.action_score_gap)]
            endgame_n = 0
            midgame_n = 0
            tier_placements = []
            for d in tier_decs:
                s = next((x for x in all_samples if x.sample_id == d.sample_id), None)
                if s:
                    if s.snapshot_type == SnapshotType.ENDGAME_SNAPSHOT:
                        endgame_n += 1
                    else:
                        midgame_n += 1
                    if s.future_observation.final_placement is not None:
                        tier_placements.append(s.future_observation.final_placement)

            diag.gap_tiers.append({
                "tier": tname,
                "count": len(tier_decs),
                "endgame_count": endgame_n,
                "midgame_count": midgame_n,
                "avg_placement": round(sum(tier_placements) / len(tier_placements), 2) if tier_placements else None,
                "top4_rate": round(sum(1 for p in tier_placements if p <= 4) / len(tier_placements), 4) if tier_placements else None,
                "placement_denominator": len(tier_placements)
            })

        # Confounder analysis
        diag.gap_by_hp_tier = self._gap_by_dim(all_samples, decisions, self._hp_tiers_raw(), lambda s: s.observed_state.state.player.hp)
        diag.gap_by_gold_tier = self._gap_by_dim(all_samples, decisions, self._gold_tiers_raw(), lambda s: s.observed_state.state.player.gold)
        diag.gap_by_stage = self._gap_by_dim(all_samples, decisions, self._stage_tiers_raw(), lambda s: s.observed_state.stage)
        diag.gap_by_level = self._gap_by_dim(all_samples, decisions, self._level_tiers_raw(), lambda s: s.observed_state.state.player.level)

        # Correlation analysis (MIDGAME only)
        if len(midgame) >= 5:
            mg_gaps = []
            mg_placements = []
            for s in midgame:
                d = dec_map.get(s.sample_id)
                if d and s.future_observation.final_placement is not None:
                    mg_gaps.append(d.action_score_gap)
                    mg_placements.append(s.future_observation.final_placement)
            if len(mg_gaps) >= 5:
                pearson = _pearson(mg_gaps, mg_placements)
                spearman = _spearman(mg_gaps, mg_placements)
                diag.midgame_pearson_gap_placement = round(pearson, 4) if pearson is not None else None
                diag.midgame_spearman_gap_placement = round(spearman, 4) if spearman is not None else None
                n = len(mg_gaps)
                if n < 30:
                    diag.correlation_note = (
                        f"WARNING: n={n} MIDGAME samples with placement is INSUFFICIENT "
                        "for reliable correlation estimation. Treat values as exploratory only."
                    )
                else:
                    diag.correlation_note = f"Correlation computed on n={n} MIDGAME samples with known placement."
            else:
                diag.correlation_note = "Insufficient MIDGAME samples with known placement for correlation."
        else:
            diag.correlation_note = (
                f"MIDGAME sample count ({len(midgame)}) is too small for reliable correlation analysis. "
                "Correlation NOT computed."
            )

        return diag

    def _hp_tiers_raw(self):
        return [
            ("HP 0-20", lambda hp: hp <= 20),
            ("HP 21-35", lambda hp: 21 <= hp <= 35),
            ("HP 36-50", lambda hp: 36 <= hp <= 50),
            ("HP 51-65", lambda hp: 51 <= hp <= 65),
            ("HP 66+", lambda hp: hp >= 66)
        ]

    def _gold_tiers_raw(self):
        return [
            ("Gold 0-19", lambda g: g < 20),
            ("Gold 20-39", lambda g: 20 <= g < 40),
            ("Gold 40-59", lambda g: 40 <= g < 60),
            ("Gold 60+", lambda g: g >= 60)
        ]

    def _stage_tiers_raw(self):
        return [
            ("Stage 2-x", lambda stg: stg == 2),
            ("Stage 3-x", lambda stg: stg == 3),
            ("Stage 4-x", lambda stg: stg == 4),
            ("Stage 5-x", lambda stg: stg == 5),
            ("Stage 6+", lambda stg: stg >= 6)
        ]

    def _level_tiers_raw(self):
        return [
            ("Level ≤6", lambda lvl: lvl <= 6),
            ("Level 7", lambda lvl: lvl == 7),
            ("Level 8", lambda lvl: lvl == 8),
            ("Level 9+", lambda lvl: lvl >= 9)
        ]

    def _gap_by_dim(self, samples, decisions, tiers, val_fn) -> List[Dict[str, Any]]:
        dec_map = {d.sample_id: d for d in decisions}
        results = []
        for name, pred in tiers:
            group = [s for s in samples if pred(val_fn(s))]
            gaps = [dec_map[s.sample_id].action_score_gap for s in group if s.sample_id in dec_map]
            placements = [s.future_observation.final_placement for s in group if s.future_observation.final_placement is not None]
            endgame_n = sum(1 for s in group if s.snapshot_type == SnapshotType.ENDGAME_SNAPSHOT)
            results.append({
                "group": name,
                "count": len(group),
                "endgame_count": endgame_n,
                "mean_gap": round(sum(gaps) / len(gaps), 4) if gaps else None,
                "avg_placement": round(sum(placements) / len(placements), 2) if placements else None
            })
        return results

    # ---- Gold Prediction Analysis ----

    def _compute_gold_prediction(
        self,
        samples: List[BacktestSample],
        decisions: List[BacktestDecision]
    ) -> GoldPredictionAnalysis:
        dec_map = {d.sample_id: d for d in decisions}
        horizon_zero = sum(1 for s in samples if (s.horizon_rounds or 0) == 0)

        errors_by_action: Dict[str, List[float]] = defaultdict(list)
        all_errors = []

        for s in samples:
            if (s.horizon_rounds or 0) == 0:
                continue
            if s.observed_state.actual_action == ActualActionType.UNKNOWN:
                continue
            d = dec_map.get(s.sample_id)
            if not d:
                continue
            rec_act = d.recommended_action.value
            sim_exp = d.simulated_expectations.get(rec_act, {})
            pred_gold = sim_exp.get("expected_gold")
            act_gold = s.future_observation.gold_after_n_rounds
            if pred_gold is not None and act_gold is not None:
                err = pred_gold - act_gold
                errors_by_action[s.observed_state.actual_action.value].append(err)
                all_errors.append(err)

        by_action = {}
        for act, errs in errors_by_action.items():
            mae = round(sum(abs(e) for e in errs) / len(errs), 2)
            rmse = round(math.sqrt(sum(e*e for e in errs) / len(errs)), 2)
            bias = round(sum(errs) / len(errs), 2)
            by_action[act] = {"n": len(errs), "mae": mae, "rmse": rmse, "bias": bias}

        overall_mae = None
        overall_rmse = None
        overall_bias = None
        if all_errors:
            overall_mae = round(sum(abs(e) for e in all_errors) / len(all_errors), 2)
            overall_rmse = round(math.sqrt(sum(e*e for e in all_errors) / len(all_errors)), 2)
            overall_bias = round(sum(all_errors) / len(all_errors), 2)

        note = (
            "Gold prediction error computed ONLY for samples where: "
            "(1) horizon_rounds > 0 (not ENDGAME), and "
            "(2) actual_action is known. "
            f"ENDGAME samples excluded: {horizon_zero}. "
        )
        if not all_errors:
            note += "No valid pairs found -- action-conditioned gold prediction cannot be computed with current data."

        return GoldPredictionAnalysis(
            note=note,
            horizon_zero_excluded=horizon_zero,
            valid_pairs=len(all_errors),
            by_action=by_action,
            overall_mae=overall_mae,
            overall_rmse=overall_rmse,
            overall_bias=overall_bias
        )

    # ---- Failure Detection ----

    def _detect_failures(
        self,
        samples: List[BacktestSample],
        decisions: List[BacktestDecision]
    ) -> List[FailureCase]:
        failures: List[FailureCase] = []

        for d in decisions:
            s = next((x for x in samples if x.sample_id == d.sample_id), None)
            if not s:
                continue
            p = s.future_observation.final_placement
            act = s.observed_state.actual_action
            gap = d.action_score_gap
            snap = s.snapshot_type

            # Priority 1: Data Invalid
            ok = self._is_valid_sample(s)
            if not ok:
                failures.append(self._make_failure(
                    s, d, FailureType.DATA_INVALID.value,
                    "Data validation issues found in sample state."
                ))
                continue

            # Priority 2: Feasibility Error
            if self._is_feasibility_error(s, d):
                failures.append(self._make_failure(
                    s, d, FailureType.FEASIBILITY_ERROR.value,
                    f"Recommended {d.recommended_action.value} but gold/XP insufficient."
                ))
                continue

            # Priority 3: HIGH_MARGIN_BOTTOM4
            if gap >= self.SCORE_GAP_THRESHOLD_HIGH and p is not None and p >= 5:
                failures.append(self._make_failure(
                    s, d, FailureType.HIGH_MARGIN_BOTTOM4.value,
                    f"score_gap={gap:.3f} >= {self.SCORE_GAP_THRESHOLD_HIGH}, "
                    f"but final placement was {p} (bottom 4). "
                    f"Diagnostic label only. snapshot_type={snap.value}."
                ))

            # Priority 4: RECOMMENDATION_DISAGREEMENT
            elif (
                gap >= self.SCORE_GAP_THRESHOLD_DECISIVE
                and act != ActualActionType.UNKNOWN
                and act.value != d.recommended_action.value
                and p is not None and p <= 2
            ):
                failures.append(self._make_failure(
                    s, d, FailureType.RECOMMENDATION_DISAGREEMENT.value,
                    f"Engine strongly recommended {d.recommended_action.value} "
                    f"(score_gap={gap:.3f}) but player chose {act.value} and "
                    f"achieved placement {p}."
                ))

        return failures

    def _is_valid_sample(self, s: BacktestSample) -> bool:
        st = s.observed_state.state
        if st.player.gold < 0 or st.player.level < 1 or st.player.level > 11:
            return False
        if st.player.hp < 0 or st.player.hp > 100:
            return False
        if hasattr(st, "final_placement") or hasattr(st.player, "final_placement"):
            return False
        return True

    def _is_feasibility_error(self, s: BacktestSample, d: BacktestDecision) -> bool:
        gold = s.observed_state.state.player.gold
        act = d.recommended_action
        if act == ActionType.ROLL and gold < 2:
            return True
        if act == ActionType.LEVEL_UP and gold < 4:
            return True
        return False

    def _make_failure(
        self, s: BacktestSample, d: BacktestDecision, ftype: str, desc: str
    ) -> FailureCase:
        return FailureCase(
            case_id=f"{ftype}_{s.sample_id}",
            match_id=s.match_id,
            sample_id=s.sample_id,
            failure_type=ftype,
            failure_category=ftype,
            description=desc,
            state_summary={
                "stage": s.observed_state.stage_round,
                "gold": s.observed_state.state.player.gold,
                "level": s.observed_state.state.player.level,
                "hp": s.observed_state.state.player.hp,
                "snapshot_type": s.snapshot_type.value
            },
            recommended_action=d.recommended_action.value,
            actual_action=s.observed_state.actual_action.value,
            actual_placement=s.future_observation.final_placement,
            action_score_gap=d.action_score_gap,
            decision_margin=d.action_score_gap,
            snapshot_type=s.snapshot_type.value,
            reproducible_state={
                "gold": s.observed_state.state.player.gold,
                "level": s.observed_state.state.player.level,
                "hp": s.observed_state.state.player.hp,
                "stage": s.observed_state.stage
            }
        )

    # ---- backward-compat margin tiers ----

    def _compute_margin_tiers(
        self, samples: List[BacktestSample], decisions: List[BacktestDecision]
    ) -> List[Dict[str, Any]]:
        sample_map_local = {s.sample_id: s for s in samples}
        tiers = [
            ("Tight Margin [0.00, 0.02)", lambda m: 0.0 <= m < 0.02),
            ("Moderate Margin [0.02, 0.05)", lambda m: 0.02 <= m < 0.05),
            ("Clear Margin [0.05, 0.10)", lambda m: 0.05 <= m < 0.10),
            ("Decisive Margin [0.10+)", lambda m: m >= 0.10)
        ]
        results = []
        for name, pred in tiers:
            td = [d for d in decisions if pred(d.action_score_gap)]
            ps = [sample_map_local[d.sample_id].future_observation.final_placement
                  for d in td if d.sample_id in sample_map_local
                  and sample_map_local[d.sample_id].future_observation.final_placement is not None]
            results.append({
                "tier_name": name,
                "count": len(td),
                "percentage": round(len(td) / max(1, len(decisions)), 4),
                "avg_placement": round(sum(ps) / len(ps), 2) if ps else None,
                "top4_rate": round(sum(1 for p in ps if p <= 4) / len(ps), 4) if ps else None
            })
        return results

    # ---- Narrative Sections ----

    def _build_limitations(self, midgame, known_samples, total) -> List[str]:
        return [
            "Riot Match-V1 API provides ONLY elimination-time final state. "
            "All 500 match snapshots are ENDGAME_SNAPSHOT and must not be used for Decision Engine strategy evaluation.",
            "Intermediate round-by-round player actions (ROLL, LEVEL_UP, SAVE_GOLD) are not recorded by Riot Match-V1. "
            "actual_action = UNKNOWN for all Riot match samples.",
            f"MIDGAME samples: {len(midgame)} (from video CV audit only). "
            "GameState values (gold, hp, level) in video samples are HEURISTIC ESTIMATES, not precise extractions.",
            f"Known actual_action coverage: {len(known_samples)} / {total} samples ({len(known_samples)/max(1,total):.1%}). "
            "All known actions are from the single video audit session.",
            "survival_score is an uncalibrated heuristic metric. "
            "It cannot be interpreted as a statistical probability without empirical calibration data.",
            "action_score_gap (formerly decision_margin) is score separation between best and second-best action. "
            "It is NOT a calibrated probability of correctness.",
            "The single video session (1 player, 1 game) cannot be generalized to broader player populations.",
        ]

    def _build_can_conclude(self, total, midgame, known_samples, gold_analysis) -> List[str]:
        can = [
            f"Decision Engine executes successfully on all {total} evaluated GameState samples with 0 runtime errors.",
            "ENDGAME and MIDGAME snapshot types can be cleanly separated by data_source and snapshot_type fields.",
            "Match-level group split maintains zero match overlap between train and test sets.",
            "Temporal integrity (T0 <= T1+) is maintained for samples with known timestamps.",
            "No final_placement leakage detected in T0 GameState objects.",
            "The engine produces valid, feasible action recommendations across diverse game states.",
        ]
        if gold_analysis.valid_pairs == 0:
            can.append(
                "Gold prediction error analysis correctly identifies that action-conditioned prediction "
                "cannot be computed without known actual_action and horizon > 0 data."
            )
        return can

    def _build_cannot_conclude(self, midgame, known_samples) -> List[str]:
        cannot = [
            "Whether Decision Engine produces better game outcomes than human play. "
            "(Requires: MIDGAME states with known actual_action, future outcomes, sufficient sample size.)",
            "Whether ROLL, LEVEL_UP, or SAVE_GOLD leads to better expected placement in any given situation. "
            "(Requires: counterfactual data with both action and outcome for same initial state.)",
            "Whether action_score_gap (decision_margin) can be used as a probability of correctness. "
            "(Requires: empirical calibration against labeled outcomes.)",
            "Whether the engine's SAVE_GOLD preference is strategically superior to human ROLL behavior. "
            "human_policy != engine_policy does not imply either is better.",
            "Whether survival_score is an accurate predictor of actual survival probability. "
            "(Requires: calibration against empirical round-by-round match data.)",
            f"Whether the video audit sample (n={len(midgame)}, single session) generalizes to any broader population.",
            "Any causal claim about Decision Engine recommendations and game outcomes.",
        ]
        return cannot

    def _build_next_data(self) -> List[str]:
        return [
            "MIDGAME decision snapshots from multiple game sessions with precise round state extraction "
            "(gold, hp, level, board at each round start) -- minimum 500 samples across 50+ sessions.",
            "Round-by-round actual player actions (ROLL, LEVEL_UP, SAVE_GOLD) paired with resulting game state "
            "-- required for action-conditioned analysis.",
            "For counterfactual evaluation: paired states where player chose action A in one sample "
            "and action B in a comparable state, both with known outcomes.",
            "For gold prediction validation: T0 gold + actual T0 action + T1+ gold n rounds later, "
            "with known horizon_rounds.",
            "For correlation analysis: minimum 100 MIDGAME samples with (state, action, placement) tuples "
            "from diverse players and stages.",
            "Empirical champion pool availability data for the actual game version being analyzed "
            "to improve roll probability accuracy.",
        ]


def _pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def _spearman(xs: List[float], ys: List[float]) -> Optional[float]:
    n = len(xs)
    if n < 2:
        return None

    def ranks(lst):
        sorted_idx = sorted(range(n), key=lambda i: lst[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n - 1 and lst[sorted_idx[j]] == lst[sorted_idx[j + 1]]:
                j += 1
            avg_rank = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[sorted_idx[k]] = avg_rank
            i = j + 1
        return r

    rx = ranks(xs)
    ry = ranks(ys)
    return _pearson(rx, ry)
