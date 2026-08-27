# TFT Video Replay Validation Report v1.1 — Event-Stratified Expansion

**Session**: `VIDEO_REPLAY_002`  
**Source Type**: **`VIDEO_REPLAY`** (Strictly Video Replay, NOT Real Live)  
**Gate Verdict**: **`VIDEO_REPLAY_VALIDATED`**  
**Video File**: `56e6fb98-3716-4124-b4f1-8718629b533c-2026-08-26-23-20-20.mp4`  
**Video SHA256**: `b7c90a99a4caebeedae541b110f3ae2044a1c0a27068c740fd1685bdd7083a3b`  
**Duration**: 26.4 min (1582.6s) | 1280x720 @ 60.0 fps  
**Validated Checkpoints**: **25 / 25**  

---

## 1. Event Stratification & Sampling Distribution

| Event Type | Count | Ratio |
|---|---|---|
| **`BOARD_CHANGE`** | 3 | 12.0% |
| **`BUY_UNIT`** | 3 | 12.0% |
| **`NO_ACTION`** | 4 | 16.0% |
| **`ROLL`** | 8 | 32.0% |
| **`SYSTEM_REFRESH`** | 7 | 28.0% |

### Temporal Distribution
- **Early Game (Stage 2)**: 10 checkpoints
- **Mid Game (Stage 3-4)**: 15 checkpoints
- **Late Game (Stage 5+)**: 0 checkpoints

---

## 2. Domain Accuracies (Independent Denominators)

| Domain | Correct | Wrong | Unknown | Total | Accuracy |
|--------|---------|-------|---------|-------|----------|
| **Shop Recognition** | 25 | 0 | 0 | 25 | **100.0%** |
| **Gold Recognition** | 25 | 0 | 0 | 25 | **100.0%** |
| **Board Units** | 25 | 0 | 0 | 25 | **100.0%** |
| **Action Detection** | 25 | 0 | 0 | 25 | **100.0%** |
| **GameState Validity** | 25 | 0 | 0 | 25 | **100.0%** |

### Action Precision / Recall / F1
- **Action Precision**: 100.0%
- **Action Recall**: 100.0%
- **Action F1 Score**: 100.0%

---

## 3. Stratified Checkpoint Registry

| Checkpoint ID | Video Time | Stage | Event Type | Shop | Gold | Board | Action | CALIB Flip | Final Action | Quality |
|---|---|---|---|---|---|---|---|---|---|---|
| `VCHK_0000_SYSTEM_REFRESH_5C729E` | 85.0s | 2-3 | `SYSTEM_REFRESH` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0001_SYSTEM_REFRESH_F1791A` | 99.0s | 2-3 | `SYSTEM_REFRESH` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0002_ROLL_038608` | 120.0s | 2-4 | `ROLL` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0003_ROLL_425456` | 129.0s | 2-4 | `ROLL` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0004_ROLL_6C2D3B` | 136.0s | 2-4 | `ROLL` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0005_SYSTEM_REFRESH_AF1FE5` | 141.5s | 2-4 | `SYSTEM_REFRESH` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0006_SYSTEM_REFRESH_0459DE` | 162.0s | 2-5 | `SYSTEM_REFRESH` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0007_NO_ACTION_D11462` | 180.0s | 2-5 | `NO_ACTION` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0008_SYSTEM_REFRESH_7F93E4` | 189.5s | 2-5 | `SYSTEM_REFRESH` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0009_BOARD_CHANGE_5D5343` | 193.0s | 2-5 | `BOARD_CHANGE` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0010_NO_ACTION_720481` | 240.0s | 3-1 | `NO_ACTION` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0011_BOARD_CHANGE_36DB48` | 248.0s | 3-1 | `BOARD_CHANGE` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0012_ROLL_C48CDF` | 272.5s | 3-1 | `ROLL` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0013_SYSTEM_REFRESH_6975F8` | 280.0s | 3-2 | `SYSTEM_REFRESH` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0014_BUY_UNIT_0D663B` | 295.0s | 3-2 | `BUY_UNIT` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0015_BUY_UNIT_8BF871` | 311.5s | 3-2 | `BUY_UNIT` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0016_ROLL_571990` | 364.0s | 3-4 | `ROLL` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0017_ROLL_DA9269` | 372.5s | 3-4 | `ROLL` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0018_ROLL_9F1670` | 384.0s | 3-4 | `ROLL` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0019_BUY_UNIT_6D2404` | 401.0s | 3-5 | `BUY_UNIT` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0020_BOARD_CHANGE_4C18CA` | 443.0s | 3-6 | `BOARD_CHANGE` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0021_SYSTEM_REFRESH_EC9B54` | 462.0s | 3-6 | `SYSTEM_REFRESH` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0022_NO_ACTION_FC639D` | 480.0s | 4-1 | `NO_ACTION` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0023_NO_ACTION_52D674` | 540.0s | 4-2 | `NO_ACTION` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0024_ROLL_03177A` | 576.5s | 4-3 | `ROLL` | CORRECT | CORRECT | CORRECT | CORRECT | NO | `SAVE_GOLD` | REASONABLE |

---

## 4. Runtime Performance Benchmarks

- **Mean End-to-End Pipeline**: 380.842 ms
- **P95 Pipeline Latency**: 468.847 ms
- **Gold OCR Latency**: 116.661 ms
- **Shop Recognizer Latency**: 263.723 ms
- **Decision Engine Latency**: 0.396 ms

---

## 5. Verification Guarantees

1. **Strict Lineage**: Every checkpoint points to physical frame PNG file on disk and verifies SHA256 hash.
2. **Label Independence**: Human labels are recorded from physical keyboard events without automatic copying of model predictions.
3. **No Synthetic / Fixture Contamination**: All inputs are decoded from actual MP4 frames.
4. **No Temporal Leakage**: Decision inputs are strictly bounded to $T_0$.
5. **Production Core Invariance**: `src/tft/decision/`, `src/tft/simulation/`, `src/tft/evaluation/`, `src/tft/domain/` remain 100% frozen.
