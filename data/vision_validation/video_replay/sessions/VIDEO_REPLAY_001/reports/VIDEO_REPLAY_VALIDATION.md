# TFT Video Replay Validation Report v1

**Session**: `VIDEO_REPLAY_001`  
**Source Type**: **`VIDEO_REPLAY`** (Strictly Video Replay, NOT Real Live)  
**Gate**: **`VIDEO_REPLAY_PRELIMINARY`**  
**Video File**: `56e6fb98-3716-4124-b4f1-8718629b533c-2026-08-26-23-20-20.mp4`  
**Video SHA256**: `b7c90a99a4caebeedae541b110f3ae2044a1c0a27068c740fd1685bdd7083a3b`  
**Duration**: 26.4 min (1582.6s) | 1280x720 @ 60.0 fps  
**Valid Checkpoints**: 10 / 10  

---

## 1. Domain Accuracies (Independent Denominators)

| Domain | Correct | Wrong | Unknown | Total | Accuracy |
|--------|---------|-------|---------|-------|----------|
| Shop | 10 | 0 | 0 | 10 | **100.0%** |
| Gold | 10 | 0 | 0 | 10 | **100.0%** |
| Board | 10 | 0 | 0 | 10 | **100.0%** |
| Action | 10 | 0 | 0 | 10 | **100.0%** |
| State | 10 | 0 | 0 | 10 | **100.0%** |

---

## 2. Checkpoint Details

| Checkpoint ID | Video Time | Key | Shop | Gold | Board | Action | CALIB Flip | Final Action | Quality |
|---|---|---|---|---|---|---|---|---|---|
| `VCHK_0000_5DBEF4` | 60.0s | `C` | CORRECT | CORRECT | CORRECT | SAVE_GOLD | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0001_509BE2` | 180.0s | `C` | CORRECT | CORRECT | CORRECT | SAVE_GOLD | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0002_8D78A2` | 300.0s | `C` | CORRECT | CORRECT | CORRECT | SAVE_GOLD | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0003_3C358A` | 420.0s | `C` | CORRECT | CORRECT | CORRECT | SAVE_GOLD | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0004_F27A1C` | 540.0s | `C` | CORRECT | CORRECT | CORRECT | SAVE_GOLD | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0005_9E7E16` | 660.0s | `C` | CORRECT | CORRECT | CORRECT | SAVE_GOLD | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0006_D87004` | 780.0s | `C` | CORRECT | CORRECT | CORRECT | SAVE_GOLD | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0007_E7B886` | 900.0s | `C` | CORRECT | CORRECT | CORRECT | SAVE_GOLD | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0008_59D574` | 1020.0s | `C` | CORRECT | CORRECT | CORRECT | SAVE_GOLD | NO | `SAVE_GOLD` | REASONABLE |
| `VCHK_0009_B94FB1` | 1140.0s | `C` | CORRECT | CORRECT | CORRECT | SAVE_GOLD | NO | `SAVE_GOLD` | REASONABLE |

---

## 3. Runtime Performance

- **Mean Pipeline Latency**: 298.291 ms
- **P95 Pipeline Latency**: 368.673 ms
- **Gold OCR Latency**: 123.939 ms
- **Shop Recognizer Latency**: 173.96 ms
- **Decision Engine Latency**: 0.336 ms

---

## 4. Integrity Verifications

- **Frame Evidence**: 100% of verified checkpoints have on-disk PNG frames matching SHA256
- **Video Source Traceability**: Every checkpoint traces back to video `56e6fb98-3716-4124-b4f1-8718629b533c-2026-08-26-23-20-20.mp4` (b7c90a99a4caebee...)
- **Label Independence**: Human labels derived strictly from keyboard events (no prediction auto-copy)
- **No Temporal Leakage**: T0 state has no future outcome information
- **Production Core Diff**: 0 lines changed in `src/tft/decision/`, `src/tft/simulation/`, `src/tft/evaluation/`, `src/tft/domain/`
