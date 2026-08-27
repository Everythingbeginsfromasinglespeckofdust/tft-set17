# TFT Human Validation Campaign v1 Specification

## 1. Overview & Objectives
**TFT Human Validation Campaign v1** establishes an operational, multi-match human validation infrastructure across 11 independent real game recordings, validating that the frozen production vision pipeline operates robustly across diverse players, placements (#1 through #7), match lengths, and economic archetypes.

```text
Real TFT Video (11 Matches)
            ↓
Frozen Production Pipeline
            ↓
Validation Overlay / Review Queue
            ↓
Independent Human Reviewer (Blind Mode)
            ↓
Human Verdicts (CORRECT / WRONG / EDIT / SKIP)
            ↓
Automatic Error Snapshots (Frames + JSONs)
            ↓
Ground Truth Dataset Export & Improvement Backlog (P0~P3)
```

---

## 2. Multi-Session Scale & Demographics

| Session ID | Match ID | Placement | Economic Archetype | Duration | Video File |
|---|---|---|---|---|---|
| **`SESSION_A`** | `MATCH_EDA87AD9` | `#2` | `BALANCED_STANDARD` | `600.0s` | `eda87ad9...mp4` |
| **`SESSION_B`** | `MATCH_3D739316` | `#1` | `FAST_LEVELUP` | `2368.8s` | `3d739316...mp4` |
| **`SESSION_C`** | `MATCH_45B5FAC1` | `#4` | `REROLL_HEAVY` | `2180.7s` | `45b5fac1_part2...mp4` |
| **`SESSION_D`** | `MATCH_32D40585` | `#2` | `FAST_LEVELUP` | `2011.5s` | `32d40585...mp4` |
| **`SESSION_E`** | `MATCH_56E6FB98` | `#5` | `REROLL_HEAVY` | `1582.0s` | `56e6fb98...mp4` |
| **`SESSION_F`** | `MATCH_6E78F07B_1` | `#3` | `BALANCED_STANDARD` | `2213.9s` | `6e78f07b...mp4` |
| **`SESSION_G`** | `MATCH_6E78F07B_2` | `#1` | `LOSS_STREAK_RECOVERY` | `2157.3s` | `6e78f07b_part2...mp4` |
| **`SESSION_H`** | `MATCH_ADEDDE76_1` | `#2` | `TEMPO_AGGRESSIVE` | `1774.2s` | `adedde76...mp4` |
| **`SESSION_I`** | `MATCH_ADEDDE76_2` | `#6` | `SLOW_ROLL_6` | `2467.7s` | `adedde76_part2...mp4` |
| **`SESSION_J`** | `MATCH_B6A200E3` | `#1` | `FAST_LEVELUP` | `2489.6s` | `b6a200e3...mp4` |
| **`SESSION_K`** | `MATCH_C5F55151` | `#7` | `LOSS_STREAK_RECOVERY` | `1867.4s` | `c5f55151...mp4` |

---

## 3. Review Queue & Sampling Methodology

To eliminate sampling bias, the review queue combines:
1. **Event-Driven Candidate Generation**: Triggers on detected actions (`ROLL`, `BUY_UNIT`, `LEVEL_UP`, `SYSTEM_REFRESH`), state transitions ($\Delta G \ne 0$, Shop transitions $\ge 2$), and vision anomalies.
2. **Seeded Random Spot Checks**: Exactly 20 seeded checkpoints per session uniformly sampled across `EARLY_GAME` ($<400\text{s}$), `MID_GAME` ($400\text{s}\sim 900\text{s}$), and `LATE_GAME` ($>900\text{s}$).

---

## 4. Prioritized Engineering Backlog

Failures are categorized into standard taxonomy classes and assigned engineering priorities:
- **`P0`**: Critical regression / pipeline halting failures.
- **`P1`**: High-frequency or core economic action misclassifications.
- **`P2`**: Moderate-frequency state diff or OCR jitter errors.
- **`P3`**: Minor visual jitter / rare edge cases.
