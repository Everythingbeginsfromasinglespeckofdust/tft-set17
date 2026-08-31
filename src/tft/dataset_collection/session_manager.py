"""Session Manager for TFT Real Match Decision Dataset Collection v1.

Manages session lifecycle, strict folder separation (raw, checkpoints, reviews, outcomes),
SHA256 video verification, and outcome linkage.
"""
from __future__ import annotations
import glob
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.dataset_collection.models import (
    SessionManifest,
    VideoMetadata,
    RawState,
    UnitState,
    DerivedFeatures,
    EnginePrediction,
    ActualPlayerAction,
    HumanReview,
    T1Outcome,
    InteractionLog,
    DatasetRow,
    QualityFlagEnum
)
from tft.dataset_collection.derived_features import DerivedFeaturesCalculator


def compute_file_sha256(filepath: str) -> str:
    """Computes SHA-256 hash of a file if it exists, else returns empty string."""
    if not os.path.exists(filepath):
        return ""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536 * 16):
            h.update(chunk)
    return h.hexdigest()


class SessionManager:
    """Manages collection sessions under data/decision_dataset/sessions/."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            self.base_dir = os.path.join(_root, "data", "decision_dataset", "sessions")
        else:
            self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self.derived_calc = DerivedFeaturesCalculator()

    def get_session_dir(self, session_id: str) -> str:
        return os.path.join(self.base_dir, session_id)

    def list_sessions(self) -> List[str]:
        if not os.path.exists(self.base_dir):
            return []
        return sorted([
            d for d in os.listdir(self.base_dir)
            if os.path.isdir(os.path.join(self.base_dir, d))
        ])

    def create_session(
        self,
        session_id: str,
        match_id: Optional[str] = None,
        video_filename: str = "",
        video_path: Optional[str] = None,
        video_sha256: str = "",
        resolution: str = "1920x1080",
        fps: float = 60.0,
        total_frames: Optional[int] = None,
        duration_sec: Optional[float] = None,
        patch: str = "14.x_18.1",
        set_num: int = 18,
        notes: str = ""
    ) -> SessionManifest:
        """Creates a new collection session with directory structure."""
        s_dir = self.get_session_dir(session_id)
        os.makedirs(s_dir, exist_ok=True)
        os.makedirs(os.path.join(s_dir, "raw"), exist_ok=True)
        os.makedirs(os.path.join(s_dir, "checkpoints"), exist_ok=True)
        os.makedirs(os.path.join(s_dir, "reviews"), exist_ok=True)
        os.makedirs(os.path.join(s_dir, "outcomes"), exist_ok=True)

        sha = video_sha256
        if not sha and video_path and os.path.exists(video_path):
            sha = compute_file_sha256(video_path)

        v_meta = VideoMetadata(
            filename=video_filename or (os.path.basename(video_path) if video_path else ""),
            video_path=video_path,
            sha256=sha,
            resolution=resolution,
            fps=fps,
            total_frames=total_frames,
            duration_sec=duration_sec
        )

        manifest = SessionManifest(
            session_id=session_id,
            match_id=match_id or session_id,
            video=v_meta,
            patch=patch,
            set_num=set_num,
            total_checkpoints=0,
            final_placement=None,
            created_at=time.time(),
            last_updated=time.time(),
            notes=notes
        )

        manifest_path = os.path.join(s_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)

        return manifest

    def load_manifest(self, session_id: str) -> Optional[SessionManifest]:
        manifest_path = os.path.join(self.get_session_dir(session_id), "manifest.json")
        if not os.path.exists(manifest_path):
            return None
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SessionManifest.from_dict(data)

    def save_manifest(self, manifest: SessionManifest) -> None:
        manifest.last_updated = time.time()
        manifest_path = os.path.join(self.get_session_dir(manifest.session_id), "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)

    def save_checkpoint(
        self,
        session_id: str,
        raw_state: RawState,
        prediction: EnginePrediction,
        actual_action: ActualPlayerAction,
        human_review: HumanReview,
        derived_features: Optional[DerivedFeatures] = None,
        interaction_log: Optional[InteractionLog] = None,
        screenshot_path: Optional[str] = None
    ) -> str:
        """Saves a multi-part checkpoint maintaining folder separation."""
        s_dir = self.get_session_dir(session_id)
        cp_id = raw_state.checkpoint_id

        # 1. Calculate derived features if not provided
        if derived_features is None:
            # Construct standard GameState for calculation
            gst = self._raw_to_gamestate(raw_state)
            derived_features = self.derived_calc.calculate(gst, sample_id=cp_id)

        # 2. Save raw state
        raw_cp_dir = os.path.join(s_dir, "raw", cp_id)
        os.makedirs(raw_cp_dir, exist_ok=True)
        with open(os.path.join(raw_cp_dir, "state.json"), "w", encoding="utf-8") as f:
            json.dump(raw_state.to_dict(), f, indent=2, ensure_ascii=False)

        if interaction_log:
            with open(os.path.join(raw_cp_dir, "interaction_log.json"), "w", encoding="utf-8") as f:
                json.dump(interaction_log.to_dict(), f, indent=2, ensure_ascii=False)

        # 3. Save canonical checkpoint
        cp_dir = os.path.join(s_dir, "checkpoints", cp_id)
        os.makedirs(cp_dir, exist_ok=True)
        with open(os.path.join(cp_dir, "state.json"), "w", encoding="utf-8") as f:
            json.dump(raw_state.to_dict(), f, indent=2, ensure_ascii=False)
        with open(os.path.join(cp_dir, "prediction.json"), "w", encoding="utf-8") as f:
            json.dump(prediction.to_dict(), f, indent=2, ensure_ascii=False)
        with open(os.path.join(cp_dir, "derived_features.json"), "w", encoding="utf-8") as f:
            json.dump(derived_features.to_dict(), f, indent=2, ensure_ascii=False)
        with open(os.path.join(cp_dir, "actual_action.json"), "w", encoding="utf-8") as f:
            json.dump(actual_action.to_dict(), f, indent=2, ensure_ascii=False)

        # 4. Save review
        rev_dir = os.path.join(s_dir, "reviews", cp_id)
        os.makedirs(rev_dir, exist_ok=True)
        with open(os.path.join(rev_dir, "human_review.json"), "w", encoding="utf-8") as f:
            json.dump(human_review.to_dict(), f, indent=2, ensure_ascii=False)

        # Update manifest checkpoint count
        manifest = self.load_manifest(session_id)
        if manifest:
            total_cps = len(glob.glob(os.path.join(s_dir, "checkpoints", "CP*")))
            manifest.total_checkpoints = total_cps
            self.save_manifest(manifest)

        return cp_id

    def link_outcomes(self, session_id: str) -> int:
        """Links sequential checkpoints (T0 -> T1, T0 -> T2) with HP and gold deltas."""
        s_dir = self.get_session_dir(session_id)
        cp_dirs = sorted(glob.glob(os.path.join(s_dir, "checkpoints", "CP*")))
        if not cp_dirs:
            return 0

        # Load all checkpoint states
        cps_data = []
        for d in cp_dirs:
            cp_id = os.path.basename(d)
            st_path = os.path.join(d, "state.json")
            if os.path.exists(st_path):
                with open(st_path, "r", encoding="utf-8") as f:
                    st = json.load(f)
                feat_path = os.path.join(d, "derived_features.json")
                bp = 0.0
                if os.path.exists(feat_path):
                    with open(feat_path, "r", encoding="utf-8") as ff:
                        feat = json.load(ff)
                        bp = feat.get("board_power", 0.0)
                cps_data.append({"cp_id": cp_id, "state": st, "board_power": bp})

        outcomes_dir = os.path.join(s_dir, "outcomes")
        os.makedirs(outcomes_dir, exist_ok=True)

        linked_count = 0
        n = len(cps_data)
        for i in range(n):
            curr = cps_data[i]
            cp_id = curr["cp_id"]
            curr_hp = curr["state"].get("hp", 100)
            curr_gold = curr["state"].get("gold", 0)

            t1_id, t1_sr, t1_hp, t1_gold, t1_bp, hp_delta, gold_delta = None, None, None, None, None, None, None
            t2_id, t2_hp, t2_hp_delta = None, None, None

            if i + 1 < n:
                t1 = cps_data[i + 1]
                t1_id = t1["cp_id"]
                t1_sr = t1["state"].get("stage_round")
                t1_hp = t1["state"].get("hp")
                t1_gold = t1["state"].get("gold")
                t1_bp = t1["board_power"]
                if t1_hp is not None:
                    hp_delta = t1_hp - curr_hp
                if t1_gold is not None:
                    gold_delta = t1_gold - curr_gold

            if i + 2 < n:
                t2 = cps_data[i + 2]
                t2_id = t2["cp_id"]
                t2_hp = t2["state"].get("hp")
                if t2_hp is not None:
                    t2_hp_delta = t2_hp - curr_hp

            outcome = T1Outcome(
                checkpoint_id=cp_id,
                t1_checkpoint_id=t1_id,
                t1_stage_round=t1_sr,
                t1_hp=t1_hp,
                t1_gold=t1_gold,
                t1_board_power=t1_bp,
                hp_delta=hp_delta,
                gold_delta=gold_delta,
                t2_checkpoint_id=t2_id,
                t2_hp=t2_hp,
                t2_hp_delta=t2_hp_delta,
                horizon_rounds=1 if t1_id else 0
            )

            cp_outcome_dir = os.path.join(outcomes_dir, cp_id)
            os.makedirs(cp_outcome_dir, exist_ok=True)
            with open(os.path.join(cp_outcome_dir, "outcome.json"), "w", encoding="utf-8") as f:
                json.dump(outcome.to_dict(), f, indent=2, ensure_ascii=False)
            linked_count += 1

        return linked_count

    def finalize_session(self, session_id: str, final_placement: int, notes: str = "") -> SessionManifest:
        """Sets final placement strictly after session completion."""
        manifest = self.load_manifest(session_id)
        if not manifest:
            raise FileNotFoundError(f"Session {session_id} not found")
        manifest.final_placement = int(final_placement)
        if notes:
            manifest.notes = (manifest.notes + "\n" + notes).strip()
        self.save_manifest(manifest)
        self.link_outcomes(session_id)
        return manifest

    def load_all_session_rows(self, session_id: str) -> List[DatasetRow]:
        """Assembles DatasetRows from separated folders for a session."""
        s_dir = self.get_session_dir(session_id)
        manifest = self.load_manifest(session_id)
        match_id = manifest.match_id if manifest else session_id

        cp_dirs = sorted(glob.glob(os.path.join(s_dir, "checkpoints", "CP*")))
        rows = []
        for d in cp_dirs:
            cp_id = os.path.basename(d)

            # Raw state
            raw_path = os.path.join(s_dir, "raw", cp_id, "state.json")
            if not os.path.exists(raw_path):
                raw_path = os.path.join(d, "state.json")
            raw_st = {}
            if os.path.exists(raw_path):
                with open(raw_path, "r", encoding="utf-8") as f:
                    raw_st = json.load(f)

            # Prediction
            pred_path = os.path.join(d, "prediction.json")
            pred = {}
            if os.path.exists(pred_path):
                with open(pred_path, "r", encoding="utf-8") as f:
                    pred = json.load(f)

            # Derived features
            feat_path = os.path.join(d, "derived_features.json")
            feat = {}
            if os.path.exists(feat_path):
                with open(feat_path, "r", encoding="utf-8") as f:
                    feat = json.load(f)

            # Actual action
            act_path = os.path.join(d, "actual_action.json")
            act = {}
            if os.path.exists(act_path):
                with open(act_path, "r", encoding="utf-8") as f:
                    act = json.load(f)

            # Review
            rev_path = os.path.join(s_dir, "reviews", cp_id, "human_review.json")
            rev = {}
            if os.path.exists(rev_path):
                with open(rev_path, "r", encoding="utf-8") as f:
                    rev = json.load(f)

            # Outcome
            out_path = os.path.join(s_dir, "outcomes", cp_id, "outcome.json")
            out = {}
            if os.path.exists(out_path):
                with open(out_path, "r", encoding="utf-8") as f:
                    out = json.load(f)

            # Interaction log
            ilog_path = os.path.join(s_dir, "raw", cp_id, "interaction_log.json")
            ilog = {}
            if os.path.exists(ilog_path):
                with open(ilog_path, "r", encoding="utf-8") as f:
                    ilog = json.load(f)

            row = DatasetRow(
                schema_version="DECISION_DATASET_V1",
                session_id=session_id,
                match_id=match_id,
                checkpoint_id=cp_id,
                video_timestamp_sec=raw_st.get("video_timestamp_sec"),
                frame_index=raw_st.get("frame_index"),
                quality_flag=QualityFlagEnum.VALID.value,
                raw_state=raw_st,
                derived_features=feat,
                engine_prediction=pred,
                actual_action=act,
                human_review=rev,
                t1_outcome=out,
                interaction_log=ilog
            )
            rows.append(row)
        return rows

    def _raw_to_gamestate(self, raw: RawState) -> GameState:
        board_u = [
            Unit(champion=u.name, cost=u.cost, star_level=u.star, items=list(u.items))
            for u in raw.board_units
        ]
        bench_u = [
            Unit(champion=u.name, cost=u.cost, star_level=u.star, items=list(u.items), is_bench=True)
            for u in raw.bench_units
        ]
        return GameState(
            stage=raw.stage,
            round=raw.round_num,
            stage_round=raw.stage_round,
            player=PlayerState(gold=raw.gold, level=raw.level, xp=raw.xp, hp=raw.hp, streak=raw.streak),
            board_units=board_u,
            bench_units=bench_u,
            shop_units=list(raw.shop_units),
            item_bench=list(raw.item_bench),
            augments=list(raw.augments)
        )
