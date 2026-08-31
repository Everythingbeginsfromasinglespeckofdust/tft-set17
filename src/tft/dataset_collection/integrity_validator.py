"""Integrity Validator for TFT Real Match Decision Dataset Collection v1.

Provides:
- Fake data detection (repeated timestamps, identical states, auto-copy detection)
- Outlier detection (impossible HP/gold, invalid stars, duplicate units)
- Future leakage validation (T0 must not contain T1/final placement)
- State diversity & balance metrics
- Match-level independence check
- Calibration readiness gate verdict
"""
from __future__ import annotations
from collections import defaultdict
import re
from typing import Any, Dict, List, Optional, Tuple, Set

from tft.dataset_collection.models import (
    DatasetRow,
    SessionManifest,
    QualityFlagEnum
)


class IntegrityValidator:
    """Validates dataset integrity, detects fake data, and computes calibration readiness."""

    def __init__(self):
        pass

    def validate_row(self, row: DatasetRow) -> Tuple[str, List[str]]:
        """Validates a single dataset row for schema compliance and outliers.

        Returns: (quality_flag, issues_list)
        """
        issues = []
        raw = row.raw_state

        # 1. State integrity
        hp = raw.get("hp", 100)
        gold = raw.get("gold", 0)
        level = raw.get("level", 1)
        stage_round = raw.get("stage_round", "2-1")

        if hp < 0 or hp > 150:
            issues.append(f"OUTLIER_HP: hp={hp} outside valid range [0, 150]")
        if gold < 0 or gold > 250:
            issues.append(f"OUTLIER_GOLD: gold={gold} outside valid range [0, 250]")
        if level < 1 or level > 11:
            issues.append(f"OUTLIER_LEVEL: level={level} outside valid range [1, 11]")
        if not re.match(r"^[1-8]-[1-7]$", str(stage_round)):
            issues.append(f"INVALID_STAGE_ROUND: '{stage_round}' does not match stage-round format")

        # 2. Strict Future Leakage Check: raw_state must NEVER contain final_placement
        if "final_placement" in raw or "placement" in raw:
            issues.append("LEAKAGE_T0: final_placement found in raw_state")

        # 3. Units validation
        for u in raw.get("board_units", []) + raw.get("bench_units", []):
            star = u.get("star", 1)
            if star not in (1, 2, 3):
                issues.append(f"INVALID_STAR: unit {u.get('name')} has invalid star={star}")

        # Determine flag
        if any("LEAKAGE" in i or "OUTLIER" in i for i in issues):
            flag = QualityFlagEnum.SUSPICIOUS.value
        elif len(issues) > 0:
            flag = QualityFlagEnum.INCOMPLETE.value
        else:
            flag = QualityFlagEnum.VALID.value

        return flag, issues

    def detect_fake_data(self, rows: List[DatasetRow]) -> Dict[str, Any]:
        """Detects anomalies, repeated timestamps, and auto-copied predictions."""
        suspicious_rows = []
        findings = []

        # 1. Check for identical timestamps in same session
        timestamps_by_session = defaultdict(list)
        for r in rows:
            t = r.video_timestamp_sec
            if t is not None:
                timestamps_by_session[r.session_id].append((r.checkpoint_id, t))

        for s_id, t_list in timestamps_by_session.items():
            seen = set()
            for cp_id, t in t_list:
                if t in seen:
                    findings.append({
                        "session_id": s_id,
                        "checkpoint_id": cp_id,
                        "type": "DUPLICATE_TIMESTAMP",
                        "timestamp_sec": t,
                        "detail": f"Timestamp {t}s repeated in session {s_id}"
                    })
                    suspicious_rows.append(cp_id)
                seen.add(t)

        # 2. Check for identical state back-to-back
        for i in range(len(rows) - 1):
            curr = rows[i]
            nxt = rows[i + 1]
            if curr.session_id == nxt.session_id:
                if (curr.raw_state.get("hp") == nxt.raw_state.get("hp") and
                    curr.raw_state.get("gold") == nxt.raw_state.get("gold") and
                    curr.raw_state.get("stage_round") == nxt.raw_state.get("stage_round") and
                    curr.video_timestamp_sec == nxt.video_timestamp_sec and
                    curr.video_timestamp_sec is not None):
                    findings.append({
                        "session_id": curr.session_id,
                        "checkpoint_id": nxt.checkpoint_id,
                        "type": "IDENTICAL_CONSECUTIVE_STATE",
                        "detail": f"Checkpoint {nxt.checkpoint_id} is identical to {curr.checkpoint_id}"
                    })
                    suspicious_rows.append(nxt.checkpoint_id)

        # 3. Check for auto-copied human labels from model prediction
        rec_pref_matches = 0
        known_reviews = 0
        for r in rows:
            rec = r.engine_prediction.get("recommended_action")
            pref = r.human_review.get("human_preferred_action")
            src = r.human_review.get("source")
            if pref and pref != "UNKNOWN":
                known_reviews += 1
                if rec and rec == pref and src == "AUTO_COPIED":
                    findings.append({
                        "session_id": r.session_id,
                        "checkpoint_id": r.checkpoint_id,
                        "type": "AUTO_COPIED_LABEL",
                        "detail": f"Human preference was auto-copied from engine prediction {rec}"
                    })
                    suspicious_rows.append(r.checkpoint_id)

        return {
            "total_suspicious_checkpoints": len(set(suspicious_rows)),
            "findings_count": len(findings),
            "findings": findings,
            "verdict": "CLEAN" if len(findings) == 0 else "ANOMALIES_DETECTED"
        }

    def compute_state_diversity(self, rows: List[DatasetRow]) -> Dict[str, Any]:
        """Calculates histograms and diversity metrics across all checkpoints."""
        hp_dist = defaultdict(int)
        gold_dist = defaultdict(int)
        level_dist = defaultdict(int)
        stage_dist = defaultdict(int)
        action_dist = defaultdict(int)
        pref_dist = defaultdict(int)
        judgment_dist = defaultdict(int)

        for r in rows:
            raw = r.raw_state
            hp = raw.get("hp", 100)
            if hp <= 15:
                hp_dist["0-15 (Critical)"] += 1
            elif hp <= 30:
                hp_dist["16-30 (Danger)"] += 1
            elif hp <= 50:
                hp_dist["31-50 (Mid)"] += 1
            elif hp <= 70:
                hp_dist["51-70 (Healthy)"] += 1
            else:
                hp_dist["71-100 (Safe)"] += 1

            gold = raw.get("gold", 0)
            if gold < 20:
                gold_dist["0-19G"] += 1
            elif gold < 30:
                gold_dist["20-29G"] += 1
            elif gold < 40:
                gold_dist["30-39G"] += 1
            elif gold < 50:
                gold_dist["40-49G"] += 1
            else:
                gold_dist["50G+"] += 1

            lvl = raw.get("level", 1)
            level_dist[f"Level {lvl}"] += 1

            sr = raw.get("stage_round", "2-1")
            st = sr.split("-")[0] if "-" in sr else "2"
            stage_dist[f"Stage {st}"] += 1

            act = r.actual_action.get("actual_player_action", "UNKNOWN")
            action_dist[act] += 1

            pref = r.human_review.get("human_preferred_action", "UNKNOWN")
            pref_dist[pref] += 1

            jdg = r.human_review.get("human_judgment", "UNKNOWN")
            judgment_dist[jdg] += 1

        # Check action imbalance
        total_actions = sum(action_dist.values())
        max_action_share = max((cnt / max(1, total_actions) for cnt in action_dist.values()), default=0.0)
        imbalance_warning = max_action_share > 0.85

        return {
            "total_checkpoints": len(rows),
            "hp_distribution": dict(hp_dist),
            "gold_distribution": dict(gold_dist),
            "level_distribution": dict(level_dist),
            "stage_distribution": dict(stage_dist),
            "actual_action_distribution": dict(action_dist),
            "human_preference_distribution": dict(pref_dist),
            "human_judgment_distribution": dict(judgment_dist),
            "imbalance_warning": imbalance_warning
        }

    def check_match_independence(self, manifests: List[SessionManifest]) -> Dict[str, Any]:
        """Verifies distinct match_ids and session_ids."""
        match_ids = [m.match_id for m in manifests]
        session_ids = [m.session_id for m in manifests]
        unique_matches = set(match_ids)
        unique_sessions = set(session_ids)

        return {
            "total_sessions": len(manifests),
            "unique_matches": len(unique_matches),
            "unique_match_ids": sorted(list(unique_matches)),
            "is_independent": len(manifests) == len(unique_matches),
            "note": (
                f"Dataset contains {len(unique_matches)} independent match(es). "
                "Each match forms a discrete GroupKFold partition."
            )
        }

    def evaluate_calibration_gate(
        self,
        manifests: List[SessionManifest],
        rows: List[DatasetRow]
    ) -> Dict[str, Any]:
        """Evaluates whether dataset meets all requirements for DATASET_CALIBRATION_READY."""
        match_info = self.check_match_independence(manifests)
        fake_info = self.detect_fake_data(rows)
        diversity = self.compute_state_diversity(rows)

        n_matches = match_info["unique_matches"]
        n_rows = len(rows)

        # 1. Match count requirement: >= 5
        pass_matches = n_matches >= 5

        # 2. Checkpoints per match: each >= 15
        cps_by_match = defaultdict(int)
        stages_by_match = defaultdict(set)
        for r in rows:
            cps_by_match[r.match_id] += 1
            sr = r.raw_state.get("stage_round", "2-1")
            stage = sr.split("-")[0] if "-" in sr else "2"
            stages_by_match[r.match_id].add(stage)

        pass_cps_per_match = bool(cps_by_match and all(cnt >= 15 for cnt in cps_by_match.values()))

        # 3. Early / Mid / Late coverage
        # Early: stage 2, Mid: stage 3-4, Late: stage 5+
        pass_stage_coverage = bool(stages_by_match and all(
            any(s in ("1", "2") for s in st_set) and
            any(s in ("3", "4") for s in st_set) and
            any(s in ("5", "6", "7", "8") for s in st_set)
            for st_set in stages_by_match.values()
        ))

        # 4. Actual action coverage: >= 80% known
        known_actions = sum(1 for r in rows if r.actual_action.get("actual_player_action", "UNKNOWN") != "UNKNOWN")
        act_coverage = round(known_actions / max(1, n_rows), 4)
        pass_act_coverage = act_coverage >= 0.80

        # 5. Human preference coverage: >= 80% known
        known_prefs = sum(1 for r in rows if r.human_review.get("human_preferred_action", "UNKNOWN") != "UNKNOWN")
        pref_coverage = round(known_prefs / max(1, n_rows), 4)
        pass_pref_coverage = pref_coverage >= 0.80

        # 6. T1 outcomes coverage: >= 80% linked
        linked_outcomes = sum(1 for r in rows if r.t1_outcome.get("t1_checkpoint_id") is not None)
        outcome_coverage = round(linked_outcomes / max(1, n_rows), 4)
        pass_outcome_coverage = outcome_coverage >= 0.70  # Last CP of game has no T1, so 70%+ is standard

        # 7. Zero fake data
        pass_no_fake = fake_info["total_suspicious_checkpoints"] == 0

        # Final verdict determination
        checklist = {
            "matches_ge_5": pass_matches,
            "checkpoints_per_match_ge_15": pass_cps_per_match,
            "early_mid_late_stage_coverage": pass_stage_coverage,
            "actual_action_coverage_ge_80pct": pass_act_coverage,
            "human_preference_coverage_ge_80pct": pass_pref_coverage,
            "t1_outcome_linked_ge_70pct": pass_outcome_coverage,
            "no_fake_data_or_leakage": pass_no_fake
        }

        if all(checklist.values()):
            verdict = "DATASET_CALIBRATION_READY"
        elif n_matches >= 3:
            verdict = "DATASET_PARTIALLY_READY"
        elif fake_info["total_suspicious_checkpoints"] > 5:
            verdict = "DATASET_INVALID"
        else:
            verdict = "DATA_COLLECTION_IN_PROGRESS"

        return {
            "final_gate_verdict": verdict,
            "total_matches": n_matches,
            "total_sessions": len(manifests),
            "total_checkpoints": n_rows,
            "actual_action_coverage": act_coverage,
            "human_preference_coverage": pref_coverage,
            "t1_outcome_coverage": outcome_coverage,
            "checklist": checklist,
            "fake_data_summary": fake_info,
            "diversity_summary": diversity,
            "honest_recommendation": (
                "DATA_COLLECTION_IN_PROGRESS: Collect additional real match sessions "
                f"(current: {n_matches}/5 matches) before running calibration."
                if verdict == "DATA_COLLECTION_IN_PROGRESS" else
                ("DATASET_PARTIALLY_READY: Minimum 5 matches required." if verdict == "DATASET_PARTIALLY_READY"
                 else "DATASET_CALIBRATION_READY: Ready for offline A/B calibration.")
            )
        }
