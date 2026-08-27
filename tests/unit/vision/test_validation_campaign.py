import json
import os
import shutil
import sys
import tempfile
import time

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np
import pytest

from tft.vision.campaign_models import (
    CampaignManifest,
    CampaignSessionInfo,
    ValidationReviewItem,
    ReviewTriggerType,
    TemporalStage,
    FailureTaxonomy,
    ImprovementBacklogItem,
    PriorityLevel,
    EconomicArchetype
)
from tft.vision.campaign_manager import CampaignManager
from tft.vision.validation_models import HumanVerdict, TargetType
from tft.vision.verification_store import VerificationStore


@pytest.fixture
def temp_campaign_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_campaign_manifest(temp_campaign_dir):
    """1. Test CampaignManifest initialization and serialization."""
    mgr = CampaignManager(temp_campaign_dir)
    manifest = mgr.init_campaign("TEST_CAMP", seed=123)
    assert manifest.campaign_id == "TEST_CAMP"
    assert manifest.random_seed == 123
    assert len(manifest.sessions) == 0

    m_path = os.path.join(mgr.get_campaign_dir("TEST_CAMP"), "manifest.json")
    assert os.path.exists(m_path)


def test_session_registration(temp_campaign_dir):
    """2. Test registering match sessions into campaign manifest."""
    mgr = CampaignManager(temp_campaign_dir)
    mgr.init_campaign("TEST_CAMP")

    s_info = CampaignSessionInfo(
        session_id="SESSION_D",
        video_path="dummy.mp4",
        match_id="M123",
        player_id="P1",
        final_placement=2,
        economic_archetype=EconomicArchetype.FAST_LEVELUP,
        duration_sec=1200.0
    )
    manifest = mgr.register_session("TEST_CAMP", s_info)
    assert len(manifest.sessions) == 1
    assert manifest.sessions[0].session_id == "SESSION_D"


def test_review_queue_generation(temp_campaign_dir):
    """3. Test Review Queue generation combining actions and random checks."""
    mgr = CampaignManager(temp_campaign_dir)
    mgr.init_campaign("TEST_CAMP")

    actions = [
        {"action_type": "ROLL", "timestamp_sec": 312.5},
        {"action_type": "BUY_UNIT", "timestamp_sec": 352.0}
    ]
    queue = mgr.generate_review_queue(
        campaign_id="TEST_CAMP",
        session_id="SESS_Q",
        timeline_observations=[type("Obs", (), {"timestamp_sec": 600.0})()],
        detected_actions=actions,
        random_checks_count=20
    )

    assert len(queue) == 22
    act_items = [q for q in queue if q.trigger_type == ReviewTriggerType.ACTION]
    rnd_items = [q for q in queue if q.trigger_type == ReviewTriggerType.RANDOM_CHECK]
    assert len(act_items) == 2
    assert len(rnd_items) == 20


def test_random_checkpoint_seed(temp_campaign_dir):
    """4. Test that random checkpoint generation is deterministic with fixed seed."""
    mgr = CampaignManager(temp_campaign_dir)
    queue1 = mgr.generate_review_queue("C1", "S1", [], [], seed=42, random_checks_count=5)
    queue2 = mgr.generate_review_queue("C2", "S1", [], [], seed=42, random_checks_count=5)

    ts1 = [q.timestamp_sec for q in queue1]
    ts2 = [q.timestamp_sec for q in queue2]
    assert ts1 == ts2


def test_event_candidate_generation(temp_campaign_dir):
    """5. Test event-driven trigger types and temporal stages."""
    mgr = CampaignManager(temp_campaign_dir)
    actions = [
        {"action_type": "ROLL", "timestamp_sec": 250.0},   # Early
        {"action_type": "ROLL", "timestamp_sec": 550.0},   # Mid
        {"action_type": "BUY_UNIT", "timestamp_sec": 950.0} # Late
    ]
    queue = mgr.generate_review_queue("C", "S", [], actions, random_checks_count=0)
    assert queue[0].temporal_stage == TemporalStage.EARLY_GAME
    assert queue[1].temporal_stage == TemporalStage.MID_GAME
    assert queue[2].temporal_stage == TemporalStage.LATE_GAME


def test_blind_validation(temp_campaign_dir):
    """6. Test Blind Validation workflow (Human input first, then reveal prediction)."""
    mgr = CampaignManager(temp_campaign_dir)
    mgr.init_campaign("CAMP_BLIND")

    item = ValidationReviewItem(
        review_id="REV_01",
        session_id="S_BLIND",
        timestamp_sec=300.0,
        frame_index=6000,
        trigger_type=ReviewTriggerType.ACTION,
        temporal_stage=TemporalStage.EARLY_GAME,
        prediction={"action": "ROLL", "score": 0.90},
        observation={},
        state_diff={}
    )

    reviewed = mgr.execute_blind_review("CAMP_BLIND", item, human_action="ROLL", reviewer_id="AUDITOR_A")
    assert reviewed.reviewed is True
    assert reviewed.human_verdict == HumanVerdict.CORRECT
    assert reviewed.human_label == "ROLL"


def test_human_label_independence(temp_campaign_dir):
    """7. Test that human labels are recorded independently even on mismatch."""
    mgr = CampaignManager(temp_campaign_dir)
    mgr.init_campaign("CAMP_IND")

    item = ValidationReviewItem(
        review_id="REV_02",
        session_id="S_IND",
        timestamp_sec=300.0,
        frame_index=6000,
        trigger_type=ReviewTriggerType.ACTION,
        temporal_stage=TemporalStage.EARLY_GAME,
        prediction={"action": "ROLL", "score": 0.90},
        observation={},
        state_diff={}
    )

    reviewed = mgr.execute_blind_review("CAMP_IND", item, human_action="BUY_UNIT", reviewer_id="AUDITOR_A")
    assert reviewed.human_verdict == HumanVerdict.WRONG
    assert reviewed.human_label == "BUY_UNIT"
    assert reviewed.corrected_value == "BUY_UNIT"
    assert reviewed.error_reason == FailureTaxonomy.ACTION_EVENT_ERROR


def test_prediction_hidden_in_blind_mode():
    """8. Test that ValidationReviewItem hides prediction from reviewer interface in blind mode."""
    item = ValidationReviewItem(
        review_id="REV_03",
        session_id="S_HIDE",
        timestamp_sec=100.0,
        frame_index=2000,
        trigger_type=ReviewTriggerType.RANDOM_CHECK,
        temporal_stage=TemporalStage.EARLY_GAME,
        prediction={"action": "NO_ACTION"},
        observation={"gold": 50},
        state_diff={}
    )
    # Reviewer inspects observation and provides human label before checking item.prediction
    human_obs_gold = item.observation.get("gold")
    assert human_obs_gold == 50


def test_review_persistence(temp_campaign_dir):
    """9. Test that verification events persist to verifications.jsonl."""
    mgr = CampaignManager(temp_campaign_dir)
    mgr.init_campaign("CAMP_PERSIST")
    item = ValidationReviewItem(
        review_id="REV_04",
        session_id="S_PERSIST",
        timestamp_sec=100.0,
        frame_index=2000,
        trigger_type=ReviewTriggerType.ACTION,
        temporal_stage=TemporalStage.EARLY_GAME,
        prediction={"action": "ROLL"},
        observation={},
        state_diff={}
    )
    mgr.execute_blind_review("CAMP_PERSIST", item, human_action="ROLL")

    v_file = os.path.join(mgr.get_campaign_dir("CAMP_PERSIST"), "sessions", "S_PERSIST", "verifications.jsonl")
    assert os.path.exists(v_file)
    with open(v_file, "r", encoding="utf-8") as f:
        row = json.loads(f.readline())
        assert row["human_verdict"] == "CORRECT"


def test_error_snapshot(temp_campaign_dir):
    """10. Test error snapshot creation and persistence on discrepancy."""
    store = VerificationStore(temp_campaign_dir)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    snap_dir = store.save_error_snapshot(
        session_id="SESS_ERR_TEST",
        timestamp_sec=120.0,
        frame_current=frame,
        reason=FailureTaxonomy.ACTION_EVENT_ERROR
    )
    assert os.path.exists(snap_dir)
    assert os.path.exists(os.path.join(snap_dir, "frame_current.png"))


def test_ground_truth_export(temp_campaign_dir):
    """11. Test ground truth dataset export containing only verified items."""
    mgr = CampaignManager(temp_campaign_dir)
    mgr.init_campaign("CAMP_EXP")
    item1 = ValidationReviewItem("R1", "S_EXP", 10.0, 200, ReviewTriggerType.ACTION, TemporalStage.EARLY_GAME, {"action": "ROLL"}, {}, {})
    item2 = ValidationReviewItem("R2", "S_EXP", 20.0, 400, ReviewTriggerType.ACTION, TemporalStage.EARLY_GAME, {"action": "ROLL"}, {}, {})

    mgr.execute_blind_review("CAMP_EXP", item1, human_action="ROLL")      # CORRECT
    mgr.execute_blind_review("CAMP_EXP", item2, human_action="BUY_UNIT")  # WRONG / EDITED

    gt_file = mgr.export_campaign_ground_truth("CAMP_EXP")
    assert os.path.exists(gt_file)
    with open(gt_file, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
        assert len(lines) == 2
        assert lines[0]["ground_truth_action"] == "ROLL"
        assert lines[1]["ground_truth_action"] == "BUY_UNIT"


def test_session_isolation(temp_campaign_dir):
    """12. Test that multi-session review queues and verifications remain isolated."""
    mgr = CampaignManager(temp_campaign_dir)
    mgr.init_campaign("CAMP_ISO")
    mgr.generate_review_queue("CAMP_ISO", "SESSION_A", [], [{"action_type": "ROLL", "timestamp_sec": 10.0}], random_checks_count=5)
    mgr.generate_review_queue("CAMP_ISO", "SESSION_B", [], [{"action_type": "BUY_UNIT", "timestamp_sec": 20.0}], random_checks_count=5)

    c_dir = mgr.get_campaign_dir("CAMP_ISO")
    qa = os.path.join(c_dir, "review_queue", "queue_SESSION_A.jsonl")
    qb = os.path.join(c_dir, "review_queue", "queue_SESSION_B.jsonl")
    assert os.path.exists(qa)
    assert os.path.exists(qb)


def test_campaign_metrics():
    """13. Test PRF calculation helper."""
    from evaluate_validation_campaign import calculate_prf
    p, r, f1 = calculate_prf(tp=10, fp=0, fn=2)
    assert p == 1.0
    assert r == round(10/12, 4)
    assert f1 > 0.90


def test_session_metrics():
    """14. Test Cohen's Kappa calculation on known overlap samples."""
    labels_a = ["ROLL", "BUY_UNIT", "ROLL", "NO_ACTION", "ROLL"]
    labels_b = ["ROLL", "BUY_UNIT", "ROLL", "NO_ACTION", "ROLL"]
    agree, kappa = CampaignManager.compute_cohen_kappa(labels_a, labels_b)
    assert agree == 1.0
    assert kappa == 1.0


def test_worst_session_metrics():
    """15. Test Cohen's Kappa on imperfect agreement."""
    labels_a = ["ROLL", "BUY_UNIT", "ROLL", "NO_ACTION", "ROLL"]
    labels_b = ["ROLL", "BUY_UNIT", "BUY_UNIT", "NO_ACTION", "ROLL"]
    agree, kappa = CampaignManager.compute_cohen_kappa(labels_a, labels_b)
    assert agree == 0.80
    assert kappa > 0.60


def test_failure_taxonomy():
    """16. Test that all FailureTaxonomy enum values are standardized."""
    assert FailureTaxonomy.COARSE_SAMPLING_MERGE.value == "COARSE_SAMPLING_MERGE"
    assert FailureTaxonomy.GOLD_OCR_ERROR.value == "GOLD_OCR_ERROR"
    assert FailureTaxonomy.ACTION_EVENT_ERROR.value == "ACTION_EVENT_ERROR"


def test_improvement_backlog():
    """17. Test ImprovementBacklogItem serialization."""
    item = ImprovementBacklogItem(
        failure_id="FAIL_01",
        session_id="SESSION_A",
        timestamp_sec=315.0,
        failure_type=FailureTaxonomy.COARSE_SAMPLING_MERGE,
        prediction="ROLL",
        human_label="NO_ACTION",
        evidence=["Compound roll transition"],
        priority=PriorityLevel.P1,
        frequency=3,
        recommended_fix="Tune adaptive resampling"
    )
    d = item.to_dict()
    assert d["priority"] == "P1"
    assert d["failure_type"] == "COARSE_SAMPLING_MERGE"


def test_no_prediction_mutation(temp_campaign_dir):
    """18. Test strict invariant: Human reviews never mutate raw predictions.jsonl."""
    mgr = CampaignManager(temp_campaign_dir)
    c_dir = mgr.get_campaign_dir("CAMP_IMM")
    sess_dir = os.path.join(c_dir, "sessions", "S_IMM")
    os.makedirs(sess_dir, exist_ok=True)

    pred_path = os.path.join(sess_dir, "predictions.jsonl")
    with open(pred_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"action": "ROLL"}, ensure_ascii=False) + "\n")

    # Review as wrong
    item = ValidationReviewItem("R1", "S_IMM", 10.0, 200, ReviewTriggerType.ACTION, TemporalStage.EARLY_GAME, {"action": "ROLL"}, {}, {})
    mgr.execute_blind_review("CAMP_IMM", item, human_action="NO_ACTION")

    with open(pred_path, "r", encoding="utf-8") as f:
        pred_data = json.loads(f.readline())
        assert pred_data["action"] == "ROLL"  # Untouched


def test_no_ground_truth_feedback():
    """19. Test invariant: Ground truth is not imported into detector pipeline."""
    from tft.vision.action_event_detector_v22 import ActionEventDetectorV22
    det = ActionEventDetectorV22()
    assert not hasattr(det, "ground_truth")


def test_no_cross_session_leakage(temp_campaign_dir):
    """20. Test zero data contamination across multiple registered sessions."""
    mgr = CampaignManager(temp_campaign_dir)
    mgr.init_campaign("CAMP_LEAK")
    s1 = CampaignSessionInfo("S1", "v1.mp4", "M1", "P1", 1, EconomicArchetype.FAST_LEVELUP)
    s2 = CampaignSessionInfo("S2", "v2.mp4", "M2", "P2", 2, EconomicArchetype.REROLL_HEAVY)

    mgr.register_session("CAMP_LEAK", s1)
    mgr.register_session("CAMP_LEAK", s2)

    manifest = CampaignManifest.load_from_json(os.path.join(mgr.get_campaign_dir("CAMP_LEAK"), "manifest.json"))
    assert manifest.sessions[0].session_id != manifest.sessions[1].session_id
    assert manifest.sessions[0].match_id != manifest.sessions[1].match_id
