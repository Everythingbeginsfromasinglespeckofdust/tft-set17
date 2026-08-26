"""TFT Action Event Detector v2 -- Multi-Signal State-Transition Driven Action Detector."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from tft.vision.events import ActionEvent, VisionActionType, ActionSource, QualityFlag
from tft.vision.observation import Observation
from tft.vision.state_diff import StateDiff, SlotTransitionType, compute_state_diff


class EvidenceCode(str, Enum):
    """독립 증거 식별 코드."""
    GOLD_DECREASE_2 = "GOLD_DECREASE_2"
    GOLD_DECREASE_MATCHING_COST = "GOLD_DECREASE_MATCHING_COST"
    GOLD_DECREASE_XP_MULTIPLE = "GOLD_DECREASE_XP_MULTIPLE"
    GOLD_INCREASE_SALE = "GOLD_INCREASE_SALE"

    MULTI_SLOT_REFRESH_3PLUS = "MULTI_SLOT_REFRESH_3PLUS"
    SLOT_EMPTIED = "SLOT_EMPTIED"
    CHAMPION_ADDED_TO_BENCH = "CHAMPION_ADDED_TO_BENCH"
    CHAMPION_ADDED_TO_BOARD = "CHAMPION_ADDED_TO_BOARD"
    CHAMPION_REMOVED_FROM_BENCH = "CHAMPION_REMOVED_FROM_BENCH"
    CHAMPION_REMOVED_FROM_BOARD = "CHAMPION_REMOVED_FROM_BOARD"
    COMPOUND_BUY_BEFORE_ROLL = "COMPOUND_BUY_BEFORE_ROLL"

    LEVEL_INCREASED = "LEVEL_INCREASED"
    XP_INCREASED_LEVEL_SAME = "XP_INCREASED_LEVEL_SAME"
    BOARD_BENCH_UNCHANGED = "BOARD_BENCH_UNCHANGED"
    SHOP_UNCHANGED = "SHOP_UNCHANGED"


@dataclass
class ActionEvidence:
    """개별 행동 증거 컨테이너."""
    code: EvidenceCode
    value: Any
    strength: float  # 0.0 to 1.0
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code.value,
            "value": self.value,
            "strength": round(self.strength, 3),
            "description": self.description
        }


@dataclass
class ActionCandidate:
    """단일 전이에서 산출된 행동 후보 및 점수."""
    action_type: VisionActionType
    score: float
    evidence_list: List[ActionEvidence] = field(default_factory=list)
    target_champion: Optional[str] = None
    slot_index: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "score": round(self.score, 3),
            "target_champion": self.target_champion,
            "slot_index": self.slot_index,
            "evidence": [e.to_dict() for e in self.evidence_list],
            "metadata": self.metadata
        }


class ActionEventDetectorV2:
    """StateDiff 기반 다중 신호 행동 검출기 v2."""

    def __init__(
        self,
        min_roll_score: float = 0.65,
        min_buy_score: float = 0.70,
        min_levelup_score: float = 0.70,
        min_sell_score: float = 0.60
    ):
        self.min_roll_score = min_roll_score
        self.min_buy_score = min_buy_score
        self.min_levelup_score = min_levelup_score
        self.min_sell_score = min_sell_score

    def detect_candidates(self, diff: StateDiff, obs_before: Optional[Observation] = None, obs_after: Optional[Observation] = None) -> List[ActionCandidate]:
        """StateDiff로부터 발생 가능한 모든 ActionCandidate를 독립 점수화."""
        candidates: List[ActionCandidate] = []

        # 1. Evaluate LEVEL_UP Candidate
        if diff.level_delta is not None and diff.level_delta > 0:
            ev_list = [
                ActionEvidence(
                    code=EvidenceCode.LEVEL_INCREASED,
                    value=diff.level_delta,
                    strength=1.0,
                    description=f"Level increased from {diff.level_before} to {diff.level_after} (+{diff.level_delta})"
                )
            ]
            if diff.gold_delta is not None and diff.gold_delta <= -4:
                ev_list.append(ActionEvidence(
                    code=EvidenceCode.GOLD_DECREASE_XP_MULTIPLE,
                    value=diff.gold_delta,
                    strength=0.85,
                    description=f"Gold decreased by {abs(diff.gold_delta)}G consistent with Level Up purchase"
                ))
            score = float(np.mean([e.strength for e in ev_list])) if ev_list else 0.95
            candidates.append(ActionCandidate(
                action_type=VisionActionType.LEVEL_UP,
                score=score,
                evidence_list=ev_list
            ))

        # 2. Evaluate BUY_XP Candidate (Level unchanged but XP increased or 4G spent)
        elif diff.xp_delta is not None and diff.xp_delta > 0 and (diff.level_delta == 0 or diff.level_delta is None):
            ev_list = [
                ActionEvidence(
                    code=EvidenceCode.XP_INCREASED_LEVEL_SAME,
                    value=diff.xp_delta,
                    strength=0.90,
                    description=f"XP increased by +{diff.xp_delta} while level remained {diff.level_before}"
                )
            ]
            if diff.gold_delta is not None and diff.gold_delta == -4:
                ev_list.append(ActionEvidence(
                    code=EvidenceCode.GOLD_DECREASE_XP_MULTIPLE,
                    value=diff.gold_delta,
                    strength=0.90,
                    description="Gold decreased exactly by 4G (1 XP purchase)"
                ))
            score = float(np.mean([e.strength for e in ev_list])) if ev_list else 0.85
            candidates.append(ActionCandidate(
                action_type=VisionActionType.BUY_XP,
                score=score,
                evidence_list=ev_list
            ))

        # 3. Evaluate BUY_UNIT Candidates
        emptied_slots = [st for st in diff.shop_changes if st.transition_type == SlotTransitionType.EMPTIED]

        # Domain Rule: If 2+ slots empty simultaneously with no bench additions, that is an animation wipe, not multiple BUYs
        if len(emptied_slots) == 1 or (len(emptied_slots) > 1 and diff.units_added_bench):
            for st in emptied_slots:
                ev_list = [
                    ActionEvidence(
                        code=EvidenceCode.SLOT_EMPTIED,
                        value=st.slot_index + 1,
                        strength=0.85,
                        description=f"Slot {st.slot_index + 1} ({st.before_champion}, {st.before_cost}C) transitioned from RECOGNIZED to EMPTY"
                    )
                ]
                champ_name = st.before_champion
                cost = st.before_cost or 1

                if champ_name and champ_name in diff.units_added_bench:
                    ev_list.append(ActionEvidence(
                        code=EvidenceCode.CHAMPION_ADDED_TO_BENCH,
                        value=champ_name,
                        strength=0.95,
                        description=f"Champion '{champ_name}' was added to bench"
                    ))
                elif champ_name and champ_name in diff.units_added_board:
                    ev_list.append(ActionEvidence(
                        code=EvidenceCode.CHAMPION_ADDED_TO_BOARD,
                        value=champ_name,
                        strength=0.90,
                        description=f"Champion '{champ_name}' was added directly to board"
                    ))

                if diff.gold_delta is not None and diff.gold_delta == -cost:
                    ev_list.append(ActionEvidence(
                        code=EvidenceCode.GOLD_DECREASE_MATCHING_COST,
                        value=diff.gold_delta,
                        strength=0.95,
                        description=f"Gold decreased exactly by cost of {champ_name} ({diff.gold_delta}G == -{cost}G)"
                    ))

                score = float(np.mean([e.strength for e in ev_list])) if ev_list else 0.80
                candidates.append(ActionCandidate(
                    action_type=VisionActionType.BUY_UNIT,
                    score=score,
                    evidence_list=ev_list,
                    target_champion=champ_name,
                    slot_index=st.slot_index
                ))

        # 3b. From compound BUY + ROLL (Unit added to bench that was in previous shop, even if shop refreshed)
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

        # 4. Evaluate ROLL Candidate
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
            if diff.gold_delta is not None and (diff.gold_delta == -2 or diff.gold_delta <= -2):
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

            score = float(np.mean([e.strength for e in ev_list])) if ev_list else 0.80
            candidates.append(ActionCandidate(
                action_type=VisionActionType.ROLL,
                score=score,
                evidence_list=ev_list
            ))

        # 5. Evaluate SELL_UNIT Candidate
        if diff.units_removed_bench or diff.units_removed_board:
            rem_units = diff.units_removed_bench + diff.units_removed_board
            ev_list = []
            if diff.units_removed_bench:
                ev_list.append(ActionEvidence(
                    code=EvidenceCode.CHAMPION_REMOVED_FROM_BENCH,
                    value=diff.units_removed_bench,
                    strength=0.85,
                    description=f"Units removed from bench: {diff.units_removed_bench}"
                ))
            if diff.units_removed_board:
                ev_list.append(ActionEvidence(
                    code=EvidenceCode.CHAMPION_REMOVED_FROM_BOARD,
                    value=diff.units_removed_board,
                    strength=0.80,
                    description=f"Units removed from board: {diff.units_removed_board}"
                ))
            if diff.gold_delta is not None and diff.gold_delta > 0:
                ev_list.append(ActionEvidence(
                    code=EvidenceCode.GOLD_INCREASE_SALE,
                    value=diff.gold_delta,
                    strength=0.90,
                    description=f"Gold increased by +{diff.gold_delta}G following unit removal"
                ))

            score = float(np.mean([e.strength for e in ev_list])) if ev_list else 0.70
            candidates.append(ActionCandidate(
                action_type=VisionActionType.SELL_UNIT,
                score=score,
                evidence_list=ev_list,
                target_champion=rem_units[0] if rem_units else None
            ))

        return candidates

    def detect_actions(
        self,
        diff: StateDiff,
        obs_after: Observation,
        obs_before: Optional[Observation] = None
    ) -> List[ActionEvent]:
        """StateDiff를 해석하여 정규화된 ActionEvent 목록 생성."""
        candidates = self.detect_candidates(diff, obs_before=obs_before, obs_after=obs_after)
        if not candidates:
            return []

        # Filter candidates by minimum score threshold
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

        if not valid_candidates:
            return []

        events: List[ActionEvent] = []
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
            events.append(event)

        return events

    def process_timeline(self, observations: List[Observation]) -> List[ActionEvent]:
        """순차적 Observation 스트림 전체를 순방향(Online)으로 스캔하여 ActionEvent 스트림 생성."""
        if len(observations) < 2:
            return []

        all_events: List[ActionEvent] = []
        for i in range(1, len(observations)):
            obs_before = observations[i - 1]
            obs_after = observations[i]

            diff = compute_state_diff(obs_before, obs_after)
            events = self.detect_actions(diff, obs_after, obs_before=obs_before)
            all_events.extend(events)

        return all_events
