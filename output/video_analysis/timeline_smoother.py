#!/usr/bin/env python3
"""TFT Set 17 타임라인 시계열 스무더 (Timeline Smoother).

주요 기능:
1. 라운드 전환 애니메이션 및 일시적 OCR 빈값(None/"") 보정: 직전 유효 상태 유지
2. 상태 전이 단조성 제약(Monotonic State Transition):
   - 스테이지-라운드는 역행 불가 (예: 2-5 도달 후 순간적 2-1 노이즈 무시)
   - 정상 전이 (2-1 -> 2-2 -> 2-3 -> 2-4 -> 2-5 -> 2-6 -> 2-7 -> 3-1 ...)
3. 골드 및 레벨 급변 노이즈 완화 (0~200 범위 및 연속성 보정)
4. 배치 유닛 일시적 가림(애니메이션/스킬 파티클) 깜빡임 완화
"""
import copy
import re
from typing import Any, Dict, List, Optional, Tuple


def parse_stage_order(stage_str: Optional[str]) -> Optional[int]:
    """'2-1' 형식 문자열을 비교 가능한 정수 순서값으로 변환 (예: '2-1' -> 21, '3-5' -> 35)."""
    if not stage_str or not isinstance(stage_str, str):
        return None
    m = re.match(r"^(\d+)-(\d+)$", stage_str.strip())
    if not m:
        return None
    stage, round_num = int(m.group(1)), int(m.group(2))
    return stage * 10 + round_num


def format_stage_order(val: int) -> str:
    """정수 순서값을 '2-1' 형식 문자열로 변환."""
    stage = val // 10
    round_num = val % 10
    return f"{stage}-{round_num}"


class TimelineSmoother:
    """비디오 프레임 단위 비전 인식 결과를 시간축 상에서 정제하는 스무더."""

    def __init__(self, stage_confirm_threshold: int = 2):
        self.stage_confirm_threshold = stage_confirm_threshold
        self.current_stage: Optional[str] = None
        self.current_stage_order: Optional[int] = None
        self.candidate_stage: Optional[str] = None
        self.candidate_count: int = 0

        self.current_gold: Optional[int] = None
        self.current_level: int = 1
        self.current_field_units: List[Dict[str, Any]] = []

    def reset(self):
        """상태 초기화."""
        self.current_stage = None
        self.current_stage_order = None
        self.candidate_stage = None
        self.candidate_count = 0
        self.current_gold = None
        self.current_level = 1
        self.current_field_units = []

    def smooth_stage_round(self, raw_stage: Optional[str]) -> Optional[str]:
        """스테이지-라운드 상태 전이 규칙 적용 및 빈값/노이즈 보정."""
        if not raw_stage:
            # 빈값이면 직전 유효값 유지
            return self.current_stage

        raw_order = parse_stage_order(raw_stage)
        if raw_order is None:
            return self.current_stage

        # 최초 감지
        if self.current_stage is None:
            self.current_stage = raw_stage
            self.current_stage_order = raw_order
            return self.current_stage

        # 동일한 스테이지 감지
        if raw_order == self.current_stage_order:
            self.candidate_stage = None
            self.candidate_count = 0
            return self.current_stage

        # 전진 전이 (순방향): 정상 라운드 진행 (예: 21 -> 22, 27 -> 31)
        if raw_order > self.current_stage_order:
            # 허용 가능한 전이 범위 내 (스테이지 점프 <= 1개 스테이지)
            diff = raw_order - self.current_stage_order
            if diff <= 11:  # 예: 21 -> 22 (+1) 또는 27 -> 31 (+4)
                self.current_stage = raw_stage
                self.current_stage_order = raw_order
                self.candidate_stage = None
                self.candidate_count = 0
                return self.current_stage
            else:
                # 너무 큰 비정상 점프일 경우 후보로 등록 후 연속 감지 시 확인
                if self.candidate_stage == raw_stage:
                    self.candidate_count += 1
                    if self.candidate_count >= self.stage_confirm_threshold:
                        self.current_stage = raw_stage
                        self.current_stage_order = raw_order
                        self.candidate_stage = None
                        self.candidate_count = 0
                else:
                    self.candidate_stage = raw_stage
                    self.candidate_count = 1
                return self.current_stage

        # 역행 전이 (역방향: 예: 25 상태에서 21이 감지됨): 노이즈로 간주하고 무시
        return self.current_stage

    def smooth_gold(self, raw_gold: Optional[int]) -> Optional[int]:
        """골드 연속성 보정."""
        if raw_gold is None:
            return self.current_gold

        if 0 <= raw_gold <= 200:
            self.current_gold = raw_gold
            return self.current_gold

        return self.current_gold

    def step(self, raw_frame_data: Dict[str, Any]) -> Dict[str, Any]:
        """단일 프레임 인식 데이터를 받아 시간축 스무딩 적용."""
        smoothed = copy.deepcopy(raw_frame_data)

        # 1. 스테이지-라운드 보정
        raw_stage = raw_frame_data.get("stage_round")
        smoothed_stage = self.smooth_stage_round(raw_stage)
        smoothed["stage_round"] = smoothed_stage
        smoothed["raw_stage_round"] = raw_stage

        # 2. 골드 보정
        raw_gold = raw_frame_data.get("gold")
        smoothed_gold = self.smooth_gold(raw_gold)
        smoothed["gold"] = smoothed_gold
        smoothed["raw_gold"] = raw_gold

        # 3. 보드 유닛 유지 (필드 유닛이 일시적으로 0개 인식 시 직전 유닛 보존)
        field_units = raw_frame_data.get("field_units", [])
        if field_units:
            self.current_field_units = field_units
        elif self.current_field_units and (raw_stage is None or raw_stage == smoothed_stage):
            # 같은 라운드 또는 전환 중 일시적 가림 시 이전 유닛 유지
            smoothed["field_units"] = copy.deepcopy(self.current_field_units)
            smoothed["units_smoothed"] = True

        return smoothed

    def smooth_timeline(self, raw_timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """전체 타임라인 리스트를 일괄 스무딩 처리."""
        self.reset()
        smoothed_timeline = []
        for item in raw_timeline:
            smoothed_timeline.append(self.step(item))
        return smoothed_timeline
