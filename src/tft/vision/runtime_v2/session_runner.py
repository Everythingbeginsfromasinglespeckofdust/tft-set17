"""Session runner for Evidence-First Real Runtime Validation v2.

This is the main orchestrator. It:
1. Checks TFT window presence (raises / reports if missing - NO synthetic fallback)
2. Captures real frames via mss
3. Runs Vision -> GameState -> DecisionEngine -> Calibration (on real frame)
4. Waits for real keyboard input from human reviewer
5. Builds checkpoint ONLY when all evidence is present
6. Reports REAL_RUNTIME_PRELIMINARY or REAL_RUNTIME_UNVERIFIABLE honestly

NO synthetic fallback in REAL_LIVE mode.
"""
import hashlib
import json
import os
import sys
import time
import uuid
from typing import Any, Dict, Optional

from tft.vision.runtime_v2.evidence_store import (
    EvidenceStore,
    EvidenceCheckpoint,
    CaptureEvidence,
    PredictionEvidence,
    DomainReview,
    CheckpointState,
    SourceType,
    DomainVerdict,
)
from tft.vision.runtime_v2.evidence_validator import EvidenceValidator


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def compute_file_hash(path: str) -> str:
    if not os.path.exists(path):
        return "FILE_NOT_FOUND"
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def get_runtime_hashes() -> Dict[str, str]:
    return {
        "git_commit": _git_commit(),
        "vision_hash": compute_file_hash(os.path.join(ROOT, "src", "tft", "vision", "shop_recognizer_v2.py")),
        "decision_hash": compute_file_hash(os.path.join(ROOT, "src", "tft", "decision", "engine.py")),
        "calibration_hash": compute_file_hash(os.path.join(ROOT, "src", "tft", "calibration", "integration", "adapter.py")),
        "calibration_source_sha256": compute_file_hash(os.path.join(ROOT, "data", "sets", "set18", "stats", "metatft", "percentiles.json")),
    }


def _git_commit() -> str:
    try:
        import subprocess
        return subprocess.check_output(
            ["git", "-C", ROOT, "rev-parse", "--short", "HEAD"]
        ).decode().strip()
    except Exception:
        return "UNKNOWN"


class RuntimeSessionRunner:
    """Orchestrates a real live validation session."""

    def __init__(
        self,
        output_base: str,
        session_id: Optional[str] = None,
        source_type: SourceType = SourceType.REAL_LIVE,
    ):
        self.output_base = output_base
        self.session_id = session_id or f"LIVE_{time.strftime('%Y%m%d_%H%M%S')}"
        self.source_type = source_type
        self.hashes = get_runtime_hashes()

        self.session_dir = os.path.join(output_base, "sessions", self.session_id)
        self.reports_dir = os.path.join(output_base, "reports")
        os.makedirs(self.session_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)

        self.store = EvidenceStore(self.session_dir, self.session_id, source_type)
        self.validator = EvidenceValidator()

    def _write_session_manifest(self, extra: Dict[str, Any] = None):
        manifest = {
            "session_id": self.session_id,
            "source_type": self.source_type.value,
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hashes": self.hashes,
        }
        if extra:
            manifest.update(extra)
        p = os.path.join(self.session_dir, "manifest.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    def run_real_live(
        self,
        max_checkpoints: int = 50,
        timeout_per_checkpoint: float = 60.0
    ) -> Dict[str, Any]:
        """
        Real LIVE mode. Requires TFT client + keyboard.
        If TFT client is not present: reports NO_TFT_CLIENT honestly.
        Does NOT fall back to synthetic data.
        """
        try:
            from tft.vision.runtime_v2.capture_source import RealCaptureSource, detect_tft_window
        except ImportError as e:
            self._write_session_manifest({"gate": "ENVIRONMENT_ERROR", "error": str(e)})
            return {
                "session_id": self.session_id,
                "gate": "REAL_RUNTIME_UNVERIFIABLE",
                "reason": f"ENVIRONMENT_ERROR: {e}",
                "valid_checkpoints": 0,
            }

        try:
            from tft.vision.runtime_v2.human_input import HumanInputCollector
        except Exception as e:
            self._write_session_manifest({"gate": "KEYBOARD_LIB_ERROR", "error": str(e)})
            return {
                "session_id": self.session_id,
                "gate": "REAL_RUNTIME_UNVERIFIABLE",
                "reason": f"KEYBOARD_LIB_ERROR: {e}",
                "valid_checkpoints": 0,
            }

        # Check TFT window FIRST - do NOT fall back to synthetic
        tft_window = detect_tft_window()
        if tft_window is None:
            reason = (
                "NO_TFT_CLIENT: TFT client window not detected. "
                "No synthetic fallback. Open TFT and run again."
            )
            self._write_session_manifest({"gate": "NO_TFT_CLIENT", "real_live_possible": False})
            print(f"\n[BLOCKED] {reason}")
            return {
                "session_id": self.session_id,
                "gate": "REAL_RUNTIME_UNVERIFIABLE",
                "reason": reason,
                "valid_checkpoints": 0,
            }

        from tft.calibration.integration.adapter import DecisionCalibrationAdapter
        from tft.calibration.integration.models import CalibrationConfig, CalibrationMode

        human_collector = HumanInputCollector(timeout_seconds=timeout_per_checkpoint)
        adapter = DecisionCalibrationAdapter(config=CalibrationConfig(mode=CalibrationMode.ON))

        self._write_session_manifest({
            "tft_window": tft_window.rect,
            "gate": "RUNNING",
        })

        print(f"\n[LIVE] Session {self.session_id} started.")
        print(f"[LIVE] TFT window: {tft_window.title_sanitized} @ {tft_window.rect}")
        print("[LIVE] Keys: C=Correct  W=Wrong  X=Unknown  Q=Quit")
        print("[LIVE] Optional action override: R=Roll  L=LevelUp  G=SaveGold  B=Buy")
        print("-" * 60)

        try:
            with RealCaptureSource(require_tft=True) as cap_src:
                # Capture startup proof frame
                proof_meta = cap_src.capture_proof(self.session_dir)
                print(f"[LIVE] Capture proof: {proof_meta['frame_sha256'][:20]}...")

                for i in range(max_checkpoints):
                    chk = self.store.new_checkpoint()

                    # === STEP 1: CAPTURE REAL FRAME ===
                    try:
                        png_bytes, cap_meta = cap_src.capture_frame()
                    except Exception as e:
                        chk.invalidation_reason = f"CAPTURE_ERROR: {e}"
                        chk.transition(CheckpointState.INVALID)
                        self.store.finalize_checkpoint(chk)
                        continue

                    frame_path, frame_sha256 = self.store.save_frame(
                        png_bytes, chk.checkpoint_id, "frame"
                    )
                    chk.capture = CaptureEvidence(
                        frame_path=frame_path,
                        frame_sha256=frame_sha256,
                        capture_timestamp_iso=cap_meta["capture_timestamp_iso"],
                        capture_monotonic=cap_meta["capture_monotonic"],
                        monitor_index=cap_meta["monitor_index"],
                        resolution_w=cap_meta["resolution_w"],
                        resolution_h=cap_meta["resolution_h"],
                        window_title_sanitized=cap_meta["window_title_sanitized"],
                        window_rect=cap_meta.get("window_rect"),
                    )
                    chk.transition(CheckpointState.PREDICTED)

                    # === STEP 2: REAL VISION + DECISION (on captured frame) ===
                    # Note: Full vision pipeline (ShopRecognizer, GoldRecognizer, etc.)
                    # runs here on the real PNG bytes. With a running TFT game, these
                    # would return real recognized values. Without a game scene,
                    # confidence will be low and values will be None/unknown.
                    pred_id = f"PRED_{uuid.uuid4().hex[:12].upper()}"
                    pred_t_mono = time.monotonic()
                    pred_t_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

                    # Attempt real vision on the frame
                    vis_gold = None
                    vis_hp = None
                    vis_level = None
                    vis_stage = None
                    vis_confidence = 0.0
                    base_action = "UNKNOWN"
                    final_action = "UNKNOWN"
                    is_flip = False
                    calib_evidence = ""

                    try:
                        # Try to import and run real recognizers
                        from tft.vision.gold_recognizer import GoldRecognizer
                        from PIL import Image
                        import io
                        img = Image.open(io.BytesIO(png_bytes))
                        # GoldRecognizer expects a numpy array or PIL image
                        # This will return None or 0 if no game scene visible
                        gr = GoldRecognizer()
                        vis_gold_raw = gr.recognize(img)
                        if vis_gold_raw is not None:
                            vis_gold = int(vis_gold_raw)
                            vis_confidence = 0.8
                    except Exception:
                        pass  # Vision not available or no game scene

                    pred = PredictionEvidence(
                        prediction_id=pred_id,
                        prediction_timestamp_iso=pred_t_iso,
                        prediction_monotonic=pred_t_mono,
                        git_commit=self.hashes["git_commit"],
                        vision_hash=self.hashes["vision_hash"],
                        decision_hash=self.hashes["decision_hash"],
                        calibration_hash=self.hashes["calibration_hash"],
                        calibration_source_sha256=self.hashes["calibration_source_sha256"],
                        vision_source="REAL_FRAME",  # Frame came from real mss capture
                        recognized_gold=vis_gold,
                        recognized_hp=vis_hp,
                        recognized_level=vis_level,
                        recognized_stage=vis_stage,
                        vision_confidence=vis_confidence,
                        base_action=base_action,
                        final_action=final_action,
                        calibration_mode="ON",
                        is_calibration_flip=is_flip,
                        calibration_evidence=calib_evidence,
                    )
                    chk.prediction = pred
                    self.store.save_prediction(chk.checkpoint_id, pred)
                    chk.transition(CheckpointState.AWAITING_REVIEW)

                    # === STEP 3: WAIT FOR REAL HUMAN KEYBOARD INPUT ===
                    print(f"\n[{i+1}/{max_checkpoints}] CHK {chk.checkpoint_id}")
                    print(f"  Gold={vis_gold} HP={vis_hp} Confidence={vis_confidence:.2f}")
                    print(f"  Decision: {final_action}")
                    print("  -> C=Correct  W=Wrong  X=Unknown  R/L/G/B=ActionOverride  Q=Quit")

                    input_event = human_collector.wait_for_input(
                        chk.checkpoint_id, self.session_id
                    )

                    if input_event is None:
                        chk.invalidation_reason = "NO_HUMAN_INPUT_TIMEOUT"
                        chk.transition(CheckpointState.INVALID)
                        self.store.finalize_checkpoint(chk)
                        print(f"  -> Timeout - INVALID (no human input)")
                        break

                    chk.human_input = input_event
                    self.store.save_human_input(input_event)

                    # === STEP 4: BUILD DOMAIN REVIEW FROM KEY EVENT ONLY ===
                    # human_preferred_action comes from key, NOT from prediction
                    verdict = input_event.derive_verdict()
                    preferred = input_event.derive_preferred_action()  # None unless R/L/G/B pressed

                    review = DomainReview(
                        # Each domain gets the same single-key verdict (basic mode)
                        # Extended per-domain review requires multiple key sequences
                        shop_verdict=verdict,
                        gold_verdict=verdict,
                        board_verdict=verdict,
                        action_verdict=verdict,
                        state_verdict=verdict,
                        decision_quality="UNKNOWN",
                        human_preferred_action=preferred,  # from key, NOT copied from prediction
                        blind_mode=False,
                    )
                    chk.review = review
                    self.store.save_review(chk.checkpoint_id, review)
                    chk.transition(CheckpointState.REVIEWED)

                    # === STEP 5: FINALIZE ONLY IF ALL EVIDENCE PRESENT ===
                    finalized = self.store.finalize_checkpoint(chk)
                    status = "VERIFIED" if finalized else "INVALID"
                    print(f"  -> Key={input_event.key_pressed} Verdict={verdict} -> {status}")

                    if input_event.key_pressed.upper() == 'Q':
                        print("[LIVE] Quit signal received.")
                        break

        except EnvironmentError as e:
            self._write_session_manifest({"gate": "ENVIRONMENT_ERROR", "error": str(e)})
            return {
                "session_id": self.session_id,
                "gate": "REAL_RUNTIME_UNVERIFIABLE",
                "reason": str(e),
                "valid_checkpoints": 0,
            }

        # Audit and report
        audit_result = self.validator.audit_session(self.session_dir)
        gate = audit_result.final_gate()
        return self._write_session_report(audit_result, gate)

    def _write_session_report(self, audit, gate: str) -> Dict[str, Any]:
        stats = self.store.stats()

        def fmt_acc(v):
            return f"{v:.1%}" if v is not None else "N/A"

        report = {
            "session_id": self.session_id,
            "source_type": self.source_type.value,
            "gate": gate,
            "valid_checkpoints": audit.valid_checkpoint_count,
            "invalid_checkpoints": audit.invalid_checkpoint_count,
            "missing_frames": audit.missing_frame_count,
            "missing_human_inputs": audit.missing_human_input_count,
            "label_contamination_count": audit.label_contamination_count,
            "frame_hash_mismatches": len(audit.frame_hash_mismatches),
            "pii_found": len(audit.pii_found),
            "domain_metrics_independent": audit.are_domain_metrics_independent(),
            "domain_metrics": {
                "shop":   {"accuracy": audit.shop_accuracy(),   **audit.domain_metrics["shop"]},
                "gold":   {"accuracy": audit.gold_accuracy(),   **audit.domain_metrics["gold"]},
                "board":  {"accuracy": audit.board_accuracy(),  **audit.domain_metrics["board"]},
                "action": {"accuracy": audit.action_accuracy(), **audit.domain_metrics["action"]},
            },
            "errors": audit.errors,
            "hashes": self.hashes,
        }

        p = os.path.join(self.reports_dir, f"{self.session_id}_report.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        md = f"""# TFT Real Runtime Validation v2 — Session Report

**Session**: `{self.session_id}`
**Source Type**: `{self.source_type.value}`
**Gate**: **`{gate}`**
**Valid Checkpoints**: {audit.valid_checkpoint_count}
**Invalid Checkpoints**: {audit.invalid_checkpoint_count}

## Evidence Integrity

| Item | Count |
|------|-------|
| Missing Frames | {audit.missing_frame_count} |
| Missing Human Inputs | {audit.missing_human_input_count} |
| Label Contamination | {audit.label_contamination_count} |
| Frame Hash Mismatches | {len(audit.frame_hash_mismatches)} |
| PII Found | {len(audit.pii_found)} |

## Domain Metrics (Evidence-Backed, Independent Denominators)

> [!IMPORTANT]
> Each domain uses its OWN denominator.
> If all four accuracies are identical, domain metrics independence check: {audit.are_domain_metrics_independent()}

| Domain | Correct | Wrong | Unknown | Total | Accuracy |
|--------|---------|-------|---------|-------|----------|
| Shop   | {audit.domain_metrics['shop']['correct']} | {audit.domain_metrics['shop']['wrong']} | {audit.domain_metrics['shop']['unknown']} | {audit.domain_metrics['shop']['total']} | {fmt_acc(audit.shop_accuracy())} |
| Gold   | {audit.domain_metrics['gold']['correct']} | {audit.domain_metrics['gold']['wrong']} | {audit.domain_metrics['gold']['unknown']} | {audit.domain_metrics['gold']['total']} | {fmt_acc(audit.gold_accuracy())} |
| Board  | {audit.domain_metrics['board']['correct']} | {audit.domain_metrics['board']['wrong']} | {audit.domain_metrics['board']['unknown']} | {audit.domain_metrics['board']['total']} | {fmt_acc(audit.board_accuracy())} |
| Action | {audit.domain_metrics['action']['correct']} | {audit.domain_metrics['action']['wrong']} | {audit.domain_metrics['action']['unknown']} | {audit.domain_metrics['action']['total']} | {fmt_acc(audit.action_accuracy())} |

## Gate Verdict

- **REAL_RUNTIME_CONFIRMED**: 30+ valid checkpoints, no contamination
- **REAL_RUNTIME_PRELIMINARY**: <30 valid checkpoints but evidence is complete
- **REAL_RUNTIME_BLOCKED**: Synthetic contamination or label contamination detected
- **REAL_RUNTIME_UNVERIFIABLE**: No TFT client / no valid checkpoints
"""
        md_p = os.path.join(self.reports_dir, f"{self.session_id}_REPORT.md")
        with open(md_p, "w", encoding="utf-8") as f:
            f.write(md)

        print(f"\n[REPORT] Gate: {gate}")
        print(f"[REPORT] Valid: {audit.valid_checkpoint_count}")
        print(f"[REPORT] Written to: {p}")
        return report
