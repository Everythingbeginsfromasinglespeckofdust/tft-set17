"""Data Models and Configuration for TFT Production Calibration Integration v1.

Core Invariants:
  - Default mode is OFF (calibration_enabled = False).
  - Production DecisionEngine core is wrapped via Adapter, zero core algorithm changes.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import json


class CalibrationMode(str, Enum):
    OFF = "OFF"
    SHADOW = "SHADOW"
    ON = "ON"


class CalibrationAppliedStatus(str, Enum):
    CALIBRATION_APPLIED = "CALIBRATION_APPLIED"
    CALIBRATION_SKIPPED = "CALIBRATION_SKIPPED"
    CALIBRATION_FALLBACK = "CALIBRATION_FALLBACK"


@dataclass
class CalibrationConfig:
    """Production Calibration Configuration with Safe Default."""
    enabled: bool = False
    mode: CalibrationMode = CalibrationMode.OFF
    candidate_name: str = "CALIB_C"
    candidate_version: str = "CALIB_C_PROD_V1"
    percentiles_path: Optional[str] = None
    expected_source_sha256: Optional[str] = None
    min_vision_confidence: float = 0.80

    def __post_init__(self):
        # Validate configuration consistency
        if isinstance(self.mode, str):
            self.mode = CalibrationMode(self.mode.upper())
        if self.enabled and self.mode == CalibrationMode.OFF:
            self.mode = CalibrationMode.ON
        elif not self.enabled and self.mode == CalibrationMode.ON:
            self.enabled = True


@dataclass
class CalibratedDecisionResult:
    """Unified Production Decision Result supporting Optional Calibration Layer."""
    # Final user-facing recommendation
    action: str
    scores: Dict[str, float]
    margin: float

    # Base Production recommendation (unmodified DecisionEngine output)
    base_action: str
    base_scores: Dict[str, float]
    base_margin: float

    # Calibration telemetry & lineage
    calibration_mode: str
    calibration_applied: bool
    applied_status: str
    is_flip: bool
    flip_direction: str

    candidate_version: str
    source_sha256: str
    calibration_value: float
    latency_ms: float
    state_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)


def compute_deterministic_state_hash(state: Any) -> str:
    """Deterministic state hash using observable T0 features only."""
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
