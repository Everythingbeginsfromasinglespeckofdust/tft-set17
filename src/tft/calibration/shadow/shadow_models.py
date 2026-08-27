"""Data Models for TFT Production Calibration Shadow Mode v1.

Core Invariants:
  - Production recommendation is untouched and user-facing.
  - Shadow decision is evaluated in an isolated layer and logged for validation.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import json


class FlipDirection(str, Enum):
    SAVE_TO_ROLL = "SAVE_GOLD->ROLL"
    SAVE_TO_LEVEL = "SAVE_GOLD->LEVEL_UP"
    ROLL_TO_SAVE = "ROLL->SAVE_GOLD"
    ROLL_TO_LEVEL = "ROLL->LEVEL_UP"
    LEVEL_TO_SAVE = "LEVEL_UP->SAVE_GOLD"
    LEVEL_TO_ROLL = "LEVEL_UP->ROLL"
    NO_FLIP = "NO_FLIP"


class ShadowRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH_RISK = "HIGH_RISK"


@dataclass
class ShadowDecision:
    """Full trace of a shadow-evaluated decision."""
    timestamp_iso: str
    session_id: str
    match_id: str
    state_hash: str

    # Production decision (frozen, user-facing)
    production_action: str
    production_scores: Dict[str, float]
    production_margin: float

    # Calibrated shadow decision (experimental, log only)
    calibrated_action: str
    calibrated_scores: Dict[str, float]
    calibrated_margin: float

    # Flip diagnostics
    is_flip: bool
    flip_direction: str

    # Calibration lineage & evidence
    calibration_source: str
    calibration_source_sha256: str
    calibration_value: float
    sample_size: int
    risk_level: str

    # Operational metrics
    state_completeness: str  # FULL, PARTIAL, MINIMAL
    vision_confidence: float
    latency_ms: float
    is_shadow_fallback: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


def compute_deterministic_state_hash(state: Any) -> str:
    """Compute deterministic SHA256 state hash using only observable T0 features."""
    if not hasattr(state, "player") or not hasattr(state, "stage_round"):
        return "UNKNOWN_STATE"

    b_units = sorted([f"{u.champion}_{u.star_level}_{u.cost}" for u in getattr(state, "board_units", [])])
    bn_units = sorted([f"{u.champion}_{u.star_level}_{u.cost}" for u in getattr(state, "bench_units", [])])
    
    hash_dict = {
        "stage_round": state.stage_round,
        "gold": state.player.gold,
        "hp": state.player.hp,
        "level": state.player.level,
        "xp": state.player.xp,
        "board_units": b_units,
        "bench_units": bn_units
    }
    raw_str = json.dumps(hash_dict, sort_keys=True)
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
