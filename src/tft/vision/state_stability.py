"""TFT State Stability & Animation Filter: Distinguishes stable game states from transient animation frames."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from tft.vision.observation import Observation, CardObservation


class StabilityStatus(str, Enum):
    """관측 시점의 화면 안정성 상태."""
    STABLE = "STABLE"                   # 안정적인 상점/보드 상태 (행동 판정 신뢰 가능)
    UNSTABLE_ANIMATION = "UNSTABLE"     # 리롤/전환 애니메이션 진행 중 (중간 상태)
    UI_CLOSED = "UI_CLOSED"             # 상점 UI가 닫힘
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class StabilityAssessment:
    """단일 Observation의 안정성 평가 결과."""
    status: StabilityStatus
    is_stable: bool
    confidence_mean: float
    empty_slot_count: int
    unrecognized_slot_count: int
    is_shop_animation: bool
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "is_stable": self.is_stable,
            "confidence_mean": round(self.confidence_mean, 3),
            "empty_slot_count": self.empty_slot_count,
            "unrecognized_slot_count": self.unrecognized_slot_count,
            "is_shop_animation": self.is_shop_animation,
            "reasons": self.reasons
        }


class StateStabilityAnalyzer:
    """상점 카드 및 UI의 안정성을 진단하는 분석기."""

    def __init__(self, min_stable_confidence: float = 0.20):
        self.min_stable_confidence = min_stable_confidence

    def assess_observation(self, obs: Observation, prev_obs: Optional[Observation] = None) -> StabilityAssessment:
        """단일 Observation의 안정성을 평가."""
        reasons: List[str] = []
        if not obs.shop_cards or len(obs.shop_cards) < 5:
            return StabilityAssessment(
                status=StabilityStatus.UI_CLOSED,
                is_stable=False,
                confidence_mean=0.0,
                empty_slot_count=5,
                unrecognized_slot_count=0,
                is_shop_animation=False,
                reasons=["Shop UI closed or less than 5 slots detected"]
            )

        conf_list = [c.confidence for c in obs.shop_cards if not c.is_empty]
        mean_conf = float(np.mean(conf_list)) if conf_list else 0.0
        empty_count = sum(1 for c in obs.shop_cards if c.is_empty)
        unrec_count = sum(1 for c in obs.shop_cards if not c.is_empty and not c.champion_pred)

        # 1. Check for transient Shop Animation
        # In-flight wipe pattern: multiple slots (2 to 4) suddenly became empty without player purchase evidence,
        # or cards are midway in sliding motion with low confidence
        is_animation = False
        if prev_obs is not None and prev_obs.shop_cards:
            prev_empty = sum(1 for c in prev_obs.shop_cards if c.is_empty)
            # If empty slots jumped from 0 to 3+ in 0.5s with no bench addition -> transient animation frame
            if empty_count >= 2 and prev_empty == 0 and not obs.bench_detections:
                is_animation = True
                reasons.append(f"Transient card wipe: {empty_count} slots empty during reroll transition")

        if unrec_count >= 2:
            is_animation = True
            reasons.append(f"Multiple unrecognized card portraits ({unrec_count}/5)")

        if mean_conf < self.min_stable_confidence and not (empty_count == 5):
            is_animation = True
            reasons.append(f"Low average recognition confidence ({mean_conf:.2f} < {self.min_stable_confidence:.2f})")

        is_stable = not is_animation
        status = StabilityStatus.STABLE if is_stable else StabilityStatus.UNSTABLE_ANIMATION

        return StabilityAssessment(
            status=status,
            is_stable=is_stable,
            confidence_mean=mean_conf,
            empty_slot_count=empty_count,
            unrecognized_slot_count=unrec_count,
            is_shop_animation=is_animation,
            reasons=reasons
        )
