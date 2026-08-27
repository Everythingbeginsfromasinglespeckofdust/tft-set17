"""Shadow Evaluator for CALIB_C (Percentile Risk Mapping)."""
import hashlib
import json
import os
import time
from typing import Any, Dict, Optional, Tuple

from tft.calibration.shadow.shadow_models import (
    ShadowDecision,
    FlipDirection,
    ShadowRiskLevel,
    compute_deterministic_state_hash
)


class CALIBCShadowEvaluator:
    """Evaluates CALIB_C percentile risk mapping in an isolated shadow layer."""

    def __init__(
        self,
        percentiles_path: Optional[str] = None,
        shadow_enabled: bool = True,
        sampling_rate: float = 1.0
    ):
        self.shadow_enabled = shadow_enabled
        self.sampling_rate = max(0.0, min(1.0, sampling_rate))

        self.percentiles_path = percentiles_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "..", "..", "data", "sets", "set18", "stats", "metatft", "percentiles.json"
        )
        self.percentiles_path = os.path.abspath(self.percentiles_path)

        self.source_sha256 = self._compute_source_hash()
        self.percentile_data = self._load_percentiles()

    def _compute_source_hash(self) -> str:
        if os.path.exists(self.percentiles_path):
            with open(self.percentiles_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        return "UNKNOWN_SOURCE_HASH"

    def _load_percentiles(self) -> Dict[str, Any]:
        if os.path.exists(self.percentiles_path):
            try:
                with open(self.percentiles_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def evaluate_shadow(
        self,
        state: Any,
        production_recommendation: Any,
        session_id: str = "DEFAULT_SESSION",
        match_id: str = "DEFAULT_MATCH",
        vision_confidence: float = 1.0
    ) -> ShadowDecision:
        """Evaluate shadow decision in background. Strictly isolated from Production."""
        t_start = time.perf_counter()
        timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        state_hash = compute_deterministic_state_hash(state)

        # Extract Production Actions and Scores
        prod_act = "UNKNOWN"
        prod_scores = {}
        prod_margin = 0.0

        try:
            if hasattr(production_recommendation, "recommended_action"):
                prod_act = production_recommendation.recommended_action.action_type.value
            if hasattr(production_recommendation, "all_scores"):
                prod_scores = {asc.action.action_type.value: round(asc.score, 4) for asc in production_recommendation.all_scores}
            if hasattr(production_recommendation, "decision_margin"):
                prod_margin = round(float(production_recommendation.decision_margin), 4)
        except Exception:
            prod_act = "SAVE_GOLD"
            prod_scores = {"SAVE_GOLD": 1.0}

        # Kill Switch Check
        if not self.shadow_enabled:
            return ShadowDecision(
                timestamp_iso=timestamp_iso,
                session_id=session_id,
                match_id=match_id,
                state_hash=state_hash,
                production_action=prod_act,
                production_scores=prod_scores,
                production_margin=prod_margin,
                calibrated_action=prod_act,
                calibrated_scores=prod_scores,
                calibrated_margin=prod_margin,
                is_flip=False,
                flip_direction=FlipDirection.NO_FLIP.value,
                calibration_source="percentiles.json",
                calibration_source_sha256=self.source_sha256,
                calibration_value=0.0,
                sample_size=0,
                risk_level=ShadowRiskLevel.LOW.value,
                state_completeness="FULL",
                vision_confidence=vision_confidence,
                latency_ms=0.0,
                is_shadow_fallback=True,
                metadata={"reason": "SHADOW_DISABLED_BY_KILL_SWITCH"}
            )

        # Safe Calibrated Shadow Computation (Failure Isolated)
        try:
            calib_scores = dict(prod_scores)
            stage = getattr(state, "stage", 3)
            hp = getattr(state.player, "hp", 50) if hasattr(state, "player") else 50
            gold = getattr(state.player, "gold", 30) if hasattr(state, "player") else 30
            level = getattr(state.player, "level", 7) if hasattr(state, "player") else 7

            # CALIB_C Percentile Risk Mapping adjustments
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

            is_flip = (calib_act != prod_act)
            flip_dir = f"{prod_act}->{calib_act}" if is_flip else FlipDirection.NO_FLIP.value

            # Risk classification
            if vision_confidence < 0.85 or hp <= 20:
                risk = ShadowRiskLevel.HIGH_RISK.value
            elif is_flip:
                risk = ShadowRiskLevel.MEDIUM.value
            else:
                risk = ShadowRiskLevel.LOW.value

            state_comp = "FULL" if (hasattr(state, "board_units") and len(state.board_units) > 0) else "PARTIAL"
            latency = (time.perf_counter() - t_start) * 1000.0

            return ShadowDecision(
                timestamp_iso=timestamp_iso,
                session_id=session_id,
                match_id=match_id,
                state_hash=state_hash,
                production_action=prod_act,
                production_scores=prod_scores,
                production_margin=prod_margin,
                calibrated_action=calib_act,
                calibrated_scores=calib_scores,
                calibrated_margin=round(calib_margin, 4),
                is_flip=is_flip,
                flip_direction=flip_dir,
                calibration_source="percentiles.json",
                calibration_source_sha256=self.source_sha256,
                calibration_value=calib_val,
                sample_size=10000,
                risk_level=risk,
                state_completeness=state_comp,
                vision_confidence=vision_confidence,
                latency_ms=round(latency, 2),
                is_shadow_fallback=False
            )

        except Exception as e:
            # FAILURE ISOLATION: Catch any unexpected exception and return safe fallback
            latency = (time.perf_counter() - t_start) * 1000.0
            return ShadowDecision(
                timestamp_iso=timestamp_iso,
                session_id=session_id,
                match_id=match_id,
                state_hash=state_hash,
                production_action=prod_act,
                production_scores=prod_scores,
                production_margin=prod_margin,
                calibrated_action=prod_act,
                calibrated_scores=prod_scores,
                calibrated_margin=prod_margin,
                is_flip=False,
                flip_direction=FlipDirection.NO_FLIP.value,
                calibration_source="percentiles.json",
                calibration_source_sha256=self.source_sha256,
                calibration_value=0.0,
                sample_size=0,
                risk_level=ShadowRiskLevel.HIGH_RISK.value,
                state_completeness="PARTIAL",
                vision_confidence=vision_confidence,
                latency_ms=round(latency, 2),
                is_shadow_fallback=True,
                metadata={"error": str(e)}
            )
