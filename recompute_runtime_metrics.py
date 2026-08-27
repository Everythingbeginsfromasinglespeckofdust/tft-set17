#!/usr/bin/env python
"""TFT Runtime Metrics Recomputer v2 - reads raw evidence only.
Usage: python recompute_runtime_metrics.py --session LIVE_20260827_001
"""
import argparse, hashlib, json, os, sys, time

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "data", "vision_validation", "runtime_v2")


def sha256_file(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def recompute(session_dir):
    chk_dir = os.path.join(session_dir, "checkpoints")
    frame_dir = os.path.join(session_dir, "raw_frames")
    human_dir = os.path.join(session_dir, "human_inputs")
    pred_dir = os.path.join(session_dir, "predictions")

    frames_on_disk = len([f for f in os.listdir(frame_dir) if f.endswith(".png")]) \
        if os.path.exists(frame_dir) else 0
    human_on_disk = len(os.listdir(human_dir)) if os.path.exists(human_dir) else 0
    preds_on_disk = len(os.listdir(pred_dir)) if os.path.exists(pred_dir) else 0

    dm = {d: {"correct":0,"wrong":0,"unknown":0,"total":0}
          for d in ["shop","gold","board","action","state"]}
    lats = []
    valid = invalid = missing_frames = hash_mm = label_contamination = 0

    if not os.path.exists(chk_dir):
        return {"error":"MISSING_CHECKPOINTS_DIR"}

    for fn in sorted(os.listdir(chk_dir)):
        if not fn.endswith(".json"): continue
        data = json.load(open(os.path.join(chk_dir, fn), encoding="utf-8"))
        if data.get("state") != "VERIFIED":
            invalid += 1; continue
        cap = data.get("capture") or {}
        fp = cap.get("frame_path", "")
        if not fp or not os.path.exists(fp):
            missing_frames += 1; invalid += 1; continue
        if sha256_file(fp) != cap.get("frame_sha256",""):
            hash_mm += 1; invalid += 1; continue
        hi = data.get("human_input")
        if not hi:
            invalid += 1; continue
        pred = data.get("prediction") or {}
        review = data.get("review") or {}
        # Label contamination (independent check)
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
        t_cap = cap.get("capture_monotonic", 0)
        t_pred = pred.get("prediction_monotonic", 0)
        if t_pred > 0 and t_cap > 0:
            lats.append(t_pred - t_cap)

    lat_stats = {}
    if lats:
        lats.sort(); n = len(lats)
        lat_stats = {"mean": sum(lats)/n, "median": lats[n//2],
                     "p95": lats[int(n*0.95)], "max": lats[-1], "count": n}

    def acc(d):
        return dm[d]["correct"]/dm[d]["total"] if dm[d]["total"] else None

    totals = [dm[d]["total"] for d in ["shop","gold","board","action"]]
    corrects = [dm[d]["correct"] for d in ["shop","gold","board","action"]]
    all_same = len(set(totals))==1 and len(set(corrects))==1 and (totals[0] if totals else 0)>1

    gate = ("REAL_RUNTIME_BLOCKED" if label_contamination > 0 else
            "REAL_RUNTIME_UNVERIFIABLE" if valid == 0 else
            "REAL_RUNTIME_PRELIMINARY" if valid < 30 else
            "REAL_RUNTIME_CONFIRMED")

    return {
        "recomputed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "frames_on_disk": frames_on_disk, "human_inputs_on_disk": human_on_disk,
        "predictions_on_disk": preds_on_disk,
        "valid_checkpoints": valid, "invalid_checkpoints": invalid,
        "missing_frames": missing_frames, "frame_hash_mismatches": hash_mm,
        "label_contamination": label_contamination,
        "shop_accuracy": acc("shop"), "gold_accuracy": acc("gold"),
        "board_accuracy": acc("board"), "action_accuracy": acc("action"),
        "domain_metrics_independent": not all_same,
        "domain_metrics": dm, "latency_stats": lat_stats, "gate": gate,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--session", required=True)
    p.add_argument("--out", default=None)
    args = p.parse_args()
    sdir = os.path.join(OUTPUT_BASE, "sessions", args.session)
    if not os.path.exists(sdir):
        print(f"Session not found: {sdir}"); sys.exit(1)
    r = recompute(sdir)
    print("=" * 60)
    print(f"RECOMPUTED METRICS: {args.session}")
    print("=" * 60)
    for k, v in r.items():
        if k not in ("domain_metrics","latency_stats"):
            print(f"  {k}: {v}")
    print("  DOMAIN:")
    for d in ["shop","gold","board","action"]:
        dm = r["domain_metrics"][d]
        acc = f"{dm['correct']/dm['total']:.1%}" if dm["total"] else "N/A"
        print(f"    {d}: N={dm['total']} C={dm['correct']} W={dm['wrong']} ACC={acc}")
    out_p = args.out or os.path.join(OUTPUT_BASE, "reports", f"{args.session}_recomputed.json")
    os.makedirs(os.path.dirname(out_p), exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2)
    print(f"\nReport: {out_p}")


if __name__ == "__main__":
    main()
