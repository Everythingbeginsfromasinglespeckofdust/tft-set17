"""Live Desktop Screen Capture FrameSource Implementation using mss with Backpressure Management."""
import queue
import threading
import time
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

try:
    import mss
except ImportError:
    mss = None

from tft.vision.frame_source import FrameSource, FramePacket


class DesktopCaptureFrameSource(FrameSource):
    """실제 TFT 게임 화면을 실시간 캡처하여 분석 파이프라인에 공급하는 Live FrameSource."""

    def __init__(
        self,
        monitor_index: int = 1,
        target_fps: float = 30.0,
        roi_bbox: Optional[Dict[str, int]] = None,
        target_width: int = 1280,
        target_height: int = 720
    ):
        self.monitor_index = monitor_index
        self.target_fps = target_fps
        self.dt = 1.0 / target_fps
        self.roi_bbox = roi_bbox
        self.target_width = target_width
        self.target_height = target_height

        self._running: bool = False
        self._paused: bool = False
        self._frame_count: int = 0
        self._dropped_frames: int = 0
        self._start_time: float = time.time()
        self._queue: queue.Queue = queue.Queue(maxsize=2)  # Bounded queue for low latency
        self._thread: Optional[threading.Thread] = None
        self._last_packet: Optional[FramePacket] = None

        if mss is not None:
            self._sct = mss.mss()
        else:
            self._sct = None

        self._start_capture_thread()

    def _start_capture_thread(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _capture_loop(self) -> None:
        """독립적인 스레드에서 화면을 지속적으로 캡처하여 큐에 유지."""
        if self._sct is None:
            return

        mon = self._sct.monitors[self.monitor_index] if self.monitor_index < len(self._sct.monitors) else self._sct.monitors[0]
        capture_region = self.roi_bbox or mon

        while self._running:
            t_loop_start = time.time()
            if not self._paused:
                try:
                    sct_img = self._sct.grab(capture_region)
                    # Convert BGRA to BGR numpy array
                    frame = np.array(sct_img)[:, :, :3]
                    if frame.shape[1] != self.target_width or frame.shape[0] != self.target_height:
                        frame = cv2.resize(frame, (self.target_width, self.target_height))

                    t_now = time.time()
                    self._frame_count += 1

                    packet = FramePacket(
                        frame=frame,
                        timestamp_sec=t_now - self._start_time,
                        frame_index=self._frame_count,
                        source_type="LIVE",
                        capture_timestamp_sec=t_now,
                        metadata={
                            "monitor_index": self.monitor_index,
                            "dropped_frames": self._dropped_frames,
                            "target_fps": self.target_fps
                        }
                    )

                    # Backpressure policy: Drop oldest if full to minimize latency
                    if self._queue.full():
                        try:
                            self._queue.get_nowait()
                            self._dropped_frames += 1
                        except queue.Empty:
                            pass

                    self._queue.put(packet)
                except Exception:
                    pass

            elapsed = time.time() - t_loop_start
            sleep_time = max(0.001, self.dt - elapsed)
            time.sleep(sleep_time)

    def read(self) -> Optional[FramePacket]:
        """큐에서 가장 최신의 실시간 프레임 패킷을 획득."""
        try:
            packet = self._queue.get(timeout=0.1)
            self._last_packet = packet
            return packet
        except queue.Empty:
            return self._last_packet

    def seek(self, timestamp_sec: float) -> None:
        """Live 모드에서는 Seek 불가능 (No-op)."""
        pass

    def current_timestamp(self) -> float:
        return time.time() - self._start_time

    def is_live(self) -> bool:
        return True

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def step_frame(self, delta: int = 1) -> Optional[FramePacket]:
        """Live 모드에서는 step 불가, 현재 프레임 반환."""
        return self._last_packet

    def set_speed(self, speed: float) -> None:
        """Live 모드에서는 속도 조절 불필요 (No-op)."""
        pass

    def get_dropped_frame_count(self) -> int:
        return self._dropped_frames

    def close(self) -> None:
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._sct is not None:
            self._sct.close()
