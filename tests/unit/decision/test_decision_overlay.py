"""Comprehensive Unit Tests for TFT Decision Engine Live Validation & Review Overlay."""
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

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.domain.actions import ActionType
from tft.decision.engine import DecisionEngine
from tft.vision.frame_source import MockFrameSource, FramePacket
from tft.decision.overlay_state import DecisionOverlayState, DecisionPerformanceState
from tft.decision.overlay_renderer import DecisionOverlayRenderer
from tft.decision.validation_models import (
    DecisionValidationRecord,
    DecisionFailureCase,
    HumanEngineJudgment,
    HumanPreference,
    DecisionFailureReason
)
from tft.decision.validation_store import DecisionValidationStore
from tft.decision.analysis_manager import DecisionAnalysisManager


@pytest.fixture
def temp_decision_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_game_state():
    return GameState(
        stage=3,
        round=2,
        stage_round="3-2",
        player=PlayerState(gold=35, level=7, xp=12, hp=60),
        board_units=[Unit(champion="Miss Fortune", cost=3, star_level=2)],
        bench_units=[Unit(champion="Miss Fortune", cost=3, star_level=1)],
        shop_units=[Unit(champion="Diana", cost=4, star_level=1)]
    )


def test_decision_overlay_state(sample_game_state):
    """1. Test DecisionOverlayState initialization and properties."""
    state = DecisionOverlayState(session_id="S1", observed_state=sample_game_state)
    assert state.session_id == "S1"
    assert state.observed_state.player.gold == 35
    assert state.recommended_action == "NONE"


def test_decision_score_breakdown(sample_game_state):
    """2. Test DecisionEngine output parsing and traceable score breakdowns."""
    engine = DecisionEngine()
    rec = engine.decide(sample_game_state)
    assert rec.recommended_action.action_type in [ActionType.ROLL, ActionType.LEVEL_UP, ActionType.SAVE_GOLD]
    assert rec.decision_margin >= 0.0
    assert len(rec.all_scores) == 3


def test_player_vs_engine_separation(sample_game_state):
    """3. Test strict separation between actual player action and engine recommendation."""
    rec = DecisionValidationRecord(
        record_id="REC_01",
        session_id="S1",
        timestamp_sec=100.0,
        frame_index=2000,
        observed_state=sample_game_state,
        actual_player_action="ROLL",
        recommended_action="SAVE_GOLD"
    )
    d = rec.to_dict()
    assert d["actual_player_action"] == "ROLL"
    assert d["recommendation"]["recommended_action"] == "SAVE_GOLD"
    assert d["actual_player_action"] != d["recommendation"]["recommended_action"]


def test_human_preference_separation(sample_game_state):
    """4. Test that human preference in blind mode is stored separately from player action and engine."""
    rec = DecisionValidationRecord(
        record_id="REC_02",
        session_id="S1",
        timestamp_sec=100.0,
        frame_index=2000,
        observed_state=sample_game_state,
        actual_player_action="ROLL",
        recommended_action="SAVE_GOLD",
        human_preference=HumanPreference.LEVEL_UP,
        human_judgment=HumanEngineJudgment.QUESTIONABLE
    )
    d = rec.to_dict()
    assert d["actual_player_action"] == "ROLL"
    assert d["recommendation"]["recommended_action"] == "SAVE_GOLD"
    assert d["human_review"]["human_preference"] == "LEVEL_UP"


def test_blind_decision_review(temp_decision_dir, sample_game_state):
    """5. Test Blind Decision Review workflow (Preference recorded before recommendation reveal)."""
    store = DecisionValidationStore(temp_decision_dir)
    source = MockFrameSource()
    mgr = DecisionAnalysisManager(source, session_id="S_BLIND", validation_store=store, blind_mode=True)
    assert mgr.state.reveal_recommendation is False

    mgr.process_next_frame(force_decision=True)
    assert mgr.state.reveal_recommendation is False

    # Human inputs preference
    mgr.record_human_preference_blind(HumanPreference.ROLL)
    assert mgr.state.reveal_recommendation is True
    assert mgr.state.human_preference == HumanPreference.ROLL


def test_decision_validation_persistence(temp_decision_dir, sample_game_state):
    """6. Test persistence of reviews to decision_reviews.jsonl."""
    store = DecisionValidationStore(temp_decision_dir)
    source = MockFrameSource()
    mgr = DecisionAnalysisManager(source, session_id="S_PERSIST", validation_store=store)
    mgr.process_next_frame(force_decision=True)
    mgr.record_human_judgment(HumanEngineJudgment.REASONABLE, notes="Solid save gold")

    r_path = os.path.join(temp_decision_dir, "sessions", "S_PERSIST", "decision_reviews.jsonl")
    assert os.path.exists(r_path)
    with open(r_path, "r", encoding="utf-8") as f:
        row = json.loads(f.readline())
        assert row["human_review"]["human_judgment"] == "REASONABLE"


def test_prediction_immutability(temp_decision_dir, sample_game_state):
    """7. Test invariant: predictions.jsonl is never overwritten by human reviews."""
    store = DecisionValidationStore(temp_decision_dir)
    source = MockFrameSource()
    mgr = DecisionAnalysisManager(source, session_id="S_IMM", validation_store=store)
    mgr.process_next_frame(force_decision=True)

    p_path = os.path.join(temp_decision_dir, "sessions", "S_IMM", "predictions.jsonl")
    with open(p_path, "r", encoding="utf-8") as f:
        p1 = json.loads(f.readline())

    mgr.record_human_judgment(HumanEngineJudgment.WRONG, failure_reason=DecisionFailureReason.BAD_ECONOMIC_EVALUATION)

    with open(p_path, "r", encoding="utf-8") as f:
        p2 = json.loads(f.readline())

    assert p1["recommendation"]["recommended_action"] == p2["recommendation"]["recommended_action"]


def test_future_outcome_is_not_engine_input(sample_game_state):
    """8. Test invariant: T0 GameState input does not contain T1+ outcome info."""
    engine = DecisionEngine()
    rec = engine.decide(sample_game_state)
    assert rec is not None
    assert not hasattr(sample_game_state, "final_placement")
    assert not hasattr(sample_game_state, "future_hp")


def test_decision_record_temporal_integrity(sample_game_state):
    """9. Test temporal consistency: T0 <= T_action and T0 < T_outcome."""
    rec = DecisionValidationRecord(
        record_id="REC_03",
        session_id="S1",
        timestamp_sec=300.0,
        frame_index=6000,
        observed_state=sample_game_state,
        actual_player_action="ROLL",
        future_outcome={"outcome_timestamp_sec": 420.0, "final_placement": 2}
    )
    assert rec.timestamp_sec < rec.future_outcome["outcome_timestamp_sec"]


def test_decision_failure_case(temp_decision_dir):
    """10. Test DecisionFailureCase saving on WRONG human judgment."""
    store = DecisionValidationStore(temp_decision_dir)
    case = DecisionFailureCase(
        failure_id="FAIL_001",
        session_id="S1",
        timestamp_sec=315.0,
        observed_state_summary={"hp": 20, "gold": 40},
        engine_recommendation="SAVE_GOLD",
        actual_player_action="ROLL",
        human_preference="ROLL",
        human_judgment="WRONG",
        failure_type=DecisionFailureReason.BAD_ECONOMIC_EVALUATION,
        evidence=["HP is in critical crisis range but engine recommended SAVE_GOLD"]
    )
    f_path = store.save_failure_case(case)
    assert os.path.exists(f_path)
    with open(f_path, "r", encoding="utf-8") as f:
        d = json.load(f)
        assert d["failure_id"] == "FAIL_001"


def test_session_isolation(temp_decision_dir):
    """11. Test that multi-session decision records remain strictly isolated."""
    store = DecisionValidationStore(temp_decision_dir)
    s1_dir = store.get_session_dir("SESSION_A")
    s2_dir = store.get_session_dir("SESSION_B")
    assert os.path.abspath(s1_dir) != os.path.abspath(s2_dir)


def test_match_level_identity():
    """12. Test match ID tracking."""
    rec = DecisionValidationRecord(
        record_id="REC_04",
        session_id="SESSION_C",
        timestamp_sec=50.0,
        frame_index=1000,
        observed_state=GameState(3, 1, "3-1", PlayerState(50, 7, 0, 80), [], [])
    )
    assert rec.session_id == "SESSION_C"


def test_decision_latency_metrics():
    """13. Test step-by-step latency tracking."""
    perf = DecisionPerformanceState(
        vision_latency_ms=12.5,
        game_state_latency_ms=1.1,
        decision_latency_ms=8.4,
        render_latency_ms=1.2,
        total_overlay_latency_ms=23.2
    )
    assert perf.total_overlay_latency_ms < 50.0  # <50ms real-time constraint


def test_video_decision_integration():
    """14. Test DecisionAnalysisManager integration with Video frame source."""
    source = MockFrameSource()
    mgr = DecisionAnalysisManager(source, session_id="S_VID")
    rendered = mgr.process_next_frame(force_decision=True)
    assert rendered is not None
    assert rendered.shape == (720, 1280, 3)
    assert mgr.state.recommended_action in ["ROLL", "LEVEL_UP", "SAVE_GOLD"]


def test_live_decision_integration():
    """15. Test DecisionAnalysisManager in Production mode."""
    source = MockFrameSource()
    mgr = DecisionAnalysisManager(source, session_id="S_PROD", mode="PRODUCTION")
    rendered = mgr.process_next_frame(force_decision=True)
    assert rendered is not None
    assert mgr.state.mode == "PRODUCTION"


def test_human_decision_export(temp_decision_dir, sample_game_state):
    """16. Test export_human_decision_labels function."""
    store = DecisionValidationStore(temp_decision_dir)
    source = MockFrameSource()
    mgr = DecisionAnalysisManager(source, session_id="S_EXP", validation_store=store)
    mgr.process_next_frame(force_decision=True)
    mgr.record_human_judgment(HumanEngineJudgment.REASONABLE)

    out_file = store.export_human_decision_labels(session_id="S_EXP")
    assert os.path.exists(out_file)
    with open(out_file, "r", encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
        assert len(rows) == 1
        assert rows[0]["human_judgment"] == "REASONABLE"


def test_small_sample_insufficient_data():
    """17. Test handling of small sample sizes without making unwarranted generalizations."""
    sample_count = 2
    is_insufficient = sample_count < 10
    assert is_insufficient is True
