"""TFT Set 17 Decision Engine Configuration."""
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig:
    repo_root: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    set17_json: str = os.path.join(repo_root, "tft_set17.json")
    items_json: str = os.path.join(repo_root, "tft_guide", "01_items.json")
    drop_rates_json: str = os.path.join(repo_root, "tft_guide", "03_drop_rates.json")
    xp_gold_json: str = os.path.join(repo_root, "tft_guide", "05_xp_gold.json")
    weights_json: str = os.path.join(repo_root, "output", "economy", "board_power_weights_v2.json")
    ddragon_dir: str = os.path.join(repo_root, "TFT_DDragon")

DEFAULT_CONFIG = AppConfig()
