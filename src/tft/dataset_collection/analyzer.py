"""Dataset Analyzer for TFT Real Match Decision Dataset Collection v1.

Generates:
- data/decision_dataset/reports/dataset_distribution.json
- data/decision_dataset/reports/dataset_quality.json
- data/decision_dataset/reports/dataset_summary.md
"""
from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Optional

from tft.dataset_collection.models import DatasetRow, SessionManifest
from tft.dataset_collection.session_manager import SessionManager
from tft.dataset_collection.integrity_validator import IntegrityValidator


class DatasetAnalyzer:
    """Computes distributions, quality metrics, and generates markdown summary reports."""

    def __init__(self, base_dir: Optional[str] = None):
        _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        self.dataset_root = base_dir or os.path.join(_root, "data", "decision_dataset")
        self.sessions_dir = os.path.join(self.dataset_root, "sessions")
        self.datasets_dir = os.path.join(self.dataset_root, "datasets", "DECISION_DATASET_V1")
        self.reports_dir = os.path.join(self.dataset_root, "reports")
        self.session_mgr = SessionManager(base_dir=self.sessions_dir)
        self.validator = IntegrityValidator()
        os.makedirs(self.reports_dir, exist_ok=True)

    def load_rows_from_jsonl(self, jsonl_path: Optional[str] = None) -> List[DatasetRow]:
        p = jsonl_path or os.path.join(self.datasets_dir, "final_dataset.jsonl")
        if not os.path.exists(p):
            return []
        rows = []
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    rows.append(DatasetRow(
                        schema_version=d.get("schema_version", "DECISION_DATASET_V1"),
                        session_id=d.get("session_id", ""),
                        match_id=d.get("match_id", ""),
                        checkpoint_id=d.get("checkpoint_id", ""),
                        video_timestamp_sec=d.get("video_timestamp_sec"),
                        frame_index=d.get("frame_index"),
                        quality_flag=d.get("quality_flag", "VALID"),
                        raw_state=d.get("raw_state", {}),
                        derived_features=d.get("derived_features", {}),
                        engine_prediction=d.get("engine_prediction", {}),
                        actual_action=d.get("actual_action", {}),
                        human_review=d.get("human_review", {}),
                        t1_outcome=d.get("t1_outcome", {}),
                        interaction_log=d.get("interaction_log", {})
                    ))
        return rows

    def analyze_and_report(self) -> Dict[str, Any]:
        """Runs full analysis on current dataset and exports reports."""
        sessions = self.session_mgr.list_sessions()
        manifests = [self.session_mgr.load_manifest(s) for s in sessions if self.session_mgr.load_manifest(s)]

        rows = self.load_rows_from_jsonl()
        if not rows:
            # Fallback to loading directly from sessions
            for s_id in sessions:
                rows.extend(self.session_mgr.load_all_session_rows(s_id))

        # 1. State diversity
        diversity = self.validator.compute_state_diversity(rows)
        with open(os.path.join(self.reports_dir, "dataset_distribution.json"), "w", encoding="utf-8") as f:
            json.dump(diversity, f, indent=2, ensure_ascii=False)

        # 2. Quality & Gate
        gate = self.validator.evaluate_calibration_gate(manifests, rows)
        with open(os.path.join(self.reports_dir, "dataset_quality.json"), "w", encoding="utf-8") as f:
            json.dump(gate, f, indent=2, ensure_ascii=False)

        # 3. Generate Markdown summary
        md = self._generate_markdown_summary(manifests, rows, diversity, gate)
        with open(os.path.join(self.reports_dir, "dataset_summary.md"), "w", encoding="utf-8") as f:
            f.write(md)

        return {
            "total_matches": gate["total_matches"],
            "total_sessions": gate["total_sessions"],
            "total_checkpoints": gate["total_checkpoints"],
            "final_gate_verdict": gate["final_gate_verdict"]
        }

    def _generate_markdown_summary(
        self,
        manifests: List[SessionManifest],
        rows: List[DatasetRow],
        diversity: Dict[str, Any],
        gate: Dict[str, Any]
    ) -> str:
        verdict = gate["final_gate_verdict"]
        n_matches = gate["total_matches"]
        n_cps = gate["total_checkpoints"]

        md = f"""# TFT Real Match Decision Dataset Collection v1 — Summary Report

## Final Gate Status: `{verdict}`

> **Current Readiness**: {gate['honest_recommendation']}
> **Strict Principle**: Zero synthetic checkpoints used as real data. Zero model-to-human label auto-copying.

---

## 1. Dataset Overview

| Metric | Current Value | Min Target (Calibration) | Recommended Target (Production) |
|---|---|---|---|
| Independent Matches | **{n_matches}** | 5 | 20 |
| Total Sessions | **{len(manifests)}** | 5 | 20 |
| Total Checkpoints | **{n_cps}** | 75 | 400 |
| Actual Action Coverage | **{gate['actual_action_coverage']:.1%}** | ≥ 80.0% | ≥ 95.0% |
| Human Preference Coverage | **{gate['human_preference_coverage']:.1%}** | ≥ 80.0% | ≥ 95.0% |
| T1 Outcome Coverage | **{gate['t1_outcome_coverage']:.1%}** | ≥ 70.0% | ≥ 90.0% |
| Fake Data Detected | **{gate['fake_data_summary']['total_suspicious_checkpoints']}** | 0 | 0 |

---

## 2. Session Manifests

| Session ID | Match ID | Video File | Resolution | FPS | Total CPs | Placement |
|---|---|---|---|---|---|---|
"""
        for m in manifests:
            v = m.video
            p = m.final_placement if m.final_placement is not None else "In Progress"
            md += f"| `{m.session_id}` | `{m.match_id}` | `{v.filename}` | {v.resolution} | {v.fps:.0f} | {m.total_checkpoints} | {p} |\n"

        md += f"""
---

## 3. State Diversity Distributions

### HP Distribution
"""
        for k, v in diversity.get("hp_distribution", {}).items():
            md += f"- **{k}**: {v} ({v / max(1, n_cps):.1%})\n"

        md += f"""
### Gold Distribution
"""
        for k, v in diversity.get("gold_distribution", {}).items():
            md += f"- **{k}**: {v} ({v / max(1, n_cps):.1%})\n"

        md += f"""
### Action Distributions

| Action | Actual Player Actions | Human Preference Actions |
|---|---|---|
"""
        all_acts = set(list(diversity.get("actual_action_distribution", {}).keys()) +
                       list(diversity.get("human_preference_distribution", {}).keys()))
        for act in sorted(list(all_acts)):
            act_cnt = diversity.get("actual_action_distribution", {}).get(act, 0)
            pref_cnt = diversity.get("human_preference_distribution", {}).get(act, 0)
            md += f"| `{act}` | {act_cnt} ({act_cnt / max(1, n_cps):.1%}) | {pref_cnt} ({pref_cnt / max(1, n_cps):.1%}) |\n"

        md += f"""
---

## 4. Calibration Ready Gate Checklist

| Requirement | Target | Actual | Passed? |
|---|---|---|---|
| Matches ≥ 5 | ≥ 5 | {n_matches} | {'✅' if gate['checklist']['matches_ge_5'] else '❌ (In Progress)'} |
| Checkpoints per match ≥ 15 | ≥ 15 | Verified | {'✅' if gate['checklist']['checkpoints_per_match_ge_15'] else '❌'} |
| Early / Mid / Late Coverage | Stages 2, 3-4, 5+ | Verified | {'✅' if gate['checklist']['early_mid_late_stage_coverage'] else '❌'} |
| Actual Action Coverage | ≥ 80% | {gate['actual_action_coverage']:.1%} | {'✅' if gate['checklist']['actual_action_coverage_ge_80pct'] else '❌'} |
| Human Preference Coverage | ≥ 80% | {gate['human_preference_coverage']:.1%} | {'✅' if gate['checklist']['human_preference_coverage_ge_80pct'] else '❌'} |
| T1 Outcome Linked | ≥ 70% | {gate['t1_outcome_coverage']:.1%} | {'✅' if gate['checklist']['t1_outcome_linked_ge_70pct'] else '❌'} |
| No Fake Data / Contamination | 0 flags | {gate['fake_data_summary']['total_suspicious_checkpoints']} flags | {'✅' if gate['checklist']['no_fake_data_or_leakage'] else '❌'} |

---

## 5. Next Steps for Data Acquisition

1. **Continue Human Entry**: Use Web Decision Assistant (`run_decision_assistant.py`) to record additional 4+ real matches from TFT video recordings.
2. **Conduct Blind Reviews**: Maintain minimum 25% blind review quota during live input.
3. **Link Outcomes**: Finalize sessions upon match conclusion to lock `final_placement` and link T1/T2 HP and gold deltas.
4. **Trigger Calibration**: Once `Matches >= 5`, transition status to `DATASET_CALIBRATION_READY` and initiate offline A/B calibration.
"""
        return md
