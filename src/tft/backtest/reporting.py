"""TFT Backtest Report Generator (Markdown and JSON formats)."""
import json
import os
from dataclasses import asdict
from typing import Dict, Any
from tft.backtest.models import BacktestReport

class ReportGenerator:
    """백테스트 결과를 JSON 및 Markdown 형식의 보고서로 렌더링."""

    @staticmethod
    def save_json(report: BacktestReport, output_path: str) -> None:
        """기계 판독용 JSON 보고서 저장."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, indent=2, ensure_ascii=False)

    @staticmethod
    def save_markdown(report: BacktestReport, output_path: str) -> None:
        """인간 친화적 Markdown 종합 보고서 생성."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        md = []
        md.append("# 📊 TFT Decision Engine Backtesting & Calibration Report\n")
        
        # 1. Overview Summary
        md.append("## 1. Executive Summary\n")
        md.append(f"- **Total Evaluated Snapshots**: `{report.total_samples:,}`")
        md.append(f"- **Unique Matches**: `{report.total_matches:,}`")
        md.append(f"- **Unique Participants**: `{report.total_participants:,}`")
        md.append(f"- **Data Sources**: " + ", ".join(f"`{k}: {v}`" for k, v in report.data_source_distribution.items()))
        md.append(f"- **Observed Action Coverage**: `{report.coverage:.1%}` (Unknown Action Rate: `{report.unknown_action_rate:.1%}`)\n")

        # 2. Behavioral Agreement & Confusion Matrix
        md.append("## 2. Behavioral Agreement Analysis (Observed vs Recommended)\n")
        md.append("> ⚠️ **주의**: Recommendation Agreement는 '프로그램이 인간의 플레이를 모방한 일치율(Behavioral Agreement)'이며, 전략적 우수성의 척도가 아닙니다.\n")
        md.append("| Action Type | Agreement Rate | Sample Count |")
        md.append("|---|---|---|")
        for act, rate in report.recommendation_agreement.items():
            md.append(f"| **{act}** | `{rate:.1%}` | - |")
        md.append("\n### Action Confusion Matrix (Actual vs Recommended)\n")
        md.append("| Actual \\ Predicted | ROLL | LEVEL_UP | SAVE_GOLD |")
        md.append("|---|---|---|---|")
        for actual, row in report.action_confusion_matrix.items():
            md.append(f"| **{actual}** | `{row.get('ROLL', 0)}` | `{row.get('LEVEL_UP', 0)}` | `{row.get('SAVE_GOLD', 0)}` |")
        md.append("\n")

        # 3. Baseline Strategy Comparison
        md.append("## 3. Baseline Strategy Comparison\n")
        md.append("| Strategy | Agreement Rate | % ROLL | % LEVEL_UP | % SAVE_GOLD |")
        md.append("|---|---|---|---|---|")
        for strat, m in report.baseline_comparisons.items():
            md.append(f"| **{strat}** | `{m['agreement_rate']:.1%}` | `{m['pct_roll']:.1%}` | `{m['pct_level_up']:.1%}` | `{m['pct_save_gold']:.1%}` |")
        md.append("\n")

        # 4. Stratified Outcome Analysis
        md.append("## 4. Stratified Outcome Analysis (By Game State)\n")
        
        md.append("### (1) By Health (HP) Tier\n")
        md.append("| Health Tier | Samples | Avg Placement | Top 4 Rate | Agreement |")
        md.append("|---|---|---|---|---|")
        for g in report.stratification_by_hp:
            avg_p = f"{g.avg_placement:.2f}" if g.avg_placement is not None else "-"
            top4 = f"{g.top4_rate:.1%}" if g.top4_rate is not None else "-"
            agr = f"{g.agreement_rate:.1%}" if g.agreement_rate is not None else "-"
            md.append(f"| **{g.group_name}** | `{g.sample_count}` | `{avg_p}` | `{top4}` | `{agr}` |")

        md.append("\n### (2) By Gold Tier\n")
        md.append("| Gold Tier | Samples | Avg Placement | Top 4 Rate | Agreement |")
        md.append("|---|---|---|---|---|")
        for g in report.stratification_by_gold:
            avg_p = f"{g.avg_placement:.2f}" if g.avg_placement is not None else "-"
            top4 = f"{g.top4_rate:.1%}" if g.top4_rate is not None else "-"
            agr = f"{g.agreement_rate:.1%}" if g.agreement_rate is not None else "-"
            md.append(f"| **{g.group_name}** | `{g.sample_count}` | `{avg_p}` | `{top4}` | `{agr}` |")

        md.append("\n### (3) By Level\n")
        md.append("| Level Tier | Samples | Avg Placement | Top 4 Rate | Agreement |")
        md.append("|---|---|---|---|---|")
        for g in report.stratification_by_level:
            avg_p = f"{g.avg_placement:.2f}" if g.avg_placement is not None else "-"
            top4 = f"{g.top4_rate:.1%}" if g.top4_rate is not None else "-"
            agr = f"{g.agreement_rate:.1%}" if g.agreement_rate is not None else "-"
            md.append(f"| **{g.group_name}** | `{g.sample_count}` | `{avg_p}` | `{top4}` | `{agr}` |")
        md.append("\n")

        # 5. Decision Margin Analysis
        md.append("## 5. Decision Margin Analysis (Confidence vs Stability)\n")
        md.append("| Margin Tier | Decisions | Distribution | Avg Placement | Top 4 Rate | Agreement |")
        md.append("|---|---|---|---|---|---|")
        for mt in report.margin_tier_analysis:
            avg_p = f"{mt['avg_placement']:.2f}" if mt['avg_placement'] is not None else "-"
            top4 = f"{mt['top4_rate']:.1%}" if mt['top4_rate'] is not None else "-"
            agr = f"{mt['agreement_rate']:.1%}" if mt['agreement_rate'] is not None else "-"
            md.append(f"| **{mt['tier_name']}** | `{mt['count']}` | `{mt['percentage']:.1%}` | `{avg_p}` | `{top4}` | `{agr}` |")
        md.append("\n")

        # 6. Simulation Prediction Errors
        md.append("## 6. Simulation Prediction Errors (Observable Metrics)\n")
        se = report.simulation_errors
        if se.get("sample_size", 0) > 0:
            md.append(f"- **Gold Prediction MAE**: `{se.get('gold_prediction_mae')}G`")
            md.append(f"- **Gold Prediction RMSE**: `{se.get('gold_prediction_rmse')}G`")
            md.append(f"- **Gold Prediction Mean Error**: `{se.get('gold_prediction_mean_error'):+G}`")
        else:
            md.append("- *No multi-round intermediate gold labels available in current endpoint.*")
        md.append("\n")

        # 7. Failure Cases
        md.append(f"## 7. Failure Case Analysis (Total Detected: `{report.failure_cases_count}`)\n")
        for idx, fc in enumerate(report.failure_cases_sample[:5], 1):
            md.append(f"### Case {idx}: [{fc.failure_type}] ({fc.sample_id})")
            md.append(f"- **Description**: {fc.description}")
            md.append(f"- **State**: Stage `{fc.state_summary.get('stage')}`, Gold `{fc.state_summary.get('gold')}G`, Level `{fc.state_summary.get('level')}`, HP `{fc.state_summary.get('hp')}`")
            md.append(f"- **Recommendation**: `{fc.recommended_action}` (Margin: `+{fc.decision_margin:.3f}`)")
            md.append(f"- **Actual Action & Placement**: Action `{fc.actual_action}`, Final Placement `#{fc.actual_placement}`\n")

        # 8. Data Limitations
        md.append("## 8. Data Limitations & Next Steps\n")
        for limit in report.data_limitations:
            md.append(f"- ℹ️ {limit}")
        md.append("\n")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
