"""Observation and Event Timeline models -- Event Sourcing architecture."""
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from tft.vision.observation import Observation, CardObservation, UnitObservation
from tft.vision.events import ActionEvent, VisionActionType, ActionSource, QualityFlag


@dataclass
class TimelineEvent:
    """타임라인 내의 일반 이벤트 기록."""
    timestamp_sec: float
    event_type: str
    confidence: float = 1.0
    evidence: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ObservationTimeline:
    """전체 게임 영상에 걸친 시계열 관측 및 행동 이벤트 타임라인 (Event Sourcing Container)."""
    video_path: Optional[str] = None
    duration_sec: float = 0.0
    fps: float = 0.0
    total_frames_processed: int = 0
    observations: List[Observation] = field(default_factory=list)
    events: List[ActionEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_observation(self, obs: Observation) -> None:
        """관측 추가 (시간순 정렬 유지)."""
        if self.observations and obs.timestamp_sec < self.observations[-1].timestamp_sec:
            # Insert maintaining order
            self.observations.append(obs)
            self.observations.sort(key=lambda o: (o.timestamp_sec, o.frame_index))
        else:
            self.observations.append(obs)
        if obs.timestamp_sec > self.duration_sec:
            self.duration_sec = obs.timestamp_sec

    def add_event(self, event: ActionEvent) -> None:
        """행동 이벤트 추가 (시간순 정렬 유지)."""
        if self.events and event.timestamp_sec < self.events[-1].timestamp_sec:
            self.events.append(event)
            self.events.sort(key=lambda e: (e.timestamp_sec, e.action_type.value))
        else:
            self.events.append(event)

    def get_observations_in_window(self, start_sec: float, end_sec: float) -> List[Observation]:
        """특정 시간 윈도우 [start_sec, end_sec] 내의 관측값 목록 반환."""
        return [o for o in self.observations if start_sec <= o.timestamp_sec <= end_sec]

    def get_latest_observation_at(self, timestamp_sec: float) -> Optional[Observation]:
        """주어진 시점(timestamp_sec) 이하에서 가장 최근 관측값 반환 (Causal, No Future Lookahead)."""
        candidates = [o for o in self.observations if o.timestamp_sec <= timestamp_sec]
        return candidates[-1] if candidates else None

    def get_events_in_window(self, start_sec: float, end_sec: float) -> List[ActionEvent]:
        """특정 시간 윈도우 [start_sec, end_sec] 내의 행동 이벤트 목록 반환."""
        return [e for e in self.events if start_sec <= e.timestamp_sec <= end_sec]

    def validate_temporal_monotonicity(self) -> Tuple[bool, List[str]]:
        """시계열 타임스탬프 단조 증가(Monotonicity) 검증."""
        violations = []
        for i in range(1, len(self.observations)):
            prev_t = self.observations[i - 1].timestamp_sec
            curr_t = self.observations[i].timestamp_sec
            if curr_t < prev_t:
                violations.append(f"Observation timestamp inversion at index {i}: {prev_t:.2f}s -> {curr_t:.2f}s")

        for i in range(1, len(self.events)):
            prev_t = self.events[i - 1].timestamp_sec
            curr_t = self.events[i].timestamp_sec
            if curr_t < prev_t:
                violations.append(f"Event timestamp inversion at index {i}: {prev_t:.2f}s -> {curr_t:.2f}s")

        return len(violations) == 0, violations

    def to_dict(self) -> Dict[str, Any]:
        """직렬화 가능한 딕셔너리로 변환."""
        return {
            "video_path": self.video_path,
            "duration_sec": self.duration_sec,
            "fps": self.fps,
            "total_frames_processed": len(self.observations),
            "observations_count": len(self.observations),
            "events_count": len(self.events),
            "observations": [
                {
                    "timestamp_sec": o.timestamp_sec,
                    "frame_index": o.frame_index,
                    "stage_text": o.stage_text,
                    "gold_val": o.gold_val,
                    "hp_val": o.hp_val,
                    "level_val": o.level_val,
                    "xp_val": o.xp_val,
                    "shop_cards": [
                        {
                            "slot_index": c.slot_index,
                            "champion_pred": c.champion_pred,
                            "cost_pred": c.cost_pred,
                            "confidence": c.confidence,
                            "is_empty": c.is_empty,
                            "raw_ocr": c.raw_ocr
                        }
                        for c in o.shop_cards
                    ],
                    "field_detections": [
                        {
                            "location": u.location,
                            "champion_pred": u.champion_pred,
                            "star_level_pred": u.star_level_pred,
                            "items_pred": u.items_pred,
                            "confidence": u.confidence
                        }
                        for u in o.field_detections
                    ],
                    "bench_detections": [
                        {
                            "location": u.location,
                            "champion_pred": u.champion_pred,
                            "star_level_pred": u.star_level_pred,
                            "items_pred": u.items_pred,
                            "confidence": u.confidence
                        }
                        for u in o.bench_detections
                    ],
                    "sources": o.sources,
                    "overall_confidence": o.overall_confidence
                }
                for o in self.observations
            ],
            "events": [
                {
                    "action_type": e.action_type.value,
                    "source": e.source.value,
                    "timestamp_sec": e.timestamp_sec,
                    "confidence": e.confidence,
                    "evidence": e.evidence,
                    "evidence_data": e.evidence_data,
                    "quality_flag": e.quality_flag.value,
                    "target_champion": e.target_champion,
                    "slot_index": e.slot_index
                }
                for e in self.events
            ],
            "metadata": self.metadata
        }
