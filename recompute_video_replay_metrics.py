#!/usr/bin/env python
"""TFT Video Replay Metrics Recomputer v1 — reads raw evidence only.
Usage: python recompute_video_replay_metrics.py --session <SESSION_ID>
"""
import argparse
import hashlib
import json
import os
import sys
import time

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "data", "vision_validation", "video_replay")


def sha256_file(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def recompute(session_dir):
    chk_dir = os.path.join(session_dir, "checkpoints")
    frame_dir = os.path.join(session_dir, "raw_frames")
    human_dir = os.path.join(session_dir, "human_inputs")
    pred_dir = os.path.join(session_dir, "predictions")

    frames_on_disk = len([f for f in os.listdir(frame_dir) if f.endswith(".png")]) if os.path.exists(frame_dir) else 0
    human_on_disk = len(os.listdir(human_dir)) if os.path.exists(human_dir) else 0
    preds_on_disk = len(os.listdir(pred_dir)) if os.path.exists(pred_dir) else 0

    dm = {d: {"correct":0,"wrong":0,"unknown":0,"total":0}
          for d in ["shop","gold","board","action","state"]}
    valid = invalid = missing_frames = hash_mm = label_contamination = 0

    if not os.path.exists(chk_dir):
        return {"error": "MISSING_CHECKPOINTS_DIR"}

    for fn in sorted(os.listdir(chk_dir)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(chk_dir, fn), encoding="utf-8") as f:
            data = json.load(f)

        if data.get("state") != "VERIFIED":
            invalid += 1
            continue

        cap = data.get("capture") or {}
        fp = cap.get("frame_path", "")
        if not fp or not os.path.exists(fp):
            missing_frames += 1
            invalid += 1
            continue
        if sha256_file(fp) != cap.get("frame_sha256", ""):
            hash_mm += 1
            invalid += 1
            continue

        hi = data.get("human_input")
        if not hi:
            invalid += 1
            continue

        pred = data.get("prediction") or {}
        review = data.get("review") or {}

        human_pref = review.get("human_preferred_action")
        final_action = pred.get("final_action")
        key = (hi.get("key_pressed") or "").upper()
        if human_pref and human_pref == final_action and key not in ("R","B","L","G"):
            label_contamination += 1

        valid += 1
        for d, k in [("shop","shop_verdict"),("gold","gold_verdict"),
                     ("board","board_verdict"),("action","action_verdict"),("state","state_verdict")]:
            v = review.get(k, "UNKNOWN")
            dm[d]["total"] += 1
            if v == "CORRECT": dm[d]["correct"] += 1
            elif v == "WRONG": dm[d]["wrong"] += 1
            else: dm[d]["unknown"] += 1

    def acc(d):
        return dm[d]["correct"] / dm[d]["total"] if dm[d]["total"] else None

    gate = ("VIDEO_REPLAY_BLOCKED" if label_contamination > 0 else
            "VIDEO_REPLAY_UNVERIFIABLE" if valid == 0 else
            "VIDEO_REPLAY_PRELIMINARY" if valid < 30 else
            "VIDEO_REPLAY_CONFIRMED")

    return {
        "recomputed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_type": "VIDEO_REPLAY",
        "frames_on_disk": frames_on_disk,
        "human_inputs_on_disk": human_on_disk,
        "predictions_on_disk": preds_on_disk,
        "valid_checkpoints": valid,
        "invalid_checkpoints": invalid,
        "missing_frames": missing_frames,
        "frame_hash_mismatches": hash_mm,
        "label_contamination": label_contamination,
        "shop_accuracy": acc("shop"),
        "gold_accuracy": acc("gold"),
        "board_accuracy": acc("board"),
        "action_accuracy": acc("action"),
        "state_accuracy": acc("state"),
        "domain_metrics": dm,
        "gate": gate,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--session", required=True)
    args = p.parse_args()

    sdir = os.path.join(OUTPUT_BASE, "sessions", args.session)
    if not os.path.exists(sdir):
        print(f"Session not found: {sdir}")
        sys.exit(1)

    r = recompute(sdir)
    print("=" * 60)
    print(f"RECOMPUTED VIDEO REPLAY METRICS: {args.session}")
    print("=" * 60)
    for k, v in r.items():
        if k not in ("domain_metrics",):
            print(f"  {k}: {v}")
    print("  DOMAIN:")
    for d in ["shop","gold","board","action","state"]:
        dm = r["domain_metrics"][d]
        acc_s = f"{dm['correct']/dm['total']:.1%}" if dm["total"] else "N/A"
        print(f"    {d:6s}: N={dm['total']} C={dm['correct']} W={dm['wrong']} ACC={acc_s}")


if __name__ == "__main__":
    main()
