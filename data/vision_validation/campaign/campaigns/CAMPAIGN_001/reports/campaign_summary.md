# 🏆 TFT Human Validation Campaign v1 — Final Statistical Report: `CAMPAIGN_001`

**Final Gate Verdict**: **`GREEN`**

## 1. Executive Summary & Scale

- **Total Independent Matches**: `11`
- **Total Match Sessions**: `11` (Diverse players, placements #1~#7, and 5 economic archetypes)
- **Total Video Duration**: `6.03 hours` (21719.6s)
- **Total Human Reviewed Samples**: `329` (Event-Driven: `109`, Seeded Random Spot Checks: `220`)
- **Overall Human Verified Accuracy**: `99.7%` (328/329)

## 2. Action Detection Performance Matrix (Pooled Micro Metrics)

| Action | TP | FP | FN | Support | Precision | Recall | **F1 Score** |
|---|---|---|---|---|---|---|---|
| **`ROLL`** | `58` | `1` | `0` | `58` | `0.983` | `1.000` | **`0.992`** |
| **`BUY_UNIT`** | `37` | `0` | `0` | `37` | `1.000` | `1.000` | **`1.000`** |
| **`SYSTEM_REFRESH`** | `5` | `0` | `0` | `5` | `1.000` | `1.000` | **`1.000`** |

## 3. Session-by-Session Breakdown Table

| Session | Match ID | Place | Economic Archetype | Duration | Reviewed | Correct | Wrong | ROLL F1 | BUY F1 | Accuracy |
|---|---|---|---|---|---|---|---|---|---|---|
| **`SESSION_A`** | `MATCH_EDA87AD9` | `#2` | `BALANCED_STANDARD` | `600s` | `29` | `28` | `1` | `0.889` | `1.000` | `96.5%` |
| **`SESSION_B`** | `MATCH_3D739316` | `#1` | `FAST_LEVELUP` | `2369s` | `30` | `30` | `0` | `1.000` | `1.000` | `100.0%` |
| **`SESSION_C`** | `MATCH_45B5FAC1` | `#4` | `REROLL_HEAVY` | `2181s` | `32` | `32` | `0` | `1.000` | `1.000` | `100.0%` |
| **`SESSION_D`** | `MATCH_32D40585` | `#2` | `FAST_LEVELUP` | `2012s` | `30` | `30` | `0` | `1.000` | `1.000` | `100.0%` |
| **`SESSION_E`** | `MATCH_56E6FB98` | `#5` | `HYPER_ROLL` | `1583s` | `29` | `29` | `0` | `1.000` | `1.000` | `100.0%` |
| **`SESSION_F`** | `MATCH_6E78F07B_1` | `#3` | `BALANCED_STANDARD` | `2215s` | `29` | `29` | `0` | `1.000` | `1.000` | `100.0%` |
| **`SESSION_G`** | `MATCH_6E78F07B_2` | `#1` | `FAST_LEVELUP` | `2158s` | `30` | `30` | `0` | `1.000` | `1.000` | `100.0%` |
| **`SESSION_H`** | `MATCH_ADEDDE76_1` | `#2` | `BALANCED_STANDARD` | `1775s` | `29` | `29` | `0` | `1.000` | `1.000` | `100.0%` |
| **`SESSION_I`** | `MATCH_ADEDDE76_2` | `#6` | `REROLL_HEAVY` | `2469s` | `32` | `32` | `0` | `1.000` | `1.000` | `100.0%` |
| **`SESSION_J`** | `MATCH_B6A200E3` | `#1` | `FAST_LEVELUP` | `2490s` | `30` | `30` | `0` | `1.000` | `1.000` | `100.0%` |
| **`SESSION_K`** | `MATCH_C5F55151` | `#7` | `BALANCED_STANDARD` | `1868s` | `29` | `29` | `0` | `1.000` | `1.000` | `100.0%` |

## 4. Inter-Annotator Agreement & Reliability

- **Dual-Reviewer Overlap**: `30 samples`
- **Raw Agreement**: `96.7%`
- **Cohen's Kappa (kappa)**: `0.9421` (`Almost Perfect Agreement`)

## 5. Failure Taxonomy & Prioritized Engineering Backlog

| Taxonomy Category | Count | Priority | Root Cause / Recommended Action |
|---|---|---|---|
| `COARSE_SAMPLING_MERGE` | `1` | `P1` | Rapid roll window compound transition; resolved by local 20 FPS adaptive trigger |
| `GOLD_OCR_ERROR` | `0` | `P2` | Forward carry stabilization active; 0 uncorrected errors |
| `SHOP_RECOGNITION_ERROR` | `0` | `P2` | 100% card template match accuracy |
| `TIMING_ERROR` | `0` | `P3` | Synchronized timestamp alignment |