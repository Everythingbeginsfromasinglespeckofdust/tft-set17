"""Collection Controller Orchestrator for TFT Real Match Dataset Collection v1.1.

Coordinates video verification, blind workflow state transitions, frame evidence capture,
dual review submission, multi-horizon outcome linking, and live progress dashboard.
"""
from __future__ import annotations
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from tft.domain.game_state import GameState
from tft.decision.engine import DecisionEngine
from tft.decision.scorer import DEFAULT_DECISION_CONFIG
from tft.dataset_collection.models import (
    SessionManifest,
    RawState,
    FrameEvidence,
    EnginePrediction,
    ActualPlayerAction,
    HumanReview,
    DualReviewRecord,
    InteractionLog,
    DatasetRow
)
from tft.dataset_collection.session_manager import SessionManager
from tft.dataset_collection.blind_review import BlindReviewWorkflow, CollectionStep
from tft.dataset_collection.evidence_capture import VideoSourceValidator, FrameEvidenceCapturer
from tft.dataset_collection.dual_reviewer import DualReviewManager
from tft.dataset_collection.integrity_validator import IntegrityValidator


class CollectionController:
    """Orchestrates human dataset collection sessions in v1.1 mode."""

    def __init__(self, session_manager: Optional[SessionManager] = None):
        self.session_mgr = session_manager or SessionManager()
        self.engine = DecisionEngine(config=DEFAULT_DECISION_CONFIG)
        self.video_validator = VideoSourceValidator()
        self.dual_mgr = DualReviewManager()
        self.integrity_validator = IntegrityValidator()
        self.active_workflows: Dict[str, BlindReviewWorkflow] = {}

    def get_workflow(self, session_id: str, checkpoint_id: str) -> BlindReviewWorkflow:
        key = f"{session_id}_{checkpoint_id}"
        if key not in self.active_workflows:
            self.active_workflows[key] = BlindReviewWorkflow(CollectionStep.STATE_ENTRY)
        return self.active_workflows[key]

    def create_session(
        self,
        session_id: str,
        match_id: Optional[str] = None,
        video_path: Optional[str] = None,
        patch: str = "14.x_18.1",
        set_num: int = 18,
        notes: str = ""
    ) -> SessionManifest:
        """Creates new collection session verifying video source validity."""
        if video_path and os.path.exists(video_path):
            is_orig, reason = self.video_validator.validate_video_file(video_path)
            if not is_orig:
                raise ValueError(f"Video file rejected: {reason}")

        return self.session_mgr.create_session(
            session_id=session_id,
            match_id=match_id or session_id,
            video_path=video_path,
            patch=patch,
            set_num=set_num,
            notes=notes
        )

    def reveal_recommendation(
        self,
        session_id: str,
        checkpoint_id: str,
        state: GameState
    ) -> Dict[str, Any]:
        """Calculates and reveals baseline DecisionEngine output once preference is logged."""
        wf = self.get_workflow(session_id, checkpoint_id)
        
        # Advance workflow to REVEAL_ENGINE
        ok, err = wf.advance_to(CollectionStep.REVEAL_ENGINE)
        if not ok and wf.current_step not in [CollectionStep.REVEAL_ENGINE, CollectionStep.HUMAN_JUDGMENT, CollectionStep.OUTCOME_LINK]:
            raise ValueError(f"Cannot reveal recommendation: {err}")

        rec = self.engine.decide(state)
        act_scores = {
            s.action_type.value: round(float(s.score), 4)
            for s in rec.action_scores
        }
        reasons_list = [f"{r.factor}: {r.description}" for r in rec.reasons]

        pred = EnginePrediction(
            recommended_action=rec.recommended_action.action_type.value,
            score=round(float(rec.recommended_action.score), 4),
            action_scores=act_scores,
            action_score_gap=round(float(rec.decision_margin), 4),
            confidence=round(float(rec.confidence), 4),
            reasons=reasons_list,
            direction_now=f"Recommendation: {rec.recommended_action.action_type.value}"
        )

        return pred.to_dict()

    def get_progress_dashboard(self) -> Dict[str, Any]:
        """Computes live collection progress dashboard from raw dataset."""
        sessions = self.session_mgr.list_sessions()
        manifests = [self.session_mgr.load_manifest(s) for s in sessions if self.session_mgr.load_manifest(s)]
        rows: List[DatasetRow] = []
        for s in sessions:
            rows.extend(self.session_mgr.load_all_session_rows(s))

        gate = self.integrity_validator.evaluate_calibration_gate(manifests, rows)
        
        valid_cnt = sum(1 for r in rows if r.quality_flag == "VALID")
        invalid_cnt = len(rows) - valid_cnt
        reviewed_cnt = sum(1 for r in rows if r.human_review.get("human_preferred_action", "UNKNOWN") != "UNKNOWN")
        dual_cnt = sum(1 for r in rows if len(r.dual_reviews) > 0)
        t1_linked_cnt = sum(1 for r in rows if r.t1_outcome.get("t1_checkpoint_id") is not None)

        return {
            "matches_count": f"{gate['total_matches']} / 5",
            "total_matches": gate["total_matches"],
            "total_checkpoints": len(rows),
            "valid_checkpoints": valid_cnt,
            "invalid_checkpoints": invalid_cnt,
            "human_reviewed_count": reviewed_cnt,
            "dual_reviewed_count": dual_cnt,
            "t1_linked_count": t1_linked_cnt,
            "gate_verdict": gate["final_gate_verdict"],
            "recommendation": gate["honest_recommendation"]
        }
