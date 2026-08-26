# 🔬 TFT Action Causality Audit v1 Report

## 1. Analyzed Event Population

- **ROLL Events Analyzed**: `28`
- **BUY_UNIT Events Analyzed**: `18`
- **NO_ACTION Windows Analyzed**: `30`
- **SYSTEM_REFRESH Events Analyzed**: `54`

## 2. ROLL Causal Dynamics & Questions

- **Shop Onset Latency**: Mean `0.963s` | Median `1.000s` | P95 `1.375s`
- **Same-Champion Collisions (<3 slots changed)**: `10` / 28 (`35.7%`)

### Rapid Reroll Interval Distribution:

| Inter-Reroll Interval | Count | Percentage |
|---|---|---|
| `<0.10s` | 0 | 0.0% |
| `0.10~0.20s` | 0 | 0.0% |
| `0.20~0.30s` | 0 | 0.0% |
| `0.30~0.50s` | 0 | 0.0% |
| `0.50~1.00s` | 1 | 3.7% |
| `>1.00s` | 26 | 96.3% |

## 3. Discovered Causal Signatures & Specificity

| Signature ID | Action | Name | Support Rate | NO_ACTION Specificity | Likelihood Ratio | Safe Standalone? |
|---|---|---|---|---|---|---|
| `SIG_ROLL_01` | `ROLL` | Multi-Slot Shop Refresh Pattern (>=3 slots) | `21.4%` (6/28) | `43.3%` | `0.4x` | ❌ (Requires Conjunction) |
| `SIG_ROLL_02` | `ROLL` | Low Slot Delta Collision Pattern (1~2 slots with reroll timing) | `35.7%` (10/28) | `100.0%` | `10.0x` | ❌ (Requires Conjunction) |
| `SIG_BUY_01` | `BUY_UNIT` | Single Slot Emptied with Champion Addition | `44.4%` (8/18) | `100.0%` | `20.0x` | ❌ (Requires Conjunction) |