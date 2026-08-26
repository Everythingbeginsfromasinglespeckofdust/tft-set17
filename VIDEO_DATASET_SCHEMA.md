# TFT Video Dataset Schema & Specification (v1.0)

## 1. Schema Hierarchy

```text
Observation (Physical Screen Measurement)
    ↓
ActionEvent (Atomic Action with Source & Evidence)
    ↓
GameState (Domain Normalized State via Causal Builder)
    ↓
BacktestSample (MIDGAME_DECISION_SNAPSHOT)
```

---

## 2. Field Specifications

### 2.1 `Observation` Schema (`timeline.json`)
```json
{
  "timestamp_sec": 321.4,
  "frame_index": 19284,
  "stage_text": "3-2",
  "gold_val": 35,
  "hp_val": 60,
  "level_val": 7,
  "shop_cards": [
    {
      "slot_index": 0,
      "champion_pred": "Miss Fortune",
      "cost_pred": 3,
      "confidence": 0.92,
      "is_empty": false,
      "source": "hybrid_shop_recognizer"
    }
  ],
  "sources": {
    "shop": "hybrid_shop_recognizer",
    "stage": "ocr_tesseract",
    "gold": "ocr_tesseract"
  },
  "overall_confidence": 0.88
}
```

### 2.2 `ActionEvent` Schema
```json
{
  "action_type": "ROLL",
  "source": "OBSERVED",
  "timestamp_sec": 322.0,
  "confidence": 0.95,
  "evidence": [
    "Shop cards changed in 4/5 slots simultaneously",
    "Player gold decreased by exactly 2G (reroll cost)"
  ],
  "evidence_data": {
    "diff_slots_count": 4,
    "gold_diff": 2
  },
  "quality_flag": "VALID"
}
```

### 2.3 `BacktestSample` Schema (`samples.jsonl`)
```json
{
  "sample_id": "VID_VIDEO_SE_322_004",
  "match_id": "VIDEO_SESSION_AUDIT",
  "participant_id": "LOCAL_PLAYER",
  "snapshot_type": "MIDGAME_DECISION_SNAPSHOT",
  "decision_timestamp_sec": 322.0,
  "horizon_rounds": 13,
  "observed_state": {
    "stage": 3,
    "round_num": 2,
    "stage_round": "3-2",
    "gold": 35,
    "level": 7,
    "hp": 60,
    "actual_action": "ROLL",
    "actual_action_evidence": "Shop cards changed in 4/5 slots simultaneously; Player gold decreased by exactly 2G (reroll cost)",
    "timestamp_sec": 322.0
  },
  "future_observation": {
    "final_placement": 2,
    "top4": true,
    "horizon_rounds": 13,
    "outcome_timestamp_sec": 1920.0
  },
  "metadata": {
    "action_source": "OBSERVED",
    "detection_confidence": 0.95,
    "quality_flag": "VALID",
    "identity_link_status": "VERIFIED"
  }
}
```

---

## 3. Action Source Rules

| Action | Allowable Source | Detection / Inference Condition |
|---|---|---|
| `ROLL` | `OBSERVED` | Shop diff $\ge 3$ or Gold $-2\text{G}$ with shop transition |
| `BUY_UNIT` | `OBSERVED` | Card transition to empty + Gold $- \text{Cost}$ |
| `LEVEL_UP` | `OBSERVED` | Level increment or Gold $- 4\text{G}$ XP purchase |
| `SAVE_GOLD` | **`INFERRED` only** | Absence of economic actions over $\ge 10\text{s}$ decision window |
| `UNKNOWN` | `UNKNOWN` | Confidence $< 0.60$ or ambiguous screen noise |
