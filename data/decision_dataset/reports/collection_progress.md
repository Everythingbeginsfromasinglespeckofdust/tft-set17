# TFT Real Match Dataset Collection Progress Dashboard v1.1

## Current Gate Verdict: `DATA_COLLECTION_IN_PROGRESS`

### Live Summary Stats (Calculated directly from raw dataset)
- **Independent Matches**: **1 / 5** (Minimum Target: 5, Recommended: 10)
- **Total Sessions**: **1**
- **Total Checkpoints**: **20** (Target: ≥ 75)
- **Valid Checkpoints**: **20**
- **Dual Reviewed Checkpoints**: **0**
- **T1 Outcome Linked**: **19 (95.0%)**
- **Frame Evidence Completeness**: **100.0%**
- **Label Contamination**: **0 (Clean)**

---

### Session Progress Tracker

| Session ID | Match ID | Video File | Resolution | FPS | Total CPs | Placement | Status |
|---|---|---|---|---|---|---|---|
| `SESSION_001` | `REAL_MATCH_562ffca4` | `562ffca4-3f1b-46be-8791-92fa6305388a-2026-08-30-22-31-00.mp4` | 1280x720 | 60 | 20 | 2 | ✅ Recorded |

---

### Collection Checklist for Next Session
1. Select next raw recording from `tft-recordings` folder.
2. Launch `/collection` mode in Web Assistant (`run_decision_assistant.py`).
3. Maintain blind preference quota (100% blind entry before reveal).
4. Perform dual review on at least 10% of checkpoints.
5. Finalize session post-match to lock placement and link T1/T2/T3 outcomes.
