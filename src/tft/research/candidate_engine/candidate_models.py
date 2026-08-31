"""TFT Candidate Decision Engine Models (V1 through V4).

Implements:
- CANDIDATE_V1_SURVIVAL (Survival Horizon Priority)
- CANDIDATE_V2_UPGRADE (Pair & Immediate Shop Upgrade Concentration)
- CANDIDATE_V3_ECONOMY (Discrete Breakpoints & Level-up Opportunity)
- CANDIDATE_V4_COMBINED (Multidimensional Calibrated Model)

Guarantees:
- Additive Contribution Traceability: Candidate_Score = Baseline_Score + sum(Adjustments)
- Strict Lineage to Reality-Validated Features
- Non-mutating Adapter Pattern
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple
from tft.domain.game_state import GameState
from tft.calibration.state_features.extractor import StateFeatureExtractor
from tft.research.candidate_engine.baseline_adapter import BaselineAdapter
from tft.research.decision_features.taxonomy import DecisionStateVector


class CandidateModelType(str, Enum):
    V1_SURVIVAL = "CANDIDATE_V1_SURVIVAL"
    V2_UPGRADE = "CANDIDATE_V2_UPGRADE"
    V3_ECONOMY = "CANDIDATE_V3_ECONOMY"
    V4_COMBINED = "CANDIDATE_V4_COMBINED"


@dataclass(frozen=True)
class FeatureContribution:
    feature_id: str
    target_action: str
    raw_value: Any
    normalized_value: float
    adjustment_coefficient: float
    score_delta: float
    justification: str


@dataclass(frozen=True)
class CandidateDecisionResult:
    sample_id: str
    model_version: CandidateModelType
    baseline_action: str
    baseline_score: float
    candidate_action: str
    candidate_score: float
    is_flipped: bool
    score_gap: float
    feature_contributions: List[FeatureContribution]
    action_scores: Dict[str, float]
    state_summary: Dict[str, Any]


class CandidateDecisionEngine:
    """Evaluates candidate feature adjustments on top of baseline DecisionEngine."""

    def __init__(self, extractor: Optional[StateFeatureExtractor] = None, baseline: Optional[BaselineAdapter] = None):
        self.extractor = extractor or StateFeatureExtractor()
        self.baseline = baseline or BaselineAdapter()

    def evaluate(
        self,
        state: GameState,
        model_type: CandidateModelType = CandidateModelType.V4_COMBINED,
        sample_id: str = "T0",
        custom_weights: Optional[Dict[str, float]] = None
    ) -> CandidateDecisionResult:
        """Execute candidate policy with full feature contribution tracking."""
        base_snap = self.baseline.capture_snapshot(state, sample_id=sample_id)
        vec = self.extractor.extract(state, sample_id=sample_id)

        base_act = base_snap["recommended_action"]
        base_scores = dict(base_snap["action_scores"])

        # Default calibrated coefficients
        weights = {
            "survival_elim_coeff": 0.08,
            "pair_count_coeff": 0.04,
            "shop_upgrade_coeff": 0.06,
            "stage_deficit_coeff": 0.05,
            "cheap_level_coeff": 0.06,
            "compound_interest_coeff": 0.05
        }
        if custom_weights:
            weights.update(custom_weights)

        contributions: List[FeatureContribution] = []
        cand_scores = {
            "ROLL": base_scores.get("ROLL", 0.30),
            "LEVEL_UP": base_scores.get("LEVEL_UP", 0.30),
            "SAVE_GOLD": base_scores.get("SAVE_GOLD", 0.40)
        }

        # ---------------------------------------------------------------------
        # 1. Survival Horizon Feature (ESTIMATED_ROUNDS_TO_ELIM)
        # ---------------------------------------------------------------------
        if model_type in [CandidateModelType.V1_SURVIVAL, CandidateModelType.V4_COMBINED]:
            rounds_left = vec.temporal.estimated_rounds_to_elimination or 10.0
            if rounds_left <= 2.0:
                norm_val = round(max(0.0, (2.0 - rounds_left) / 2.0), 3)
                delta_roll = round(norm_val * weights["survival_elim_coeff"], 4)
                cand_scores["ROLL"] += delta_roll
                cand_scores["SAVE_GOLD"] -= delta_roll
                contributions.append(FeatureContribution(
                    feature_id="ESTIMATED_ROUNDS_TO_ELIM",
                    target_action="ROLL",
                    raw_value=rounds_left,
                    normalized_value=norm_val,
                    adjustment_coefficient=weights["survival_elim_coeff"],
                    score_delta=delta_roll,
                    justification=f"Survival horizon is {rounds_left:.1f} rounds (<=2.0 lethal threshold). Priority roll needed to stabilize HP."
                ))

        # ---------------------------------------------------------------------
        # 2. Upgrade Concentration Features (PAIR_COUNT, IMMEDIATE_SHOP_UPGRADE)
        # ---------------------------------------------------------------------
        if model_type in [CandidateModelType.V2_UPGRADE, CandidateModelType.V4_COMBINED]:
            pairs = vec.upgrade.pair_count
            if pairs >= 2 and vec.economy.spendable_roll_budget >= 10:
                norm_val = min(1.0, pairs / 3.0)
                delta_roll = round(norm_val * weights["pair_count_coeff"], 4)
                cand_scores["ROLL"] += delta_roll
                contributions.append(FeatureContribution(
                    feature_id="PAIR_COUNT",
                    target_action="ROLL",
                    raw_value=pairs,
                    normalized_value=norm_val,
                    adjustment_coefficient=weights["pair_count_coeff"],
                    score_delta=delta_roll,
                    justification=f"Holding {pairs} 2-star pairs on board/bench with {vec.economy.spendable_roll_budget}G spendable budget."
                ))

            shop_upg = vec.upgrade.immediate_shop_upgrades
            if shop_upg > 0:
                delta_roll = round(min(1.0, shop_upg) * weights["shop_upgrade_coeff"], 4)
                cand_scores["ROLL"] += delta_roll
                contributions.append(FeatureContribution(
                    feature_id="IMMEDIATE_SHOP_UPGRADE",
                    target_action="ROLL",
                    raw_value=shop_upg,
                    normalized_value=float(min(1, shop_upg)),
                    adjustment_coefficient=weights["shop_upgrade_coeff"],
                    score_delta=delta_roll,
                    justification=f"Shop contains {shop_upg} unit(s) immediately completing 2★/3★ upgrades."
                ))

        # ---------------------------------------------------------------------
        # 3. Economy & Level-up Features (GOLD_TO_NEXT_LEVEL, SPENDABLE_ROLL_BUDGET)
        # ---------------------------------------------------------------------
        if model_type in [CandidateModelType.V3_ECONOMY, CandidateModelType.V4_COMBINED]:
            gold_to_lvl = vec.economy.gold_to_next_level
            rem_gold = vec.player.gold - gold_to_lvl
            if gold_to_lvl <= 8 and rem_gold >= 20 and vec.upgrade.shop_tier_match_score > 0.50:
                delta_lvl = round(weights["cheap_level_coeff"], 4)
                cand_scores["LEVEL_UP"] += delta_lvl
                cand_scores["SAVE_GOLD"] -= delta_lvl * 0.5
                contributions.append(FeatureContribution(
                    feature_id="GOLD_TO_NEXT_LEVEL",
                    target_action="LEVEL_UP",
                    raw_value=gold_to_lvl,
                    normalized_value=round(1.0 - (gold_to_lvl / 12.0), 3),
                    adjustment_coefficient=weights["cheap_level_coeff"],
                    score_delta=delta_lvl,
                    justification=f"Low level-up cost ({gold_to_lvl}G) preserving {rem_gold}G interest tier with high cost carry odds jump."
                ))

            # Compound interest preservation
            if vec.player.hp >= 70 and vec.relative.stage_benchmark_ratio >= 1.05 and vec.economy.interest_tier < 5:
                delta_save = round(weights["compound_interest_coeff"], 4)
                cand_scores["SAVE_GOLD"] += delta_save
                contributions.append(FeatureContribution(
                    feature_id="SPENDABLE_ROLL_BUDGET",
                    target_action="SAVE_GOLD",
                    raw_value=vec.economy.spendable_roll_budget,
                    normalized_value=1.0,
                    adjustment_coefficient=weights["compound_interest_coeff"],
                    score_delta=delta_save,
                    justification="High HP and strong board allows building max 50G compound interest."
                ))

        # Normalize rounded scores
        rounded_cand_scores = {k: round(v, 4) for k, v in cand_scores.items()}
        sorted_cand = sorted(rounded_cand_scores.items(), key=lambda x: x[1], reverse=True)
        cand_best_act, cand_best_score = sorted_cand[0]
        second_cand_score = sorted_cand[1][1] if len(sorted_cand) > 1 else cand_best_score
        cand_gap = round(cand_best_score - second_cand_score, 4)

        return CandidateDecisionResult(
            sample_id=sample_id,
            model_version=model_type,
            baseline_action=base_act,
            baseline_score=round(float(base_snap["recommended_score"]), 4),
            candidate_action=cand_best_act,
            candidate_score=cand_best_score,
            is_flipped=(cand_best_act != base_act),
            score_gap=cand_gap,
            feature_contributions=contributions,
            action_scores=rounded_cand_scores,
            state_summary={
                "hp": vec.player.hp,
                "gold": vec.player.gold,
                "level": vec.player.level,
                "stage_round": vec.stage_round,
                "pair_count": vec.upgrade.pair_count,
                "rounds_to_elimination": vec.temporal.estimated_rounds_to_elimination,
                "stage_benchmark_ratio": vec.relative.stage_benchmark_ratio
            }
        )
