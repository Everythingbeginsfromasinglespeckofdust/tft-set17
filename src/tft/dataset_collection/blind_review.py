"""Blind Review Workflow State Machine for TFT Real Match Dataset Collection v1.1.

Enforces strict sequential order to eliminate cognitive confirmation bias:
1. STATE_ENTRY (T0 State)
2. HUMAN_PREFERENCE (Independent human choice + confidence)
3. ACTUAL_ACTION (Observed video action)
4. REVEAL_ENGINE (Unlocks baseline engine output)
5. HUMAN_JUDGMENT (Quality review & rationale)
6. OUTCOME_LINK (Post-review T1/T2 linkage)
"""
from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class CollectionStep(str, Enum):
    STATE_ENTRY = "STATE_ENTRY"
    HUMAN_PREFERENCE = "HUMAN_PREFERENCE"
    ACTUAL_ACTION = "ACTUAL_ACTION"
    REVEAL_ENGINE = "REVEAL_ENGINE"
    HUMAN_JUDGMENT = "HUMAN_JUDGMENT"
    OUTCOME_LINK = "OUTCOME_LINK"


class BlindReviewWorkflow:
    """State machine enforcing strict blind review order."""

    STEP_ORDER = [
        CollectionStep.STATE_ENTRY,
        CollectionStep.HUMAN_PREFERENCE,
        CollectionStep.ACTUAL_ACTION,
        CollectionStep.REVEAL_ENGINE,
        CollectionStep.HUMAN_JUDGMENT,
        CollectionStep.OUTCOME_LINK
    ]

    def __init__(self, current_step: CollectionStep = CollectionStep.STATE_ENTRY):
        self.current_step = current_step
        self.step_history: List[CollectionStep] = [current_step]

    def is_engine_recommendation_allowed(self) -> bool:
        """Engine recommendation is ONLY visible at or after REVEAL_ENGINE step."""
        allowed_steps = {
            CollectionStep.REVEAL_ENGINE,
            CollectionStep.HUMAN_JUDGMENT,
            CollectionStep.OUTCOME_LINK
        }
        return self.current_step in allowed_steps

    def is_candidate_recommendation_allowed(self) -> bool:
        """Candidate engine recommendations are strictly forbidden during collection mode."""
        return False

    def is_outcome_allowed(self) -> bool:
        """T1/T2 outcomes are ONLY revealed after HUMAN_JUDGMENT is finalized."""
        return self.current_step == CollectionStep.OUTCOME_LINK

    def advance_to(self, target_step: CollectionStep) -> Tuple[bool, Optional[str]]:
        """Advances the state machine verifying strict forward transition."""
        curr_idx = self.STEP_ORDER.index(self.current_step)
        target_idx = self.STEP_ORDER.index(target_step)

        # Must move sequentially or allow stay
        if target_idx < curr_idx:
            return False, f"Cannot revert from {self.current_step.value} to {target_step.value}"
        if target_idx > curr_idx + 1:
            return False, f"Cannot skip from {self.current_step.value} to {target_step.value}"

        self.current_step = target_step
        self.step_history.append(target_step)
        return True, None

    def filter_response_payload(self, full_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Filters a payload to strip hidden fields based on current step."""
        filtered = dict(full_payload)
        
        # Strip engine prediction if not yet revealed
        if not self.is_engine_recommendation_allowed():
            if "engine_prediction" in filtered:
                filtered["engine_prediction"] = {
                    "status": "HIDDEN_UNTIL_PREFERENCE_SUBMITTED",
                    "recommended_action": "BLIND_HIDDEN"
                }
            if "prediction" in filtered:
                filtered["prediction"] = {
                    "status": "HIDDEN_UNTIL_PREFERENCE_SUBMITTED",
                    "recommended_action": "BLIND_HIDDEN"
                }

        # Strip Candidate recommendation
        filtered.pop("candidate_prediction", None)
        filtered.pop("candidate_adjustments", None)

        # Strip T1 outcome if not yet in outcome phase
        if not self.is_outcome_allowed():
            if "t1_outcome" in filtered:
                filtered["t1_outcome"] = {
                    "status": "HIDDEN_UNTIL_REVIEW_FINALIZED"
                }

        return filtered
