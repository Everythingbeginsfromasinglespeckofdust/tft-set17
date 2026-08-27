"""Evidence Completeness Validator and Static Contamination Detector.

Checks:
- Each checkpoint has all required evidence
- No synthetic data patterns in REAL_LIVE records
- No label contamination (human label != prediction auto-copy)
- Domain metrics are computed INDEPENDENTLY (no shared boolean)
- Timestamp ordering is valid
"""
import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from tft.vision.runtime_v2.evidence_store import (
    EvidenceCheckpoint,
    CheckpointState,
    SourceType,
    DomainVerdict,
)

# Patterns that indicate synthetic/hardcoded data in source files
SYNTHETIC_PATTERNS = [
    r'for i in range\(\d+\)',
    r'gold = \d+ if i',
    r'is_wrong = \(i ==',
    r'human_preferred_action=dec_res\.action',
    r'human_label = prediction',
    r'label = expected',
    r'human = prediction',
    r'rotating_fixture',
    r'champs_pool.*%.*len',
    r'REAL_LIVE.*if.*LIVE.*in.*sess',
    r'shop_correct \+= 1.*\n.*gold_correct \+= 1',
]


class EvidenceAuditResult:
    def __init__(self):
        self.valid_checkpoint_count = 0
        self.invalid_checkpoint_count = 0
        self.missing_frame_count = 0
        self.missing_human_input_count = 0
        self.label_contamination_count = 0
        self.blind_order_violations = 0
        self.timestamp_inversions = 0
        self.synthetic_contamination_found: List[str] = []
        self.pii_found: List[str] = []
        # Domain metrics: each domain has its OWN denominator
        self.domain_metrics: Dict[str, Dict[str, int]] = {
            "shop":   {"correct": 0, "wrong": 0, "unknown": 0, "total": 0},
            "gold":   {"correct": 0, "wrong": 0, "unknown": 0, "total": 0},
            "board":  {"correct": 0, "wrong": 0, "unknown": 0, "total": 0},
            "action": {"correct": 0, "wrong": 0, "unknown": 0, "total": 0},
            "state":  {"correct": 0, "wrong": 0, "unknown": 0, "total": 0},
        }
        self.frame_hash_mismatches: List[str] = []
        self.errors: List[str] = []

    def _acc(self, domain: str) -> Optional[float]:
        d = self.domain_metrics[domain]
        return d["correct"] / d["total"] if d["total"] > 0 else None

    def shop_accuracy(self) -> Optional[float]:   return self._acc("shop")
    def gold_accuracy(self) -> Optional[float]:   return self._acc("gold")
    def board_accuracy(self) -> Optional[float]:  return self._acc("board")
    def action_accuracy(self) -> Optional[float]: return self._acc("action")

    def are_domain_metrics_independent(self) -> bool:
        """Verify that domain metrics are NOT all identical (sign of shared flag)."""
        accs = [self._acc(d) for d in ["shop", "gold", "board", "action"]]
        non_none = [a for a in accs if a is not None]
        if len(non_none) < 2:
            return True  # can't tell with only one domain
        # All identical AND total > 0 is suspicious
        totals = [self.domain_metrics[d]["total"] for d in ["shop", "gold", "board", "action"]]
        corrects = [self.domain_metrics[d]["correct"] for d in ["shop", "gold", "board", "action"]]
        # If all totals are equal AND all corrects are equal -> shared flag
        return not (len(set(totals)) == 1 and len(set(corrects)) == 1 and totals[0] > 1)

    def final_gate(self) -> str:
        if self.synthetic_contamination_found:
            return "REAL_RUNTIME_BLOCKED"
        if self.label_contamination_count > 0:
            return "REAL_RUNTIME_BLOCKED"
        if self.valid_checkpoint_count == 0:
            return "REAL_RUNTIME_UNVERIFIABLE"
        if self.valid_checkpoint_count < 30:
            return "REAL_RUNTIME_PRELIMINARY"
        return "REAL_RUNTIME_CONFIRMED"


class EvidenceValidator:
    """Validates evidence completeness and computes evidence-backed metrics."""

    def validate_checkpoint(self, chk: EvidenceCheckpoint):
        """Returns (valid: bool, issues: List[str])."""
        issues = []

        # Frame evidence
        if chk.capture is None:
            issues.append("MISSING_CAPTURE")
        elif not chk.capture.frame_path or not os.path.exists(chk.capture.frame_path):
            issues.append(f"MISSING_FRAME_FILE: {chk.capture.frame_path}")
        else:
            with open(chk.capture.frame_path, "rb") as f:
                actual_hash = hashlib.sha256(f.read()).hexdigest()
            if actual_hash != chk.capture.frame_sha256:
                issues.append(f"FRAME_HASH_MISMATCH: {chk.checkpoint_id}")

        # Prediction evidence
        if chk.prediction is None:
            issues.append("MISSING_PREDICTION")
        elif chk.prediction.vision_source != "REAL_FRAME":
            issues.append(f"NON_REAL_VISION_SOURCE: {chk.prediction.vision_source}")

        # Human input
        if chk.human_input is None:
            issues.append("MISSING_HUMAN_INPUT")
        else:
            if chk.review and chk.prediction:
                # Label contamination: preferred_action set without action key
                if (
                    chk.review.human_preferred_action is not None
                    and chk.review.human_preferred_action == chk.prediction.final_action
                    and chk.human_input.key_pressed.upper() not in ('R', 'B', 'L', 'G')
                ):
                    issues.append("LABEL_CONTAMINATION")

        # Blind order
        if chk.review and chk.review.blind_mode and chk.human_input:
            if not chk.review.blind_order_valid(chk.human_input):
                issues.append("BLIND_ORDER_VIOLATION")

        # Timestamp ordering
        if chk.capture and chk.prediction:
            if chk.prediction.prediction_monotonic < chk.capture.capture_monotonic:
                issues.append("TIMESTAMP_INVERSION: prediction before capture")

        return len(issues) == 0, issues

    def audit_session(self, session_dir: str) -> EvidenceAuditResult:
        result = EvidenceAuditResult()

        chk_dir = os.path.join(session_dir, "checkpoints")
        if not os.path.exists(chk_dir):
            result.errors.append(f"MISSING_CHECKPOINTS_DIR: {chk_dir}")
            return result

        for fn in sorted(os.listdir(chk_dir)):
            if not fn.endswith(".json"):
                continue
            fp = os.path.join(chk_dir, fn)
            try:
                with open(fp, encoding="utf-8") as f:
                    data = json.load(f)

                if data.get("state") != CheckpointState.VERIFIED.value:
                    result.invalid_checkpoint_count += 1
                    continue

                # Verify frame file exists and hash matches
                cap = data.get("capture") or {}
                frame_path = cap.get("frame_path", "")
                frame_hash = cap.get("frame_sha256", "")
                if not frame_path or not os.path.exists(frame_path):
                    result.missing_frame_count += 1
                    result.invalid_checkpoint_count += 1
                    continue
                with open(frame_path, "rb") as ff:
                    actual_hash = hashlib.sha256(ff.read()).hexdigest()
                if actual_hash != frame_hash:
                    result.frame_hash_mismatches.append(fn)
                    result.invalid_checkpoint_count += 1
                    continue

                # Verify human input file exists
                hi = data.get("human_input")
                if not hi:
                    result.missing_human_input_count += 1
                    result.invalid_checkpoint_count += 1
                    continue

                # Count as valid
                result.valid_checkpoint_count += 1

                # Accumulate domain metrics INDEPENDENTLY (each domain its own counter)
                review = data.get("review") or {}
                for domain, key in [
                    ("shop",   "shop_verdict"),
                    ("gold",   "gold_verdict"),
                    ("board",  "board_verdict"),
                    ("action", "action_verdict"),
                    ("state",  "state_verdict"),
                ]:
                    verdict = review.get(key, DomainVerdict.UNKNOWN.value)
                    result.domain_metrics[domain]["total"] += 1
                    if verdict == DomainVerdict.CORRECT.value:
                        result.domain_metrics[domain]["correct"] += 1
                    elif verdict == DomainVerdict.WRONG.value:
                        result.domain_metrics[domain]["wrong"] += 1
                    else:
                        result.domain_metrics[domain]["unknown"] += 1

            except Exception as e:
                result.errors.append(f"CHECKPOINT_READ_ERROR: {fn}: {e}")

        return result

    def scan_for_synthetic_patterns(self, source_file: str) -> List[str]:
        """Scan a source file for synthetic data generation patterns."""
        findings = []
        if not os.path.exists(source_file):
            return findings
        with open(source_file, encoding="utf-8", errors="replace") as f:
            content = f.read()
        for pattern in SYNTHETIC_PATTERNS:
            if re.search(pattern, content):
                findings.append(f"SYNTHETIC_PATTERN in {os.path.basename(source_file)}: {pattern}")
        return findings

    def scan_for_pii(self, directory: str) -> List[str]:
        pii_keywords = ["puuid", "summonerid", "accountid", "gamename", "tagline"]
        findings = []
        for root, _, files in os.walk(directory):
            for fn in files:
                if not fn.endswith((".json", ".jsonl")):
                    continue
                fp = os.path.join(root, fn)
                try:
                    with open(fp, encoding="utf-8", errors="replace") as f:
                        content = f.read().lower()
                    for kw in pii_keywords:
                        if kw in content:
                            findings.append(f"PII_KEYWORD '{kw}' in {fp}")
                except Exception:
                    pass
        return findings
