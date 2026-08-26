"""TFT System Event Detector: Detects automated system-driven state changes (Round Start, Free Shop Refreshes)."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from tft.vision.events import ActionEvent, VisionActionType, ActionSource, QualityFlag
from tft.vision.observation import Observation
from tft.vision.state_diff import StateDiff


class SystemEventType(str, Enum):
    """게임 시스템이 유발하는 자동 사건 유형."""
    SYSTEM_SHOP_REFRESH = "SYSTEM_SHOP_REFRESH"  # 라운드 시작 시 무료 자동 상점 갱신
    ROUND_START = "ROUND_START"                  # 라운드 시작 시점 (정비 단계 진입)
    ROUND_TRANSITION = "ROUND_TRANSITION"        # 라운드 간 전이 구간
    SHOP_ANIMATION = "SHOP_ANIMATION"            # 상점 렌더링 과도기 상태


class SystemEventDetector:
    """게임 시스템의 자동 갱신 및 라운드 전이를 분리하는 검출기."""

    def __init__(self, round_interval_approx_sec: float = 60.0):
        self.round_interval_approx_sec = round_interval_approx_sec

    def detect_system_events(
        self,
        diff: StateDiff,
        obs_before: Observation,
        obs_after: Observation
    ) -> List[ActionEvent]:
        """StateDiff와 두 관측값으로부터 시스템 이벤트를 독립 검출."""
        events: List[ActionEvent] = []

        # 1. Round Start / Transition Detection
        is_round_change = False
        if obs_before.stage_text and obs_after.stage_text:
            if obs_before.stage_text != obs_after.stage_text:
                is_round_change = True
                ev_round = ActionEvent(
                    action_type=VisionActionType.UNKNOWN,
                    source=ActionSource.OBSERVED,
                    timestamp_sec=diff.timestamp_after,
                    confidence=1.0,
                    evidence=[f"Stage-round changed from {obs_before.stage_text} to {obs_after.stage_text}"],
                    evidence_data={"stage_before": obs_before.stage_text, "stage_after": obs_after.stage_text, "system_event": SystemEventType.ROUND_START.value},
                    quality_flag=QualityFlag.VALID,
                    metadata={"system_event_type": SystemEventType.ROUND_START.value}
                )
                events.append(ev_round)

        # 2. System Shop Refresh Detection
        # A full shop refresh (>=4 slots changed) that occurs at round start OR with zero gold cost (delta == 0)
        # without player reroll interaction evidence
        refreshed_count = diff.shop_slots_refreshed + diff.shop_slots_filled
        is_free_refresh = False

        if refreshed_count >= 4:
            if is_round_change:
                is_free_refresh = True
            elif diff.gold_delta is not None and diff.gold_delta >= 0:
                is_free_refresh = True

        if is_free_refresh:
            ev_refresh = ActionEvent(
                action_type=VisionActionType.UNKNOWN,
                source=ActionSource.OBSERVED,
                timestamp_sec=diff.timestamp_after,
                confidence=0.95,
                evidence=[
                    f"System free shop refresh ({refreshed_count}/5 slots updated automatically)",
                    f"Round start transition: {is_round_change}, Gold delta: {diff.gold_delta}"
                ],
                evidence_data={
                    "system_event": SystemEventType.SYSTEM_SHOP_REFRESH.value,
                    "refreshed_slots": refreshed_count,
                    "is_round_start": is_round_change,
                    "gold_delta": diff.gold_delta
                },
                quality_flag=QualityFlag.VALID,
                metadata={"system_event_type": SystemEventType.SYSTEM_SHOP_REFRESH.value}
            )
            events.append(ev_refresh)

        return events
