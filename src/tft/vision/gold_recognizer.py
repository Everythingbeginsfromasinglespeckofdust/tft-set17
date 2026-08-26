"""TFT Gold Recognizer: High-accuracy OCR extraction and numeric domain validation for Gold HUD."""
from dataclasses import dataclass, field
from enum import Enum
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import pytesseract

_TESS_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
]
for tp in _TESS_PATHS:
    if os.path.exists(tp):
        pytesseract.pytesseract.tesseract_cmd = tp
        break


class GoldErrorType(str, Enum):
    """골드 OCR 오류 분류."""
    NONE = "NONE"
    OCR_WRONG_DIGIT = "OCR_WRONG_DIGIT"
    OCR_MISSING = "OCR_MISSING"
    HUD_OCCLUSION = "HUD_OCCLUSION"
    TRANSITION_BLUR = "TRANSITION_BLUR"
    ANIMATION = "ANIMATION"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    OTHER = "OTHER"


@dataclass(frozen=True)
class GoldObservation:
    """단일 프레임의 골드 인식 결과 컨테이너."""
    timestamp_sec: float
    frame_index: int = 0
    raw_text: str = ""
    parsed_gold: Optional[int] = None
    confidence: float = 0.0
    source: str = "tesseract"
    is_valid: bool = False
    error_type: GoldErrorType = GoldErrorType.NONE
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_sec": round(self.timestamp_sec, 3),
            "frame_index": self.frame_index,
            "raw_text": self.raw_text,
            "parsed_gold": self.parsed_gold,
            "confidence": round(self.confidence, 3),
            "source": self.source,
            "is_valid": self.is_valid,
            "error_type": self.error_type.value,
            "metadata": self.metadata
        }


class GoldRecognizer:
    """TFT 1280x720 영상의 골드 HUD를 고정밀 인식하는 엔진."""

    DEFAULT_GOLD_ROI = {"y1": 680, "y2": 720, "x1": 450, "x2": 520}
    MAX_VALID_GOLD = 250

    def __init__(self, roi: Optional[Dict[str, int]] = None, max_valid_gold: int = 250):
        self.roi = roi or self.DEFAULT_GOLD_ROI
        self.max_valid_gold = max_valid_gold

    def preprocess_crop(self, crop: np.ndarray) -> List[Tuple[str, np.ndarray, int]]:
        """고속 다단계 전처리 이미지 생성 (Otsu, Inverted)."""
        if crop.size == 0:
            return []

        # 3.0x Bicubic resize
        r3 = cv2.resize(crop, (0, 0), fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(r3, cv2.COLOR_BGR2GRAY)
        norm = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

        # 1. Otsu Threshold
        _, th_otsu = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 2. Inverted Otsu
        th_inv = cv2.bitwise_not(th_otsu)

        return [
            ("otsu", th_otsu, 7),
            ("inv", th_inv, 7)
        ]

    def parse_numeric(self, raw_text: str) -> Optional[int]:
        """텍스트에서 유효한 TFT 골드 정수 파싱 (0 ~ MAX_VALID_GOLD)."""
        digits = re.findall(r"\d+", raw_text)
        if not digits:
            return None
        try:
            val = int(digits[0])
            if 0 <= val <= self.max_valid_gold:
                return val
        except ValueError:
            pass
        return None

    def recognize_gold(
        self,
        frame: np.ndarray,
        timestamp_sec: float = 0.0,
        frame_index: int = 0
    ) -> GoldObservation:
        """단일 프레임에서 골드 영역을 추출하고 OCR 및 도메인 검증 수행."""
        crop = frame[self.roi["y1"]:self.roi["y2"], self.roi["x1"]:self.roi["x2"]]
        if crop.size == 0:
            return GoldObservation(
                timestamp_sec=timestamp_sec,
                frame_index=frame_index,
                raw_text="",
                parsed_gold=None,
                confidence=0.0,
                is_valid=False,
                error_type=GoldErrorType.HUD_OCCLUSION
            )

        preprocessed = self.preprocess_crop(crop)
        best_gold = None
        best_raw = ""
        best_conf = 0.0

        for name, img_prep, psm in preprocessed:
            cfg = f"--psm {psm} -c tessedit_char_whitelist=0123456789"
            txt = pytesseract.image_to_string(img_prep, config=cfg).strip()
            gold_val = self.parse_numeric(txt)

            if gold_val is not None:
                best_gold = gold_val
                best_raw = txt
                best_conf = 0.95
                break
            elif txt and not best_raw:
                best_raw = txt

        if best_gold is not None:
            return GoldObservation(
                timestamp_sec=timestamp_sec,
                frame_index=frame_index,
                raw_text=best_raw,
                parsed_gold=best_gold,
                confidence=best_conf,
                is_valid=True,
                error_type=GoldErrorType.NONE
            )

        err = GoldErrorType.OCR_MISSING if not best_raw else GoldErrorType.OCR_WRONG_DIGIT
        return GoldObservation(
            timestamp_sec=timestamp_sec,
            frame_index=frame_index,
            raw_text=best_raw,
            parsed_gold=None,
            confidence=0.0,
            is_valid=False,
            error_type=err
        )
