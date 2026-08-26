"""TFT Shop Recognition Error Debug Gallery Generator."""
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import cv2
import numpy as np


@dataclass
class ShopDebugSample:
    """개별 오류 디버그 샘플."""
    sample_id: str
    timestamp_sec: float
    slot_index: int
    ground_truth_champion: Optional[str]
    ground_truth_cost: Optional[int]
    predicted_champion: Optional[str]
    predicted_cost: Optional[int]
    status: str
    confidence: float
    template_score: float
    ocr_score: float
    raw_ocr: str
    reason: str  # "NO_DETECTION", "WRONG_CANDIDATE", "LOW_CONFIDENCE", "OCR_MISMATCH", "COLOR_COST_MISMATCH"
    crop_path: Optional[str] = None


class ShopDebugGallery:
    """오류 사례를 이미지 크롭 및 메타데이터와 함께 저장하는 디버그 갤러리."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.crops_dir = os.path.join(output_dir, "crops")
        self.samples: List[ShopDebugSample] = []
        os.makedirs(self.crops_dir, exist_ok=True)

    def add_sample(
        self,
        timestamp_sec: float,
        slot_index: int,
        gt_champ: Optional[str],
        gt_cost: Optional[int],
        pred_champ: Optional[str],
        pred_cost: Optional[int],
        status: str,
        confidence: float,
        template_score: float,
        ocr_score: float,
        raw_ocr: str,
        reason: str,
        crop_bgr: Optional[np.ndarray] = None
    ):
        """오류 샘플 등록 및 이미지 크롭 저장."""
        sample_id = f"dbg_{int(timestamp_sec)}_{slot_index + 1}"
        crop_path = None

        if crop_bgr is not None and crop_bgr.size > 0:
            crop_filename = f"{sample_id}.jpg"
            full_crop_path = os.path.join(self.crops_dir, crop_filename)
            cv2.imwrite(full_crop_path, crop_bgr)
            crop_path = f"crops/{crop_filename}"

        sample = ShopDebugSample(
            sample_id=sample_id,
            timestamp_sec=timestamp_sec,
            slot_index=slot_index,
            ground_truth_champion=gt_champ,
            ground_truth_cost=gt_cost,
            predicted_champion=pred_champ,
            predicted_cost=pred_cost,
            status=status,
            confidence=round(confidence, 3),
            template_score=round(template_score, 3),
            ocr_score=round(ocr_score, 3),
            raw_ocr=raw_ocr,
            reason=reason,
            crop_path=crop_path
        )
        self.samples.append(sample)

    def save_gallery(self):
        """갤러리 인덱스 JSON 및 Markdown 리포트 생성."""
        index_path = os.path.join(self.output_dir, "gallery_index.json")
        report_path = os.path.join(self.output_dir, "debug_gallery_report.md")

        data = {
            "total_debug_samples": len(self.samples),
            "samples": [
                {
                    "sample_id": s.sample_id,
                    "timestamp_sec": s.timestamp_sec,
                    "slot": s.slot_index + 1,
                    "ground_truth": {"champion": s.ground_truth_champion, "cost": s.ground_truth_cost},
                    "prediction": {"champion": s.predicted_champion, "cost": s.predicted_cost},
                    "status": s.status,
                    "confidence": s.confidence,
                    "template_score": s.template_score,
                    "ocr_score": s.ocr_score,
                    "raw_ocr": s.raw_ocr,
                    "reason": s.reason,
                    "crop_path": s.crop_path
                }
                for s in self.samples
            ]
        }

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        md = ["# 🖼️ Shop Recognition Error Debug Gallery\n"]
        md.append(f"- **Total Discrepancies / Low Confidence Cases Logged**: `{len(self.samples)}`\n")
        md.append("| Sample ID | Time | Slot | Ground Truth | Prediction | Reason | Confidence | Raw OCR |")
        md.append("|---|---|---|---|---|---|---|---|")
        for s in self.samples[:50]:
            gt_str = f"{s.ground_truth_champion} ({s.ground_truth_cost}C)" if s.ground_truth_champion else "EMPTY"
            pred_str = f"{s.predicted_champion} ({s.predicted_cost}C)" if s.predicted_champion else s.status
            md.append(f"| `{s.sample_id}` | `{s.timestamp_sec:.1f}s` | Slot {s.slot_index + 1} | **{gt_str}** | {pred_str} | `{s.reason}` | `{s.confidence:.2f}` | `{s.raw_ocr}` |")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
