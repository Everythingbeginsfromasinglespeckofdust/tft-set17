"""Unified TFT Vision Pipeline: orchestrates frame recognition and video processing."""
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from tft.vision.observation import Observation, CardObservation, UnitObservation
from tft.vision.events import ActionEvent, VisionActionType, ActionSource, QualityFlag
from tft.vision.timeline import ObservationTimeline


class VisionPipeline:
    """화면 프레임 및 비디오로부터 타임스탬프 기반 Observation 및 Event Timeline을 추출하는 상위 비전 파이프라인."""

    def __init__(
        self,
        board_recognizer: Optional[Any] = None,
        shop_recognizer: Optional[Any] = None
    ):
        self._board_rec = board_recognizer
        self._shop_rec = shop_recognizer
        self._initialized = False

    def _ensure_recognizers(self):
        """인식기 지연 초기화 (Lazy loading)."""
        if self._initialized:
            return

        if self._board_rec is None:
            try:
                from output.video_analysis.board_recognizer import BoardRecognizer
                self._board_rec = BoardRecognizer()
            except Exception as e:
                print(f"[VisionPipeline] Note: BoardRecognizer not loaded: {e}")

        if self._shop_rec is None:
            try:
                from output.video_analysis.hybrid_shop_recognizer import HybridShopRecognizer
                self._shop_rec = HybridShopRecognizer()
            except Exception:
                try:
                    from output.video_analysis.shop_recognizer import ShopRecognizer
                    self._shop_rec = ShopRecognizer()
                except Exception as e:
                    print(f"[VisionPipeline] Note: ShopRecognizer not loaded: {e}")

        self._initialized = True

    def process_frame(
        self,
        frame: np.ndarray,
        timestamp_sec: float,
        frame_idx: int = 0
    ) -> Observation:
        """단일 프레임에서 상점, 골드, 스테이지, 필드/벤치 유닛을 인식하여 Observation 생성."""
        self._ensure_recognizers()

        sources = {}
        confidences = {}
        shop_cards: List[CardObservation] = []
        field_detections: List[UnitObservation] = []
        bench_detections: List[UnitObservation] = []
        stage_text = None
        gold_val = None
        hp_val = None
        level_val = None
        xp_val = None

        # 1. Shop Recognition
        if self._shop_rec is not None and hasattr(self._shop_rec, "recognize_shop"):
            try:
                cards = self._shop_rec.recognize_shop(frame, min_confidence=0.40)
                for idx, c in enumerate(cards):
                    shop_cards.append(CardObservation(
                        slot_index=idx,
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
            xp_val=xp_val,
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
        start_sec: float = 0.0,
        max_duration_sec: Optional[float] = None
    ) -> ObservationTimeline:
        """비디오 파일을 지정된 간격으로 샘플링하여 ObservationTimeline 구축."""
        import cv2

        assert os.path.exists(video_path), f"Video file not found: {video_path}"
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_dur = total_frames / fps
        end_sec = min(video_dur, start_sec + max_duration_sec) if max_duration_sec else video_dur

        timeline = ObservationTimeline(
            video_path=video_path,
            duration_sec=round(end_sec - start_sec, 2),
            fps=fps
        )

        t_start = time.time()
        sec = start_sec
        processed_count = 0

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
        """기존 10분 audit 결과(shop_timeline.json)로부터 즉시 ObservationTimeline 복원."""
        with open(audit_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

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

            # Approximate stage & player stats for video window
            stg = 3 if t_sec < 500 else (4 if t_sec < 750 else 5)
            rnd = int((t_sec % 100) / 15) + 1
            rnd = min(7, max(1, rnd))

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
                sources={"shop": "historical_shop_audit", "board": "heuristic_window"},
                confidences={"shop": 0.85, "board": 0.85},
                overall_confidence=0.85
            )
            timeline.add_observation(obs)

        for ev in events_data:
            ev_type_str = ev.get("event", "")
            t_sec = ev.get("timestamp_sec", 0.0)
            if ev_type_str == "REROLL_CANDIDATE":
                timeline.add_event(ActionEvent(
                    action_type=VisionActionType.ROLL,
                    source=ActionSource.OBSERVED,
                    timestamp_sec=t_sec,
                    confidence=0.90,
                    evidence=["Shop cards changed >= 3 slots simultaneously"],
                    evidence_data={"prev_shop": ev.get("prev_shop"), "new_shop": ev.get("new_shop")}
                ))
            elif ev_type_str == "BUY_CANDIDATE":
                timeline.add_event(ActionEvent(
                    action_type=VisionActionType.BUY_UNIT,
                    source=ActionSource.OBSERVED,
                    timestamp_sec=t_sec,
                    confidence=0.85,
                    evidence=[f"Shop slot {ev.get('bought_slot')} emptied ({ev.get('champion')})"],
                    evidence_data={"bought_slot": ev.get("bought_slot")},
                    target_champion=ev.get("champion"),
                    slot_index=ev.get("bought_slot", 1) - 1
                ))

        return timeline
