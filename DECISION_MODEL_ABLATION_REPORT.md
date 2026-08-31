# TFT Decision Model Feature Ablation & Interaction Study Report

## 1. Single Feature Ablation Results

| Ablation Configuration | Model Tested | Total Checkpoints | Flips Produced | Agreement with Baseline | Action Distribution (Roll/Level/Save) |
|---|---|---|---|---|---|
| `BASELINE` | BASELINE | 20 | 0 (0.0%) | **100.0%** | 10 / 0 / 10 |
| `ABLATION_SURVIVAL_ONLY` | ABLATION_SURVIVAL_ONLY | 20 | 10 (50.0%) | **50.0%** | 4 / 0 / 16 |
| `ABLATION_UPGRADE_ONLY` | ABLATION_UPGRADE_ONLY | 20 | 10 (50.0%) | **50.0%** | 4 / 0 / 16 |
| `ABLATION_ECONOMY_ONLY` | ABLATION_ECONOMY_ONLY | 20 | 10 (50.0%) | **50.0%** | 4 / 0 / 16 |
| `COMBINED_V4` | COMBINED_V4 | 20 | 10 (50.0%) | **50.0%** | 4 / 0 / 16 |

---

## 2. Feature Interaction Matrix
1. **`HP Risk x Pair Count`**: When survival horizon is <= 2.0 rounds and player holds >= 1 pairs, ROLL score increases by +0.12, converting passive SAVE into emergency stabilization.
2. **`HP Risk x Board Strength`**: When HP is safe (>= 70) and board power exceeds stage benchmark (>1.05), SAVE_GOLD score increases by +0.05 to preserve compound interest.
3. **`Level-Up Cost x High-Cost Carry Odds`**: When `gold_to_level` <= 8G and level jump provides >10% 4/5-cost carry odds jump, LEVEL_UP dominates SAVE_GOLD.
