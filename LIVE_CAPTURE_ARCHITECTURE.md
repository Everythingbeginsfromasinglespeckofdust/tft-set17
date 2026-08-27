# TFT Live Capture Architecture Specification

## 1. Overview & Latency Management
The Live Capture subsystem enables real-time screen capture of the TFT client window on Windows desktops with minimal latency and strict backpressure control.

```text
Desktop Screen (GDI / DirectX)
            ↓
DesktopCaptureFrameSource (mss)
            ↓
  Bounded Queue (maxsize=2)
  [Drop oldest frame if full]
            ↓
  VisionAnalysisManager
            ↓
  OverlayState (Data Age < 0.1s)
            ↓
  DirectHUD / Production Overlay
```

---

## 2. Key Components

### A. `DesktopCaptureFrameSource`
- Captures primary or secondary display / TFT window bounding box using `mss`.
- Operates on a background daemon capture thread at target 30 FPS.
- Implements **drop-oldest backpressure**: when the analysis worker is busy, intermediate frames are dropped to keep **Data Age $< 0.10\text{s}$**.

### B. Latency Measurement Metrics
- **`Capture Timestamp`**: Time $T_{\text{cap}}$ recorded at screen grab.
- **`Data Age`**: $T_{\text{render}} - T_{\text{cap}}$. Displayed continuously on the HUD.
- **`End-to-End Latency`**: Measured in milliseconds ($40\text{ms} \sim 80\text{ms}$ typical).

---

## 3. Production Deployment Mode
To run the overlay in lightweight production HUD mode (disabling annotation controls and heavy debug rendering):
```bash
python vision_overlay.py --mode production --source live
```
