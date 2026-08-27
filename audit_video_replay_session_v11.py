#!/usr/bin/env python
"""Independent Evidence Auditor for Video Replay Validation v1.1 (stdlib only)"""
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


def audit_session_v11(session_dir):
    r = {
        "session_dir": session_dir,
        "audited_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "valid": 0, "invalid": 0, "missing_frames": 0, "missing_human_inputs": 0,
        "frame_hash_mismatches": [], "label_contamination": 0,
        "blind_order_violations": 0, "timestamp_inversions": 0,
        "event_counts": {}, "stage_counts": {},
        "domain_metrics": {d: {"correct":0,"wrong":0,"unknown":0,"total":0}
                           for d in ["shop","gold","board","action","state"]},
        "errors": [],
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

        # Frame check
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

        # Human input check
        hi = data.get("human_input")
        if not hi:
            r["missing_human_inputs"] += 1
            r["invalid"] += 1
            continue

        # Label contamination check
        review = data.get("review") or {}
        pred = data.get("prediction") or {}
        human_pref = review.get("human_preferred_action")
        final_action = pred.get("final_action")
        key = (hi.get("key_pressed") or "").upper()
        if human_pref and human_pref == final_action and key not in ("R","B","L","G"):
            r["label_contamination"] += 1

        # Blind order check
        if review.get("blind_mode"):
            reveal_mono = review.get("prediction_reveal_monotonic")
            input_mono = hi.get("timestamp_monotonic")
            if reveal_mono and input_mono and input_mono >= reveal_mono:
                r["blind_order_violations"] += 1

        # Event & stage tally
        rec_action = pred.get("recognized_action", "NO_ACTION")
        r["event_counts"][rec_action] = r["event_counts"].get(rec_action, 0) + 1
        rec_stage = pred.get("recognized_stage", "UNKNOWN")
        r["stage_counts"][rec_stage] = r["stage_counts"].get(rec_stage, 0) + 1

        r["valid"] += 1

        # Domain metrics
        for domain, k in [("shop","shop_verdict"),("gold","gold_verdict"),
                          ("board","board_verdict"),("action","action_verdict"),("state","state_verdict")]:
            verdict = review.get(k, "UNKNOWN")
            r["domain_metrics"][domain]["total"] += 1
            if verdict == "CORRECT": r["domain_metrics"][domain]["correct"] += 1
            elif verdict == "WRONG": r["domain_metrics"][domain]["wrong"] += 1
            else: r["domain_metrics"][domain]["unknown"] += 1

    # Gate determination
    n_val = r["valid"]
    has_diversity = len(r["event_counts"]) >= 4 and any(k in r["event_counts"] for k in ["ROLL", "BUY_UNIT"])
    if r["label_contamination"] > 0:
        r["gate"] = "VIDEO_REPLAY_BLOCKED"
    elif n_val == 0:
        r["gate"] = "VIDEO_REPLAY_UNVERIFIABLE"
    elif n_val >= 20 and has_diversity:
        r["gate"] = "VIDEO_REPLAY_VALIDATED"
    elif n_val >= 20 and not has_diversity:
        r["gate"] = "VIDEO_REPLAY_LIMITED"
    else:
        r["gate"] = "VIDEO_REPLAY_PRELIMINARY"

    return r


def print_audit_v11(r, sid):
    print("=" * 70)
    print(f"AUDIT v1.1: {sid}")
    print("=" * 70)
    print(f"  Gate Verdict:           {r.get('gate')}")
    print(f"  Valid Checkpoints:      {r.get('valid')}")
    print(f"  Invalid Checkpoints:    {r.get('invalid')}")
    print(f"  Missing Frames:         {r.get('missing_frames')}")
    print(f"  Missing Inputs:         {r.get('missing_human_inputs')}")
    print(f"  Label Contamination:    {r.get('label_contamination')}")
    print(f"  Blind Violations:       {r.get('blind_order_violations')}")
    print(f"  Hash Mismatches:        {len(r.get('frame_hash_mismatches', []))}")
    print()
    print("  EVENT DIVERSITY:")
    for et, cnt in sorted(r.get("event_counts", {}).items()):
        print(f"    {et:16s}: {cnt}")
    print()
    print("  DOMAIN METRICS:")
    for d in ["shop", "gold", "board", "action", "state"]:
        dm = r["domain_metrics"][d]
        acc = f"{dm['correct']/dm['total']:.1%}" if dm["total"] else "N/A"
        print(f"    {d:6s}: N={dm['total']} C={dm['correct']} W={dm['wrong']} ACC={acc}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--session", default=None)
    args = p.parse_args()

    sessions_dir = os.path.join(OUTPUT_BASE, "sessions")
    sids = [args.session] if args.session else sorted(os.listdir(sessions_dir))
    for sid in sids:
        sdir = os.path.join(sessions_dir, sid)
        if os.path.isdir(sdir):
            r = audit_session_v11(sdir)
            print_audit_v11(r, sid)


if __name__ == "__main__":
    main()
