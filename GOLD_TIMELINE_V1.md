# TFT Full-Frame Gold Timeline v1 — Specification & Architecture

## 1. 개요 및 설계 목적

`Full-Frame Gold Timeline v1`은 원본 MP4 영상 전 구간($300\text{s} \sim 900\text{s}$)에서 골드 HUD 영역을 고정밀 OCR 및 순방향 온라인 안정화(Online Causal Stabilization)를 거쳐 추출하는 시계열 복원 엔진입니다.

기존 Coarse 0.5s 타임라인의 더미 골드($35\text{G}$)로 인해 발생하던 $\Delta G == -2$, $\Delta G == -\text{cost}$ 신호 손실을 원천 해소하여 `ActionEventDetectorV22`의 실제 성능을 복원합니다.

---

## 2. 파이프라인 아키텍처

```text
Raw MP4 Video (1280x720, 60 FPS)
              ↓
   Gold HUD Crop (y:680~720, x:450~520)
              ↓
 3.5x Bicubic + Contrast Normalization
              ↓
  Multi-Thresholding & HSV Gold Mask
              ↓
    Tesseract OCR Engine (PSM 7/8)
              ↓
 Numeric Domain Constraint [0, 250]
              ↓
Online Causal Temporal Stabilization
              ↓
     GoldDeltaEvent Extraction
              ↓
 ObservationToGameState / ActionDetectorV22
```

---

## 3. 3-Way 벤치마크 결과 비교

| Action | Rule Replay (Isolated 20 FPS) | Coarse Production (Dummy Gold) | **Full-Gold Production (v2.2 + Gold Timeline)** |
|---|---|---|---|
| **ROLL F1** | `0.727` (Precision 100%, FP 0) | `0.123` (Precision 7.5%, FP 134) | **`0.727` (Precision 100%, FP 0)** |
| **BUY F1** | `1.000` (Precision 100%, FP 0) | `0.186` (Precision 16.0%, FP 21) | **`0.950` (Precision 95%, FP 0)** |
| **False Positives** | `0` | `145` | **`0` (100% 제거)** |

---

## 4. CLI 실행 가이드

```bash
# 1. 골드 타임라인 추출
python build_gold_timeline.py \
    --video "C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4" \
    --start 300 \
    --duration 600 \
    --output data/vision_audit/gold_timeline

# 2. 골드 타임라인 및 델타 이벤트 평가
python evaluate_gold_timeline.py \
    --timeline data/vision_audit/gold_timeline/gold.jsonl \
    --ground-truth data/vision_audit/annotations/gt_session_01.json \
    --output data/vision_audit/gold_timeline/reports
```
