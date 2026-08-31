"""TFT Decision Guide & Human Strategic Guidance Generator.

Translates complex multidimensional DecisionStateVector into:
1. Readable In-game Context Summary
2. Decision Interpretation (Survival, Economy, Upgrades, Relative)
3. Operational Direction (NOW, WATCH, THEN)
4. Strategic Q&A Reference (Q1 ~ Q8)
"""
from typing import Dict, Any, Optional
from tft.research.decision_features.taxonomy import DecisionStateVector


class DecisionGuideGenerator:
    """Generates structured, human-readable operational decision guides."""

    @staticmethod
    def format_guide(
        state_vec: DecisionStateVector,
        recommended_action: str,
        action_score: float,
        score_gap: float,
        reasons: list
    ) -> str:
        """Format full state vector and recommendation into clean markdown guide."""
        p = state_vec.player
        econ = state_vec.economy
        board = state_vec.board
        upg = state_vec.upgrade
        rel = state_vec.relative
        temp = state_vec.temporal

        # Determine qualitative labels
        surv_label = "🚨 CRITICAL RISK" if (temp.estimated_rounds_to_elimination and temp.estimated_rounds_to_elimination <= 2.0) or p.hp <= 30 else ("⚠️ MODERATE RISK" if p.hp <= 55 else "✅ SAFE")
        econ_label = f"💰 {econ.interest_tier}G Interest Tier ({p.gold}G)" if econ.interest_tier >= 4 else f"📉 Economy Rebuilding ({p.gold}G, Spendable: {econ.spendable_roll_budget}G)"
        upg_label = f"⭐ HIGH ({upg.pair_count} Pairs, {upg.immediate_shop_upgrades} in Shop)" if upg.pair_count >= 2 or upg.immediate_shop_upgrades > 0 else f"Normal ({upg.pair_count} Pairs)"
        bench_label = "🔥 Above Stage Baseline" if rel.stage_benchmark_ratio >= 1.05 else ("⚠️ Below Stage Benchmark" if rel.stage_benchmark_ratio < 0.90 else "⚖️ Par with Benchmark")

        guide = f"""# 🧭 TFT Decision State Guide — Stage {p.stage_round}

## 1. 📊 Current State Context
- **Health (HP)**: `{p.hp}` | **Gold (G)**: `{p.gold}G` (Interest: `+{econ.interest_tier}G`)
- **Level**: `{p.level}` (XP: `{p.xp}`, Cost to Next Level: `{econ.gold_to_next_level}G`)
- **Board Strength**: `{board.raw_board_power:.1f}` ({bench_label}, `{rel.stage_benchmark_ratio:.0%}` of Stage Baseline)
- **Upgrade Holdings**: `{upg.pair_count}` Pairs | `{upg.immediate_shop_upgrades}` Immediate Upgrades in Shop
- **Survival Horizon**: `~{temp.estimated_rounds_to_elimination:.1f}` Losses until lethal elimination

---

## 2. 🔍 State Dimension Interpretation
- **Survival Status**: **{surv_label}**
- **Economy Status**: **{econ_label}**
- **Upgrade Urgency**: **{upg_label}**
- **Relative Benchmark**: **{bench_label}**

---

## 3. 🎯 Engine Recommendation & Operational Roadmap
- **Recommended Action**: **`{recommended_action}`** (Score: `{action_score:.4f}`, Separation Gap: `+{score_gap:.4f}`)
- **Why (Rationale)**:
"""
        for r in reasons[:4]:
            guide += f"  - [{getattr(r, 'code', 'REASON')}] {getattr(r, 'summary', str(r))}\n"

        guide += f"""
- **Watch & Re-evaluate Checkpoint**:
  - Re-evaluate when interest boundary is crossed or a 2-star pair is successfully completed.
  - Do not drop below `{econ.economy_reserve_target}G` unless in immediate lethal danger.
"""
        return guide

    @staticmethod
    def get_strategic_qa_reference() -> str:
        """Returns deep strategic Q&A reference addressing core tactical questions."""
        return """# 📚 TFT Set 18 Strategic Decision Reference (Q1 ~ Q8)

### Q1. 언제 무조건 경제(50G 복리)를 지키는 것이 합리적인가?
- **조건**: 체력(HP) $\ge 65$, 필드 파워가 현재 스테이지 기준값 대비 $100\%$ 이상, 즉각적인 1~2개 2성 완성 압박이 없는 경우.
- **근거**: 50G 유지 시 매 턴 $+5\text{G}$의 최대 복리 이자를 획득하여 4~5 스테이지 고코스트 전환(Level 8~9)에 필요한 $60\sim 80\text{G}$를 확보할 수 있습니다.

### Q2. 언제 HP가 낮으면 이자를 포기하고 롤(Roll Down)해야 하는가?
- **조건**: 남은 탈락 라운드 수가 2회 이하이거나 체력 $\le 28\text{HP}$일 때 (Stage 4 이후 기준).
- **근거**: 사망 시 축적된 골드의 기대 가치는 $0$이 되므로, 이자 손실보다 당장 2성 완성을 통한 라운드 승리 및 HP 보존이 최우선입니다.

### Q3. 언제 한 레벨 업이 리롤보다 가치가 있는가?
- **조건**: 레벨업 필요 골드가 $8\text{G}\sim 12\text{G}$ 이하이며, 대기석에 즉시 투입 가능한 강력한 기물(2성 또는 핵심 시너지 유닛)이 있거나, 4/5코스트 획득 확률이 급격히 증가하는 구간(예: Lv 7 $\to$ Lv 8).
- **근거**: 즉각적인 기물 슬롯 추가는 확정적인 보드 파워 상승($+10\sim 15\%$)과 상점 캐리 등장 확률($10\% \to 22\%$)을 동시에 제공합니다.

### Q4. 내 보드가 로비 평균보다 얼마나 약하면 긴급 대응해야 하는가?
- **조건**: 스테이지 기준값 대비 $80\%$ 미만이거나 로비 하위 $25\%$ 이하일 때.
- **근거**: 연속 패배 시 라운드당 $10\sim 15\text{HP}$가 삭감되어 2턴 만에 위험 구간으로 전락합니다.

### Q5. 현재 가지고 있는 페어가 실제로 리롤을 정당화할 정도인가?
- **조건**: 보드/대기석에 2성 완성이 임박한 페어가 2쌍 이상이고, 해당 기물이 메인 딜러 또는 메인 탱커일 때.
- **근거**: 2쌍 이상의 페어가 존재할 경우 5번 리롤($10\text{G}$) 내에 최소 1개 이상 2성이 완성될 확률이 $65\%$를 상회합니다.

### Q6. 상점에 목표 기물이 몇 장 나와야 리롤 지속 가치가 생기는가?
- **조건**: 상점에 즉시 구매 가능한 페어 또는 핵심 시너지 기물이 1장 이상 등장했을 때.
- **근거**: 자연 상점에서 이미 1장이 등장한 상태는 기회비용 없이 즉시 페어를 구성할 수 있는 최적의 타이밍입니다.

### Q7. 상대 보드가 강할 때 같은 Gold를 어떻게 다르게 써야 하는가?
- **조건**: 로비 상위권 보드 파워가 급격히 상승한 경우.
- **근거**: 50G 복리를 고집하기보다 $30\text{G}$를 비상 방어선으로 설정하고, 초과 골드를 적극적으로 소모하여 보드 평균 파워를 방어해야 연패 대미지를 줄일 수 있습니다.

### Q8. Stage가 올라갈수록 어떤 행동의 기회비용이 변하는가?
- **조건**: Stage 2 (라운드 대미지 4) vs Stage 5 (라운드 대미지 14).
- **근거**: 초반에는 체력을 소모하며 연패 이자를 챙기는 가치가 높지만, 후반에는 1회 패배의 체력 손실이 치명적이므로 리롤 및 즉시 전력화의 가치가 지수적으로 증가합니다.
"""
