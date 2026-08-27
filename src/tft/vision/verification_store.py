"""Verification Store: Persistent storage for Human Verification, Error Snapshots, and Ground Truth Export."""
import json
import os
import shutil
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from tft.vision.validation_models import (
    VerificationEvent,
    VerificationSummary,
    TargetType,
    HumanVerdict,
    ErrorReason
)


class VerificationStore:
    """인간 검증 로그, 예측 스트림, 수정 데이터, 오류 스냅샷을 분리 보존하는 검증 데이터 스토리지."""

    def __init__(self, base_dir: str = "data/vision_validation"):
        self.base_dir = base_dir
        self.sessions_dir = os.path.join(self.base_dir, "sessions")
        self.frames_dir = os.path.join(self.base_dir, "frames")
        self.ground_truth_dir = os.path.join(self.base_dir, "ground_truth")
        self.reports_dir = os.path.join(self.base_dir, "reports")

        os.makedirs(self.sessions_dir, exist_ok=True)
        os.makedirs(self.frames_dir, exist_ok=True)
        os.makedirs(self.ground_truth_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)

    def get_session_dir(self, session_id: str) -> str:
        s_dir = os.path.join(self.sessions_dir, session_id)
        os.makedirs(s_dir, exist_ok=True)
        return s_dir

    def get_session_frames_dir(self, session_id: str) -> str:
        f_dir = os.path.join(self.frames_dir, session_id)
        os.makedirs(f_dir, exist_ok=True)
        return f_dir

    def log_prediction(self, session_id: str, prediction_data: Dict[str, Any]) -> None:
        """비전 파이프라인의 원본 예측 스트림 기록 (절대 인간 레이블로 덮어쓰지 않음)."""
        s_dir = self.get_session_dir(session_id)
        pred_path = os.path.join(s_dir, "predictions.jsonl")
        with open(pred_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(prediction_data, ensure_ascii=False) + "\n")

    def log_verification(self, event: VerificationEvent) -> None:
        """인간 검증 판정 이벤트 기록."""
        s_dir = self.get_session_dir(event.session_id)
        ver_path = os.path.join(s_dir, "verifications.jsonl")
        with open(ver_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

        # If corrected, also log in corrections.jsonl
        if event.corrected_value is not None or event.human_verdict == HumanVerdict.EDITED:
            corr_path = os.path.join(s_dir, "corrections.jsonl")
            with open(corr_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def save_error_snapshot(
        self,
        session_id: str,
        timestamp_sec: float,
        frame_current: np.ndarray,
        frame_before: Optional[np.ndarray] = None,
        frame_after: Optional[np.ndarray] = None,
        current_obs: Optional[Dict[str, Any]] = None,
        state_diff: Optional[Dict[str, Any]] = None,
        action_event: Optional[Dict[str, Any]] = None,
        reason: Optional[ErrorReason] = None
    ) -> str:
        """[WRONG] 클릭 시 ±2초 전후 프레임 및 상태 JSON을 자동으로 영구 보존."""
        f_dir = self.get_session_frames_dir(session_id)
        snap_id = f"error_{int(timestamp_sec * 100):06d}"
        snap_dir = os.path.join(f_dir, snap_id)
        os.makedirs(snap_dir, exist_ok=True)

        # Save frames
        curr_path = os.path.join(snap_dir, "frame_current.png")
        cv2.imwrite(curr_path, frame_current)

        if frame_before is not None:
            cv2.imwrite(os.path.join(snap_dir, "frame_before.png"), frame_before)
        if frame_after is not None:
            cv2.imwrite(os.path.join(snap_dir, "frame_after.png"), frame_after)

        # Save diagnostic JSONs
        diag_path = os.path.join(snap_dir, "error_diagnostics.json")
        diag_data = {
            "session_id": session_id,
            "timestamp_sec": round(timestamp_sec, 3),
            "error_reason": reason.value if reason else "OTHER",
            "current_observation": current_obs,
            "state_diff": state_diff,
            "action_event": action_event
        }
        with open(diag_path, "w", encoding="utf-8") as f:
            json.dump(diag_data, f, indent=2, ensure_ascii=False)

        return snap_dir

    def get_summary(self, session_id: str) -> VerificationSummary:
        """세션의 인간 검증 집계 통계 계산."""
        summary = VerificationSummary(session_id=session_id)
        s_dir = self.get_session_dir(session_id)
        ver_path = os.path.join(s_dir, "verifications.jsonl")

        if not os.path.exists(ver_path):
            return summary

        with open(ver_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    summary.total_reviewed += 1
                    v = data.get("human_verdict")
                    if v == HumanVerdict.CORRECT.value:
                        summary.correct_count += 1
                    elif v == HumanVerdict.WRONG.value:
                        summary.wrong_count += 1
                        r = data.get("error_reason", "OTHER")
                        summary.errors_by_reason[r] = summary.errors_by_reason.get(r, 0) + 1
                        t = data.get("target_type", "OTHER")
                        summary.errors_by_target[t] = summary.errors_by_target.get(t, 0) + 1
                    elif v == HumanVerdict.UNKNOWN.value:
                        summary.unknown_count += 1
                    elif v == HumanVerdict.SKIPPED.value:
                        summary.skipped_count += 1
                    elif v == HumanVerdict.EDITED.value:
                        summary.correct_count += 1

        return summary

    def export_ground_truth(
        self,
        session_id: str,
        output_path: Optional[str] = None
    ) -> str:
        """인간이 직접 확인/수정한 검증 데이터만을 추출하여 순수 Ground Truth 데이터셋 빌드."""
        s_dir = self.get_session_dir(session_id)
        ver_path = os.path.join(s_dir, "verifications.jsonl")
        out_file = output_path or os.path.join(self.ground_truth_dir, f"gt_{session_id.lower()}.json")

        gt_events = []
        if os.path.exists(ver_path):
            with open(ver_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        v = data.get("human_verdict")
                        if v in [HumanVerdict.CORRECT.value, HumanVerdict.EDITED.value]:
                            val = data.get("corrected_value") or data.get("human_label") or data.get("predicted_value")
                            gt_events.append({
                                "timestamp_sec": data.get("timestamp_sec"),
                                "target_type": data.get("target_type"),
                                "verified_value": val,
                                "human_verdict": v,
                                "notes": data.get("notes")
                            })

        gt_dataset = {
            "session_id": session_id,
            "total_verified_samples": len(gt_events),
            "events": gt_events
        }

        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(gt_dataset, f, indent=2, ensure_ascii=False)

        return out_file
