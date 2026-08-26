import cv2
import os
import sys
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')

repo_root = r"C:\Users\mrjdh\.gemini\antigravity\scratch\tft-set17"
sys.path.insert(0, os.path.join(repo_root, "output", "video_analysis"))

import shop_recognizer as sr
import hybrid_shop_recognizer as hsr
import board_recognizer as br
from generate_shop_timeline import infer_star_from_purchase_history

VIDEO_PATH = r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4"
out_dir = os.path.join(repo_root, "output", "video_analysis")
out_video_path = os.path.join(out_dir, "overlay_verification_eda87ad9_300s_360s.mp4")

START_SEC = 300.0
END_SEC = 360.0

cap = cv2.VideoCapture(VIDEO_PATH)
fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

start_frame = int(START_SEC * fps)
end_frame = int(END_SEC * fps)
total_render_frames = end_frame - start_frame

print(f"Rendering overlay video: {w}x{h}, {fps} fps")
print(f"Segment: {START_SEC}s ~ {END_SEC}s ({total_render_frames} frames)")

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
writer = cv2.VideoWriter(out_video_path, fourcc, fps, (w, h))

# Load models
hybrid_shop = hsr.HybridShopRecognizer()
board_rec = br.BoardRecognizer()

# Load Fonts
font_path = r"C:\Windows\Fonts\malgunbd.ttf"
font_title = ImageFont.truetype(font_path, 22)
font_shop = ImageFont.truetype(font_path, 14)
font_small = ImageFont.truetype(font_path, 11)
font_board = ImageFont.truetype(font_path, 13)

# Track purchases and star completions
buy_events = []
star_completions = []
purchase_counts = {}
prev_shop_champs = None

# Cache for frame prediction (update every 0.25s / 15 frames)
cached_shop = None
cached_board = None
last_update_f = -999

# Star symbol mapping
star_symbols = {1: "★", 2: "★★", 3: "★★★"}

print("Starting frame-by-frame rendering...")

cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

for f_idx in range(start_frame, end_frame):
    ret, frame = cap.read()
    if not ret: break

    current_sec = f_idx / fps

    # 1. Update recognizers every 15 frames (0.25s)
    if f_idx - last_update_f >= 15 or cached_shop is None:
        last_update_f = f_idx
        cached_shop = hybrid_shop.recognize_shop_hybrid(frame)
        cached_board = board_rec.recognize_board(frame, min_confidence=0.52)

        # Check for BUY_CANDIDATE event
        curr_champs = [c["champion"] or "EMPTY" for c in cached_shop]
        if prev_shop_champs is not None:
            diffs = [i for i in range(5) if prev_shop_champs[i] != curr_champs[i]]
            if len(diffs) == 1:
                if curr_champs[diffs[0]] == "EMPTY" and prev_shop_champs[diffs[0]] != "EMPTY":
                    bought_c = prev_shop_champs[diffs[0]]
                    buy_ev = {
                        "sec": current_sec,
                        "champion": bought_c,
                        "slot": diffs[0] + 1
                    }
                    buy_events.append(buy_ev)
                    purchase_counts[bought_c] = purchase_counts.get(bought_c, 0) + 1
                    # Check 2-star completion
                    if purchase_counts[bought_c] == 3:
                        star_completions.append({
                            "sec": current_sec,
                            "champion": bought_c,
                            "star": 2
                        })
                    elif purchase_counts[bought_c] == 9:
                        star_completions.append({
                            "sec": current_sec,
                            "champion": bought_c,
                            "star": 3
                        })
        prev_shop_champs = curr_champs

    # 2. Draw Overlays
    # (A) OpenCV base geometry (Rectangles)
    # Shop boxes
    for i in range(5):
        cx1 = sr.SHOP_GEOMETRY["start_x"] + i * (sr.SHOP_GEOMETRY["card_w"] + sr.SHOP_GEOMETRY["gap"])
        cx2 = cx1 + sr.SHOP_GEOMETRY["card_w"]
        cy1, cy2 = sr.SHOP_GEOMETRY["card_y1"], sr.SHOP_GEOMETRY["card_y2"]
        slot_data = cached_shop[i]

        if slot_data.get("is_empty"):
            color = (80, 80, 80)
            cv2.rectangle(frame, (cx1, cy1), (cx2, cy2), color, 1)
        else:
            conf = slot_data.get("confidence", 0.0)
            color = (0, 255, 0) if conf >= 0.50 else (0, 0, 255)
            cv2.rectangle(frame, (cx1, cy1), (cx2, cy2), color, 2)

    # Board Hexes & Bench
    for u in cached_board["field_units"]:
        r, c = u["row"], u["col"]
        row_height = (br.DEFAULT_ROIS["field"]["y2"] - br.DEFAULT_ROIS["field"]["y1"]) // 4
        col_width = (br.DEFAULT_ROIS["field"]["x2"] - br.DEFAULT_ROIS["field"]["x1"]) // 7
        ry1 = br.DEFAULT_ROIS["field"]["y1"] + r * row_height
        ry2 = ry1 + row_height
        x_offset = (col_width // 2) if r % 2 == 1 else 0
        cx1 = br.DEFAULT_ROIS["field"]["x1"] + c * col_width + x_offset
        cx2 = cx1 + col_width - 10
        cv2.rectangle(frame, (cx1, ry1), (cx2, ry2), (0, 255, 0), 2)

    for u in cached_board["bench_units"]:
        slot_idx = u["slot"]
        by1, by2 = br.DEFAULT_ROIS["bench"]["y1"], br.DEFAULT_ROIS["bench"]["y2"]
        bx1 = 250 + slot_idx * 80
        bx2 = bx1 + 65
        cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0, 255, 0), 2)

    # (B) PIL Korean Text & Banner Overlays
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    # Overlay Shop Text
    for i in range(5):
        cx1 = sr.SHOP_GEOMETRY["start_x"] + i * (sr.SHOP_GEOMETRY["card_w"] + sr.SHOP_GEOMETRY["gap"])
        cy1 = sr.SHOP_GEOMETRY["card_y1"]
        slot_data = cached_shop[i]

        if not slot_data.get("is_empty"):
            cname = slot_data.get("champion", "")
            cost = slot_data.get("cost", "")
            conf = slot_data.get("confidence", 0.0)
            ocr = slot_data.get("raw_ocr", "")
            # Background chip for readability
            draw.rectangle([cx1 + 4, cy1 + 4, cx1 + 132, cy1 + 40], fill=(0, 0, 0, 180))
            draw.text((cx1 + 6, cy1 + 6), f"{cname} ({cost}G)", font=font_shop, fill=(255, 255, 0))
            draw.text((cx1 + 6, cy1 + 24), f"Conf:{conf:.2f} | OCR:{ocr}", font=font_small, fill=(200, 255, 200))
        else:
            draw.rectangle([cx1 + 4, cy1 + 4, cx1 + 132, cy1 + 24], fill=(0, 0, 0, 150))
            draw.text((cx1 + 8, cy1 + 6), "EMPTY (빈 슬롯)", font=font_small, fill=(160, 160, 160))

    # Overlay Board Text
    for u in cached_board["field_units"]:
        r, c = u["row"], u["col"]
        row_height = (br.DEFAULT_ROIS["field"]["y2"] - br.DEFAULT_ROIS["field"]["y1"]) // 4
        col_width = (br.DEFAULT_ROIS["field"]["x2"] - br.DEFAULT_ROIS["field"]["x1"]) // 7
        ry1 = br.DEFAULT_ROIS["field"]["y1"] + r * row_height
        x_offset = (col_width // 2) if r % 2 == 1 else 0
        cx1 = br.DEFAULT_ROIS["field"]["x1"] + c * col_width + x_offset
        cname = u["champion"]
        star_str = star_symbols.get(u["star_level"], "★")
        draw.rectangle([cx1, ry1 - 18, cx1 + 95, ry1], fill=(0, 0, 0, 200))
        draw.text((cx1 + 2, ry1 - 16), f"{cname} {star_str}", font=font_board, fill=(0, 255, 100))

    for u in cached_board["bench_units"]:
        slot_idx = u["slot"]
        by1 = br.DEFAULT_ROIS["bench"]["y1"]
        bx1 = 250 + slot_idx * 80
        cname = u["champion"]
        star_str = star_symbols.get(u["star_level"], "★")
        draw.rectangle([bx1, by1 - 18, bx1 + 65, by1], fill=(0, 0, 0, 200))
        draw.text((bx1 + 2, by1 - 16), f"{cname} {star_str}", font=font_small, fill=(100, 255, 255))

    # Time code overlay at top left
    draw.rectangle([10, 10, 240, 42], fill=(0, 0, 0, 220))
    draw.text((15, 14), f"TIME: {current_sec:05.1f}s / {END_SEC}s", font=font_title, fill=(255, 255, 255))

    # (C) Event Banners
    # 1. Buy Event Banner (Active for 3.0s after occurrence)
    active_buys = [b for b in buy_events if 0.0 <= (current_sec - b["sec"]) <= 3.0]
    if active_buys:
        latest_buy = active_buys[-1]
        draw.rectangle([340, 12, 940, 52], fill=(20, 120, 20), outline=(0, 255, 0), width=2)
        draw.text((360, 18), f"🛒 BUY DETECTED: {latest_buy['champion']} (Card Slot {latest_buy['slot']})",
                  font=font_title, fill=(255, 255, 0))

    # 2. 2★ Complete Banner (Active for 5.0s after occurrence)
    active_stars = [s for s in star_completions if 0.0 <= (current_sec - s["sec"]) <= 5.0]
    if active_stars:
        latest_star = active_stars[-1]
        draw.rectangle([300, 58, 980, 102], fill=(120, 20, 120), outline=(255, 100, 255), width=2)
        draw.text((320, 64), f"✨ {latest_star['star']}★ COMPLETE: {latest_star['champion']} (3장 합성 완료!)",
                  font=font_title, fill=(255, 255, 255))

    # Convert back to BGR and write
    final_frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    writer.write(final_frame)

    if (f_idx - start_frame) % 300 == 0:
        pct = ((f_idx - start_frame) / total_render_frames) * 100.0
        print(f"  Rendered {f_idx - start_frame}/{total_render_frames} frames ({pct:.1f}%)...")

cap.release()
writer.release()

file_size_mb = os.path.getsize(out_video_path) / (1024 * 1024)
print(f"\nOverlay Video Successfully Created!")
print(f"Output File: {out_video_path}")
print(f"File Size:   {file_size_mb:.2f} MB")
