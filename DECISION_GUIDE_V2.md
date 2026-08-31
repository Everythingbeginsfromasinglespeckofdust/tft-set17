# TFT Decision State Guide v2 (Human Operational Guide)

## 🧭 In-Game Decision Framework

```
[Current GameState Input]
        ↓
1. Survival Risk Assessment (HP & Stage Damage)
        ↓
2. Board Strength vs Stage Benchmark Ratio
        ↓
3. Upgrade Concentration (Pair Count & Shop Hits)
        ↓
4. Economy Reserve & Interest Breakpoint
        ↓
[Calibrated Action Recommendation + Why Explanation]
```

---

## 📋 Standard Operational Roadmaps

### Situation A: Lethal Danger (HP <= 28 or Horizon <= 2.0 rounds)
- **Engine Direction**: **`ROLL`**
- **Why**: 1 combat loss causes elimination. Gold has 0 value if eliminated.
- **Action Rule**: Spend spendable roll budget down to 0G if necessary to complete 2-star front/backline.

### Situation B: Healthy Economy Snowball (HP >= 70 & Board >= 100% Benchmark)
- **Engine Direction**: **`SAVE_GOLD`**
- **Why**: Board strength is sufficient to win or take negligible loss damage.
- **Action Rule**: Preserve 50G to earn +5G maximum compound interest every turn.

### Situation C: Low-Cost Tempo Level-Up (XP Cost <= 8G & Gold Remaining >= 20G)
- **Engine Direction**: **`LEVEL_UP`**
- **Why**: 2 clicks (8G) adds +1 board slot immediately and jumps 4-cost shop odds from 10% to 22%.
