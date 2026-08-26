#!/usr/bin/env python3
"""TFT Set 17 Decision Engine v1 CLI Demonstration Tool.

사용법:
    python cli_decision_demo.py
    python cli_decision_demo.py --scenario crisis
    python cli_decision_demo.py --scenario econ
    python cli_decision_demo.py --scenario levelup
"""
import argparse
import json
import os
import sys

# Ensure src is on python path
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit, BoardPosition
from tft.domain.actions import ActionType
from tft.application.services import DecisionService

def get_demo_scenarios():
    return {
        "crisis": {
            "title": "시나리오 1: [체력 위기] 4-2 라운드 체력 26 / 38골드 (리롤 안정화 타이밍)",
            "state": GameState(
                stage=4,
                round=2,
                stage_round="4-2",
                player=PlayerState(gold=38, level=7, xp=4, hp=26),
                board_units=[
                    Unit(champion="조이", cost=2, star_level=1),
                    Unit(champion="나서스", cost=1, star_level=2),
                    Unit(champion="자크", cost=2, star_level=1),
                    Unit(champion="소나", cost=5, star_level=1),
                ],
                bench_units=[
                    Unit(champion="조이", cost=2, star_level=1),  # Zoe pair (2/3 copies -> 1 away from 2★)
                    Unit(champion="자크", cost=2, star_level=1),  # Zac pair (2/3 copies -> 1 away from 2★)
                    Unit(champion="벨베스", cost=4, star_level=1),
                ]
            )
        },
        "econ": {
            "title": "시나리오 2: [초반 연승/이자] 2-3 라운드 체력 92 / 28골드 (50G 복리 저축 타이밍)",
            "state": GameState(
                stage=2,
                round=3,
                stage_round="2-3",
                player=PlayerState(gold=28, level=5, xp=0, hp=92),
                board_units=[
                    Unit(champion="나서스", cost=1, star_level=2),
                    Unit(champion="조이", cost=2, star_level=2),
                    Unit(champion="케일", cost=1, star_level=2),
                ],
                bench_units=[
                    Unit(champion="애쉬", cost=1, star_level=1)
                ]
            )
        },
        "levelup": {
            "title": "시나리오 3: [레벨업 적기] 3-5 라운드 체력 72 / 56골드 (즉시 7레벨 파워업 타이밍)",
            "state": GameState(
                stage=3,
                round=5,
                stage_round="3-5",
                player=PlayerState(gold=56, level=6, xp=32, hp=72), # 4 XP away from Lv.7 (4G 필요)
                board_units=[
                    Unit(champion="나서스", cost=1, star_level=2),
                    Unit(champion="조이", cost=2, star_level=2),
                    Unit(champion="소나", cost=5, star_level=1),
                ],
                bench_units=[
                    Unit(champion="벨베스", cost=4, star_level=2), # 강력한 4코스트 2성이 벤치에서 대기 중
                ]
            )
        }
    }

def print_decision_report(title: str, state: GameState, result: dict):
    print("=" * 80)
    print(f"🎯 {title}")
    print("=" * 80)
    print(f"State:")
    print(f"  Stage/Round : {state.stage_round}")
    print(f"  Level       : {state.player.level}")
    print(f"  Gold        : {state.player.gold}G")
    print(f"  HP          : {state.player.hp}")
    print(f"  Board Power : {result['board_evaluation']['total_power']:.1f}")
    print(f"  Active Traits: {[s['trait'] for s in result['board_evaluation']['active_synergies']]}")
    print()

    print("Decision Comparison (Horizon = 3 Turns):")
    print("-" * 80)
    
    sim_summaries = result["recommendation"]["simulation_summaries"]
    all_scores = [result["recommendation"]] + result["recommendation"]["alternatives"]
    # Group by action
    for item in result["recommendation"]["alternatives"] + [result["recommendation"]]:
        action_name = item["action"]
        score = item["score"]
        conf = item["confidence"]
        sim = sim_summaries.get(action_name, {})
        
        is_rec = " 🌟 [RECOMMENDED]" if action_name == result["recommendation"]["action"] else ""
        print(f"[{action_name}]{is_rec}")
        print(f"  Score                : {score:.4f} (Confidence: {conf:.0%})")
        print(f"  Expected Gold (T+3)  : {sim.get('expected_gold', 0):.1f}G")
        print(f"  Expected HP (T+3)    : {sim.get('expected_hp', 0):.1f}")
        print(f"  Expected Board Power : {sim.get('expected_power', 0):.1f}")
        print(f"  Upgrade Probability  : {sim.get('upgrade_prob', 0):.1%}")
        print(f"  Survival Probability : {sim.get('survival_prob', 0):.1%}")
        print()

    print("=" * 80)
    print(f"🏆 Recommended Action: {result['recommendation']['action']} (Score: {result['recommendation']['score']:.4f})")
    print("=" * 80)
    print("Structured Reasons & Evidence:")
    for idx, r in enumerate(result["recommendation"]["reasons"], 1):
        print(f"  {idx}. [{r['code']}] {r['summary']}")
        if r.get("evidence"):
            ev_str = ", ".join(f"{k}={v}" for k, v in r["evidence"].items() if isinstance(v, (int, float, str)))
            print(f"     📊 Evidence: {ev_str}")
    print()

def main():
    parser = argparse.ArgumentParser(description="TFT Set 17 Decision Engine v1 CLI Demo")
    parser.add_argument("--scenario", choices=["crisis", "econ", "levelup", "all"], default="all", help="Select scenario to run")
    args = parser.parse_args()

    service = DecisionService(random_seed=42)
    scenarios = get_demo_scenarios()

    if args.scenario == "all":
        for sc_key, sc_data in scenarios.items():
            res = service.analyze_and_recommend(sc_data["state"], horizon=3)
            print_decision_report(sc_data["title"], sc_data["state"], res)
    else:
        sc_data = scenarios[args.scenario]
        res = service.analyze_and_recommend(sc_data["state"], horizon=3)
        print_decision_report(sc_data["title"], sc_data["state"], res)

if __name__ == "__main__":
    main()
