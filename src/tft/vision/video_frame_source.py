"""Video File FrameSource Implementation with Precision Playback and Frame-Stepping."""
import os
import time
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

from tft.vision.frame_source import FrameSource, FramePacket


class VideoFileFrameSource(FrameSource):
    """MP4 비디오 파일을 프레임 단위로 읽고 재생/일시정지/탐색/배속을 제어하는 프레임 소스."""

    def __init__(
        self,
        video_path: str,
        start_sec: float = 0.0,
        end_sec: Optional[float] = None
    ):
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"Failed to open video: {video_path}")

        self.native_fps = self.cap.get(cv2.CAP_PROP_FPS) or 60.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration_sec = self.total_frames / max(1.0, self.native_fps)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.start_sec = max(0.0, start_sec)
        self.end_sec = min(self.duration_sec, end_sec) if end_sec is not None else self.duration_sec

        self.playback_speed: float = 1.0
        self.is_paused: bool = False
        self._current_frame_idx: int = int(self.start_sec * self.native_fps)
        self._last_read_time: float = time.time()
        self._last_packet: Optional[FramePacket] = None

        self.seek(self.start_sec)

    def read(self) -> Optional[FramePacket]:
        """비디오의 다음 프레임을 읽어 FramePacket으로 반환."""
        if self._current_frame_idx > int(self.end_sec * self.native_fps):
            return None

        if self.is_paused and self._last_packet is not None:
            return self._last_packet

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self._current_frame_idx)
        ret, frame = self.cap.read()
        if not ret or frame is None:
            return None

        t_sec = self._current_frame_idx / self.native_fps
        packet = FramePacket(
            frame=frame,
            timestamp_sec=t_sec,
            frame_index=self._current_frame_idx,
            source_type="VIDEO",
            metadata={
                "video_path": self.video_path,
                "native_fps": self.native_fps,
                "total_frames": self.total_frames,
                "duration_sec": self.duration_sec,
                "playback_speed": self.playback_speed,
                "is_paused": self.is_paused
            }
        )

        self._last_packet = packet
        if not self.is_paused:
            self._current_frame_idx += 1

        self._last_read_time = time.time()
        return packet

    def seek(self, timestamp_sec: float) -> None:
        """지정된 초 위치로 탐색."""
        target_sec = max(self.start_sec, min(self.end_sec, timestamp_sec))
        target_idx = int(target_sec * self.native_fps)
        self._current_frame_idx = max(0, min(target_idx, self.total_frames - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self._current_frame_idx)
        ret, frame = self.cap.read()
        if ret and frame is not None:
            self._last_packet = FramePacket(
                frame=frame,
                timestamp_sec=self._current_frame_idx / self.native_fps,
                frame_index=self._current_frame_idx,
                source_type="VIDEO",
                metadata={"video_path": self.video_path, "is_paused": self.is_paused}
            )

    def current_timestamp(self) -> float:
        return self._current_frame_idx / self.native_fps

    def is_live(self) -> bool:
        return False

    def pause(self) -> None:
        self.is_paused = True

    def resume(self) -> None:
        self.is_paused = False

    def step_frame(self, delta: int = 1) -> Optional[FramePacket]:
        """프레임 단위 전진/후진 (자동 일시정지 상태 유지)."""
        self.is_paused = True
        new_idx = max(0, min(self._current_frame_idx + delta, self.total_frames - 1))
        self._current_frame_idx = new_idx
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self._current_frame_idx)
        ret, frame = self.cap.read()
        if ret and frame is not None:
            self._last_packet = FramePacket(
                frame=frame,
                timestamp_sec=self._current_frame_idx / self.native_fps,
                frame_index=self._current_frame_idx,
                source_type="VIDEO",
                metadata={"video_path": self.video_path, "is_paused": True}
            )
            return self._last_packet
        return None

    def set_speed(self, speed: float) -> None:
        """재생 속도 설정 (0.25x ~ 8.0x)."""
        self.playback_speed = max(0.1, min(16.0, speed))

    def close(self) -> None:
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
