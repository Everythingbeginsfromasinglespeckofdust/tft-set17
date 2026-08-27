"""Persistence and storage engine for TFT Decision Validation Overlay."""
import json
import os
from typing import Any, Dict, List, Optional

from tft.decision.validation_models import (
    DecisionValidationRecord,
    DecisionFailureCase,
    HumanEngineJudgment,
    HumanPreference,
    DecisionFailureReason
)


class DecisionValidationStore:
    """Decision Validation 데이터의 격리 저장소 (Predictions, Reviews, Outcomes, Failure Cases)."""

    def __init__(self, base_dir: str = "data/decision_validation"):
        self.base_dir = base_dir
        self.sessions_dir = os.path.join(self.base_dir, "sessions")
        self.outcomes_dir = os.path.join(self.base_dir, "outcomes")
        self.failure_cases_dir = os.path.join(self.base_dir, "failure_cases")
        self.ground_truth_dir = os.path.join(self.base_dir, "ground_truth")
        self.reports_dir = os.path.join(self.base_dir, "reports")

        for d in [self.sessions_dir, self.outcomes_dir, self.failure_cases_dir, self.ground_truth_dir, self.reports_dir]:
            os.makedirs(d, exist_ok=True)

    def get_session_dir(self, session_id: str) -> str:
        s_dir = os.path.join(self.sessions_dir, session_id)
        os.makedirs(s_dir, exist_ok=True)
        return s_dir

    def log_prediction(self, session_id: str, record: DecisionValidationRecord) -> None:
        """DecisionEngine의 원본 추천 결과를 predictions.jsonl에 불변 기록."""
        s_dir = self.get_session_dir(session_id)
        p_path = os.path.join(s_dir, "predictions.jsonl")
        with open(p_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def log_decision_review(self, session_id: str, record: DecisionValidationRecord) -> None:
        """인간의 DecisionEngine 판단 및 Blind 선호도를 decision_reviews.jsonl에 기록."""
        s_dir = self.get_session_dir(session_id)
        r_path = os.path.join(s_dir, "decision_reviews.jsonl")
        with open(r_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def save_failure_case(self, case: DecisionFailureCase) -> str:
        """결함 진단 케이스를 failure_cases/ 디렉토리에 저장."""
        f_path = os.path.join(self.failure_cases_dir, f"fail_{case.failure_id}.json")
        with open(f_path, "w", encoding="utf-8") as f:
            json.dump(case.to_dict(), f, indent=2, ensure_ascii=False)
        return f_path

    def export_human_decision_labels(self, session_id: Optional[str] = None, output_path: Optional[str] = None) -> str:
        """인간이 검토한 Decision Label만 독립 추출 (human_decision_labels.jsonl)."""
        out_file = output_path or os.path.join(self.ground_truth_dir, "human_decision_labels.jsonl")
        os.makedirs(os.path.dirname(out_file), exist_ok=True)

        exported_count = 0
        with open(out_file, "w", encoding="utf-8") as out_f:
            target_sessions = [session_id] if session_id else os.listdir(self.sessions_dir)
            for s in target_sessions:
                r_path = os.path.join(self.sessions_dir, s, "decision_reviews.jsonl")
                if os.path.exists(r_path):
                    with open(r_path, "r", encoding="utf-8") as in_f:
                        for line in in_f:
                            if line.strip():
                                row = json.loads(line)
                                hr = row.get("human_review", {})
                                if hr.get("human_judgment") or hr.get("human_preference"):
                                    out_row = {
                                        "record_id": row.get("record_id"),
                                        "session_id": row.get("session_id"),
                                        "timestamp_sec": row.get("timestamp_sec"),
                                        "observed_state": row.get("observed_state"),
                                        "actual_player_action": row.get("actual_player_action"),
                                        "engine_recommendation": row.get("recommendation", {}).get("recommended_action"),
                                        "human_judgment": hr.get("human_judgment"),
                                        "human_preference": hr.get("human_preference"),
                                        "reviewer_id": hr.get("reviewer_id")
                                    }
                                    out_f.write(json.dumps(out_row, ensure_ascii=False) + "\n")
                                    exported_count += 1
        return out_file
