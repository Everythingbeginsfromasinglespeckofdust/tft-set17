import cv2
import os
import sys
import json
import difflib
import numpy as np
import pytesseract

sys.stdout.reconfigure(encoding='utf-8')
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

repo_root = r"C:\Users\mrjdh\.gemini\antigravity\scratch\tft-set17"
sys.path.insert(0, os.path.join(repo_root, "output", "video_analysis"))
import shop_recognizer as sr

class HybridShopRecognizer:
    def __init__(self):
        self.base_rec = sr.ShopRecognizer()
        with open(os.path.join(repo_root, "tft_set17.json"), "r", encoding="utf-8") as f:
            self.set17 = json.load(f)
        self.champions_by_cost = {1: [], 2: [], 3: [], 4: [], 5: []}
        for c in self.set17["champions"]:
            self.champions_by_cost[c["cost"]].append(c["name"])

    def recognize_slot_hybrid(self, card_crop):
        if card_crop is None or card_crop.size == 0:
            return {"champion": None, "cost": None, "confidence": 0.0, "is_empty": True, "raw_ocr": "", "detected_cost": None}

        gray = cv2.cvtColor(card_crop, cv2.COLOR_BGR2GRAY)
        std_val = float(np.std(gray))
        mean_val = float(np.mean(gray))
        if std_val < 18.0 or mean_val < 25.0:
            return {"champion": None, "cost": None, "confidence": 0.0, "is_empty": True, "raw_ocr": "", "detected_cost": None}

        # 1. Cost Color Detection
        detected_cost = self.base_rec.detect_card_cost_color(card_crop)
        valid_candidates = self.champions_by_cost.get(detected_cost, list(self.base_rec.champion_templates.keys()))
        if not valid_candidates:
            valid_candidates = list(self.base_rec.champion_templates.keys())

        # 2. Portrait Template Matching
        port_gray = gray[:105, :]
        portrait_scores = {}
        for cname in valid_candidates:
            cdata = self.base_rec.champion_templates.get(cname)
            if not cdata: continue
            t_gray = cv2.cvtColor(cdata["img"], cv2.COLOR_BGR2GRAY)
            best_s = -1.0
            for sz in [80, 95, 110, 125]:
                if sz > port_gray.shape[0] * 1.3 or sz > port_gray.shape[1] * 1.3: continue
                t_scaled = cv2.resize(t_gray, (min(sz, port_gray.shape[1]), min(sz, port_gray.shape[0])))
                th, tw = t_scaled.shape
                if th > port_gray.shape[0] or tw > port_gray.shape[1]: continue
                res = cv2.matchTemplate(port_gray, t_scaled, cv2.TM_CCOEFF_NORMED)
                _, max_v, _, _ = cv2.minMaxLoc(res)
                if max_v > best_s:
                    best_s = max_v
            portrait_scores[cname] = max(0.0, best_s)

        # 3. Text OCR & Fuzzy Matching on Name Area
        text_roi = card_crop[86:118, 10:128]
        ocr_scores = {cname: 0.0 for cname in valid_candidates}
        raw_ocr = ""
        if text_roi.size > 0:
            hsv = cv2.cvtColor(text_roi, cv2.COLOR_BGR2HSV)
            mask_white = cv2.inRange(hsv, np.array([0, 0, 170]), np.array([180, 65, 255]))
            mask_gold = cv2.inRange(hsv, np.array([15, 60, 170]), np.array([40, 255, 255]))
            mask = cv2.bitwise_or(mask_white, mask_gold)
            text_scaled = cv2.resize(mask, (0, 0), fx=3.5, fy=3.5, interpolation=cv2.INTER_CUBIC)
            
            custom_config = r'--oem 3 --psm 7 -l kor'
            try:
                ocr_text = pytesseract.image_to_string(text_scaled, config=custom_config).strip()
                raw_ocr = "".join([ch for ch in ocr_text if ch.isalnum()])
                if raw_ocr:
                    for cname in valid_candidates:
                        c_clean = cname.replace(" ", "")
                        ratio = difflib.SequenceMatcher(None, raw_ocr, c_clean).ratio()
                        ocr_scores[cname] = ratio
            except Exception:
                pass

        # 4. Ensemble Fusion: 60% Portrait + 40% Text OCR
        best_champ = None
        best_total_score = -1.0
        for cname in valid_candidates:
            p_s = portrait_scores.get(cname, 0.0)
            t_s = ocr_scores.get(cname, 0.0)
            total_s = 0.60 * p_s + 0.40 * t_s
            if total_s > best_total_score:
                best_total_score = total_s
                best_champ = cname

        champ_cost = None
        if best_champ:
            for c in self.set17["champions"]:
                if c["name"] == best_champ:
                    champ_cost = c["cost"]
                    break

        return {
            "champion": best_champ,
            "cost": champ_cost,
            "detected_cost": detected_cost,
            "confidence": float(best_total_score),
            "portrait_score": portrait_scores.get(best_champ, 0.0),
            "text_score": ocr_scores.get(best_champ, 0.0),
            "raw_ocr": raw_ocr,
            "is_empty": False
        }

    def recognize_shop_hybrid(self, frame):
        results = []
        for slot_idx in range(5):
            cx1 = sr.SHOP_GEOMETRY["start_x"] + slot_idx * (sr.SHOP_GEOMETRY["card_w"] + sr.SHOP_GEOMETRY["gap"])
            cx2 = cx1 + sr.SHOP_GEOMETRY["card_w"]
            card_crop = frame[sr.SHOP_GEOMETRY["card_y1"]:sr.SHOP_GEOMETRY["card_y2"], cx1:cx2]
            res = self.recognize_slot_hybrid(card_crop)
            results.append(res)
        return results
