"""Causal GameState Reconstruction from Observation Timeline -- strictly forward-only smoothing."""
from typing import Any, Dict, List, Optional, Tuple
from tft.domain.game_state import GameState, PlayerState
from tft.vision.observation import Observation
from tft.vision.timeline import ObservationTimeline
from tft.vision.adapters import ObservationToGameStateBuilder


class GameStateReconstructor:
    """Observation 시계열로부터 미래 정보 누수 없이 도메인 GameState 타임라인을 재구성."""

    def __init__(self, builder: Optional[ObservationToGameStateBuilder] = None):
        self.builder = builder or ObservationToGameStateBuilder()

    def reconstruct_timeline(
        self,
        timeline: ObservationTimeline
    ) -> List[Tuple[float, GameState]]:
        """타임라인의 관측값들을 순방향(Causal Forward-Only)으로만 처리하여 GameState 시계열 생성.

        규칙:
          - 절대 미래 Observation을 참조하여 과거 GameState를 수정(Hindsight)하지 않는다.
          - 순간적 OCR 결손(1프레임 튐)은 직전 유효 상태 기반 순방향 디바운싱(Forward-only debounce)을 적용한다.
          - 레벨 및 스테이지는 순방향 단조 증가(Monotonically non-decreasing) 도메인 제약을 적용한다.
        """
        reconstructed: List[Tuple[float, GameState]] = []
        current_state: Optional[GameState] = None

        # State tracking buffers for online forward smoothing
        last_valid_gold: int = 0
        last_valid_level: int = 1
        last_valid_hp: int = 100
        last_valid_stage: int = 2
        last_valid_round: int = 1

        for obs in timeline.observations:
            t = obs.timestamp_sec

            # 1. Forward-only Gold Debounce:
            # If gold is None or sudden unplausible single-frame drop without action, carry forward
            if obs.gold_val is not None and 0 <= obs.gold_val <= 200:
                gold = obs.gold_val
                last_valid_gold = gold
            else:
                gold = last_valid_gold

            # 2. Forward-only Level Monotonicity:
            # Level cannot decrease during game
            if obs.level_val is not None and 1 <= obs.level_val <= 11:
                level = max(last_valid_level, obs.level_val)
                last_valid_level = level
            else:
                level = last_valid_level

            # 3. Forward-only HP:
            if obs.hp_val is not None and 0 <= obs.hp_val <= 100:
                hp = obs.hp_val
                last_valid_hp = hp
            else:
                hp = last_valid_hp

            # 4. Stage-Round Parsing & Monotonicity:
            stage_text = obs.stage_text
            if stage_text:
                import re
                m = re.search(r"(\d)[-~_](\d)", stage_text)
                if m:
                    stg, rnd = int(m.group(1)), int(m.group(2))
                    if stg > last_valid_stage or (stg == last_valid_stage and rnd >= last_valid_round):
                        last_valid_stage, last_valid_round = stg, rnd
            
            stage_round_str = f"{last_valid_stage}-{last_valid_round}"

            # Create smoothed observation for builder
            smoothed_obs = Observation(
                timestamp_sec=t,
                frame_index=obs.frame_index,
                stage_text=stage_round_str,
                gold_val=gold,
                hp_val=hp,
                level_val=level,
                xp_val=obs.xp_val,
                shop_cards=obs.shop_cards,
                field_detections=obs.field_detections,
                bench_detections=obs.bench_detections,
                sources=obs.sources,
                confidences=obs.confidences,
                overall_confidence=obs.overall_confidence,
                metadata=obs.metadata
            )

            # Build GameState using strictly past/current state
            state = self.builder.build(smoothed_obs, fallback_state=current_state)
            current_state = state
            reconstructed.append((t, state))

        return reconstructed

    def get_state_at(
        self,
        reconstructed_timeline: List[Tuple[float, GameState]],
        timestamp_sec: float
    ) -> Optional[GameState]:
        """지정된 시점(timestamp_sec) 이하에서 가장 최신의 유효 GameState 반환."""
        candidates = [st for t, st in reconstructed_timeline if t <= timestamp_sec]
        return candidates[-1] if candidates else None
