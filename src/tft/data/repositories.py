"""TFT Set 17 Static Data Repository."""
import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple
from tft.infrastructure.config import DEFAULT_CONFIG, AppConfig

TRAIT_BREAKPOINTS_DEFAULT = {
    "중재자": [2, 3],
    "동물특공대": [3, 5],
    "정령족": [3, 5, 7, 10],
    "파티광": [1],
    "N.O.V.A.": [2, 5],
    "암흑의 별": [2, 4, 6, 9],
    "신성 결투가": [1],
    "최신상": [1],
    "말살자": [1],
    "메카": [3, 4, 6],
    "기동총격여신": [1],
    "어둠의 여인": [1],
    "태고족": [2, 3],
    "초능력": [2, 4],
    "구원자": [1],
    "보루": [1],
    "지휘관": [1],
    "우주 그루브": [1, 3, 5, 7, 10],
    "별돌보미": [3, 4, 5, 6],
    "예언자": [1],
    "시간 균열자": [2, 3, 4],
    "파멸자": [1],
    "은하계 사냥꾼": [1],
    "복제자": [2, 4],
    "도전자": [2, 3, 4, 5],
    "불한당": [2, 3, 4, 5],
    "운명술사": [2, 4],
    "여행자": [2, 3, 4, 5, 6],
    "싸움꾼": [2, 4, 6],
    "전달자": [2, 3, 4, 5],
    "습격자": [2, 4, 6],
    "저격수": [2, 3, 4],
    "요새": [2, 4, 6],
    "선봉대": [2, 4, 6],
    "길잡이": [3, 5, 7],
}

class StaticDataRepository:
    """TFT Set 17 정적 데이터(챔피언, 특성, 아이템, 드랍률, 레벨업)의 단일 Source of Truth."""

    def __init__(self, config: AppConfig = DEFAULT_CONFIG):
        self.config = config
        self._champions: Dict[str, Dict[str, Any]] = {}
        self._champions_by_cost: Dict[int, List[str]] = {1: [], 2: [], 3: [], 4: [], 5: []}
        self._basic_components: Set[str] = set()
        self._completed_items: Set[str] = set()
        self._drop_rates: Dict[int, Dict[int, float]] = {}
        self._pool_sizes: Dict[int, int] = {1: 30, 2: 25, 3: 18, 4: 10, 5: 9}
        self._levelup_table: Dict[int, int] = {}
        self._star_multipliers: Dict[int, float] = {1: 1.0, 2: 2.2, 3: 3.6}
        self._item_scores: Dict[str, float] = {"completed": 3.0, "component": 0.0}
        self._trait_breakpoints: Dict[str, List[int]] = dict(TRAIT_BREAKPOINTS_DEFAULT)
        self.reload_all()

    def reload_all(self):
        self._load_champions()
        self._load_items()
        self._load_drop_rates()
        self._load_xp_gold()
        self._load_weights()

    def _load_champions(self):
        if os.path.exists(self.config.set17_json):
            with open(self.config.set17_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                for c in data.get("champions", []):
                    self._champions[c["name"]] = c
                    cost = int(c.get("cost", 1))
                    if cost in self._champions_by_cost:
                        self._champions_by_cost[cost].append(c["name"])
                    for t in c.get("traits", []):
                        if t not in self._trait_breakpoints:
                            self._trait_breakpoints[t] = [1]
                traits_raw = data.get("traits", [])
                if isinstance(traits_raw, dict):
                    for t_name, bp in traits_raw.items():
                        if isinstance(bp, list):
                            self._trait_breakpoints[t_name] = bp

    def _load_items(self):
        if os.path.exists(self.config.items_json):
            with open(self.config.items_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                for it in data.get("basic_components", []):
                    if isinstance(it, str):
                        self._basic_components.add(it)
                    elif isinstance(it, dict) and "name" in it:
                        self._basic_components.add(it["name"])

                for it in data.get("standard_items", []):
                    if isinstance(it, str):
                        self._completed_items.add(it)
                    elif isinstance(it, dict) and "name" in it:
                        self._completed_items.add(it["name"])

                for it in data.get("set17_special_items", []):
                    if isinstance(it, str):
                        self._completed_items.add(it)
                    elif isinstance(it, dict) and "name" in it:
                        self._completed_items.add(it["name"])

    def _load_drop_rates(self):
        if os.path.exists(self.config.drop_rates_json):
            with open(self.config.drop_rates_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                rows = data.get("shop_drop_rates", [])
                for row in rows:
                    if row.get("exists_in_game", True) is False:
                        continue
                    lvl = int(row["level"])
                    pct = row.get("drop_rate_percent", {})
                    self._drop_rates[lvl] = {
                        int(k[:-len("cost")]): pct[k] / 100.0
                        for k in pct
                        if k.endswith("cost")
                    }
                self._pool_sizes = {int(k): int(v) for k, v in data.get("pool_sizes", {1: 30, 2: 25, 3: 18, 4: 10, 5: 9}).items()}

    def _load_xp_gold(self):
        if os.path.exists(self.config.xp_gold_json):
            with open(self.config.xp_gold_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                for entry in data.get("level_up_xp", []):
                    to_lvl = int(entry["to_level"])
                    xp_req = int(entry["xp_required"])
                    self._levelup_table[to_lvl] = xp_req

    def _load_weights(self):
        if os.path.exists(self.config.weights_json):
            with open(self.config.weights_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                star_raw = data.get("star_multiplier", {"1": 1.0, "2": 2.2, "3": 3.6})
                self._star_multipliers = {int(k): float(v) for k, v in star_raw.items()}
                item_data = data.get("item_score", {"completed": 3.0, "component": 0.0})
                self._item_scores = {
                    "completed": float(item_data.get("completed", 3.0)),
                    "component": float(item_data.get("component", 0.0))
                }

    # Public Queries
    def get_champion(self, name: str) -> Optional[Dict[str, Any]]:
        return self._champions.get(name)

    def get_all_champions(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._champions)

    def get_champion_count_by_cost(self, cost: int) -> int:
        return len(self._champions_by_cost.get(cost, [])) or 13

    def is_basic_component(self, name: str) -> bool:
        return name in self._basic_components

    def is_completed_item(self, name: str) -> bool:
        return name in self._completed_items

    def get_drop_rate(self, level: int, cost: int) -> float:
        return self._drop_rates.get(level, {}).get(cost, 0.0)

    def get_pool_size(self, cost: int) -> int:
        return self._pool_sizes.get(cost, 0)

    def get_levelup_cost_table(self) -> Dict[int, int]:
        return dict(self._levelup_table)

    def get_star_multipliers(self) -> Dict[int, float]:
        return dict(self._star_multipliers)

    def get_item_score_weights(self) -> Tuple[float, float]:
        return self._item_scores["component"], self._item_scores["completed"]

_DEFAULT_REPO = StaticDataRepository()

def get_data_repository() -> StaticDataRepository:
    return _DEFAULT_REPO
