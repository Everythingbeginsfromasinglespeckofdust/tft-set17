# 🧭 TFT Decision State Guide — Stage 3-5

## 1. 📊 Current State Context
- **Health (HP)**: `68` | **Gold (G)**: `54G` (Interest: `+5G`)
- **Level**: `6` (XP: `12`, Cost to Next Level: `48G`)
- **Board Strength**: `6.0` (⚠️ Below Stage Benchmark, `17%` of Stage Baseline)
- **Upgrade Holdings**: `0` Pairs | `0` Immediate Upgrades in Shop
- **Survival Horizon**: `~7.6` Losses until lethal elimination

---

## 2. 🔍 State Dimension Interpretation
- **Survival Status**: **✅ SAFE**
- **Economy Status**: **💰 5G Interest Tier (54G)**
- **Upgrade Urgency**: **Normal (0 Pairs)**
- **Relative Benchmark**: **⚠️ Below Stage Benchmark**

---

## 3. 🎯 Engine Recommendation & Operational Roadmap
- **Recommended Action**: **`ROLL`** (Score: `0.8850`, Separation Gap: `+0.1420`)
- **Why (Rationale)**:
  - [REASON] [CRISIS_PAIR_STABILIZATION] Survival horizon is 1.8 rounds with 2 pairs waiting on bench.
  - [REASON] [STAGE_DEFICIT] Board power is 78% of Stage 4 benchmark (43.2 vs 55.0G).

- **Watch & Re-evaluate Checkpoint**:
  - Re-evaluate when interest boundary is crossed or a 2-star pair is successfully completed.
  - Do not drop below `50G` unless in immediate lethal danger.


# 📚 TFT Set 18 Strategic Decision Reference (Q1 ~ Q8)

### Q1. 언제 무조건 경제(50G 복리)를 지키는 것이 합리적인가?
- **조건**: 체력(HP) $\ge 65$, 필드 파워가 현재 스테이지 기준값 대비 $100\%$ 이상, 즉각적인 1~2개 2성 완성 압박이 없는 경우.
- **근거**: 50G 유지 시 매 턴 $+5	ext{G}$의 최대 복리 이자를 획득하여 4~5 스테이지 고코스트 전환(Level 8~9)에 필요한 $60\sim 80	ext{G}$를 확보할 수 있습니다.

### Q2. 언제 HP가 낮으면 이자를 포기하고 롤(Roll Down)해야 하는가?
- **조건**: 남은 탈락 라운드 수가 2회 이하이거나 체력 $\le 28	ext{HP}$일 때 (Stage 4 이후 기준).
- **근거**: 사망 시 축적된 골드의 기대 가치는 $0$이 되므로, 이자 손실보다 당장 2성 완성을 통한 라운드 승리 및 HP 보존이 최우선입니다.

### Q3. 언제 한 레벨 업이 리롤보다 가치가 있는가?
- **조건**: 레벨업 필요 골드가 $8	ext{G}\sim 12	ext{G}$ 이하이며, 대기석에 즉시 투입 가능한 강력한 기물(2성 또는 핵심 시너지 유닛)이 있거나, 4/5코스트 획득 확률이 급격히 증가하는 구간(예: Lv 7 $	o$ Lv 8).
- **근거**: 즉각적인 기물 슬롯 추가는 확정적인 보드 파워 상승($+10\sim 15\%$)과 상점 캐리 등장 확률($10\% 	o 22\%$)을 동시에 제공합니다.

### Q4. 내 보드가 로비 평균보다 얼마나 약하면 긴급 대응해야 하는가?
- **조건**: 스테이지 기준값 대비 $80\%$ 미만이거나 로비 하위 $25\%$ 이하일 때.
- **근거**: 연속 패배 시 라운드당 $10\sim 15	ext{HP}$가 삭감되어 2턴 만에 위험 구간으로 전락합니다.

### Q5. 현재 가지고 있는 페어가 실제로 리롤을 정당화할 정도인가?
- **조건**: 보드/대기석에 2성 완성이 임박한 페어가 2쌍 이상이고, 해당 기물이 메인 딜러 또는 메인 탱커일 때.
- **근거**: 2쌍 이상의 페어가 존재할 경우 5번 리롤($10	ext{G}$) 내에 최소 1개 이상 2성이 완성될 확률이 $65\%$를 상회합니다.

### Q6. 상점에 목표 기물이 몇 장 나와야 리롤 지속 가치가 생기는가?
- **조건**: 상점에 즉시 구매 가능한 페어 또는 핵심 시너지 기물이 1장 이상 등장했을 때.
- **근거**: 자연 상점에서 이미 1장이 등장한 상태는 기회비용 없이 즉시 페어를 구성할 수 있는 최적의 타이밍입니다.

### Q7. 상대 보드가 강할 때 같은 Gold를 어떻게 다르게 써야 하는가?
- **조건**: 로비 상위권 보드 파워가 급격히 상승한 경우.
- **근거**: 50G 복리를 고집하기보다 $30	ext{G}$를 비상 방어선으로 설정하고, 초과 골드를 적극적으로 소모하여 보드 평균 파워를 방어해야 연패 대미지를 줄일 수 있습니다.

### Q8. Stage가 올라갈수록 어떤 행동의 기회비용이 변하는가?
- **조건**: Stage 2 (라운드 대미지 4) vs Stage 5 (라운드 대미지 14).
- **근거**: 초반에는 체력을 소모하며 연패 이자를 챙기는 가치가 높지만, 후반에는 1회 패배의 체력 손실이 치명적이므로 리롤 및 즉시 전력화의 가치가 지수적으로 증가합니다.
