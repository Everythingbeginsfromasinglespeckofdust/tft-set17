"""Shadow Mode File and JSONL Logger."""
import json
import os
from typing import Any, Dict, List
from tft.calibration.shadow.shadow_models import ShadowDecision


class ShadowLogger:
    """Streams and records shadow decisions, flip logs, and performance metrics."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.replay_dir = os.path.join(output_dir, "replay")
        self.live_dir = os.path.join(output_dir, "live")
        self.flips_dir = os.path.join(output_dir, "flips")
        self.val_dir = os.path.join(output_dir, "validation")
        self.human_review_dir = os.path.join(output_dir, "human_review")
        self.reports_dir = os.path.join(output_dir, "reports")

        for d in [
            self.output_dir,
            self.replay_dir,
            self.live_dir,
            self.flips_dir,
            self.val_dir,
            self.human_review_dir,
            self.reports_dir
        ]:
            os.makedirs(d, exist_ok=True)

    def log_decision(self, decision: ShadowDecision, mode: str = "replay"):
        target_dir = self.live_dir if mode == "live" else self.replay_dir
        path = os.path.join(target_dir, "shadow_decisions.jsonl" if mode == "live" else "comparison.jsonl")
        
        row = decision.__dict__
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

        if decision.is_flip:
            all_flips_p = os.path.join(self.flips_dir, "all_flips.jsonl")
            with open(all_flips_p, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

            if decision.risk_level == "HIGH_RISK":
                hr_p = os.path.join(self.flips_dir, "high_risk_flips.jsonl")
                with open(hr_p, "a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

                rev_p = os.path.join(self.human_review_dir, "review_queue.jsonl")
                with open(rev_p, "a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
