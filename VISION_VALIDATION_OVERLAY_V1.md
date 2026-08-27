# TFT Vision Validation Overlay v1 Specification

## 1. Overview & Architectural Goals
**TFT Vision Validation Overlay v1** provides a real-time, interactive HUD and verification pipeline for the TFT Vision Analysis Core. It bridges offline video replay analysis with online live desktop capture, ensuring that:
1. Human auditors can visually observe and verify vision pipeline detections in real-time or during video replay.
2. Single-click feedback (`[✓ CORRECT]`, `[✗ WRONG]`, `[EDIT]`, `[SKIP]`) automatically captures error snapshots and generates Ground Truth datasets.
3. Both **VIDEO_MODE** (video replay) and **LIVE_CAPTURE_MODE** (desktop screen capture) share the exact same Analysis Core (`VisionAnalysisManager`).

```text
                    ┌─────────────────────────┐
                    │      Input Source       │
                    └────────────┬────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 │                               │
            VIDEO_MODE                   LIVE_CAPTURE_MODE
          (Video Replay)                 (Desktop Capture)
                 │                               │
                 └───────────────┬───────────────┘
                                 ↓
                       FrameSource Protocol
                                 ↓
                       Vision Analysis Core
                                 ↓
        ┌────────────────────────┼────────────────────────┐
        ↓                        ↓                        ↓
  ShopRecognizerV2        GoldRecognizer          StateStability
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 ↓
                            Observation
                                 ↓
                             StateDiff
                                 ↓
                      ActionEventDetectorV2.2
                                 ↓
                         OverlayState HUD
                                 ↓
                     Human Verification Bar
                                 ↓
                    VerificationStore (JSONL)
```

---

## 2. 4-Layer Information State Model

| Layer | Type | Content | Display Style |
|---|---|---|---|
| **Layer A** | **Observed** | Gold, HP, Level, Stage, 5 Shop Slots, Board/Bench units | Raw recognized values with status badges (`RECOGNIZED`, `EMPTY`, `LOW_CONFIDENCE`) |
| **Layer B** | **Derived** | `StateDiff`: Gold $\Delta$, Shop slots changed, Board/Bench unchanged | Highlighted change indicators (e.g. `Gold Δ -2G`) |
| **Layer C** | **Detected** | Action events (`ROLL`, `BUY_UNIT`, `LEVEL_UP`, `SYSTEM_REFRESH`) | Rule Signal Checklist (`[✓] Gold -2`, `[✓] Shop Transition`, `[✓] Not System Refresh`) |
| **Layer D** | **Verification** | Human judgments (`CORRECT`, `WRONG`, `UNKNOWN`, `EDITED`, `SKIPPED`) | Interactive buttons & real-time tally |

---

## 3. Strict Invariants

1. **Prediction Preservation**: Human corrections never overwrite raw detector predictions.
2. **Ground Truth Independence**: Ground Truth is never fed back into the live detector.
3. **No Calibrated Probabilities**: Rule evidence is rendered as signal checklists and raw detection scores ($0.0 \sim 1.0$), not false accuracy claims.
4. **Decoupled Ticks**: Frame Ingestion / Rendering (30~60 FPS) runs independently from the Vision Analysis Tick (10~20 FPS).
