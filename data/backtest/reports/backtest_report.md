# 📊 TFT Decision Engine Backtesting & Calibration Report

## 1. Executive Summary

- **Total Evaluated Snapshots**: `584`
- **Unique Matches**: `64`
- **Unique Participants**: `501`
- **Data Sources**: `historical_match_snapshot: 500`, `historical_video_audit: 84`
- **Observed Action Coverage**: `14.4%` (Unknown Action Rate: `85.6%`)

## 2. Behavioral Agreement Analysis (Observed vs Recommended)

> ⚠️ **주의**: Recommendation Agreement는 '프로그램이 인간의 플레이를 모방한 일치율(Behavioral Agreement)'이며, 전략적 우수성의 척도가 아닙니다.

| Action Type | Agreement Rate | Sample Count |
|---|---|---|
| **ROLL** | `0.0%` | - |
| **OVERALL** | `0.0%` | - |

### Action Confusion Matrix (Actual vs Recommended)

| Actual \ Predicted | ROLL | LEVEL_UP | SAVE_GOLD |
|---|---|---|---|
| **ROLL** | `0` | `0` | `84` |
| **LEVEL_UP** | `0` | `0` | `0` |
| **SAVE_GOLD** | `0` | `0` | `0` |


## 3. Baseline Strategy Comparison

| Strategy | Agreement Rate | % ROLL | % LEVEL_UP | % SAVE_GOLD |
|---|---|---|---|---|
| **DecisionEngine_v1.1** | `0.0%` | `22.8%` | `3.6%` | `73.6%` |
| **AlwaysSave** | `0.0%` | `0.0%` | `0.0%` | `100.0%` |
| **HPThreshold** | `0.0%` | `74.8%` | `0.0%` | `25.2%` |
| **RuleEngine** | `0.0%` | `32.2%` | `0.0%` | `67.8%` |


## 4. Stratified Outcome Analysis (By Game State)

### (1) By Health (HP) Tier

| Health Tier | Samples | Avg Placement | Top 4 Rate | Agreement |
|---|---|---|---|---|
| **HP 0-20 (Critical)** | `437` | `5.00` | `43.0%` | `-` |
| **HP 21-35 (Crisis)** | `0` | `-` | `-` | `-` |
| **HP 36-50 (Low)** | `0` | `-` | `-` | `-` |
| **HP 51-65 (Mid)** | `84` | `2.00` | `100.0%` | `0.0%` |
| **HP 66+ (Safe)** | `63` | `1.00` | `100.0%` | `-` |

### (2) By Gold Tier

| Gold Tier | Samples | Avg Placement | Top 4 Rate | Agreement |
|---|---|---|---|---|
| **Gold 0-19 (Poor)** | `423` | `4.41` | `51.5%` | `-` |
| **Gold 20-39 (Building)** | `130` | `3.02` | `80.8%` | `0.0%` |
| **Gold 40-59 (Econ Target)** | `29` | `4.97` | `41.4%` | `-` |
| **Gold 60+ (Rich)** | `2` | `7.50` | `0.0%` | `-` |

### (3) By Level

| Level Tier | Samples | Avg Placement | Top 4 Rate | Agreement |
|---|---|---|---|---|
| **Level 6 & below** | `1` | `8.00` | `0.0%` | `-` |
| **Level 7** | `125` | `3.48` | `69.6%` | `0.0%` |
| **Level 8** | `172` | `5.42` | `32.6%` | `-` |
| **Level 9+** | `286` | `3.64` | `67.1%` | `-` |


## 5. Decision Margin Analysis (Confidence vs Stability)

| Margin Tier | Decisions | Distribution | Avg Placement | Top 4 Rate | Agreement |
|---|---|---|---|---|---|
| **Tight Margin [0.00, 0.02)** | `222` | `38.0%` | `3.27` | `71.6%` | `0.0%` |
| **Moderate Margin [0.02, 0.05)** | `305` | `52.2%` | `4.58` | `50.2%` | `-` |
| **Clear Margin [0.05, 0.10)** | `50` | `8.6%` | `4.98` | `44.0%` | `-` |
| **Decisive Margin [0.10+)** | `7` | `1.2%` | `6.57` | `14.3%` | `-` |


## 6. Simulation Prediction Errors (Observable Metrics)

- **Gold Prediction MAE**: `18.23G`
- **Gold Prediction RMSE**: `20.02G`
- **Gold Prediction Mean Error**: `+13.55`


## 7. Failure Case Analysis (Total Detected: `0`)

## 8. Data Limitations & Next Steps

- ℹ️ Riot Match-V1 API endpoint provides endgame final state (level, gold_left, placement) but does not record tick-by-tick player decisions.
- ℹ️ Intermediate state player actions are marked as UNKNOWN for match snapshots to prevent falsification.
- ℹ️ Video CV audit timeline contains verified real player action detections (REROLL, BUY).
- ℹ️ Survival score is an uncalibrated heuristic metric and should not be interpreted as a statistical empirical probability without real match match-up logs.

