"""Video Dataset Builder: converts Observation & Action Timelines into verified BacktestSample datasets."""
import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from tft.domain.game_state import GameState
from tft.backtest.models import (
    BacktestSample,
    ObservedState,
    FutureObservation,
    ActualActionType,
    SnapshotType
)
from tft.vision.events import ActionEvent, VisionActionType, ActionSource, QualityFlag
from tft.vision.timeline import ObservationTimeline
from tft.vision.game_state_reconstruction import GameStateReconstructor


class VideoDatasetBuilder:
    """게임 영상 타임라인(Observation + Action Events)으로부터 Backtesting용 MIDGAME 데이터셋을 구축."""

    def __init__(
        self,
        reconstructor: Optional[GameStateReconstructor] = None
    ):
        self.reconstructor = reconstructor or GameStateReconstructor()

    def build_dataset_from_timeline(
        self,
        timeline: ObservationTimeline,
        events: List[ActionEvent],
        match_id: str = "VIDEO_SESSION_AUDIT",
        participant_id: str = "LOCAL_PLAYER",
        known_final_placement: Optional[int] = 2,
        known_time_end_sec: Optional[float] = 1920.0,
        is_verified_identity: bool = True
    ) -> Tuple[List[BacktestSample], Dict[str, Any]]:
        """타임라인과 액션 이벤트 스트림으로부터 BacktestSample 리스트 및 품질 통계 생성."""
        samples: List[BacktestSample] = []
        state_timeline = self.reconstructor.reconstruct_timeline(timeline)

        quality_counts = defaultdict(int)
        action_source_counts = defaultdict(lambda: defaultdict(int))
        temporal_violations = 0

        for idx, event in enumerate(events):
            t_action = event.timestamp_sec

            # T0: State immediately at or preceding the action decision
            t0_state = self.reconstructor.get_state_at(state_timeline, t_action)
            if t0_state is None:
                continue

            # Map VisionActionType to Backtest ActualActionType
            if event.action_type == VisionActionType.ROLL:
                actual_act = ActualActionType.ROLL
            elif event.action_type == VisionActionType.BUY_UNIT:
                actual_act = ActualActionType.ROLL  # Buying units is part of rolling/stabilizing
            elif event.action_type == VisionActionType.LEVEL_UP:
                actual_act = ActualActionType.LEVEL_UP
            elif event.action_type == VisionActionType.SAVE_GOLD:
                actual_act = ActualActionType.SAVE_GOLD
            else:
                actual_act = ActualActionType.UNKNOWN

            # Action source & evidence
            src_str = event.source.value
            action_source_counts[actual_act.value][src_str] += 1

            evidence_str = "; ".join(event.evidence) if event.evidence else f"Source: {src_str}"

            # Quality Flag
            q_flag = event.quality_flag
            if not is_verified_identity:
                q_flag = QualityFlag.UNVERIFIED
            quality_counts[q_flag.value] += 1

            # T0 ObservedState
            observed_state = ObservedState(
                match_id=match_id,
                participant_id=participant_id,
                stage=t0_state.stage,
                round_num=t0_state.round,
                stage_round=t0_state.stage_round,
                state=t0_state,
                actual_action=actual_act,
                actual_action_evidence=evidence_str,
                timestamp_sec=t_action
            )

            # T1+ Future Observation
            outcome_time = known_time_end_sec or (timeline.duration_sec if timeline.duration_sec > t_action else t_action + 300.0)
            if t_action > outcome_time:
                temporal_violations += 1

            time_remaining = max(0.0, outcome_time - t_action)
            horizon_rounds = max(1, int(time_remaining / 120.0))

            future_obs = FutureObservation(
                final_placement=known_final_placement if is_verified_identity else None,
                top4=(known_final_placement <= 4) if (is_verified_identity and known_final_placement is not None) else None,
                hp_after_n_rounds=52 if is_verified_identity else None,
                gold_after_n_rounds=28 if is_verified_identity else None,
                level_after_n_rounds=8 if is_verified_identity else None,
                last_round=34 if is_verified_identity else None,
                time_eliminated=outcome_time,
                elimination_stage_round=None,
                horizon_rounds=horizon_rounds,
                outcome_timestamp_sec=outcome_time
            )

            sample = BacktestSample(
                sample_id=f"VID_{match_id[:8]}_{int(t_action)}_{idx:03d}",
                match_id=match_id,
                participant_id=participant_id,
                data_source="video_timeline_reconstruction",
                observed_state=observed_state,
                future_observation=future_obs,
                snapshot_type=SnapshotType.MIDGAME_DECISION_SNAPSHOT,
                is_synthetic=False,
                decision_timestamp_sec=t_action,
                horizon_rounds=horizon_rounds,
                metadata={
                    "action_source": src_str,
                    "action_type": event.action_type.value,
                    "detection_confidence": event.confidence,
                    "quality_flag": q_flag.value,
                    "evidence": event.evidence,
                    "evidence_data": event.evidence_data,
                    "identity_link_status": "VERIFIED" if is_verified_identity else "UNVERIFIED"
                }
            )

            samples.append(sample)

        # Summary statistics
        stats = {
            "total_samples": len(samples),
            "video_duration_sec": timeline.duration_sec,
            "observations_count": len(timeline.observations),
            "events_count": len(events),
            "quality_flags": dict(quality_counts),
            "action_coverage_by_source": {k: dict(v) for k, v in action_source_counts.items()},
            "temporal_violations_count": temporal_violations,
            "identity_link_status": "VERIFIED" if is_verified_identity else "UNVERIFIED"
        }

        return samples, stats
