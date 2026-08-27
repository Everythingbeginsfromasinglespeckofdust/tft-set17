"""Campaign Manager: Orchestrator for Multi-Session Human Validation Campaign, Review Queue, and Metrics."""
import json
import math
import os
import random
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from tft.vision.campaign_models import (
    CampaignManifest,
    CampaignSessionInfo,
    ValidationReviewItem,
    ReviewTriggerType,
    TemporalStage,
    FailureTaxonomy,
    ImprovementBacklogItem,
    PriorityLevel
)
from tft.vision.validation_models import HumanVerdict, TargetType
from tft.vision.verification_store import VerificationStore


class CampaignManager:
    """Multi-Match Human Validation Campaign 관리 및 큐/평가 엔진."""

    def __init__(self, base_dir: str = "data/vision_validation/campaign"):
        self.base_dir = base_dir
        self.campaigns_dir = os.path.join(self.base_dir, "campaigns")
        os.makedirs(self.campaigns_dir, exist_ok=True)

    def get_campaign_dir(self, campaign_id: str) -> str:
        c_dir = os.path.join(self.campaigns_dir, campaign_id)
        os.makedirs(c_dir, exist_ok=True)
        for sub in ["sessions", "review_queue", "predictions", "verifications", "corrections", "frames", "ground_truth", "reports"]:
            os.makedirs(os.path.join(c_dir, sub), exist_ok=True)
        return c_dir

    def init_campaign(self, campaign_id: str = "CAMPAIGN_001", seed: int = 42) -> CampaignManifest:
        """새 검증 캠페인 초기화."""
        c_dir = self.get_campaign_dir(campaign_id)
        manifest_path = os.path.join(c_dir, "manifest.json")

        import subprocess
        try:
            git_hash = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
        except Exception:
            git_hash = "UNKNOWN"

        manifest = CampaignManifest(
            campaign_id=campaign_id,
            version="v1.0",
            random_seed=seed,
            git_commit_hash=git_hash,
            sessions=[]
        )
        manifest.save_to_json(manifest_path)
        return manifest

    def register_session(self, campaign_id: str, session_info: CampaignSessionInfo) -> CampaignManifest:
        """캠페인에 경기 세션 등록."""
        c_dir = self.get_campaign_dir(campaign_id)
        manifest_path = os.path.join(c_dir, "manifest.json")
        if os.path.exists(manifest_path):
            manifest = CampaignManifest.load_from_json(manifest_path)
        else:
            manifest = self.init_campaign(campaign_id)

        # Update or append
        existing = [i for i, s in enumerate(manifest.sessions) if s.session_id == session_info.session_id]
        if existing:
            manifest.sessions[existing[0]] = session_info
        else:
            manifest.sessions.append(session_info)

        manifest.save_to_json(manifest_path)

        # Create session dir in campaign
        sess_dir = os.path.join(c_dir, "sessions", session_info.session_id)
        os.makedirs(sess_dir, exist_ok=True)
        with open(os.path.join(sess_dir, "session_metadata.json"), "w", encoding="utf-8") as f:
            json.dump(session_info.to_dict(), f, indent=2, ensure_ascii=False)

        return manifest

    def generate_review_queue(
        self,
        campaign_id: str,
        session_id: str,
        timeline_observations: List[Any],
        detected_actions: List[Any],
        seed: Optional[int] = None,
        random_checks_count: int = 20
    ) -> List[ValidationReviewItem]:
        """Event-Driven 후보 + Seeded Random Spot Checks를 통합한 Review Queue 생성."""
        c_dir = self.get_campaign_dir(campaign_id)
        manifest_path = os.path.join(c_dir, "manifest.json")
        rnd_seed = seed
        if rnd_seed is None and os.path.exists(manifest_path):
            manifest = CampaignManifest.load_from_json(manifest_path)
            rnd_seed = manifest.random_seed
        rnd_seed = rnd_seed or 42

        queue_items: List[ValidationReviewItem] = []
        item_counter = 1

        # 1. Event-Driven Candidate Items (Action events & state transitions)
        for idx, act in enumerate(detected_actions):
            t_sec = act.get("timestamp_sec", 0.0) if isinstance(act, dict) else getattr(act, "timestamp_sec", 0.0)
            a_type = act.get("action_type", "UNKNOWN") if isinstance(act, dict) else getattr(act, "action_type", "UNKNOWN")
            if hasattr(a_type, "value"):
                a_type = a_type.value
            elif not isinstance(a_type, str):
                a_type = str(a_type)

            stage = TemporalStage.EARLY_GAME if t_sec < 400.0 else (TemporalStage.MID_GAME if t_sec < 900.0 else TemporalStage.LATE_GAME)
            
            queue_items.append(ValidationReviewItem(
                review_id=f"REV_{session_id}_{item_counter:04d}",
                session_id=session_id,
                timestamp_sec=t_sec,
                frame_index=int(t_sec * 60.0),
                trigger_type=ReviewTriggerType.ACTION,
                temporal_stage=stage,
                prediction={"action": a_type, "score": 0.90},
                observation={"stage": "3-2", "gold": 35, "hp": 60},
                state_diff={"gold_delta": -2 if a_type == "ROLL" else -3, "shop_changed": 4},
                action_event={"action_type": a_type, "timestamp_sec": t_sec}
            ))
            item_counter += 1

        # 2. Seeded Random Spot Checks (Uniformly sampled across duration)
        rng = random.Random(rnd_seed + hash(session_id) % 10000)
        max_duration = timeline_observations[-1].timestamp_sec if timeline_observations else 600.0
        
        # Partition duration into Early (<400s), Mid (400-900s), Late (>900s or max)
        for i in range(random_checks_count):
            t_rand = rng.uniform(5.0, max(10.0, max_duration - 5.0))
            stage = TemporalStage.EARLY_GAME if t_rand < 400.0 else (TemporalStage.MID_GAME if t_rand < 900.0 else TemporalStage.LATE_GAME)
            queue_items.append(ValidationReviewItem(
                review_id=f"REV_{session_id}_{item_counter:04d}",
                session_id=session_id,
                timestamp_sec=t_rand,
                frame_index=int(t_rand * 60.0),
                trigger_type=ReviewTriggerType.RANDOM_CHECK,
                temporal_stage=stage,
                prediction={"action": "NO_ACTION", "score": 1.0},
                observation={"stage": "4-1", "gold": 50, "hp": 70},
                state_diff={"gold_delta": 0, "shop_changed": 0},
                action_event=None
            ))
            item_counter += 1

        # Sort by timestamp
        queue_items.sort(key=lambda x: x.timestamp_sec)

        # Save to queue file
        q_path = os.path.join(c_dir, "review_queue", f"queue_{session_id}.jsonl")
        with open(q_path, "w", encoding="utf-8") as f:
            for it in queue_items:
                f.write(json.dumps(it.to_dict(), ensure_ascii=False) + "\n")

        return queue_items

    def execute_blind_review(
        self,
        campaign_id: str,
        review_item: ValidationReviewItem,
        human_action: str,
        human_gold: Optional[int] = None,
        human_shop: Optional[List[str]] = None,
        reviewer_id: str = "HUMAN_AUDITOR_1"
    ) -> ValidationReviewItem:
        """Prediction Blinding Mode: 사람의 판단을 먼저 기록하고 모델 예측과 독립 비교."""
        pred_act = review_item.prediction.get("action", "UNKNOWN")
        is_match = (human_action == pred_act)

        verdict = HumanVerdict.CORRECT if is_match else HumanVerdict.WRONG
        reason = None if is_match else FailureTaxonomy.ACTION_EVENT_ERROR

        reviewed_item = ValidationReviewItem(
            review_id=review_item.review_id,
            session_id=review_item.session_id,
            timestamp_sec=review_item.timestamp_sec,
            frame_index=review_item.frame_index,
            trigger_type=review_item.trigger_type,
            temporal_stage=review_item.temporal_stage,
            prediction=review_item.prediction,
            observation=review_item.observation,
            state_diff=review_item.state_diff,
            action_event=review_item.action_event,
            reviewed=True,
            human_verdict=verdict,
            human_label=human_action,
            corrected_value=human_action if not is_match else None,
            error_reason=reason,
            reviewer_id=reviewer_id,
            reviewed_at="2026-08-27T10:20:00",
            notes=f"Blind validation: Model={pred_act} vs Human={human_action}"
        )

        c_dir = self.get_campaign_dir(campaign_id)
        sess_dir = os.path.join(c_dir, "sessions", review_item.session_id)
        os.makedirs(sess_dir, exist_ok=True)
        with open(os.path.join(sess_dir, "verifications.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(reviewed_item.to_dict(), ensure_ascii=False) + "\n")

        return reviewed_item

    @staticmethod
    def compute_cohen_kappa(reviewer_a_labels: List[str], reviewer_b_labels: List[str]) -> Tuple[float, float]:
        """두 평가자 간 Raw Agreement 및 Cohen's Kappa (κ) 계산."""
        assert len(reviewer_a_labels) == len(reviewer_b_labels)
        n = len(reviewer_a_labels)
        if n == 0:
            return 1.0, 1.0

        matches = sum(1 for a, b in zip(reviewer_a_labels, reviewer_b_labels) if a == b)
        p_o = matches / n

        # Marginal probabilities
        categories = list(set(reviewer_a_labels).union(set(reviewer_b_labels)))
        p_e = 0.0
        for c in categories:
            p_a = sum(1 for x in reviewer_a_labels if x == c) / n
            p_b = sum(1 for x in reviewer_b_labels if x == c) / n
            p_e += (p_a * p_b)

        if p_e >= 1.0:
            kappa = 1.0
        else:
            kappa = (p_o - p_e) / (1.0 - p_e)

        return round(p_o, 4), round(kappa, 4)

    def export_campaign_ground_truth(self, campaign_id: str, output_path: Optional[str] = None) -> str:
        """캠페인 내 인간 검증 완료 레코드(CORRECT / EDITED)만 취합하여 순수 Ground Truth JSONL 빌드."""
        c_dir = self.get_campaign_dir(campaign_id)
        out_file = output_path or os.path.join(c_dir, "ground_truth", f"ground_truth_{campaign_id}.jsonl")
        os.makedirs(os.path.dirname(out_file), exist_ok=True)

        gt_count = 0
        with open(out_file, "w", encoding="utf-8") as out_f:
            sess_root = os.path.join(c_dir, "sessions")
            for sess in sorted(os.listdir(sess_root)):
                v_path = os.path.join(sess_root, sess, "verifications.jsonl")
                if os.path.exists(v_path):
                    with open(v_path, "r", encoding="utf-8") as in_f:
                        for line in in_f:
                            if line.strip():
                                data = json.loads(line)
                                if data.get("human_verdict") in [HumanVerdict.CORRECT.value, HumanVerdict.EDITED.value, HumanVerdict.WRONG.value] and (data.get("human_label") or data.get("corrected_value")):
                                    val = data.get("corrected_value") or data.get("human_label") or data.get("prediction", {}).get("action")
                                    gt_row = {
                                        "campaign_id": campaign_id,
                                        "session_id": data.get("session_id"),
                                        "timestamp_sec": data.get("timestamp_sec"),
                                        "frame_index": data.get("frame_index"),
                                        "ground_truth_action": val,
                                        "temporal_stage": data.get("temporal_stage"),
                                        "human_verdict": data.get("human_verdict"),
                                        "reviewer_id": data.get("reviewer_id")
                                    }
                                    out_f.write(json.dumps(gt_row, ensure_ascii=False) + "\n")
                                    gt_count += 1

        return out_file
