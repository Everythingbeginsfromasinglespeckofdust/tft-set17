"""Baseline Strategies for Decision Engine Backtest Benchmarking."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from tft.domain.game_state import GameState
from tft.domain.actions import ActionType

class BaseStrategy(ABC):
    """의사결정 전략 기본 인터페이스."""
    name: str

    @abstractmethod
    def decide_action(self, state: GameState) -> ActionType:
        """주어진 GameState에서 추천할 ActionType 반환."""
        pass

class AlwaysSaveBaseline(BaseStrategy):
    """Baseline A: 항상 골드를 저축하여 이자 극대화 (Always SAVE_GOLD)."""
    name = "AlwaysSave"

    def decide_action(self, state: GameState) -> ActionType:
        return ActionType.SAVE_GOLD

class HPThresholdBaseline(BaseStrategy):
    """Baseline B: 체력 임계값 기반 규칙 (HP <= threshold 이면 ROLL, 아니면 SAVE)."""
    name = "HPThreshold"

    def __init__(self, hp_threshold: int = 35):
        self.hp_threshold = hp_threshold

    def decide_action(self, state: GameState) -> ActionType:
        if state.player.hp <= self.hp_threshold:
            return ActionType.ROLL
        return ActionType.SAVE_GOLD

class RuleEngineBaseline(BaseStrategy):
    """Baseline C: 전통적 TFT 레벨/이자/체력 복합 휴리스틱 규칙 엔진."""
    name = "RuleEngine"

    def __init__(self, crisis_hp: int = 30, econ_threshold: int = 50):
        self.crisis_hp = crisis_hp
        self.econ_threshold = econ_threshold

    def decide_action(self, state: GameState) -> ActionType:
        hp = state.player.hp
        gold = state.player.gold
        level = state.player.level
        xp = state.player.xp

        # 1. Crisis Defense
        if hp <= self.crisis_hp and gold >= 2:
            return ActionType.ROLL

        # 2. Level Up Breakpoint Timing (Near next level with high gold)
        # Check standard level-up XP
        req_xp_map = {2: 2, 3: 6, 4: 10, 5: 20, 6: 36, 7: 60, 8: 68, 9: 68, 10: 68}
        next_lvl = level + 1
        req_xp = req_xp_map.get(next_lvl, 999)
        needed_xp = max(0, req_xp - xp)
        clicks_needed = (needed_xp + 3) // 4
        gold_needed = clicks_needed * 4

        if clicks_needed <= 2 and gold >= (self.econ_threshold + gold_needed) and level < 9:
            return ActionType.LEVEL_UP

        # 3. Default Econ Compound
        return ActionType.SAVE_GOLD
