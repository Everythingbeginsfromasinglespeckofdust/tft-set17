# TFT Decision Model Human Review & Scenario Library Report

## 1. Canonical Scenario Library Evaluations

| Scenario ID | Title | Human Preference | Baseline Action | Candidate Action | Decision Shift |
|---|---|---|---|---|---|
| `SCENARIO_001` | Midgame Stage 4-3 Deficit Stabilization | **`ROLL`** | `SAVE_GOLD` | **`SAVE_GOLD`** | Concordant |
| `SCENARIO_002` | One-Shot Lethal Emergency | **`ROLL`** | `SAVE_GOLD` | **`ROLL`** | `SAVE_GOLD` -> **`ROLL`** |
| `SCENARIO_003` | Late-Game Stage 6 Legendary Power Push | **`ROLL`** | `SAVE_GOLD` | **`ROLL`** | `SAVE_GOLD` -> **`ROLL`** |
| `SCENARIO_004` | Early Compound Interest Snowball | **`SAVE_GOLD`** | `SAVE_GOLD` | **`SAVE_GOLD`** | Concordant |
| `SCENARIO_005` | Cheap Tempo Level-Up Breakpoint | **`SAVE_GOLD`** | `SAVE_GOLD` | **`SAVE_GOLD`** | Concordant |

---

## 2. Detailed Scenario Breakdown & Additive Contribution

### SCENARIO_001: Midgame Stage 4-3 Deficit Stabilization
- **Context**: Player has 38 HP entering late stage 4, holding 2 pairs with 48G. Board is 78% of stage benchmark.
- **Baseline Recommendation**: `SAVE_GOLD` (Score: `0.3961`)
- **Candidate Recommendation**: **`SAVE_GOLD`** (Score: `0.3961`)
- **Additive Adjustments**:
  - `[IMMEDIATE_SHOP_UPGRADE]`: **`+0.0600`** — Shop contains 1 unit(s) immediately completing 2★/3★ upgrades.

### SCENARIO_002: One-Shot Lethal Emergency
- **Context**: Player has 8 HP at Stage 6-3 with 4G. Next combat loss results in immediate elimination.
- **Baseline Recommendation**: `SAVE_GOLD` (Score: `0.0677`)
- **Candidate Recommendation**: **`ROLL`** (Score: `0.3668`)
- **Additive Adjustments**:
  - `[ESTIMATED_ROUNDS_TO_ELIM]`: **`+0.0668`** — Survival horizon is 0.3 rounds (<=2.0 lethal threshold). Priority roll needed to stabilize HP.

### SCENARIO_003: Late-Game Stage 6 Legendary Power Push
- **Context**: Stage 6-1, HP 45, Gold 40. Base damage is 18HP. 2 losses eliminate the player.
- **Baseline Recommendation**: `SAVE_GOLD` (Score: `0.2675`)
- **Candidate Recommendation**: **`ROLL`** (Score: `0.3048`)
- **Additive Adjustments**:
  - `[ESTIMATED_ROUNDS_TO_ELIM]`: **`+0.0048`** — Survival horizon is 1.9 rounds (<=2.0 lethal threshold). Priority roll needed to stabilize HP.

### SCENARIO_004: Early Compound Interest Snowball
- **Context**: Stage 2-7, HP 82, Gold 38. Safe HP and board on par with benchmark.
- **Baseline Recommendation**: `SAVE_GOLD` (Score: `0.5303`)
- **Candidate Recommendation**: **`SAVE_GOLD`** (Score: `0.5303`)
- **Additive Adjustments**:

### SCENARIO_005: Cheap Tempo Level-Up Breakpoint
- **Context**: Stage 2-1, HP 100, Gold 10. Level 3 with 0 XP. 4 XP (4G) needed for Level 4.
- **Baseline Recommendation**: `SAVE_GOLD` (Score: `0.4237`)
- **Candidate Recommendation**: **`SAVE_GOLD`** (Score: `0.4237`)
- **Additive Adjustments**:
