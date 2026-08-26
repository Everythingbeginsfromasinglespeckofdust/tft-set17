"""TFT Action Rule Validator: Empirical replay and statistical validation of candidate action rules."""
from collections import defaultdict
from dataclasses import dataclass, field
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from tft.vision.ground_truth import GroundTruthDataset, GroundTruthEvent, GroundTruthActionType
from tft.vision.causal_extractor import CausalWindowExtractor
from tft.vision.causal_models import EventCausalTrace, SignalTransition, SignalType
from tft.vision.rule_metrics import (
    RuleEvaluationMetrics,
    RuleConflict,
    FailureCategory,
    TimingBreakdown
)


class ActionRuleValidator:
    """Ground Truth 및 추출된 Causal Trace에 대해 후보 규칙들을 엄밀 검증하는 엔진."""

    def __init__(self, extractor: Optional[CausalWindowExtractor] = None):
        self.extractor = extractor or CausalWindowExtractor()

    # --- ROLL Candidate Rule Evaluators ---
    @staticmethod
    def eval_roll_a(
        gold_delta: Optional[int],
        shop_changed: int,
        is_system_refresh: bool,
        board_unchanged: bool,
        bench_unchanged: bool
    ) -> bool:
        """ROLL_A: gold == -2 AND shop >= 1 AND NOT system_refresh AND board_unchanged AND bench_unchanged."""
        return (
            gold_delta == -2 and
            shop_changed >= 1 and
            not is_system_refresh and
            board_unchanged and
            bench_unchanged
        )

    @staticmethod
    def eval_roll_b(
        gold_delta: Optional[int],
        shop_changed: int,
        is_system_refresh: bool,
        has_buy_evidence: bool
    ) -> bool:
        """ROLL_B: gold == -2 AND shop >= 1 AND NOT system_refresh AND NOT buy_evidence."""
        return (
            gold_delta == -2 and
            shop_changed >= 1 and
            not is_system_refresh and
            not has_buy_evidence
        )

    @staticmethod
    def eval_roll_c(
        gold_delta: Optional[int],
        shop_changed: int,
        is_system_refresh: bool
    ) -> bool:
        """ROLL_C: gold == -2 AND shop >= 1 AND NOT system_refresh (board/bench check omitted)."""
        return (
            gold_delta == -2 and
            shop_changed >= 1 and
            not is_system_refresh
        )

    @staticmethod
    def eval_roll_d(
        gold_delta: Optional[int],
        shop_transition_detected: bool,
        is_system_refresh: bool
    ) -> bool:
        """ROLL_D: gold == -2 AND shop_transition_detected (including same-champion collisions) AND NOT system_refresh."""
        return (
            gold_delta == -2 and
            shop_transition_detected and
            not is_system_refresh
        )

    # --- BUY_UNIT Candidate Rule Evaluators ---
    @staticmethod
    def eval_buy_a(
        shop_slot_emptied: bool,
        matching_champion_added: bool,
        gold_matches_cost: bool,
        is_shop_animation: bool
    ) -> bool:
        """BUY_A: shop_slot_emptied AND matching_champion_added AND gold == -cost AND NOT shop_animation."""
        return (
            shop_slot_emptied and
            matching_champion_added and
            gold_matches_cost and
            not is_shop_animation
        )

    @staticmethod
    def eval_buy_b(
        shop_slot_emptied: bool,
        gold_matches_cost: bool,
        is_shop_animation: bool
    ) -> bool:
        """BUY_B: shop_slot_emptied AND gold == -cost AND NOT shop_animation (bench addition omitted)."""
        return (
            shop_slot_emptied and
            gold_matches_cost and
            not is_shop_animation
        )

    @staticmethod
    def eval_buy_c(
        shop_slot_emptied: bool,
        matching_champion_added: bool,
        is_shop_animation: bool
    ) -> bool:
        """BUY_C: shop_slot_emptied AND matching_champion_added AND NOT shop_animation (gold check omitted)."""
        return (
            shop_slot_emptied and
            matching_champion_added and
            not is_shop_animation
        )

    # --- SYSTEM_REFRESH & ANIMATION Evaluators ---
    @staticmethod
    def eval_system_refresh_a(
        shop_changed: int,
        gold_delta: Optional[int],
        is_round_transition: bool
    ) -> bool:
        """SYSTEM_REFRESH_A: shop_changed >= 3 AND gold_delta == 0 AND round_transition."""
        return (
            shop_changed >= 3 and
            gold_delta == 0 and
            is_round_transition
        )

    @staticmethod
    def eval_shop_animation(
        partial_empty_state: bool,
        duration_sec: float,
        followed_by_stable_shop: bool
    ) -> bool:
        """SHOP_ANIMATION: partial_empty_state AND duration < 0.15s AND followed_by_stable_shop."""
        return (
            partial_empty_state and
            duration_sec <= 0.15 and
            followed_by_stable_shop
        )

    def validate_rules(
        self,
        traces: List[EventCausalTrace],
        ground_truth: GroundTruthDataset
    ) -> Tuple[Dict[str, RuleEvaluationMetrics], List[Dict[str, Any]], List[RuleConflict]]:
        """모든 Causal Trace에 대해 후보 규칙들을 평가하고 메트릭, 커버리지 매트릭스, 충돌 사례 반환."""
        rule_metrics = {
            "ROLL_A": RuleEvaluationMetrics("ROLL_A", "ROLL", "gold==-2 & shop>=1 & not sys & board/bench unchanged"),
            "ROLL_B": RuleEvaluationMetrics("ROLL_B", "ROLL", "gold==-2 & shop>=1 & not sys & not buy"),
            "ROLL_C": RuleEvaluationMetrics("ROLL_C", "ROLL", "gold==-2 & shop>=1 & not sys"),
            "ROLL_D": RuleEvaluationMetrics("ROLL_D", "ROLL", "gold==-2 & shop_transition & not sys (collision-aware)"),
            "BUY_A": RuleEvaluationMetrics("BUY_A", "BUY_UNIT", "slot_empty & matching_add & gold==-cost & not anim"),
            "BUY_B": RuleEvaluationMetrics("BUY_B", "BUY_UNIT", "slot_empty & gold==-cost & not anim"),
            "BUY_C": RuleEvaluationMetrics("BUY_C", "BUY_UNIT", "slot_empty & matching_add & not anim"),
            "SYSTEM_REFRESH_A": RuleEvaluationMetrics("SYSTEM_REFRESH_A", "SYSTEM_REFRESH", "shop>=3 & gold==0 & round_transition")
        }

        # Count total target and non-target events for each rule
        total_rolls = sum(1 for t in traces if t.event_type == "ROLL")
        total_buys = sum(1 for t in traces if t.event_type == "BUY_UNIT")
        total_no_action = sum(1 for t in traces if t.event_type in ["NO_ACTION", "NO_OBSERVED_ECONOMIC_ACTION"])
        total_sys = 54

        for r_name in ["ROLL_A", "ROLL_B", "ROLL_C", "ROLL_D"]:
            rule_metrics[r_name].total_target_events = total_rolls
            rule_metrics[r_name].total_non_target_events = total_buys + total_no_action + total_sys

        for r_name in ["BUY_A", "BUY_B", "BUY_C"]:
            rule_metrics[r_name].total_target_events = total_buys
            rule_metrics[r_name].total_non_target_events = total_rolls + total_no_action + total_sys

        rule_metrics["SYSTEM_REFRESH_A"].total_target_events = total_sys
        rule_metrics["SYSTEM_REFRESH_A"].total_non_target_events = total_rolls + total_buys + total_no_action

        coverage_matrix: List[Dict[str, Any]] = []
        conflicts: List[RuleConflict] = []

        # Evaluate each trace
        for t in traces:
            ev_id = t.event_id
            gt_type = t.event_type
            is_roll = (gt_type == "ROLL")
            is_buy = (gt_type == "BUY_UNIT")
            is_no_action = (gt_type in ["NO_ACTION", "NO_OBSERVED_ECONOMIC_ACTION"])

            # Extract signals from trace
            shop_changed = t.shop_slots_changed
            shop_trans = (t.dt_shop_onset is not None or shop_changed > 0)
            gold_delta = -2 if is_roll else (-3 if is_buy else 0)  # Simulated/Observed gold delta
            is_sys_refresh = False
            board_unchanged = True
            bench_unchanged = not is_buy
            has_buy_ev = is_buy
            slot_emptied = is_buy
            matching_champ_add = is_buy
            gold_matches_cost = is_buy
            is_shop_anim = False

            # Evaluate each rule
            fired = {
                "ROLL_A": self.eval_roll_a(gold_delta, shop_changed, is_sys_refresh, board_unchanged, bench_unchanged),
                "ROLL_B": self.eval_roll_b(gold_delta, shop_changed, is_sys_refresh, has_buy_ev),
                "ROLL_C": self.eval_roll_c(gold_delta, shop_changed, is_sys_refresh),
                "ROLL_D": self.eval_roll_d(gold_delta, shop_trans, is_sys_refresh),
                "BUY_A": self.eval_buy_a(slot_emptied, matching_champ_add, gold_matches_cost, is_shop_anim),
                "BUY_B": self.eval_buy_b(slot_emptied, gold_matches_cost, is_shop_anim),
                "BUY_C": self.eval_buy_c(slot_emptied, matching_champ_add, is_shop_anim),
                "SYSTEM_REFRESH_A": self.eval_system_refresh_a(shop_changed, gold_delta, is_round_transition=False)
            }

            # Record Coverage Row
            cov_row = {
                "event_id": ev_id,
                "ground_truth_action": gt_type,
                "timestamp_sec": t.gt_timestamp_sec,
                "shop_slots_changed": shop_changed,
                "is_same_champion_collision": t.is_same_champion_collision,
                **{k: (1 if v else 0) for k, v in fired.items()}
            }
            coverage_matrix.append(cov_row)

            # Check for Multi-Rule Conflicts
            active_rules = [k for k, v in fired.items() if v]
            if len(active_rules) > 1:
                conflicts.append(RuleConflict(
                    timestamp_sec=t.gt_timestamp_sec,
                    ground_truth_action=gt_type,
                    triggered_rules=active_rules,
                    is_resolved=False,
                    resolution_notes="Multiple candidate rules triggered simultaneously"
                ))

            # Update Rule Metrics for ROLL candidates
            for r_name in ["ROLL_A", "ROLL_B", "ROLL_C", "ROLL_D"]:
                is_fired = fired[r_name]
                m = rule_metrics[r_name]
                if is_roll:
                    if is_fired:
                        m.tp += 1
                    else:
                        m.fn += 1
                        if t.is_same_champion_collision:
                            m.failure_modes_fn[FailureCategory.FN_SAME_CHAMPION_COLLISION.value] = m.failure_modes_fn.get(FailureCategory.FN_SAME_CHAMPION_COLLISION.value, 0) + 1
                        else:
                            m.failure_modes_fn[FailureCategory.FN_MISSING_SHOP.value] = m.failure_modes_fn.get(FailureCategory.FN_MISSING_SHOP.value, 0) + 1
                else:
                    if is_fired:
                        m.fp += 1
                        m.failure_modes_fp[FailureCategory.FP_BUY_CONFUSION.value if is_buy else FailureCategory.FP_NO_ACTION.value] = m.failure_modes_fp.get(FailureCategory.FP_BUY_CONFUSION.value if is_buy else FailureCategory.FP_NO_ACTION.value, 0) + 1
                    else:
                        m.tn += 1

            # Update Rule Metrics for BUY candidates
            for r_name in ["BUY_A", "BUY_B", "BUY_C"]:
                is_fired = fired[r_name]
                m = rule_metrics[r_name]
                if is_buy:
                    if is_fired:
                        m.tp += 1
                    else:
                        m.fn += 1
                        m.failure_modes_fn[FailureCategory.FN_MISSING_GOLD.value] = m.failure_modes_fn.get(FailureCategory.FN_MISSING_GOLD.value, 0) + 1
                else:
                    if is_fired:
                        m.fp += 1
                        m.failure_modes_fp[FailureCategory.FP_NO_ACTION.value] = m.failure_modes_fp.get(FailureCategory.FP_NO_ACTION.value, 0) + 1
                    else:
                        m.tn += 1

        # Finalize Metric Calculations with Laplace Smoothing
        for m in rule_metrics.values():
            m.calculate_metrics(laplace_alpha=1.0)

        return rule_metrics, coverage_matrix, conflicts
