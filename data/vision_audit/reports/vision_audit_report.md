# 🔍 TFT Vision Ground Truth Audit & Fidelity Report (v1.0)

## 1. Executive Summary & Readiness Verdict

- **DATASET_READINESS Verdict**: 🔴 **RED (Not Ready / Action Fidelity Low)**
- **Session ID**: `SESSION_EDA87AD9_AUDIT` (Single Session, 1 Participant)
- **Video Path**: `C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4`
- **Duration**: `900.0s` (10-minute active gameplay slice)
- **Ground Truth Annotations**: `76` Events, `40` Observation Checkpoints
- **CV Automated Detections**: `131` Events

### Criteria Assessment Summary

- ✅ Timing error excellent (MAE=0.33s <= 0.5s)
- ✅ Shop recognition highly accurate (100.0%)
- ✅ Gold OCR error low (MAE=0.0G <= 1.5G)
- ⚠️ ROLL detection fidelity LOW (Precision=8.3%, Recall=35.7%)


## 2. Action Detection Metrics (Precision / Recall / F1)

> ℹ️ **원칙**: 사람의 육안으로 실제 확인된 Ground Truth와 CV 검출 결과를 $\pm 1.0\text{s}$ 시간 허용 오차 내에서 대조 평가합니다.

| Action Type | Precision | Recall | F1 Score | FP Rate | FN Rate | GT Count | Detected |
|---|---|---|---|---|---|---|---|
| **ROLL** | `8.3%` | `35.7%` | `0.135` | `100.0%` | `64.3%` | `28` | `120` |
| **BUY_UNIT** | `9.1%` | `5.6%` | `0.069` | `100.0%` | `94.4%` | `18` | `11` |
| **LEVEL_UP** | `0.0%` | `0.0%` | `0.000` | `0.0%` | `0.0%` | `0` | `0` |


## 3. Inferred SAVE_GOLD Fidelity

> 💡 **원칙**: `SAVE_GOLD`는 화면에서 직접 클릭되는 행동이 아니므로, 인간 검증자의 `NO_OBSERVED_ECONOMIC_ACTION`과 파이프라인의 `INFERRED SAVE_GOLD`를 대조합니다.

- **Inferred SAVE_GOLD Precision**: `0.0%` (0 TP / 0 Inferred)
- **Inferred SAVE_GOLD Recall**: `0.0%` (0 TP / 30 Ground Truth No-Action Windows)
- **Spurious Inferred Saves (False Positives during Action)**: `0`건

## 4. Action Confusion Matrix (Ground Truth \ CV Detected)

| Ground Truth \ CV | ROLL | BUY_UNIT | LEVEL_UP | SAVE_GOLD | NO_ACTION | UNKNOWN |
|---|---|---|---|---|---|---|
| **ROLL** | `10` | `0` | `0` | `0` | `18` | `0` |
| **BUY_UNIT** | `4` | `1` | `0` | `0` | `13` | `0` |
| **LEVEL_UP** | `0` | `0` | `0` | `0` | `0` | `0` |
| **SAVE_GOLD** | `0` | `0` | `0` | `0` | `0` | `0` |
| **NO_ACTION** | `99` | `9` | `0` | `0` | `0` | `0` |
| **UNKNOWN** | `7` | `1` | `0` | `0` | `22` | `0` |


## 5. Timing Error Analysis (Event Timestamp Alignment)

- **Evaluated Matched Events**: `23`
- **Mean Absolute Timing Error**: `0.326s`
- **Median Timing Error**: `0.500s`
- **P95 Timing Error**: `0.500s`
- **Max Timing Error**: `1.000s`


## 6. Observation Field Accuracy

### (1) HUD Stats & Text OCR Accuracy

| Field | Exact Match Accuracy | MAE (Error) | Max Error | Missing Rate | Samples |
|---|---|---|---|---|---|
| **gold** | `100.0%` | `0.00` | `0.00` | `0.0%` | `40` |
| **hp** | `100.0%` | `0.00` | `0.00` | `0.0%` | `40` |
| **stage_round** | `100.0%` | `-` | `-` | `0.0%` | `40` |

### (2) Shop Slot Recognition Accuracy by Slot (1 to 5)

- **Overall 5-Slot Combined Accuracy**: `100.0%`

| Slot Index | Exact Accuracy | Missing Rate | Evaluated Slots |
|---|---|---|---|
| **Slot 1** | `100.0%` | `0.0%` | `40` |
| **Slot 2** | `100.0%` | `0.0%` | `40` |
| **Slot 3** | `100.0%` | `0.0%` | `40` |
| **Slot 4** | `100.0%` | `0.0%` | `40` |
| **Slot 5** | `100.0%` | `0.0%` | `40` |


## 7. Error Taxonomy & Discrepancy Breakdown (Total: `155`)

- **`FALSE_NEGATIVE`**: `31`건 (`20.0%`)
- **`FALSE_POSITIVE`**: `120`건 (`77.4%`)
- **`WRONG_ACTION`**: `4`건 (`2.6%`)

### Sample Discrepancy Cases

### Case 1: [FALSE_NEGATIVE] at `321.5s`
- **Description**: CV missed BUY_UNIT event
- **Ground Truth**: `BUY_UNIT` | **CV Detected**: `None`

### Case 2: [FALSE_NEGATIVE] at `340.0s`
- **Description**: CV missed BUY_UNIT event
- **Ground Truth**: `BUY_UNIT` | **CV Detected**: `None`

### Case 3: [FALSE_NEGATIVE] at `343.0s`
- **Description**: CV missed ROLL event
- **Ground Truth**: `ROLL` | **CV Detected**: `None`

### Case 4: [FALSE_NEGATIVE] at `343.5s`
- **Description**: CV missed ROLL event
- **Ground Truth**: `ROLL` | **CV Detected**: `None`

### Case 5: [FALSE_NEGATIVE] at `349.5s`
- **Description**: CV missed ROLL event
- **Ground Truth**: `ROLL` | **CV Detected**: `None`

### Case 6: [FALSE_NEGATIVE] at `351.0s`
- **Description**: CV missed BUY_UNIT event
- **Ground Truth**: `BUY_UNIT` | **CV Detected**: `None`

## 8. Human Annotation Agreement (Cohen's Kappa)

- **Evaluated Checkpoints**: `28`
- **Raw Agreement Rate**: `96.4%`
- **Cohen's Kappa ($\kappa$)**: `0.946` (High Inter-Annotator Reliability)


## 9. Data Integrity (`VALID`) vs Detection Correctness (`CORRECT`) Separation

- 💡 **구조적 무결성 (`VALID`)**: 시계열 단조성($t_i \ge t_{i-1}$), $T0 \le T_{\text{action}} \le T1+$, 상태 제약($0\le\text{gold}\le200$) 통과율 **`100.0%`**.
- 🎯 **인식 정답률 (`CORRECT`)**: Ground Truth 대비 ROLL F1=`0.135`, Shop Accuracy=`100.0%`.

## 10. Multi-Video Expansion Recommendations

- 🛑 **권고**: 핵심 행동 인식 재현율이 낮아 대규모 확장을 보류하고 CV 파이프라인을 수정해야 합니다.

