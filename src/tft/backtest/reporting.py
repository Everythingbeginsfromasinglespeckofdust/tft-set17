"""TFT Backtest Report Generator (Markdown and JSON formats) -- v1.1."""
import json
import os
from dataclasses import asdict
from typing import Dict, Any
from tft.backtest.models import BacktestReport


class ReportGenerator:
    """Renders backtest results into JSON and 15-section Markdown reports."""

    @staticmethod
    def save_json(report: BacktestReport, output_path: str) -> None:
        """Save machine-readable JSON report."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, indent=2, ensure_ascii=False)

    @staticmethod
    def save_markdown(report: BacktestReport, output_path: str) -> None:
        """Generate human-readable 15-section Markdown comprehensive report."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        md = []
        md.append("# 📊 TFT Decision Engine Backtesting & Statistical Validity Report (v1.1)\n")

        # 1. Dataset Composition
        md.append("## 1. Dataset Composition\n")
        md.append(f"- **Total Evaluated Snapshots**: `{report.total_samples:,}`")
        md.append(f"- **Unique Matches**: `{report.total_matches:,}`")
        md.append(f"- **Unique Participants**: `{report.total_participants:,}`")
        md.append("- **Data Sources**:\n")
        for src, count in report.data_source_distribution.items():
            pct = count / max(1, report.total_samples)
            md.append(f"  - `{src}`: `{count:,}` samples (`{pct:.1%}`)")
        md.append("\n")

        # 2. Snapshot Type Distribution
        md.append("## 2. Snapshot Type Distribution\n")
        md.append("> ℹ️ **중요 원칙**: `ENDGAME_SNAPSHOT`은 탈락 시점 최종 상태이며 전략 평가의 모집단으로 사용하지 않습니다. `MIDGAME_DECISION_SNAPSHOT`만 의사결정 유효성 평가 대상입니다.\n")
        md.append("| Snapshot Type | Count | Percentage | Purpose |")
        md.append("|---|---|---|---|")
        for stype, count in report.snapshot_type_distribution.items():
            pct = count / max(1, report.total_samples)
            purpose = "Strategy Evaluation (Primary)" if "MIDGAME" in stype else "Descriptive / Integrity only (NOT strategy eval)"
            md.append(f"| **`{stype}`** | `{count:,}` | `{pct:.1%}` | {purpose} |")
        md.append("\n")

        # 3. Action Observation Coverage
        md.append("## 3. Action Observation Coverage\n")
        cov = report.action_observation_coverage
        if cov:
            md.append(f"- **Known Action Samples**: `{cov.known_action_samples:,}` / `{cov.total_samples:,}` (`{cov.coverage_rate:.1%}`)")
            md.append(f"- **Unknown Action Samples**: `{cov.unknown_action_samples:,}` / `{cov.total_samples:,}` (`{1.0 - cov.coverage_rate:.1%}`)")
            md.append("\n### Coverage by Snapshot Type\n")
            md.append("| Snapshot Type | Total Samples | Known Actions | Coverage Rate |")
            md.append("|---|---|---|---|")
            for stype, d in cov.by_snapshot_type.items():
                tot = d.get("total", 0)
                k = d.get("known", 0)
                r = k / max(1, tot)
                md.append(f"| **`{stype}`** | `{tot:,}` | `{k:,}` | `{r:.1%}` |")
        md.append("\n")

        # 4. Temporal Integrity
        md.append("## 4. Temporal Integrity (T0 <= T1+ Validation)\n")
        temp = report.temporal_integrity
        if temp:
            md.append(f"- **Timestamps Checked**: `{temp.total_checked:,}` samples")
            md.append(f"- **Temporal Violations (T0 > T1+)**: `{temp.violations}`")
            md.append(f"- **Uncalibrated Timestamps (Riot API)**: `{temp.unknown_timestamps:,}`")
            if temp.violations == 0:
                md.append("- **Status**: ✅ **PASSED** (모든 시계열 순방향 무결성 확인)")
        md.append("\n")

        # 5. Leakage Validation
        md.append("## 5. Leakage Validation\n")
        leak = report.leakage_validation
        if leak:
            md.append(f"- **Total Samples Inspected**: `{leak.total_checked:,}`")
            md.append(f"- **Placement in T0 State**: `{leak.placement_in_state}`")
            md.append(f"- **Endgame Samples in Midgame Report**: `{leak.endgame_in_midgame_report}`")
            if leak.leakage_detected == 0 and leak.endgame_in_midgame_report == 0:
                md.append("- **Status**: ✅ **ZERO LEAKAGE** (미래 정보 유입 0건)")
        md.append("\n")

        # 6. Midgame Descriptive Statistics
        md.append(f"## 6. Midgame Descriptive Statistics (n={report.midgame_count})\n")
        if report.midgame_count > 0:
            ms = report.midgame_statistics
            md.append(f"- **Evaluated Samples**: `{ms.get('count')}`")
            md.append(f"- **Samples with Final Placement**: `{ms.get('with_placement')}` (Avg Placement: `#{ms.get('avg_placement')}`, Top4: `{ms.get('top4_rate', 0.0):.1%}`)")
            md.append(f"- **Known Action Count**: `{ms.get('known_action_count')}`\n")
            
            md.append("### (1) By Stage (Midgame Only)\n")
            md.append("| Stage Tier | Samples | Avg Placement | Top 4 Rate | Agreement | Mean Score Gap |")
            md.append("|---|---|---|---|---|---|")
            for g in report.midgame_stratification_by_stage:
                avg_p = f"{g.avg_placement:.2f}" if g.avg_placement is not None else "-"
                top4 = f"{g.top4_rate:.1%}" if g.top4_rate is not None else "-"
                agr = f"{g.agreement_rate:.1%}" if g.agreement_rate is not None else "-"
                mgap = f"{g.mean_score_gap:.3f}" if g.mean_score_gap is not None else "-"
                md.append(f"| **{g.group_name}** | `{g.sample_count}` | `{avg_p}` | `{top4}` | `{agr}` | `{mgap}` |")
        else:
            md.append("- *No midgame decision samples in current slice.*")
        md.append("\n")

        # 7. Endgame Descriptive Statistics
        md.append(f"## 7. Endgame Descriptive Statistics (n={report.endgame_count})\n")
        md.append("> ⚠️ **알림**: 아래 수치는 탈락 시점의 기술통계(Descriptive)이며, Decision Engine의 성능 지표가 아닙니다.\n")
        if report.endgame_count > 0:
            es = report.endgame_statistics
            md.append(f"- **Total Endgame Snapshots**: `{es.get('count')}`")
            md.append(f"- **Average Final Placement**: `#{es.get('avg_placement')}`")
            md.append(f"- **Top 4 Rate**: `{es.get('top4_rate', 0.0):.1%}` (분모: `{es.get('with_placement')}`)\n")
            
            md.append("### (1) By Gold at Elimination\n")
            md.append("| Gold Tier | Samples | Avg Placement | Top 4 Rate | Mean Score Gap |")
            md.append("|---|---|---|---|---|")
            for g in report.endgame_stratification_by_gold:
                avg_p = f"{g.avg_placement:.2f}" if g.avg_placement is not None else "-"
                top4 = f"{g.top4_rate:.1%}" if g.top4_rate is not None else "-"
                mgap = f"{g.mean_score_gap:.3f}" if g.mean_score_gap is not None else "-"
                md.append(f"| **{g.group_name}** | `{g.sample_count}` | `{avg_p}` | `{top4}` | `{mgap}` |")
        md.append("\n")

        # 8. Recommendation Agreement
        md.append("## 8. Recommendation Agreement (Behavioral Comparison)\n")
        md.append("> ℹ️ **원칙**: Recommendation Agreement는 '프로그램이 인간의 플레이와 일치한 비율(Behavioral Agreement)'을 나타내며 전략적 우수성의 척도가 아닙니다. `human_policy != engine_policy`는 두 정책이 다름을 의미할 뿐입니다.\n")
        md.append(f"- **Overall Behavioral Agreement**: `{report.recommendation_agreement.get('OVERALL', 0.0):.1%}` (분모: `{report.action_observation_coverage.known_action_samples if report.action_observation_coverage else 0}` known action samples)\n")
        
        md.append("### Strategy Policy Distribution & Behavioral Agreement\n")
        md.append("| Strategy | Behavioral Agreement | % ROLL | % LEVEL_UP | % SAVE_GOLD | Sample Denominator |")
        md.append("|---|---|---|---|---|---|")
        for strat, m in report.baseline_comparisons.items():
            denom = m.get("agreement_denominator", "-")
            md.append(f"| **{strat}** | `{m['agreement_rate']:.1%}` | `{m['pct_roll']:.1%}` | `{m['pct_level_up']:.1%}` | `{m['pct_save_gold']:.1%}` | `{denom}` |")
        md.append("\n")

        # 9. Action Score Gap Diagnostics
        md.append("## 9. Action Score Gap Diagnostics (formerly: Decision Margin)\n")
        diag = report.score_gap_diagnostics
        if diag:
            md.append(f"> 💡 **정의**: `{diag.definition}`\n")
            md.append(f"- **Mean Score Gap in ENDGAME Snapshots**: `{diag.endgame_mean_gap if diag.endgame_mean_gap is not None else '-'}`")
            md.append(f"- **Mean Score Gap in MIDGAME Snapshots**: `{diag.midgame_mean_gap if diag.midgame_mean_gap is not None else '-'}`\n")
            
            md.append("### Score Gap Tiers & Snapshot Type Breakdown\n")
            md.append("| Score Gap Tier | Total Decisions | ENDGAME Count | MIDGAME Count | Avg Placement (Observed) | Top 4 Rate |")
            md.append("|---|---|---|---|---|---|")
            for gt in diag.gap_tiers:
                avg_p = f"{gt['avg_placement']:.2f}" if gt['avg_placement'] is not None else "-"
                top4 = f"{gt['top4_rate']:.1%}" if gt['top4_rate'] is not None else "-"
                md.append(f"| **{gt['tier']}** | `{gt['count']}` | `{gt['endgame_count']}` | `{gt['midgame_count']}` | `{avg_p}` | `{top4}` |")
            
            md.append(f"\n- **MIDGAME Correlation Analysis**: {diag.correlation_note}")
            if diag.midgame_pearson_gap_placement is not None:
                md.append(f"  - Pearson $r$(Score Gap, Placement): `{diag.midgame_pearson_gap_placement:+.3f}`")
                md.append(f"  - Spearman $\\rho$(Score Gap, Placement): `{diag.midgame_spearman_gap_placement:+.3f}`")
        md.append("\n")

        # 10. Simulation Accuracy
        md.append("## 10. Simulation Accuracy (Gold & State Prediction)\n")
        ga = report.gold_prediction_analysis
        if ga:
            md.append(f"- **Valid Pairs Evaluated**: `{ga.valid_pairs}`")
            md.append(f"- **Horizon = 0 Excluded (ENDGAME)**: `{ga.horizon_zero_excluded}`")
            md.append(f"- **Note**: {ga.note}\n")
            if ga.overall_mae is not None:
                md.append(f"- **Overall Gold MAE**: `{ga.overall_mae}G`")
                md.append(f"- **Overall Gold RMSE**: `{ga.overall_rmse}G`")
                md.append(f"- **Overall Gold Bias**: `{ga.overall_bias:+G}`")
        md.append("\n")

        # 11. Failure Diagnostics
        md.append(f"## 11. Failure Diagnostics (Total Detected: `{report.failure_cases_count}`)\n")
        md.append("> ℹ️ **알림**: Failure Case는 의사결정이 틀렸다는 '증명'이 아니라, 모델의 판단과 실제 결과 사이에 큰 격차가 있는 '진단용 레이블(Diagnostic Label)'입니다.\n")
        if report.failure_cases_sample:
            for idx, fc in enumerate(report.failure_cases_sample[:5], 1):
                md.append(f"### Case {idx}: [{fc.failure_category}] (`{fc.sample_id}`)")
                md.append(f"- **Description**: {fc.description}")
                md.append(f"- **State**: Stage `{fc.state_summary.get('stage')}`, Gold `{fc.state_summary.get('gold')}G`, Level `{fc.state_summary.get('level')}`, HP `{fc.state_summary.get('hp')}` (`{fc.snapshot_type}`)")
                md.append(f"- **Recommendation**: `{fc.recommended_action}` (Score Gap: `+{fc.action_score_gap:.3f}`)")
                md.append(f"- **Actual Outcome**: Action `{fc.actual_action}`, Final Placement `#{fc.actual_placement}`\n")
        else:
            md.append("- *No suspicious failure cases detected under configured thresholds.*")
        md.append("\n")

        # 12. Statistical Limitations
        md.append("## 12. Statistical Limitations\n")
        for limit in report.data_limitations:
            md.append(f"- ⚠️ {limit}")
        md.append("\n")

        # 13. What Can Be Concluded
        md.append("## 13. What Can Be Concluded (현재 데이터로 확인 가능한 사실)\n")
        for item in report.what_can_be_concluded:
            md.append(f"- ✅ {item}")
        md.append("\n")

        # 14. What Cannot Be Concluded
        md.append("## 14. What Cannot Be Concluded (현재 데이터로 결론내릴 수 없는 항목)\n")
        for item in report.what_cannot_be_concluded:
            md.append(f"- ❌ {item}")
        md.append("\n")

        # 15. Next Required Data
        md.append("## 15. Next Required Data (다음 Calibration에 필요한 최소 데이터 조건)\n")
        for item in report.next_required_data:
            md.append(f"- 🎯 {item}")
        md.append("\n")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
