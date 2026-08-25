#!/usr/bin/env python3
"""TFT Set 17 통합 경제 & 보드 파워 종합 리포트 CLI 도구 (Dashboard Report).

통합 모듈:
- economy/board_power.py (v2 확정 가중치: 성급 1.0/2.2/3.6, 부품 0.0점, 완성 3.0점)
- economy/interest.py (이자 계산)
- economy/levelup.py (레벨업 필요 골드)
- economy/reroll.py (리롤 횟수)
- economy/roll_probability.py (챔피언 출현 확률)
- economy/strategy_comparator.py (N턴 뒤 전략별 결과 비교)

실행 방식:
1. JSON 파일 입력:
   python report.py path/to/scenario.json
   python report.py --file path/to/scenario.json

2. CLI 직접 인자 입력:
   python report.py --gold 30 --level 4 --xp 0 --stage 2-1 --board '{"units": [...]}'
"""
import argparse
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_OUTPUT = os.path.join(_HERE, "..")
_ECONOMY = os.path.join(_OUTPUT, "economy")
if _ECONOMY not in sys.path:
    sys.path.insert(0, _ECONOMY)

import board_power as bp
from interest import calculate_interest
from levelup import gold_to_reach_level
from strategy_comparator import compare_strategies


def generate_tactical_comment(stage_round: str, level: int, gold: int, gold_for_next: int, total_power: float) -> str:
    """규칙 기반 인게임 상황 판단 코멘트 생성 (1~2줄)."""
    # 1. 초반 단계 (Stage 2 또는 Level <= 5)
    if stage_round.startswith("2-") or level <= 5:
        if gold >= 20 and total_power < 15.0:
            return "💡 [초반 운영] 골드 여유가 있으나 보드가 약합니다. 연패 이자를 챙기거나 빠른 5레벨 타이밍에 2성작을 노려 체력을 보존하세요."
        elif total_power >= 15.0:
            return "🔥 [초반 우세] 강력한 연승 보드입니다. 체력 우위를 바탕으로 50골드 이자를 모아 빠른 레벨업 템포를 추천합니다."
        else:
            return "⚖️ [초반 탐색] 기물 2성작과 아이템 빌드업을 진행하며 연승/연패 방향을 결정하세요."

    # 2. 후반 단계 (Stage 6+ 또는 Level >= 9)
    if stage_round.startswith("6-") or stage_round.startswith("7-") or level >= 9:
        if level == 9 and gold_for_next > 0 and gold >= gold_for_next:
            return "🚀 [10레벨 적기] 10레벨 도달 가능 골드를 보유하고 있습니다. 즉시 10레벨을 달성해 5코스트 2성/시너지를 추가하세요."
        elif total_power >= 75.0:
            return "🏆 [우승권 보드] 강력한 최종 덱입니다. 3성 4/5코스트 리롤이나 10레벨 밸류업으로 1위를 확정지으세요."
        else:
            return "🛡️ [후반 결승] 배치 조정 및 서풍/침묵 등 서포트 아이템으로 핵심 매치업 상성을 극복하세요."

    # 3. 중반 단계 (Stage 3~5, Level 6~8)
    if gold < 15 and total_power < 40.0:
        return "⚠️ [위기 신호] 보드 파워가 낮고 골드가 부족합니다. 즉시 템을 조합하고 핵심 기물 2성작 리롤로 체력 방어가 시급합니다."
    elif gold >= 30 and total_power < 35.0:
        return "🔄 [전환 타이밍] 골드 여유가 있으나 보드가 약합니다. 4코스트 핵심 캐리 중심의 덱 전환 또는 2성작 리롤이 필요합니다."
    elif total_power >= 45.0:
        return "⚔️ [중반 안정] 준수한 보드 파워를 갖추고 있습니다. 50골드 이자를 유지하며 8/9레벨 밸류업을 도모하세요."
    else:
        return "📊 [중반 템포] 덱의 메인 캐리 3신기 아이템 완성과 앞라인 2성 탱커 보강에 집중하세요."


def generate_dashboard_report(state: dict) -> dict:
    """게임 상태 데이터를 받아 통합 경제 및 보드 파워 리포트 딕셔너리 생성."""
    gold = state.get("gold", 0)
    level = state.get("level", 1)
    xp = state.get("xp", 0)
    stage_round = str(state.get("stage_round", "N/A"))
    board = state.get("board", {"units": []})
    strategies = state.get("strategies", [])
    num_turns = state.get("num_turns", 3)
    title = state.get("title", f"TFT Game Report ({stage_round})")

    # 1. 보드 파워 계산 (board_power.py)
    board_res = bp.calculate_board_power(board)
    total_power = board_res["total_power"]
    breakdown = board_res["breakdown"]

    # 2. 경제 상태 분석 (interest.py, levelup.py)
    next_interest = calculate_interest(gold)
    next_level = min(10, level + 1)
    gold_for_next_level = gold_to_reach_level(level, xp, next_level) if level < 10 else 0

    # 3. 전략 시뮬레이션 (strategy_comparator.py)
    strategies_res = None
    if strategies:
        strategies_res = compare_strategies(
            current_gold=gold,
            current_level=level,
            current_xp=xp,
            num_turns=num_turns,
            strategies=strategies,
        )

    # 4. 규칙 기반 코멘트
    tactical_comment = generate_tactical_comment(
        stage_round=stage_round,
        level=level,
        gold=gold,
        gold_for_next=gold_for_next_level,
        total_power=total_power,
    )

    return {
        "title": title,
        "state": {
            "stage_round": stage_round,
            "level": level,
            "xp": xp,
            "gold": gold,
            "units_count": len(board.get("units", [])),
        },
        "board_power": {
            "total_power": total_power,
            "breakdown": breakdown,
        },
        "economy": {
            "current_gold": gold,
            "next_turn_interest": next_interest,
            "next_level": next_level,
            "gold_to_next_level": gold_for_next_level,
        },
        "num_turns": num_turns,
        "strategies_comparison": strategies_res,
        "tactical_comment": tactical_comment,
    }


def format_report_text(report_data: dict) -> str:
    """리포트 딕셔너리를 가독성 높은 텍스트 포맷으로 렌더링."""
    lines = []
    lines.append("=" * 68)
    lines.append(f"  📊 TFT Set 17 종합 분석 대시보드 리포트")
    lines.append(f"  📌 {report_data['title']}")
    lines.append("=" * 68)

    # 1. 기본 상태
    s = report_data["state"]
    lines.append(f"\n[1] 🎮 현재 게임 상태")
    lines.append(f"  - 진행 상황: Stage {s['stage_round']} | 레벨: {s['level']} Lv (XP: {s['xp']})")
    lines.append(f"  - 보유 골드: {s['gold']} G | 보드 기물 수: {s['units_count']}명")

    # 2. 보드 파워 점수
    bp_data = report_data["board_power"]
    bk = bp_data["breakdown"]
    lines.append(f"\n[2] ⚔️ 보드 가치평가 (v2 가중치)")
    lines.append(f"  - 🏆 종합 보드 파워: {bp_data['total_power']:.2f} 점")
    lines.append(f"    ├─ 유닛 파워 (성급 1.0/2.2/3.6): {bk['unit_power']:.2f} 점")
    lines.append(f"    ├─ 아이템 점수 (완성 +3.0 / 부품 +0.0): {bk['item_score']:.2f} 점")
    lines.append(f"    └─ 시너지 보너스 (단계^1.5 * 2.0): {bk['synergy_bonus']:.2f} 점")

    if bk.get("active_synergies"):
        syn_str = ", ".join(
            f"{syn['trait']} ({syn['unit_count']}명/단계{syn['breakpoint_reached']}: +{syn['bonus']:.1f}점)"
            for syn in bk["active_synergies"]
        )
        lines.append(f"  - 활성 시너지: {syn_str}")
    else:
        lines.append(f"  - 활성 시너지: 없음")

    # 3. 경제 상태 요약
    eco = report_data["economy"]
    lines.append(f"\n[3] 💰 경제 상태 요약")
    lines.append(f"  - 다음 턴 예상 기본 이자: +{eco['next_turn_interest']} G")
    if eco["next_level"] > s["level"]:
        lines.append(f"  - {eco['next_level']}레벨 도달 필요 골드: {eco['gold_to_next_level']} G (현재 골드로 {'도달 가능' if s['gold'] >= eco['gold_to_next_level'] else '부족'})")
    else:
        lines.append(f"  - 최고 레벨(10Lv)에 도달한 상태입니다.")

    # 4. 전략 비교 (있을 경우)
    strat_list = report_data.get("strategies_comparison")
    num_turns = report_data.get("num_turns", 3)
    if strat_list:
        lines.append(f"\n[4] 📈 {num_turns}턴 뒤 전략별 시뮬레이션 비교")
        lines.append(f"  {'전략명':<30} | {'최종골드':<7} | {'최종레벨':<6} | {'목표기물 적중률'}")
        lines.append("  " + "-" * 66)
        for st in strat_list:
            s_info = st["strategy"]
            s_name = s_info.get("name", s_info.get("type", "전략"))
            hit_str = "-"
            if st.get("target_hit_prob_cumulative") is not None:
                p_val = st["target_hit_prob_cumulative"] * 100.0
                target_c = s_info.get("target_champion", "기물")
                hit_str = f"{target_c} ({p_val:.1f}%)"
            lines.append(
                f"  {s_name:<30} | {st['final_gold']:>5.0f} G | {st['final_level']:>4} Lv | {hit_str}"
            )

    # 5. 종합 코멘트
    lines.append(f"\n[5] 🎯 전술적 조언 & 가이드")
    lines.append(f"  {report_data['tactical_comment']}")
    lines.append("=" * 68)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="TFT Set 17 종합 대시보드 리포트 도구")
    parser.add_argument("scenario_file", nargs="?", default=None, help="시나리오 JSON 파일 경로")
    parser.add_argument("--file", "-f", default=None, help="시나리오 JSON 파일 경로")
    parser.add_argument("--gold", type=int, default=None, help="현재 보유 골드")
    parser.add_argument("--level", type=int, default=None, help="현재 레벨 (1~10)")
    parser.add_argument("--xp", type=int, default=0, help="현재 보유 XP")
    parser.add_argument("--stage", type=str, default="1-1", help="스테이지-라운드 (예: '5-2')")
    parser.add_argument("--board", type=str, default=None, help="보드 상태 JSON 문자열")
    parser.add_argument("--json", action="store_true", help="JSON 포맷으로 출력")

    args = parser.parse_args()

    # 입력 소스 결정
    file_path = args.file or args.scenario_file

    if file_path:
        if not os.path.exists(file_path):
            print(f"오류: 시나리오 파일을 찾을 수 없습니다: {file_path}", file=sys.stderr)
            sys.exit(1)
        with open(file_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    elif args.gold is not None and args.level is not None:
        board_data = {"units": []}
        if args.board:
            try:
                board_data = json.loads(args.board)
            except Exception as e:
                print(f"오류: --board JSON 파싱 실패: {e}", file=sys.stderr)
                sys.exit(1)

        state = {
            "title": f"CLI 매뉴얼 입력 ({args.stage})",
            "stage_round": args.stage,
            "level": args.level,
            "xp": args.xp,
            "gold": args.gold,
            "board": board_data,
        }
    else:
        print("사용법: python report.py [scenario.json] 또는 --file [scenario.json] 또는 CLI 인자 (--gold, --level 등)")
        sys.exit(1)

    report_data = generate_dashboard_report(state)

    if args.json:
        print(json.dumps(report_data, ensure_ascii=False, indent=2))
    else:
        print(format_report_text(report_data))


if __name__ == "__main__":
    main()
