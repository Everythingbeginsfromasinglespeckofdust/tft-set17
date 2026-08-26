"""Generate 5 Diagnostic Visualization Plots for TFT Backtest v1.1."""
import os
from typing import List, Dict, Any
from tft.backtest.models import BacktestSample, BacktestDecision, BacktestReport, SnapshotType


def generate_all_plots(
    samples: List[BacktestSample],
    decisions: List[BacktestDecision],
    report: BacktestReport,
    output_dir: str
) -> List[str]:
    """Generates 5 visualization charts saved as PNG."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[!] matplotlib not installed. Skipping plot generation.")
        return []

    os.makedirs(output_dir, exist_ok=True)
    generated = []
    dec_map = {d.sample_id: d for d in decisions}
    sample_map = {s.sample_id: s for s in samples}

    # Graph 1: Decision Margin (Score Gap) vs Final Placement
    try:
        fig, ax = plt.subplots(figsize=(8, 5))
        endgame_gaps, endgame_placements = [], []
        midgame_gaps, midgame_placements = [], []

        for d in decisions:
            s = sample_map.get(d.sample_id)
            if s and s.future_observation.final_placement is not None:
                p = s.future_observation.final_placement
                g = d.action_score_gap
                if s.snapshot_type == SnapshotType.ENDGAME_SNAPSHOT:
                    endgame_gaps.append(g)
                    endgame_placements.append(p)
                else:
                    midgame_gaps.append(g)
                    midgame_placements.append(p)

        if endgame_gaps:
            ax.scatter(endgame_gaps, endgame_placements, color="salmon", alpha=0.5, label=f"ENDGAME (n={len(endgame_gaps)})")
        if midgame_gaps:
            ax.scatter(midgame_gaps, midgame_placements, color="royalblue", alpha=0.7, s=50, label=f"MIDGAME (n={len(midgame_gaps)})")

        ax.set_xlabel("Action Score Gap (Best - 2nd Score)")
        ax.set_ylabel("Final Placement (1 = 1st, 8 = 8th)")
        ax.set_title("Graph 1: Action Score Gap vs Final Placement")
        ax.invert_yaxis()
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.5)

        p1 = os.path.join(output_dir, "margin_vs_placement.png")
        fig.tight_layout()
        fig.savefig(p1, dpi=150)
        plt.close(fig)
        generated.append(p1)
    except Exception as e:
        print(f"[!] Error generating plot 1: {e}")

    # Graph 2: Decision Margin vs Top 4 Rate
    try:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        tiers = report.score_gap_diagnostics.gap_tiers if report.score_gap_diagnostics else []
        tier_names = [t["tier"] for t in tiers]
        top4_rates = [t.get("top4_rate", 0.0) or 0.0 for t in tiers]
        counts = [t.get("count", 0) for t in tiers]

        x = range(len(tier_names))
        bars = ax.bar(x, top4_rates, color="teal", alpha=0.7, edgecolor="black")
        ax.set_xticks(x)
        ax.set_xticklabels([f"{name}\n(n={c})" for name, c in zip(tier_names, counts)], rotation=15)
        ax.set_ylabel("Top 4 Rate")
        ax.set_ylim(0, 1.1)
        ax.set_title("Graph 2: Action Score Gap Tiers vs Top 4 Rate")
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.02, f"{h:.1%}", ha="center", va="bottom", fontsize=9)
        ax.grid(True, axis="y", linestyle="--", alpha=0.5)

        p2 = os.path.join(output_dir, "margin_vs_top4.png")
        fig.tight_layout()
        fig.savefig(p2, dpi=150)
        plt.close(fig)
        generated.append(p2)
    except Exception as e:
        print(f"[!] Error generating plot 2: {e}")

    # Graph 3: HP vs Placement
    try:
        fig, ax = plt.subplots(figsize=(8, 5))
        hps, placements = [], []
        for s in samples:
            if s.future_observation.final_placement is not None:
                hps.append(s.observed_state.state.player.hp)
                placements.append(s.future_observation.final_placement)

        ax.scatter(hps, placements, color="purple", alpha=0.4, label=f"All Samples (n={len(hps)})")
        ax.set_xlabel("T0 Player HP")
        ax.set_ylabel("Final Placement")
        ax.set_title("Graph 3: Player HP vs Final Placement (Descriptive)")
        ax.invert_yaxis()
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.5)

        p3 = os.path.join(output_dir, "hp_vs_placement.png")
        fig.tight_layout()
        fig.savefig(p3, dpi=150)
        plt.close(fig)
        generated.append(p3)
    except Exception as e:
        print(f"[!] Error generating plot 3: {e}")

    # Graph 4: Score Gap distribution by Stage
    try:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        stages = [2, 3, 4, 5, 6]
        stage_labels = ["Stage 2", "Stage 3", "Stage 4", "Stage 5", "Stage 6+"]
        data_by_stage = []
        for stg in stages:
            if stg == 6:
                subset = [d.action_score_gap for d in decisions if sample_map.get(d.sample_id) and sample_map[d.sample_id].observed_state.stage >= 6]
            else:
                subset = [d.action_score_gap for d in decisions if sample_map.get(d.sample_id) and sample_map[d.sample_id].observed_state.stage == stg]
            data_by_stage.append(subset if subset else [0.0])

        try:
            ax.boxplot(data_by_stage, tick_labels=stage_labels)
        except Exception:
            ax.boxplot(data_by_stage, labels=stage_labels)
        ax.set_ylabel("Action Score Gap")
        ax.set_title("Graph 4: Action Score Gap Distribution by Stage")
        ax.grid(True, linestyle="--", alpha=0.5)

        p4 = os.path.join(output_dir, "margin_by_stage.png")
        fig.tight_layout()
        fig.savefig(p4, dpi=150)
        plt.close(fig)
        generated.append(p4)
    except Exception as e:
        print(f"[!] Error generating plot 4: {e}")

    # Graph 5: Gold Prediction Error distribution
    try:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        gold_errors = []
        for s in samples:
            if (s.horizon_rounds or 0) > 0 and s.observed_state.actual_action.value != "UNKNOWN":
                d = dec_map.get(s.sample_id)
                if d:
                    rec_act = d.recommended_action.value
                    pred = d.simulated_expectations.get(rec_act, {}).get("expected_gold")
                    actual = s.future_observation.gold_after_n_rounds
                    if pred is not None and actual is not None:
                        gold_errors.append(pred - actual)

        if gold_errors:
            ax.hist(gold_errors, bins=15, color="goldenrod", edgecolor="black", alpha=0.7)
            ax.set_xlabel("Prediction Error (Predicted Gold - Actual Gold)")
            ax.set_ylabel("Frequency")
            ax.set_title(f"Graph 5: Gold Prediction Error Distribution (n={len(gold_errors)})")
        else:
            ax.text(0.5, 0.5, "No valid action-conditioned gold prediction pairs\n(horizon > 0, known action)", ha="center", va="center", transform=ax.transAxes)
            ax.set_title("Graph 5: Gold Prediction Error Distribution (No Data)")
        ax.grid(True, linestyle="--", alpha=0.5)

        p5 = os.path.join(output_dir, "gold_prediction_error.png")
        fig.tight_layout()
        fig.savefig(p5, dpi=150)
        plt.close(fig)
        generated.append(p5)
    except Exception as e:
        print(f"[!] Error generating plot 5: {e}")

    return generated
