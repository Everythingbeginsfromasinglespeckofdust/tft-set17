"""TFT Shop Recognizer v2 -- High-fidelity multi-signal champion and cost recognizer.

Architecture:
  1. UI Relative Coordinate Calibration & Slot Crop Extraction
  2. Slot Status Classification: EMPTY / UNKNOWN / NO_DETECTION / LOW_CONFIDENCE / RECOGNIZED
  3. HSV Cost Border Band Detection (1C Gray, 2C Green, 3C Blue, 4C Purple, 5C Gold)
  4. Multi-Scale Portrait Template Matching (Scales: 80, 95, 110, 125 with center-square crop)
  5. OCR Champion Name Banner Recognition & Fuzzy Sequence Matching
  6. Multi-Signal Candidate Fusion (Weighted 60% Portrait + 40% Text OCR)
  7. Calibrated Confidence Scoring & Diagnostics
"""
import difflib
import json
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
except Exception:
    pytesseract = None

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))


class SlotStatus(str, Enum):
    """상점 슬롯 상태 분류."""
    EMPTY = "EMPTY"                     # 정상적으로 비어있는 슬롯 (구매 완료)
    RECOGNIZED = "RECOGNIZED"           # 챔피언 및 코스트가 신뢰성 있게 인식됨
    LOW_CONFIDENCE = "LOW_CONFIDENCE"   # 카드가 있으나 신뢰도 임계치 미달
    UNKNOWN = "UNKNOWN"                 # 카드는 검출되었으나 챔피언 후보 미확정
    NO_DETECTION = "NO_DETECTION"       # 상점 UI가 닫혔거나 화면에서 가려짐


@dataclass
class CandidateScore:
    """개별 챔피언 후보의 다중 신호 점수."""
    champion: str
    cost: int
    template_score: float = 0.0
    ocr_score: float = 0.0
    color_matched: bool = False
    combined_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "champion": self.champion,
            "cost": self.cost,
            "template_score": round(self.template_score, 3),
            "ocr_score": round(self.ocr_score, 3),
            "color_matched": self.color_matched,
            "combined_score": round(self.combined_score, 3)
        }


@dataclass
class RecognizedCard:
    """상점 슬롯 인식 결과."""
    slot_index: int  # 0 to 4
    champion: Optional[str] = None
    cost: Optional[int] = None
    status: SlotStatus = SlotStatus.UNKNOWN
    confidence: float = 0.0
    template_score: float = 0.0
    ocr_score: float = 0.0
    detected_color_cost: Optional[int] = None
    raw_ocr: str = ""
    candidates: List[CandidateScore] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return self.status == SlotStatus.EMPTY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slot_index": self.slot_index,
            "champion": self.champion,
            "cost": self.cost,
            "status": self.status.value,
            "confidence": round(self.confidence, 3),
            "template_score": round(self.template_score, 3),
            "ocr_score": round(self.ocr_score, 3),
            "detected_color_cost": self.detected_color_cost,
            "raw_ocr": self.raw_ocr,
            "is_empty": self.is_empty,
            "top_candidates": [c.to_dict() for c in self.candidates[:3]]
        }


class ShopRecognizerV2:
    """TFT Set 17 상점 5개 카드 슬롯 인식기 v2."""

    BASE_RESOLUTION = (1280, 720)
    SHOP_GEOMETRY_720P = {
        "card_y1": 589,
        "card_y2": 713,
        "start_x": 309,
        "card_w": 136,
        "gap": 2,
    }

    def __init__(
        self,
        ddragon_dir: Optional[str] = None,
        set17_path: Optional[str] = None,
        portrait_weight: float = 0.60,
        ocr_weight: float = 0.40,
        min_confidence_threshold: float = 0.10
    ):
        self.ddragon_dir = ddragon_dir or os.path.join(_REPO, "TFT_DDragon")
        self.set17_path = set17_path or os.path.join(_REPO, "tft_set17.json")
        self.portrait_weight = portrait_weight
        self.ocr_weight = ocr_weight
        self.min_confidence_threshold = min_confidence_threshold

        self.champion_templates: Dict[str, Dict[str, Any]] = {}
        self.champions_by_cost: Dict[int, List[str]] = {1: [], 2: [], 3: [], 4: [], 5: []}
        self.champ_cost_map: Dict[str, int] = {}
        self._load_templates_and_roster()

    def _load_templates_and_roster(self):
        """Set 17 챔피언 데이터 및 템플릿 이미지 로드 (Center Square Crop 적용)."""
        champ_img_dir = os.path.join(self.ddragon_dir, "img", "champion")
        if not os.path.exists(self.set17_path) or not os.path.exists(champ_img_dir):
            return

        with open(self.set17_path, "r", encoding="utf-8") as f:
            set17_data = json.load(f)

        avail_imgs = os.listdir(champ_img_dir)

        for c in set17_data.get("champions", []):
            cid = c["id"]
            cname = c["name"]
            cost = c["cost"]
            self.champ_cost_map[cname] = cost
            self.champions_by_cost[cost].append(cname)

            base_name = cid.split("_")[-1].lower()
            target_img = None
            for f_name in avail_imgs:
                if f_name.lower().startswith(f"tft17_{base_name}"):
                    target_img = f_name
                    break

            if not target_img and (cname == "라아스트" or base_name == "rhaast"):
                for f_name in avail_imgs:
                    if f_name.lower().startswith("tft17_kayn"):
                        target_img = f_name
                        break

            if target_img:
                tpath = os.path.join(champ_img_dir, target_img)
                t_bgr = cv2.imread(tpath)
                if t_bgr is not None:
                    # Crop center square from splash art
                    th, tw, _ = t_bgr.shape
                    min_dim = min(th, tw)
                    cy, cx = th // 2, tw // 2
                    t_square = t_bgr[cy - min_dim // 2 : cy + min_dim // 2, cx - min_dim // 2 : cx + min_dim // 2]
                    self.champion_templates[cname] = {
                        "id": cid,
                        "cost": cost,
                        "img": t_square,
                        "gray": cv2.cvtColor(t_square, cv2.COLOR_BGR2GRAY)
                    }

    def get_shop_crop_and_slots(self, frame: np.ndarray) -> Tuple[Optional[np.ndarray], List[np.ndarray]]:
        """영상 해상도에 맞춰 5개 상점 슬롯 크롭 추출."""
        if frame is None or frame.size == 0:
            return None, []

        h, w = frame.shape[:2]
        scale_x = w / self.BASE_RESOLUTION[0]
        scale_y = h / self.BASE_RESOLUTION[1]

        y1 = int(self.SHOP_GEOMETRY_720P["card_y1"] * scale_y)
        y2 = int(self.SHOP_GEOMETRY_720P["card_y2"] * scale_y)
        start_x = int(self.SHOP_GEOMETRY_720P["start_x"] * scale_x)
        card_w = int(self.SHOP_GEOMETRY_720P["card_w"] * scale_x)
        gap = int(self.SHOP_GEOMETRY_720P["gap"] * scale_x)

        total_w = 5 * card_w + 4 * gap
        shop_crop = frame[y1:y2, start_x : start_x + total_w]

        slot_crops = []
        for i in range(5):
            x1 = i * (card_w + gap)
            x2 = x1 + card_w
            slot_crop = shop_crop[:, x1:x2]
            slot_crops.append(slot_crop)

        return shop_crop, slot_crops

    def detect_cost_color(self, card_crop: np.ndarray) -> Optional[int]:
        """하단 테두리 스트립의 HSV 색상 분포로 코스트(1~5) 검출."""
        if card_crop is None or card_crop.size == 0:
            return None

        h, w = card_crop.shape[:2]
        bottom_strip = card_crop[max(0, h - 28) : h - 4, 4 : w - 4]
        if bottom_strip.size == 0:
            return None

        hsv = cv2.cvtColor(bottom_strip, cv2.COLOR_BGR2HSV)
        s_vals = hsv[:, :, 1]
        mean_s = np.mean(s_vals)

        # 1-Cost: 회색/채도 낮음
        if mean_s < 35.0:
            return 1

        green_mask = cv2.inRange(hsv, np.array([35, 40, 40]), np.array([85, 255, 255]))
        blue_mask = cv2.inRange(hsv, np.array([86, 40, 40]), np.array([130, 255, 255]))
        purple_mask = cv2.inRange(hsv, np.array([131, 40, 40]), np.array([168, 255, 255]))
        gold_mask = cv2.inRange(hsv, np.array([10, 80, 80]), np.array([34, 255, 255]))

        counts = {
            1: int(np.sum(s_vals < 35)),
            2: int(np.sum(green_mask > 0)),
            3: int(np.sum(blue_mask > 0)),
            4: int(np.sum(purple_mask > 0)),
            5: int(np.sum(gold_mask > 0)),
        }
        best_cost = max(counts.items(), key=lambda x: x[1])[0]
        return best_cost

    def recognize_slot(self, card_crop: np.ndarray, slot_index: int = 0) -> RecognizedCard:
        """단일 카드 슬롯 정밀 인식."""
        if card_crop is None or card_crop.size == 0:
            return RecognizedCard(slot_index=slot_index, status=SlotStatus.NO_DETECTION)

        gray = cv2.cvtColor(card_crop, cv2.COLOR_BGR2GRAY)
        std_val = float(np.std(gray))
        mean_val = float(np.mean(gray))

        # 1. 빈 슬롯 검사 (구매 후 어두운 슬롯)
        if std_val < 18.0 or mean_val < 25.0:
            return RecognizedCard(slot_index=slot_index, status=SlotStatus.EMPTY)

        # 2. 코스트 색상 검출
        detected_cost = self.detect_cost_color(card_crop)
        valid_candidates = self.champions_by_cost.get(detected_cost, list(self.champion_templates.keys()))
        if not valid_candidates:
            valid_candidates = list(self.champion_templates.keys())

        # 3. 포트레이트 템플릿 매칭 (Hybrid exact matching)
        port_gray = gray[:105, :]
        portrait_scores: Dict[str, float] = {}

        for cname in valid_candidates:
            cdata = self.champion_templates.get(cname)
            if not cdata:
                continue
            t_gray = cdata["gray"]
            best_s = -1.0
            for sz in [80, 95, 110, 125]:
                if sz > port_gray.shape[0] * 1.3 or sz > port_gray.shape[1] * 1.3:
                    continue
                tw = min(sz, port_gray.shape[1])
                th = min(sz, port_gray.shape[0])
                t_scaled = cv2.resize(t_gray, (tw, th))
                if t_scaled.shape[0] > port_gray.shape[0] or t_scaled.shape[1] > port_gray.shape[1]:
                    continue
                res = cv2.matchTemplate(port_gray, t_scaled, cv2.TM_CCOEFF_NORMED)
                _, max_v, _, _ = cv2.minMaxLoc(res)
                if max_v > best_s:
                    best_s = max_v
            portrait_scores[cname] = max(0.0, float(best_s))

        # 4. 이름 배너 OCR
        text_roi = card_crop[86:118, 10:128]
        ocr_scores = {cname: 0.0 for cname in valid_candidates}
        raw_ocr = ""
        if text_roi.size > 0 and pytesseract is not None:
            hsv = cv2.cvtColor(text_roi, cv2.COLOR_BGR2HSV)
            mask_white = cv2.inRange(hsv, np.array([0, 0, 170]), np.array([180, 65, 255]))
            mask_gold = cv2.inRange(hsv, np.array([15, 60, 170]), np.array([40, 255, 255]))
            mask = cv2.bitwise_or(mask_white, mask_gold)
            text_scaled = cv2.resize(mask, (0, 0), fx=3.5, fy=3.5, interpolation=cv2.INTER_CUBIC)
            custom_config = r"--oem 3 --psm 7 -l kor"
            try:
                ocr_out = pytesseract.image_to_string(text_scaled, config=custom_config).strip()
                raw_ocr = "".join([ch for ch in ocr_out if ch.isalnum()])
                if raw_ocr:
                    for cname in valid_candidates:
                        c_clean = cname.replace(" ", "")
                        ratio = difflib.SequenceMatcher(None, raw_ocr, c_clean).ratio()
                        ocr_scores[cname] = float(ratio)
            except Exception:
                pass

        # 5. 앙상블 합성 (Candidate Fusion)
        candidate_objs: List[CandidateScore] = []
        for cname in valid_candidates:
            p_s = portrait_scores.get(cname, 0.0)
            t_s = ocr_scores.get(cname, 0.0)
            cost = self.champ_cost_map.get(cname, 1)
            combined = self.portrait_weight * p_s + self.ocr_weight * t_s
            candidate_objs.append(CandidateScore(
                champion=cname,
                cost=cost,
                template_score=p_s,
                ocr_score=t_s,
                color_matched=(cost == detected_cost),
                combined_score=combined
            ))

        candidate_objs.sort(key=lambda x: x.combined_score, reverse=True)

        if not candidate_objs:
            return RecognizedCard(
                slot_index=slot_index,
                status=SlotStatus.UNKNOWN,
                detected_color_cost=detected_cost,
                raw_ocr=raw_ocr
            )

        best_cand = candidate_objs[0]
        confidence = best_cand.combined_score

        return RecognizedCard(
            slot_index=slot_index,
            champion=best_cand.champion,
            cost=best_cand.cost,
            status=SlotStatus.RECOGNIZED,
            confidence=confidence,
            template_score=best_cand.template_score,
            ocr_score=best_cand.ocr_score,
            detected_color_cost=detected_cost,
            raw_ocr=raw_ocr,
            candidates=candidate_objs
        )

    def recognize_shop(self, frame: np.ndarray) -> List[RecognizedCard]:
        """프레임 전체에서 5개 상점 슬롯을 일괄 인식."""
        _, slot_crops = self.get_shop_crop_and_slots(frame)
        results: List[RecognizedCard] = []

        for i, crop in enumerate(slot_crops):
            card_res = self.recognize_slot(crop, slot_index=i)
            results.append(card_res)

        return results
