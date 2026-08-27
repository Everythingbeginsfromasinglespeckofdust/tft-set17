"""Adaptive Candidate Refiner and Event Clusterer for TFT Video Replay Validation v1.1.

Refines coarse candidate windows (T - 1.0s to T + 1.0s) at higher temporal resolution,
clusters consecutive transitions into unique discrete events, and selects representative
timestamps with target coverage across:
- ROLL
- BUY_UNIT
- LEVEL_UP
- SYSTEM_REFRESH
- NO_ACTION
- BOARD_CHANGE
- GOLD_CHANGE
"""
from __future__ import annotations
import json
import math
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from tft.vision.video_replay.coarse_discovery import CoarseCandidateEvent


@dataclass
class RefinedEventWindow:
    event_id: str
    primary_type: str
    secondary_types: List[str]
    timestamp_center: float
    start_sec: float
    end_sec: float
    duration_sec: float
    frame_count: int
    gold_delta: Optional[int] = None
    shop_slots_changed: int = 0
    shop_slots_emptied: int = 0
    board_units_changed: int = 0
    confidence: float = 0.85
    cluster_size: int = 1
    representative_frame_idx: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AdaptiveCandidateRefiner:
    """Refines and clusters candidate event windows."""

    def __init__(
        self,
        video_path: str,
        refine_fps: float = 20.0,
        cluster_window_sec: float = 2.5,
    ):
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")
        self.video_path = video_path
        self.refine_fps = refine_fps
        self.cluster_window_sec = cluster_window_sec

        cap = cv2.VideoCapture(video_path)
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration_sec = self.total_frames / max(1.0, self.fps)
        cap.release()

    def cluster_candidates(
        self,
        candidates: List[CoarseCandidateEvent]
    ) -> List[RefinedEventWindow]:
        """Cluster coarse candidates within cluster_window_sec into distinct event windows."""
        if not candidates:
            return []

        # Sort by timestamp
        sorted_cands = sorted(candidates, key=lambda c: c.timestamp_sec)
        clusters: List[List[CoarseCandidateEvent]] = []
        current_cluster: List[CoarseCandidateEvent] = [sorted_cands[0]]

        for cand in sorted_cands[1:]:
            last_t = current_cluster[-1].timestamp_sec
            if cand.timestamp_sec - last_t <= self.cluster_window_sec:
                current_cluster.append(cand)
            else:
                clusters.append(current_cluster)
                current_cluster = [cand]
        if current_cluster:
            clusters.append(current_cluster)

        refined_events: List[RefinedEventWindow] = []
        for idx, cluster in enumerate(clusters):
            # Aggregate types
            all_types: List[str] = []
            for c in cluster:
                for t in c.candidate_types:
                    if t not in all_types:
                        all_types.append(t)

            # Determine primary type
            # Priority: ROLL > BUY_UNIT > SYSTEM_REFRESH > LEVEL_UP > BOARD_CHANGE > GOLD_CHANGE > NO_ACTION
            priority = ["ROLL", "BUY_UNIT", "SYSTEM_REFRESH", "LEVEL_UP", "BOARD_CHANGE", "GOLD_CHANGE", "NO_ACTION"]
            primary = "NO_ACTION"
            for p in priority:
                if p in all_types:
                    primary = p
                    break

            secondaries = [t for t in all_types if t != primary]

            # Pick peak timestamp (candidate with highest change score)
            best_cand = max(cluster, key=lambda c: c.shop_change_score + c.gold_change_score + c.board_change_score)
            t_center = best_cand.timestamp_sec
            t_start = max(0.0, cluster[0].timestamp_sec - 0.5)
            t_end = min(self.duration_sec, cluster[-1].timestamp_sec + 0.5)

            event_id = f"EVT_{idx:04d}_{primary}_{int(t_center)}S"
            refined_events.append(RefinedEventWindow(
                event_id=event_id,
                primary_type=primary,
                secondary_types=secondaries,
                timestamp_center=round(t_center, 2),
                start_sec=round(t_start, 2),
                end_sec=round(t_end, 2),
                duration_sec=round(t_end - t_start, 2),
                frame_count=int((t_end - t_start) * self.fps),
                cluster_size=len(cluster),
                representative_frame_idx=best_cand.frame_index,
                metadata={
                    "stage_est": best_cand.estimated_stage,
                    "max_shop_diff": best_cand.shop_change_score,
                    "max_gold_diff": best_cand.gold_change_score,
                    "max_board_diff": best_cand.board_change_score,
                }
            ))

        return refined_events

    def select_stratified_sample(
        self,
        refined_events: List[RefinedEventWindow],
        target_count: int = 25,
    ) -> List[RefinedEventWindow]:
        """Select an event-stratified subset of candidates."""
        by_type: Dict[str, List[RefinedEventWindow]] = {}
        for ev in refined_events:
            by_type.setdefault(ev.primary_type, []).append(ev)

        # Target allocations
        targets = {
            "ROLL": 7,
            "BUY_UNIT": 5,
            "SYSTEM_REFRESH": 3,
            "LEVEL_UP": 2,
            "BOARD_CHANGE": 3,
            "GOLD_CHANGE": 3,
            "NO_ACTION": 4,
        }

        selected: List[RefinedEventWindow] = []
        for event_type, desired in targets.items():
            pool = by_type.get(event_type, [])
            # Spread selections evenly across time if multiple available
            if len(pool) <= desired:
                selected.extend(pool)
            else:
                step = len(pool) / float(desired)
                for i in range(desired):
                    idx = int(i * step)
                    selected.append(pool[min(idx, len(pool) - 1)])

        # If still under target_count, backfill from remaining
        selected_ids = set(s.event_id for s in selected)
        remaining = [e for e in refined_events if e.event_id not in selected_ids]
        for e in remaining:
            if len(selected) >= target_count:
                break
            selected.append(e)

        # Sort chronologically
        selected.sort(key=lambda e: e.timestamp_center)
        return selected[:target_count]


def refine_video_candidates(
    video_path: str,
    candidates_jsonl: str,
    output_dir: str,
    target_count: int = 25
) -> Dict[str, Any]:
    """Refine candidates and write refined_windows.jsonl and stratified_selection.jsonl."""
    os.makedirs(output_dir, exist_ok=True)
    if not os.path.exists(candidates_jsonl):
        raise FileNotFoundError(f"Candidates file not found: {candidates_jsonl}")

    # Load candidates
    candidates: List[CoarseCandidateEvent] = []
    with open(candidates_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            candidates.append(CoarseCandidateEvent(**data))

    refiner = AdaptiveCandidateRefiner(video_path)
    all_refined = refiner.cluster_candidates(candidates)
    stratified = refiner.select_stratified_sample(all_refined, target_count=target_count)

    # Save all refined windows
    refined_jsonl = os.path.join(output_dir, "refined_windows.jsonl")
    with open(refined_jsonl, "w", encoding="utf-8") as f:
        for ev in all_refined:
            f.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")

    # Save stratified selection
    strat_jsonl = os.path.join(output_dir, "stratified_selection.jsonl")
    with open(strat_jsonl, "w", encoding="utf-8") as f:
        for ev in stratified:
            f.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")

    # Distribution summary
    dist: Dict[str, int] = {}
    for s in stratified:
        dist[s.primary_type] = dist.get(s.primary_type, 0) + 1

    summary = {
        "video_path": video_path,
        "total_coarse_candidates": len(candidates),
        "total_clustered_events": len(all_refined),
        "total_stratified_selected": len(stratified),
        "stratified_distribution": dist,
        "stratified_selection_jsonl": strat_jsonl,
    }

    sum_path = os.path.join(output_dir, "refinement_summary.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return summary
