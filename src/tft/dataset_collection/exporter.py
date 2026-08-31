"""Dataset Exporter for TFT Real Match Decision Dataset Collection v1.

Compiles session data into canonical final_dataset.jsonl and convenience final_dataset.csv
under data/decision_dataset/datasets/DECISION_DATASET_V1/.
"""
from __future__ import annotations
import csv
import json
import os
import time
from typing import Any, Dict, List, Optional

from tft.dataset_collection.models import DatasetRow, SessionManifest
from tft.dataset_collection.session_manager import SessionManager


class DatasetExporter:
    """Exports compiled dataset across sessions into JSONL and CSV."""

    def __init__(self, base_dir: Optional[str] = None):
        _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        self.dataset_root = base_dir or os.path.join(_root, "data", "decision_dataset")
        self.sessions_dir = os.path.join(self.dataset_root, "sessions")
        self.export_dir = os.path.join(self.dataset_root, "datasets", "DECISION_DATASET_V1")
        self.session_mgr = SessionManager(base_dir=self.sessions_dir)
        os.makedirs(self.export_dir, exist_ok=True)

    def export_all(self, session_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Loads all sessions and compiles final_dataset.jsonl and final_dataset.csv."""
        target_sessions = session_ids or self.session_mgr.list_sessions()
        all_rows: List[DatasetRow] = []
        manifests: List[SessionManifest] = []

        for s_id in target_sessions:
            man = self.session_mgr.load_manifest(s_id)
            if man:
                manifests.append(man)
            # Ensure outcomes are linked before exporting
            self.session_mgr.link_outcomes(s_id)
            rows = self.session_mgr.load_all_session_rows(s_id)
            all_rows.extend(rows)

        # 1. Export JSONL (canonical)
        jsonl_path = os.path.join(self.export_dir, "final_dataset.jsonl")
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for row in all_rows:
                f.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")

        # 2. Export CSV (convenience)
        csv_path = os.path.join(self.export_dir, "final_dataset.csv")
        fieldnames = [
            "session_id", "match_id", "checkpoint_id", "video_timestamp_sec",
            "quality_flag", "stage_round", "hp", "gold", "level", "xp", "streak",
            "board_units_count", "bench_units_count",
            "board_power", "pair_count", "immediate_shop_upgrades",
            "estimated_rounds_to_elim", "stage_benchmark_ratio", "gold_to_next_level",
            "spendable_roll_budget", "recent_hp_delta",
            "recommended_action", "action_score_gap",
            "actual_player_action", "actual_action_source",
            "human_preferred_action", "human_confidence", "blind_review", "human_judgment",
            "t1_checkpoint_id", "t1_hp", "hp_delta", "t1_gold", "gold_delta",
            "t2_checkpoint_id", "t2_hp", "t2_hp_delta"
        ]

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in all_rows:
                raw = r.raw_state
                feat = r.derived_features
                pred = r.engine_prediction
                act = r.actual_action
                rev = r.human_review
                out = r.t1_outcome
                writer.writerow({
                    "session_id": r.session_id,
                    "match_id": r.match_id,
                    "checkpoint_id": r.checkpoint_id,
                    "video_timestamp_sec": r.video_timestamp_sec,
                    "quality_flag": r.quality_flag,
                    "stage_round": raw.get("stage_round", ""),
                    "hp": raw.get("hp", 100),
                    "gold": raw.get("gold", 0),
                    "level": raw.get("level", 1),
                    "xp": raw.get("xp", 0),
                    "streak": raw.get("streak", 0),
                    "board_units_count": len(raw.get("board_units", [])),
                    "bench_units_count": len(raw.get("bench_units", [])),
                    "board_power": feat.get("board_power", 0.0),
                    "pair_count": feat.get("pair_count", 0),
                    "immediate_shop_upgrades": feat.get("immediate_shop_upgrades", 0),
                    "estimated_rounds_to_elim": feat.get("estimated_rounds_to_elim"),
                    "stage_benchmark_ratio": feat.get("stage_benchmark_ratio", 1.0),
                    "gold_to_next_level": feat.get("gold_to_next_level", 0),
                    "spendable_roll_budget": feat.get("spendable_roll_budget", 0),
                    "recent_hp_delta": feat.get("recent_hp_delta"),
                    "recommended_action": pred.get("recommended_action", ""),
                    "action_score_gap": pred.get("action_score_gap", 0.0),
                    "actual_player_action": act.get("actual_player_action", "UNKNOWN"),
                    "actual_action_source": act.get("source", "HUMAN_VIDEO_REVIEW"),
                    "human_preferred_action": rev.get("human_preferred_action", "UNKNOWN"),
                    "human_confidence": rev.get("human_confidence", "UNKNOWN"),
                    "blind_review": rev.get("blind_review", False),
                    "human_judgment": rev.get("human_judgment", "UNKNOWN"),
                    "t1_checkpoint_id": out.get("t1_checkpoint_id"),
                    "t1_hp": out.get("t1_hp"),
                    "hp_delta": out.get("hp_delta"),
                    "t1_gold": out.get("t1_gold"),
                    "gold_delta": out.get("gold_delta"),
                    "t2_checkpoint_id": out.get("t2_checkpoint_id"),
                    "t2_hp": out.get("t2_hp"),
                    "t2_hp_delta": out.get("t2_hp_delta")
                })

        # Manifest
        export_manifest = {
            "dataset_version": "DECISION_DATASET_V1",
            "exported_at": time.time(),
            "total_sessions": len(target_sessions),
            "total_checkpoints": len(all_rows),
            "jsonl_path": jsonl_path,
            "csv_path": csv_path
        }
        with open(os.path.join(self.export_dir, "export_manifest.json"), "w", encoding="utf-8") as f:
            json.dump(export_manifest, f, indent=2, ensure_ascii=False)

        return export_manifest
