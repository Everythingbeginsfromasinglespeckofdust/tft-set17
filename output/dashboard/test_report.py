#!/usr/bin/env python3
"""test_report.py — 종합 대시보드 리포트(report.py) 단위 및 통합 테스트."""
import json
import os
import subprocess
import sys
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_OUTPUT = os.path.join(_HERE, "..")
_ECONOMY = os.path.join(_OUTPUT, "economy")
if _ECONOMY not in sys.path:
    sys.path.insert(0, _ECONOMY)

import report as rep

SCENARIOS_DIR = os.path.join(_HERE, "example_scenarios")


def load_scenario(filename: str) -> dict:
    path = os.path.join(SCENARIOS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_scenario_1_early_weak_rich():
    """시나리오 1: 초반(2-1) 약한 보드, 골드 여유."""
    state = load_scenario("scenario_1_early_weak_rich.json")
    res = rep.generate_dashboard_report(state)

    assert res["state"]["stage_round"] == "2-1"
    assert res["state"]["level"] == 4
    assert res["state"]["gold"] == 30

    # 보드 파워 (v2 기준 7.0점)
    assert res["board_power"]["total_power"] == pytest.approx(7.0)
    assert res["board_power"]["breakdown"]["unit_power"] == pytest.approx(3.0)
    assert res["board_power"]["breakdown"]["item_score"] == pytest.approx(0.0)

    # 경제 요약
    assert res["economy"]["next_turn_interest"] == 3
    assert res["economy"]["gold_to_next_level"] == 10

    # 전략 비교 결과 검증
    strat_res = res["strategies_comparison"]
    assert strat_res is not None
    assert len(strat_res) == 3
    # 리롤 전략에 누적 확률 존재 확인
    roll_strat = next(s for s in strat_res if s["strategy"]["type"] == "roll")
    assert roll_strat["target_hit_prob_cumulative"] > 0.9

    # 전술 코멘트
    assert "초반 운영" in res["tactical_comment"]


def test_scenario_2_mid_neutral_poor():
    """시나리오 2: 중반(5-2) 애매한 보드, 골드 부족."""
    state = load_scenario("scenario_2_mid_neutral_poor.json")
    res = rep.generate_dashboard_report(state)

    assert res["state"]["stage_round"] == "5-2"
    assert res["state"]["level"] == 7
    assert res["state"]["gold"] == 8

    # 보드 파워
    assert res["board_power"]["total_power"] == pytest.approx(48.0)
    assert res["economy"]["next_turn_interest"] == 0
    assert res["economy"]["gold_to_next_level"] == 24

    strat_res = res["strategies_comparison"]
    assert len(strat_res) == 3


def test_scenario_3_late_strong_leveling():
    """시나리오 3: 후반(7-1) 강한 보드, 레벨업 임박."""
    state = load_scenario("scenario_3_late_strong_leveling.json")
    res = rep.generate_dashboard_report(state)

    assert res["state"]["stage_round"] == "7-1"
    assert res["state"]["level"] == 9
    assert res["state"]["gold"] == 54

    # 보드 파워 (100점 이상 고밸류)
    assert res["board_power"]["total_power"] == pytest.approx(122.4)
    assert res["economy"]["next_turn_interest"] == 5
    assert res["economy"]["next_level"] == 10
    assert res["economy"]["gold_to_next_level"] == 8  # 10레벨까지 8골드 필요 (54골드로 도달 가능)

    # 10레벨 적기 코멘트
    assert "10레벨 적기" in res["tactical_comment"]


def test_scenario_1_vs_scenario_3_distinctness():
    """완료 기준: 시나리오 1(약한보드)과 시나리오 3(강한보드)의 리포트 내용 실질 차이 검증."""
    s1 = rep.generate_dashboard_report(load_scenario("scenario_1_early_weak_rich.json"))
    s3 = rep.generate_dashboard_report(load_scenario("scenario_3_late_strong_leveling.json"))

    # 보드 파워 격차 15배 이상
    assert s3["board_power"]["total_power"] > s1["board_power"]["total_power"] * 15.0

    # 상태 및 코멘트가 확연히 다름
    assert s1["economy"]["next_level"] == 5
    assert s3["economy"]["next_level"] == 10
    assert s1["tactical_comment"] != s3["tactical_comment"]


def test_format_report_text_sections():
    """텍스트 리포트가 5개 섹션을 모두 정상 포함하는지 검증."""
    state = load_scenario("scenario_1_early_weak_rich.json")
    rep_dict = rep.generate_dashboard_report(state)
    text = rep.format_report_text(rep_dict)

    assert "[1] 🎮 현재 게임 상태" in text
    assert "[2] ⚔️ 보드 가치평가" in text
    assert "[3] 💰 경제 상태 요약" in text
    assert "[4] 📈 3턴 뒤 전략별 시뮬레이션 비교" in text
    assert "[5] 🎯 전술적 조언 & 가이드" in text


def test_cli_execution_with_json_and_manual_args():
    """CLI 서브프로세스 실행 테스트 (파일 입력, --json 플래그, 수동 인자)."""
    script_path = os.path.join(_HERE, "report.py")
    s1_path = os.path.join(SCENARIOS_DIR, "scenario_1_early_weak_rich.json")

    # 1. 파일 경로 인자 실행
    proc = subprocess.run(
        [sys.executable, script_path, s1_path, "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["state"]["stage_round"] == "2-1"
    assert data["board_power"]["total_power"] == pytest.approx(7.0)

    # 2. 수동 CLI 인자 실행
    proc2 = subprocess.run(
        [
            sys.executable,
            script_path,
            "--gold", "20",
            "--level", "5",
            "--xp", "4",
            "--stage", "3-1",
            "--json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc2.returncode == 0
    data2 = json.loads(proc2.stdout)
    assert data2["state"]["gold"] == 20
    assert data2["state"]["level"] == 5
    assert data2["state"]["stage_round"] == "3-1"
