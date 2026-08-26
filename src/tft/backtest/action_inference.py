"""Action Detection and Inference Engine: multi-evidence event extraction."""
from typing import Any, Dict, List, Optional, Tuple
from tft.vision.observation import Observation
from tft.vision.events import ActionEvent, VisionActionType, ActionSource, QualityFlag
from tft.vision.timeline import ObservationTimeline


class ActionInferenceEngine:
    """Observation 시계열로부터 관측된 행동(OBSERVED) 및 추론된 행동(INFERRED)을 정밀 추출."""

    def __init__(
        self,
        decision_window_sec: float = 10.0,
        min_roll_diff_slots: int = 3,
        min_detection_confidence: float = 0.60
    ):
        self.decision_window_sec = decision_window_sec
        self.min_roll_diff_slots = min_roll_diff_slots
        self.min_detection_confidence = min_detection_confidence

    def extract_action_events(
        self,
        timeline: ObservationTimeline
    ) -> List[ActionEvent]:
        """Observation 시계열을 분석하여 전체 ActionEvent 리스트를 생성.

        규칙:
          - ROLL, LEVEL_UP, BUY_UNIT: 화면 변화로부터 직접 탐지 -> ActionSource.OBSERVED
          - SAVE_GOLD: 윈도우 동안 경제 행동 부재 시에만 추론 -> ActionSource.INFERRED (절대 OBSERVED 금지)
        """
        events: List[ActionEvent] = []
        observations = timeline.observations
        if len(observations) < 2:
            return events

        economic_event_timestamps: List[float] = []

        for i in range(1, len(observations)):
            prev = observations[i - 1]
            curr = observations[i]
            t = curr.timestamp_sec

            # 1. ROLL Detection
            roll_event = self._detect_roll(prev, curr)
            if roll_event:
                events.append(roll_event)
                economic_event_timestamps.append(t)
                continue

            # 2. BUY_UNIT Detection
            buy_event = self._detect_buy_unit(prev, curr)
            if buy_event:
                events.append(buy_event)
                economic_event_timestamps.append(t)
                continue

            # 3. LEVEL_UP / BUY_XP Detection
            lvl_event = self._detect_level_up(prev, curr)
            if lvl_event:
                events.append(lvl_event)
                economic_event_timestamps.append(t)
                continue

        # 4. SAVE_GOLD Inference (Window-based)
        # Identify quiescent periods of duration >= decision_window_sec with no economic actions
        inferred_save_events = self._infer_save_gold_windows(observations, economic_event_timestamps)
        events.extend(inferred_save_events)

        # Sort all events chronologically
        events.sort(key=lambda e: (e.timestamp_sec, e.action_type.value))
        return events

    def _detect_roll(self, prev: Observation, curr: Observation) -> Optional[ActionEvent]:
        """다중 증거 기반 ROLL 탐지."""
        prev_champs = [c.champion_pred or "EMPTY" for c in prev.shop_cards]
        curr_champs = [c.champion_pred or "EMPTY" for c in curr.shop_cards]

        if len(prev_champs) == 5 and len(curr_champs) == 5:
            diff_indices = [idx for idx in range(5) if prev_champs[idx] != curr_champs[idx]]
            gold_diff = (prev.gold_val - curr.gold_val) if (prev.gold_val is not None and curr.gold_val is not None) else None

            evidence = []
            conf = 0.0

            # Signal 1: Multiple shop cards changed
            if len(diff_indices) >= self.min_roll_diff_slots:
                evidence.append(f"Shop cards changed in {len(diff_indices)}/5 slots simultaneously")
                conf += 0.70

            # Signal 2: Gold decreased by exactly 2 (Reroll cost)
            if gold_diff == 2:
                evidence.append("Player gold decreased by exactly 2G (reroll cost)")
                conf += 0.25
            elif gold_diff is not None and gold_diff > 0:
                evidence.append(f"Player gold decreased by {gold_diff}G")
                conf += 0.10

            if conf >= self.min_detection_confidence:
                return ActionEvent(
                    action_type=VisionActionType.ROLL,
                    source=ActionSource.OBSERVED,
                    timestamp_sec=curr.timestamp_sec,
                    confidence=min(1.0, conf),
                    evidence=evidence,
                    evidence_data={
                        "diff_slots_count": len(diff_indices),
                        "prev_shop": prev_champs,
                        "new_shop": curr_champs,
                        "gold_diff": gold_diff
                    },
                    quality_flag=QualityFlag.VALID
                )
        return None

    def _detect_buy_unit(self, prev: Observation, curr: Observation) -> Optional[ActionEvent]:
        """상점 단일 슬롯 공백화 및 골드 감소 기반 BUY_UNIT 탐지."""
        prev_champs = [c.champion_pred or "EMPTY" for c in prev.shop_cards]
        curr_champs = [c.champion_pred or "EMPTY" for c in curr.shop_cards]

        if len(prev_champs) == 5 and len(curr_champs) == 5:
            diff_indices = [idx for idx in range(5) if prev_champs[idx] != curr_champs[idx]]
            if len(diff_indices) == 1:
                idx = diff_indices[0]
                if curr_champs[idx] == "EMPTY" and prev_champs[idx] != "EMPTY":
                    bought_champ = prev_champs[idx]
                    cost_val = prev.shop_cards[idx].cost_pred if idx < len(prev.shop_cards) else None
                    gold_diff = (prev.gold_val - curr.gold_val) if (prev.gold_val is not None and curr.gold_val is not None) else None

                    evidence = [f"Shop card at slot {idx+1} transitioned from '{bought_champ}' to EMPTY"]
                    conf = 0.75

                    if cost_val is not None and gold_diff == cost_val:
                        evidence.append(f"Gold decreased by unit cost ({cost_val}G)")
                        conf += 0.20

                    return ActionEvent(
                        action_type=VisionActionType.BUY_UNIT,
                        source=ActionSource.OBSERVED,
                        timestamp_sec=curr.timestamp_sec,
                        confidence=min(1.0, conf),
                        evidence=evidence,
                        evidence_data={
                            "bought_slot": idx + 1,
                            "champion": bought_champ,
                            "cost": cost_val,
                            "gold_diff": gold_diff
                        },
                        target_champion=bought_champ,
                        slot_index=idx,
                        quality_flag=QualityFlag.VALID
                    )
        return None

    def _detect_level_up(self, prev: Observation, curr: Observation) -> Optional[ActionEvent]:
        """레벨 증가 및 골드/XP 감소 기반 LEVEL_UP / BUY_XP 탐지."""
        if prev.level_val is not None and curr.level_val is not None:
            if curr.level_val > prev.level_val:
                gold_diff = (prev.gold_val - curr.gold_val) if (prev.gold_val is not None and curr.gold_val is not None) else None
                evidence = [f"Player level increased from {prev.level_val} to {curr.level_val}"]
                if gold_diff and gold_diff >= 4:
                    evidence.append(f"Gold decreased by {gold_diff}G (XP purchase)")
                return ActionEvent(
                    action_type=VisionActionType.LEVEL_UP,
                    source=ActionSource.OBSERVED,
                    timestamp_sec=curr.timestamp_sec,
                    confidence=0.90,
                    evidence=evidence,
                    evidence_data={
                        "prev_level": prev.level_val,
                        "new_level": curr.level_val,
                        "gold_diff": gold_diff
                    },
                    quality_flag=QualityFlag.VALID
                )
        return None

    def _infer_save_gold_windows(
        self,
        observations: List[Observation],
        economic_timestamps: List[float]
    ) -> List[ActionEvent]:
        """지정된 의사결정 윈도우 동안 경제 행동이 없었던 구간에 대해 INFERRED SAVE_GOLD 생성."""
        inferred_events: List[ActionEvent] = []
        if not observations:
            return inferred_events

        start_t = observations[0].timestamp_sec
        end_t = observations[-1].timestamp_sec

        # Check windows of size decision_window_sec
        w_size = self.decision_window_sec
        current_w_start = start_t

        while current_w_start + w_size <= end_t:
            w_end = current_w_start + w_size
            # Count economic actions in [w_start, w_end]
            actions_in_w = [t for t in economic_timestamps if current_w_start <= t <= w_end]

            if len(actions_in_w) == 0:
                # Quiescent period confirmed -> Infer SAVE_GOLD at midpoint of window
                mid_t = round(current_w_start + w_size / 2.0, 2)
                inferred_events.append(ActionEvent(
                    action_type=VisionActionType.SAVE_GOLD,
                    source=ActionSource.INFERRED,  # STRICT: Inferred, NOT Observed
                    timestamp_sec=mid_t,
                    confidence=0.80,
                    evidence=[
                        f"No economic action (ROLL/BUY/LEVEL) observed in {w_size:.1f}s window [{current_w_start:.1f}s - {w_end:.1f}s]",
                        "Player maintained gold for compound interest accumulation"
                    ],
                    evidence_data={
                        "window_start_sec": current_w_start,
                        "window_end_sec": w_end,
                        "window_duration_sec": w_size
                    },
                    quality_flag=QualityFlag.VALID
                ))
                current_w_start += w_size  # Advance full window
            else:
                # Advance to after the last action
                current_w_start = max(actions_in_w) + 1.0

        return inferred_events
