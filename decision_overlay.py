#!/usr/bin/env python3
"""TFT Decision Validation Overlay CLI Application (Video Replay & Live Capture)."""
import argparse
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import cv2
from tft.vision.video_frame_source import VideoFileFrameSource
from tft.vision.live_capture_source import DesktopCaptureFrameSource
from tft.decision.analysis_manager import DecisionAnalysisManager
from tft.decision.validation_models import HumanEngineJudgment, HumanPreference


def parse_args():
    parser = argparse.ArgumentParser(description="TFT Decision Validation Overlay v1.0")
    parser.add_argument("--mode", choices=["validation", "production"], default="validation", help="Overlay mode")
    parser.add_argument("--source", choices=["video", "live"], default="video", help="Input source")
    parser.add_argument("--video", type=str, default="output/video_analysis/overlay_verification_eda87ad9_300s_360s.mp4", help="Path to video file")
    parser.add_argument("--session", type=str, default="SESSION_A", help="Session ID")
    parser.add_argument("--blind", action="store_true", help="Enable Blind Decision Review mode")
    parser.add_argument("--no-gui", action="store_true", help="Run in headless smoke test mode")
    parser.add_argument("--max-frames", type=int, default=100, help="Max frames for headless run")
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 80)
    print("🚀 TFT DECISION VALIDATION OVERLAY v1.0")
    print("=" * 80)
    print(f"  • Mode        : {args.mode.upper()}")
    print(f"  • Source      : {args.source.upper()}")
    print(f"  • Session     : {args.session}")
    print(f"  • Blind Mode  : {'ENABLED' if args.blind else 'DISABLED'}")
    print("=" * 80)

    # Frame Source initialization
    if args.source == "video":
        if not os.path.exists(args.video):
            print(f"[!] Video file not found: {args.video}")
            sys.exit(1)
        frame_source = VideoFileFrameSource(args.video)
    else:
        frame_source = DesktopCaptureFrameSource(target_fps=30.0)

    manager = DecisionAnalysisManager(
        frame_source=frame_source,
        session_id=args.session,
        mode=args.mode.upper(),
        blind_mode=args.blind
    )

    if args.no_gui:
        print(f"[*] Running in headless mode for {args.max_frames} frames...")
        frames_done = 0
        latencies = []
        for _ in range(args.max_frames):
            frame = manager.process_next_frame(force_decision=True)
            if frame is None:
                break
            frames_done += 1
            latencies.append(manager.state.performance.total_overlay_latency_ms)
            time.sleep(0.01)

        avg_lat = sum(latencies) / max(1, len(latencies))
        print(f"[+] Headless run completed: {frames_done} frames, Avg Total Latency: {avg_lat:.2f}ms")
        frame_source.close()
        return

    # Interactive GUI Loop
    win_name = "TFT Decision Validation Overlay"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, 1280, 720)

    try:
        while True:
            rendered = manager.process_next_frame()
            if rendered is None:
                break

            cv2.imshow(win_name, rendered)
            key = cv2.waitKey(16) & 0xFF

            if key == 27 or key == ord("q"):  # ESC or Q to quit
                break
            elif key == ord(" "):  # Space: toggle play/pause
                if hasattr(frame_source, "toggle_pause"):
                    frame_source.toggle_pause()
            elif key == ord("1"):  # [1] REASONABLE
                manager.record_human_judgment(HumanEngineJudgment.REASONABLE)
                print(f"[*] Recorded: REASONABLE @ {manager.state.timestamp_sec:.2f}s")
            elif key == ord("2"):  # [2] QUESTIONABLE
                manager.record_human_judgment(HumanEngineJudgment.QUESTIONABLE)
                print(f"[*] Recorded: QUESTIONABLE @ {manager.state.timestamp_sec:.2f}s")
            elif key == ord("3"):  # [3] WRONG
                manager.record_human_judgment(HumanEngineJudgment.WRONG)
                print(f"[*] Recorded: WRONG @ {manager.state.timestamp_sec:.2f}s")
            elif key == ord("4"):  # [4] UNKNOWN
                manager.record_human_judgment(HumanEngineJudgment.UNKNOWN)
                print(f"[*] Recorded: UNKNOWN @ {manager.state.timestamp_sec:.2f}s")
            elif key == ord("b"):  # [B] Toggle Blind Mode
                manager.state.blind_mode = not manager.state.blind_mode
                manager.state.reveal_recommendation = not manager.state.blind_mode
                print(f"[*] Blind Mode: {'ON' if manager.state.blind_mode else 'OFF'}")
            elif key == ord("r"):  # [R] Blind Preference: ROLL
                manager.record_human_preference_blind(HumanPreference.ROLL)
                print(f"[*] Blind Choice: ROLL -> Engine: {manager.state.recommended_action}")
            elif key == ord("l"):  # [L] Blind Preference: LEVEL_UP
                manager.record_human_preference_blind(HumanPreference.LEVEL_UP)
                print(f"[*] Blind Choice: LEVEL_UP -> Engine: {manager.state.recommended_action}")
            elif key == ord("s"):  # [S] Blind Preference: SAVE_GOLD
                manager.record_human_preference_blind(HumanPreference.SAVE_GOLD)
                print(f"[*] Blind Choice: SAVE_GOLD -> Engine: {manager.state.recommended_action}")

    finally:
        frame_source.close()
        cv2.destroyAllWindows()
        print("[+] Application closed.")


if __name__ == "__main__":
    main()
