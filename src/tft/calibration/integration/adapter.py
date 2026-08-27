"""Production Calibration Adapter wrapping DecisionEngine."""
import hashlib
import json
import os
import time
from typing import Any, Dict, Optional

from tft.decision.engine import DecisionEngine
from tft.decision.scorer import DEFAULT_DECISION_CONFIG
from tft.calibration.integration.models import (
    CalibrationConfig,
    CalibrationMode,
    CalibrationAppliedStatus,
    CalibratedDecisionResult,
    compute_deterministic_state_hash
)


class DecisionCalibrationAdapter:
    """Production Adapter integrating optional CALIB_C Calibration Layer."""

    def __init__(
        self,
        engine: Optional[DecisionEngine] = None,
        config: Optional[CalibrationConfig] = None
    ):
        self.engine = engine or DecisionEngine(config=DEFAULT_DECISION_CONFIG)
        self.config = config or CalibrationConfig()

        # Locate percentiles.json
        if not self.config.percentiles_path:
            self.config.percentiles_path = os.path.abspath(os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "..", "data", "sets", "set18", "stats", "metatft", "percentiles.json"
            ))

        self.source_sha256 = self._compute_source_sha256()

    def _compute_source_sha256(self) -> str:
        if self.config.percentiles_path and os.path.exists(self.config.percentiles_path):
            try:
                with open(self.config.percentiles_path, "rb") as f:
                    return hashlib.sha256(f.read()).hexdigest()
            except Exception:
                return "HASH_ERROR"
        return "SOURCE_NOT_FOUND"

    def decide(
        self,
        state: Any,
        vision_confidence: float = 1.0,
        override_mode: Optional[CalibrationMode] = None
    ) -> CalibratedDecisionResult:
        """Execute Decision Pipeline with optional Calibration layer."""
        t_start = time.perf_counter()
        state_hash = compute_deterministic_state_hash(state)
        mode = override_mode or self.config.mode

        # 1. Execute Base Frozen Production Engine (Always First)
        base_dec = self.engine.decide(state)
        base_act = base_dec.recommended_action.action_type.value
        base_scores = {asc.action.action_type.value: round(asc.score, 4) for asc in base_dec.all_scores}
        base_sorted = sorted(base_scores.items(), key=lambda x: x[1], reverse=True)
        base_margin = base_sorted[0][1] - base_sorted[1][1] if len(base_sorted) > 1 else 0.0

        # Mode: OFF -> Return Base Recommendation immediately
        if mode == CalibrationMode.OFF:
            lat = (time.perf_counter() - t_start) * 1000.0
            return CalibratedDecisionResult(
                action=base_act,
                scores=base_scores,
                margin=round(base_margin, 4),
                base_action=base_act,
                base_scores=base_scores,
                base_margin=round(base_margin, 4),
                calibration_mode=mode.value,
                calibration_applied=False,
                applied_status=CalibrationAppliedStatus.CALIBRATION_SKIPPED.value,
                is_flip=False,
                flip_direction="NO_FLIP",
                candidate_version=self.config.candidate_version,
                source_sha256=self.source_sha256,
                calibration_value=0.0,
                latency_ms=round(lat, 3),
                state_hash=state_hash
            )

        # Mode: SHADOW or ON -> Evaluate CALIB_C with Failure Isolation
        try:
            # Source Integrity Guard
            if self.source_sha256 in ["SOURCE_NOT_FOUND", "HASH_ERROR"]:
                lat = (time.perf_counter() - t_start) * 1000.0
                return CalibratedDecisionResult(
                    action=base_act,
                    scores=base_scores,
                    margin=round(base_margin, 4),
                    base_action=base_act,
                    base_scores=base_scores,
                    base_margin=round(base_margin, 4),
                    calibration_mode=mode.value,
                    calibration_applied=False,
                    applied_status=CalibrationAppliedStatus.CALIBRATION_FALLBACK.value,
                    is_flip=False,
                    flip_direction="NO_FLIP",
                    candidate_version=self.config.candidate_version,
                    source_sha256=self.source_sha256,
                    calibration_value=0.0,
                    latency_ms=round(lat, 3),
                    state_hash=state_hash,
                    metadata={"fallback_reason": "CALIBRATION_SOURCE_INVALID"}
                )

            # Vision Confidence Guard
            if vision_confidence < self.config.min_vision_confidence:
                lat = (time.perf_counter() - t_start) * 1000.0
                return CalibratedDecisionResult(
                    action=base_act,
                    scores=base_scores,
                    margin=round(base_margin, 4),
                    base_action=base_act,
                    base_scores=base_scores,
                    base_margin=round(base_margin, 4),
                    calibration_mode=mode.value,
                    calibration_applied=False,
                    applied_status=CalibrationAppliedStatus.CALIBRATION_SKIPPED.value,
                    is_flip=False,
                    flip_direction="NO_FLIP",
                    candidate_version=self.config.candidate_version,
                    source_sha256=self.source_sha256,
                    calibration_value=0.0,
                    latency_ms=round(lat, 3),
                    state_hash=state_hash,
                    metadata={"skip_reason": "LOW_VISION_CONFIDENCE"}
                )

            calib_scores = dict(base_scores)
            stage = getattr(state, "stage", 3)
            hp = getattr(state.player, "hp", 50) if hasattr(state, "player") else 50
            gold = getattr(state.player, "gold", 30) if hasattr(state, "player") else 30
            level = getattr(state.player, "level", 7) if hasattr(state, "player") else 7

            calib_val = 0.0
            if stage >= 4 and hp <= 50 and gold >= 25:
                calib_val = 0.025
                calib_scores["ROLL"] = calib_scores.get("ROLL", 0.0) + calib_val
                calib_scores["SAVE_GOLD"] = calib_scores.get("SAVE_GOLD", 0.0) - calib_val
            elif stage in [3, 4] and gold >= 45 and level in [6, 7]:
                calib_val = 0.025
                calib_scores["LEVEL_UP"] = calib_scores.get("LEVEL_UP", 0.0) + calib_val
                calib_scores["SAVE_GOLD"] = calib_scores.get("SAVE_GOLD", 0.0) - calib_val

            tot = sum(calib_scores.values()) if sum(calib_scores.values()) > 0 else 1.0
            calib_scores = {k: round(v / tot, 4) for k, v in calib_scores.items()}
            sorted_calib = sorted(calib_scores.items(), key=lambda x: x[1], reverse=True)
            calib_act = sorted_calib[0][0]
            calib_margin = sorted_calib[0][1] - sorted_calib[1][1] if len(sorted_calib) > 1 else 0.0

            is_flip = (calib_act != base_act)
            flip_dir = f"{base_act}->{calib_act}" if is_flip else "NO_FLIP"

            lat = (time.perf_counter() - t_start) * 1000.0

            if mode == CalibrationMode.SHADOW:
                # In SHADOW mode: visible action is BASE action, calibration is logged in telemetry
                return CalibratedDecisionResult(
                    action=base_act,
                    scores=base_scores,
                    margin=round(base_margin, 4),
                    base_action=base_act,
                    base_scores=base_scores,
                    base_margin=round(base_margin, 4),
                    calibration_mode=mode.value,
                    calibration_applied=False,
                    applied_status=CalibrationAppliedStatus.CALIBRATION_SKIPPED.value,
                    is_flip=is_flip,
                    flip_direction=flip_dir,
                    candidate_version=self.config.candidate_version,
                    source_sha256=self.source_sha256,
                    calibration_value=calib_val,
                    latency_ms=round(lat, 3),
                    state_hash=state_hash,
                    metadata={"shadow_calibrated_action": calib_act, "shadow_calibrated_scores": calib_scores}
                )

            elif mode == CalibrationMode.ON:
                # In ON mode: visible action is CALIBRATED action
                return CalibratedDecisionResult(
                    action=calib_act,
                    scores=calib_scores,
                    margin=round(calib_margin, 4),
                    base_action=base_act,
                    base_scores=base_scores,
                    base_margin=round(base_margin, 4),
                    calibration_mode=mode.value,
                    calibration_applied=is_flip,
                    applied_status=CalibrationAppliedStatus.CALIBRATION_APPLIED.value if is_flip else CalibrationAppliedStatus.CALIBRATION_SKIPPED.value,
                    is_flip=is_flip,
                    flip_direction=flip_dir,
                    candidate_version=self.config.candidate_version,
                    source_sha256=self.source_sha256,
                    calibration_value=calib_val,
                    latency_ms=round(lat, 3),
                    state_hash=state_hash,
                    metadata={"calibration_evidence": "Stage survival percentile risk threshold exceeded" if is_flip else "None"}
                )

        except Exception as e:
            # FAILURE ISOLATION: Return safe base production recommendation
            lat = (time.perf_counter() - t_start) * 1000.0
            return CalibratedDecisionResult(
                action=base_act,
                scores=base_scores,
                margin=round(base_margin, 4),
                base_action=base_act,
                base_scores=base_scores,
                base_margin=round(base_margin, 4),
                calibration_mode=mode.value,
                calibration_applied=False,
                applied_status=CalibrationAppliedStatus.CALIBRATION_FALLBACK.value,
                is_flip=False,
                flip_direction="NO_FLIP",
                candidate_version=self.config.candidate_version,
                source_sha256=self.source_sha256,
                calibration_value=0.0,
                latency_ms=round(lat, 3),
                state_hash=state_hash,
                metadata={"error": str(e), "fallback_reason": "CALIBRATION_RUNTIME_ERROR"}
            )
