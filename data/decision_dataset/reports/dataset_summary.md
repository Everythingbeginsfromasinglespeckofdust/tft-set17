# TFT Real Match Decision Dataset Collection v1 — Summary Report

## Final Gate Status: `DATA_COLLECTION_IN_PROGRESS`

> **Current Readiness**: DATA_COLLECTION_IN_PROGRESS: Collect additional real match sessions (current: 1/5 matches) before running calibration.
> **Strict Principle**: Zero synthetic checkpoints used as real data. Zero model-to-human label auto-copying.

---

## 1. Dataset Overview

| Metric | Current Value | Min Target (Calibration) | Recommended Target (Production) |
|---|---|---|---|
| Independent Matches | **1** | 5 | 20 |
| Total Sessions | **1** | 5 | 20 |
| Total Checkpoints | **20** | 75 | 400 |
| Actual Action Coverage | **100.0%** | ≥ 80.0% | ≥ 95.0% |
| Human Preference Coverage | **100.0%** | ≥ 80.0% | ≥ 95.0% |
| T1 Outcome Coverage | **95.0%** | ≥ 70.0% | ≥ 90.0% |
| Fake Data Detected | **0** | 0 | 0 |

---

## 2. Session Manifests

| Session ID | Match ID | Video File | Resolution | FPS | Total CPs | Placement |
|---|---|---|---|---|---|---|
| `SESSION_001` | `REAL_MATCH_562ffca4` | `562ffca4-3f1b-46be-8791-92fa6305388a-2026-08-30-22-31-00.mp4` | 1280x720 | 60 | 20 | 2 |

---

## 3. State Diversity Distributions

### HP Distribution
- **71-100 (Safe)**: 6 (30.0%)
- **51-70 (Healthy)**: 2 (10.0%)
- **31-50 (Mid)**: 7 (35.0%)
- **16-30 (Danger)**: 3 (15.0%)
- **0-15 (Critical)**: 2 (10.0%)

### Gold Distribution
- **0-19G**: 5 (25.0%)
- **20-29G**: 4 (20.0%)
- **30-39G**: 3 (15.0%)
- **40-49G**: 5 (25.0%)
- **50G+**: 3 (15.0%)

### Action Distributions

| Action | Actual Player Actions | Human Preference Actions |
|---|---|---|
| `BUY_UNIT` | 1 (5.0%) | 0 (0.0%) |
| `LEVEL_UP` | 1 (5.0%) | 1 (5.0%) |
| `ROLL` | 4 (20.0%) | 5 (25.0%) |
| `SAVE_GOLD` | 14 (70.0%) | 14 (70.0%) |

---

## 4. Calibration Ready Gate Checklist

| Requirement | Target | Actual | Passed? |
|---|---|---|---|
| Matches ≥ 5 | ≥ 5 | 1 | ❌ (In Progress) |
| Checkpoints per match ≥ 15 | ≥ 15 | Verified | ✅ |
| Early / Mid / Late Coverage | Stages 2, 3-4, 5+ | Verified | ✅ |
| Actual Action Coverage | ≥ 80% | 100.0% | ✅ |
| Human Preference Coverage | ≥ 80% | 100.0% | ✅ |
| T1 Outcome Linked | ≥ 70% | 95.0% | ✅ |
| No Fake Data / Contamination | 0 flags | 0 flags | ✅ |

---

## 5. Next Steps for Data Acquisition

1. **Continue Human Entry**: Use Web Decision Assistant (`run_decision_assistant.py`) to record additional 4+ real matches from TFT video recordings.
2. **Conduct Blind Reviews**: Maintain minimum 25% blind review quota during live input.
3. **Link Outcomes**: Finalize sessions upon match conclusion to lock `final_placement` and link T1/T2 HP and gold deltas.
4. **Trigger Calibration**: Once `Matches >= 5`, transition status to `DATASET_CALIBRATION_READY` and initiate offline A/B calibration.
