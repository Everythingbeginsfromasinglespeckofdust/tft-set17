"""TFT Action Event Detector v2.1 -- System Refresh Separation & Adaptive Resampling."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from tft.vision.events import ActionEvent, VisionActionType, ActionSource, QualityFlag
from tft.vision.observation import Observation
from tft.vision.state_diff import StateDiff, SlotTransitionType, compute_state_diff
from tft.vision.state_stability import StateStabilityAnalyzer, StabilityStatus
from tft.vision.system_event_detector import SystemEventDetector, SystemEventType
from tft.vision.adaptive_resampler import AdaptiveResampler
from tft.vision.action_event_detector import ActionEvidence, ActionCandidate, EvidenceCode


class ActionEventDetectorV21:
    """System Event Separation & Adaptive Resampling을 탑재한 ActionEventDetector v2.1."""

    def __init__(
        self,
        min_roll_score: float = 0.65,
        min_buy_score: float = 0.70,
        min_levelup_score: float = 0.70,
        min_sell_score: float = 0.60,
        enable_adaptive_resampling: bool = True,
        adaptive_target_fps: float = 20.0
    ):
        self.min_roll_score = min_roll_score
        self.min_buy_score = min_buy_score
        self.min_levelup_score = min_levelup_score
        self.min_sell_score = min_sell_score
        self.enable_adaptive_resampling = enable_adaptive_resampling
        self.adaptive_target_fps = adaptive_target_fps

        self.stability_analyzer = StateStabilityAnalyzer()
        self.system_detector = SystemEventDetector()
        self.resampler = AdaptiveResampler() if enable_adaptive_resampling else None

    def detect_actions_from_diff(
        self,
        diff: StateDiff,
        obs_before: Observation,
        obs_after: Observation
    ) -> List[ActionEvent]:
        """StateDiff와 두 Observation을 분석하여 시스템 이벤트 및 플레이어 행동을 엄밀 분리 생성."""
        emitted_events: List[ActionEvent] = []

        # 1. System Event Detection (Round start, System free refresh)
        system_events = self.system_detector.detect_system_events(diff, obs_before, obs_after)
        is_system_shop_refresh = any(
            e.metadata.get("system_event_type") == SystemEventType.SYSTEM_SHOP_REFRESH.value
            for e in system_events
        )

        for se in system_events:
            emitted_events.append(se)

        # 2. State Stability Assessment
        stability = self.stability_analyzer.assess_observation(obs_after, prev_obs=obs_before)
        if stability.is_shop_animation:
            # Mark as transient animation frame, suppress false BUY detections
            anim_ev = ActionEvent(
                action_type=VisionActionType.UNKNOWN,
                source=ActionSource.OBSERVED,
                timestamp_sec=diff.timestamp_after,
                confidence=0.80,
                evidence=["Transient shop animation in-flight (wipe/sliding cards)"],
                evidence_data={"stability_assessment": stability.to_dict()},
                quality_flag=QualityFlag.VALID,
                metadata={"system_event_type": SystemEventType.SHOP_ANIMATION.value}
            )
            emitted_events.append(anim_ev)

        # 3. Player Action Candidates (Evaluated only if NOT a system shop refresh)
        candidates: List[ActionCandidate] = []

        # 3a. LEVEL_UP
        if diff.level_delta is not None and diff.level_delta > 0:
            candidates.append(ActionCandidate(
                action_type=VisionActionType.LEVEL_UP,
                score=0.95,
                evidence_list=[
                    ActionEvidence(
                        code=EvidenceCode.LEVEL_INCREASED,
                        value=diff.level_delta,
                        strength=1.0,
                        description=f"Level increased from {diff.level_before} to {diff.level_after} (+{diff.level_delta})"
                    )
                ]
            ))

        # 3b. BUY_XP
        elif diff.xp_delta is not None and diff.xp_delta > 0 and (diff.level_delta == 0 or diff.level_delta is None):
            candidates.append(ActionCandidate(
                action_type=VisionActionType.BUY_XP,
                score=0.85,
                evidence_list=[
                    ActionEvidence(
                        code=EvidenceCode.XP_INCREASED_LEVEL_SAME,
                        value=diff.xp_delta,
                        strength=0.90,
                        description=f"XP increased by +{diff.xp_delta} while level remained {diff.level_before}"
                    )
                ]
            ))

        # 3c. BUY_UNIT (Only if not a transient animation wipe)
        if not stability.is_shop_animation and not is_system_shop_refresh:
            emptied_slots = [st for st in diff.shop_changes if st.transition_type == SlotTransitionType.EMPTIED]
            if len(emptied_slots) == 1 or (len(emptied_slots) > 1 and diff.units_added_bench):
                for st in emptied_slots:
                    champ_name = st.before_champion
                    cost = st.before_cost or 1
                    ev_list = [
                        ActionEvidence(
                            code=EvidenceCode.SLOT_EMPTIED,
                            value=st.slot_index + 1,
                            strength=0.85,
                            description=f"Slot {st.slot_index + 1} ({champ_name}, {cost}C) transitioned from RECOGNIZED to EMPTY"
                        )
                    ]
                    if champ_name and (champ_name in diff.units_added_bench or champ_name in diff.units_added_board):
                        ev_list.append(ActionEvidence(
                            code=EvidenceCode.CHAMPION_ADDED_TO_BENCH,
                            value=champ_name,
                            strength=0.95,
                            description=f"Champion '{champ_name}' was added to bench/board"
                        ))
                    if diff.gold_delta is not None and diff.gold_delta == -cost:
                        ev_list.append(ActionEvidence(
                            code=EvidenceCode.GOLD_DECREASE_MATCHING_COST,
                            value=diff.gold_delta,
                            strength=0.95,
                            description=f"Gold decreased exactly by cost of {champ_name} ({diff.gold_delta}G == -{cost}G)"
                        ))
                    score = float(np.mean([e.strength for e in ev_list]))
                    candidates.append(ActionCandidate(
                        action_type=VisionActionType.BUY_UNIT,
                        score=score,
                        evidence_list=ev_list,
                        target_champion=champ_name,
                        slot_index=st.slot_index
                    ))

            # 3d. Compound BUY + ROLL (Unit added to bench that was in previous shop, even if shop refreshed)
            if not emptied_slots and (diff.units_added_bench or diff.units_added_board):
                all_added = diff.units_added_bench + diff.units_added_board
                for u_name in all_added:
                    prev_slot = next((st for st in diff.shop_changes if st.before_champion == u_name), None)
                    if prev_slot:
                        ev_list = [
                            ActionEvidence(
                                code=EvidenceCode.COMPOUND_BUY_BEFORE_ROLL,
                                value=u_name,
                                strength=0.90,
                                description=f"Champion '{u_name}' purchased from Slot {prev_slot.slot_index + 1} before shop refresh"
                            ),
                            ActionEvidence(
                                code=EvidenceCode.CHAMPION_ADDED_TO_BENCH,
                                value=u_name,
                                strength=0.95,
                                description=f"Champion '{u_name}' added to bench in compound window"
                            )
                        ]
                        score = float(np.mean([e.strength for e in ev_list]))
                        candidates.append(ActionCandidate(
                            action_type=VisionActionType.BUY_UNIT,
                            score=score,
                            evidence_list=ev_list,
                            target_champion=u_name,
                            slot_index=prev_slot.slot_index
                        ))

        # 3e. PLAYER_ROLL (Evaluated ONLY if NOT a system shop refresh)
        if not is_system_shop_refresh:
            refreshed_count = diff.shop_slots_refreshed + diff.shop_slots_filled
            is_roll_pattern = (refreshed_count >= 3) or (refreshed_count >= 2 and diff.gold_delta is not None and diff.gold_delta <= -2)
            if is_roll_pattern:
                ev_list = [
                    ActionEvidence(
                        code=EvidenceCode.MULTI_SLOT_REFRESH_3PLUS,
                        value=refreshed_count,
                        strength=min(1.0, 0.70 + 0.10 * refreshed_count),
                        description=f"Shop refreshed across {refreshed_count}/5 slots simultaneously"
                    )
                ]
                if diff.gold_delta is not None and diff.gold_delta <= -2:
                    ev_list.append(ActionEvidence(
                        code=EvidenceCode.GOLD_DECREASE_2,
                        value=diff.gold_delta,
                        strength=0.95 if diff.gold_delta == -2 else 0.85,
                        description=f"Gold decreased by {abs(diff.gold_delta)}G consistent with reroll"
                    ))
                if not diff.units_added_bench and not diff.units_added_board:
                    ev_list.append(ActionEvidence(
                        code=EvidenceCode.BOARD_BENCH_UNCHANGED,
                        value=True,
                        strength=0.85,
                        description="Board and bench remained unchanged during shop refresh"
                    ))
                score = float(np.mean([e.strength for e in ev_list]))
                candidates.append(ActionCandidate(
                    action_type=VisionActionType.ROLL,
                    score=score,
                    evidence_list=ev_list
                ))

        # 4. Filter & Emit Valid Player Actions
        valid_candidates = []
        for c in candidates:
            if c.action_type == VisionActionType.ROLL and c.score >= self.min_roll_score:
                valid_candidates.append(c)
            elif c.action_type == VisionActionType.BUY_UNIT and c.score >= self.min_buy_score:
                valid_candidates.append(c)
            elif c.action_type == VisionActionType.LEVEL_UP and c.score >= self.min_levelup_score:
                valid_candidates.append(c)
            elif c.action_type == VisionActionType.BUY_XP and c.score >= 0.70:
                valid_candidates.append(c)
            elif c.action_type == VisionActionType.SELL_UNIT and c.score >= self.min_sell_score:
                valid_candidates.append(c)

        is_multi = len(valid_candidates) > 1
        for c in valid_candidates:
            ev_descriptions = [e.description for e in c.evidence_list]
            ev_data = {
                "diff_summary": diff.to_dict(),
                "candidate_score": c.score,
                "evidences": [e.to_dict() for e in c.evidence_list],
                "is_multi_action_transition": is_multi
            }
            event = ActionEvent(
                action_type=c.action_type,
                source=ActionSource.OBSERVED,
                timestamp_sec=diff.timestamp_after,
                confidence=c.score,
                evidence=ev_descriptions,
                evidence_data=ev_data,
                quality_flag=QualityFlag.VALID,
                target_champion=c.target_champion,
                slot_index=c.slot_index,
                metadata={"is_multi_action_transition": is_multi}
            )
            emitted_events.append(event)

        return emitted_events

    def process_timeline(
        self,
        observations: List[Observation],
        video_path: Optional[str] = None
    ) -> List[ActionEvent]:
        """순차적 Observation 스트림 및 원본 비디오를 순방향으로 스캔하여 ActionEvent 스트림 생성."""
        if len(observations) < 2:
            return []

        all_events: List[ActionEvent] = []

        for i in range(1, len(observations)):
            obs_before = observations[i - 1]
            obs_after = observations[i]

            diff = compute_state_diff(obs_before, obs_after)

            # Check if candidate transition merits adaptive raw MP4 refinement
            needs_resampling = (
                self.enable_adaptive_resampling and
                self.resampler is not None and
                video_path is not None and
                os.path.exists(video_path) and
                (diff.shop_slots_changed >= 3 or diff.shop_slots_emptied >= 1)
            )

            if needs_resampling:
                refined_obs_list = self.resampler.refine_window(
                    video_path=video_path,
                    start_sec=obs_before.timestamp_sec,
                    end_sec=obs_after.timestamp_sec,
                    target_fps=self.adaptive_target_fps
                )
                if len(refined_obs_list) >= 2:
                    for r_i in range(1, len(refined_obs_list)):
                        r_before = refined_obs_list[r_i - 1]
                        r_after = refined_obs_list[r_i]
                        r_diff = compute_state_diff(r_before, r_after)
                        events = self.detect_actions_from_diff(r_diff, r_before, r_after)
                        all_events.extend(events)
                    continue

            # Default coarse transition detection
            events = self.detect_actions_from_diff(diff, obs_before, obs_after)
            all_events.extend(events)

        return all_events
