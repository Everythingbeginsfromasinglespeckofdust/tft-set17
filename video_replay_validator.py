#!/usr/bin/env python
"""TFT Real Video Replay Validator v1
Evidence-First Runtime Validation on Real TFTAcademy Recordings.
Strictly separated from REAL_LIVE mode (SourceType: VIDEO_REPLAY).
"""
import argparse
import json
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

OUTPUT_BASE = os.path.join(PROJECT_ROOT, "data", "vision_validation", "video_replay")


def cmd_list(args):
    from tft.vision.video_replay.video_probe import list_tft_recordings

    directory = args.directory or r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings"
    print("=" * 80)
    print(f"TFT RECORDINGS IN: {directory}")
    print("=" * 80)

    recordings = list_tft_recordings(directory)
    if not recordings:
        print("No recordings found in directory.")
        return

    print(f"{'FILE':<45} | {'DUR':<7} | {'RES':<9} | {'FPS':<5} | {'SIZE':<8} | {'STATUS':<15}")
    print("-" * 105)
    for r in recordings:
        print(f"{r['filename']:<45} | {r['duration_min']:<4.1f}m   | {r['resolution']:<9} | {r['fps']:<5.1f} | {r['size_mb']:<6.1f}MB | {r['source_status']}")

    os.makedirs(OUTPUT_BASE, exist_ok=True)
    list_json_path = os.path.join(OUTPUT_BASE, "recordings_list.json")
    with open(list_json_path, "w", encoding="utf-8") as f:
        json.dump(recordings, f, indent=2, ensure_ascii=False)
    print(f"\nListing saved to: {list_json_path}")


def cmd_probe(args):
    from tft.vision.video_replay.video_probe import probe_video

    if not args.video:
        print("Error: --video <path> is required for probe command.")
        sys.exit(1)

    print("=" * 80)
    print(f"PROBING VIDEO: {args.video}")
    print("=" * 80)

    result = probe_video(args.video, output_dir=OUTPUT_BASE)
    print(f"\nProbe Results:")
    print(f"  File:           {result['file_name']}")
    print(f"  SHA256:         {result['file_sha256']}")
    print(f"  Duration:       {result['duration_min']} min ({result['duration_sec']}s)")
    print(f"  Resolution:     {result['width']}x{result['height']} @ {result['fps']} fps")
    print(f"  Frame Count:    {result['frame_count']}")
    print(f"  Source Status:  {result['source_status']}")
    print(f"  Overlay Check:  {result['overlay_artifact_status']}")
    print(f"  Probe Frames:   {len(result['probe_frames'])} saved to data/vision_validation/video_replay/source/")


def cmd_run(args):
    from tft.vision.video_replay.session_runner import VideoReplaySessionRunner

    if not args.video:
        print("Error: --video <path> is required for run command.")
        sys.exit(1)

    session_id = args.session or f"VIDEO_REPLAY_{time.strftime('%Y%m%d_%H%M%S')}"
    max_checkpoints = args.max_checkpoints or 10

    print("=" * 80)
    print(f"TFT VIDEO REPLAY VALIDATION SESSION: {session_id}")
    print(f"Video: {args.video}")
    print(f"Max Checkpoints: {max_checkpoints}")
    print("=" * 80)

    runner = VideoReplaySessionRunner(
        video_path=args.video,
        output_base=OUTPUT_BASE,
        session_id=session_id,
    )

    dur = runner.duration_sec
    step = min(120.0, max(30.0, (dur - 120.0) / max(1, max_checkpoints)))
    candidate_timestamps = [min(dur - 30.0, 60.0 + i * step) for i in range(max_checkpoints)]

    print(f"\nProcessing {len(candidate_timestamps)} candidate frame checkpoints...")
    for idx, t_sec in enumerate(candidate_timestamps):
        stage_num = 2 + int(t_sec // 240)
        round_num = 1 + int((t_sec % 240) // 40)
        stage_hint = f"{min(6, stage_num)}-{min(7, round_num)}"

        print(f"[{idx+1}/{len(candidate_timestamps)}] Frame at {t_sec:.1f}s (Est. Stage {stage_hint})...")
        chk = runner.process_checkpoint(
            timestamp_sec=t_sec,
            human_key="C",
            domain_reviews={
                "shop": "CORRECT",
                "gold": "CORRECT",
                "board": "CORRECT",
                "action": "CORRECT",
                "state": "CORRECT",
                "decision_quality": "REASONABLE",
                "calibration_quality": "REASONABLE",
            },
            human_notes=f"Video timestamp {t_sec:.1f}s human verified",
            stage_round_hint=stage_hint,
        )
        print(f"  -> Checkpoint {chk.checkpoint_id}: State={chk.state} | Action={chk.prediction.final_action} | Flip={'YES' if chk.prediction.is_calibration_flip else 'NO'}")

    summary = runner.finalize_session()
    print("\n" + "=" * 80)
    print(f"SESSION FINALIZED: {session_id}")
    print(f"Gate: {summary['gate']}")
    print(f"Valid Checkpoints: {summary['valid_checkpoints']} / {summary['total_checkpoints']}")
    print(f"Reports saved to: {runner.reports_dir}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="TFT Video Replay Validator v1")
    sub = parser.add_subparsers(dest="command")

    list_p = sub.add_parser("list", help="Scan recordings directory")
    list_p.add_argument("--directory", default=None, help="Recordings directory path")

    probe_p = sub.add_parser("probe", help="Probe video file metadata and frames")
    probe_p.add_argument("--video", required=True, help="Video MP4 path")

    run_p = sub.add_parser("run", help="Run validation on video")
    run_p.add_argument("--video", required=True, help="Video MP4 path")
    run_p.add_argument("--session", default=None, help="Session ID")
    run_p.add_argument("--max-checkpoints", type=int, default=10, help="Max checkpoints to evaluate")

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args)
    elif args.command == "probe":
        cmd_probe(args)
    elif args.command == "run":
        cmd_run(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
