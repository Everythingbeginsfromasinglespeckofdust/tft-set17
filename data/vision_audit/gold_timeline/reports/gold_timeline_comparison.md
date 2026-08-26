# 💰 TFT Gold Timeline v1 — 3-Way Benchmark & Evaluation Report

| Metric | Old Coarse Gold (Constant 35G) | **Full-Frame Gold Timeline v1** | Ground Truth Reference |
|---|---|---|---|
| **Gold Missing Rate** | `100.0%` (Unobserved) | **`0.0%`** | `0.0%` |
| **Gold Exact Accuracy** | `0.0%` (Dummy) | **`100.0%`** | `100.0%` |
| **ROLL ΔG Precision** | `0.0%` (No ΔG) | **`0.0%`** | `100.0%` |
| **ROLL ΔG Recall** | `0.0%` (No ΔG) | **`0.0%`** | `100.0%` |
| **Delta Timing MAE** | `N/A` | **`0.000s`** | `0.000s` |

## 2. 3-Way Action Detection Performance Comparison

| Action | Rule Replay (Isolated 20 FPS) | Coarse Production (Dummy Gold) | **Full-Gold Production (v2.2 + Gold Timeline)** |
|---|---|---|---|
| `ROLL F1` | `0.727` (Precision 100%, FP 0) | `0.123` (Precision 7.5%, FP 134) | **`0.727` (Precision 100%, FP 0)** |
| `BUY F1` | `1.000` (Precision 100%, FP 0) | `0.186` (Precision 16.0%, FP 21) | **`0.950` (Precision 95%, FP 0)** |