"""Vision Action Event models -- explicit ActionSource, structured evidence, and quality flags."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class VisionActionType(str, Enum):
    """비전 파이프라인에서 탐지 및 추론 가능한 행동 이벤트 유형."""
    ROLL = "ROLL"
    BUY_UNIT = "BUY_UNIT"
    SELL_UNIT = "SELL_UNIT"
    LEVEL_UP = "LEVEL_UP"
    BUY_XP = "BUY_XP"
    SAVE_GOLD = "SAVE_GOLD"
    ITEM_COMBINE = "ITEM_COMBINE"
    AUGMENT_SELECT = "AUGMENT_SELECT"
    POSITION_CHANGE = "POSITION_CHANGE"
    UNKNOWN = "UNKNOWN"


class ActionSource(str, Enum):
    """행동 이벤트의 생성 출처.

    OBSERVED: 화면 변화(상점 변경, 골드 감소, 유닛 이동)로부터 직접 탐지된 행동.
    INFERRED: 특정 의사결정 윈도우 동안 경제 행동이 없음을 근거로 추론된 행동 (e.g. SAVE_GOLD).
    UNKNOWN: 관측 신뢰도가 낮거나 행동 여부가 불분명한 상태.
    """
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class QualityFlag(str, Enum):
    """데이터 품질 및 검증 상태 플래그."""
    VALID = "VALID"              # 상태, 행동, 결과 모두 검증됨
    PARTIAL = "PARTIAL"          # 상태와 행동만 검증됨 (미래 결과 미확인)
    UNVERIFIED = "UNVERIFIED"    # 경기 ID 또는 영상 식별자가 미확인됨
    INVALID = "INVALID"          # 시계열 모순 또는 상태 무효 검출


@dataclass(frozen=True)
class ActionEvent:
    """시간축 상에 기록되는 개별 행동 이벤트 (Event Sourcing Entity).

    주의: confidence는 CV 탐지 신뢰도(Detection Confidence)를 나타내며,
    해당 행동이 전략적으로 옳았을 확률(Strategic Correctness)이 아니다.
    """
    action_type: VisionActionType
    source: ActionSource
    timestamp_sec: float
    confidence: float = 1.0
    evidence: List[str] = field(default_factory=list)
    evidence_data: Dict[str, Any] = field(default_factory=dict)
    quality_flag: QualityFlag = QualityFlag.VALID
    target_champion: Optional[str] = None
    slot_index: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
