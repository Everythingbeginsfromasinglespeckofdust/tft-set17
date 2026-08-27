#!/usr/bin/env python3
"""Register video sessions into pilot_manifest.json."""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import cv2
from tft.vision.pilot_models import PilotSession, PilotManifest, EconomicArchetype


def parse_args():
    parser = argparse.ArgumentParser(description="Register Pilot Sessions")
    parser.add_argument("--manifest", type=str, default=os.path.join(_HERE, "data", "backtest", "pilot", "pilot_manifest.json"))
    parser.add_argument("--session-id", type=str, required=False, help="Session ID (e.g. SESSION_A)")
    parser.add_argument("--video", type=str, required=False, help="Video path")
    parser.add_argument("--match-id", type=str, default=None)
    parser.add_argument("--participant-id", type=str, default=None)
    parser.add_argument("--final-placement", type=int, default=None)
    parser.add_argument("--archetype", type=str, default="UNKNOWN")
    parser.add_argument("--init-default", action="store_true", help="Initialize default 3 pilot sessions")
    return parser.parse_args()


def inspect_video(video_path: str):
    if not os.path.exists(video_path):
        return 0.0, "1280x720", 60.0
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    n_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dur = n_frames / max(1.0, fps)
    cap.release()
    return dur, f"{w}x{h}", fps


def main():
    args = parse_args()
    print("=" * 80)
    print("📋 TFT MULTI-SESSION PILOT V1 -- SESSION REGISTRATION")
    print("=" * 80)

    manifest = PilotManifest()
    if os.path.exists(args.manifest):
        manifest = PilotManifest.load_from_json(args.manifest)

    if args.init_default or not args.session_id:
        # Register standard 3 sessions
        default_sessions = [
            (
                "SESSION_A",
                r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4",
                "MATCH_EDA87AD9",
                "PLAYER_1",
                2,
                EconomicArchetype.BALANCED_STANDARD
            ),
            (
                "SESSION_B",
                r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\3d739316-3c52-441a-81a2-2b585097e67c-2026-08-16-02-22-55.mp4",
                "MATCH_3D739316",
                "PLAYER_2",
                1,
                EconomicArchetype.FAST_LEVELUP
            ),
            (
                "SESSION_C",
                r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\45b5fac1-76f7-42d9-847d-a504bb5d6653-2026-08-16-01-35-19.mp4",
                "MATCH_45B5FAC1",
                "PLAYER_3",
                4,
                EconomicArchetype.REROLL_HEAVY
            ),
        ]

        for sid, vpath, mid, pid, place, arch in default_sessions:
            dur, res, fps = inspect_video(vpath)
            session = PilotSession(
                session_id=sid,
                video_path=vpath,
                duration=dur,
                resolution=res,
                source_fps=fps,
                match_id=mid,
                participant_id=pid,
                identity_verified=True,
                final_placement=place,
                economic_archetype=arch,
                metadata={"registered_by": "pilot_v1_initializer"}
            )
            manifest.add_session(session)
            print(f"[*] Registered {sid}: {dur:.1f}s, {res} @ {fps:.1f} fps (Match: {mid}, Placement: {place})")

    else:
        dur, res, fps = inspect_video(args.video)
        session = PilotSession(
            session_id=args.session_id,
            video_path=args.video,
            duration=dur,
            resolution=res,
            source_fps=fps,
            match_id=args.match_id,
            participant_id=args.participant_id,
            identity_verified=True,
            final_placement=args.final_placement,
            economic_archetype=EconomicArchetype(args.archetype),
            metadata={"registered_by": "cli"}
        )
        manifest.add_session(session)
        print(f"[*] Registered {args.session_id}: {dur:.1f}s, {res} @ {fps:.1f} fps")

    manifest.save_to_json(args.manifest)
    print(f"\n[+] Saved manifest ({len(manifest.sessions)} sessions) -> {args.manifest}")
    print("=" * 80)


if __name__ == "__main__":
    main()
