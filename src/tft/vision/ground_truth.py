"""Ground Truth Data Models and Dataset Loader for TFT Vision Audit -- v1.0."""
import json
import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class GroundTruthActionType(str, Enum):
    """사람이 화면에서 직접 확인하여 라벨링하는 참값(Ground Truth) 행동 유형."""
    ROLL = "ROLL"
    BUY_UNIT = "BUY_UNIT"
    SELL_UNIT = "SELL_UNIT"
    LEVEL_UP = "LEVEL_UP"
    BUY_XP = "BUY_XP"
    NO_OBSERVED_ECONOMIC_ACTION = "NO_OBSERVED_ECONOMIC_ACTION"  # 골드 저축 및 대기
    ITEM_COMBINE = "ITEM_COMBINE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class GroundTruthEvent:
    """사람에 의해 검증된 개별 사건 (Ground Truth Event).

    주의: CV가 'ROLL'이라고 판정했다고 해서 실제 ROLL로 기록하지 않는다.
    실제 상점 리롤 애니메이션, 상점 카드 갱신, 골드 차감 상호작용이
    인간 검증자에 의해 육안으로 확인된 경우에만 기록한다.
    """
    session_id: str
    timestamp_sec: float
    event_type: GroundTruthActionType
    target_champion: Optional[str] = None
    slot_index: Optional[int] = None
    gold_before: Optional[int] = None
    gold_after: Optional[int] = None
    annotator_id: str = "human_annotator_1"
    evidence_observed: List[str] = field(default_factory=list)
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GroundTruthCard:
    """상점 단일 슬롯의 인간 검증 정답."""
    slot_index: int  # 0 to 4
    champion_name: Optional[str]  # None if EMPTY
    cost: Optional[int]
    is_empty: bool = False


@dataclass(frozen=True)
class GroundTruthObservation:
    """특정 타임스탬프에서 인간 검증자가 확인한 화면 상태 정답."""
    timestamp_sec: float
    stage_round: Optional[str] = None  # e.g. "3-2"
    gold: Optional[int] = None
    hp: Optional[int] = None
    level: Optional[int] = None
    shop_cards: List[GroundTruthCard] = field(default_factory=list)
    is_in_combat: bool = False
    annotator_id: str = "human_annotator_1"
    notes: str = ""


@dataclass
class GroundTruthDataset:
    """단일 게임 세션에 대한 종합 Ground Truth 데이터셋."""
    session_id: str
    video_path: str
    duration_sec: float
    annotator_ids: List[str] = field(default_factory=lambda: ["human_annotator_1"])
    events: List[GroundTruthEvent] = field(default_factory=list)
    observations: List[GroundTruthObservation] = field(default_factory=list)
    double_annotations: Dict[str, List[GroundTruthEvent]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate_integrity(self) -> Tuple[bool, List[str]]:
        """타임스탬프 유효성 및 단조성 검증."""
        issues = []
        if self.duration_sec <= 0:
            issues.append(f"Invalid dataset duration: {self.duration_sec}")

        for i, ev in enumerate(self.events):
            if ev.timestamp_sec < 0 or ev.timestamp_sec > self.duration_sec:
                issues.append(f"Event {i} timestamp out of range: {ev.timestamp_sec}s (Duration: {self.duration_sec}s)")

        for i, obs in enumerate(self.observations):
            if obs.timestamp_sec < 0 or obs.timestamp_sec > self.duration_sec:
                issues.append(f"Observation {i} timestamp out of range: {obs.timestamp_sec}s")

        return len(issues) == 0, issues

    @classmethod
    def load_from_json(cls, json_path: str) -> "GroundTruthDataset":
        """JSON 파일로부터 GroundTruthDataset 로드."""
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Ground truth file not found: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        events: List[GroundTruthEvent] = []
        for e in data.get("events", []):
            etype_str = e.get("event_type", "UNKNOWN")
            etype = GroundTruthActionType(etype_str) if etype_str in [x.value for x in GroundTruthActionType] else GroundTruthActionType.UNKNOWN
            events.append(GroundTruthEvent(
                session_id=data.get("session_id", "SESSION_01"),
                timestamp_sec=float(e.get("timestamp_sec", 0.0)),
                event_type=etype,
                target_champion=e.get("target_champion"),
                slot_index=e.get("slot_index"),
                gold_before=e.get("gold_before"),
                gold_after=e.get("gold_after"),
                annotator_id=e.get("annotator_id", "human_annotator_1"),
                evidence_observed=e.get("evidence_observed", []),
                notes=e.get("notes", ""),
                metadata=e.get("metadata", {})
            ))

        # Sort events chronologically
        events.sort(key=lambda x: x.timestamp_sec)

        observations: List[GroundTruthObservation] = []
        for o in data.get("observations", []):
            cards: List[GroundTruthCard] = []
            for c in o.get("shop_cards", []):
                cards.append(GroundTruthCard(
                    slot_index=int(c.get("slot_index", 0)),
                    champion_name=c.get("champion_name"),
                    cost=c.get("cost"),
                    is_empty=bool(c.get("is_empty", False))
                ))
            observations.append(GroundTruthObservation(
                timestamp_sec=float(o.get("timestamp_sec", 0.0)),
                stage_round=o.get("stage_round"),
                gold=o.get("gold"),
                hp=o.get("hp"),
                level=o.get("level"),
                shop_cards=cards,
                is_in_combat=bool(o.get("is_in_combat", False)),
                annotator_id=o.get("annotator_id", "human_annotator_1"),
                notes=o.get("notes", "")
            ))

        observations.sort(key=lambda x: x.timestamp_sec)

        double_ann = {}
        for ann_id, ev_list in data.get("double_annotations", {}).items():
            parsed_list = []
            for e in ev_list:
                etype_str = e.get("event_type", "UNKNOWN")
                etype = GroundTruthActionType(etype_str) if etype_str in [x.value for x in GroundTruthActionType] else GroundTruthActionType.UNKNOWN
                parsed_list.append(GroundTruthEvent(
                    session_id=data.get("session_id", "SESSION_01"),
                    timestamp_sec=float(e.get("timestamp_sec", 0.0)),
                    event_type=etype,
                    target_champion=e.get("target_champion"),
                    annotator_id=ann_id,
                    evidence_observed=e.get("evidence_observed", []),
                    notes=e.get("notes", "")
                ))
            double_ann[ann_id] = parsed_list

        ds = cls(
            session_id=data.get("session_id", "SESSION_01"),
            video_path=data.get("video_path", ""),
            duration_sec=float(data.get("duration_sec", 900.0)),
            annotator_ids=data.get("annotator_ids", ["human_annotator_1"]),
            events=events,
            observations=observations,
            double_annotations=double_ann,
            metadata=data.get("metadata", {})
        )

        ok, issues = ds.validate_integrity()
        if not ok:
            raise ValueError(f"GroundTruth dataset validation failed: {'; '.join(issues)}")

        return ds
