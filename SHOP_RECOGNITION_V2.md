# TFT Shop Recognition v2 Architecture & Verification Specification

## 1. Executive Summary & Problem Diagnosis

In the Vision Ground Truth Audit v1, the legacy shop timeline (`output/video_analysis/10min_audit/shop_timeline.json`) exhibited a combined 5-slot recognition accuracy of only **`3.5%`**.

### Root Cause Analysis of Legacy ShopRecognizer v1:
1. **Single Fixed Scale & Low Match Scores**: Native champion splash art templates matched at a single scale scored between $0.20 \sim 0.45$. With a hardcoded threshold of $0.50$ (or $0.40$), almost all valid champion portraits failed thresholding and collapsed to `EMPTY`.
2. **Absence of Name Banner OCR & Fuzzy String Matching**: The legacy recognizer discarded the Korean champion name banner below the portrait (`[86:118, 10:128]`).
3. **No HSV Cost Band Pruning**: Did not filter the 60-champion roster by border strip cost color before template matching.
4. **No Causal Temporal Smoothing**: Single-frame threshold misses resulted in slot flickering.

---

## 2. ShopRecognizer v2 Architecture

```text
Video Frame (1280x720)
       ↓
Relative Coordinate Crop (Y: 589-713, X: 309-997)
       ↓
5 Slot Crops (124x136 px each)
       ↓
[ Stage 1: Empty / Dark Slot Check ] (Std < 18.0 or Mean < 25.0 -> EMPTY)
       ↓
[ Stage 2: HSV Cost Color Band Detection ] (1C Gray, 2C Green, 3C Blue, 4C Purple, 5C Gold)
       ↓
[ Stage 3: Multi-Scale Portrait Template Matching ] (Scales: 80, 95, 110, 125 px)
       ↓
[ Stage 4: Dual-HSV Masked Tesseract OCR ] (Korean Name Banner + Fuzzy SequenceMatcher)
       ↓
[ Stage 5: Candidate Fusion ] (Combined Score = 0.60 * Portrait + 0.40 * OCR Text)
       ↓
[ Stage 6: Causal Temporal Stabilization ] (Forward-only online debouncing, zero hindsight)
       ↓
Clean Shop Observation (SlotStatus: RECOGNIZED / EMPTY / UNKNOWN / LOW_CONFIDENCE)
```

---

## 3. Slot Status Taxonomy

- **`RECOGNIZED`**: Champion and cost resolved with calibrated confidence $\ge 0.18$.
- **`EMPTY`**: Physically vacant slot (card purchased by player).
- **`LOW_CONFIDENCE`**: Card present, but ensemble score below confidence gate.
- **`UNKNOWN`**: Card present, but candidate roster failed resolution.
- **`NO_DETECTION`**: Shop UI closed or occluded.

---

## 4. CLI Tools & Evaluation Commands

### (1) Extract Timeline from MP4 Video:
```bash
python build_shop_timeline_v2.py \
    --video "C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4" \
    --start 300.0 --duration 600.0 --interval 0.5 \
    --output data/vision_audit/new_shop_timeline
```

### (2) Evaluate New Timeline against Ground Truth:
```bash
python evaluate_shop_recognition.py \
    --timeline data/vision_audit/new_shop_timeline \
    --ground-truth data/vision_audit/annotations/gt_session_01.json \
    --output data/vision_audit/reports/shop_v2
```

### (3) Compare OLD vs. NEW Performance:
```bash
python compare_shop_versions.py \
    --old output/video_analysis/10min_audit/shop_timeline.json \
    --new data/vision_audit/new_shop_timeline \
    --ground-truth data/vision_audit/annotations/gt_session_01.json
```
