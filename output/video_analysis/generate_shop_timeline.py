#!/usr/bin/env python3
"""TFT Set 17 상점 타임라인, 구매/리롤 이벤트 및 구매 이력 기반 성급 추론기 (Shop Timeline & Purchase Star Inference)."""
import argparse
import csv
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUTPUT = os.path.join(r"C:\Users\mrjdh\.gemini\antigravity\scratch\tft-set17\output\video_analysis")
if _OUTPUT not in sys.path:
    sys.path.insert(0, _OUTPUT)

import shop_recognizer as sr


def infer_star_from_purchase_history(
    buy_events: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    구매 이력(BUY_CANDIDATE 이벤트 스트림)으로부터 기물별 누적 구매 수 및 성급(2★, 3★) 완성 시점을 추론.
    
    규칙:
      - 동일 챔피언 3회 구매 -> 2성(2★) 완성
      - 동일 챔피언 6회 구매 -> 2번째 2성 완성
      - 동일 챔피언 9회 구매 -> 3성(3★) 완성
    """
    purchase_counts: Dict[str, int] = {}
    star_completions: List[Dict[str, Any]] = []
    champion_history: Dict[str, List[float]] = {}

    for event in buy_events:
        cname = event.get("champion")
        t_sec = event.get("timestamp_sec", 0.0)
        
        if not cname or cname == "EMPTY":
            continue

        purchase_counts[cname] = purchase_counts.get(cname, 0) + 1
        curr_count = purchase_counts[cname]

        if cname not in champion_history:
            champion_history[cname] = []
        champion_history[cname].append(t_sec)

        # Check star completion triggers
        if curr_count == 3:
            star_completions.append({
                "champion": cname,
                "star_level": 2,
                "completion_index": 1,
                "timestamp_sec": t_sec,
                "trigger_copy": 3,
                "purchase_timestamps": list(champion_history[cname])
            })
        elif curr_count == 6:
            star_completions.append({
                "champion": cname,
                "star_level": 2,
                "completion_index": 2,
                "timestamp_sec": t_sec,
                "trigger_copy": 6,
                "purchase_timestamps": list(champion_history[cname])
            })
        elif curr_count == 9:
            star_completions.append({
                "champion": cname,
                "star_level": 3,
                "completion_index": 1,
                "timestamp_sec": t_sec,
                "trigger_copy": 9,
                "purchase_timestamps": list(champion_history[cname])
            })

    # Summary of final star state per champion
    final_states: Dict[str, Dict[str, Any]] = {}
    for cname, total_copies in purchase_counts.items():
        highest_star = 3 if total_copies >= 9 else (2 if total_copies >= 3 else 1)
        final_states[cname] = {
            "total_purchased_copies": total_copies,
            "inferred_highest_star": highest_star,
            "two_star_count": total_copies // 3,
            "three_star_count": total_copies // 9,
            "remaining_1star_copies": total_copies % 3
        }

    return {
        "total_buy_events": len(buy_events),
        "unique_champions_purchased": len(purchase_counts),
        "star_completions": star_completions,
        "final_champion_states": final_states
    }


def process_video_shop_timeline(
    video_path: str,
    output_dir: str,
    interval_sec: float = 0.5,
    start_sec: float = 0.0,
    max_duration_sec: Optional[float] = 300.0,
) -> Dict[str, Any]:
    """비디오를 정기 샘플링하여 상점 카드 상태 변화 및 리롤/구매 후보 이벤트를 추출하고 성급 추론."""
    assert os.path.exists(video_path), f"Video not found: {video_path}"
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_dur = total_frames / fps
    end_sec = min(video_dur, start_sec + max_duration_sec) if max_duration_sec else video_dur

    recognizer = sr.ShopRecognizer()
    timeline_records: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []
    buy_events: List[Dict[str, Any]] = []

    sec = start_sec
    prev_cards: Optional[List[str]] = None

    print(f"Scanning shop timeline from {start_sec:.1f}s to {end_sec:.1f}s (Interval: {interval_sec}s)...")

    while sec <= end_sec:
        f_idx = int(sec * fps)
        if f_idx >= total_frames:
            break
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
        ret, frame = cap.read()
        if not ret:
            break

        shop_cards = recognizer.recognize_shop(frame, min_confidence=0.40)
        curr_champs = [c["champion"] or "EMPTY" for c in shop_cards]

        event_type = "NO_CHANGE"
        if prev_cards is not None:
            diff_indices = [i for i in range(5) if prev_cards[i] != curr_champs[i]]
            if len(diff_indices) >= 3:
                event_type = "REROLL_CANDIDATE"
                events.append({
                    "timestamp_sec": round(sec, 2),
                    "event": "REROLL_CANDIDATE",
                    "prev_shop": prev_cards,
                    "new_shop": curr_champs,
                })
            elif len(diff_indices) == 1:
                if curr_champs[diff_indices[0]] == "EMPTY" and prev_cards[diff_indices[0]] != "EMPTY":
                    event_type = "BUY_CANDIDATE"
                    buy_ev = {
                        "timestamp_sec": round(sec, 2),
                        "event": "BUY_CANDIDATE",
                        "bought_slot": diff_indices[0] + 1,
                        "champion": prev_cards[diff_indices[0]],
                    }
                    events.append(buy_ev)
                    buy_events.append(buy_ev)

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

    # 성급 추론 실행
    star_inference = infer_star_from_purchase_history(buy_events)

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
            "start_sec": start_sec,
            "end_sec": end_sec,
            "total_samples": len(timeline_records),
            "total_events_detected": len(events),
            "total_buy_events": len(buy_events),
            "events": events,
            "star_inference": star_inference,
            "timeline": timeline_records,
        }, f, indent=2, ensure_ascii=False)

    print(f"Saved timeline to {csv_path} and {json_path} ({len(timeline_records)} samples, {len(events)} events, {len(buy_events)} purchases).")
    return {
        "csv_path": csv_path,
        "json_path": json_path,
        "samples_count": len(timeline_records),
        "events_count": len(events),
        "buy_events_count": len(buy_events),
        "star_inference": star_inference,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=str, default=r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\6e831624-4c47-4e94-9176-92e7063b7a75-2026-08-16-00-24-31.mp4")
    parser.add_argument("--out", type=str, default=r"C:\Users\mrjdh\.gemini\antigravity\scratch\tft-set17\output\video_analysis\10min_audit")
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--start_sec", type=float, default=300.0)
    parser.add_argument("--max_sec", type=float, default=600.0)
    args = parser.parse_args()

    process_video_shop_timeline(
        args.video, args.out, interval_sec=args.interval,
        start_sec=args.start_sec, max_duration_sec=args.max_sec
    )
