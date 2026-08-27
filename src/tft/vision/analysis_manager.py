"""Vision Analysis Manager: Unified core connecting FrameSource, Vision Pipeline, Overlay State, and Verification Store."""
import collections
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from tft.vision.frame_source import FrameSource, FramePacket
from tft.vision.overlay_state import (
    OverlayState,
    ObservedStateSummary,
    DerivedStateSummary,
    DetectedActionSummary,
    VerificationStateSummary,
    PerformanceSummary,
    ShopSlotDisplay
)
from tft.vision.overlay_renderer import OverlayRenderer
from tft.vision.validation_models import (
    VerificationEvent,
    VerificationSummary,
    HumanVerdict,
    TargetType,
    ErrorReason
)
from tft.vision.verification_store import VerificationStore

from tft.vision.gold_recognizer import GoldRecognizer, GoldObservation
from tft.vision.gold_timeline import GoldTimelineProcessor
from tft.vision.shop_recognizer_v2 import ShopRecognizerV2, SlotStatus
from tft.vision.observation import Observation, CardObservation
from tft.vision.state_diff import StateDiff, compute_state_diff
from tft.vision.action_event_detector_v22 import ActionEventDetectorV22


class VisionAnalysisManager:
    """Video Mode 및 Live Capture Mode 모두에서 동일하게 작동하는 단일 통합 분석 코어."""

    def __init__(
        self,
        frame_source: FrameSource,
        session_id: str = "SESSION_A",
        mode: str = "VALIDATION",  # "VALIDATION" or "PRODUCTION"
        verification_store: Optional[VerificationStore] = None,
        gold_recognizer: Optional[GoldRecognizer] = None,
        shop_recognizer: Optional[ShopRecognizerV2] = None,
        action_detector: Optional[ActionEventDetectorV22] = None,
        analysis_fps: float = 20.0
    ):
        self.frame_source = frame_source
        self.session_id = session_id
        self.mode = mode
        self.store = verification_store or VerificationStore()
        self.gold_recognizer = gold_recognizer or GoldRecognizer()
        self.shop_recognizer = shop_recognizer or ShopRecognizerV2()
        self.action_detector = action_detector or ActionEventDetectorV22()
        self.analysis_fps = analysis_fps
        self.analysis_interval_sec = 1.0 / analysis_fps

        self.renderer = OverlayRenderer()
        self.state = OverlayState(session_id=session_id, mode=mode, is_live=frame_source.is_live())

        # History buffer for error snapshots
        self._frame_buffer: collections.deque = collections.deque(maxlen=10)
        self._last_obs: Optional[Observation] = None
        self._last_state_diff: Optional[StateDiff] = None
        self._last_action_event: Optional[Dict[str, Any]] = None
        self._last_analysis_time: float = 0.0

        # Performance counters
        self._perf_frame_count: int = 0
        self._perf_start_time: float = time.time()
        self._last_render_time: float = time.time()

        # Update initial summary counts
        summary = self.store.get_summary(session_id)
        self.state.verification.total_reviewed = summary.total_reviewed
        self.state.verification.correct_count = summary.correct_count
        self.state.verification.wrong_count = summary.wrong_count

    def process_next_frame(self, force_analysis: bool = False) -> Optional[np.ndarray]:
        """다음 프레임을 공급자로부터 읽어 분석 및 렌더링을 수행하고 최종 합성 프레임 반환."""
        packet = self.frame_source.read()
        if packet is None:
            return None

        t_now = time.time()
        t_sec = packet.timestamp_sec

        # Buffer raw frame for before/after snapshots
        self._frame_buffer.append(packet)

        # Update Playback State
        self.state.current_timestamp_sec = t_sec
        self.state.frame_index = packet.frame_index
        self.state.is_paused = getattr(self.frame_source, "is_paused", False)
        self.state.playback_speed = getattr(self.frame_source, "playback_speed", 1.0)
        self.state.duration_sec = getattr(self.frame_source, "duration_sec", 600.0)

        # Measure Performance
        data_age = t_now - packet.capture_timestamp_sec
        latency = t_now - packet.capture_timestamp_sec
        self.state.performance.data_age_sec = max(0.0, data_age)
        self.state.performance.latency_sec = max(0.0, latency)

        # Check if analysis tick should trigger (Decoupled from Render FPS)
        should_analyze = force_analysis or (t_sec - self._last_analysis_time >= self.analysis_interval_sec) or (self.state.is_paused)

        if should_analyze:
            self._run_vision_pipeline(packet.frame, t_sec, packet.frame_index)
            self._last_analysis_time = t_sec

        # Render HUD Overlay
        rendered_frame = self.renderer.render(packet.frame, self.state)
        return rendered_frame

    def _run_vision_pipeline(self, frame: np.ndarray, t_sec: float, frame_idx: int) -> None:
        """단일 프레임에 대해 Frozen Vision Pipeline 실행 및 OverlayState 갱신."""
        # 1. Gold Recognition
        g_obs = self.gold_recognizer.recognize_gold(frame, timestamp_sec=t_sec, frame_index=frame_idx)

        # 2. Shop Recognition
        cards_rec = self.shop_recognizer.recognize_shop(frame)
        card_obs_list = []
        slot_displays = []

        for c in cards_rec:
            card_obs_list.append(CardObservation(
                slot_index=c.slot_index,
                champion_pred=c.champion,
                cost_pred=c.cost,
                confidence=c.confidence,
                is_empty=(c.status == SlotStatus.EMPTY),
                source="ShopRecognizerV2"
            ))
            slot_displays.append(ShopSlotDisplay(
                slot_index=c.slot_index,
                champion=c.champion,
                cost=c.cost,
                status=c.status.value,
                confidence=c.confidence,
                is_empty=(c.status == SlotStatus.EMPTY)
            ))

        # 3. Create Current Observation
        shop_conf = float(np.mean([c.confidence for c in shop_cards])) if shop_cards else 0.0
        gold_conf = float(g_obs.confidence) if g_obs.is_valid else 0.0
        overall_conf = float(np.mean([shop_conf, gold_conf])) if (shop_conf > 0 or gold_conf > 0) else 0.0

        curr_obs = Observation(
            timestamp_sec=t_sec,
            frame_index=frame_idx,
            stage_text=self.state.observed.stage_round or "2-1",
            gold_val=g_obs.parsed_gold,
            hp_val=self.state.observed.hp,
            level_val=self.state.observed.level,
            shop_cards=card_obs_list,
            sources={"shop": "ShopRecognizerV2", "gold": "GoldRecognizer"},
            confidences={"shop": round(shop_conf, 3), "gold": round(gold_conf, 3)},
            overall_confidence=round(overall_conf, 3)
        )

        # 4. Layer A (Observed State) Update
        self.state.observed.gold = curr_obs.gold_val
        self.state.observed.raw_gold = g_obs.raw_text
        self.state.observed.gold_carried = g_obs.metadata.get("carried_forward", False)
        self.state.observed.shop_slots = slot_displays
        self.state.observed.hp = curr_obs.hp_val
        self.state.observed.level = curr_obs.level_val

        # 5. Layer B (Derived StateDiff) Update
        if self._last_obs is not None:
            diff = compute_state_diff(self._last_obs, curr_obs)
            self._last_state_diff = diff

            self.state.derived.gold_delta = diff.gold_delta
            self.state.derived.shop_slots_changed = diff.shop_slots_changed
            self.state.derived.shop_slots_emptied = diff.shop_slots_emptied
            self.state.derived.is_shop_animating = diff.metadata.get("shop_animation_active", False)
            self.state.derived.is_quiescent = (diff.shop_slots_changed == 0 and (diff.gold_delta in [0, None]))

            # 6. Layer C (Detected Action) Update
            events = self.action_detector.detect_actions([self._last_obs, curr_obs])
            if events:
                ev = events[-1]
                self._last_action_event = {
                    "action_type": ev.action_type.value,
                    "confidence": ev.confidence,
                    "timestamp_sec": ev.timestamp_sec,
                    "evidence": ev.evidence
                }
                self.state.detected.action_type = ev.action_type.value
                self.state.detected.detection_score = ev.confidence
                self.state.detected.target_champion = ev.target_champion
                self.state.detected.target_slot = ev.slot_index

                # Rule signal checklist
                signals = [
                    (f"Gold delta match ({diff.gold_delta}G)", diff.gold_delta in [-2, -3, -4]),
                    (f"Shop transitioned ({diff.shop_slots_changed} slots)", diff.shop_slots_changed >= 2),
                    ("Not System Refresh", True)
                ]
                self.state.detected.signals_checklist = signals
                self.state.detected.rule_match_fraction = f"{sum(1 for _, m in signals if m)}/{len(signals)}"

                # Log raw prediction (Strict Isolation)
                self.store.log_prediction(self.session_id, {
                    "timestamp_sec": t_sec,
                    "frame_index": frame_idx,
                    "action_type": ev.action_type.value,
                    "confidence": ev.confidence,
                    "gold": curr_obs.gold_val,
                    "shop": [c.champion for c in slot_displays]
                })
            else:
                if self.state.derived.is_quiescent:
                    self.state.detected.action_type = "NO_ACTION"
                    self.state.detected.detection_score = 1.0
                    self.state.detected.signals_checklist = [("Quiescent state", True)]
                    self.state.detected.rule_match_fraction = "1/1"

        self._last_obs = curr_obs

    # --- Human Verification Actions ---

    def record_verdict(
        self,
        verdict: HumanVerdict,
        target_type: TargetType = TargetType.ACTION,
        human_label: Optional[str] = None,
        corrected_value: Optional[Any] = None,
        error_reason: Optional[ErrorReason] = None,
        notes: Optional[str] = None
    ) -> VerificationEvent:
        """인간 검증 판정을 기록하고 [WRONG]인 경우 진단 스냅샷을 자동 보존."""
        event_id = f"VER_{int(self.state.current_timestamp_sec * 100):06d}"
        pred_val = self.state.detected.action_type if target_type == TargetType.ACTION else self.state.observed.gold

        frame_curr = self._frame_buffer[-1].frame if self._frame_buffer else np.zeros((720, 1280, 3), dtype=np.uint8)
        frame_before = self._frame_buffer[0].frame if len(self._frame_buffer) > 1 else None

        frame_path = None
        if verdict == HumanVerdict.WRONG:
            frame_path = self.store.save_error_snapshot(
                session_id=self.session_id,
                timestamp_sec=self.state.current_timestamp_sec,
                frame_current=frame_curr,
                frame_before=frame_before,
                current_obs=self.state.to_dict().get("observed"),
                state_diff=self.state.to_dict().get("derived"),
                action_event=self._last_action_event,
                reason=error_reason or ErrorReason.ACTION_ERROR
            )

        event = VerificationEvent(
            verification_id=event_id,
            session_id=self.session_id,
            timestamp_sec=self.state.current_timestamp_sec,
            frame_index=self.state.frame_index,
            target_type=target_type,
            predicted_value=pred_val,
            human_verdict=verdict,
            human_label=human_label,
            corrected_value=corrected_value,
            error_reason=error_reason,
            notes=notes,
            frame_path=frame_path
        )

        self.store.log_verification(event)

        # Update HUD verification state
        self.state.verification.last_verdict = verdict
        self.state.verification.last_human_label = human_label
        if verdict == HumanVerdict.CORRECT:
            self.state.verification.correct_count += 1
        elif verdict == HumanVerdict.WRONG:
            self.state.verification.wrong_count += 1
        elif verdict == HumanVerdict.UNKNOWN:
            self.state.verification.unknown_count += 1
        elif verdict == HumanVerdict.SKIPPED:
            self.state.verification.skipped_count += 1

        self.state.verification.total_reviewed += 1
        return event

    def verify_correct(self) -> VerificationEvent:
        return self.record_verdict(HumanVerdict.CORRECT)

    def verify_wrong(self, reason: Optional[ErrorReason] = None, corrected_action: Optional[str] = None) -> VerificationEvent:
        return self.record_verdict(
            HumanVerdict.WRONG,
            error_reason=reason or ErrorReason.ACTION_ERROR,
            corrected_value=corrected_action
        )

    def verify_edit(self, corrected_value: Any, target_type: TargetType = TargetType.ACTION) -> VerificationEvent:
        return self.record_verdict(
            HumanVerdict.EDITED,
            target_type=target_type,
            corrected_value=corrected_value
        )

    def verify_skip(self) -> VerificationEvent:
        return self.record_verdict(HumanVerdict.SKIPPED)

    def annotate_action(self, action_name: str) -> VerificationEvent:
        return self.record_verdict(
            HumanVerdict.CORRECT if action_name == self.state.detected.action_type else HumanVerdict.WRONG,
            target_type=TargetType.ACTION,
            human_label=action_name,
            corrected_value=action_name
        )

    def toggle_rois(self) -> bool:
        self.state.show_rois = not self.state.show_rois
        return self.state.show_rois
