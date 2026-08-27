#!/usr/bin/env python3
"""TFT Vision Validation Overlay Application: Video Replay, Live Capture, and Human Verification GUI."""
import argparse
import os
import sys
import time

import cv2
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from tft.vision.frame_source import FrameSource, MockFrameSource
from tft.vision.video_frame_source import VideoFileFrameSource
from tft.vision.live_capture_source import DesktopCaptureFrameSource
from tft.vision.analysis_manager import VisionAnalysisManager
from tft.vision.validation_models import ErrorReason, HumanVerdict


def parse_args():
    parser = argparse.ArgumentParser(description="TFT Vision Validation Overlay")
    parser.add_argument("--mode", type=str, choices=["validation", "production"], default="validation", help="Overlay mode")
    parser.add_argument("--source", type=str, choices=["video", "live", "mock"], default="video", help="Input frame source")
    parser.add_argument("--video", type=str, default=None, help="Path to MP4 video file for video mode")
    parser.add_argument("--session", type=str, default="SESSION_A", help="Session ID")
    parser.add_argument("--fps", type=float, default=20.0, help="Analysis FPS (default: 20.0)")
    parser.add_argument("--no-gui", action="store_true", help="Run in headless mode without opening OpenCV window")
    parser.add_argument("--max-frames", type=int, default=None, help="Max frames to process in headless mode")
    return parser.parse_args()


def create_frame_source(args) -> FrameSource:
    if args.source == "video":
        v_path = args.video
        if not v_path or not os.path.exists(v_path):
            # Fallback to test clip if video not specified or not found
            fallback = os.path.join(_HERE, "output", "video_analysis", "overlay_verification_eda87ad9_300s_360s.mp4")
            if os.path.exists(fallback):
                v_path = fallback
            else:
                print(f"[!] Video file not found: {v_path}. Falling back to MockFrameSource.")
                return MockFrameSource(fps=args.fps, total_frames=100)
        return VideoFileFrameSource(v_path)
    elif args.source == "live":
        return DesktopCaptureFrameSource(target_fps=30.0)
    else:
        return MockFrameSource(fps=args.fps, total_frames=100)


def main():
    args = parse_args()
    print("=" * 80)
    print("🖥️  TFT VISION VALIDATION OVERLAY v1")
    print("=" * 80)
    print(f"[*] Mode        : {args.mode.upper()}")
    print(f"[*] Frame Source: {args.source.upper()}")
    print(f"[*] Session ID  : {args.session}")

    source = create_frame_source(args)
    manager = VisionAnalysisManager(
        frame_source=source,
        session_id=args.session,
        mode=args.mode.upper(),
        analysis_fps=args.fps
    )

    window_name = "TFT Vision Validation Overlay v1"
    if not args.no_gui:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1280, 720)

    frame_count = 0
    t_start = time.time()

    print("[*] Controls: [Space]=Pause/Play | [C]=Correct | [W]=Wrong | [R]=Roll | [B]=Buy | [T]=Toggle ROIs | [Esc]=Exit")

    try:
        while True:
            rendered = manager.process_next_frame()
            if rendered is None:
                print("[*] End of frame stream reached.")
                break

            frame_count += 1
            if args.max_frames and frame_count >= args.max_frames:
                print(f"[*] Reached max frames limit ({args.max_frames}).")
                break

            if not args.no_gui:
                cv2.imshow(window_name, rendered)
                key = cv2.waitKey(1) & 0xFF

                if key in [27, ord('q')]:  # Esc or q
                    break
                elif key == 32:  # Space (Pause/Resume)
                    if manager.state.is_paused:
                        source.resume()
                    else:
                        source.pause()
                elif key == ord('c'):  # Correct
                    manager.verify_correct()
                    print(f"[{manager.state.current_timestamp_sec:.2f}s] Marked CORRECT")
                elif key == ord('w'):  # Wrong
                    manager.verify_wrong(ErrorReason.ACTION_ERROR)
                    print(f"[{manager.state.current_timestamp_sec:.2f}s] Marked WRONG (Diagnostic snapshot saved)")
                elif key == ord('x'):  # Skip
                    manager.verify_skip()
                elif key == ord('r'):  # Annotate Roll
                    manager.annotate_action("ROLL")
                    print(f"[{manager.state.current_timestamp_sec:.2f}s] Annotated ROLL")
                elif key == ord('b'):  # Annotate Buy
                    manager.annotate_action("BUY_UNIT")
                    print(f"[{manager.state.current_timestamp_sec:.2f}s] Annotated BUY_UNIT")
                elif key == ord('l'):  # Annotate Level
                    manager.annotate_action("LEVEL_UP")
                elif key == ord('n'):  # Annotate No Action
                    manager.annotate_action("NO_ACTION")
                elif key == ord('t'):  # Toggle ROIs
                    manager.toggle_rois()
                elif key == ord('1'):
                    source.set_speed(0.25)
                elif key == ord('2'):
                    source.set_speed(0.50)
                elif key == ord('3'):
                    source.set_speed(1.00)
                elif key == ord('4'):
                    source.set_speed(2.00)

    finally:
        source.close()
        if not args.no_gui:
            cv2.destroyAllWindows()

    elapsed = time.time() - t_start
    summary = manager.store.get_summary(args.session)
    print("\n" + "=" * 80)
    print("🏁 OVERLAY SESSION SUMMARY")
    print("=" * 80)
    print(f"  • Processed Frames : {frame_count} ({frame_count/max(0.01, elapsed):.1f} FPS)")
    print(f"  • Total Reviewed   : {summary.total_reviewed}")
    print(f"  • Correct Labels   : {summary.correct_count}")
    print(f"  • Wrong Labels     : {summary.wrong_count}")
    print(f"  • Accuracy (Human) : {summary.to_dict()['accuracy']:.1%}")
    print("=" * 80)


if __name__ == "__main__":
    main()
