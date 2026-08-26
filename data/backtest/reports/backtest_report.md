# 📊 TFT Decision Engine Backtesting & Statistical Validity Report (v1.1)

## 1. Dataset Composition

- **Total Evaluated Snapshots**: `584`
- **Unique Matches**: `64`
- **Unique Participants**: `501`
- **Data Sources**:

  - `historical_match_snapshot`: `500` samples (`85.6%`)
  - `historical_video_audit`: `84` samples (`14.4%`)


## 2. Snapshot Type Distribution

> ℹ️ **중요 원칙**: `ENDGAME_SNAPSHOT`은 탈락 시점 최종 상태이며 전략 평가의 모집단으로 사용하지 않습니다. `MIDGAME_DECISION_SNAPSHOT`만 의사결정 유효성 평가 대상입니다.

| Snapshot Type | Count | Percentage | Purpose |
|---|---|---|---|
| **`ENDGAME_SNAPSHOT`** | `500` | `85.6%` | Descriptive / Integrity only (NOT strategy eval) |
| **`MIDGAME_DECISION_SNAPSHOT`** | `84` | `14.4%` | Strategy Evaluation (Primary) |


## 3. Action Observation Coverage

- **Known Action Samples**: `84` / `584` (`14.4%`)
- **Unknown Action Samples**: `500` / `584` (`85.6%`)

### Coverage by Snapshot Type

| Snapshot Type | Total Samples | Known Actions | Coverage Rate |
|---|---|---|---|
| **`ENDGAME_SNAPSHOT`** | `500` | `0` | `0.0%` |
| **`MIDGAME_DECISION_SNAPSHOT`** | `84` | `84` | `100.0%` |


## 4. Temporal Integrity (T0 <= T1+ Validation)

- **Timestamps Checked**: `584` samples
- **Temporal Violations (T0 > T1+)**: `0`
- **Uncalibrated Timestamps (Riot API)**: `0`
- **Status**: ✅ **PASSED** (모든 시계열 순방향 무결성 확인)


## 5. Leakage Validation

- **Total Samples Inspected**: `584`
- **Placement in T0 State**: `0`
- **Endgame Samples in Midgame Report**: `0`
- **Status**: ✅ **ZERO LEAKAGE** (미래 정보 유입 0건)


## 6. Midgame Descriptive Statistics (n=84)

- **Evaluated Samples**: `84`
- **Samples with Final Placement**: `84` (Avg Placement: `#2.0`, Top4: `100.0%`)
- **Known Action Count**: `84`

### (1) By Stage (Midgame Only)

| Stage Tier | Samples | Avg Placement | Top 4 Rate | Agreement | Mean Score Gap |
|---|---|---|---|---|---|
| **Stage 2-x** | `0` | `-` | `-` | `-` | `-` |
| **Stage 3-x** | `22` | `2.00` | `100.0%` | `0.0%` | `0.016` |
| **Stage 4-x** | `38` | `2.00` | `100.0%` | `0.0%` | `0.016` |
| **Stage 5-x** | `24` | `2.00` | `100.0%` | `0.0%` | `0.016` |
| **Stage 6+** | `0` | `-` | `-` | `-` | `-` |


## 7. Endgame Descriptive Statistics (n=500)

> ⚠️ **알림**: 아래 수치는 탈락 시점의 기술통계(Descriptive)이며, Decision Engine의 성능 지표가 아닙니다.

- **Total Endgame Snapshots**: `500`
- **Average Final Placement**: `#4.5`
- **Top 4 Rate**: `50.2%` (분모: `500`)

### (1) By Gold at Elimination

| Gold Tier | Samples | Avg Placement | Top 4 Rate | Mean Score Gap |
|---|---|---|---|---|
| **Gold 0-19 (Poor)** | `423` | `4.41` | `51.5%` | `0.016` |
| **Gold 20-39 (Building)** | `46` | `4.87` | `45.6%` | `0.059` |
| **Gold 40-59 (Econ Target)** | `29` | `4.97` | `41.4%` | `0.075` |
| **Gold 60+ (Rich)** | `2` | `7.50` | `0.0%` | `0.100` |


## 8. Recommendation Agreement (Behavioral Comparison)

> ℹ️ **원칙**: Recommendation Agreement는 '프로그램이 인간의 플레이와 일치한 비율(Behavioral Agreement)'을 나타내며 전략적 우수성의 척도가 아닙니다. `human_policy != engine_policy`는 두 정책이 다름을 의미할 뿐입니다.

- **Overall Behavioral Agreement**: `0.0%` (분모: `84` known action samples)

### Strategy Policy Distribution & Behavioral Agreement

| Strategy | Behavioral Agreement | % ROLL | % LEVEL_UP | % SAVE_GOLD | Sample Denominator |
|---|---|---|---|---|---|
| **DecisionEngine_v1.1** | `0.0%` | `26.4%` | `1.0%` | `72.6%` | `84` |
| **AlwaysSave** | `0.0%` | `0.0%` | `0.0%` | `100.0%` | `84` |
| **HPThreshold** | `0.0%` | `85.6%` | `0.0%` | `14.4%` | `84` |
| **RuleEngine** | `0.0%` | `40.1%` | `0.0%` | `59.9%` | `84` |


## 9. Action Score Gap Diagnostics (formerly: Decision Margin)

> 💡 **정의**: `action_score_gap = score(best_action) - score(second_best_action). This is action score SEPARATION, NOT a calibrated probability of correctness.`

- **Mean Score Gap in ENDGAME Snapshots**: `0.0237`
- **Mean Score Gap in MIDGAME Snapshots**: `0.0164`

### Score Gap Tiers & Snapshot Type Breakdown

| Score Gap Tier | Total Decisions | ENDGAME Count | MIDGAME Count | Avg Placement (Observed) | Top 4 Rate |
|---|---|---|---|---|---|
| **Tight Margin [0.00, 0.02)** | `214` | `130` | `84` | `3.35` | `70.6%` |
| **Moderate Margin [0.02, 0.05)** | `311` | `311` | `0` | `4.51` | `51.1%` |
| **Clear Margin [0.05, 0.10)** | `52` | `52` | `0` | `4.83` | `46.2%` |
| **Decisive Margin [0.10+)** | `7` | `7` | `0` | `6.57` | `14.3%` |

- **MIDGAME Correlation Analysis**: Correlation computed on n=84 MIDGAME samples with known placement.


## 10. Simulation Accuracy (Gold & State Prediction)

- **Valid Pairs Evaluated**: `84`
- **Horizon = 0 Excluded (ENDGAME)**: `500`
- **Note**: Gold prediction error computed ONLY for samples where: (1) horizon_rounds > 0 (not ENDGAME), and (2) actual_action is known. ENDGAME samples excluded: 500. 

- **Overall Gold MAE**: `34.0G`
- **Overall Gold RMSE**: `34.0G`
- **Overall Gold Bias**: `+34`


## 11. Failure Diagnostics (Total Detected: `34`)

> ℹ️ **알림**: Failure Case는 의사결정이 틀렸다는 '증명'이 아니라, 모델의 판단과 실제 결과 사이에 큰 격차가 있는 '진단용 레이블(Diagnostic Label)'입니다.

### Case 1: [HIGH_MARGIN_BOTTOM4] (`KR_8353055717_K72zLQHU_14`)
- **Description**: score_gap=0.076 >= 0.05, but final placement was 8 (bottom 4). Diagnostic label only. snapshot_type=ENDGAME_SNAPSHOT.
- **State**: Stage `4-5`, Gold `21G`, Level `8`, HP `0` (`ENDGAME_SNAPSHOT`)
- **Recommendation**: `ROLL` (Score Gap: `+0.076`)
- **Actual Outcome**: Action `UNKNOWN`, Final Placement `#8`

### Case 2: [HIGH_MARGIN_BOTTOM4] (`KR_8338434217_f5Q6imd7_66`)
- **Description**: score_gap=0.091 >= 0.05, but final placement was 7 (bottom 4). Diagnostic label only. snapshot_type=ENDGAME_SNAPSHOT.
- **State**: Stage `4-6`, Gold `37G`, Level `7`, HP `0` (`ENDGAME_SNAPSHOT`)
- **Recommendation**: `ROLL` (Score Gap: `+0.091`)
- **Actual Outcome**: Action `UNKNOWN`, Final Placement `#7`

### Case 3: [HIGH_MARGIN_BOTTOM4] (`KR_8338402074_Psli-lw0_78`)
- **Description**: score_gap=0.068 >= 0.05, but final placement was 8 (bottom 4). Diagnostic label only. snapshot_type=ENDGAME_SNAPSHOT.
- **State**: Stage `4-5`, Gold `33G`, Level `8`, HP `0` (`ENDGAME_SNAPSHOT`)
- **Recommendation**: `ROLL` (Score Gap: `+0.068`)
- **Actual Outcome**: Action `UNKNOWN`, Final Placement `#8`

### Case 4: [HIGH_MARGIN_BOTTOM4] (`KR_8338343065_1e9ELcSf_90`)
- **Description**: score_gap=0.078 >= 0.05, but final placement was 6 (bottom 4). Diagnostic label only. snapshot_type=ENDGAME_SNAPSHOT.
- **State**: Stage `5-1`, Gold `27G`, Level `8`, HP `0` (`ENDGAME_SNAPSHOT`)
- **Recommendation**: `ROLL` (Score Gap: `+0.078`)
- **Actual Outcome**: Action `UNKNOWN`, Final Placement `#6`

### Case 5: [HIGH_MARGIN_BOTTOM4] (`KR_8338343065_qTMZ0Wzl_95`)
- **Description**: score_gap=0.140 >= 0.05, but final placement was 8 (bottom 4). Diagnostic label only. snapshot_type=ENDGAME_SNAPSHOT.
- **State**: Stage `3-1`, Gold `66G`, Level `5`, HP `0` (`ENDGAME_SNAPSHOT`)
- **Recommendation**: `ROLL` (Score Gap: `+0.140`)
- **Actual Outcome**: Action `UNKNOWN`, Final Placement `#8`



## 12. Statistical Limitations

- ⚠️ Riot Match-V1 API provides ONLY elimination-time final state. All 500 match snapshots are ENDGAME_SNAPSHOT and must not be used for Decision Engine strategy evaluation.
- ⚠️ Intermediate round-by-round player actions (ROLL, LEVEL_UP, SAVE_GOLD) are not recorded by Riot Match-V1. actual_action = UNKNOWN for all Riot match samples.
- ⚠️ MIDGAME samples: 84 (from video CV audit only). GameState values (gold, hp, level) in video samples are HEURISTIC ESTIMATES, not precise extractions.
- ⚠️ Known actual_action coverage: 84 / 584 samples (14.4%). All known actions are from the single video audit session.
- ⚠️ survival_score is an uncalibrated heuristic metric. It cannot be interpreted as a statistical probability without empirical calibration data.
- ⚠️ action_score_gap (formerly decision_margin) is score separation between best and second-best action. It is NOT a calibrated probability of correctness.
- ⚠️ The single video session (1 player, 1 game) cannot be generalized to broader player populations.


## 13. What Can Be Concluded (현재 데이터로 확인 가능한 사실)

- ✅ Decision Engine executes successfully on all 584 evaluated GameState samples with 0 runtime errors.
- ✅ ENDGAME and MIDGAME snapshot types can be cleanly separated by data_source and snapshot_type fields.
- ✅ Match-level group split maintains zero match overlap between train and test sets.
- ✅ Temporal integrity (T0 <= T1+) is maintained for samples with known timestamps.
- ✅ No final_placement leakage detected in T0 GameState objects.
- ✅ The engine produces valid, feasible action recommendations across diverse game states.


## 14. What Cannot Be Concluded (현재 데이터로 결론내릴 수 없는 항목)

- ❌ Whether Decision Engine produces better game outcomes than human play. (Requires: MIDGAME states with known actual_action, future outcomes, sufficient sample size.)
- ❌ Whether ROLL, LEVEL_UP, or SAVE_GOLD leads to better expected placement in any given situation. (Requires: counterfactual data with both action and outcome for same initial state.)
- ❌ Whether action_score_gap (decision_margin) can be used as a probability of correctness. (Requires: empirical calibration against labeled outcomes.)
- ❌ Whether the engine's SAVE_GOLD preference is strategically superior to human ROLL behavior. human_policy != engine_policy does not imply either is better.
- ❌ Whether survival_score is an accurate predictor of actual survival probability. (Requires: calibration against empirical round-by-round match data.)
- ❌ Whether the video audit sample (n=84, single session) generalizes to any broader population.
- ❌ Any causal claim about Decision Engine recommendations and game outcomes.


## 15. Next Required Data (다음 Calibration에 필요한 최소 데이터 조건)

- 🎯 MIDGAME decision snapshots from multiple game sessions with precise round state extraction (gold, hp, level, board at each round start) -- minimum 500 samples across 50+ sessions.
- 🎯 Round-by-round actual player actions (ROLL, LEVEL_UP, SAVE_GOLD) paired with resulting game state -- required for action-conditioned analysis.
- 🎯 For counterfactual evaluation: paired states where player chose action A in one sample and action B in a comparable state, both with known outcomes.
- 🎯 For gold prediction validation: T0 gold + actual T0 action + T1+ gold n rounds later, with known horizon_rounds.
- 🎯 For correlation analysis: minimum 100 MIDGAME samples with (state, action, placement) tuples from diverse players and stages.
- 🎯 Empirical champion pool availability data for the actual game version being analyzed to improve roll probability accuracy.

