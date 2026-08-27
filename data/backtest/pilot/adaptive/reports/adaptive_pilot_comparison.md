# 🚀 TFT Adaptive Action Resampling v1 — 3-Way Benchmark & Cross-Session Report

**Gate Verdict**: **`GREEN`**

## 1. 3-Way Cross-Session Comparison Table

| Session | Strategy Archetype | Coarse ROLL F1 | **Adaptive ROLL F1** | Rule Replay ROLL F1 | Coarse BUY F1 | **Adaptive BUY F1** | Rule Replay BUY F1 | FP Red. | Refinement Ratio | Recovery Rate |
|---|---|---|---|---|---|---|---|---|---|---|
| **`SESSION_A`** | `BALANCED_STANDARD` | `0.086` | **`0.727`** (+`0.641`) | `0.727` | `0.093` | **`1.000`** (+`0.907`) | `1.000` | `-150` | `6.2%` | `80.0%` |
| **`SESSION_B`** | `FAST_LEVELUP` | `1.000` | **`1.000`** (+`0.000`) | `1.000` | `1.000` | **`1.000`** (+`0.000`) | `1.000` | `-0` | `4.8%` | `100.0%` |
| **`SESSION_C`** | `REROLL_HEAVY` | `1.000` | **`1.000`** (+`0.000`) | `1.000` | `1.000` | **`1.000`** (+`0.000`) | `1.000` | `-0` | `5.5%` | `100.0%` |

## 2. Statistical Summary

- **Mean Adaptive ROLL F1**: `0.909` (Coarse: `0.695` $\to$ Adaptive: `0.909`)
- **Mean Adaptive BUY F1**: `1.000` (Coarse: `0.698` $\to$ Adaptive: `1.000`)
- **Total False Positives**: `0` (Reduced by `150` from 150 to 0)
- **Mean Refinement Ratio**: `5.5%` (Only 5.5% of total frames scanned at 20 FPS)
- **Failure Recovery Rate (`COARSE_SAMPLING_MERGE`)**: `93.3%`