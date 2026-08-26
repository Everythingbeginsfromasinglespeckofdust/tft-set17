"""TFT Core Domain Contract: GameState."""
import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from tft.domain.units import Unit, BoardPosition
from tft.domain.items import Item
from tft.domain.augments import Augment
from tft.domain.traits import Trait

@dataclass(frozen=True)
class PlayerState:
    gold: int
    level: int
    xp: int
    hp: int = 100
    streak: int = 0

    def with_updates(
        self,
        gold: Optional[int] = None,
        level: Optional[int] = None,
        xp: Optional[int] = None,
        hp: Optional[int] = None,
        streak: Optional[int] = None,
    ) -> "PlayerState":
        return PlayerState(
            gold=self.gold if gold is None else gold,
            level=self.level if level is None else level,
            xp=self.xp if xp is None else xp,
            hp=self.hp if hp is None else hp,
            streak=self.streak if streak is None else streak,
        )

@dataclass(frozen=True)
class LobbyState:
    player_id: str
    hp: int
    level: int
    estimated_board_power: float

@dataclass(frozen=True)
class GameState:
    """TFT 실시간 게임 상태의 단일 중심 모델 (Pure Immutable State Contract)."""
    stage: int
    round: int
    stage_round: str
    player: PlayerState
    board_units: List[Unit] = field(default_factory=list)
    bench_units: List[Unit] = field(default_factory=list)
    shop_units: List[Optional[str]] = field(default_factory=lambda: [None]*5)
    item_bench: List[str] = field(default_factory=list)
    augments: List[str] = field(default_factory=list)
    opponents: List[LobbyState] = field(default_factory=list)

    def with_updates(
        self,
        stage: Optional[int] = None,
        round: Optional[int] = None,
        stage_round: Optional[str] = None,
        player: Optional[PlayerState] = None,
        board_units: Optional[List[Unit]] = None,
        bench_units: Optional[List[Unit]] = None,
        shop_units: Optional[List[Optional[str]]] = None,
        item_bench: Optional[List[str]] = None,
        augments: Optional[List[str]] = None,
        opponents: Optional[List[LobbyState]] = None,
    ) -> "GameState":
        """안전한 불변 객체 복제 및 업데이트 (Immutable state update)."""
        new_stage = self.stage if stage is None else stage
        new_round = self.round if round is None else round
        new_sr = f"{new_stage}-{new_round}" if stage_round is None else stage_round
        return GameState(
            stage=new_stage,
            round=new_round,
            stage_round=new_sr,
            player=self.player if player is None else player,
            board_units=list(self.board_units) if board_units is None else list(board_units),
            bench_units=list(self.bench_units) if bench_units is None else list(bench_units),
            shop_units=list(self.shop_units) if shop_units is None else list(shop_units),
            item_bench=list(self.item_bench) if item_bench is None else list(item_bench),
            augments=list(self.augments) if augments is None else list(augments),
            opponents=list(self.opponents) if opponents is None else list(opponents),
        )

    def clone(self) -> "GameState":
        return copy.deepcopy(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameState":
        stage_round = str(data.get("stage_round", "2-1"))
        if "-" in stage_round:
            parts = stage_round.split("-")
            stage = int(parts[0]) if parts[0].isdigit() else 2
            rnd = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        else:
            stage, rnd = int(data.get("stage", 2)), int(data.get("round", 1))

        player = PlayerState(
            gold=int(data.get("gold", 0)),
            level=int(data.get("level", 1)),
            xp=int(data.get("xp", 0)),
            hp=int(data.get("hp", 100)),
            streak=int(data.get("streak", 0))
        )

        board_units = []
        raw_board = data.get("board", {})
        raw_units = raw_board.get("units", []) if isinstance(raw_board, dict) else data.get("board_units", [])
        for u in raw_units:
            pos = None
            if "position" in u and isinstance(u["position"], dict):
                pos = BoardPosition(row=u["position"].get("row", 0), col=u["position"].get("col", 0))
            elif "row" in u and "col" in u:
                pos = BoardPosition(row=u["row"], col=u["col"])
            
            board_units.append(Unit(
                champion=u["champion"],
                cost=int(u.get("cost", 1)),
                star_level=int(u.get("star_level", 1)),
                items=list(u.get("items", [])),
                position=pos,
                is_bench=False
            ))

        bench_units = []
        for u in data.get("bench_units", []):
            bench_units.append(Unit(
                champion=u["champion"],
                cost=int(u.get("cost", 1)),
                star_level=int(u.get("star_level", 1)),
                items=list(u.get("items", [])),
                slot_index=u.get("slot_index", u.get("slot")),
                is_bench=True
            ))

        return cls(
            stage=stage,
            round=rnd,
            stage_round=stage_round,
            player=player,
            board_units=board_units,
            bench_units=bench_units,
            shop_units=list(data.get("shop_units", [None]*5)),
            item_bench=list(data.get("item_bench", [])),
            augments=list(data.get("augments", [])),
            opponents=[]
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "round": self.round,
            "stage_round": self.stage_round,
            "gold": self.player.gold,
            "level": self.player.level,
            "xp": self.player.xp,
            "hp": self.player.hp,
            "streak": self.player.streak,
            "board": {
                "units": [u.to_dict() for u in self.board_units]
            },
            "bench_units": [u.to_dict() for u in self.bench_units],
            "shop_units": list(self.shop_units),
            "item_bench": list(self.item_bench),
            "augments": list(self.augments)
        }
