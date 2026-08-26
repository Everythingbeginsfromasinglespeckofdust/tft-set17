"""Adapters: Transform Observation -> GameState."""
import re
from typing import Optional
from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit, BoardPosition
from tft.vision.observation import Observation
from tft.data.repositories import get_data_repository

class ObservationToGameStateBuilder:
    """Observation(화면 인식 결과)을 정규화된 GameState(도메인 진실 상태)로 변환."""

    def __init__(self, data_repo=None):
        self.data_repo = data_repo or get_data_repository()

    def build(self, obs: Observation, fallback_state: Optional[GameState] = None) -> GameState:
        # 1. Parse Stage & Round
        stage_round = obs.stage_text or (fallback_state.stage_round if fallback_state else "2-1")
        m = re.search(r"(\d)[-~_](\d)", stage_round)
        if m:
            stage, rnd = int(m.group(1)), int(m.group(2))
            stage_round = f"{stage}-{rnd}"
        else:
            stage, rnd = (fallback_state.stage, fallback_state.round) if fallback_state else (2, 1)

        # 2. Player stats
        gold = obs.gold_val if obs.gold_val is not None else (fallback_state.player.gold if fallback_state else 0)
        level = obs.level_val if obs.level_val is not None else (fallback_state.player.level if fallback_state else 1)
        xp = obs.xp_val if obs.xp_val is not None else (fallback_state.player.xp if fallback_state else 0)
        hp = obs.hp_val if obs.hp_val is not None else (fallback_state.player.hp if fallback_state else 100)

        player = PlayerState(gold=gold, level=level, xp=xp, hp=hp)

        # 3. Units from field detections
        board_units = []
        for det in obs.field_detections:
            if not det.champion_pred: continue
            cinfo = self.data_repo.get_champion(det.champion_pred)
            cost = cinfo["cost"] if cinfo else 1
            pos = None
            if "hex_r" in det.location:
                m_pos = re.search(r"hex_r(\d)_c(\d)", det.location)
                if m_pos:
                    pos = BoardPosition(row=int(m_pos.group(1)), col=int(m_pos.group(2)))
            board_units.append(Unit(
                champion=det.champion_pred,
                cost=cost,
                star_level=det.star_level_pred,
                items=list(det.items_pred),
                position=pos,
                is_bench=False
            ))

        # 4. Units from bench detections
        bench_units = []
        for det in obs.bench_detections:
            if not det.champion_pred: continue
            cinfo = self.data_repo.get_champion(det.champion_pred)
            cost = cinfo["cost"] if cinfo else 1
            slot_idx = None
            if "bench_" in det.location:
                m_slot = re.search(r"bench_(\d)", det.location)
                if m_slot:
                    slot_idx = int(m_slot.group(1))
            bench_units.append(Unit(
                champion=det.champion_pred,
                cost=cost,
                star_level=det.star_level_pred,
                items=list(det.items_pred),
                slot_index=slot_idx,
                is_bench=True
            ))

        # 5. Shop cards
        shop_units = [c.champion_pred if not c.is_empty else None for c in obs.shop_cards]
        while len(shop_units) < 5:
            shop_units.append(None)

        return GameState(
            stage=stage,
            round=rnd,
            stage_round=stage_round,
            player=player,
            board_units=board_units,
            bench_units=bench_units,
            shop_units=shop_units[:5]
        )
