# 🎯 TFT Action Event Detection v2 Evaluation Report

- **Evaluated Model**: `ActionEventDetectorV2`
- **Total Predicted Events**: `132`
- **Total Ground Truth Target Actions**: `76`

## 1. Action-by-Action Classification Performance

| Action Type | Precision | Recall | F1 Score | TP | FP | FN |
|---|---|---|---|---|---|---|
| **ROLL** | `6.3%` | `21.4%` | **`0.098`** | 6 | 89 | 22 |
| **BUY_UNIT** | `2.7%` | `5.6%` | **`0.036`** | 1 | 36 | 17 |
| **LEVEL_UP** | `0.0%` | `0.0%` | **`0.000`** | 0 | 0 | 0 |

## 2. Timing Error Distribution

- **MAE**: `0.500s` | **Median**: `0.500s` | **P95**: `1.000s` | **Max Error**: `1.000s`
