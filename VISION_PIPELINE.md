# TFT Vision Pipeline Technical Specification (v1.0)

## 1. Overview

The TFT Vision-to-Backtest Pipeline transforms continuous game video recordings into structured, timestamped observation streams, causal game state timelines, and verified MIDGAME backtest samples.

```text
Game Video (.mp4) / Timeline JSON
             ↓
VisionPipeline (Frame Sampling & Multi-Recognizer Coordination)
             ↓
ObservationTimeline (Timestamped Physical Screen Detections)
             ↓
ActionInferenceEngine (Multi-Signal Action Extraction & Window-based Inferred SAVE_GOLD)
             ↓
GameStateReconstructor (Strictly Causal Forward-Only Smoothing)
             ↓
VideoDatasetBuilder (Verified MIDGAME Decision Snapshots)
             ↓
BacktestRunner / Evaluator / CLI Tools
```

---

## 2. Core Architecture & Modules

### 2.1 `src/tft/vision/observation.py`
- `ObservedField`: Encapsulates physical screen detections with explicit extraction source (e.g. `ocr`, `template_matching`, `hsv_color`) and detection confidence.
- `Observation`: Complete multi-slot screen detection snapshot at timestamp $T$.

### 2.2 `src/tft/vision/events.py`
- `VisionActionType`: `ROLL`, `BUY_UNIT`, `SELL_UNIT`, `LEVEL_UP`, `BUY_XP`, `SAVE_GOLD`, `ITEM_COMBINE`, `AUGMENT_SELECT`, `POSITION_CHANGE`, `UNKNOWN`.
- `ActionSource`:
  - `OBSERVED`: Directly detected from physical screen transitions.
  - `INFERRED`: Strictly reserved for passive economic choices (e.g. `SAVE_GOLD`) over a verified decision window.
  - `UNKNOWN`: Insufficient signal confidence.
- `ActionEvent`: Immutable event sourcing entity with structured evidence list and quality flags.

### 2.3 `src/tft/vision/timeline.py`
- `ObservationTimeline`: Chronologically sorted container enforcing strict timestamp monotonicity ($t_i \ge t_{i-1}$) and deterministic event ordering.

### 2.4 `src/tft/vision/game_state_reconstruction.py`
- `GameStateReconstructor`: Causal forward-only reconstruction. Never uses future observations to alter past game states (zero hindsight leakage). Applies forward debouncing on OCR flickers and enforces domain monotonicity constraints on level and stage.

### 2.5 `src/tft/backtest/action_inference.py`
- Multi-evidence detection rules:
  - **ROLL**: $\ge 3$ shop cards changed simultaneously, or gold decreased by 2G with shop transition.
  - **BUY_UNIT**: Single shop card transitioned to empty with matching unit cost decrease.
  - **LEVEL_UP**: Level increase or 4G XP purchase.
  - **SAVE_GOLD**: Absence of any economic action in a $\ge 10.0\text{s}$ preparation window (marked as `INFERRED`).

---

## 3. CLI Usage

```bash
# Process video into MIDGAME dataset
python build_video_dataset.py \
    --video output/video_analysis/10min_audit/shop_timeline.json \
    --output data/backtest/video_dataset

# Inspect timeline & action events
python inspect_timeline.py \
    --input data/backtest/video_dataset/timeline.json
```
