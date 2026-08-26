# 🎯 TFT Action Event Detection v2.1 Evaluation Report

- **Evaluated Model**: `ActionEventDetectorV21`
- **Total Predicted Actions**: `66`
- **Total System Free Refreshes Isolated**: `54`
- **Total Ground Truth Target Actions**: `76`

## 1. Action-by-Action Classification Performance

| Action Type | Precision | Recall | F1 Score | TP | FP | FN |
|---|---|---|---|---|---|---|
| **PLAYER_ROLL** | `4.9%` | `7.1%` | **`0.058`** | 2 | 39 | 26 |
| **BUY_UNIT** | `4.0%` | `5.6%` | **`0.046`** | 1 | 24 | 17 |
| **LEVEL_UP** | `0.0%` | `0.0%` | **`0.000`** | 0 | 0 | 0 |

## 2. 6x6 Confusion Matrix (Ground Truth vs Prediction)

| Ground Truth \ Prediction | ROLL | BUY_UNIT | LEVEL_UP | NO_ACTION | SYSTEM_REFRESH | UNKNOWN |
|---|---|---|---|---|---|---|
| **ROLL** | 2 | 5 | 0 | 26 | 0 | 0 |
| **BUY_UNIT** | 2 | 1 | 0 | 17 | 0 | 0 |
| **LEVEL_UP** | 0 | 0 | 0 | 0 | 0 | 0 |
| **NO_ACTION** | 37 | 19 | 0 | 0 | 0 | 0 |

## 3. Timing Error Distribution

- **MAE**: `0.450s` | **Median**: `0.500s` | **P95**: `0.500s` | **Max Error**: `0.500s`
