# TFT Human Validation Dataset Specification

## 1. Directory Structure

```text
data/vision_validation/campaign/
└── campaigns/
    └── {CAMPAIGN_ID}/
        ├── manifest.json
        ├── sessions/
        │   └── {SESSION_ID}/
        │       ├── session_metadata.json
        │       ├── predictions.jsonl        # Raw immutable model predictions
        │       ├── verifications.jsonl      # Human judgment records
        │       └── corrections.jsonl        # Human corrected state values
        ├── review_queue/
        │   └── queue_{SESSION_ID}.jsonl     # Event-driven + random spot check items
        ├── frames/                          # Error diagnostic frame snapshots
        ├── ground_truth/
        │   └── ground_truth_{CAMPAIGN_ID}.jsonl  # Clean exported human ground truth
        ├── reports/
        │   ├── campaign_summary.json
        │   ├── campaign_summary.md
        │   ├── session_comparison.csv
        │   └── failure_taxonomy.json
        └── improvement_backlog.jsonl        # Prioritized engineering backlog
```

---

## 2. File Schema & Data Contracts

### `predictions.jsonl`
```json
{
  "timestamp_sec": 312.5,
  "frame_index": 6250,
  "prediction": {
    "action": "ROLL",
    "score": 0.90
  }
}
```

### `verifications.jsonl`
```json
{
  "review_id": "REV_SESSION_A_0004",
  "session_id": "SESSION_A",
  "timestamp_sec": 312.5,
  "frame_index": 6250,
  "trigger_type": "ACTION",
  "temporal_stage": "EARLY_GAME",
  "prediction": {"action": "ROLL", "score": 0.90},
  "reviewed": true,
  "human_verdict": "CORRECT",
  "human_label": "ROLL",
  "corrected_value": null,
  "error_reason": null,
  "reviewer_id": "HUMAN_AUDITOR_1"
}
```

### `ground_truth_{CAMPAIGN_ID}.jsonl`
```json
{
  "campaign_id": "CAMPAIGN_001",
  "session_id": "SESSION_A",
  "timestamp_sec": 312.5,
  "frame_index": 6250,
  "ground_truth_action": "ROLL",
  "temporal_stage": "EARLY_GAME",
  "human_verdict": "CORRECT",
  "reviewer_id": "HUMAN_AUDITOR_1"
}
```
