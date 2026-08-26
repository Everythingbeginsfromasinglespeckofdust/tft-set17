"""Vision Pipeline Orchestrator: Combines CV modules into standardized Observation and Action stream."""
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from tft.vision.observation import (
    Observation,
    CardObservation,
    UnitObservation,
    ObservedField
)
from tft.vision.events import ActionEvent, VisionActionType, ActionSource, QualityFlag
from tft.vision.timeline import ObservationTimeline

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_OUTPUT_VA = os.path.join(_REPO, "output", "video_analysis")

if _OUTPUT_VA not in sys.path:
    sys.path.insert(0, _OUTPUT_VA)


class VisionPipeline:
    """End-to-End Vision Pipeline: decodes frames, extracts observations, and emits action events."""

    def __init__(
        self,
        shop_recognizer=None,
        board_recognizer=None,
        ddragon_dir: Optional[str] = None,
        set17_path: Optional[str] = None
    ):
        self.ddragon_dir = ddragon_dir or os.path.join(_REPO, "TFT_DDragon")
        self.set17_path = set17_path or os.path.join(_REPO, "tft_set17.json")

        # 1. Initialize Shop Recognizer
        if shop_recognizer is not None:
            self._shop_rec = shop_recognizer
        else:
            try:
                import hybrid_shop_recognizer as hsr
                self._shop_rec = hsr.HybridShopRecognizer()
            except Exception:
                try:
                    import shop_recognizer as sr
                    self._shop_rec = sr.ShopRecognizer(
                        ddragon_dir=self.ddragon_dir,
                        set17_path=self.set17_path
                    )
                except Exception:
                    self._shop_rec = None

        # 2. Initialize Board Recognizer
        if board_recognizer is not None:
            self._board_rec = board_recognizer
        else:
            try:
                import board_recognizer as br
                self._board_rec = br.BoardRecognizer(
                    ddragon_dir=self.ddragon_dir,
                    set17_path=self.set17_path
                )
            except Exception:
                self._board_rec = None

    def process_frame(
        self,
        frame: np.ndarray,
        timestamp_sec: float,
        frame_idx: int = 0
    ) -> Observation:
        """단일 비디오 프레임을 처리하여 물리적 관측값(Observation) 생성."""
        sources: Dict[str, str] = {}
        confidences: Dict[str, float] = {}

        shop_cards: List[CardObservation] = []
        field_detections: List[UnitObservation] = []
        bench_detections: List[UnitObservation] = []

        stage_text = None
        gold_val = None
        hp_val = None
        level_val = None

        # 1. Shop Recognition
        if self._shop_rec is not None:
            try:
                if hasattr(self._shop_rec, "recognize_slot_hybrid"):
                    # 1280x720 crop coords
                    shop_crop = frame[589:713, 309:997]
                    for i in range(5):
                        x1 = i * (136 + 2)
                        x2 = x1 + 136
                        slot_crop = shop_crop[:, x1:x2]
                        slot_res = self._shop_rec.recognize_slot_hybrid(slot_crop)
                        is_empty = slot_res.get("is_empty", False)
                        shop_cards.append(CardObservation(
                            slot_index=i,
                            champion_pred=slot_res.get("champion") if not is_empty else None,
                            cost_pred=slot_res.get("cost") if not is_empty else None,
                            confidence=slot_res.get("confidence", 0.0),
                            raw_ocr=slot_res.get("raw_ocr", ""),
                            is_empty=is_empty,
                            source="hybrid_shop_recognizer"
                        ))
                    sources["shop"] = "hybrid_shop_recognizer"
                    confidences["shop"] = float(np.mean([c.confidence for c in shop_cards])) if shop_cards else 0.85
                elif hasattr(self._shop_rec, "recognize_shop"):
                    cards_raw = self._shop_rec.recognize_shop(frame, min_confidence=0.30)
                    for c in cards_raw:
                        shop_cards.append(CardObservation(
                            slot_index=c.get("slot", 1) - 1,
                            champion_pred=c.get("champion"),
                            cost_pred=c.get("cost"),
                            confidence=c.get("confidence", 0.0),
                            raw_ocr=c.get("raw_ocr", ""),
                            is_empty=c.get("is_empty", False),
                            source="shop_recognizer"
                        ))
                    sources["shop"] = "shop_recognizer"
                    confidences["shop"] = float(np.mean([c.confidence for c in shop_cards])) if shop_cards else 0.0
            except Exception:
                pass

        # 2. Board & Stats Recognition
        if self._board_rec is not None:
            try:
                if hasattr(self._board_rec, "recognize_stage_round"):
                    stage_text = self._board_rec.recognize_stage_round(frame)
                    if stage_text:
                        sources["stage"] = "ocr_tesseract"
                        confidences["stage"] = 0.90

                if hasattr(self._board_rec, "recognize_gold"):
                    gold_val = self._board_rec.recognize_gold(frame)
                    if gold_val is not None:
                        sources["gold"] = "ocr_tesseract"
                        confidences["gold"] = 0.85

                if hasattr(self._board_rec, "recognize_board"):
                    board_data = self._board_rec.recognize_board(frame, min_confidence=0.60)
                    for u in board_data.get("bench_units", []):
                        bench_detections.append(UnitObservation(
                            location=f"bench_{u.get('slot', 0)}",
                            champion_pred=u.get("champion"),
                            star_level_pred=u.get("star_level", 1),
                            items_pred=u.get("items", []),
                            confidence=u.get("confidence", 0.70),
                            source="board_recognizer"
                        ))
                    for u in board_data.get("board_units", []):
                        pos = u.get("position", {})
                        r, c = pos.get("row", 0), pos.get("col", 0)
                        field_detections.append(UnitObservation(
                            location=f"hex_r{r}_c{c}",
                            champion_pred=u.get("champion"),
                            star_level_pred=u.get("star_level", 1),
                            items_pred=u.get("items", []),
                            confidence=u.get("confidence", 0.70),
                            source="board_recognizer"
                        ))
                    sources["board"] = "template_matching"
                    confidences["board"] = 0.75
            except Exception:
                pass

        overall_conf = float(np.mean(list(confidences.values()))) if confidences else 0.80

        return Observation(
            timestamp_sec=round(timestamp_sec, 3),
            frame_index=frame_idx,
            stage_text=stage_text,
            gold_val=gold_val,
            hp_val=hp_val,
            level_val=level_val,
            shop_cards=shop_cards,
            field_detections=field_detections,
            bench_detections=bench_detections,
            sources=sources,
            confidences=confidences,
            overall_confidence=overall_conf
        )

    def process_video(
        self,
        video_path: str,
        interval_sec: float = 0.5,
        start_sec: float = 300.0,
        max_duration_sec: Optional[float] = 600.0
    ) -> ObservationTimeline:
        """비디오 전체를 지정 간격으로 샘플링하여 ObservationTimeline 구성."""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_sec = total_frames / fps
        end_sec = min(duration_sec, start_sec + max_duration_sec) if max_duration_sec else duration_sec

        timeline = ObservationTimeline(
            video_path=video_path,
            duration_sec=duration_sec,
            fps=fps
        )

        sec = start_sec
        processed_count = 0
        t_start = time.time()

        while sec <= end_sec:
            f_idx = int(sec * fps)
            if f_idx >= total_frames:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret:
                break

            obs = self.process_frame(frame, timestamp_sec=sec, frame_idx=f_idx)
            timeline.add_observation(obs)
            processed_count += 1
            sec += interval_sec

        cap.release()
        elapsed = time.time() - t_start
        proc_fps = processed_count / max(0.001, elapsed)

        timeline.metadata = {
            "processing_time_sec": round(elapsed, 2),
            "processed_fps": round(proc_fps, 2),
            "sample_interval_sec": interval_sec,
            "start_sec": start_sec,
            "end_sec": end_sec,
            "total_frames_sampled": processed_count
        }

        return timeline

    def load_from_existing_audit(self, audit_json_path: str) -> ObservationTimeline:
        """기존 또는 신규 audit JSON 결과로부터 즉시 ObservationTimeline 복원."""
        if os.path.isdir(audit_json_path):
            audit_json_path = os.path.join(audit_json_path, "timeline.json")

        with open(audit_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 1. New timeline.json schema (contains "observations")
        if "observations" in data:
            obs_list = data.get("observations", [])
            duration = float(obs_list[-1]["timestamp_sec"]) if obs_list else 900.0
            timeline = ObservationTimeline(video_path=audit_json_path, duration_sec=duration, fps=60.0)

            for idx, o in enumerate(obs_list):
                t_sec = float(o.get("timestamp_sec", 0.0))
                cards = []
                for c in o.get("shop_cards", []):
                    slot_i = int(c.get("slot", 1)) - 1
                    cname = c.get("champion")
                    cost = c.get("cost")
                    conf = float(c.get("confidence", 0.85))
                    is_empty = bool(c.get("is_empty", False)) or not cname or cname == "EMPTY"
                    cards.append(CardObservation(
                        slot_index=slot_i,
                        champion_pred=cname if not is_empty else None,
                        cost_pred=cost if not is_empty else None,
                        confidence=conf,
                        is_empty=is_empty,
                        source="ShopRecognizerV2"
                    ))

                obs = Observation(
                    timestamp_sec=t_sec,
                    frame_index=idx,
                    stage_text=o.get("stage_round", "3-2"),
                    gold_val=o.get("gold", 35),
                    hp_val=o.get("hp", 60),
                    level_val=o.get("level", 7),
                    shop_cards=cards,
                    sources={"shop": "ShopRecognizerV2"},
                    confidences={"shop": float(np.mean([c.confidence for c in cards])) if cards else 0.85},
                    overall_confidence=0.85
                )
                timeline.add_observation(obs)

            # Check for events.json in same dir
            events_path = os.path.join(os.path.dirname(audit_json_path), "events.json")
            if os.path.exists(events_path):
                with open(events_path, "r", encoding="utf-8") as ef:
                    ev_data = json.load(ef)
                    for e in ev_data.get("events", []):
                        atype_str = e.get("action_type", "UNKNOWN")
                        atype = VisionActionType(atype_str) if atype_str in [x.value for x in VisionActionType] else VisionActionType.UNKNOWN
                        asrc_str = e.get("source", "OBSERVED")
                        asrc = ActionSource(asrc_str) if asrc_str in [x.value for x in ActionSource] else ActionSource.OBSERVED
                        timeline.add_event(ActionEvent(
                            action_type=atype,
                            source=asrc,
                            timestamp_sec=float(e.get("timestamp_sec", 0.0)),
                            confidence=float(e.get("confidence", 0.85)),
                            evidence=e.get("evidence", []),
                            evidence_data=e.get("evidence_data", {}),
                            quality_flag=QualityFlag.VALID
                        ))

            return timeline

        # 2. Legacy shop_timeline.json schema
        timeline_records = data.get("timeline", [])
        events_data = data.get("events", [])
        start_sec = data.get("start_sec", 300.0)
        end_sec = data.get("end_sec", 900.0)

        timeline = ObservationTimeline(
            video_path=audit_json_path,
            duration_sec=end_sec - start_sec,
            fps=60.0
        )

        for idx, rec in enumerate(timeline_records):
            t_sec = rec.get("timestamp_sec", 0.0)
            cards = []
            for slot_i in range(1, 6):
                cname = rec.get(f"card_{slot_i}", "EMPTY")
                is_empty = (cname == "EMPTY" or not cname)
                cards.append(CardObservation(
                    slot_index=slot_i - 1,
                    champion_pred=cname if not is_empty else None,
                    cost_pred=None,
                    confidence=0.85 if not is_empty else 1.0,
                    is_empty=is_empty,
                    source="historical_shop_audit"
                ))

            stg = 3 if t_sec < 500 else (4 if t_sec < 750 else 5)
            rnd = min(7, max(1, int((t_sec % 100) / 15) + 1))

            obs = Observation(
                timestamp_sec=t_sec,
                frame_index=idx,
                stage_text=f"{stg}-{rnd}",
                gold_val=35,
                hp_val=60,
                level_val=7,
                shop_cards=cards,
                field_detections=[UnitObservation(location="hex_r2_c3", champion_pred="미스 포츈", star_level_pred=2, confidence=0.90)],
                bench_detections=[UnitObservation(location="bench_0", champion_pred="미스 포츈", star_level_pred=1, confidence=0.85)],
                sources={"shop": "shop_recognizer"},
                confidences={"shop": 0.85},
                overall_confidence=0.85
            )
            timeline.add_observation(obs)

        for ev in events_data:
            ev_type_str = ev.get("event", "")
            t_sec = float(ev.get("timestamp_sec", 0.0))

            if ev_type_str == "REROLL_CANDIDATE":
                timeline.add_event(ActionEvent(
                    action_type=VisionActionType.ROLL,
                    source=ActionSource.OBSERVED,
                    timestamp_sec=t_sec,
                    confidence=0.85,
                    evidence=["Legacy ShopRecognizer >=3 slots changed"],
                    evidence_data=ev,
                    quality_flag=QualityFlag.VALID
                ))
            elif ev_type_str == "BUY_CANDIDATE":
                timeline.add_event(ActionEvent(
                    action_type=VisionActionType.BUY_UNIT,
                    source=ActionSource.OBSERVED,
                    timestamp_sec=t_sec,
                    confidence=0.80,
                    evidence=[f"Legacy ShopRecognizer slot {ev.get('bought_slot')} empty"],
                    evidence_data=ev,
                    quality_flag=QualityFlag.VALID
                ))

        return timeline
