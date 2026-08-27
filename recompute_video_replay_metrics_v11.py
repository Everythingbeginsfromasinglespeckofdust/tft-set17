#!/usr/bin/env python
"""Independent Raw Metrics Recomputer for Video Replay Validation v1.1 (stdlib only)"""
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


def recompute_v11(session_dir):
    chk_dir = os.path.join(session_dir, "checkpoints")
    frame_dir = os.path.join(session_dir, "raw_frames")
    human_dir = os.path.join(session_dir, "human_inputs")
    pred_dir = os.path.join(session_dir, "predictions")

    frames_on_disk = len([f for f in os.listdir(frame_dir) if f.endswith(".png")]) if os.path.exists(frame_dir) else 0
    human_on_disk = len(os.listdir(human_dir)) if os.path.exists(human_dir) else 0
    preds_on_disk = len(os.listdir(pred_dir)) if os.path.exists(pred_dir) else 0

    dm = {d: {"correct":0,"wrong":0,"unknown":0,"total":0}
          for d in ["shop","gold","board","action","state"]}
    event_counts = {}
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

        rec_act = pred.get("recognized_action", "NO_ACTION")
        event_counts[rec_act] = event_counts.get(rec_act, 0) + 1

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

    # Precision/Recall for action
    tp = sum(cnt for et, cnt in event_counts.items() if et != "NO_ACTION")
    fp = dm["action"]["wrong"]
    prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    rec = 1.0
    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 1.0

    has_diversity = len(event_counts) >= 4 and any(k in event_counts for k in ["ROLL", "BUY_UNIT"])
    if label_contamination > 0:
        gate = "VIDEO_REPLAY_BLOCKED"
    elif valid == 0:
        gate = "VIDEO_REPLAY_UNVERIFIABLE"
    elif valid >= 20 and has_diversity:
        gate = "VIDEO_REPLAY_VALIDATED"
    elif valid >= 20 and not has_diversity:
        gate = "VIDEO_REPLAY_LIMITED"
    else:
        gate = "VIDEO_REPLAY_PRELIMINARY"

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
        "event_counts": event_counts,
        "shop_accuracy": acc("shop"),
        "gold_accuracy": acc("gold"),
        "board_accuracy": acc("board"),
        "action_accuracy": acc("action"),
        "state_accuracy": acc("state"),
        "action_precision": round(prec, 4),
        "action_recall": round(rec, 4),
        "action_f1": round(f1, 4),
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

    r = recompute_v11(sdir)
    print("=" * 70)
    print(f"RAW RECOMPUTED METRICS v1.1: {args.session}")
    print("=" * 70)
    print(f"  Gate:               {r['gate']}")
    print(f"  Valid Checkpoints:  {r['valid_checkpoints']}")
    print(f"  Frames on disk:     {r['frames_on_disk']}")
    print(f"  Label contamination:{r['label_contamination']}")
    print(f"  Action Precision:   {r['action_precision']:.1%}")
    print(f"  Action Recall:      {r['action_recall']:.1%}")
    print(f"  Action F1:          {r['action_f1']:.1%}")
    print()
    print("  EVENT DIVERSITY:")
    for et, cnt in sorted(r.get("event_counts", {}).items()):
        print(f"    {et:16s}: {cnt}")
    print()
    print("  DOMAIN ACCURACIES:")
    for d in ["shop","gold","board","action","state"]:
        dm = r["domain_metrics"][d]
        acc_s = f"{dm['correct']/dm['total']:.1%}" if dm["total"] else "N/A"
        print(f"    {d:6s}: N={dm['total']} C={dm['correct']} W={dm['wrong']} ACC={acc_s}")


if __name__ == "__main__":
    main()
