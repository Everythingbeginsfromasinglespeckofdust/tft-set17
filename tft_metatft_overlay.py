"""MetaTFT-Style In-Game Transparent Overlay for TFT Set 18.
100% Real-time Vision & Decision Overlay floating directly over your screen:
- 100% Transparent See-Through Canvas (no black video frame)
- Top Center: Real-Time AI Decision Engine Recommendation Pill
- Bottom Center: 5-Slot Floating Shop Badges (Only shows when real TFT shop is visible)
- Bottom Left: Real-Time Gold & Interest HUD
- Left Sidebar: Live Engine Telemetry & Decision Reasons ([Tab] to toggle)
"""
from __future__ import annotations
import argparse
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional

import cv2
import mss
import numpy as np
import tkinter as tk

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

_TESS = r"C:\Program Files\Tesseract-OCR"
if os.path.exists(_TESS) and _TESS not in os.environ.get("PATH", ""):
    os.environ["PATH"] += f";{_TESS}"

from tft.vision.shop_recognizer_v2 import ShopRecognizerV2, SlotStatus
from tft.vision.gold_recognizer import GoldRecognizer
from tft.vision.adapters import ObservationToGameStateBuilder
from tft.vision.observation import Observation, CardObservation
from tft.calibration.integration.adapter import DecisionCalibrationAdapter
from tft.calibration.integration.models import CalibrationConfig, CalibrationMode


# Color Palette (MetaTFT Dark Glass Theme)
BG_TRANSPARENT = "#000001"  # Chroma key for 100% transparency
PANEL_BG = "#0d131d"
PANEL_BORDER = "#1f2b3e"
TEXT_WHITE = "#f1f5f9"
TEXT_MUTED = "#94a3b8"
TEXT_GOLD = "#f59e0b"
ACCENT_CYAN = "#06b6d4"
ACCENT_GREEN = "#10b981"
ACCENT_PURPLE = "#8b5cf6"
ACCENT_RED = "#ef4444"

COST_COLORS = {
    1: "#94a3b8",  # Grey
    2: "#10b981",  # Green
    3: "#0284c7",  # Blue
    4: "#a855f7",  # Purple
    5: "#eab308",  # Gold
}


class ScreenVisionWorker:
    """Continuously grabs active monitor screen and runs vision + decision engine."""

    def __init__(self, monitor_idx: int = 2):
        self.monitor_idx = monitor_idx
        self.running = False

        self.shop_recognizer = ShopRecognizerV2()
        self.gold_recognizer = GoldRecognizer()
        self.state_builder = ObservationToGameStateBuilder()
        self.adapter = DecisionCalibrationAdapter(config=CalibrationConfig(enabled=True, mode=CalibrationMode.ON))

        # Shared state for GUI
        self.gold: Optional[int] = None
        self.cards: List[Dict[str, Any]] = [
            {"slot": i, "name": None, "cost": None, "status": "NO_DETECTION"} for i in range(5)
        ]
        self.recommended_action: str = "WAITING"
        self.confidence: float = 0.0
        self.is_flip: bool = False
        self.reasons: List[str] = ["Waiting for TFT screen..."]
        self.scores: Dict[str, float] = {}
        self.fps: float = 0.0
        self.frame_count = 0

    def start(self):
        self.running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        t_start = time.time()
        fps_count = 0
        t_fps = time.time()

        with mss.mss() as sct:
            while self.running:
                t0 = time.time()
                m_idx = self.monitor_idx if self.monitor_idx < len(sct.monitors) else 1
                mon = sct.monitors[m_idx]

                try:
                    sct_img = sct.grab(mon)
                    raw_frame = np.array(sct_img)[:, :, :3]

                    # Standardize to 1280x720 for Set 18 recognizers
                    f_720 = cv2.resize(raw_frame, (1280, 720))
                    self.frame_count += 1
                    fps_count += 1

                    # 1. Shop Recognition
                    shop_cards = self.shop_recognizer.recognize_shop(f_720)
                    parsed_cards = []
                    card_obs_list = []
                    conf_list = []

                    for c in shop_cards:
                        if c.status == SlotStatus.RECOGNIZED and c.champion:
                            parsed_cards.append({"slot": c.slot_index, "name": c.champion, "cost": c.cost, "status": "REC", "conf": c.confidence})
                            card_obs_list.append(CardObservation(c.slot_index, c.champion, c.cost, c.confidence, False, "ShopRecognizerV2"))
                            conf_list.append(c.confidence)
                        elif c.status == SlotStatus.EMPTY:
                            parsed_cards.append({"slot": c.slot_index, "name": "EMPTY", "cost": 0, "status": "EMP", "conf": 1.0})
                            card_obs_list.append(CardObservation(c.slot_index, "EMPTY", None, 0.95, True, "ShopRecognizerV2"))
                            conf_list.append(0.95)
                        else:
                            parsed_cards.append({"slot": c.slot_index, "name": None, "cost": None, "status": "NO_DETECTION", "conf": 0.0})
                            card_obs_list.append(CardObservation(c.slot_index, None, None, 0.0, False, "ShopRecognizerV2"))
                            conf_list.append(0.0)

                    self.cards = parsed_cards

                    # 2. Gold Recognition
                    g_obs = self.gold_recognizer.recognize_gold(f_720, t0 - t_start, self.frame_count)
                    if g_obs.is_valid and g_obs.parsed_gold is not None:
                        self.gold = g_obs.parsed_gold
                    else:
                        self.gold = None

                    # Dynamic Confidences
                    shop_conf = float(np.mean(conf_list)) if conf_list else 0.0
                    gold_conf = float(g_obs.confidence) if g_obs.is_valid else 0.0
                    overall_conf = float(np.mean([shop_conf, gold_conf])) if (shop_conf > 0 or gold_conf > 0) else 0.0

                    # 3. Decision Engine + CALIB_C
                    if self.gold is not None or any(c["status"] == "REC" for c in parsed_cards):
                        obs = Observation(
                            timestamp_sec=t0 - t_start,
                            frame_index=self.frame_count,
                            stage_text="2-1",
                            gold_val=self.gold if self.gold is not None else 0,
                            hp_val=None,
                            level_val=None,
                            shop_cards=card_obs_list,
                            sources={"shop": "ShopRecognizerV2", "gold": "GoldRecognizer"},
                            confidences={"shop": round(shop_conf, 3), "gold": round(gold_conf, 3)},
                            overall_confidence=round(overall_conf, 3)
                        )
                        gs = self.state_builder.build(obs)
                        dec_res = self.adapter.decide(gs)

                        self.recommended_action = dec_res.action
                        self.is_flip = dec_res.is_flip
                        self.scores = dec_res.scores or {}
                        self.confidence = self.scores.get(dec_res.action, 0.0)
                        self.reasons = dec_res.reasons or ["Evaluated by DecisionEngine"]
                    else:
                        self.recommended_action = "SEARCHING"
                        self.reasons = ["Waiting for TFT Shop / Gold HUD on screen..."]
                        self.scores = {}

                except Exception:
                    pass

                now = time.time()
                if now - t_fps >= 1.0:
                    self.fps = fps_count / (now - t_fps)
                    fps_count = 0
                    t_fps = now

                elapsed = time.time() - t0
                time.sleep(max(0.01, 0.066 - elapsed))


class MetaTFTTransparentOverlay:
    """Full-Screen Transparent In-Game Overlay matching MetaTFT aesthetics."""

    def __init__(self, worker: ScreenVisionWorker):
        self.worker = worker

        self.root = tk.Tk()
        self.root.title("MetaTFT AI In-Game Overlay")

        # Set transparent fullscreen overlay
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", BG_TRANSPARENT)
        self.root.configure(bg=BG_TRANSPARENT)

        # Detect screen resolution
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"{self.screen_w}x{self.screen_h}+0+0")
        self.root.overrideredirect(True)  # Frameless window

        self.panel_visible = True
        self._build_hud_elements()

        # Global Hotkeys
        self.root.bind("<Escape>", lambda e: self.close())
        self.root.bind("<Tab>", lambda e: self.toggle_sidebar())
        self.root.bind("<m>", lambda e: self.toggle_monitor())
        self.root.bind("<M>", lambda e: self.toggle_monitor())

    def _build_hud_elements(self):
        # ── 1. Top Center: AI Decision Engine Pill ────────────────────────────
        self.top_pill = tk.Frame(self.root, bg=PANEL_BG, bd=1, relief="solid", highlightbackground=PANEL_BORDER, highlightthickness=1)
        self.top_pill.place(relx=0.5, y=25, anchor="n", width=460, height=54)

        pill_title = tk.Label(self.top_pill, text="⚡ TFT REAL-TIME DECISION ENGINE", bg=PANEL_BG, fg=TEXT_MUTED, font=("Segoe UI", 8, "bold"))
        pill_title.pack(anchor="w", padx=12, pady=(3, 0))

        self.action_lbl = tk.Label(self.top_pill, text="⚪ SCANNING SCREEN...", bg=PANEL_BG, fg=TEXT_WHITE, font=("Segoe UI", 12, "bold"))
        self.action_lbl.pack(side="left", padx=12)

        self.calib_badge = tk.Label(self.top_pill, text="[CALIB_C ON]", bg="#1e293b", fg=TEXT_GOLD, font=("Segoe UI", 8, "bold"), padx=6, pady=2)
        self.calib_badge.pack(side="right", padx=12)

        # ── 2. Left Sidebar: Live Telemetry & Insights ────────────────────────
        self.sidebar = tk.Frame(self.root, bg=PANEL_BG, bd=1, relief="solid", highlightbackground=PANEL_BORDER, highlightthickness=1)
        self.sidebar.place(x=20, y=100, width=280, height=380)

        sb_header = tk.Frame(self.sidebar, bg="#162030", height=32)
        sb_header.pack(fill="x")
        sb_title = tk.Label(sb_header, text="📊 ENGINE TELEMETRY", bg="#162030", fg=ACCENT_CYAN, font=("Segoe UI", 9, "bold"))
        sb_title.pack(side="left", padx=10, pady=6)

        self.fps_lbl = tk.Label(sb_header, text="M2 | 0.0 FPS", bg="#162030", fg=TEXT_MUTED, font=("Segoe UI", 8))
        self.fps_lbl.pack(side="right", padx=10)

        # Status block
        status_frame = tk.Frame(self.sidebar, bg=PANEL_BG)
        status_frame.pack(fill="x", padx=10, pady=8)

        tk.Label(status_frame, text="VISION STATUS:", bg=PANEL_BG, fg=TEXT_MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.vision_status_lbl = tk.Label(status_frame, text="Waiting for TFT HUD...", bg=PANEL_BG, fg=TEXT_GOLD, font=("Segoe UI", 9))
        self.vision_status_lbl.pack(anchor="w", pady=(2, 6))

        # Score Breakdown
        tk.Label(self.sidebar, text="ACTION SCORES:", bg=PANEL_BG, fg=TEXT_MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(4, 2))
        self.score_box = tk.Frame(self.sidebar, bg="#131c2a", bd=1, relief="ridge")
        self.score_box.pack(fill="x", padx=10, pady=2)

        self.score_save_lbl = tk.Label(self.score_box, text="SAVE_GOLD : --", bg="#131c2a", fg=ACCENT_GREEN, font=("Segoe UI", 9))
        self.score_save_lbl.pack(anchor="w", padx=8, pady=2)
        self.score_roll_lbl = tk.Label(self.score_box, text="ROLL      : --", bg="#131c2a", fg=ACCENT_PURPLE, font=("Segoe UI", 9))
        self.score_roll_lbl.pack(anchor="w", padx=8, pady=2)
        self.score_lvl_lbl = tk.Label(self.score_box, text="LEVEL_UP  : --", bg="#131c2a", fg=ACCENT_CYAN, font=("Segoe UI", 9))
        self.score_lvl_lbl.pack(anchor="w", padx=8, pady=2)

        # Rationale
        tk.Label(self.sidebar, text="DECISION RATIONALE:", bg=PANEL_BG, fg=TEXT_MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.reason_lbl = tk.Label(self.sidebar, text="Waiting for active frame...", bg=PANEL_BG, fg=TEXT_WHITE, font=("Segoe UI", 8), wraplength=250, justify="left")
        self.reason_lbl.pack(anchor="w", padx=10, pady=2)

        # Bottom shortcut hint
        hint = tk.Label(self.sidebar, text="[Tab] Hide/Show | [M] Monitor | [Esc] Exit", bg=PANEL_BG, fg="#475569", font=("Segoe UI", 8))
        hint.pack(side="bottom", pady=8)

        # ── 3. Bottom: Floating Shop 5-Slot Card Badges ────────────────────────
        self.shop_bar = tk.Frame(self.root, bg=PANEL_BG, bd=1, relief="solid", highlightbackground=PANEL_BORDER, highlightthickness=1)
        self.shop_bar.place(relx=0.5, rely=0.92, anchor="center", width=720, height=64)

        shop_header = tk.Frame(self.shop_bar, bg="#162030", height=18)
        shop_header.pack(fill="x", side="top")
        tk.Label(shop_header, text="🛒 RECOGNIZED SHOP SLOTS (REAL-TIME VISION)", bg="#162030", fg=TEXT_MUTED, font=("Segoe UI", 7, "bold")).pack(side="left", padx=8)

        self.shop_slots_frame = tk.Frame(self.shop_bar, bg=PANEL_BG)
        self.shop_slots_frame.pack(fill="both", expand=True, padx=4, pady=2)

        self.slot_widgets = []
        for i in range(5):
            slot_box = tk.Frame(self.shop_slots_frame, bg="#161f2e", bd=1, relief="ridge")
            slot_box.pack(side="left", fill="both", expand=True, padx=3, pady=2)

            name_lbl = tk.Label(slot_box, text="-", bg="#161f2e", fg=TEXT_MUTED, font=("Segoe UI", 9, "bold"))
            name_lbl.pack(pady=(2, 0))

            tag_lbl = tk.Label(slot_box, text="Searching...", bg="#161f2e", fg=TEXT_MUTED, font=("Segoe UI", 7))
            tag_lbl.pack(pady=(0, 2))

            self.slot_widgets.append((slot_box, name_lbl, tag_lbl))

        # ── 4. Bottom Left: Gold HUD Badge ─────────────────────────────────────
        self.gold_badge = tk.Frame(self.root, bg=PANEL_BG, bd=1, relief="solid", highlightbackground=PANEL_BORDER, highlightthickness=1)
        self.gold_badge.place(x=20, rely=0.92, anchor="w", width=180, height=64)

        self.gold_val_lbl = tk.Label(self.gold_badge, text="💰 Gold: -- G", bg=PANEL_BG, fg=TEXT_GOLD, font=("Segoe UI", 12, "bold"))
        self.gold_val_lbl.pack(anchor="w", padx=10, pady=(6, 0))

        self.interest_lbl = tk.Label(self.gold_badge, text="Searching Gold HUD...", bg=PANEL_BG, fg=TEXT_MUTED, font=("Segoe UI", 7))
        self.interest_lbl.pack(anchor="w", padx=10, pady=(0, 4))

    def toggle_sidebar(self):
        if self.panel_visible:
            self.sidebar.place_forget()
            self.panel_visible = False
        else:
            self.sidebar.place(x=20, y=100, width=280, height=380)
            self.panel_visible = True

    def toggle_monitor(self):
        self.worker.monitor_idx = 1 if self.worker.monitor_idx == 2 else 2
        self.fps_lbl.config(text=f"M{self.worker.monitor_idx} | {self.worker.fps:.1f} FPS")

    def update_overlay(self):
        # 1. Update Decision Pill
        act = self.worker.recommended_action
        flip = self.worker.is_flip

        if act == "SAVE_GOLD":
            act_text = "🟢 ACTION: SAVE GOLD (Hold for Interest)"
            act_color = ACCENT_GREEN
        elif act == "ROLL":
            act_text = "🟣 ACTION: ROLL (Upgrade Board & Hit Units)"
            act_color = ACCENT_PURPLE
        elif act == "LEVEL_UP":
            act_text = "🟡 ACTION: LEVEL UP (Push Tempo & Win Streak)"
            act_color = ACCENT_CYAN
        elif act == "SEARCHING":
            act_text = "⚪ SEARCHING TFT SCREEN..."
            act_color = TEXT_MUTED
        else:
            act_text = f"⚪ ACTION: {act}"
            act_color = TEXT_WHITE

        self.action_lbl.config(text=act_text, fg=act_color)
        self.calib_badge.config(
            text="⚡ CALIB_C FLIP" if flip else "🛡️ CALIB_C ON",
            fg="#fff" if flip else TEXT_GOLD,
            bg=ACCENT_RED if flip else "#1e293b"
        )

        # 2. Update Sidebar Telemetry
        recognized_count = sum(1 for c in self.worker.cards if c.get("status") == "REC")
        if self.worker.gold is not None or recognized_count > 0:
            self.vision_status_lbl.config(text=f"TFT Active (Shop: {recognized_count}/5)", fg=ACCENT_GREEN)
        else:
            self.vision_status_lbl.config(text="Searching for TFT HUD...", fg=TEXT_GOLD)

        scores = self.worker.scores
        if scores:
            self.score_save_lbl.config(text=f"SAVE_GOLD : {scores.get('SAVE_GOLD', 0.0):.3f}")
            self.score_roll_lbl.config(text=f"ROLL      : {scores.get('ROLL', 0.0):.3f}")
            self.score_lvl_lbl.config(text=f"LEVEL_UP  : {scores.get('LEVEL_UP', 0.0):.3f}")
        else:
            self.score_save_lbl.config(text="SAVE_GOLD : --")
            self.score_roll_lbl.config(text="ROLL      : --")
            self.score_lvl_lbl.config(text="LEVEL_UP  : --")

        if self.worker.reasons:
            self.reason_lbl.config(text=self.worker.reasons[0])

        # 3. Update Gold Badge & Interest
        g = self.worker.gold
        if g is not None:
            self.gold_val_lbl.config(text=f"💰 Gold: {g} G")
            interest = min(5, g // 10)
            next_g = (interest + 1) * 10 if interest < 5 else 50
            diff = next_g - g if interest < 5 else 0
            if diff > 0:
                self.interest_lbl.config(text=f"Interest: +{interest}G (Need {diff}G for +{interest+1}G)")
            else:
                self.interest_lbl.config(text=f"Interest: +{interest}G (Max Interest)")
        else:
            self.gold_val_lbl.config(text="💰 Gold: -- G")
            self.interest_lbl.config(text="Searching Gold HUD...")

        # 4. Update Shop Slot Badges (Only show champions if real shop recognized!)
        for idx, card in enumerate(self.worker.cards[:5]):
            if idx < len(self.slot_widgets):
                box, name_l, tag_l = self.slot_widgets[idx]
                name = card.get("name")
                cost = card.get("cost")
                status = card.get("status", "NO_DETECTION")

                if status == "EMP":
                    name_l.config(text="[EMPTY]", fg=TEXT_MUTED)
                    tag_l.config(text="Purchased", fg=TEXT_MUTED)
                    box.config(bg="#0b1017")
                elif status == "REC" and name:
                    cost_col = COST_COLORS.get(cost, TEXT_WHITE)
                    name_l.config(text=f"{name} ({cost}G)", fg=cost_col)
                    tag_l.config(text=f"Conf: {card.get('conf', 0.0):.2f}", fg=ACCENT_CYAN)
                    box.config(bg="#112238")
                else:
                    name_l.config(text="-", fg=TEXT_MUTED)
                    tag_l.config(text="No Shop", fg=TEXT_MUTED)
                    box.config(bg="#161f2e")

        # 5. Update FPS
        self.fps_lbl.config(text=f"M{self.worker.monitor_idx} | {self.worker.fps:.1f} FPS")

        # Re-schedule update
        self.root.after(100, self.update_overlay)

    def close(self):
        self.worker.running = False
        self.root.destroy()


def run_metatft_overlay(monitor_idx: int = 2):
    worker = ScreenVisionWorker(monitor_idx=monitor_idx)
    worker.start()

    overlay = MetaTFTTransparentOverlay(worker)
    overlay.update_overlay()
    overlay.root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MetaTFT In-Game Transparent Overlay")
    parser.add_argument("--monitor", type=int, default=2, help="Monitor index (1 or 2)")
    args = parser.parse_args()
    run_metatft_overlay(monitor_idx=args.monitor)
