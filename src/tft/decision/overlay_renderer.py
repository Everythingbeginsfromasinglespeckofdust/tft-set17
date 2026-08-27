"""HUD Overlay Renderer for TFT Decision Engine Live Validation."""
from typing import Optional, Tuple
import cv2
import numpy as np

from tft.decision.overlay_state import DecisionOverlayState


class DecisionOverlayRenderer:
    """OpenCV 기반 TFT Decision Engine 실시간 HUD 및 검증 오버레이 렌더러."""

    # Colors (BGR)
    COLOR_BG_DARK = (18, 22, 28)
    COLOR_PANEL_BG = (28, 34, 44)
    COLOR_BORDER = (55, 65, 81)
    COLOR_WHITE = (245, 245, 245)
    COLOR_GRAY = (156, 163, 175)
    COLOR_GOLD = (34, 197, 94)      # #22c55e (Green/Gold theme)
    COLOR_CYAN = (235, 206, 135)
    COLOR_ACCENT = (14, 165, 233)   # Sky blue
    COLOR_WARN = (38, 162, 245)     # Amber
    COLOR_ERR = (68, 68, 239)       # Red
    COLOR_SUCCESS = (34, 197, 94)   # Green
    COLOR_PURPLE = (192, 132, 252)

    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height

    def render(self, base_frame: np.ndarray, state: DecisionOverlayState) -> np.ndarray:
        """기본 비디오/캡처 프레임 위에 Decision Engine HUD 오버레이 합성."""
        canvas = base_frame.copy()
        if canvas.shape[1] != self.width or canvas.shape[0] != self.height:
            canvas = cv2.resize(canvas, (self.width, self.height))

        if state.mode == "PRODUCTION":
            return self._render_production_hud(canvas, state)

        # 1. Top Status Banner
        self._render_top_banner(canvas, state)

        # 2. Right Decision HUD Panel
        self._render_right_decision_panel(canvas, state)

        # 3. Bottom Timeline & Review Control Bar
        self._render_bottom_control_bar(canvas, state)

        return canvas

    def _render_top_banner(self, canvas: np.ndarray, state: DecisionOverlayState) -> None:
        """상단 헤더 바 (모드, 세션, 타임스탬프, 재생 상태, 레이턴시/FPS)."""
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (self.width, 36), self.COLOR_BG_DARK, -1)
        cv2.addWeighted(overlay, 0.88, canvas, 0.12, 0, canvas)
        cv2.line(canvas, (0, 36), (self.width, 36), self.COLOR_BORDER, 1)

        # Title
        cv2.putText(canvas, "TFT DECISION VALIDATION v1.0", (12, 24), cv2.FONT_HERSHEY_DUPLEX, 0.55, self.COLOR_ACCENT, 1, cv2.LINE_AA)

        # Session & Time
        paused_str = " [PAUSED]" if state.is_paused else " [PLAYING]"
        info_txt = f"Session: {state.session_id} | T={state.timestamp_sec:.2f}s (Frame #{state.frame_index}) | Speed: {state.playback_speed}x{paused_str}"
        cv2.putText(canvas, info_txt, (310, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_WHITE, 1, cv2.LINE_AA)

        # Performance (Latency & FPS)
        perf = state.performance
        lat_txt = f"Vision: {perf.vision_latency_ms:.1f}ms | Engine: {perf.decision_latency_ms:.1f}ms | Tot: {perf.total_overlay_latency_ms:.1f}ms | {perf.analysis_fps:.0f} FPS"
        cv2.putText(canvas, lat_txt, (self.width - 430, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.42, self.COLOR_CYAN, 1, cv2.LINE_AA)

    def _render_right_decision_panel(self, canvas: np.ndarray, state: DecisionOverlayState) -> None:
        """우측 의사결정 상세 패널 (현재 상태, 플레이어 vs 엔진, 점수 분해, 이유, 미래 관측)."""
        panel_w = 400
        panel_x = self.width - panel_w
        panel_y = 42
        panel_h = self.height - panel_y - 70

        overlay = canvas.copy()
        cv2.rectangle(overlay, (panel_x, panel_y), (self.width - 8, panel_y + panel_h), self.COLOR_PANEL_BG, -1)
        cv2.addWeighted(overlay, 0.90, canvas, 0.10, 0, canvas)
        cv2.rectangle(canvas, (panel_x, panel_y), (self.width - 8, panel_y + panel_h), self.COLOR_BORDER, 1)

        y = panel_y + 22

        # 1. CURRENT OBSERVED STATE (T0)
        cv2.putText(canvas, "CURRENT GAME STATE (T0)", (panel_x + 12, y), cv2.FONT_HERSHEY_DUPLEX, 0.48, self.COLOR_CYAN, 1, cv2.LINE_AA)
        y += 20

        st = state.observed_state
        if st:
            st_txt1 = f"Stage: {st.stage_round}  |  HP: {st.player.hp}  |  Gold: {st.player.gold}G  |  Lvl: {st.player.level} ({st.player.xp}XP)"
            cv2.putText(canvas, st_txt1, (panel_x + 12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, self.COLOR_WHITE, 1, cv2.LINE_AA)
            y += 18
            shop_str = ", ".join([u.champion for u in st.shop_units[:5]]) if st.shop_units else "EMPTY"
            cv2.putText(canvas, f"Shop: {shop_str[:38]}", (panel_x + 12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.40, self.COLOR_GRAY, 1, cv2.LINE_AA)
            y += 18
            board_str = f"Board: {len(st.board_units)} units  |  Bench: {len(st.bench_units)} units"
            cv2.putText(canvas, board_str, (panel_x + 12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.40, self.COLOR_GRAY, 1, cv2.LINE_AA)
            y += 24
        else:
            cv2.putText(canvas, "No game state observed", (panel_x + 12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, self.COLOR_GRAY, 1, cv2.LINE_AA)
            y += 30

        cv2.line(canvas, (panel_x + 10, y - 8), (self.width - 18, y - 8), self.COLOR_BORDER, 1)

        # 2. ACTUAL PLAYER ACTION vs ENGINE RECOMMENDATION
        cv2.putText(canvas, "ACTION COMPARISON", (panel_x + 12, y), cv2.FONT_HERSHEY_DUPLEX, 0.48, self.COLOR_CYAN, 1, cv2.LINE_AA)
        y += 22

        p_act = state.actual_player_action or "NONE"
        cv2.putText(canvas, f"PLAYER ACTION : {p_act}", (panel_x + 12, y), cv2.FONT_HERSHEY_DUPLEX, 0.45, self.COLOR_WARN, 1, cv2.LINE_AA)
        y += 20

        if state.blind_mode and not state.reveal_recommendation:
            cv2.putText(canvas, "ENGINE RECOMMEND: [HIDDEN (BLIND MODE)]", (panel_x + 12, y), cv2.FONT_HERSHEY_DUPLEX, 0.45, self.COLOR_PURPLE, 1, cv2.LINE_AA)
        else:
            e_act = state.recommended_action
            is_match = (p_act == e_act)
            match_str = " (AGREES)" if is_match else " (DIFFERS)"
            col = self.COLOR_SUCCESS if is_match else self.COLOR_ERR
            cv2.putText(canvas, f"ENGINE RECOMMEND: {e_act}{match_str}", (panel_x + 12, y), cv2.FONT_HERSHEY_DUPLEX, 0.45, col, 1, cv2.LINE_AA)
        y += 24

        cv2.line(canvas, (panel_x + 10, y - 8), (self.width - 18, y - 8), self.COLOR_BORDER, 1)

        # 3. ACTION SCORES & GAP
        cv2.putText(canvas, "ACTION SCORES & GAP", (panel_x + 12, y), cv2.FONT_HERSHEY_DUPLEX, 0.48, self.COLOR_CYAN, 1, cv2.LINE_AA)
        y += 20

        if not (state.blind_mode and not state.reveal_recommendation):
            for act_name, sc in sorted(state.action_scores.items(), key=lambda x: x[1], reverse=True):
                is_best = (act_name == state.recommended_action)
                bar_w = int(sc * 140)
                bar_col = self.COLOR_ACCENT if is_best else self.COLOR_GRAY
                cv2.putText(canvas, f"{act_name:10s} : {sc:.4f}", (panel_x + 12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, self.COLOR_WHITE, 1, cv2.LINE_AA)
                cv2.rectangle(canvas, (panel_x + 180, y - 10), (panel_x + 180 + bar_w, y), bar_col, -1)
                y += 18

            cv2.putText(canvas, f"Action Score Gap: {state.action_score_gap:.4f} (Separation)", (panel_x + 12, y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, self.COLOR_GOLD, 1, cv2.LINE_AA)
            y += 24
        else:
            cv2.putText(canvas, "Scores hidden during blind evaluation", (panel_x + 12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.40, self.COLOR_GRAY, 1, cv2.LINE_AA)
            y += 30

        cv2.line(canvas, (panel_x + 10, y - 8), (self.width - 18, y - 8), self.COLOR_BORDER, 1)

        # 4. EXPLANATION / EVIDENCE
        cv2.putText(canvas, f"WHY {state.recommended_action}?", (panel_x + 12, y), cv2.FONT_HERSHEY_DUPLEX, 0.48, self.COLOR_CYAN, 1, cv2.LINE_AA)
        y += 20

        if not (state.blind_mode and not state.reveal_recommendation):
            if state.reasons:
                for r in state.reasons[:3]:
                    cv2.putText(canvas, f"- {r[:45]}", (panel_x + 12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.COLOR_WHITE, 1, cv2.LINE_AA)
                    y += 16
            else:
                cv2.putText(canvas, "- Highest expected utility across simulated horizon", (panel_x + 12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.COLOR_WHITE, 1, cv2.LINE_AA)
                y += 16
        else:
            cv2.putText(canvas, "- Reasons hidden in blind mode", (panel_x + 12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.COLOR_GRAY, 1, cv2.LINE_AA)
            y += 16

        # 5. FUTURE OUTCOME (T1+)
        if state.future_outcome:
            y += 8
            cv2.line(canvas, (panel_x + 10, y - 8), (self.width - 18, y - 8), self.COLOR_BORDER, 1)
            cv2.putText(canvas, "FUTURE OUTCOME (T1+ strictly observed)", (panel_x + 12, y), cv2.FONT_HERSHEY_DUPLEX, 0.44, self.COLOR_WARN, 1, cv2.LINE_AA)
            y += 18
            fo = state.future_outcome
            fo_txt = f"HP delta: {fo.get('hp_delta', 0):+d} | Gold delta: {fo.get('gold_delta', 0):+d} | Place: #{fo.get('final_placement', '?')}"
            cv2.putText(canvas, fo_txt, (panel_x + 12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.40, self.COLOR_WHITE, 1, cv2.LINE_AA)

    def _render_bottom_control_bar(self, canvas: np.ndarray, state: DecisionOverlayState) -> None:
        """하단 타임라인 및 인간 판단 인터랙티브 컨트롤 바."""
        bar_h = 58
        bar_y = self.height - bar_h

        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, bar_y), (self.width, self.height), self.COLOR_BG_DARK, -1)
        cv2.addWeighted(overlay, 0.92, canvas, 0.08, 0, canvas)
        cv2.line(canvas, (0, bar_y), (self.width, bar_y), self.COLOR_BORDER, 1)

        # Human Review / Blind Mode Controls
        y_ctrl = bar_y + 24
        cv2.putText(canvas, "HUMAN REVIEW:", (14, y_ctrl), cv2.FONT_HERSHEY_DUPLEX, 0.46, self.COLOR_CYAN, 1, cv2.LINE_AA)

        btns = [
            ("[1] REASONABLE", self.COLOR_SUCCESS),
            ("[2] QUESTIONABLE", self.COLOR_WARN),
            ("[3] WRONG", self.COLOR_ERR),
            ("[4] UNKNOWN", self.COLOR_GRAY),
            ("[B] BLIND TOGGLE", self.COLOR_PURPLE),
            ("[R] PREF ROLL", self.COLOR_WHITE),
            ("[L] PREF LVL", self.COLOR_WHITE),
            ("[S] PREF SAVE", self.COLOR_WHITE)
        ]

        x_off = 160
        for btn_txt, btn_col in btns:
            cv2.putText(canvas, btn_txt, (x_off, y_ctrl), cv2.FONT_HERSHEY_SIMPLEX, 0.42, btn_col, 1, cv2.LINE_AA)
            x_off += 135

        # Sub-status note
        judg_str = state.human_judgment.value if state.human_judgment else "None"
        pref_str = state.human_preference.value if state.human_preference else "None"
        blind_str = "ENABLED" if state.blind_mode else "DISABLED"
        sub_txt = f"Judgment: {judg_str}  |  Human Preference: {pref_str}  |  Blind Mode: {blind_str}  |  Space: Play/Pause  |  Left/Right: Step  |  +/-: Speed"
        cv2.putText(canvas, sub_txt, (14, bar_y + 46), cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.COLOR_GRAY, 1, cv2.LINE_AA)

    def _render_production_hud(self, canvas: np.ndarray, state: DecisionOverlayState) -> np.ndarray:
        """라이브 프로덕션 경량 헤더 HUD."""
        cv2.rectangle(canvas, (0, 0), (self.width, 32), self.COLOR_BG_DARK, -1)
        cv2.putText(canvas, f"RECOMMEND: {state.recommended_action}", (12, 22), cv2.FONT_HERSHEY_DUPLEX, 0.55, self.COLOR_GOLD, 1, cv2.LINE_AA)
        cv2.putText(canvas, f"Gap: {state.action_score_gap:.4f}", (240, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_WHITE, 1, cv2.LINE_AA)
        if state.reasons:
            cv2.putText(canvas, f"Reason: {state.reasons[0][:50]}", (400, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, self.COLOR_GRAY, 1, cv2.LINE_AA)
        perf = state.performance
        cv2.putText(canvas, f"Latency: {perf.total_overlay_latency_ms:.1f}ms | {perf.analysis_fps:.0f}FPS", (self.width - 240, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, self.COLOR_CYAN, 1, cv2.LINE_AA)
        return canvas
