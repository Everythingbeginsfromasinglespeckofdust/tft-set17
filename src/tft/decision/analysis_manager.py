"""Unified Analysis & Execution Manager for TFT Decision Engine Live Validation."""
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.domain.actions import ActionType
from tft.decision.engine import DecisionEngine
from tft.decision.models import Recommendation, ActionScore
from tft.vision.frame_source import FrameSource, FramePacket
from tft.vision.analysis_manager import VisionAnalysisManager
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


class DecisionAnalysisManager:
    """비전 파이프라인의 GameState를 DecisionEngine에 연결하고 실시간 검증 오버레이를 구동하는 통합 매니저."""

    def __init__(
        self,
        frame_source: FrameSource,
        session_id: str = "SESSION_A",
        mode: str = "VALIDATION",
        validation_store: Optional[DecisionValidationStore] = None,
        decision_engine: Optional[DecisionEngine] = None,
        blind_mode: bool = False
    ):
        self.frame_source = frame_source
        self.session_id = session_id
        self.mode = mode
        self.store = validation_store or DecisionValidationStore()
        self.decision_engine = decision_engine or DecisionEngine()
        self.renderer = DecisionOverlayRenderer()

        # Core Vision Pipeline manager for visual extraction
        self.vision_manager = VisionAnalysisManager(
            frame_source=frame_source,
            session_id=session_id,
            mode=mode,
            analysis_fps=20.0
        )

        self.state = DecisionOverlayState(
            session_id=session_id,
            mode=mode,
            blind_mode=blind_mode,
            reveal_recommendation=not blind_mode
        )

        self._record_counter = 1
        self._last_decision_time = 0.0
        self._decision_interval = 0.5  # Re-evaluate decision every 0.5s or on step

    def process_next_frame(self, force_decision: bool = False) -> Optional[np.ndarray]:
        """다음 프레임을 읽어 Vision -> GameState -> DecisionEngine -> Overlay 렌더링 파이프라인 실행."""
        t_start = time.time()

        # 1. Vision Processing
        t_v0 = time.time()
        packet = self.frame_source.read()
        if packet is None:
            return None

        self.state.timestamp_sec = packet.timestamp_sec
        self.state.frame_index = packet.frame_index
        self.state.is_paused = getattr(self.frame_source, "is_paused", False)
        self.state.playback_speed = getattr(self.frame_source, "playback_speed", 1.0)

        # Run vision analysis
        v_state = self.vision_manager.state
        # Analyze shop, gold, action on frame
        self.vision_manager._run_vision_pipeline(packet.frame, packet.timestamp_sec, packet.frame_index)
        t_v1 = time.time()
        vision_lat_ms = (t_v1 - t_v0) * 1000

        # 2. Reconstruct GameState at T0
        t_g0 = time.time()
        obs = v_state.observed
        current_gold = obs.gold if (obs and obs.gold is not None) else 0
        current_hp = obs.hp if (obs and obs.hp is not None) else 100
        current_level = obs.level if (obs and obs.level is not None) else 1
        current_stage = obs.stage_round if (obs and obs.stage_round) else "2-1"

        # Shop units
        shop_units = []
        if obs and obs.shop_slots:
            for card in obs.shop_slots:
                if card.champion and card.champion != "EMPTY" and card.champion != "UNK":
                    shop_units.append(Unit(champion=card.champion, cost=card.cost or 1, star_level=1))

        # Board units extracted from vision observation
        board_units = []
        if obs and getattr(obs, "board_units", None):
            for bu in obs.board_units:
                if hasattr(bu, "champion") and bu.champion:
                    board_units.append(Unit(champion=bu.champion, cost=getattr(bu, "cost", 1), star_level=getattr(bu, "star_level", 1)))

        game_state = GameState(
            stage=int(current_stage.split("-")[0]) if "-" in current_stage else 2,
            round=int(current_stage.split("-")[1]) if "-" in current_stage else 1,
            stage_round=current_stage,
            player=PlayerState(gold=current_gold, level=current_level, xp=0, hp=current_hp),
            board_units=board_units,
            bench_units=[],
            shop_units=shop_units
        )
        self.state.observed_state = game_state

        # Actual Player Action detected by vision pipeline
        if v_state.detected and v_state.detected.action_type:
            act_str = v_state.detected.action_type
            self.state.actual_player_action = act_str if act_str != "NO_ACTION" else "SAVE_GOLD"
        else:
            self.state.actual_player_action = "SAVE_GOLD"

        t_g1 = time.time()
        game_state_lat_ms = (t_g1 - t_g0) * 1000

        # 3. Decision Engine Computation at T0
        t_d0 = time.time()
        should_decide = force_decision or (packet.timestamp_sec - self._last_decision_time >= self._decision_interval)
        if should_decide or self.state.recommendation is None:
            recommendation = self.decision_engine.decide(game_state)
            self._last_decision_time = packet.timestamp_sec
            self._update_decision_output(recommendation)

        t_d1 = time.time()
        decision_lat_ms = (t_d1 - t_d0) * 1000

        # 4. Rendering & Performance Update
        t_r0 = time.time()
        self.state.performance = DecisionPerformanceState(
            vision_latency_ms=vision_lat_ms,
            game_state_latency_ms=game_state_lat_ms,
            decision_latency_ms=decision_lat_ms,
            render_latency_ms=1.2,
            total_overlay_latency_ms=vision_lat_ms + game_state_lat_ms + decision_lat_ms + 1.2,
            capture_fps=30.0,
            analysis_fps=20.0,
            render_fps=60.0
        )

        rendered_frame = self.renderer.render(packet.frame, self.state)
        t_r1 = time.time()

        return rendered_frame

    def _update_decision_output(self, recommendation: Recommendation) -> None:
        """DecisionEngine의 Recommendation 결과를 오버레이 상태 모델로 파싱."""
        self.state.recommendation = recommendation
        self.state.recommended_action = recommendation.recommended_action.action_type.value
        self.state.action_score_gap = recommendation.decision_margin

        # Action Scores
        scores = {}
        for s in recommendation.all_scores:
            scores[s.action.action_type.value] = s.score
        self.state.action_scores = scores

        # Score Breakdown per action
        breakdowns = {}
        for s in recommendation.all_scores:
            breakdowns[s.action.action_type.value] = {
                k: {
                    "raw": mb.raw_value,
                    "norm": mb.normalized_value,
                    "weight": mb.weight,
                    "contribution": mb.contribution
                }
                for k, mb in s.breakdown.items()
            }
        self.state.score_breakdowns = breakdowns

        # Reasons
        self.state.reasons = [r.summary for r in recommendation.reasons]

        # Log prediction to store (immutable)
        rec_record = DecisionValidationRecord(
            record_id=f"DEC_{self.session_id}_{self._record_counter:04d}",
            session_id=self.session_id,
            timestamp_sec=self.state.timestamp_sec,
            frame_index=self.state.frame_index,
            observed_state=self.state.observed_state,
            actual_player_action=self.state.actual_player_action,
            recommended_action=self.state.recommended_action,
            action_score_gap=self.state.action_score_gap,
            action_scores=self.state.action_scores,
            score_breakdown=self.state.score_breakdowns,
            reasons=self.state.reasons,
            blind_mode=self.state.blind_mode,
            pipeline_latency_ms={
                "vision": self.state.performance.vision_latency_ms,
                "game_state": self.state.performance.game_state_latency_ms,
                "decision": self.state.performance.decision_latency_ms,
                "total": self.state.performance.total_overlay_latency_ms
            }
        )
        self.store.log_prediction(self.session_id, rec_record)
        self._record_counter += 1

    def record_human_judgment(
        self,
        judgment: HumanEngineJudgment,
        notes: Optional[str] = None,
        failure_reason: Optional[DecisionFailureReason] = None,
        reviewer_id: str = "HUMAN_AUDITOR_1"
    ) -> DecisionValidationRecord:
        """현재 추천에 대한 인간의 정성적 평가 기록."""
        self.state.human_judgment = judgment
        self.state.human_notes = notes

        record = DecisionValidationRecord(
            record_id=f"DEC_REV_{self.session_id}_{self._record_counter:04d}",
            session_id=self.session_id,
            timestamp_sec=self.state.timestamp_sec,
            frame_index=self.state.frame_index,
            observed_state=self.state.observed_state,
            actual_player_action=self.state.actual_player_action,
            recommended_action=self.state.recommended_action,
            action_score_gap=self.state.action_score_gap,
            action_scores=self.state.action_scores,
            score_breakdown=self.state.score_breakdowns,
            reasons=self.state.reasons,
            human_judgment=judgment,
            human_preference=self.state.human_preference,
            human_notes=notes,
            failure_reason=failure_reason,
            reviewer_id=reviewer_id,
            blind_mode=self.state.blind_mode,
            reviewed_at=time.strftime("%Y-%m-%dT%H:%M:%S")
        )
        self.store.log_decision_review(self.session_id, record)

        if judgment == HumanEngineJudgment.WRONG:
            fail_case = DecisionFailureCase(
                failure_id=f"FAIL_{self.session_id}_{int(self.state.timestamp_sec)}",
                session_id=self.session_id,
                timestamp_sec=self.state.timestamp_sec,
                observed_state_summary={
                    "stage": self.state.observed_state.stage_round if self.state.observed_state else "3-2",
                    "gold": self.state.observed_state.player.gold if self.state.observed_state else 0,
                    "hp": self.state.observed_state.player.hp if self.state.observed_state else 0
                },
                engine_recommendation=self.state.recommended_action,
                actual_player_action=self.state.actual_player_action,
                human_preference=self.state.human_preference.value if self.state.human_preference else None,
                human_judgment=judgment.value,
                failure_type=failure_reason or DecisionFailureReason.BAD_ECONOMIC_EVALUATION,
                evidence=self.state.reasons
            )
            self.store.save_failure_case(fail_case)

        return record

    def record_human_preference_blind(
        self,
        preference: HumanPreference,
        reviewer_id: str = "HUMAN_AUDITOR_1"
    ) -> DecisionValidationRecord:
        """Blind Mode에서 인간이 독립적으로 선호한 행동을 먼저 기록하고 엔진 추천을 공개."""
        self.state.human_preference = preference
        self.state.reveal_recommendation = True

        # Determine reasonable vs questionable based on preference comparison
        judg = HumanEngineJudgment.REASONABLE if preference.value == self.state.recommended_action else HumanEngineJudgment.QUESTIONABLE

        return self.record_human_judgment(
            judgment=judg,
            notes=f"Blind choice: Human={preference.value} vs Engine={self.state.recommended_action}",
            reviewer_id=reviewer_id
        )
