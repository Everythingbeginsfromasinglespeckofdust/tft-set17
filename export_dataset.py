"""TFT Decision Assistant Dataset Exporter CLI."""
import argparse
import glob
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SESSIONS_DIR = os.path.join(_HERE, "data", "decision_assistant", "sessions")
_DEFAULT_OUT = os.path.join(_HERE, "data", "decision_assistant", "exported_dataset.jsonl")


def main():
    parser = argparse.ArgumentParser(description="Export Decision Assistant Sessions to Backtest Dataset")
    parser.add_argument("--sessions-dir", type=str, default=_SESSIONS_DIR, help="Path to sessions directory")
    parser.add_argument("--output", type=str, default=_DEFAULT_OUT, help="Path to output JSONL file")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    records_count = 0

    print("=" * 80)
    print(f"📊 EXPORTING DATASET FROM: {args.sessions_dir}")
    print(f"   Target: {args.output}")
    print("=" * 80)

    with open(args.output, "w", encoding="utf-8") as out:
        for s_dir in glob.glob(os.path.join(args.sessions_dir, "*")):
            t_path = os.path.join(s_dir, "turns.jsonl")
            if os.path.exists(t_path):
                with open(t_path, "r", encoding="utf-8") as tf:
                    for line in tf:
                        if not line.strip():
                            continue
                        t_data = json.loads(line.strip())
                        export_row = {
                            "session_id": os.path.basename(s_dir),
                            "turn_id": t_data.get("turn_id"),
                            "stage_round": t_data.get("stage_round"),
                            "video_timestamp_sec": t_data.get("video_timestamp_sec"),
                            "state": t_data.get("state"),
                            "actual_action": t_data.get("actual_player_action", "UNKNOWN"),
                            "human_preference": t_data.get("human_preferred_action", "UNKNOWN"),
                            "engine_recommendation": t_data.get("decision", {}).get("recommended_action"),
                            "action_score_gap": t_data.get("decision", {}).get("action_score_gap"),
                            "score_breakdown": t_data.get("decision", {}).get("all_scores"),
                            "human_judgment": t_data.get("human_feedback", "UNKNOWN"),
                            "notes": t_data.get("notes", "")
                        }
                        out.write(json.dumps(export_row, ensure_ascii=False) + "\n")
                        records_count += 1

    print(f"[+] Total records exported: {records_count}")
    print(f"[+] Saved to: {os.path.abspath(args.output)}")


if __name__ == "__main__":
    main()
