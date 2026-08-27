"""Unified FrameSource Interface and FramePacket Protocol for TFT Vision System."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class FramePacket:
    """단일 비디오 프레임 또는 실시간 캡처 프레임의 불변 데이터 패킷."""
    frame: np.ndarray
    timestamp_sec: float
    frame_index: int
    source_type: str = "VIDEO"  # "VIDEO", "LIVE", "MOCK"
    capture_timestamp_sec: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class FrameSource(ABC):
    """비디오 파일 재생 및 실시간 데스크톱 캡처를 모두 지원하는 공통 프레임 공급자 인터페이스."""

    @abstractmethod
    def read(self) -> Optional[FramePacket]:
        """다음 프레임을 순차적으로 읽어 반환. 끝에 도달하면 None 반환."""
        pass

    @abstractmethod
    def seek(self, timestamp_sec: float) -> None:
        """지정된 시간(초) 위치로 탐색 (실시간 모드에서는 No-op)."""
        pass

    @abstractmethod
    def current_timestamp(self) -> float:
        """현재 프레임의 타임스탬프(초) 반환."""
        pass

    @abstractmethod
    def is_live(self) -> bool:
        """실시간 캡처 소스 여부 반환."""
        pass

    @abstractmethod
    def pause(self) -> None:
        """재생 일시 정지."""
        pass

    @abstractmethod
    def resume(self) -> None:
        """재생 재개."""
        pass

    @abstractmethod
    def step_frame(self, delta: int = 1) -> Optional[FramePacket]:
        """단일 프레임 단위 전진(+1) 또는 후진(-1)."""
        pass

    @abstractmethod
    def set_speed(self, speed: float) -> None:
        """재생 속도 설정 (0.25x ~ 8.0x)."""
        pass

    @abstractmethod
    def close(self) -> None:
        """리소스 해제."""
        pass


class MockFrameSource(FrameSource):
    """테스트 및 결정론적 회귀 검증을 위한 모의 프레임 소스."""

    def __init__(
        self,
        frames: Optional[List[np.ndarray]] = None,
        fps: float = 20.0,
        width: int = 1280,
        height: int = 720,
        total_frames: int = 30
    ):
        self.fps = fps
        self.dt = 1.0 / fps
        self.width = width
        self.height = height
        self.paused = False
        self.playback_speed = 1.0
        self.current_idx = 0

        if frames is not None:
            self.frames = frames
        else:
            self.frames = [
                np.zeros((height, width, 3), dtype=np.uint8)
                for _ in range(total_frames)
            ]

    def read(self) -> Optional[FramePacket]:
        if self.current_idx >= len(self.frames):
            return None
        frame = self.frames[self.current_idx]
        t = self.current_idx * self.dt
        packet = FramePacket(
            frame=frame,
            timestamp_sec=t,
            frame_index=self.current_idx,
            source_type="MOCK"
        )
        if not self.paused:
            self.current_idx += 1
        return packet

    def seek(self, timestamp_sec: float) -> None:
        idx = int(timestamp_sec * self.fps)
        self.current_idx = max(0, min(idx, len(self.frames) - 1))

    def current_timestamp(self) -> float:
        return self.current_idx * self.dt

    def is_live(self) -> bool:
        return False

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def step_frame(self, delta: int = 1) -> Optional[FramePacket]:
        new_idx = self.current_idx + delta
        if 0 <= new_idx < len(self.frames):
            self.current_idx = new_idx
            return FramePacket(
                frame=self.frames[self.current_idx],
                timestamp_sec=self.current_idx * self.dt,
                frame_index=self.current_idx,
                source_type="MOCK"
            )
        return None

    def set_speed(self, speed: float) -> None:
        self.playback_speed = max(0.1, speed)

    def close(self) -> None:
        pass
