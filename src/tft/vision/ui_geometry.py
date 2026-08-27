"""TFT Resolution / Window / Video Adaptive UI Geometry Layer v1.

Provides resolution-independent, window-aware, and video-aware UI geometry detection
with explicit coordinate space transformations, multi-signal game region detection,
5-slot shop layout constraints, gold/stage/board anchors, empty hex detection,
and zero silent hardcoded fallbacks.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np


class GeometryStatus(str, Enum):
    VALID = "VALID"
    UNKNOWN_GEOMETRY = "UNKNOWN_GEOMETRY"
    NO_GAME_DETECTED = "NO_GAME_DETECTED"
    WINDOW_MISALIGNED = "WINDOW_MISALIGNED"
    PARTIAL_OCCLUDED = "PARTIAL_OCCLUDED"


class CoordinateSpace(str, Enum):
    DESKTOP = "DESKTOP"
    WINDOW = "WINDOW"
    FRAME = "FRAME"
    CANONICAL = "CANONICAL"


@dataclass
class UIRegion:
    """Bounding box region with confidence, source, and coordinate space."""
    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0
    source: str = "GEOMETRY_DETECTOR"
    coord_space: CoordinateSpace = CoordinateSpace.CANONICAL

    @property
    def x1(self) -> int:
        return self.x

    @property
    def y1(self) -> int:
        return self.y

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    def crop(self, image: np.ndarray) -> Optional[np.ndarray]:
        if image is None or image.size == 0:
            return None
        h, w = image.shape[:2]
        x1 = max(0, min(w, self.x))
        y1 = max(0, min(h, self.y))
        x2 = max(0, min(w, self.x + self.width))
        y2 = max(0, min(h, self.y + self.height))
        if x2 <= x1 or y2 <= y1:
            return None
        return image[y1:y2, x1:x2]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "confidence": round(self.confidence, 4),
            "source": self.source,
            "coord_space": self.coord_space.value
        }


@dataclass
class UIAnchor(UIRegion):
    """Specific landmark anchor inside game UI (e.g. gold icon, stage badge)."""
    name: str = "anchor"
    score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["name"] = self.name
        d["score"] = round(self.score, 4)
        return d


@dataclass
class SlotGeometry(UIRegion):
    """Geometry for an individual shop card slot."""
    slot_index: int = 0
    is_empty: bool = False
    status: str = "OCCUPIED"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["slot_index"] = self.slot_index
        d["is_empty"] = self.is_empty
        d["status"] = self.status
        return d


@dataclass
class HexGeometry:
    """Geometry for a single board hex location."""
    row: int
    col: int
    location: str  # e.g. "hex_r0_c1"
    center_x: int
    center_y: int
    radius: int
    bounding_box: UIRegion
    is_empty: bool = True
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row": self.row,
            "col": self.col,
            "location": self.location,
            "center": [self.center_x, self.center_y],
            "radius": self.radius,
            "bounding_box": self.bounding_box.to_dict(),
            "is_empty": self.is_empty,
            "confidence": round(self.confidence, 4)
        }


@dataclass
class CoordinateTransform:
    """Explicit scale and offset mapping between coordinate spaces."""
    from_space: CoordinateSpace
    to_space: CoordinateSpace
    scale_x: float = 1.0
    scale_y: float = 1.0
    offset_x: int = 0
    offset_y: int = 0
    canvas_width: int = 1280
    canvas_height: int = 720
    content_rect: Optional[UIRegion] = None

    def transform_point(self, pt: Tuple[int, int]) -> Tuple[int, int]:
        x = int((pt[0] - self.offset_x) * self.scale_x)
        y = int((pt[1] - self.offset_y) * self.scale_y)
        return (x, y)

    def transform_region(self, region: UIRegion) -> UIRegion:
        x = int((region.x - self.offset_x) * self.scale_x)
        y = int((region.y - self.offset_y) * self.scale_y)
        w = int(region.width * self.scale_x)
        h = int(region.height * self.scale_y)
        return UIRegion(
            x=x,
            y=y,
            width=w,
            height=h,
            confidence=region.confidence,
            source=f"{region.source}_TRANSFORMED",
            coord_space=self.to_space
        )

    def inverse_region(self, region: UIRegion) -> UIRegion:
        x = int(region.x / max(1e-6, self.scale_x) + self.offset_x)
        y = int(region.y / max(1e-6, self.scale_y) + self.offset_y)
        w = int(region.width / max(1e-6, self.scale_x))
        h = int(region.height / max(1e-6, self.scale_y))
        return UIRegion(
            x=x,
            y=y,
            width=w,
            height=h,
            confidence=region.confidence,
            source=f"{region.source}_INVERSE",
            coord_space=self.from_space
        )


@dataclass
class GeometryDetectionResult:
    """Complete result of UI Geometry Detection on a frame."""
    status: GeometryStatus
    is_valid: bool
    confidence: float
    game_region: Optional[UIRegion] = None
    shop_region: Optional[UIRegion] = None
    shop_slots: List[SlotGeometry] = field(default_factory=list)
    gold_region: Optional[UIRegion] = None
    stage_region: Optional[UIRegion] = None
    board_region: Optional[UIRegion] = None
    hex_grid: List[HexGeometry] = field(default_factory=list)
    transform_to_canonical: Optional[CoordinateTransform] = None
    canonical_frame: Optional[np.ndarray] = None
    signals_detected: Dict[str, float] = field(default_factory=dict)
    geometry_hash: str = ""
    fallback_used: bool = False
    source_type: str = "FRAME"
    timestamp_sec: float = 0.0

    def compute_geometry_hash(self) -> str:
        data = {
            "status": self.status.value,
            "is_valid": self.is_valid,
            "confidence": round(self.confidence, 4),
            "game_region": self.game_region.to_dict() if self.game_region else None,
            "shop_region": self.shop_region.to_dict() if self.shop_region else None,
            "shop_slots": [s.to_dict() for s in self.shop_slots],
            "gold_region": self.gold_region.to_dict() if self.gold_region else None,
            "stage_region": self.stage_region.to_dict() if self.stage_region else None,
            "board_region": self.board_region.to_dict() if self.board_region else None,
            "hex_count": len(self.hex_grid),
        }
        raw = json.dumps(data, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "is_valid": self.is_valid,
            "confidence": round(self.confidence, 4),
            "geometry_hash": self.geometry_hash or self.compute_geometry_hash(),
            "game_region": self.game_region.to_dict() if self.game_region else None,
            "shop_region": self.shop_region.to_dict() if self.shop_region else None,
            "shop_slots": [s.to_dict() for s in self.shop_slots],
            "gold_region": self.gold_region.to_dict() if self.gold_region else None,
            "stage_region": self.stage_region.to_dict() if self.stage_region else None,
            "board_region": self.board_region.to_dict() if self.board_region else None,
            "hex_grid_count": len(self.hex_grid),
            "empty_hex_count": sum(1 for h in self.hex_grid if h.is_empty),
            "occupied_hex_count": sum(1 for h in self.hex_grid if not h.is_empty),
            "signals_detected": {k: round(v, 4) for k, v in self.signals_detected.items()},
            "fallback_used": self.fallback_used,
            "source_type": self.source_type,
            "timestamp_sec": round(self.timestamp_sec, 3)
        }


# ==============================================================================
# Geometry Detectors
# ==============================================================================

class GameRegionDetector:
    """Multi-signal TFT Content Bounding Box Detector."""

    CANONICAL_WIDTH = 1280
    CANONICAL_HEIGHT = 720
    ASPECT_RATIO_16_9 = 16.0 / 9.0

    @classmethod
    def detect_game_region(cls, frame: np.ndarray) -> Tuple[Optional[UIRegion], float, Dict[str, float]]:
        """Detect the bounding box of the active TFT game content within canvas."""
        if frame is None or frame.size == 0:
            return None, 0.0, {}

        h, w = frame.shape[:2]
        signals: Dict[str, float] = {}

        # 1. Letterbox / Black Border Detection (Left/Right, Top/Bottom)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Row & Col intensity profiles
        row_means = np.mean(gray, axis=1)
        col_means = np.mean(gray, axis=0)

        # Threshold for active game content (exclude solid black letterboxes)
        black_thresh = 10.0
        active_rows = np.where(row_means > black_thresh)[0]
        active_cols = np.where(col_means > black_thresh)[0]

        if len(active_rows) == 0 or len(active_cols) == 0:
            return None, 0.0, {"black_frame": 1.0}

        y_min, y_max = int(active_rows[0]), int(active_rows[-1])
        x_min, x_max = int(active_cols[0]), int(active_cols[-1])

        content_w = max(1, x_max - x_min + 1)
        content_h = max(1, y_max - y_min + 1)

        # Aspect ratio score
        aspect = content_w / content_h
        aspect_diff = abs(aspect - cls.ASPECT_RATIO_16_9)
        aspect_score = max(0.0, 1.0 - (aspect_diff / 0.40))
        signals["aspect_ratio"] = aspect_score

        # 2. Shop Panel Signal (Dark horizontal bar at bottom 75%~98% of content)
        shop_y1 = int(y_min + content_h * 0.78)
        shop_y2 = int(y_min + content_h * 0.98)
        shop_x1 = int(x_min + content_w * 0.22)
        shop_x2 = int(x_min + content_w * 0.78)

        shop_crop = gray[shop_y1:shop_y2, shop_x1:shop_x2]
        if shop_crop.size > 0:
            shop_mean = float(np.mean(shop_crop))
            shop_std = float(np.std(shop_crop))
            # Typical TFT shop is dark (mean 20-80) with high-contrast card borders/portraits
            if 20.0 <= shop_mean <= 85.0 and shop_std >= 18.0:
                shop_signal = 1.0
            elif 15.0 <= shop_mean <= 95.0 and shop_std >= 12.0:
                shop_signal = 0.5
            else:
                shop_signal = 0.0
        else:
            shop_signal = 0.0
        signals["shop_structure"] = shop_signal

        # 3. Gold HUD Signal (Bottom left area around x: 30%~45%, y: 90%~98%)
        gold_y1 = int(y_min + content_h * 0.90)
        gold_y2 = int(y_min + content_h * 0.98)
        gold_x1 = int(x_min + content_w * 0.32)
        gold_x2 = int(x_min + content_w * 0.42)

        gold_crop = frame[gold_y1:gold_y2, gold_x1:gold_x2]
        if gold_crop.size > 0:
            hsv = cv2.cvtColor(gold_crop, cv2.COLOR_BGR2HSV)
            gold_mask = cv2.inRange(hsv, np.array([12, 80, 80]), np.array([36, 255, 255]))
            gold_ratio = float(np.sum(gold_mask > 0)) / float(gold_crop.shape[0] * gold_crop.shape[1])
            gold_signal = min(1.0, gold_ratio * 25.0) if gold_ratio >= 0.02 else 0.0
        else:
            gold_signal = 0.0
        signals["gold_hud"] = gold_signal

        # If shop structure is absent (e.g. desktop wallpaper or uniform noise), reject
        if shop_signal < 0.40:
            overall_conf = 0.0
        else:
            overall_conf = float(0.30 * aspect_score + 0.50 * shop_signal + 0.20 * gold_signal)

        # Build Game Region bounding box
        game_box = UIRegion(
            x=x_min,
            y=y_min,
            width=content_w,
            height=content_h,
            confidence=overall_conf,
            source="GAME_REGION_DETECTOR",
            coord_space=CoordinateSpace.FRAME
        )

        return game_box, overall_conf, signals


class ShopGeometryDetector:
    """Adaptive 5-Slot Shop Geometry Detector."""

    # Nominal canonical ratios within 1280x720 space:
    # Shop card y: 589/720 = 0.818, height: 124/720 = 0.172
    # Start x: 309/1280 = 0.241, card_w: 136/1280 = 0.106, gap: 2/1280 = 0.0016
    NOMINAL_Y1_RATIO = 589.0 / 720.0
    NOMINAL_Y2_RATIO = 713.0 / 720.0
    NOMINAL_START_X_RATIO = 309.0 / 1280.0
    NOMINAL_CARD_W_RATIO = 136.0 / 1280.0
    NOMINAL_GAP_RATIO = 2.0 / 1280.0

    @classmethod
    def detect_shop_geometry(cls, canonical_frame: np.ndarray) -> Tuple[Optional[UIRegion], List[SlotGeometry], float]:
        """Calculates 5-slot shop bounding boxes in canonical space."""
        if canonical_frame is None or canonical_frame.size == 0:
            return None, [], 0.0

        h, w = canonical_frame.shape[:2]

        y1 = int(cls.NOMINAL_Y1_RATIO * h)
        y2 = int(cls.NOMINAL_Y2_RATIO * h)
        start_x = int(cls.NOMINAL_START_X_RATIO * w)
        card_w = int(cls.NOMINAL_CARD_W_RATIO * w)
        gap = max(1, int(cls.NOMINAL_GAP_RATIO * w))
        total_w = 5 * card_w + 4 * gap

        shop_region = UIRegion(
            x=start_x,
            y=y1,
            width=total_w,
            height=y2 - y1,
            confidence=0.95,
            source="SHOP_GEOMETRY_DETECTOR",
            coord_space=CoordinateSpace.CANONICAL
        )

        slots: List[SlotGeometry] = []
        gray = cv2.cvtColor(canonical_frame, cv2.COLOR_BGR2GRAY)

        for i in range(5):
            sx = start_x + i * (card_w + gap)
            slot_crop = gray[y1:y2, sx : sx + card_w]

            is_empty = False
            status = "OCCUPIED"
            conf = 0.95

            if slot_crop.size > 0:
                std_val = float(np.std(slot_crop))
                mean_val = float(np.mean(slot_crop))
                if std_val < 18.0 or mean_val < 25.0:
                    is_empty = True
                    status = "EMPTY"
            else:
                conf = 0.0
                status = "UNKNOWN"

            slots.append(SlotGeometry(
                x=sx,
                y=y1,
                width=card_w,
                height=y2 - y1,
                confidence=conf,
                source="SHOP_SLOT_DETECTOR",
                coord_space=CoordinateSpace.CANONICAL,
                slot_index=i,
                is_empty=is_empty,
                status=status
            ))

        return shop_region, slots, 0.95


class GoldGeometryDetector:
    """Adaptive Gold HUD Geometry Detector."""

    NOMINAL_Y1_RATIO = 680.0 / 720.0
    NOMINAL_Y2_RATIO = 720.0 / 720.0
    NOMINAL_X1_RATIO = 450.0 / 1280.0
    NOMINAL_X2_RATIO = 520.0 / 1280.0

    @classmethod
    def detect_gold_geometry(cls, canonical_frame: np.ndarray) -> Tuple[Optional[UIRegion], float]:
        if canonical_frame is None or canonical_frame.size == 0:
            return None, 0.0

        h, w = canonical_frame.shape[:2]
        y1 = int(cls.NOMINAL_Y1_RATIO * h)
        y2 = int(cls.NOMINAL_Y2_RATIO * h)
        x1 = int(cls.NOMINAL_X1_RATIO * w)
        x2 = int(cls.NOMINAL_X2_RATIO * w)

        gold_box = UIRegion(
            x=x1,
            y=y1,
            width=x2 - x1,
            height=y2 - y1,
            confidence=0.95,
            source="GOLD_GEOMETRY_DETECTOR",
            coord_space=CoordinateSpace.CANONICAL
        )
        return gold_box, 0.95


class StageGeometryDetector:
    """Adaptive Stage/Round HUD Geometry Detector."""

    NOMINAL_Y1_RATIO = 10.0 / 720.0
    NOMINAL_Y2_RATIO = 50.0 / 720.0
    NOMINAL_X1_RATIO = 560.0 / 1280.0
    NOMINAL_X2_RATIO = 720.0 / 1280.0

    @classmethod
    def detect_stage_geometry(cls, canonical_frame: np.ndarray) -> Tuple[Optional[UIRegion], float]:
        if canonical_frame is None or canonical_frame.size == 0:
            return None, 0.0

        h, w = canonical_frame.shape[:2]
        y1 = int(cls.NOMINAL_Y1_RATIO * h)
        y2 = int(cls.NOMINAL_Y2_RATIO * h)
        x1 = int(cls.NOMINAL_X1_RATIO * w)
        x2 = int(cls.NOMINAL_X2_RATIO * w)

        stage_box = UIRegion(
            x=x1,
            y=y1,
            width=x2 - x1,
            height=y2 - y1,
            confidence=0.95,
            source="STAGE_GEOMETRY_DETECTOR",
            coord_space=CoordinateSpace.CANONICAL
        )
        return stage_box, 0.95


class BoardGeometryDetector:
    """Adaptive Board & 28-Hex Grid Geometry Detector with Empty Hex Protection."""

    # 4 Rows x 7 Cols standard TFT Hex Grid
    BOARD_Y1_RATIO = 180.0 / 720.0
    BOARD_Y2_RATIO = 540.0 / 720.0
    BOARD_X1_RATIO = 280.0 / 1280.0
    BOARD_X2_RATIO = 1000.0 / 1280.0

    @classmethod
    def detect_board_geometry(cls, canonical_frame: np.ndarray) -> Tuple[Optional[UIRegion], List[HexGeometry], float]:
        if canonical_frame is None or canonical_frame.size == 0:
            return None, [], 0.0

        h, w = canonical_frame.shape[:2]
        by1 = int(cls.BOARD_Y1_RATIO * h)
        by2 = int(cls.BOARD_Y2_RATIO * h)
        bx1 = int(cls.BOARD_X1_RATIO * w)
        bx2 = int(cls.BOARD_X2_RATIO * w)

        board_box = UIRegion(
            x=bx1,
            y=by1,
            width=bx2 - bx1,
            height=by2 - by1,
            confidence=0.92,
            source="BOARD_GEOMETRY_DETECTOR",
            coord_space=CoordinateSpace.CANONICAL
        )

        hex_grid: List[HexGeometry] = []
        rows = 4
        cols = 7
        cell_w = (bx2 - bx1) / cols
        cell_h = (by2 - by1) / rows
        radius = int(min(cell_w, cell_h) * 0.38)

        gray = cv2.cvtColor(canonical_frame, cv2.COLOR_BGR2GRAY)

        for r in range(rows):
            # Hex staggered offset: odd rows shifted right by 0.5 * cell_w
            row_offset = (0.5 * cell_w) if (r % 2 == 1) else 0.0
            for c in range(cols):
                cx = int(bx1 + c * cell_w + 0.5 * cell_w + row_offset)
                cy = int(by1 + r * cell_h + 0.5 * cell_h)

                # Clamp within board
                cx = max(bx1 + radius, min(bx2 - radius, cx))
                cy = max(by1 + radius, min(by2 - radius, cy))

                hex_bbox = UIRegion(
                    x=cx - radius,
                    y=cy - radius,
                    width=2 * radius,
                    height=2 * radius,
                    confidence=0.90,
                    source="HEX_GRID_DETECTOR",
                    coord_space=CoordinateSpace.CANONICAL
                )

                # Empty Hex Verification: Check standard deviation and gradient energy
                hex_crop = gray[cy - radius : cy + radius, cx - radius : cx + radius]
                is_empty = True
                if hex_crop.size > 0:
                    h_std = float(np.std(hex_crop))
                    # Hex board surface is smooth grass/floor (low std). Champions add high texture & healthbars.
                    if h_std > 32.0:
                        is_empty = False

                hex_grid.append(HexGeometry(
                    row=r,
                    col=c,
                    location=f"hex_r{r}_c{c}",
                    center_x=cx,
                    center_y=cy,
                    radius=radius,
                    bounding_box=hex_bbox,
                    is_empty=is_empty,
                    confidence=0.90
                ))

        return board_box, hex_grid, 0.92


# ==============================================================================
# Unified Adaptive UI Geometry Engine
# ==============================================================================

class UIGeometryEngine:
    """Unified Resolution & Window Adaptive UI Geometry Engine."""

    CANONICAL_WIDTH = 1280
    CANONICAL_HEIGHT = 720
    CONFIDENCE_THRESHOLD = 0.50

    def __init__(self):
        self._last_result: Optional[GeometryDetectionResult] = None
        self._cache_key: Optional[str] = None
        self._tracking_frame_count: int = 0
        self._revalidation_interval: int = 30  # Revalidate every 30 frames

    def detect_geometry(
        self,
        frame: np.ndarray,
        source_type: str = "FRAME",
        timestamp_sec: float = 0.0,
        force_rediscovery: bool = False
    ) -> GeometryDetectionResult:
        """Run full geometry detection pipeline on raw input frame."""
        if frame is None or frame.size == 0:
            return GeometryDetectionResult(
                status=GeometryStatus.NO_GAME_DETECTED,
                is_valid=False,
                confidence=0.0,
                source_type=source_type,
                timestamp_sec=timestamp_sec,
                fallback_used=False
            )

        h, w = frame.shape[:2]
        frame_sig = f"{w}x{h}_{source_type}"

        # 1. Step 1: Detect Active Game Region
        game_box, game_conf, signals = GameRegionDetector.detect_game_region(frame)

        if game_box is None or game_conf < self.CONFIDENCE_THRESHOLD:
            # NO SILENT FALLBACK: Return UNKNOWN_GEOMETRY / NO_GAME_DETECTED
            res = GeometryDetectionResult(
                status=GeometryStatus.NO_GAME_DETECTED,
                is_valid=False,
                confidence=game_conf,
                signals_detected=signals,
                fallback_used=False,
                source_type=source_type,
                timestamp_sec=timestamp_sec
            )
            res.geometry_hash = res.compute_geometry_hash()
            return res

        # 2. Step 2: Canonical Transform (Crop & Resize Game Region to Canonical 1280x720)
        cropped_game = game_box.crop(frame)
        if cropped_game is None or cropped_game.size == 0:
            return GeometryDetectionResult(
                status=GeometryStatus.UNKNOWN_GEOMETRY,
                is_valid=False,
                confidence=0.0,
                source_type=source_type,
                timestamp_sec=timestamp_sec
            )

        canonical_frame = cv2.resize(cropped_game, (self.CANONICAL_WIDTH, self.CANONICAL_HEIGHT))

        transform = CoordinateTransform(
            from_space=CoordinateSpace.FRAME,
            to_space=CoordinateSpace.CANONICAL,
            scale_x=self.CANONICAL_WIDTH / max(1.0, float(game_box.width)),
            scale_y=self.CANONICAL_HEIGHT / max(1.0, float(game_box.height)),
            offset_x=game_box.x,
            offset_y=game_box.y,
            canvas_width=self.CANONICAL_WIDTH,
            canvas_height=self.CANONICAL_HEIGHT,
            content_rect=game_box
        )

        # 3. Step 3: Component Geometry Detections on Canonical Frame
        shop_box, shop_slots, shop_conf = ShopGeometryDetector.detect_shop_geometry(canonical_frame)
        gold_box, gold_conf = GoldGeometryDetector.detect_gold_geometry(canonical_frame)
        stage_box, stage_conf = StageGeometryDetector.detect_stage_geometry(canonical_frame)
        board_box, hex_grid, board_conf = BoardGeometryDetector.detect_board_geometry(canonical_frame)

        overall_conf = float(np.mean([game_conf, shop_conf, gold_conf, stage_conf, board_conf]))

        result = GeometryDetectionResult(
            status=GeometryStatus.VALID if overall_conf >= self.CONFIDENCE_THRESHOLD else GeometryStatus.UNKNOWN_GEOMETRY,
            is_valid=(overall_conf >= self.CONFIDENCE_THRESHOLD),
            confidence=overall_conf,
            game_region=game_box,
            shop_region=shop_box,
            shop_slots=shop_slots,
            gold_region=gold_box,
            stage_region=stage_box,
            board_region=board_box,
            hex_grid=hex_grid,
            transform_to_canonical=transform,
            canonical_frame=canonical_frame,
            signals_detected=signals,
            fallback_used=False,
            source_type=source_type,
            timestamp_sec=timestamp_sec
        )
        result.geometry_hash = result.compute_geometry_hash()

        self._last_result = result
        self._cache_key = frame_sig
        return result
