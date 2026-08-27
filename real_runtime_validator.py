"""
TFT Real Runtime Validator v2
Usage: python real_runtime_validator.py live [--session ID] [--max-checkpoints N]
       python real_runtime_validator.py status [--session ID]
NO synthetic fallback in REAL_LIVE mode.
"""
import argparse, json, os, subprocess, sys, time
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
OUTPUT_BASE = os.path.join(ROOT, "data", "vision_validation", "runtime_v2")

def _git_audit():
    groups = {"decision": ["src/tft/decision/"], "simulation": ["src/tft/simulation/"],
              "evaluation": ["src/tft/evaluation/"], "domain": ["src/tft/domain/"]}
    print("\n[GIT AUDIT]")
    for g, paths in groups.items():
        try:
            out = subprocess.check_output(["git","diff","--stat","--"]+paths, cwd=ROOT).decode().strip()
            print(f"  {g}: {out or chr(79)+chr(75)}")
        except Exception: pass

def cmd_live(args):
    from tft.vision.runtime_v2.session_runner import RuntimeSessionRunner
    from tft.vision.runtime_v2.evidence_store import SourceType
    sid = getattr(args, "session", None) or f"LIVE_{time.strftime('%Y%m%d_%H%M%S')}"
    print(f"[REAL_RUNTIME_V2] Starting LIVE session: {sid}")
    runner = RuntimeSessionRunner(output_base=OUTPUT_BASE, session_id=sid, source_type=SourceType.REAL_LIVE)
    mc = getattr(args, "max_checkpoints", 50)
    to = getattr(args, "timeout", 60.0)
    result = runner.run_real_live(max_checkpoints=mc, timeout_per_checkpoint=to)
    print(f"[RESULT] Gate: {result.get('gate')}")
    print(f"[RESULT] Valid: {result.get('valid_checkpoints', 0)}")
    _git_audit()
    return result

def cmd_status(args):
    sid = getattr(args, "session", None)
    sd = os.path.join(OUTPUT_BASE, "sessions")
    if not os.path.exists(sd):
        print("No sessions found."); return
    sessions = [sid] if sid else sorted(os.listdir(sd))
    for s in sessions:
        sp = os.path.join(sd, s)
        chk_d = os.path.join(sp, "checkpoints")
        verified = len([f for f in os.listdir(chk_d) if f.endswith(".json") and "INVALID" not in f]) if os.path.exists(chk_d) else 0
        frames = len(os.listdir(os.path.join(sp,"raw_frames"))) if os.path.exists(os.path.join(sp,"raw_frames")) else 0
        human = len(os.listdir(os.path.join(sp,"human_inputs"))) if os.path.exists(os.path.join(sp,"human_inputs")) else 0
        print(f"  {s}: verified={verified} frames={frames} human_inputs={human}")

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    lv = sub.add_parser("live")
    lv.add_argument("--session", default=None)
    lv.add_argument("--max-checkpoints", type=int, default=50, dest="max_checkpoints")
    lv.add_argument("--timeout", type=float, default=60.0)
    st = sub.add_parser("status")
    st.add_argument("--session", default=None)
    args = p.parse_args()
    if args.cmd == "live": cmd_live(args)
    elif args.cmd == "status": cmd_status(args)
    else: cmd_status(args)

if __name__ == "__main__": main()