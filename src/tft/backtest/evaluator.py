"""TFT Backtest Evaluator: Metrics, Stratification, and Failure Analysis."""
import math
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from tft.domain.actions import ActionType
from tft.backtest.models import (
    BacktestSample,
    BacktestDecision,
    FailureCase,
    StratifiedMetricGroup,
    BacktestReport,
    ActualActionType
)

class BacktestEvaluator:
    """백테스트 결과 종합 평가 및 지표 산출기."""

    def evaluate(
        self,
        samples: List[BacktestSample],
        engine_decisions: List[BacktestDecision],
        baseline_decisions: Dict[str, List[BacktestDecision]]
    ) -> BacktestReport:
        sample_map = {s.sample_id: s for s in samples}
        total_samples = len(samples)
        unique_matches = len(set(s.match_id for s in samples))
        unique_participants = len(set(f"{s.match_id}_{s.participant_id}" for s in samples))

        # Data Source distribution
        source_counts = defaultdict(int)
        for s in samples:
            source_counts[s.data_source] += 1

        # 1. Behavioral Agreement & Confusion Matrix
        known_samples = []
        known_decisions = []
        for d in engine_decisions:
            s = sample_map.get(d.sample_id)
            if s and s.observed_state.actual_action != ActualActionType.UNKNOWN:
                known_samples.append(s)
                known_decisions.append(d)

        unknown_count = total_samples - len(known_samples)
        unknown_rate = round(unknown_count / max(1, total_samples), 4)
        coverage = round(len(known_samples) / max(1, total_samples), 4)

        agreement_by_action: Dict[str, float] = {}
        confusion_matrix: Dict[str, Dict[str, int]] = {
            act.value: {rec_act.value: 0 for rec_act in [ActionType.ROLL, ActionType.LEVEL_UP, ActionType.SAVE_GOLD]}
            for act in [ActualActionType.ROLL, ActualActionType.LEVEL_UP, ActualActionType.SAVE_GOLD]
        }

        action_totals = defaultdict(int)
        action_matches = defaultdict(int)
        overall_matches = 0

        for s, d in zip(known_samples, known_decisions):
            actual_str = s.observed_state.actual_action.value
            rec_str = d.recommended_action.value

            action_totals[actual_str] += 1
            if actual_str in confusion_matrix and rec_str in confusion_matrix[actual_str]:
                confusion_matrix[actual_str][rec_str] += 1

            if actual_str == rec_str:
                action_matches[actual_str] += 1
                overall_matches += 1

        for act_str, count in action_totals.items():
            agreement_by_action[act_str] = round(action_matches[act_str] / max(1, count), 4)
        agreement_by_action["OVERALL"] = round(overall_matches / max(1, len(known_samples)), 4) if known_samples else 0.0

        # 2. Baseline Comparisons
        baseline_comps: Dict[str, Dict[str, float]] = {}
        all_strats = {"DecisionEngine_v1.1": engine_decisions}
        all_strats.update(baseline_decisions)

        for strat_name, dec_list in all_strats.items():
            strat_matches = 0
            strat_actions = defaultdict(int)
            for d in dec_list:
                s = sample_map.get(d.sample_id)
                strat_actions[d.recommended_action.value] += 1
                if s and s.observed_state.actual_action != ActualActionType.UNKNOWN:
                    if d.recommended_action.value == s.observed_state.actual_action.value:
                        strat_matches += 1

            baseline_comps[strat_name] = {
                "agreement_rate": round(strat_matches / max(1, len(known_samples)), 4) if known_samples else 0.0,
                "pct_roll": round(strat_actions["ROLL"] / max(1, total_samples), 4),
                "pct_level_up": round(strat_actions["LEVEL_UP"] / max(1, total_samples), 4),
                "pct_save_gold": round(strat_actions["SAVE_GOLD"] / max(1, total_samples), 4)
            }

        # 3. Outcome Summary & Stratification
        valid_placements = [s.future_observation.final_placement for s in samples if s.future_observation.final_placement is not None]
        top4_count = sum(1 for p in valid_placements if p <= 4)
        outcome_summary = {
            "total_with_placement": len(valid_placements),
            "avg_placement": round(sum(valid_placements) / max(1, len(valid_placements)), 2) if valid_placements else None,
            "top4_rate": round(top4_count / max(1, len(valid_placements)), 4) if valid_placements else None
        }

        strat_hp = self._stratify_by_hp(samples, engine_decisions)
        strat_gold = self._stratify_by_gold(samples, engine_decisions)
        strat_stage = self._stratify_by_stage(samples, engine_decisions)
        strat_level = self._stratify_by_level(samples, engine_decisions)

        # 4. Decision Margin Analysis
        margin_tiers = self._analyze_margin_tiers(samples, engine_decisions)

        # 5. Simulation Error Analysis
        sim_errors = self._calculate_simulation_errors(samples, engine_decisions)

        # 6. Failure Case Detection
        failure_cases = self._detect_failure_cases(samples, engine_decisions)

        data_limits = [
            "Riot Match-V1 API endpoint provides endgame final state (level, gold_left, placement) but does not record tick-by-tick player decisions.",
            "Intermediate state player actions are marked as UNKNOWN for match snapshots to prevent falsification.",
            "Video CV audit timeline contains verified real player action detections (REROLL, BUY).",
            "Survival score is an uncalibrated heuristic metric and should not be interpreted as a statistical empirical probability without real match match-up logs."
        ]

        return BacktestReport(
            total_samples=total_samples,
            total_matches=unique_matches,
            total_participants=unique_participants,
            data_source_distribution=dict(source_counts),
            recommendation_agreement=agreement_by_action,
            action_confusion_matrix=confusion_matrix,
            unknown_action_rate=unknown_rate,
            coverage=coverage,
            baseline_comparisons=baseline_comps,
            outcome_summary=outcome_summary,
            stratification_by_hp=strat_hp,
            stratification_by_gold=strat_gold,
            stratification_by_stage=strat_stage,
            stratification_by_level=strat_level,
            margin_tier_analysis=margin_tiers,
            simulation_errors=sim_errors,
            failure_cases_count=len(failure_cases),
            failure_cases_sample=failure_cases[:10],
            data_limitations=data_limits
        )

    def _stratify_by_hp(self, samples: List[BacktestSample], decisions: List[BacktestDecision]) -> List[StratifiedMetricGroup]:
        tiers = [
            ("HP 0-20 (Critical)", lambda hp: hp <= 20),
            ("HP 21-35 (Crisis)", lambda hp: 21 <= hp <= 35),
            ("HP 36-50 (Low)", lambda hp: 36 <= hp <= 50),
            ("HP 51-65 (Mid)", lambda hp: 51 <= hp <= 65),
            ("HP 66+ (Safe)", lambda hp: hp >= 66)
        ]
        return self._build_stratified_groups(samples, decisions, lambda s: s.observed_state.state.player.hp, tiers)

    def _stratify_by_gold(self, samples: List[BacktestSample], decisions: List[BacktestDecision]) -> List[StratifiedMetricGroup]:
        tiers = [
            ("Gold 0-19 (Poor)", lambda g: g < 20),
            ("Gold 20-39 (Building)", lambda g: 20 <= g < 40),
            ("Gold 40-59 (Econ Target)", lambda g: 40 <= g < 60),
            ("Gold 60+ (Rich)", lambda g: g >= 60)
        ]
        return self._build_stratified_groups(samples, decisions, lambda s: s.observed_state.state.player.gold, tiers)

    def _stratify_by_stage(self, samples: List[BacktestSample], decisions: List[BacktestDecision]) -> List[StratifiedMetricGroup]:
        tiers = [
            ("Stage 2-x", lambda stg: stg == 2),
            ("Stage 3-x", lambda stg: stg == 3),
            ("Stage 4-x", lambda stg: stg == 4),
            ("Stage 5-x", lambda stg: stg == 5),
            ("Stage 6+", lambda stg: stg >= 6)
        ]
        return self._build_stratified_groups(samples, decisions, lambda s: s.observed_state.stage, tiers)

    def _stratify_by_level(self, samples: List[BacktestSample], decisions: List[BacktestDecision]) -> List[StratifiedMetricGroup]:
        tiers = [
            ("Level 6 & below", lambda lvl: lvl <= 6),
            ("Level 7", lambda lvl: lvl == 7),
            ("Level 8", lambda lvl: lvl == 8),
            ("Level 9+", lambda lvl: lvl >= 9)
        ]
        return self._build_stratified_groups(samples, decisions, lambda s: s.observed_state.state.player.level, tiers)

    def _build_stratified_groups(self, samples, decisions, val_fn, tiers) -> List[StratifiedMetricGroup]:
        results: List[StratifiedMetricGroup] = []
        dec_map = {d.sample_id: d for d in decisions}

        for name, pred in tiers:
            group_samples = [s for s in samples if pred(val_fn(s))]
            count = len(group_samples)
            if count == 0:
                results.append(StratifiedMetricGroup(group_name=name, sample_count=0, avg_placement=None, top4_rate=None, agreement_rate=None))
                continue

            placements = [s.future_observation.final_placement for s in group_samples if s.future_observation.final_placement is not None]
            avg_p = round(sum(placements) / len(placements), 2) if placements else None
            top4_r = round(sum(1 for p in placements if p <= 4) / len(placements), 4) if placements else None

            known_g = [s for s in group_samples if s.observed_state.actual_action != ActualActionType.UNKNOWN]
            matches = 0
            for s in known_g:
                d = dec_map.get(s.sample_id)
                if d and d.recommended_action.value == s.observed_state.actual_action.value:
                    matches += 1
            ag_r = round(matches / max(1, len(known_g)), 4) if known_g else None

            results.append(StratifiedMetricGroup(
                group_name=name,
                sample_count=count,
                avg_placement=avg_p,
                top4_rate=top4_r,
                agreement_rate=ag_r
            ))
        return results

    def _analyze_margin_tiers(self, samples: List[BacktestSample], decisions: List[BacktestDecision]) -> List[Dict[str, Any]]:
        sample_map = {s.sample_id: s for s in samples}
        tiers = [
            ("Tight Margin [0.00, 0.02)", lambda m: 0.0 <= m < 0.02),
            ("Moderate Margin [0.02, 0.05)", lambda m: 0.02 <= m < 0.05),
            ("Clear Margin [0.05, 0.10)", lambda m: 0.05 <= m < 0.10),
            ("Decisive Margin [0.10+)", lambda m: m >= 0.10)
        ]
        results = []
        for name, pred in tiers:
            tier_decs = [d for d in decisions if pred(d.decision_margin)]
            count = len(tier_decs)
            pct = round(count / max(1, len(decisions)), 4)

            tier_placements = []
            known_matches = 0
            known_count = 0

            for d in tier_decs:
                s = sample_map.get(d.sample_id)
                if s:
                    if s.future_observation.final_placement is not None:
                        tier_placements.append(s.future_observation.final_placement)
                    if s.observed_state.actual_action != ActualActionType.UNKNOWN:
                        known_count += 1
                        if d.recommended_action.value == s.observed_state.actual_action.value:
                            known_matches += 1

            avg_p = round(sum(tier_placements) / len(tier_placements), 2) if tier_placements else None
            top4_r = round(sum(1 for p in tier_placements if p <= 4) / len(tier_placements), 4) if tier_placements else None
            ag_r = round(known_matches / max(1, known_count), 4) if known_count else None

            results.append({
                "tier_name": name,
                "count": count,
                "percentage": pct,
                "avg_placement": avg_p,
                "top4_rate": top4_r,
                "agreement_rate": ag_r
            })
        return results

    def _calculate_simulation_errors(self, samples: List[BacktestSample], decisions: List[BacktestDecision]) -> Dict[str, Any]:
        """미래 관측 골드/레벨이 존재하는 경우 Simulation MAE/RMSE 산출."""
        dec_map = {d.sample_id: d for d in decisions}
        gold_errors = []
        level_errors = []

        for s in samples:
            d = dec_map.get(s.sample_id)
            if not d:
                continue
            rec_act = d.recommended_action.value
            sim_exp = d.simulated_expectations.get(rec_act, {})

            pred_gold = sim_exp.get("expected_gold")
            act_gold = s.future_observation.gold_after_n_rounds
            if pred_gold is not None and act_gold is not None:
                gold_errors.append(pred_gold - act_gold)

        if not gold_errors:
            return {"gold_prediction_mae": None, "gold_prediction_rmse": None, "sample_size": 0}

        mae = round(sum(abs(e) for e in gold_errors) / len(gold_errors), 2)
        rmse = round(math.sqrt(sum(e * e for e in gold_errors) / len(gold_errors)), 2)
        mean_err = round(sum(gold_errors) / len(gold_errors), 2)

        return {
            "gold_prediction_mae": mae,
            "gold_prediction_rmse": rmse,
            "gold_prediction_mean_error": mean_err,
            "sample_size": len(gold_errors)
        }

    def _detect_failure_cases(self, samples: List[BacktestSample], decisions: List[BacktestDecision]) -> List[FailureCase]:
        sample_map = {s.sample_id: s for s in samples}
        failures: List[FailureCase] = []

        for d in decisions:
            s = sample_map.get(d.sample_id)
            if not s:
                continue
            p = s.future_observation.final_placement
            act = s.observed_state.actual_action

            # Failure Type 1: High-margin recommendation where actual action agreed but player was eliminated bottom 4 (7th or 8th)
            if d.decision_margin >= 0.05 and act.value == d.recommended_action.value and p is not None and p >= 7:
                failures.append(FailureCase(
                    case_id=f"FAIL_AGREE_BOT4_{s.sample_id}",
                    match_id=s.match_id,
                    sample_id=s.sample_id,
                    failure_type="AGREEMENT_BUT_BOTTOM4",
                    description=f"Engine and Player both chose {act.value} with strong margin (+{d.decision_margin:.3f}), but player finished {p}th.",
                    state_summary={
                        "stage": s.observed_state.stage_round,
                        "gold": s.observed_state.state.player.gold,
                        "level": s.observed_state.state.player.level,
                        "hp": s.observed_state.state.player.hp,
                        "board_units_len": len(s.observed_state.state.board_units)
                    },
                    recommended_action=d.recommended_action.value,
                    actual_action=act.value,
                    actual_placement=p,
                    decision_margin=d.decision_margin,
                    reproducible_state={
                        "gold": s.observed_state.state.player.gold,
                        "level": s.observed_state.state.player.level,
                        "hp": s.observed_state.state.player.hp,
                        "stage": s.observed_state.stage
                    }
                ))

            # Failure Type 2: High margin recommendation where player chose different action and won Top 2 (1st or 2nd)
            elif d.decision_margin >= 0.08 and act != ActualActionType.UNKNOWN and act.value != d.recommended_action.value and p is not None and p <= 2:
                failures.append(FailureCase(
                    case_id=f"FAIL_DISAGREE_TOP2_{s.sample_id}",
                    match_id=s.match_id,
                    sample_id=s.sample_id,
                    failure_type="HIGH_MARGIN_DISAGREEMENT",
                    description=f"Engine strongly favored {d.recommended_action.value} (+{d.decision_margin:.3f}) but player chose {act.value} and finished {p}th.",
                    state_summary={
                        "stage": s.observed_state.stage_round,
                        "gold": s.observed_state.state.player.gold,
                        "level": s.observed_state.state.player.level,
                        "hp": s.observed_state.state.player.hp
                    },
                    recommended_action=d.recommended_action.value,
                    actual_action=act.value,
                    actual_placement=p,
                    decision_margin=d.decision_margin,
                    reproducible_state={
                        "gold": s.observed_state.state.player.gold,
                        "level": s.observed_state.state.player.level,
                        "hp": s.observed_state.state.player.hp,
                        "stage": s.observed_state.stage
                    }
                ))

        return failures
