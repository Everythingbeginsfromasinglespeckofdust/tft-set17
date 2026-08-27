"""Unit and Regression Tests for TFT Resolution / Window / Video Adaptive UI Geometry Layer v1."""
import os
import sys
import cv2
import numpy as np
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.vision.ui_geometry import (
    UIGeometryEngine,
    GameRegionDetector,
    ShopGeometryDetector,
    GoldGeometryDetector,
    StageGeometryDetector,
    BoardGeometryDetector,
    CoordinateTransform,
    CoordinateSpace,
    GeometryStatus,
    UIRegion,
    SlotGeometry,
    HexGeometry
)


def create_synthetic_game_frame(w: int = 1280, h: int = 720) -> np.ndarray:
    """Create a basic synthetic game frame with dark shop and board area."""
    frame = np.full((h, w, 3), 40, dtype=np.uint8)  # Dark background
    
    # Bottom Shop bar: dark bar (y: 78%~98%, x: 22%~78%) with card textures
    sy1, sy2 = int(h * 0.80), int(h * 0.98)
    sx1, sx2 = int(w * 0.24), int(w * 0.78)
    frame[sy1:sy2, sx1:sx2] = 30
    
    # 5 card slots with contrast
    card_w = (sx2 - sx1) // 5
    for i in range(5):
        cx1 = sx1 + i * card_w + 5
        cx2 = cx1 + card_w - 10
        frame[sy1+10:sy2-10, cx1:cx2] = 65
    
    # Gold HUD area (y: 90%~98%, x: 32%~42%) with gold yellow pixels
    gy1, gy2 = int(h * 0.92), int(h * 0.98)
    gx1, gx2 = int(w * 0.34), int(w * 0.40)
    frame[gy1:gy2, gx1:gx2] = [20, 215, 255]
    
    return frame


def test_coordinate_transform_deterministic():
    """1. Test forward and inverse coordinate transforms are deterministic."""
    region = UIRegion(x=100, y=50, width=200, height=100, coord_space=CoordinateSpace.FRAME)
    transform = CoordinateTransform(
        from_space=CoordinateSpace.FRAME,
        to_space=CoordinateSpace.CANONICAL,
        scale_x=2.0,
        scale_y=2.0,
        offset_x=20,
        offset_y=10
    )
    
    transformed = transform.transform_region(region)
    assert transformed.x == (100 - 20) * 2  # 160
    assert transformed.y == (50 - 10) * 2   # 80
    assert transformed.width == 400
    assert transformed.height == 200
    assert transformed.coord_space == CoordinateSpace.CANONICAL

    inverse = transform.inverse_region(transformed)
    assert inverse.x == 100
    assert inverse.y == 50
    assert inverse.width == 200
    assert inverse.height == 100


def test_game_region_detection():
    """2. Test game content bounding box detection on 16:9 canvas."""
    frame = create_synthetic_game_frame(1280, 720)
    box, conf, signals = GameRegionDetector.detect_game_region(frame)
    
    assert box is not None
    assert box.width == 1280
    assert box.height == 720
    assert conf >= 0.50
    assert "shop_structure" in signals
    assert signals["shop_structure"] > 0.0


def test_shop_geometry_detection():
    """3. Test adaptive shop region and slot detection."""
    frame = create_synthetic_game_frame(1280, 720)
    shop_box, slots, conf = ShopGeometryDetector.detect_shop_geometry(frame)
    
    assert shop_box is not None
    assert shop_box.width > 0
    assert shop_box.height > 0
    assert len(slots) == 5
    assert conf >= 0.90


def test_slot_geometry_detection():
    """4. Test individual slot geometry, width equality, and ordering."""
    frame = create_synthetic_game_frame(1280, 720)
    _, slots, _ = ShopGeometryDetector.detect_shop_geometry(frame)
    
    assert len(slots) == 5
    for i, s in enumerate(slots):
        assert s.slot_index == i
        assert s.width == slots[0].width
        assert s.height == slots[0].height
        if i > 0:
            assert s.x > slots[i-1].x


def test_gold_geometry_detection():
    """5. Test Gold HUD geometry detection."""
    frame = create_synthetic_game_frame(1280, 720)
    gold_box, conf = GoldGeometryDetector.detect_gold_geometry(frame)
    
    assert gold_box is not None
    assert gold_box.x >= 0
    assert gold_box.y >= int(720 * 0.85)
    assert conf >= 0.90


def test_stage_geometry_detection():
    """6. Test Stage HUD geometry detection."""
    frame = create_synthetic_game_frame(1280, 720)
    stage_box, conf = StageGeometryDetector.detect_stage_geometry(frame)
    
    assert stage_box is not None
    assert stage_box.y < 100
    assert conf >= 0.90


def test_board_geometry_detection():
    """7. Test 4x7 (28 hexes) Board geometry detection."""
    frame = create_synthetic_game_frame(1280, 720)
    board_box, hex_grid, conf = BoardGeometryDetector.detect_board_geometry(frame)
    
    assert board_box is not None
    assert len(hex_grid) == 28
    assert conf >= 0.90
    
    rows = set(h.row for h in hex_grid)
    cols = set(h.col for h in hex_grid)
    assert rows == {0, 1, 2, 3}
    assert cols == {0, 1, 2, 3, 4, 5, 6}


def test_empty_hex_detection():
    """8. Test empty hex detection vs occupied textured hex."""
    frame = create_synthetic_game_frame(1280, 720)
    
    # On smooth synthetic board, all hexes should be empty
    _, hex_grid_empty, _ = BoardGeometryDetector.detect_board_geometry(frame)
    assert all(h.is_empty for h in hex_grid_empty)
    
    # Inject high contrast unit texture at hex r1_c3
    target_hex = next(h for h in hex_grid_empty if h.location == "hex_r1_c3")
    cx, cy, r = target_hex.center_x, target_hex.center_y, target_hex.radius
    frame[cy-r:cy+r, cx-r:cx+r] = np.random.randint(0, 255, (2*r, 2*r, 3), dtype=np.uint8)
    
    _, hex_grid_occ, _ = BoardGeometryDetector.detect_board_geometry(frame)
    occ_hex = next(h for h in hex_grid_occ if h.location == "hex_r1_c3")
    assert occ_hex.is_empty is False


def test_unknown_geometry_propagation():
    """9. Test unknown / low-confidence geometry does not produce false valid detections."""
    engine = UIGeometryEngine()
    
    # Solid black frame
    black = np.zeros((720, 1280, 3), dtype=np.uint8)
    res_black = engine.detect_geometry(black)
    assert res_black.is_valid is False
    assert res_black.status == GeometryStatus.NO_GAME_DETECTED
    
    # Uniform grey noise
    noise = np.random.randint(80, 140, (720, 1280, 3), dtype=np.uint8)
    res_noise = engine.detect_geometry(noise)
    assert res_noise.is_valid is False
    assert res_noise.status == GeometryStatus.NO_GAME_DETECTED


def test_no_hardcoded_roi_fallback():
    """10. Test that fallback_used is strictly False and no silent fallback is injected."""
    engine = UIGeometryEngine()
    bad_frame = np.full((500, 500, 3), 128, dtype=np.uint8)
    res = engine.detect_geometry(bad_frame)
    
    assert res.fallback_used is False
    assert res.is_valid is False


def test_live_video_geometry_consistency():
    """11. Test that same frame produces identical geometry regardless of source_type label."""
    engine = UIGeometryEngine()
    frame = create_synthetic_game_frame(1280, 720)
    
    res_live = engine.detect_geometry(frame, source_type="REAL_LIVE")
    res_video = engine.detect_geometry(frame, source_type="VIDEO_REPLAY")
    
    assert res_live.is_valid == res_video.is_valid
    assert res_live.confidence == res_video.confidence
    assert res_live.game_region.to_dict() == res_video.game_region.to_dict()
    assert res_live.shop_region.to_dict() == res_video.shop_region.to_dict()
    assert len(res_live.shop_slots) == len(res_video.shop_slots)


def test_multi_resolution_transform():
    """12. Test 1080p, 1440p, and 4K frames transform to canonical 1280x720."""
    engine = UIGeometryEngine()
    
    for w, h in [(1920, 1080), (2560, 1440), (3840, 2160)]:
        f = create_synthetic_game_frame(w, h)
        res = engine.detect_geometry(f, source_type="DERIVED_PRESENTATION_TEST")
        assert res.is_valid is True
        assert res.canonical_frame is not None
        assert res.canonical_frame.shape == (720, 1280, 3)
        assert res.game_region.width == w
        assert res.game_region.height == h


def test_letterbox_handling():
    """13. Test letterboxed video in centered canvas is accurately cropped."""
    engine = UIGeometryEngine()
    game_720 = create_synthetic_game_frame(1280, 720)
    
    # Place in 1920x1080 canvas with (320, 180) letterbox
    canvas = np.zeros((1080, 1920, 3), dtype=np.uint8)
    canvas[180:900, 320:1600] = game_720
    
    res = engine.detect_geometry(canvas, source_type="DERIVED_PRESENTATION_TEST")
    assert res.is_valid is True
    assert res.game_region.x == 320
    assert res.game_region.y == 180
    assert res.game_region.width == 1280
    assert res.game_region.height == 720
    assert res.canonical_frame.shape == (720, 1280, 3)


def test_dpi_transform():
    """14. Test DPI scale transform (125% and 150% scaling)."""
    region = UIRegion(x=100, y=100, width=200, height=200, coord_space=CoordinateSpace.WINDOW)
    
    # 150% DPI scale
    transform_150 = CoordinateTransform(
        from_space=CoordinateSpace.WINDOW,
        to_space=CoordinateSpace.FRAME,
        scale_x=1.5,
        scale_y=1.5
    )
    scaled = transform_150.transform_region(region)
    assert scaled.x == 150
    assert scaled.y == 150
    assert scaled.width == 300
    assert scaled.height == 300


def test_geometry_hash_determinism():
    """15. Test that Geometry SHA256 hash is strictly deterministic."""
    engine = UIGeometryEngine()
    frame = create_synthetic_game_frame(1280, 720)
    
    res1 = engine.detect_geometry(frame)
    res2 = engine.detect_geometry(frame)
    
    assert res1.geometry_hash != ""
    assert res1.geometry_hash == res2.geometry_hash


def test_real_video_frame_probe():
    """16. Test real video frame extraction and geometry validation if recording exists."""
    vid_p = r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\56e6fb98-3716-4124-b4f1-8718629b533c-2026-08-26-23-20-20.mp4"
    if not os.path.exists(vid_p):
        pytest.skip("Test match recording not found")
        
    cap = cv2.VideoCapture(vid_p)
    cap.set(cv2.CAP_PROP_POS_MSEC, 300000.0)  # 300s
    ret, frame = cap.read()
    cap.release()
    
    assert ret is True and frame is not None
    engine = UIGeometryEngine()
    res = engine.detect_geometry(frame, source_type="VIDEO_REPLAY", timestamp_sec=300.0)
    
    assert res.is_valid is True
    assert res.status == GeometryStatus.VALID
    assert res.confidence >= 0.80
    assert len(res.shop_slots) == 5
    assert len(res.hex_grid) == 28
    assert res.game_region.width == 1280
    assert res.game_region.height == 720
