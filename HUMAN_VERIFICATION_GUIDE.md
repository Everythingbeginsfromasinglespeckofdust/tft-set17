# TFT Vision Validation Overlay — Human Verification Guide

## 1. Keyboard Shortcuts & Controls

| Key | Action | Description |
|---|---|---|
| **`Space`** | **Play / Pause** | Toggle video replay playback |
| **`Left Arrow` / `q`** | **Step Frame Backward** | Step 1 frame backward (-1) |
| **`Right Arrow` / `e`** | **Step Frame Forward** | Step 1 frame forward (+1) |
| **`C`** | **[✓ CORRECT]** | Mark current prediction as correct |
| **`W`** | **[✗ WRONG]** | Mark current prediction as wrong (Auto-captures diagnostic snapshot) |
| **`X`** | **[SKIP]** | Skip current sample from evaluation |
| **`E`** | **[EDIT]** | Edit current prediction |
| **`R`** | **Annotate ROLL** | Directly assign human ground truth action `ROLL` |
| **`B`** | **Annotate BUY** | Directly assign human ground truth action `BUY_UNIT` |
| **`L`** | **Annotate LEVEL** | Directly assign human ground truth action `LEVEL_UP` |
| **`N`** | **Annotate NO_ACTION** | Directly assign human ground truth action `NO_ACTION` |
| **`S`** | **Annotate SYSTEM** | Directly assign human ground truth action `SYSTEM_REFRESH` |
| **`T`** | **Toggle ROIs** | Show/hide bounding boxes for Gold, Stage, Shop Slots, Board, Bench |
| **`1` ~ `4`** | **Playback Speed** | Select speed: `1`=0.25x, `2`=0.5x, `3`=1.0x, `4`=2.0x |
| **`Esc`** | **Exit** | Close application and save summary |

---

## 2. Error Snapshot Storage Structure

When **`[W]`** (Wrong) is pressed, the system automatically saves:
```text
data/vision_validation/frames/{SESSION_ID}/error_{TIMESTAMP}/
  ├── frame_before.png         # Frame before action transition
  ├── frame_current.png        # Frame at moment of detection
  ├── frame_after.png          # Frame after action transition
  └── error_diagnostics.json   # Snapshot containing Observation, StateDiff, and Action candidate data
```

---

## 3. Ground Truth Dataset Export

To export a clean ground truth dataset from human-verified logs:
```bash
python export_verified_dataset.py --session SESSION_A --output data/vision_validation/ground_truth/gt_session_a.json
```
