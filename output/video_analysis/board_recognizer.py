#!/usr/bin/env python3
"""TFT Set 17 보드 및 게임 상태 비전 인식기 (Board & Vision Recognizer v2).

주요 기능:
1. 스테이지-라운드 OCR (Tesseract + 다중 이진화)
2. 골드 OCR (HSV 색상 마스킹 H:12~38, S:60~255, V:60~255)
3. 벤치(9슬롯) 및 필드(28헥스) 챔피언 템플릿 매칭 (OpenCV MatchTemplate)
4. 유닛별 아이템 슬롯(최대 3개) DDragon 아이템 템플릿 매칭
5. 성급(1/2/3성) 별 개수 검출
6. 신뢰도 임계값 미달 시 명시적 'null/unknown' 처리 (임의 추측 금지)
"""
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import pytesseract

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUTPUT = os.path.dirname(_HERE)
_REPO = os.path.dirname(_OUTPUT)

# Windows Tesseract 경로 자동 탐색
_TESS_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
]
for tp in _TESS_PATHS:
    if os.path.exists(tp):
        pytesseract.pytesseract.tesseract_cmd = tp
        break

# 720p (1280x720) 기준 기본 ROI 좌표
DEFAULT_ROIS = {
    "stage_round": {"y1": 5, "y2": 45, "x1": 390, "x2": 530},
    "gold_bottom": {"y1": 685, "y2": 718, "x1": 460, "x2": 510},
    "level_xp": {"y1": 670, "y2": 715, "x1": 260, "x2": 340},
    "field": {"y1": 220, "y2": 500, "x1": 220, "x2": 1060},
    "bench": {"y1": 510, "y2": 590, "x1": 240, "x2": 1040},
}


class BoardRecognizer:
    """TFT 게임 화면 프레임으로부터 보드 상태와 UI 텍스트를 추출하는 비전 엔진."""

    def __init__(self, ddragon_dir: Optional[str] = None, set17_path: Optional[str] = None):
        self.ddragon_dir = ddragon_dir or os.path.join(_REPO, "TFT_DDragon")
        self.set17_path = set17_path or os.path.join(_REPO, "tft_set17.json")
        self.champion_templates: Dict[str, Dict[str, Any]] = {}
        self.item_templates: Dict[str, np.ndarray] = {}
        self._load_templates()

    def _load_templates(self):
        """Set 17 챔피언 및 아이템 템플릿 로드."""
        champ_img_dir = os.path.join(self.ddragon_dir, "img", "champion")
        item_img_dir = os.path.join(self.ddragon_dir, "img", "item")

        # 1. 챔피언 템플릿 로드
        if os.path.exists(self.set17_path) and os.path.exists(champ_img_dir):
            with open(self.set17_path, "r", encoding="utf-8") as f:
                set17_data = json.load(f)

            avail_imgs = os.listdir(champ_img_dir)
            avail_lower = {f.lower(): f for f in avail_imgs}

            for c in set17_data.get("champions", []):
                cid = c["id"]
                cname = c["name"]
                base_name = cid.split("_")[-1]

                target_img = None
                for cand in [
                    f"{cid}.png",
                    f"{base_name}.png",
                    f"TFT_{base_name}.png",
                    f"TFT15_{base_name}.png",
                    f"TFT16_{base_name}_splash_centered_0.png",
                ]:
                    if cand.lower() in avail_lower:
                        target_img = avail_lower[cand.lower()]
                        break

                if not target_img:
                    for f in avail_imgs:
                        if base_name.lower() in f.lower():
                            target_img = f
                            break

                if not target_img and cname == "라아스트":
                    target_img = avail_lower.get("tft15_kayn.png") or avail_lower.get("kayn.png")

                if target_img:
                    tpath = os.path.join(champ_img_dir, target_img)
                    t_bgr = cv2.imread(tpath)
                    if t_bgr is not None:
                        th, tw, _ = t_bgr.shape
                        min_dim = min(th, tw)
                        cy, cx = th // 2, tw // 2
                        t_square = t_bgr[cy - min_dim // 2 : cy + min_dim // 2, cx - min_dim // 2 : cx + min_dim // 2]
                        self.champion_templates[cname] = {
                            "img": t_square,
                            "cost": c["cost"],
                            "file": target_img,
                        }

        # 2. 주요 아이템 템플릿 로드 (DDragon/img/item)
        if os.path.exists(item_img_dir):
            common_items = [
                "BFSword", "RecurveBow", "NeedlesslyLargeRod", "TearOfTheGoddess",
                "ChainVest", "NegatronCloak", "GiantsBelt", "SparringGloves", "Spatula",
                "InfinityEdge", "Deathblade", "RabadonsDeathcap", "ArchangelsStaff",
                "Bloodthirster", "GuinsoosRageblade", "SunfireCape", "WarmogsArmor",
                "GargoyleStoneplate", "DragonClaw", "LastWhisper", "HandOfJustice",
                "JeweledGauntlet", "SpearOfShojin", "StatikkShiv", "TitansResolve"
            ]
            for it_file in os.listdir(item_img_dir):
                if it_file.endswith(".png"):
                    it_base = os.path.splitext(it_file)[0]
                    it_img = cv2.imread(os.path.join(item_img_dir, it_file))
                    if it_img is not None:
                        self.item_templates[it_base] = it_img

    def recognize_stage_round(self, frame: np.ndarray) -> Optional[str]:
        """스테이지-라운드 텍스트 인식 (예: '2-1', '2-5')."""
        roi_cfg = DEFAULT_ROIS["stage_round"]
        crop = frame[roi_cfg["y1"] : roi_cfg["y2"], roi_cfg["x1"] : roi_cfg["x2"]]
        if crop.size == 0:
            return None

        # 3배 보간 + 이진화
        resized = cv2.resize(crop, (0, 0), fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        
        # 1. Grayscale direct OCR
        txt_raw = pytesseract.image_to_string(gray, config="--psm 7 -c tessedit_char_whitelist=0123456789-").strip()
        matches = re.findall(r"\d-\d", txt_raw)
        if matches:
            return matches[0]

        # 2. Binary Thresholding OCR
        _, thresh = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
        txt_th = pytesseract.image_to_string(thresh, config="--psm 7 -c tessedit_char_whitelist=0123456789-").strip()
        matches_th = re.findall(r"\d-\d", txt_th)
        return matches_th[0] if matches_th else None

    def recognize_gold(self, frame: np.ndarray) -> Optional[int]:
        """HSV 색상 마스킹(노란색/흰색 분리)을 적용한 골드 수치 판독."""
        roi_cfg = DEFAULT_ROIS["gold_bottom"]
        crop = frame[roi_cfg["y1"] : roi_cfg["y2"], roi_cfg["x1"] : roi_cfg["x2"]]
        if crop.size == 0:
            return None

        crop_3x = cv2.resize(crop, (0, 0), fx=3.5, fy=3.5, interpolation=cv2.INTER_CUBIC)
        hsv = cv2.cvtColor(crop_3x, cv2.COLOR_BGR2HSV)

        # 1. 노란색/골드 색상 마스크 (H: 12~38, S: 60~255, V: 60~255)
        mask_yellow = cv2.inRange(hsv, np.array([12, 60, 60]), np.array([38, 255, 255]))
        # 2. 밝은 흰색 폰트 마스크
        mask_white = cv2.inRange(hsv, np.array([0, 0, 180]), np.array([180, 40, 255]))
        mask = cv2.bitwise_or(mask_yellow, mask_white)

        kernel = np.ones((2, 2), np.uint8)
        mask_clean = cv2.dilate(mask, kernel, iterations=1)

        txt = pytesseract.image_to_string(mask_clean, config="--psm 7 -c tessedit_char_whitelist=0123456789").strip()
        digits = re.findall(r"\d+", txt)
        if digits:
            val = int(digits[0])
            if 0 <= val <= 200:
                return val
        return None

    def detect_star_level(self, overhead_roi: np.ndarray) -> int:
        """기물 머리 위/체력바 상단의 별(Star) 개수 감지 (1, 2, 3성)."""
        if overhead_roi.size == 0:
            return 1

        gray = cv2.cvtColor(overhead_roi, cv2.COLOR_BGR2GRAY)
        # 밝은 별 픽셀 검출
        _, bright = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        star_count = 0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 3 <= area <= 60:
                star_count += 1

        if star_count >= 3:
            return 3
        elif star_count == 2:
            return 2
        return 1

    def match_unit_items(self, item_bar_roi: np.ndarray, min_confidence: float = 0.65) -> List[str]:
        """유닛 하단/체력바 하단 3개 아이템 슬롯 인식.
        
        Args:
            item_bar_roi: 유닛 체력바 하단의 아이템 표시 영역 (약 15x50px)
            min_confidence: 아이템 매칭 최소 상관계수
        Returns:
            인식된 아이템 리스트 (예: ['B.F. 대검', '무한의 대검'])
        """
        if item_bar_roi.size == 0 or not self.item_templates:
            return []

        h, w, _ = item_bar_roi.shape
        if w < 20 or h < 10:
            return []

        # 3개 슬롯으로 균등 분할
        slot_w = w // 3
        detected_items = []
        bar_gray = cv2.cvtColor(item_bar_roi, cv2.COLOR_BGR2GRAY)

        for s in range(3):
            sx1 = s * slot_w
            sx2 = sx1 + slot_w
            slot_crop = bar_gray[:, sx1:sx2]
            if slot_crop.shape[0] < 8 or slot_crop.shape[1] < 8:
                continue

            # 슬롯 내 분산이 너무 낮으면(단색/빈 슬롯) 스킵
            if np.std(slot_crop) < 18.0:
                continue

            best_score = -1.0
            best_item = None

            for iname, i_img in list(self.item_templates.items())[:50]:  # 주요 아이템 50종 매칭
                i_gray = cv2.cvtColor(i_img, cv2.COLOR_BGR2GRAY)
                i_scaled = cv2.resize(i_gray, (slot_crop.shape[1], slot_crop.shape[0]), interpolation=cv2.INTER_AREA)
                res = cv2.matchTemplate(slot_crop, i_scaled, cv2.TM_CCOEFF_NORMED)
                _, max_v, _, _ = cv2.minMaxLoc(res)
                if max_v > best_score:
                    best_score = max_v
                    best_item = iname

            if best_score >= min_confidence and best_item:
                detected_items.append(best_item)

        return detected_items

    def match_slot_champion(
        self, slot_img: np.ndarray, min_confidence: float = 0.60
    ) -> Tuple[Optional[str], Optional[int], float]:
        """특정 슬롯 이미지에서 가장 일치하는 챔피언 매칭.
        
        Returns:
            (champion_name, cost, confidence_score)
            신뢰도가 min_confidence 미만이면 (None, None, max_score) 반환.
        """
        if slot_img.size == 0 or not self.champion_templates:
            return None, None, 0.0

        slot_gray = cv2.cvtColor(slot_img, cv2.COLOR_BGR2GRAY)
        sh, sw = slot_gray.shape

        best_score = -1.0
        best_champ = None
        best_cost = None

        scales = [min(sh, sw), int(min(sh, sw) * 0.85), int(min(sh, sw) * 1.15)]

        for cname, cdata in self.champion_templates.items():
            t_gray = cv2.cvtColor(cdata["img"], cv2.COLOR_BGR2GRAY)
            for sz in scales:
                if sz <= 10 or sz > max(sh, sw) * 1.5:
                    continue
                t_scaled = cv2.resize(t_gray, (sz, sz), interpolation=cv2.INTER_AREA)
                th, tw = t_scaled.shape
                if th > sh or tw > sw:
                    continue

                res = cv2.matchTemplate(slot_gray, t_scaled, cv2.TM_CCOEFF_NORMED)
                _, max_v, _, _ = cv2.minMaxLoc(res)
                if max_v > best_score:
                    best_score = max_v
                    best_champ = cname
                    best_cost = cdata["cost"]

        if best_score >= min_confidence and best_champ is not None:
            return best_champ, best_cost, float(best_score)

        return None, None, float(max(0.0, best_score))

    def recognize_board(self, frame: np.ndarray, min_confidence: float = 0.62) -> Dict[str, Any]:
        """프레임 전체에서 보드 유닛, 벤치 유닛, 골드, 스테이지-라운드 종합 판독."""
        stage_round = self.recognize_stage_round(frame)
        gold = self.recognize_gold(frame)

        # 1. 벤치 9개 슬롯 분석 (Y: 510~590, X: 250~1030)
        bench_units = []
        bench_y1, bench_y2 = DEFAULT_ROIS["bench"]["y1"], DEFAULT_ROIS["bench"]["y2"]
        slot_width = 80
        for slot_idx in range(9):
            x1 = 250 + slot_idx * slot_width
            x2 = x1 + 65
            if x2 > frame.shape[1]:
                break
            slot_crop = frame[bench_y1:bench_y2, x1:x2]
            cname, cost, conf = self.match_slot_champion(slot_crop, min_confidence=min_confidence)

            # 머리 위 별 인식
            overhead_crop = frame[max(0, bench_y1 - 25) : bench_y1, x1:x2]
            star = self.detect_star_level(overhead_crop) if cname else 1

            # 아이템 바 인식
            item_bar_crop = frame[bench_y2 - 15 : bench_y2, x1:x2]
            items = self.match_unit_items(item_bar_crop) if cname else []

            if cname:
                bench_units.append({
                    "slot": slot_idx,
                    "location": "bench",
                    "champion": cname,
                    "cost": cost,
                    "star_level": star,
                    "items": items,
                    "confidence": round(conf, 3),
                })

        # 2. 필드 4행 7열 헥스 분석 (Y: 230~490, X: 260~1020)
        field_units = []
        field_y1, field_y2 = DEFAULT_ROIS["field"]["y1"], DEFAULT_ROIS["field"]["y2"]
        row_height = (field_y2 - field_y1) // 4
        col_width = (DEFAULT_ROIS["field"]["x2"] - DEFAULT_ROIS["field"]["x1"]) // 7

        for r in range(4):
            ry1 = field_y1 + r * row_height
            ry2 = ry1 + row_height
            # 지그재그 헥스 오프셋
            x_offset = (col_width // 2) if r % 2 == 1 else 0
            for c in range(7):
                cx1 = DEFAULT_ROIS["field"]["x1"] + c * col_width + x_offset
                cx2 = cx1 + col_width - 10
                if cx2 > frame.shape[1]:
                    continue
                hex_crop = frame[ry1:ry2, cx1:cx2]
                cname, cost, conf = self.match_slot_champion(hex_crop, min_confidence=min_confidence)

                overhead_crop = frame[max(0, ry1 - 25) : ry1, cx1:cx2]
                star = self.detect_star_level(overhead_crop) if cname else 1

                item_bar_crop = frame[ry2 - 15 : ry2, cx1:cx2]
                items = self.match_unit_items(item_bar_crop) if cname else []

                if cname:
                    field_units.append({
                        "row": r,
                        "col": c,
                        "location": "field",
                        "champion": cname,
                        "cost": cost,
                        "star_level": star,
                        "items": items,
                        "confidence": round(conf, 3),
                    })

        return {
            "stage_round": stage_round,
            "gold": gold,
            "field_units": field_units,
            "bench_units": bench_units,
            "total_detected_units": len(field_units) + len(bench_units),
        }
