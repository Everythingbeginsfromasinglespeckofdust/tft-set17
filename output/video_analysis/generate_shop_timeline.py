#!/usr/bin/env python3
"""TFT Set 17 상점 타임라인 및 구매/새로고침 후보 이벤트 생성기 (Generate Shop Timeline)."""
import argparse
import csv
import json
import os
import sys
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import shop_recognizer as sr


def process_video_shop_timeline(
    video_path: str,
    output_dir: str,
    interval_sec: float = 0.5,
    max_duration_sec: Optional[float] = 300.0,
) -> Dict[str, Any]:
    """비디오를 정기 샘플링하여 상점 카드 상태 변화 및 리롤/구매 후보 이벤트를 추출."""
    assert os.path.exists(video_path), f"Video not found: {video_path}"
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_dur = total_frames / fps
    scan_limit = min(video_dur, max_duration_sec) if max_duration_sec else video_dur

    recognizer = sr.ShopRecognizer()
    timeline_records: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []

    sec = 0.0
    prev_cards: Optional[List[str]] = None

    print(f"Scanning shop timeline from 0.0s to {scan_limit:.1f}s (Interval: {interval_sec}s)...")

    while sec <= scan_limit:
        f_idx = int(sec * fps)
        if f_idx >= total_frames:
            break
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
        ret, frame = cap.read()
        if not ret:
            break

        shop_cards = recognizer.recognize_shop(frame, min_confidence=0.50)
        curr_champs = [c["champion"] or "EMPTY" for c in shop_cards]

        event_type = "NO_CHANGE"
        if prev_cards is not None:
            # Check difference
            diff_indices = [i for i in range(5) if prev_cards[i] != curr_champs[i]]
            if len(diff_indices) >= 3:
                # 3개 이상 카드가 동시에 바뀌면 새로고침/자동 리롤 후보
                event_type = "REROLL_CANDIDATE"
                events.append({
                    "timestamp_sec": round(sec, 2),
                    "event": "REROLL_CANDIDATE",
                    "prev_shop": prev_cards,
                    "new_shop": curr_champs,
                })
            elif len(diff_indices) == 1:
                # 1개 슬롯만 비워지면 구매 후보
                if curr_champs[diff_indices[0]] == "EMPTY" and prev_cards[diff_indices[0]] != "EMPTY":
                    event_type = "BUY_CANDIDATE"
                    events.append({
                        "timestamp_sec": round(sec, 2),
                        "event": "BUY_CANDIDATE",
                        "bought_slot": diff_indices[0] + 1,
                        "champion": prev_cards[diff_indices[0]],
                    })

        timeline_records.append({
            "timestamp_sec": round(sec, 2),
            "card_1": curr_champs[0],
            "card_2": curr_champs[1],
            "card_3": curr_champs[2],
            "card_4": curr_champs[3],
            "card_5": curr_champs[4],
            "event_candidate": event_type,
        })

        prev_cards = curr_champs
        sec += interval_sec

    cap.release()

    # Save CSV
    csv_path = os.path.join(output_dir, "shop_timeline.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "timestamp_sec", "card_1", "card_2", "card_3", "card_4", "card_5", "event_candidate"
        ])
        writer.writeheader()
        writer.writerows(timeline_records)

    # Save JSON
    json_path = os.path.join(output_dir, "shop_timeline.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_samples": len(timeline_records),
            "total_events_detected": len(events),
            "events": events,
            "timeline": timeline_records,
        }, f, indent=2, ensure_ascii=False)

    print(f"Saved timeline to {csv_path} and {json_path} ({len(timeline_records)} samples, {len(events)} events).")
    return {
        "csv_path": csv_path,
        "json_path": json_path,
        "samples_count": len(timeline_records),
        "events_count": len(events),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=str, default=r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\6e831624-4c47-4e94-9176-92e7063b7a75-2026-08-16-00-24-31.mp4")
    parser.add_argument("--out", type=str, default=_HERE)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--max_sec", type=float, default=120.0)
    args = parser.parse_args()

    process_video_shop_timeline(args.video, args.out, interval_sec=args.interval, max_duration_sec=args.max_sec)
