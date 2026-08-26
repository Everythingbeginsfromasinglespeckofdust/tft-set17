# 🔬 TFT Action Event Detector 4-Generation Comparison (V1 vs V2 vs V2.1 vs V2.2)

| Metric | V1 (Old Shop) | V2 (StateDiff) | V2.1 (System Filter) | **V2.2 (Causal Rules Production)** |
|---|---|---|---|---|
| **ROLL Precision** | `14.8%` | `6.3%` | `4.9%` | **`7.5%`** |
| **ROLL Recall** | `28.6%` | `21.4%` | `7.1%` | **`35.7%`** |
| **ROLL F1** | `0.195` | `0.098` | `0.058` | **`0.123`** |
| **BUY Precision** | `16.7%` | `2.7%` | `4.0%` | **`16.0%`** |
| **BUY Recall** | `27.8%` | `5.6%` | `5.6%` | **`22.2%`** |
| **BUY F1** | `0.208` | `0.036` | `0.047` | **`0.186`** |
| **SYSTEM_REFRESH F1** | `0.000` | `0.000` | `1.000` | **`1.000`** |
| **Timing MAE** | `0.326s` | `0.500s` | `0.450s` | **`0.929s`** |
| **False Positives** | `177` | `125` | `63` | **`145`** |
| **False Negatives** | `33` | `39` | `43` | **`32`** |
| **Predicted Actions** | `297` | `132` | `43` | **`159`** |

## 2. Rule Replay vs Production Pipeline Mismatch Analysis

| Action | Rule Replay F1 (Isolated) | Production Detector F1 (End-to-End) | Difference / Information Loss Analysis |
|---|---|---|---|
| `ROLL` | `0.727` (16 TP) | `0.123` (10 TP) | Coarse 0.5s timeline frame sampling timing alignment |
| `BUY_UNIT` | `1.000` (18 TP) | `0.186` (4 TP) | Transient shop animation filtering consistency |