# TFT Vision Ground Truth Audit & Fidelity Validation Specification (v1.0)

## 1. Overview & Objective

The Vision Ground Truth Audit framework quantitatively benchmarks the accuracy, timing alignment, and error modes of the Vision Pipeline against independent, human-verified ground truth annotations.

```text
Game Video Recording (.mp4)
            ↓
Vision Pipeline Detections
            ↓
[ VisionAuditor Benchmark ]  ←──  Human Ground Truth Dataset (gt_session_01.json)
            ↓
- Precision / Recall / F1
- Timing Error (MAE, P95)
- Inferred SAVE_GOLD vs NO_ACTION Confusion
- Field Accuracy (Gold, HP, Stage, Shop Slots 1-5)
- Error Taxonomy (FP, FN, Wrong Action, OCR Error)
            ↓
DATASET_READINESS Gate Assessment (GREEN / YELLOW / RED)
```

---

## 2. Statistical Metrics & Definitions

### 2.1 Action Event Fidelity
- **`Precision`**: $\frac{TP}{TP + FP}$ (Fraction of CV detections that actually occurred).
- **`Recall`**: $\frac{TP}{TP + FN}$ (Fraction of true human-verified events captured by CV).
- **`F1 Score`**: $2 \cdot \frac{P \cdot R}{P + R}$.
- **`Timing Error`**: $|t_{\text{cv}} - t_{\text{gt}}|$ for matched events within $\pm 1.0\text{s}$ tolerance.

### 2.2 Inferred `SAVE_GOLD` Validation
- `SAVE_GOLD` is an unobservable action on screen.
- Evaluated by contrasting pipeline `INFERRED SAVE_GOLD` against Ground Truth `NO_OBSERVED_ECONOMIC_ACTION` quiescent windows.

### 2.3 Observation Field Accuracy
- **Gold & HP**: Exact match accuracy, Mean Absolute Error (MAE), Max Error.
- **Shop Cards (Slots 1 to 5)**: Exact champion name and tier/cost matching.

---

## 3. Error Taxonomy

1. **`FALSE_POSITIVE`**: CV detected an action when no action occurred.
2. **`FALSE_NEGATIVE`**: True event occurred on screen but was missed by CV.
3. **`WRONG_ACTION`**: True event was misclassified as a different action.
4. **`TIMING_ERROR`**: Event detected but with timestamp discrepancy $> 1.0\text{s}$.
5. **`OCR_ERROR`**: Numerical mismatch on Gold, HP, or Stage text.
6. **`SHOP_RECOGNITION_ERROR`**: Champion or cost misidentified in a shop slot.

---

## 4. Multi-Video Expansion Gate (`DATASET_READINESS`)

| Verdict | Criteria | Actionable Decision |
|---|---|---|
| 🟢 **`GREEN`** | ROLL Recall $\ge 85\%$, Precision $\ge 90\%$, Timing MAE $\le 0.5\text{s}$, Shop Acc $\ge 95\%$, Zero Leakage | **Safe to expand to 10+ game videos** |
| 🟡 **`YELLOW`** | ROLL Recall $\ge 70\%$, Precision $\ge 80\%$, Timing MAE $\le 1.0\text{s}$, Gold MAE $\le 3.0\text{G}$ | **Conditional expansion** with documented limitations and specific module fixes |
| 🔴 **`RED`** | Critical action recall $< 70\%$ or timing error $> 1.2\text{s}$ | **Halt expansion**; fix CV recognizers first |
