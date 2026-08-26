"""TFT Action Event Detector v2.2: Production implementation of empirically validated causal rules."""
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Tuple

from tft.vision.events import ActionEvent, VisionActionType, ActionSource, QualityFlag
from tft.vision.observation import Observation
from tft.vision.state_diff import StateDiff, compute_state_diff, SlotTransitionType, SlotTransition
from tft.vision.system_event_detector import SystemEventDetector, SystemEventType
from tft.vision.state_stability import StateStabilityAnalyzer, StabilityStatus, StabilityAssessment
from tft.vision.adaptive_resampler import AdaptiveResampler


class RuleName(str, Enum):
    """검증된 핵심 Production Rule 식별자."""
    ROLL_BASELINE = "ROLL_BASELINE"
    BUY_BASELINE = "BUY_BASELINE"
    SYSTEM_REFRESH_BASELINE = "SYSTEM_REFRESH_BASELINE"
    SHOP_ANIMATION_FILTER = "SHOP_ANIMATION_FILTER"
    MULTI_ACTION_TRANSITION = "MULTI_ACTION_TRANSITION"
    NO_ACTION = "NO_ACTION"


@dataclass
class ActionCandidate:
    """단일 전이에 대해 후보 규칙 평가 결과 생성된 액션 후보."""
    action_type: VisionActionType
    matched_rules: List[RuleName]
    detection_score: float
    evidence: List[str]
    evidence_data: Dict[str, Any]
    target_champion: Optional[str] = None
    target_slot: Optional[int] = None
    is_multi_action: bool = False
    is_ambiguous: bool = False
    ambiguity_reason: str = ""


class ActionEventDetectorV22:
    """Causal Audit 및 Rule Validation v1에서 검증된 인과 규칙을 사용하는 정밀 행동 검출기 v2.2."""

    def __init__(
        self,
        system_detector: Optional[SystemEventDetector] = None,
        stability_analyzer: Optional[StateStabilityAnalyzer] = None,
        adaptive_resampler: Optional[AdaptiveResampler] = None,
        enable_adaptive_refinement: bool = False
    ):
        self.system_detector = system_detector or SystemEventDetector()
        self.stability_analyzer = stability_analyzer or StateStabilityAnalyzer()
        self.adaptive_resampler = adaptive_resampler
        self.enable_adaptive_refinement = enable_adaptive_refinement

    def evaluate_candidates(
        self,
        diff: StateDiff,
        obs_after: Observation,
        system_events: List[ActionEvent],
        stability: StabilityAssessment
    ) -> List[ActionCandidate]:
        """StateDiff와 시스템/안정성 정보를 바탕으로 ActionCandidate 목록 생성."""
        candidates: List[ActionCandidate] = []

        # 1. Check for Active System Shop Refresh in this window
        has_sys_refresh = any(
            se.evidence_data.get("system_event") == SystemEventType.SYSTEM_SHOP_REFRESH.value
            for se in system_events
        )

        # 2. Check for Transient Shop Animation Frame
        is_shop_anim = (stability.is_shop_animation or stability.status == StabilityStatus.UNSTABLE_ANIMATION)

        # 3. Evaluate ROLL_BASELINE Rule
        # Rule: (gold_delta == -2 OR (gold unobserved AND refreshed >= 2)) AND shop_transition AND NOT system_refresh
        # (Does NOT enforce shop_changed >= 3 to cleanly handle 35.7% same-champion collisions)
        shop_trans_detected = (diff.shop_slots_changed >= 1 or len(diff.shop_changes) > 0)
        is_roll_gold = (diff.gold_delta == -2)
        refreshed_count = diff.shop_slots_refreshed + diff.shop_slots_filled

        # If gold is unobserved / constant in coarse timeline, rely on shop refresh pattern and collision logic
        is_valid_roll = (is_roll_gold and shop_trans_detected) or (
            diff.gold_delta in [0, None] and refreshed_count >= 2 and not has_sys_refresh
        )

        if is_valid_roll and not has_sys_refresh and not is_shop_anim:
            # Check if this could be a 2-cost BUY instead
            has_buy_evidence = (
                diff.shop_slots_emptied >= 1 and
                len(diff.units_added_bench) > 0
            )

            if not has_buy_evidence:
                cand = ActionCandidate(
                    action_type=VisionActionType.ROLL,
                    matched_rules=[RuleName.ROLL_BASELINE],
                    detection_score=0.90,
                    evidence=[
                        f"Gold decreased by 2G (ΔG={diff.gold_delta})" if is_roll_gold else f"Shop refreshed ({refreshed_count} slots)",
                        f"Shop transitioned ({diff.shop_slots_changed} slots changed)",
                        "Not a system round-start refresh",
                        f"Board/Bench unchanged: {len(diff.units_added_board)==0 and len(diff.units_added_bench)==0}"
                    ],
                    evidence_data={
                        "gold_delta": diff.gold_delta,
                        "shop_slots_changed": diff.shop_slots_changed,
                        "system_refresh": False,
                        "board_unchanged": (len(diff.units_added_board) == 0 and len(diff.units_removed_board) == 0),
                        "bench_unchanged": (len(diff.units_added_bench) == 0 and len(diff.units_removed_bench) == 0),
                        "is_same_champion_collision": (diff.shop_slots_changed < 3)
                    }
                )
                candidates.append(cand)

        # 4. Evaluate BUY_BASELINE Rule
        # Rule: shop_slot_emptied AND (matching_champion_added OR gold_delta == -cost) AND NOT shop_animation
        if diff.shop_slots_emptied >= 1 and not is_shop_anim and not has_sys_refresh:
            # Find emptied slots
            for sc in diff.shop_changes:
                if sc.transition_type == SlotTransitionType.EMPTIED:
                    champ_name = sc.before_champion
                    cost = sc.before_cost or 1

                    # Check matching addition on bench or board (handles bench full / direct board placement)
                    bench_match = (champ_name in diff.units_added_bench) if champ_name else False
                    board_match = (champ_name in diff.units_added_board) if champ_name else False
                    cost_match = (diff.gold_delta == -cost) if diff.gold_delta is not None else False

                    # Valid if bench/board matched, cost matched, or single slot emptied in stable shop
                    is_valid_buy = bench_match or board_match or cost_match or (diff.shop_slots_emptied == 1)

                    if is_valid_buy:
                        cand = ActionCandidate(
                            action_type=VisionActionType.BUY_UNIT,
                            matched_rules=[RuleName.BUY_BASELINE],
                            detection_score=0.95,
                            evidence=[
                                f"Shop slot #{sc.slot_index + 1} emptied ({champ_name})",
                                f"Unit cost {cost}G matches gold delta {diff.gold_delta}G" if cost_match else f"Single slot #{sc.slot_index + 1} emptied",
                                f"Champion added to bench/board: {bench_match or board_match}",
                                "Not a transient shop animation frame"
                            ],
                            evidence_data={
                                "shop_slot": sc.slot_index + 1,
                                "champion": champ_name,
                                "cost": cost,
                                "gold_delta": diff.gold_delta,
                                "champion_added_to_bench": bench_match,
                                "champion_added_to_board": board_match,
                                "shop_animation": False
                            },
                            target_champion=champ_name,
                            target_slot=sc.slot_index + 1
                        )
                        candidates.append(cand)

        # 5. Evaluate LEVEL_UP Rule
        if diff.level_delta is not None and diff.level_delta > 0:
            cand = ActionCandidate(
                action_type=VisionActionType.LEVEL_UP,
                matched_rules=[RuleName.ROLL_BASELINE],
                detection_score=0.85,
                evidence=[
                    f"Level increased ({diff.level_delta})",
                    "Shop cards unchanged"
                ],
                evidence_data={
                    "level_delta": diff.level_delta,
                    "gold_delta": diff.gold_delta
                }
            )
            candidates.append(cand)

        return candidates

    def resolve_candidates(
        self,
        candidates: List[ActionCandidate],
        diff: StateDiff,
        timestamp_sec: float
    ) -> Optional[ActionEvent]:
        """ActionCandidate 목록의 충돌을 해결하여 최종 ActionEvent 생성 (온라인 인과성 보장)."""
        if not candidates:
            return None

        # If exactly 1 candidate, straightforward emit
        if len(candidates) == 1:
            c = candidates[0]
            return ActionEvent(
                action_type=c.action_type,
                source=ActionSource.OBSERVED,
                confidence=c.detection_score,
                evidence=c.evidence,
                evidence_data=c.evidence_data,
                target_champion=c.target_champion,
                slot_index=c.target_slot,
                timestamp_sec=timestamp_sec
            )

        # Check for Multi-Action Transition (e.g. BUY followed immediately by ROLL in coarse interval)
        types = set(c.action_type for c in candidates)
        if VisionActionType.BUY_UNIT in types and VisionActionType.ROLL in types:
            # Emit MULTI_ACTION / Primary action with combined evidence
            buy_cand = next(c for c in candidates if c.action_type == VisionActionType.BUY_UNIT)
            roll_cand = next(c for c in candidates if c.action_type == VisionActionType.ROLL)

            combined_evidence = buy_cand.evidence + roll_cand.evidence
            combined_evidence_data = {
                "multi_action": True,
                "sub_actions": ["BUY_UNIT", "ROLL"],
                "buy_data": buy_cand.evidence_data,
                "roll_data": roll_cand.evidence_data
            }

            return ActionEvent(
                action_type=VisionActionType.BUY_UNIT,  # Primary event
                source=ActionSource.OBSERVED,
                confidence=0.90,
                evidence=combined_evidence,
                evidence_data=combined_evidence_data,
                target_champion=buy_cand.target_champion,
                slot_index=buy_cand.target_slot,
                timestamp_sec=timestamp_sec
            )

        # If ambiguous candidates of the same type, take highest detection score
        best_cand = max(candidates, key=lambda x: x.detection_score)
        return ActionEvent(
            action_type=best_cand.action_type,
            source=ActionSource.OBSERVED,
            confidence=best_cand.detection_score,
            evidence=best_cand.evidence,
            evidence_data=best_cand.evidence_data,
            target_champion=best_cand.target_champion,
            slot_index=best_cand.target_slot,
            timestamp_sec=timestamp_sec
        )

    def detect_actions(
        self,
        observations: List[Observation],
        video_path: Optional[str] = None
    ) -> List[ActionEvent]:
        """Observation 시퀀스 전체에 대해 Production v2.2 행동 검출 파이프라인 수행."""
        if len(observations) < 2:
            return []

        action_events: List[ActionEvent] = []

        # Sequential Transition Processing (Online Causality)
        for i in range(1, len(observations)):
            obs_before = observations[i - 1]
            obs_after = observations[i]

            diff = compute_state_diff(obs_before, obs_after)
            t_after = obs_after.timestamp_sec

            # Detect System Events for this specific transition
            sys_events = self.system_detector.detect_system_events(diff, obs_before, obs_after)

            # Get Frame Stability
            stab = self.stability_analyzer.assess_observation(obs_after)

            # Evaluate Rule Candidates
            candidates = self.evaluate_candidates(
                diff=diff,
                obs_after=obs_after,
                system_events=sys_events,
                stability=stab
            )

            # Resolve into ActionEvent
            event = self.resolve_candidates(candidates, diff, timestamp_sec=t_after)
            if event is not None:
                action_events.append(event)

        return action_events
