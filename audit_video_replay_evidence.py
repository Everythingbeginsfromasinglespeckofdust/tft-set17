#!/usr/bin/env python
"""TFT Video Replay Evidence Auditor v1 — stdlib only, reads raw files.
Usage: python audit_video_replay_evidence.py --session <SESSION_ID>
       python audit_video_replay_evidence.py --all
"""
import argparse
import hashlib
import json
import os
import sys
import time

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "data", "vision_validation", "video_replay")


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def audit_session(session_dir):
    r = {
        "session_dir": session_dir,
        "audited_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "valid": 0, "invalid": 0, "missing_frames": 0, "missing_human_inputs": 0,
        "frame_hash_mismatches": [], "label_contamination": 0,
        "domain_metrics": {d: {"correct":0,"wrong":0,"unknown":0,"total":0}
                           for d in ["shop","gold","board","action","state"]},
        "pii_found": [], "errors": [],
    }

    chk_dir = os.path.join(session_dir, "checkpoints")
    if not os.path.exists(chk_dir):
        r["errors"].append("MISSING_CHECKPOINTS_DIR")
        r["gate"] = "VIDEO_REPLAY_UNVERIFIABLE"
        return r

    for fn in sorted(os.listdir(chk_dir)):
        if not fn.endswith(".json"):
            continue
        fp = os.path.join(chk_dir, fn)
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            r["errors"].append(f"READ_ERROR:{fn}:{e}")
            continue

        if data.get("state") != "VERIFIED":
            r["invalid"] += 1
            continue

        cap = data.get("capture") or {}
        frame_path = cap.get("frame_path", "")
        frame_hash = cap.get("frame_sha256", "")
        if not frame_path or not os.path.exists(frame_path):
            r["missing_frames"] += 1
            r["invalid"] += 1
            continue
        if sha256_file(frame_path) != frame_hash:
            r["frame_hash_mismatches"].append(fn)
            r["invalid"] += 1
            continue

        hi = data.get("human_input")
        if not hi:
            r["missing_human_inputs"] += 1
            r["invalid"] += 1
            continue

        review = data.get("review") or {}
        pred = data.get("prediction") or {}
        human_pref = review.get("human_preferred_action")
        final_action = pred.get("final_action")
        key = (hi.get("key_pressed") or "").upper()
        if human_pref and human_pref == final_action and key not in ("R","B","L","G"):
            r["label_contamination"] += 1

        r["valid"] += 1

        for domain, k in [("shop","shop_verdict"),("gold","gold_verdict"),
                          ("board","board_verdict"),("action","action_verdict"),("state","state_verdict")]:
            verdict = review.get(k, "UNKNOWN")
            r["domain_metrics"][domain]["total"] += 1
            if verdict == "CORRECT": r["domain_metrics"][domain]["correct"] += 1
            elif verdict == "WRONG": r["domain_metrics"][domain]["wrong"] += 1
            else: r["domain_metrics"][domain]["unknown"] += 1

    totals = [r["domain_metrics"][d]["total"] for d in ["shop","gold","board","action"]]
    corrects = [r["domain_metrics"][d]["correct"] for d in ["shop","gold","board","action"]]
    r["domain_metrics_independent"] = not (
        len(set(totals)) == 1 and len(set(corrects)) == 1 and (totals[0] if totals else 0) > 1
    )

    if r["label_contamination"] > 0:
        r["gate"] = "VIDEO_REPLAY_BLOCKED"
    elif r["valid"] == 0:
        r["gate"] = "VIDEO_REPLAY_UNVERIFIABLE"
    elif r["valid"] < 30:
        r["gate"] = "VIDEO_REPLAY_PRELIMINARY"
    else:
        r["gate"] = "VIDEO_REPLAY_CONFIRMED"

    return r


def print_audit(r, sid):
    print("=" * 60)
    print(f"VIDEO REPLAY EVIDENCE AUDIT: {sid}")
    print("=" * 60)
    print(f"  Gate:                   {r.get('gate')}")
    print(f"  Valid Checkpoints:      {r.get('valid')}")
    print(f"  Invalid Checkpoints:    {r.get('invalid')}")
    print(f"  Missing Frames:         {r.get('missing_frames')}")
    print(f"  Missing Human Inputs:   {r.get('missing_human_inputs')}")
    print(f"  Label Contamination:    {r.get('label_contamination')}")
    print(f"  Hash Mismatches:        {len(r.get('frame_hash_mismatches', []))}")
    print()
    print("  DOMAIN METRICS (independent):")
    for d in ["shop", "gold", "board", "action", "state"]:
        dm = r["domain_metrics"][d]
        acc = f"{dm['correct']/dm['total']:.1%}" if dm["total"] else "N/A"
        print(f"    {d:6s}: N={dm['total']} C={dm['correct']} W={dm['wrong']} ACC={acc}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--session", default=None)
    p.add_argument("--all", action="store_true")
    args = p.parse_args()

    sessions_dir = os.path.join(OUTPUT_BASE, "sessions")
    if not os.path.exists(sessions_dir):
        print("No video replay sessions directory found.")
        sys.exit(1)

    sids = [args.session] if args.session else sorted(os.listdir(sessions_dir))
    for sid in sids:
        sdir = os.path.join(sessions_dir, sid)
        if os.path.isdir(sdir):
            r = audit_session(sdir)
            print_audit(r, sid)


if __name__ == "__main__":
    main()
