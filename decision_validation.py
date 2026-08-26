#!/usr/bin/env python3
"""TFT Set 17 Decision Engine v1.1 — Mathematical Validation & Golden Scenario Benchmark Tool.

사용법:
    python decision_validation.py
"""
import argparse
import math
import os
import random
import sys

# Ensure src is on python path
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.domain.actions import Action, ActionType
from tft.data.repositories import get_data_repository
from tft.simulation.future_state import FutureStateSimulator
from tft.decision.engine import DecisionEngine
from tft.decision.scorer import ActionScorer, DecisionConfig
from tft.evaluation.golden_scenarios import get_golden_scenarios

data_repo = get_data_repository()

def monte_carlo_shop_rolls(
    level: int,
    targets: list[dict],
    num_rolls: int,
    num_simulations: int = 50000,
    seed: int = 42
) -> dict:
    """Monte Carlo empirical simulation of TFT shop rolls."""
    random.seed(seed)
    pool_data = {}
    for c in range(1, 6):
        k_c = data_repo.get_pool_size(c)
        n_c = data_repo.get_champion_count_by_cost(c)
        pool_data[c] = {"K": k_c, "N": n_c, "total": k_c * n_c}

    target_hits_count = [0] * len(targets)
    any_target_hit_sims = 0
    drop_rates = {c: data_repo.get_drop_rate(level, c) for c in range(1, 6)}

    for _ in range(num_simulations):
        hit_in_sim = [0] * len(targets)
        for _ in range(num_rolls):
            for _ in range(5):
                r = random.random()
                cum = 0.0
                slot_cost = 1
                for c in range(1, 6):
                    cum += drop_rates[c]
                    if r <= cum:
                        slot_cost = c
                        break
                
                for idx, t in enumerate(targets):
                    if t["cost"] == slot_cost:
                        k_c = pool_data[slot_cost]["K"]
                        n_c = pool_data[slot_cost]["N"]
                        rem_target = k_c - t.get("target_taken", 0)
                        rem_tier = (k_c * n_c) - t.get("tier_taken", 0)
                        p_target_given_cost = rem_target / max(1, rem_tier)
                        if random.random() <= p_target_given_cost:
                            hit_in_sim[idx] += 1

        for idx in range(len(targets)):
            if hit_in_sim[idx] >= 1:
                target_hits_count[idx] += 1
        if any(h >= 1 for h in hit_in_sim):
            any_target_hit_sims += 1

    return {
        "num_simulations": num_simulations,
        "single_target_probs": [hits / num_simulations for hits in target_hits_count],
        "any_target_prob": any_target_hit_sims / num_simulations
    }

def run_roll_math_validation():
    print("=" * 80)
    print("🔬 [PHASE 1] ROLL PROBABILITY MATHEMATICAL VALIDATION (Analytical vs Monte Carlo)")
    print("=" * 80)

    test_cases = [
        {"name": "1-Cost Nasus (Level 4, 10 rolls / 50 slots)", "level": 4, "rolls": 10, "targets": [{"name": "나서스", "cost": 1, "target_taken": 0, "tier_taken": 0}]},
        {"name": "2-Cost Zoe (Level 7, 19 rolls / 95 slots / 38G)", "level": 7, "rolls": 19, "targets": [{"name": "조이", "cost": 2, "target_taken": 2, "tier_taken": 10}]},
        {"name": "3-Cost Gangplank (Level 7, 10 rolls / 50 slots)", "level": 7, "rolls": 10, "targets": [{"name": "갱플랭크", "cost": 3, "target_taken": 0, "tier_taken": 0}]},
        {"name": "Multi-Target 2-Cost Zoe + Zac (Level 7, 19 rolls)", "level": 7, "rolls": 19, "targets": [{"name": "조이", "cost": 2, "target_taken": 2, "tier_taken": 10}, {"name": "자크", "cost": 2, "target_taken": 2, "tier_taken": 10}]},
        {"name": "Contested 4-Cost Bel'Veth (Level 8, 15 rolls, 8/10 taken)", "level": 8, "rolls": 15, "targets": [{"name": "벨베스", "cost": 4, "target_taken": 8, "tier_taken": 40}]}
    ]

    for tc in test_cases:
        slots = 5 * tc["rolls"]
        mc = monte_carlo_shop_rolls(tc["level"], tc["targets"], tc["rolls"], num_simulations=50000)
        print(f"\n📌 {tc['name']}")
        print(f"  Config: Level {tc['level']}, Rolls: {tc['rolls']} (Total Slots: {slots})")

        combined_p_slot = 0.0
        for idx, t in enumerate(tc["targets"]):
            c = t["cost"]
            drop_rate = data_repo.get_drop_rate(tc["level"], c)
            k_c = data_repo.get_pool_size(c)
            n_c = data_repo.get_champion_count_by_cost(c)
            p_slot = drop_rate * (k_c - t.get("target_taken", 0)) / max(1, (k_c * n_c) - t.get("tier_taken", 0))
            combined_p_slot += p_slot
            p_analytical = 1.0 - ((1.0 - p_slot) ** slots)
            p_mc = mc["single_target_probs"][idx]
            abs_err = abs(p_analytical - p_mc)
            rel_err = abs_err / max(1e-9, p_mc)
            print(f"  • Target [{t['name']} (Cost {c})]:")
            print(f"      p_slot               : {p_slot:.5f}")
            print(f"      Analytical P(>=1)    : {p_analytical:.4f} ({p_analytical*100:.2f}%)")
            print(f"      Monte Carlo (50k)    : {p_mc:.4f} ({p_mc*100:.2f}%)")
            print(f"      Absolute Error       : {abs_err:.5f}")
            print(f"      Relative Error       : {rel_err:.2%}")

        if len(tc["targets"]) > 1:
            p_joint = 1.0 - ((1.0 - combined_p_slot) ** slots)
            p_mc_any = mc["any_target_prob"]
            print(f"  • Multi-Target Joint Upgrade Probability:")
            print(f"      Correct Joint Analytical: {p_joint:.4f} ({p_joint*100:.2f}%)")
            print(f"      Monte Carlo Empirical   : {p_mc_any:.4f} ({p_mc_any*100:.2f}%)")
            print(f"      Joint Absolute Error    : {abs(p_joint - p_mc_any):.5f}")

def run_save_gold_trajectory():
    print("\n" + "=" * 80)
    print("📈 [PHASE 2] SAVE_GOLD ECONOMIC TRAJECTORY VERIFICATION (3-Turn Horizon)")
    print("=" * 80)
    simulator = FutureStateSimulator()
    state = GameState(
        stage=3, round=2, stage_round="3-2",
        player=PlayerState(gold=42, level=6, xp=8, hp=75),
        board_units=[Unit(champion="조이", cost=2, star_level=2)]
    )
    res = simulator.simulate(state, Action(ActionType.SAVE_GOLD), horizon=3)
    
    print(f"Starting State: Gold={state.player.gold}G, Level={state.player.level}, XP={state.player.xp}, HP={state.player.hp}\n")
    print(f"{'Turn':<6}{'Start Gold':<12}{'Interest':<10}{'Round Gold':<12}{'XP Gain':<10}{'End Level':<12}{'End XP':<10}{'End Gold':<10}")
    print("-" * 82)
    for td in res.turn_by_turn:
        print(f"{td.turn:<6}{td.start_gold:<12}{td.interest_earned:<10}{td.base_gold_earned:<12}{'+2':<10}{td.end_level:<12}{td.end_xp:<10}{td.end_gold:<10}")

def run_golden_scenarios_validation():
    print("\n" + "=" * 80)
    print("🏆 [PHASE 3] 8 GOLDEN SCENARIOS VALIDATION & SCORE BREAKDOWN")
    print("=" * 80)

    engine = DecisionEngine(random_seed=42)
    scenarios = get_golden_scenarios()

    for sc_id, sc in scenarios.items():
        state = sc["state"]
        rec = engine.decide(state, horizon=3)
        expected = sc.get("expected_best_action")
        passed = (expected is None) or (rec.recommended_action.action_type == expected)
        status = "✅ PASS" if passed else "❌ FAIL"

        print(f"\n{status} | {sc_id} : {sc['name']}")
        print(f"  State: Stage {state.stage_round} | Gold: {state.player.gold}G | Level: {state.player.level} | HP: {state.player.hp} | Board Power: {rec.metadata['simulation_summaries']['SAVE_GOLD']['expected_power']:.1f}")
        print(f"  Recommended: {rec.recommended_action.action_type.value} (Score: {rec.score:.4f}, Margin: +{rec.decision_margin:.4f}, Rel Conf: {rec.confidence:.0%})")
        
        print("  Score Breakdown by Action:")
        for a_score in rec.all_scores:
            is_top = " 🌟" if a_score.action.action_type == rec.recommended_action.action_type else ""
            print(f"    • [{a_score.action.action_type.value}]{is_top} Total: {a_score.score:.4f}")
            for k, b in a_score.breakdown.items():
                print(f"        - {k:<12}: raw={b.raw_value:<6.1f} norm={b.normalized_value:<6.3f} wt={b.weight:<5.2f} -> contrib={b.contribution:+.4f}")
        
        if rec.reasons:
            print("  Reasons:")
            for r in rec.reasons[:2]:
                print(f"    - [{r.code}] {r.summary}")

def main():
    run_roll_math_validation()
    run_save_gold_trajectory()
    run_golden_scenarios_validation()

if __name__ == "__main__":
    main()
