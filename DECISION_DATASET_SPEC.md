# TFT Decision Validation Dataset Specification

## 1. Directory Structure

```text
data/decision_validation/
├── sessions/
│   └── {SESSION_ID}/
│       ├── predictions.jsonl          # Immutable model recommendations & score breakdowns
│       ├── decision_reviews.jsonl     # Human qualitative judgments & blind preferences
│       └── decision_corrections.jsonl # Correction notes
├── outcomes/
│   └── outcomes_{SESSION_ID}.jsonl    # Observed T1+ round outcomes & placements
├── failure_cases/
│   └── fail_{RECORD_ID}.json          # Diagnostic failure cases for questionable decisions
├── ground_truth/
│   └── human_decision_labels.jsonl    # Clean exported human-annotated decision dataset
├── reports/
│   ├── decision_validation_summary.json
│   ├── decision_validation_summary.md
│   └── state_stratification.csv
└── improvement_backlog.jsonl          # Prioritized engineering backlog
```

---

## 2. JSON Schema Examples

### `predictions.jsonl`
```json
{
  "record_id": "DEC_SESSION_A_0001",
  "session_id": "SESSION_A",
  "timestamp_sec": 312.5,
  "observed_state": {
    "stage": 3,
    "round": 2,
    "stage_round": "3-2",
    "gold": 35,
    "hp": 60,
    "level": 7
  },
  "recommendation": {
    "recommended_action": "SAVE_GOLD",
    "action_score_gap": 0.0512,
    "action_scores": {
      "SAVE_GOLD": 0.3621,
      "ROLL": 0.3109,
      "LEVEL_UP": 0.2415
    },
    "reasons": [
      "HP is above crisis threshold",
      "No immediate high-value upgrade target"
    ]
  }
}
```
