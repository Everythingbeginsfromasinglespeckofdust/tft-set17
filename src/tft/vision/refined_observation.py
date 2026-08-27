"""Refined Observation, Candidate Trigger Detection, and Temporal Merging Models."""
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from tft.vision.observation import Observation, CardObservation, UnitObservation
from tft.vision.timeline import ObservationTimeline
from tft.vision.state_diff import StateDiff, compute_state_diff


class ResolutionSource(str, Enum):
    """관측치의 시간 해상도 출처."""
    COARSE = "COARSE"
    REFINED = "REFINED"
    INTERPOLATED = "INTERPOLATED"


class TriggerReason(str, Enum):
    """국소 고해상도 리샘플링 트리거 사유."""
    GOLD_DELTA = "GOLD_DELTA"
    GOLD_UNKNOWN = "GOLD_UNKNOWN"
    GOLD_CONFIDENCE_DROP = "GOLD_CONFIDENCE_DROP"
    SHOP_SLOTS_CHANGED = "SHOP_SLOTS_CHANGED"
    SHOP_SLOT_EMPTIED = "SHOP_SLOT_EMPTIED"
    SHOP_ANIMATION = "SHOP_ANIMATION"
    BOARD_DELTA = "BOARD_DELTA"
    BENCH_DELTA = "BENCH_DELTA"
    STAGE_ROUND_TRANSITION = "STAGE_ROUND_TRANSITION"


@dataclass
class CandidateWindow:
    """국소 고해상도 리샘플링 대상 시간 구간."""
    window_id: str
    start_sec: float
    end_sec: float
    trigger_time_sec: float
    trigger_reasons: List[TriggerReason] = field(default_factory=list)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_id": self.window_id,
            "start_sec": round(self.start_sec, 3),
            "end_sec": round(self.end_sec, 3),
            "duration_sec": round(self.end_sec - self.start_sec, 3),
            "trigger_time_sec": round(self.trigger_time_sec, 3),
            "trigger_reasons": [r.value for r in self.trigger_reasons],
            "confidence": round(self.confidence, 3),
            "metadata": self.metadata
        }


class CandidateTriggerDetector:
    """Coarse 0.5s 관측치 시계열에서 고해상도 리샘플링이 필요한 후보 전이 구간을 감지."""

    DEFAULT_WINDOW_RADIUS_SEC = 0.5

    def __init__(self, window_radius_sec: float = 0.5):
        self.window_radius_sec = window_radius_sec

    def detect_candidates(
        self,
        timeline: ObservationTimeline
    ) -> List[CandidateWindow]:
        """Coarse 관측치 타임라인을 순회하며 후보 전이 구간 목록 생성."""
        candidates: List[CandidateWindow] = []
        obs_list = timeline.observations
        if len(obs_list) < 2:
            return candidates

        for i in range(1, len(obs_list)):
            obs_prev = obs_list[i - 1]
            obs_curr = obs_list[i]
            t_curr = obs_curr.timestamp_sec
            reasons: List[TriggerReason] = []

            # 1. Gold Trigger Check (action level delta >= 2G)
            g_prev = obs_prev.gold_val
            g_curr = obs_curr.gold_val
            if g_prev is not None and g_curr is not None and abs(g_prev - g_curr) >= 2:
                reasons.append(TriggerReason.GOLD_DELTA)
            elif g_curr is None and g_prev is not None:
                reasons.append(TriggerReason.GOLD_UNKNOWN)

            # 2. Shop StateDiff Trigger Check (slots emptied or >= 2 slots changed)
            diff = compute_state_diff(obs_prev, obs_curr)
            if diff.shop_slots_emptied > 0:
                reasons.append(TriggerReason.SHOP_SLOT_EMPTIED)
            elif diff.shop_slots_changed >= 2:
                reasons.append(TriggerReason.SHOP_SLOTS_CHANGED)
            elif diff.metadata.get("shop_animation_active", False):
                reasons.append(TriggerReason.SHOP_ANIMATION)

            # 3. Board / Bench Trigger Check
            if diff.units_added_bench or diff.units_removed_bench:
                reasons.append(TriggerReason.BENCH_DELTA)
            if diff.units_added_board or diff.units_removed_board:
                reasons.append(TriggerReason.BOARD_DELTA)

            # 4. System Transition Check
            if obs_prev.stage_text and obs_curr.stage_text and obs_prev.stage_text != obs_curr.stage_text:
                reasons.append(TriggerReason.STAGE_ROUND_TRANSITION)

            if reasons:
                cand = CandidateWindow(
                    window_id=f"CAND_{len(candidates):04d}_{int(t_curr)}",
                    start_sec=max(0.0, t_curr - self.window_radius_sec),
                    end_sec=t_curr + self.window_radius_sec,
                    trigger_time_sec=t_curr,
                    trigger_reasons=reasons,
                    metadata={"slots_changed": diff.shop_slots_changed, "gold_delta": diff.gold_delta}
                )
                candidates.append(cand)

        return candidates


class WindowMerger:
    """인접하거나 겹치는 CandidateWindow들을 하나의 연속된 구간으로 병합."""

    @staticmethod
    def merge_windows(
        windows: List[CandidateWindow],
        max_gap_sec: float = 0.5
    ) -> List[CandidateWindow]:
        """겹치거나 gap <= max_gap_sec 인 윈도우들을 병합하여 반환."""
        if not windows:
            return []

        # Sort by start_sec
        sorted_windows = sorted(windows, key=lambda w: w.start_sec)
        merged: List[CandidateWindow] = []

        curr_start = sorted_windows[0].start_sec
        curr_end = sorted_windows[0].end_sec
        curr_reasons: Set[TriggerReason] = set(sorted_windows[0].trigger_reasons)
        trigger_times: List[float] = [sorted_windows[0].trigger_time_sec]

        for w in sorted_windows[1:]:
            if w.start_sec <= curr_end + max_gap_sec:
                # Overlap / Close gap -> Merge
                curr_end = max(curr_end, w.end_sec)
                curr_reasons.update(w.trigger_reasons)
                trigger_times.append(w.trigger_time_sec)
            else:
                # Disjoint -> Emit current and start new
                merged.append(CandidateWindow(
                    window_id=f"MERGED_{len(merged):03d}_{int(curr_start)}",
                    start_sec=curr_start,
                    end_sec=curr_end,
                    trigger_time_sec=float(np.median(trigger_times)),
                    trigger_reasons=list(curr_reasons),
                    metadata={"sub_window_count": len(trigger_times)}
                ))
                curr_start = w.start_sec
                curr_end = w.end_sec
                curr_reasons = set(w.trigger_reasons)
                trigger_times = [w.trigger_time_sec]

        merged.append(CandidateWindow(
            window_id=f"MERGED_{len(merged):03d}_{int(curr_start)}",
            start_sec=curr_start,
            end_sec=curr_end,
            trigger_time_sec=float(np.median(trigger_times)),
            trigger_reasons=list(curr_reasons),
            metadata={"sub_window_count": len(trigger_times)}
        ))

        return merged


class TemporalMerger:
    """Coarse 관측치와 Local Refined 관측치를 시계열 순방향으로 무결하게 통합."""

    @staticmethod
    def merge_timelines(
        coarse_timeline: ObservationTimeline,
        refined_observations: List[Observation],
        tolerance_sec: float = 0.02
    ) -> ObservationTimeline:
        """Refined observation이 존재하는 시점에서는 coarse observation보다 우선하여 통합 타임라인 생성."""
        merged_timeline = ObservationTimeline(
            video_path=coarse_timeline.video_path,
            duration_sec=coarse_timeline.duration_sec,
            fps=coarse_timeline.fps
        )

        all_obs_map: Dict[float, Observation] = {}

        # 1. Add coarse observations
        for o in coarse_timeline.observations:
            t_key = round(o.timestamp_sec, 3)
            srcs = dict(o.sources)
            srcs["resolution"] = ResolutionSource.COARSE.value
            obs_copy = Observation(
                timestamp_sec=o.timestamp_sec,
                frame_index=o.frame_index,
                stage_text=o.stage_text,
                gold_val=o.gold_val,
                hp_val=o.hp_val,
                level_val=o.level_val,
                xp_val=o.xp_val,
                shop_cards=o.shop_cards,
                field_detections=o.field_detections,
                bench_detections=o.bench_detections,
                sources=srcs,
                confidences=dict(o.confidences),
                overall_confidence=o.overall_confidence,
                metadata=dict(o.metadata)
            )
            all_obs_map[t_key] = obs_copy

        # 2. Add / overwrite with refined observations
        for o in refined_observations:
            t_key = round(o.timestamp_sec, 3)
            srcs = dict(o.sources)
            srcs["resolution"] = ResolutionSource.REFINED.value
            obs_copy = Observation(
                timestamp_sec=o.timestamp_sec,
                frame_index=o.frame_index,
                stage_text=o.stage_text,
                gold_val=o.gold_val,
                hp_val=o.hp_val,
                level_val=o.level_val,
                xp_val=o.xp_val,
                shop_cards=o.shop_cards,
                field_detections=o.field_detections,
                bench_detections=o.bench_detections,
                sources=srcs,
                confidences=dict(o.confidences),
                overall_confidence=o.overall_confidence,
                metadata=dict(o.metadata)
            )
            all_obs_map[t_key] = obs_copy

        # 3. Sort chronologically
        sorted_keys = sorted(all_obs_map.keys())
        for idx, k in enumerate(sorted_keys):
            o = all_obs_map[k]
            obs_indexed = Observation(
                timestamp_sec=o.timestamp_sec,
                frame_index=idx,
                stage_text=o.stage_text,
                gold_val=o.gold_val,
                hp_val=o.hp_val,
                level_val=o.level_val,
                xp_val=o.xp_val,
                shop_cards=o.shop_cards,
                field_detections=o.field_detections,
                bench_detections=o.bench_detections,
                sources=o.sources,
                confidences=o.confidences,
                overall_confidence=o.overall_confidence,
                metadata=o.metadata
            )
            merged_timeline.add_observation(obs_indexed)

        return merged_timeline
