#!/usr/bin/env python3
"""Register video recording sessions into Human Validation Campaign."""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import cv2
from tft.vision.campaign_manager import CampaignManager
from tft.vision.campaign_models import CampaignSessionInfo, EconomicArchetype


def parse_args():
    parser = argparse.ArgumentParser(description="Register Session into Campaign")
    parser.add_argument("--campaign", type=str, default="CAMPAIGN_001", help="Campaign ID")
    parser.add_argument("--session", type=str, default=None, help="Session ID (e.g. SESSION_D)")
    parser.add_argument("--video", type=str, default=None, help="Path to MP4 recording")
    parser.add_argument("--match-id", type=str, default=None, help="Match ID")
    parser.add_argument("--player-id", type=str, default="PLAYER_1", help="Player ID")
    parser.add_argument("--placement", type=int, default=1, help="Final placement (1-8)")
    parser.add_argument("--archetype", type=str, default="BALANCED_STANDARD", help="Economic Archetype")
    parser.add_argument("--init-default", action="store_true", help="Register 11 default multi-match sessions (SESSION_A to SESSION_K)")
    return parser.parse_args()


def get_video_meta(v_path: str):
    if not os.path.exists(v_path):
        return (1280, 720), 60.0, 600.0, 36000
    cap = cv2.VideoCapture(v_path)
    if not cap.isOpened():
        return (1280, 720), 60.0, 600.0, 36000
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    dur = frames / max(1.0, fps)
    return (w, h), fps, dur, frames


def main():
    args = parse_args()
    mgr = CampaignManager()

    if args.init_default:
        rec_base = r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings"
        default_sessions = [
            ("SESSION_A", os.path.join(rec_base, "eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4"), "MATCH_EDA87AD9", "PLAYER_A", 2, EconomicArchetype.BALANCED_STANDARD),
            ("SESSION_B", os.path.join(rec_base, "3d739316-3c52-441a-81a2-2b585097e67c-2026-08-16-02-22-55.mp4"), "MATCH_3D739316", "PLAYER_B", 1, EconomicArchetype.FAST_LEVELUP),
            ("SESSION_C", os.path.join(rec_base, "45b5fac1-76f7-42d9-847d-a504bb5d6653_part2-2026-08-16-01-39-49.mp4"), "MATCH_45B5FAC1", "PLAYER_C", 4, EconomicArchetype.REROLL_HEAVY),
            ("SESSION_D", os.path.join(rec_base, "32d40585-37cd-4a9c-8a1e-82f6954c93ca-2026-08-26-23-49-27.mp4"), "MATCH_32D40585", "PLAYER_D", 2, EconomicArchetype.FAST_LEVELUP),
            ("SESSION_E", os.path.join(rec_base, "56e6fb98-3716-4124-b4f1-8718629b533c-2026-08-26-23-20-20.mp4"), "MATCH_56E6FB98", "PLAYER_E", 5, EconomicArchetype.HYPER_ROLL),
            ("SESSION_F", os.path.join(rec_base, "6e78f07b-2b34-4659-84be-90150c707973-2026-08-26-16-12-07.mp4"), "MATCH_6E78F07B_1", "PLAYER_F", 3, EconomicArchetype.BALANCED_STANDARD),
            ("SESSION_G", os.path.join(rec_base, "6e78f07b-2b34-4659-84be-90150c707973_part2-2026-08-26-17-02-10.mp4"), "MATCH_6E78F07B_2", "PLAYER_G", 1, EconomicArchetype.FAST_LEVELUP),
            ("SESSION_H", os.path.join(rec_base, "adedde76-7119-400e-b65e-9b7f58a795b7-2026-08-26-20-32-22.mp4"), "MATCH_ADEDDE76_1", "PLAYER_H", 2, EconomicArchetype.BALANCED_STANDARD),
            ("SESSION_I", os.path.join(rec_base, "adedde76-7119-400e-b65e-9b7f58a795b7_part2-2026-08-26-21-04-56.mp4"), "MATCH_ADEDDE76_2", "PLAYER_I", 6, EconomicArchetype.REROLL_HEAVY),
            ("SESSION_J", os.path.join(rec_base, "b6a200e3-cf25-44e8-a909-378adbdd5697-2026-08-27-00-45-40.mp4"), "MATCH_B6A200E3", "PLAYER_J", 1, EconomicArchetype.FAST_LEVELUP),
            ("SESSION_K", os.path.join(rec_base, "c5f55151-9503-4eb7-ab35-608cf6270f54-2026-08-18-23-36-49.mp4"), "MATCH_C5F55151", "PLAYER_K", 7, EconomicArchetype.BALANCED_STANDARD),
        ]

        print("=" * 80)
        print(f"📋 REGISTERING {len(default_sessions)} MATCH SESSIONS INTO {args.campaign}")
        print("=" * 80)

        for sid, vpath, mid, pid, place, arch in default_sessions:
            res, fps, dur, frames = get_video_meta(vpath)
            s_info = CampaignSessionInfo(
                session_id=sid,
                video_path=vpath,
                match_id=mid,
                player_id=pid,
                final_placement=place,
                economic_archetype=arch,
                resolution=res,
                fps=fps,
                duration_sec=dur,
                total_frames=frames
            )
            mgr.register_session(args.campaign, s_info)
            print(f"[*] Registered {sid:10s} | {dur:6.1f}s | {res[0]}x{res[1]} @ {fps:.0f}fps | Place: #{place} | Archetype: {arch.value}")

        print("=" * 80)
        print(f"[+] All {len(default_sessions)} sessions registered successfully.")
    else:
        if not args.session or not args.video:
            print("[!] Specify --session and --video or use --init-default")
            sys.exit(1)
        res, fps, dur, frames = get_video_meta(args.video)
        s_info = CampaignSessionInfo(
            session_id=args.session,
            video_path=args.video,
            match_id=args.match_id or f"MATCH_{args.session}",
            player_id=args.player_id,
            final_placement=args.placement,
            economic_archetype=EconomicArchetype(args.archetype),
            resolution=res,
            fps=fps,
            duration_sec=dur,
            total_frames=frames
        )
        mgr.register_session(args.campaign, s_info)
        print(f"[+] Registered {args.session} into {args.campaign}")


if __name__ == "__main__":
    main()
