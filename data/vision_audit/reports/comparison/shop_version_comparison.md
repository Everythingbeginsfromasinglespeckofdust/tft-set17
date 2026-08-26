# ⚖️ Shop Recognition Architecture Comparison (OLD v1 vs NEW v2)

## 1. Slot-by-Slot Accuracy Comparison

| Metric | OLD (ShopRecognizer v1) | NEW (ShopRecognizer v2) | Delta (pp) |
|---|---|---|---|
| **Overall Champion Accuracy** | `3.5%` | `100.0%` | **`+96.5%`** |
| **Overall Cost Accuracy** | `3.0%` | `100.0%` | **`+97.0%`** |
| **Slot 1 Accuracy** | `0.0%` | `100.0%` | **`+100.0%`** |
| **Slot 2 Accuracy** | `7.5%` | `100.0%` | **`+92.5%`** |
| **Slot 3 Accuracy** | `0.0%` | `100.0%` | **`+100.0%`** |
| **Slot 4 Accuracy** | `2.5%` | `100.0%` | **`+97.5%`** |
| **Slot 5 Accuracy** | `7.5%` | `100.0%` | **`+92.5%`** |

## 2. Action Event Extraction Comparison

| Action Metric | OLD v1 | NEW v2 | Delta |
|---|---|---|---|
| **ROLL Precision** | `16.7%` | `9.2%` | **`-7.5%`** |
| **ROLL Recall** | `28.6%` | `35.7%` | **`+7.1%`** |
| **ROLL F1 Score** | `0.210` | `0.146` | **`-0.065`** |
| **BUY Precision** | `20.0%` | `10.0%` | **`-10.0%`** |
| **BUY Recall** | `27.8%` | `5.6%` | **`-22.2%`** |
| **BUY F1 Score** | `0.233` | `0.071` | **`-0.161`** |