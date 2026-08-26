#!/usr/bin/env python3
"""TFT Set 17 상점 챔피언 및 코스트 인식기 (Shop Recognizer v1)."""
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUTPUT = os.path.dirname(_HERE)
_REPO = os.path.dirname(_OUTPUT)

SHOP_GEOMETRY = {
    "card_y1": 589,
    "card_y2": 713,
    "start_x": 309,
    "card_w": 136,
    "gap": 2,
}


class ShopRecognizer:
    """TFT Set 17 상점 5개 카드 슬롯 챔피언/코스트 전용 인식기."""

    def __init__(self, ddragon_dir: Optional[str] = None, set17_path: Optional[str] = None):
        self.ddragon_dir = ddragon_dir or os.path.join(_REPO, "TFT_DDragon")
        self.set17_path = set17_path or os.path.join(_REPO, "tft_set17.json")
        self.champion_templates: Dict[str, Dict[str, Any]] = {}
        self.champ_cost_map: Dict[str, int] = {}
        self._load_templates()

    def _load_templates(self):
        """Set 17 정식 챔피언 템플릿 로드 (TFT17_ 무결성 Assert 포함)."""
        champ_img_dir = os.path.join(self.ddragon_dir, "img", "champion")
        assert os.path.exists(self.set17_path), f"Missing roster file: {self.set17_path}"
        assert os.path.exists(champ_img_dir), f"Missing champion images dir: {champ_img_dir}"

        with open(self.set17_path, "r", encoding="utf-8") as f:
            set17_data = json.load(f)

        avail_imgs = os.listdir(champ_img_dir)

        for c in set17_data.get("champions", []):
            cid = c["id"]
            cname = c["name"]
            cost = c["cost"]
            self.champ_cost_map[cname] = cost
            base_name = cid.split("_")[-1].lower()

            target_img = None
            for f in avail_imgs:
                if f.lower().startswith(f"tft17_{base_name}"):
                    target_img = f
                    break

            if not target_img and (cname == "라아스트" or base_name == "rhaast"):
                for f in avail_imgs:
                    if f.lower().startswith("tft17_kayn"):
                        target_img = f
                        break

            # P0 Version Assert
            assert target_img is not None, f"Set 17 asset not found for {cname} ({cid})"
            assert target_img.startswith("TFT17_"), f"Asset version mismatch: {target_img} is not TFT17 for {cname}"

            tpath = os.path.join(champ_img_dir, target_img)
            t_bgr = cv2.imread(tpath)
            assert t_bgr is not None, f"Failed to read {tpath}"

            th, tw, _ = t_bgr.shape
            min_dim = min(th, tw)
            cy, cx = th // 2, tw // 2
            t_square = t_bgr[cy - min_dim // 2 : cy + min_dim // 2, cx - min_dim // 2 : cx + min_dim // 2]

            self.champion_templates[cname] = {
                "img": t_square,
                "cost": cost,
                "file": target_img,
                "id": cid,
            }

    def detect_card_cost_color(self, card_roi: np.ndarray) -> Optional[int]:
        """카드 하단 및 테두리 색상으로 코스트(1~5) 추정."""
        if card_roi.size == 0:
            return None
        h, w, _ = card_roi.shape
        # Bottom border strip (Y: h-28 to h-4)
        bottom_strip = card_roi[max(0, h - 28) : h - 4, 4 : w - 4]
        if bottom_strip.size == 0:
            return None

        hsv = cv2.cvtColor(bottom_strip, cv2.COLOR_BGR2HSV)
        h_vals = hsv[:, :, 0]
        s_vals = hsv[:, :, 1]
        v_vals = hsv[:, :, 2]

        mean_s = np.mean(s_vals)
        mean_h = np.mean(h_vals)

        # 1-Cost: Gray/Desaturated
        if mean_s < 35.0:
            return 1

        # Check color bands
        green_mask = cv2.inRange(hsv, np.array([35, 40, 40]), np.array([85, 255, 255]))
        blue_mask = cv2.inRange(hsv, np.array([86, 40, 40]), np.array([130, 255, 255]))
        purple_mask = cv2.inRange(hsv, np.array([131, 40, 40]), np.array([168, 255, 255]))
        gold_mask = cv2.inRange(hsv, np.array([10, 80, 80]), np.array([34, 255, 255]))

        counts = {
            1: np.sum(s_vals < 35),
            2: np.sum(green_mask > 0),
            3: np.sum(blue_mask > 0),
            4: np.sum(purple_mask > 0),
            5: np.sum(gold_mask > 0),
        }
        best_cost = max(counts.items(), key=lambda x: x[1])[0]
        return best_cost

    def recognize_shop_slot(
        self, card_roi: np.ndarray, min_confidence: float = 0.50
    ) -> Dict[str, Any]:
        """단일 상점 카드 슬롯 챔피언 및 코스트 정밀 인식."""
        if card_roi.size == 0:
            return {"champion": None, "cost": None, "confidence": 0.0, "is_empty": True}

        # 1. 빈 슬롯 검사 (구매 후 어두운 슬롯 또는 상점 닫힘)
        card_gray = cv2.cvtColor(card_roi, cv2.COLOR_BGR2GRAY)
        std_val = np.std(card_gray)
        mean_val = np.mean(card_gray)
        if std_val < 18.0 or mean_val < 25.0:
            return {
                "champion": None,
                "cost": None,
                "detected_color_cost": None,
                "is_consistent": False,
                "confidence": 0.0,
                "is_empty": True,
            }

        # 2. 포트레이트 상단 영역 크롭 (Y: 0~110)
        h, w, _ = card_roi.shape
        port_h = min(h, 110)
        port_gray = card_gray[:port_h, :]

        best_score = -1.0
        best_champ = None
        best_cost = None

        scales = [80, 95, 110, 125]
        for cname, cdata in self.champion_templates.items():
            t_gray = cv2.cvtColor(cdata["img"], cv2.COLOR_BGR2GRAY)
            for sz in scales:
                if sz > port_gray.shape[0] * 1.3 or sz > port_gray.shape[1] * 1.3:
                    continue
                t_scaled = cv2.resize(t_gray, (min(sz, port_gray.shape[1]), min(sz, port_gray.shape[0])), interpolation=cv2.INTER_AREA)
                th, tw = t_scaled.shape
                if th > port_gray.shape[0] or tw > port_gray.shape[1]:
                    continue
                res = cv2.matchTemplate(port_gray, t_scaled, cv2.TM_CCOEFF_NORMED)
                _, max_v, _, _ = cv2.minMaxLoc(res)
                if max_v > best_score:
                    best_score = max_v
                    best_champ = cname
                    best_cost = cdata["cost"]

        # 3. 색상 기반 코스트 교차 검증
        color_cost = self.detect_card_cost_color(card_roi)
        is_consistent = (best_cost == color_cost)

        # 코스트 불일치 시 신뢰도 패널티 적용
        final_conf = float(best_score)
        if not is_consistent and color_cost is not None and best_cost is not None:
            final_conf = max(0.0, final_conf - 0.15)

        if final_conf >= min_confidence and best_champ is not None:
            return {
                "champion": best_champ,
                "cost": best_cost,
                "detected_color_cost": color_cost,
                "is_consistent": is_consistent,
                "confidence": round(final_conf, 4),
                "is_empty": False,
            }

        return {
            "champion": None,
            "cost": color_cost,
            "detected_color_cost": color_cost,
            "is_consistent": False,
            "confidence": round(float(best_score), 4),
            "is_empty": True if best_score < 0.35 else False,
        }

    def recognize_shop(self, frame: np.ndarray, min_confidence: float = 0.50) -> List[Dict[str, Any]]:
        """상점 5개 카드 슬롯 전수 인식."""
        cards = []
        y1, y2 = SHOP_GEOMETRY["card_y1"], SHOP_GEOMETRY["card_y2"]
        start_x = SHOP_GEOMETRY["start_x"]
        w = SHOP_GEOMETRY["card_w"]
        gap = SHOP_GEOMETRY["gap"]

        for i in range(5):
            cx1 = start_x + i * (w + gap)
            cx2 = cx1 + w
            if cx2 > frame.shape[1] or y2 > frame.shape[0]:
                break
            card_crop = frame[y1:y2, cx1:cx2]
            slot_res = self.recognize_shop_slot(card_crop, min_confidence=min_confidence)
            slot_res["slot_index"] = i + 1
            slot_res["coordinates"] = f"[{y1}:{y2}, {cx1}:{cx2}]"
            cards.append(slot_res)

        return cards
