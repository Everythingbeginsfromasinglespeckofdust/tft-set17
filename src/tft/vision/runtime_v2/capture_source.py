import hashlib, io, json, time, os
from typing import Optional, Dict, Any

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    import pygetwindow as gw
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

KEYWORDS = ["teamfight tactics", "league of legends", "riot client"]


class TFTWindowInfo:
    def __init__(self, title, rect, handle=0):
        self.title_sanitized = next(
            (kw.title() for kw in KEYWORDS if kw in title.lower()), title
        )
        self.rect = rect
        self.handle = handle


def detect_tft_window():
    """Find TFT client window. Returns None if not found."""
    if not WIN32_AVAILABLE:
        return None
    try:
        for w in gw.getAllWindows():
            if not w.title or not w.visible:
                continue
            for kw in KEYWORDS:
                if kw in w.title.lower():
                    rect = {
                        "left": w.left, "top": w.top,
                        "width": w.width, "height": w.height,
                    }
                    return TFTWindowInfo(w.title, rect)
    except Exception:
        pass
    return None


class RealCaptureSource:
    """Real mss-based screen capture. Raises EnvironmentError if unavailable."""

    def __init__(self, monitor_index=1, require_tft=True):
        if not MSS_AVAILABLE:
            raise EnvironmentError("mss not installed. Cannot capture real frames.")
        if not PIL_AVAILABLE:
            raise EnvironmentError("PIL not installed. Cannot save frames.")
        self.monitor_index = monitor_index
        self.tft_window = None
        self._sct = None
        if require_tft:
            self.tft_window = detect_tft_window()
            if self.tft_window is None:
                raise EnvironmentError(
                    "NO_TFT_CLIENT: TFT client window not found. "
                    "Open TFT and try again."
                )

    def __enter__(self):
        self._sct = mss.mss()
        return self

    def __exit__(self, *a):
        if self._sct:
            self._sct.close()

    def capture_frame(self):
        """Capture real frame. Returns (png_bytes, metadata)."""
        if self._sct is None:
            raise RuntimeError("Use as context manager")
        monitors = self._sct.monitors
        idx = min(self.monitor_index, len(monitors) - 1)
        mon = monitors[idx]
        t_mono = time.monotonic()
        t_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        shot = self._sct.grab(mon)
        img = Image.frombytes("RGB", shot.size, shot.rgb)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png = buf.getvalue()
        sha = hashlib.sha256(png).hexdigest()
        meta = {
            "monitor_index": idx,
            "resolution_w": shot.width,
            "resolution_h": shot.height,
            "capture_timestamp_iso": t_iso,
            "capture_monotonic": t_mono,
            "frame_sha256": sha,
            "window_title_sanitized": (
                self.tft_window.title_sanitized if self.tft_window else "NO_WINDOW"
            ),
            "window_rect": self.tft_window.rect if self.tft_window else None,
        }
        return png, meta

    def capture_proof(self, output_dir):
        """Capture and save a startup proof frame."""
        png, meta = self.capture_frame()
        pp = os.path.join(output_dir, "capture_proof.png")
        with open(pp, "wb") as f:
            f.write(png)
        jp = os.path.join(output_dir, "capture_proof.json")
        with open(jp, "w", encoding="utf-8") as f:
            json.dump({**meta, "proof_frame_path": pp}, f, indent=2)
        return meta
