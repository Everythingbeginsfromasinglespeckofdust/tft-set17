"""TFT Decision Engine Golden Scenarios Suite (8 Deterministic Reference Testcases)."""
from typing import Dict, Any, List
from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit, BoardPosition
from tft.domain.actions import ActionType

def get_golden_scenarios() -> Dict[str, Dict[str, Any]]:
    """8개의 정형화된 골든 시나리오 정의 반환."""
    return {
        "SCENARIO_01_CRISIS_ROLL": {
            "name": "Scenario 01: Crisis Mode (HP Low, Pairs on Bench -> ROLL)",
            "expected_best_action": ActionType.ROLL,
            "min_margin": 0.03,
            "description": "체력 24로 위기 상태이며 2성 완성이 임박한 페어 2종(조이, 자크) 보유. 즉각 리롤로 생존 확보 필요.",
            "state": GameState(
                stage=4,
                round=1,
                stage_round="4-1",
                player=PlayerState(gold=38, level=7, xp=4, hp=24),
                board_units=[
                    Unit(champion="조이", cost=2, star_level=1),
                    Unit(champion="나서스", cost=1, star_level=2),
                    Unit(champion="자크", cost=2, star_level=1),
                    Unit(champion="소나", cost=5, star_level=1),
                ],
                bench_units=[
                    Unit(champion="조이", cost=2, star_level=1), # Pair -> 1 copy away
                    Unit(champion="자크", cost=2, star_level=1), # Pair -> 1 copy away
                    Unit(champion="벨베스", cost=4, star_level=1),
                ]
            )
        },
        "SCENARIO_02_HEALTHY_SAVE": {
            "name": "Scenario 02: Healthy Economy (HP High, Early Game -> SAVE_GOLD)",
            "expected_best_action": ActionType.SAVE_GOLD,
            "min_margin": 0.005,
            "description": "체력 92로 안전권이며 2-3 라운드에서 28골드 보유. 50골드 복리 이자 극대화 추천.",
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
        "SCENARIO_03_LEVELUP_BREAKPOINT": {
            "name": "Scenario 03: Level Up Timing (4 XP to Lv.7, 54G, Strong Bench Unit -> LEVEL_UP)",
            "expected_best_action": ActionType.LEVEL_UP,
            "min_margin": 0.0, # Competitive with SAVE
            "description": "3-5 라운드 54골드 보유, 4골드(4XP)로 즉시 7레벨 달성 가능하며 벤치에 강력한 4코 2성 대기 중.",
            "state": GameState(
                stage=3,
                round=5,
                stage_round="3-5",
                player=PlayerState(gold=54, level=6, xp=56, hp=72), # 4 XP away from Lv.7
                board_units=[
                    Unit(champion="나서스", cost=1, star_level=2),
                    Unit(champion="조이", cost=2, star_level=2),
                    Unit(champion="소나", cost=5, star_level=1),
                ],
                bench_units=[
                    Unit(champion="벨베스", cost=4, star_level=2), # Strong 2★ 4-cost ready
                ]
            )
        },
        "SCENARIO_04_NO_UPGRADE_TARGET": {
            "name": "Scenario 04: No Valid Upgrade Target (All Board 2★, Empty Bench)",
            "expected_best_action": ActionType.SAVE_GOLD,
            "min_margin": 0.005,
            "description": "보드 유닛이 전부 2성이고 벤치가 비어있어 리롤로 업그레이드할 기물이 없음 -> 저축 또는 레벨업 유리.",
            "state": GameState(
                stage=3,
                round=2,
                stage_round="3-2",
                player=PlayerState(gold=45, level=6, xp=10, hp=80),
                board_units=[
                    Unit(champion="나서스", cost=1, star_level=2),
                    Unit(champion="조이", cost=2, star_level=2),
                    Unit(champion="자크", cost=2, star_level=2),
                ],
                bench_units=[]
            )
        },
        "SCENARIO_05_ZERO_GOLD": {
            "name": "Scenario 05: Zero Gold Edge Case (Gold = 0 -> SAVE_GOLD)",
            "expected_best_action": ActionType.SAVE_GOLD,
            "min_margin": 0.0,
            "description": "골드가 0이므로 롤이나 레벨업이 불가능하며 저축이 유일하게 유효함.",
            "state": GameState(
                stage=2,
                round=1,
                stage_round="2-1",
                player=PlayerState(gold=0, level=4, xp=0, hp=100),
                board_units=[
                    Unit(champion="나서스", cost=1, star_level=1)
                ],
                bench_units=[]
            )
        },
        "SCENARIO_06_EMPTY_BENCH": {
            "name": "Scenario 06: Empty Bench Handling",
            "expected_best_action": ActionType.SAVE_GOLD,
            "min_margin": 0.0,
            "description": "벤치에 기물이 없을 때 레벨업 시뮬레이션이 기본 티어 평균 파워를 정상 산출하는지 검증.",
            "state": GameState(
                stage=3,
                round=1,
                stage_round="3-1",
                player=PlayerState(gold=50, level=6, xp=20, hp=68),
                board_units=[
                    Unit(champion="나서스", cost=1, star_level=2),
                    Unit(champion="조이", cost=2, star_level=2),
                ],
                bench_units=[]
            )
        },
        "SCENARIO_07_POOL_DEPLETED": {
            "name": "Scenario 07: Pool Depleted (Contested 4-cost)",
            "expected_best_action": ActionType.SAVE_GOLD,
            "min_margin": 0.0,
            "description": "4코스트 목표 기물이 로비에서 8장 소모되어 풀에 2장만 남음 -> 리롤 기대치 저하 확인.",
            "state": GameState(
                stage=4,
                round=5,
                stage_round="4-5",
                player=PlayerState(gold=40, level=8, xp=20, hp=55),
                board_units=[
                    Unit(champion="벨베스", cost=4, star_level=1),
                    Unit(champion="나서스", cost=1, star_level=2),
                ],
                bench_units=[]
            )
        },
        "SCENARIO_08_BALANCED_MARGIN": {
            "name": "Scenario 08: Balanced Decision State (Close Scores)",
            "expected_best_action": None, # Any reasonable action
            "min_margin": 0.0,
            "description": "체력 55, 골드 45로 롤/업/저축 간의 점수 격차가 좁아 의사결정 마진이 명확히 보고되는지 검증.",
            "state": GameState(
                stage=3,
                round=3,
                stage_round="3-3",
                player=PlayerState(gold=45, level=6, xp=24, hp=55),
                board_units=[
                    Unit(champion="나서스", cost=1, star_level=2),
                    Unit(champion="조이", cost=2, star_level=1),
                ],
                bench_units=[
                    Unit(champion="조이", cost=2, star_level=1)
                ]
            )
        }
    }
