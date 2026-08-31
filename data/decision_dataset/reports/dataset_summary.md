# TFT Real Match Decision Dataset Collection v1.1 — Summary Report

## Final Gate Status: `DATA_COLLECTION_IN_PROGRESS`

> **Schema Version**: `DECISION_DATASET_V1_1`
> **Current Readiness**: DATA_COLLECTION_IN_PROGRESS: Collect additional real match sessions (current: 1/5 matches) before running calibration.

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
| Frame Evidence Completeness | **100.0%** | ≥ 95.0% | ≥ 99.0% |
| Fake Data Detected | **0** | 0 | 0 |

---

## 2. Session Manifests

| Session ID | Match ID | Video File | Resolution | FPS | Total CPs | Placement |
|---|---|---|---|---|---|---|
| `SESSION_001` | `REAL_MATCH_562ffca4` | `562ffca4-3f1b-46be-8791-92fa6305388a-2026-08-30-22-31-00.mp4` | 1280x720 | 60 | 20 | 2 |

---

## 3. Calibration Ready Gate Checklist

| Requirement | Target | Actual | Passed? |
|---|---|---|---|
| Matches ≥ 5 | ≥ 5 | 1 | ❌ (In Progress) |
| Checkpoints per match ≥ 15 | ≥ 15 | Verified | ✅ |
| Early / Mid / Late Coverage | Stages 2, 3-4, 5+ | Verified | ✅ |
| Actual Action Coverage | ≥ 80% | 100.0% | ✅ |
| Human Preference Coverage | ≥ 80% | 100.0% | ✅ |
| T1 Outcome Linked | ≥ 70% | 95.0% | ✅ |
| Frame Evidence Complete | ≥ 95% | 100.0% | ✅ |
| No Fake Data / Contamination | 0 flags | 0 flags | ✅ |
