"""HUD Overlay Renderer: Real-time visual rendering of 4-layer state, ROI debug views, and verification controls."""
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from tft.vision.overlay_state import OverlayState, ShopSlotDisplay


class OverlayRenderer:
    """게임/비디오 프레임 위에 비전 인식 결과, ROI 박스, 신호 체크리스트, 검증 컨트롤을 렌더링하는 HUD 엔진."""

    # Color Palette (BGR format)
    COLOR_BG_DARK = (20, 20, 25)
    COLOR_PANEL_BG = (35, 35, 45)
    COLOR_TEXT_WHITE = (245, 245, 245)
    COLOR_TEXT_DIM = (160, 160, 170)
    COLOR_GREEN = (60, 200, 90)
    COLOR_RED = (60, 60, 230)
    COLOR_YELLOW = (40, 200, 240)
    COLOR_BLUE = (220, 140, 40)
    COLOR_PURPLE = (200, 80, 180)
    COLOR_GRAY = (100, 100, 110)

    # Standard 1280x720 ROI Coordinates
    ROI_COORDS = {
        "gold": (610, 680, 70, 36),       # (x, y, w, h)
        "stage": (580, 8, 120, 30),
        "shop_slot_1": (330, 580, 120, 130),
        "shop_slot_2": (455, 580, 120, 130),
        "shop_slot_3": (580, 580, 120, 130),
        "shop_slot_4": (705, 580, 120, 130),
        "shop_slot_5": (830, 580, 130, 130),
        "board": (280, 180, 720, 320),
        "bench": (240, 500, 800, 75)
    }

    def __init__(self, font_scale: float = 0.5):
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale = font_scale

    def render(self, frame: np.ndarray, state: OverlayState) -> np.ndarray:
        """프레임 위에 OverlayState의 모든 계층 정보를 합성하여 렌더링된 프레임 반환."""
        out = frame.copy()
        h, w = out.shape[:2]

        if state.mode == "PRODUCTION":
            return self._render_minimal_production(out, state)

        # 1. ROI Debug Bounding Boxes (if enabled)
        if state.show_rois:
            self._render_rois(out)

        # 2. Top Header HUD Banner
        self._render_header(out, state)

        # 3. Left Side Panel: Observed & Derived State
        self._render_state_panel(out, state)

        # 4. Right Side Panel: Action Detection & Signal Checklist
        self._render_action_panel(out, state)

        # 5. Shop Card Slot Badges
        self._render_shop_slots(out, state)

        # 6. Bottom Panel: Timeline & Human Verification Controls
        self._render_bottom_controls(out, state)

        return out

    def _render_header(self, img: np.ndarray, state: OverlayState) -> None:
        """상단 헤더 바 렌더링."""
        w = img.shape[1]
        cv2.rectangle(img, (0, 0), (w, 42), self.COLOR_BG_DARK, -1)
        cv2.line(img, (0, 42), (w, 42), self.COLOR_GRAY, 1)

        # Title
        cv2.putText(img, "TFT VISION VALIDATION OVERLAY v1", (15, 26), self.font, 0.6, self.COLOR_TEXT_WHITE, 2)

        # Mode Badge
        mode_text = f"[{state.mode}]"
        cv2.putText(img, mode_text, (410, 26), self.font, 0.5, self.COLOR_YELLOW, 1)

        # Source / Playback info
        if state.is_live:
            src_text = f"LIVE DESKTOP CAPTURE | Data Age: {state.performance.data_age_sec:.2f}s | Latency: {state.performance.latency_sec*1000:.0f}ms"
            cv2.putText(img, src_text, (530, 26), self.font, 0.45, self.COLOR_GREEN, 1)
        else:
            status = "PAUSED" if state.is_paused else f"PLAYING ({state.playback_speed:.2f}x)"
            src_text = f"TIME: {state.current_timestamp_sec:.2f}s / {state.duration_sec:.1f}s (Frame #{state.frame_index}) | {status}"
            cv2.putText(img, src_text, (530, 26), self.font, 0.45, self.COLOR_TEXT_WHITE, 1)

        # Verification Tally (Truth Monitor)
        tally_text = f"Verified: {state.verification.correct_count} Correct / {state.verification.wrong_count} Wrong"
        cv2.putText(img, tally_text, (w - 280, 26), self.font, 0.45, self.COLOR_YELLOW, 1)

    def _render_rois(self, img: np.ndarray) -> None:
        """디버그용 ROI 영역 박스 및 라벨 렌더링."""
        overlay = img.copy()
        for label, (x, y, rw, rh) in self.ROI_COORDS.items():
            cv2.rectangle(overlay, (x, y), (x + rw, y + rh), self.COLOR_BLUE, 1)
            cv2.putText(overlay, label.upper(), (x + 2, y + 12), self.font, 0.35, self.COLOR_YELLOW, 1)
        cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)

    def _render_state_panel(self, img: np.ndarray, state: OverlayState) -> None:
        """좌측 상태 패널 (Stage, HP, Gold, Level, Board/Bench)."""
        x, y, pw, ph = 15, 55, 230, 200
        self._draw_panel(img, x, y, pw, ph, "CURRENT OBSERVATION")

        obs = state.observed
        diff = state.derived

        lines = [
            f"Stage: {obs.stage_round} (Level {obs.level or '?'})",
            f"HP: {obs.hp or '?'} HP",
            f"Gold: {obs.gold if obs.gold is not None else '?'}G" + (f" (Δ {diff.gold_delta:+d}G)" if diff.gold_delta is not None and diff.gold_delta != 0 else ""),
            f"  └ Raw OCR: {obs.raw_gold or '?'}",
            f"  └ Carried: {obs.gold_carried}",
            f"Board: {obs.board_unit_count} units",
            f"Bench: {obs.bench_unit_count} units",
            f"Shop Delta: {diff.shop_slots_changed}/5 changed"
        ]

        for i, text in enumerate(lines):
            color = self.COLOR_YELLOW if "Gold:" in text and diff.gold_delta else self.COLOR_TEXT_WHITE
            cv2.putText(img, text, (x + 10, y + 25 + i * 20), self.font, 0.42, color, 1)

    def _render_action_panel(self, img: np.ndarray, state: OverlayState) -> None:
        """우측 액션 검출 및 인과 규칙 체크리스트 패널."""
        w = img.shape[1]
        x, y, pw, ph = w - 290, 55, 275, 200
        self._draw_panel(img, x, y, pw, ph, "DETECTED ACTION EVENT")

        det = state.detected
        act_name = det.action_type or "NO_ACTION"
        act_color = self.COLOR_GREEN if act_name in ["ROLL", "BUY_UNIT", "LEVEL_UP"] else self.COLOR_TEXT_DIM

        cv2.putText(img, f"Action: {act_name}", (x + 10, y + 28), self.font, 0.55, act_color, 2)
        cv2.putText(img, f"Detection Score: {det.detection_score:.2f} (Match: {det.rule_match_fraction})", (x + 10, y + 48), self.font, 0.40, self.COLOR_TEXT_DIM, 1)

        # Signal checklist
        cv2.line(img, (x + 5, y + 55), (x + pw - 5, y + 55), self.COLOR_GRAY, 1)
        cv2.putText(img, "Causal Evidence Checklist:", (x + 10, y + 70), self.font, 0.40, self.COLOR_YELLOW, 1)

        default_signals = det.signals_checklist or [
            ("Gold Delta Match", state.derived.gold_delta in [-2, -3, -4]),
            ("Shop Transition Match", state.derived.shop_slots_changed >= 2),
            ("Not System Refresh", True)
        ]

        for idx, (sig_text, is_met) in enumerate(default_signals[:5]):
            mark = "[v]" if is_met else "[ ]"
            m_color = self.COLOR_GREEN if is_met else self.COLOR_GRAY
            cv2.putText(img, f"{mark} {sig_text}", (x + 10, y + 90 + idx * 18), self.font, 0.40, m_color, 1)

    def _render_shop_slots(self, img: np.ndarray, state: OverlayState) -> None:
        """5개 상점 슬롯 카드 상태 오버레이 배지."""
        slots = state.observed.shop_slots or [
            ShopSlotDisplay(slot_index=i, status="UNKNOWN") for i in range(5)
        ]

        for s in slots:
            slot_key = f"shop_slot_{s.slot_index + 1}"
            if slot_key in self.ROI_COORDS:
                sx, sy, sw, sh = self.ROI_COORDS[slot_key]
                badge_h = 24
                badge_y = sy - badge_h - 2

                # Badge Color
                if s.status == "RECOGNIZED":
                    b_color = self.COLOR_GREEN
                elif s.status == "EMPTY":
                    b_color = self.COLOR_GRAY
                elif s.status == "LOW_CONFIDENCE":
                    b_color = self.COLOR_YELLOW
                else:
                    b_color = self.COLOR_PURPLE

                cv2.rectangle(img, (sx, badge_y), (sx + sw, badge_y + badge_h), self.COLOR_BG_DARK, -1)
                cv2.rectangle(img, (sx, badge_y), (sx + sw, badge_y + badge_h), b_color, 1)

                name_str = s.champion or (f"SLOT {s.slot_index + 1}" if not s.is_empty else "EMPTY")
                cost_str = f"{s.cost}G" if s.cost else ""
                disp_text = f"{name_str} {cost_str}".strip()
                cv2.putText(img, disp_text, (sx + 4, badge_y + 16), self.font, 0.38, self.COLOR_TEXT_WHITE, 1)

    def _render_bottom_controls(self, img: np.ndarray, state: OverlayState) -> None:
        """하단 타임라인 및 인간 검증 컨트롤 패널."""
        h, w = img.shape[:2]
        by = h - 90
        cv2.rectangle(img, (0, by), (w, h), self.COLOR_BG_DARK, -1)
        cv2.line(img, (0, by), (w, by), self.COLOR_GRAY, 1)

        # 1. Timeline Bar
        tl_y = by + 20
        cv2.line(img, (20, tl_y), (w - 20, tl_y), self.COLOR_GRAY, 2)

        # Scrubber playhead
        progress = state.current_timestamp_sec / max(1.0, state.duration_sec)
        scrubber_x = int(20 + progress * (w - 40))
        cv2.circle(img, (scrubber_x, tl_y), 6, self.COLOR_YELLOW, -1)

        # 2. Key Action Annotations / Controls
        ctrl_y = by + 50
        cv2.putText(img, "HUMAN CONTROLS:", (20, ctrl_y + 5), self.font, 0.42, self.COLOR_YELLOW, 1)

        buttons = [
            ("[C] CORRECT", self.COLOR_GREEN),
            ("[W] WRONG", self.COLOR_RED),
            ("[E] EDIT", self.COLOR_BLUE),
            ("[X] SKIP", self.COLOR_GRAY),
            ("[R] ROLL", self.COLOR_PURPLE),
            ("[B] BUY", self.COLOR_PURPLE),
            ("[L] LEVEL", self.COLOR_PURPLE),
            ("[Space] Play/Pause", self.COLOR_TEXT_WHITE),
            ("[<- / ->] Step", self.COLOR_TEXT_WHITE)
        ]

        bx = 160
        for b_text, b_col in buttons:
            cv2.putText(img, b_text, (bx, ctrl_y + 5), self.font, 0.40, b_col, 1)
            bx += 115

    def _render_minimal_production(self, img: np.ndarray, state: OverlayState) -> None:
        """Production 모드용 최소 경량 HUD."""
        w = img.shape[1]
        cv2.rectangle(img, (0, 0), (w, 32), self.COLOR_BG_DARK, -1)
        gold = state.observed.gold if state.observed.gold is not None else '?'
        act = state.detected.action_type or "STABLE"
        txt = f"TFT LIVE HUD | Stage: {state.observed.stage_round} | Gold: {gold}G | Action: {act} | Latency: {state.performance.latency_sec*1000:.0f}ms"
        cv2.putText(img, txt, (15, 21), self.font, 0.48, self.COLOR_TEXT_WHITE, 1)
        return img

    def _draw_panel(self, img: np.ndarray, x: int, y: int, w: int, h: int, title: str) -> None:
        """반투명 패널 배경 및 테두리 렌더링."""
        overlay = img.copy()
        cv2.rectangle(overlay, (x, y), (x + w, y + h), self.COLOR_PANEL_BG, -1)
        cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)
        cv2.rectangle(img, (x, y), (x + w, y + h), self.COLOR_GRAY, 1)
        # Title bar
        cv2.rectangle(img, (x, y), (x + w, y + 18), self.COLOR_BG_DARK, -1)
        cv2.putText(img, title, (x + 8, y + 13), self.font, 0.38, self.COLOR_YELLOW, 1)
