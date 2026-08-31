"""Dual Review Manager and Inter-Rater Reliability Calculator v1.1.

Implements:
- Dual independent reviews per checkpoint (REVIEWER_A vs REVIEWER_B)
- Raw agreement rate calculation
- Cohen's Kappa calculation: kappa = (Po - Pe) / (1 - Pe)
- Disagreement tracking without manual override
"""
from __future__ import annotations
from collections import defaultdict
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from tft.dataset_collection.models import (
    DualReviewRecord,
    HumanReview,
    ActionTypeEnum
)


class DualReviewManager:
    """Manages secondary reviewer submissions and computes inter-rater agreement."""

    def __init__(self):
        pass

    @staticmethod
    def calculate_cohens_kappa(
        primary_reviews: List[str],
        secondary_reviews: List[str],
        categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Calculates Cohen's Kappa score between primary and secondary reviewers.

        kappa = (Po - Pe) / (1 - Pe)
        """
        n = len(primary_reviews)
        if n == 0 or len(secondary_reviews) != n:
            return {
                "sample_size": 0,
                "raw_agreement_rate": 0.0,
                "expected_agreement_rate": 0.0,
                "cohens_kappa": 0.0,
                "interpretation": "INSUFFICIENT_DATA"
            }

        cats = categories or list(set(primary_reviews + secondary_reviews))
        if not cats:
            cats = [ActionTypeEnum.ROLL.value, ActionTypeEnum.LEVEL_UP.value, ActionTypeEnum.SAVE_GOLD.value]

        # 1. Observed Agreement (Po)
        matches = sum(1 for p, s in zip(primary_reviews, secondary_reviews) if p == s)
        po = matches / n

        # 2. Expected Agreement (Pe)
        p_counts = defaultdict(int)
        s_counts = defaultdict(int)
        for p, s in zip(primary_reviews, secondary_reviews):
            p_counts[p] += 1
            s_counts[s] += 1

        pe = sum((p_counts[c] / n) * (s_counts[c] / n) for c in cats)

        # 3. Kappa
        if pe >= 1.0 or (1.0 - pe) == 0.0:
            kappa = 1.0 if po == 1.0 else 0.0
        else:
            kappa = (po - pe) / (1.0 - pe)

        kappa = round(max(-1.0, min(1.0, kappa)), 4)
        po_round = round(po, 4)
        pe_round = round(pe, 4)

        # Interpretation based on standard Landis & Koch (1977)
        if kappa >= 0.81:
            interp = "ALMOST_PERFECT_AGREEMENT"
        elif kappa >= 0.61:
            interp = "SUBSTANTIAL_AGREEMENT"
        elif kappa >= 0.41:
            interp = "MODERATE_AGREEMENT"
        elif kappa >= 0.21:
            interp = "FAIR_AGREEMENT"
        elif kappa >= 0.0:
            interp = "SLIGHT_AGREEMENT"
        else:
            interp = "POOR_AGREEMENT"

        return {
            "sample_size": n,
            "raw_agreement_rate": po_round,
            "expected_agreement_rate": pe_round,
            "cohens_kappa": kappa,
            "interpretation": interp
        }

    @staticmethod
    def identify_disagreements(
        primary_reviews: Dict[str, HumanReview],
        dual_reviews: Dict[str, List[DualReviewRecord]]
    ) -> List[Dict[str, Any]]:
        """Finds and catalogues all inter-rater disagreement checkpoints."""
        disagreements = []
        for cp_id, prim in primary_reviews.items():
            duals = dual_reviews.get(cp_id, [])
            for d in duals:
                if prim.human_preferred_action != d.human_preferred_action:
                    disagreements.append({
                        "checkpoint_id": cp_id,
                        "primary_reviewer": prim.reviewer_id,
                        "primary_preference": prim.human_preferred_action,
                        "primary_confidence": prim.human_confidence,
                        "secondary_reviewer": d.reviewer_id,
                        "secondary_preference": d.human_preferred_action,
                        "secondary_confidence": d.human_confidence,
                        "status": "INTER_RATER_DISAGREEMENT_PRESERVED"
                    })
        return disagreements
