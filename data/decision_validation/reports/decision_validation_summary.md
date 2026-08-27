# 📋 TFT Decision Validation Overlay v1.0 — Statistical Report

**Final Gate Verdict**: **`DECISION_VALIDATION_READY`**

## 1. Evaluation Summary
- **Total Decision Records Evaluated**: `20`
- **Total Human Judgments**: `20` (Reasonable: `16`, Questionable: `4`, Wrong: `0`)
- **Blind Mode Reviews**: `10` samples

## 2. Three-Way Metric Independence
- **1. Behavioral Agreement (Engine vs Player)**: `95.0%` (19/20)
  - ROLL Agreement: `0.0%`
  - LEVEL_UP Agreement: `0.0%`
  - SAVE_GOLD Agreement: `95.0%`
- **2. Human Preference Agreement (Engine vs Human Blind)**: `70.0%` (7/10)
- **3. Outcome Association (Observed T1+ Outcomes)**:
  - Avg HP change (3 rounds): `-12.4`
  - Avg Gold change (3 rounds): `+8.2`
  - Avg Final Placement: `#2.8` (Descriptive association, non-causal)

## 3. Failure Taxonomy Breakdown
- `BAD_STATE`: `0`
- `BAD_ECONOMIC_EVALUATION`: `0`
- `BAD_BOARD_EVALUATION`: `0`
- `FEASIBILITY_ERROR`: `0`
- `SIMULATION_ERROR`: `0`
