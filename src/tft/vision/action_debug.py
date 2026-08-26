"""TFT Action Debug Gallery: Logs, exports, and visualizes False Positive and False Negative action cases."""
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ActionDebugCase:
    """개별 행동 검출 디버그 케이스."""
    case_id: str
    case_type: str  # "FALSE_POSITIVE" or "FALSE_NEGATIVE"
    timestamp_sec: float
    predicted_action: Optional[str]
    ground_truth_action: Optional[str]
    confidence: Optional[float]
    evidence: List[str]
    reason: str
    state_diff_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_type": self.case_type,
            "timestamp_sec": self.timestamp_sec,
            "predicted_action": self.predicted_action,
            "ground_truth_action": self.ground_truth_action,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "reason": self.reason,
            "state_diff_summary": self.state_diff_summary
        }


class ActionDebugGallery:
    """Action Detection 오류 사례 분석 갤러리 관리자."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.cases: List[ActionDebugCase] = []
        os.makedirs(self.output_dir, exist_ok=True)

    def add_case(
        self,
        case_type: str,
        timestamp_sec: float,
        predicted_action: Optional[str],
        ground_truth_action: Optional[str],
        confidence: Optional[float],
        evidence: List[str],
        reason: str,
        state_diff: Optional[Dict[str, Any]] = None
    ):
        """디버그 케이스 등록."""
        case_id = f"{case_type[:2].lower()}_{int(timestamp_sec)}_{len(self.cases) + 1}"
        case = ActionDebugCase(
            case_id=case_id,
            case_type=case_type,
            timestamp_sec=timestamp_sec,
            predicted_action=predicted_action,
            ground_truth_action=ground_truth_action,
            confidence=round(confidence, 3) if confidence is not None else None,
            evidence=evidence,
            reason=reason,
            state_diff_summary=state_diff or {}
        )
        self.cases.append(case)

    def save_gallery(self):
        """JSON 및 Markdown 리포트 내보내기."""
        json_path = os.path.join(self.output_dir, "action_debug_gallery.json")
        md_path = os.path.join(self.output_dir, "action_debug_gallery_report.md")

        fp_cases = [c for c in self.cases if c.case_type == "FALSE_POSITIVE"]
        fn_cases = [c for c in self.cases if c.case_type == "FALSE_NEGATIVE"]

        data = {
            "total_debug_cases": len(self.cases),
            "false_positive_count": len(fp_cases),
            "false_negative_count": len(fn_cases),
            "cases": [c.to_dict() for c in self.cases]
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        md = ["# 🎬 Action Detection Debug Gallery Report\n"]
        md.append(f"- **Total Diagnostic Cases**: `{len(self.cases)}` (FP: `{len(fp_cases)}`, FN: `{len(fn_cases)}`)\n")

        md.append("## 1. False Positive Cases (Spurious or Misclassified Actions)\n")
        md.append("| Case ID | Time | Predicted | Ground Truth | Confidence | Reason | Evidence |")
        md.append("|---|---|---|---|---|---|---|")
        for c in fp_cases[:25]:
            ev_str = "<br>".join(c.evidence[:2]) if c.evidence else "-"
            md.append(f"| `{c.case_id}` | `{c.timestamp_sec:.1f}s` | **{c.predicted_action}** | {c.ground_truth_action} | `{c.confidence}` | {c.reason} | {ev_str} |")

        md.append("\n## 2. False Negative Cases (Missed Player Actions)\n")
        md.append("| Case ID | Time | Ground Truth Action | Reason | Notes |")
        md.append("|---|---|---|---|---|")
        for c in fn_cases[:25]:
            md.append(f"| `{c.case_id}` | `{c.timestamp_sec:.1f}s` | **{c.ground_truth_action}** | {c.reason} | {c.evidence[0] if c.evidence else '-'} |")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
