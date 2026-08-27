# TFT Blind Validation Mode Guide

## 1. Concept & Rationale
Prediction Blinding Mode (`BLIND_VALIDATION`) prevents reviewer confirmation bias. In standard validation, showing model predictions beforehand unconsciously influences human judgment. In Blind Validation, the human reviewer observes the raw frame first, inputs the true action/state label, and only then reveals the model prediction for automated discrepancy analysis.

---

## 2. Blind Validation Protocol

```text
1. Seek video to target review timestamp
2. Pause playback
3. Display raw video frame & ROI bounding boxes (Model prediction HIDDEN)
4. Reviewer inspects shop, gold, board, and action
5. Reviewer inputs Human Label (e.g. ROLL, BUY_UNIT, NO_ACTION)
6. System records human label in verifications.jsonl
7. System reveals Model Prediction
8. Automated comparison:
   - Match    → Marked CORRECT
   - Mismatch → Marked WRONG, Error Snapshots auto-saved, Backlog Item created
```

---

## 3. CLI Execution

```bash
# Run campaign in Prediction Blinding Mode
python run_validation_campaign.py --campaign CAMPAIGN_001 --blind --reviewer HUMAN_AUDITOR_1
```
