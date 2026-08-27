#!/usr/bin/env python
"""TFT Runtime Evidence Auditor v2 - stdlib only, reads raw files.
Usage: python audit_runtime_evidence.py --session LIVE_20260827_001
       python audit_runtime_evidence.py --all
"""
import argparse, hashlib, json, os, sys, time

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "data", "vision_validation", "runtime_v2")
PII_KEYWORDS = ["puuid", "summonerid", "accountid", "gamename", "tagline"]


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def audit_session(session_dir):
    r = {
        "session_dir": session_dir,
        "audited_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "valid": 0, "invalid": 0, "missing_frames": 0, "missing_human_inputs": 0,
        "frame_hash_mismatches": [], "label_contamination": 0,
        "blind_order_violations": 0, "timestamp_inversions": 0,
        "domain_metrics": {d: {"correct":0,"wrong":0,"unknown":0,"total":0}
                           for d in ["shop","gold","board","action","state"]},
        "pii_found": [], "errors": [],
    }
    chk_dir = os.path.join(session_dir, "checkpoints")
    if not os.path.exists(chk_dir):
        r["errors"].append("MISSING_CHECKPOINTS_DIR")
        r["gate"] = "REAL_RUNTIME_UNVERIFIABLE"
        return r

    for fn in sorted(os.listdir(chk_dir)):
        if not fn.endswith(".json"):
            continue
        fp = os.path.join(chk_dir, fn)
        try:
            data = json.load(open(fp, encoding="utf-8"))
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

        # Blind order
        if review.get("blind_mode"):
            reveal_mono = review.get("reveal_monotonic")
            input_mono = hi.get("timestamp_monotonic")
            if reveal_mono and input_mono and input_mono >= reveal_mono:
                r["blind_order_violations"] += 1

        # Timestamp order
        cap_mono = cap.get("capture_monotonic", 0)
        pred_mono = (data.get("prediction") or {}).get("prediction_monotonic", 0)
        if pred_mono > 0 and pred_mono < cap_mono:
            r["timestamp_inversions"] += 1

        r["valid"] += 1

        # Domain metrics (independent counters)
        for domain, k in [("shop","shop_verdict"),("gold","gold_verdict"),
                          ("board","board_verdict"),("action","action_verdict"),("state","state_verdict")]:
            verdict = review.get(k, "UNKNOWN")
            r["domain_metrics"][domain]["total"] += 1
            if verdict == "CORRECT": r["domain_metrics"][domain]["correct"] += 1
            elif verdict == "WRONG": r["domain_metrics"][domain]["wrong"] += 1
            else: r["domain_metrics"][domain]["unknown"] += 1

    # PII scan
    for root, _, files in os.walk(session_dir):
        for fn2 in files:
            if not fn2.endswith((".json",".jsonl")): continue
            try:
                content = open(os.path.join(root, fn2), encoding="utf-8", errors="replace").read().lower()
                for kw in PII_KEYWORDS:
                    if kw in content:
                        r["pii_found"].append(f"{kw}:{fn2}")
            except Exception:
                pass

    # Independence check
    totals = [r["domain_metrics"][d]["total"] for d in ["shop","gold","board","action"]]
    corrects = [r["domain_metrics"][d]["correct"] for d in ["shop","gold","board","action"]]
    r["domain_metrics_independent"] = not (
        len(set(totals)) == 1 and len(set(corrects)) == 1 and (totals[0] if totals else 0) > 1
    )

    # Gate
    if r["label_contamination"] > 0:
        r["gate"] = "REAL_RUNTIME_BLOCKED"
    elif r["valid"] == 0:
        r["gate"] = "REAL_RUNTIME_UNVERIFIABLE"
    elif r["valid"] < 30:
        r["gate"] = "REAL_RUNTIME_PRELIMINARY"
    else:
        r["gate"] = "REAL_RUNTIME_CONFIRMED"
    return r


def print_audit(r, sid):
    print("=" * 60)
    print(f"EVIDENCE AUDIT: {sid}")
    print("=" * 60)
    for k in ["gate","valid","invalid","missing_frames","missing_human_inputs",
              "label_contamination","timestamp_inversions","domain_metrics_independent"]:
        print(f"  {k}: {r.get(k)}")
    print("  FRAME HASH MISMATCHES:", len(r.get("frame_hash_mismatches",[])))
    print("  PII FOUND:", len(r.get("pii_found",[])))
    print()
    print("  DOMAIN METRICS (independent denominators):")
    for d in ["shop","gold","board","action"]:
        dm = r["domain_metrics"][d]
        acc = f"{dm['correct']/dm['total']:.1%}" if dm["total"] else "N/A"
        print(f"    {d:6s}: N={dm['total']} C={dm['correct']} W={dm['wrong']} ACC={acc}")
    if r.get("errors"):
        print("  ERRORS:", r["errors"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--session", default=None)
    p.add_argument("--all", action="store_true")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    sessions_dir = os.path.join(OUTPUT_BASE, "sessions")
    if not os.path.exists(sessions_dir):
        print("No sessions directory. Run real_runtime_validator.py live first.")
        sys.exit(1)

    if args.all:
        sids = [s for s in os.listdir(sessions_dir) if os.path.isdir(os.path.join(sessions_dir, s))]
    elif args.session:
        sids = [args.session]
    else:
        sids = [s for s in os.listdir(sessions_dir) if os.path.isdir(os.path.join(sessions_dir, s))]

    all_r = {}
    for sid in sorted(sids):
        sdir = os.path.join(sessions_dir, sid)
        r = audit_session(sdir)
        print_audit(r, sid)
        all_r[sid] = r

    if not all_r:
        print("No sessions to audit.")
        return

    out_p = args.out or os.path.join(OUTPUT_BASE, "reports", "evidence_audit.json")
    os.makedirs(os.path.dirname(out_p), exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(all_r, f, indent=2, ensure_ascii=False)
    print(f"\nAudit report: {out_p}")


if __name__ == "__main__":
    main()
