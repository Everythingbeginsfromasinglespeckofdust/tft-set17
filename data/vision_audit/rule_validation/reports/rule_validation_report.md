# 🔬 TFT Action Rule Validation v1 Report

## 1. Candidate Rule Performance Summary

| Rule Name | Action | Description | TP | FP | FN | Precision | Recall (Coverage) | F1 | Specificity | Likelihood Ratio | Laplace LR (α=1.0) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **`ROLL_A`** | `ROLL` | gold==-2 & shop>=1 & not sys & board/bench unchanged | 16 | 0 | 12 | `100.0%` | `57.1%` | **`0.727`** | `100.0%` | `∞` | `58.93x` |
| **`ROLL_B`** | `ROLL` | gold==-2 & shop>=1 & not sys & not buy | 16 | 0 | 12 | `100.0%` | `57.1%` | **`0.727`** | `100.0%` | `∞` | `58.93x` |
| **`ROLL_C`** | `ROLL` | gold==-2 & shop>=1 & not sys | 16 | 0 | 12 | `100.0%` | `57.1%` | **`0.727`** | `100.0%` | `∞` | `58.93x` |
| **`ROLL_D`** | `ROLL` | gold==-2 & shop_transition & not sys (collision-aware) | 16 | 0 | 12 | `100.0%` | `57.1%` | **`0.727`** | `100.0%` | `∞` | `58.93x` |
| **`BUY_A`** | `BUY_UNIT` | slot_empty & matching_add & gold==-cost & not anim | 18 | 0 | 0 | `100.0%` | `100.0%` | **`1.000`** | `100.0%` | `∞` | `108.30x` |
| **`BUY_B`** | `BUY_UNIT` | slot_empty & gold==-cost & not anim | 18 | 0 | 0 | `100.0%` | `100.0%` | **`1.000`** | `100.0%` | `∞` | `108.30x` |
| **`BUY_C`** | `BUY_UNIT` | slot_empty & matching_add & not anim | 18 | 0 | 0 | `100.0%` | `100.0%` | **`1.000`** | `100.0%` | `∞` | `108.30x` |
| **`SYSTEM_REFRESH_A`** | `SYSTEM_REFRESH` | shop>=3 & gold==0 & round_transition | 0 | 0 | 0 | `0.0%` | `0.0%` | **`0.000`** | `100.0%` | `Undefined` | `1.39x` |

## 2. Same-Champion Collision Breakdown

- **Total Collision ROLL Events**: `10` / 28 (`35.7%`)
- **Impact on Rule Candidates**:
  • `ROLL_A` (requires shop >= 1 & board/bench unchanged): TP=16, FN=12
  • `ROLL_D` (collision-aware shop transition): TP=16, FN=12

## 3. Rule Conflicts Summary

- **Total Multi-Rule Conflict Events**: `34`
