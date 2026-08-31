# TFT Decision Assistant — Real Gameplay Usability Validation Report (v1)

**Session ID:** `REAL_GAMEPLAY_SESSION_001`  
**Video File:** `562ffca4-3f1b-46be-8791-92fa6305388a-2026-08-30-22-31-00.mp4`  
**Video SHA256:** `842e129e4d50b0549469d4e12a85b005ee60585ed4f3e549a97d7985b8c402c5`  
**Resolution & Duration:** 1280x720 @ 60.00fps (1724.3s / 28.7min)  
**Final Match Placement:** #2  

## 1. Executive Summary & Verification Metrics

| Metric | Result | Target / Standard |
|---|---|---|
| **Total Real Checkpoints** | **20** | $\ge 20$ Real Gameplay Checkpoints |
| **Blind Review Checkpoints** | **11 / 20** | $\ge 10$ Blind Mode Reviews |
| **Copy Previous Turn Usage** | **19 / 20** | $\ge 10$ Incremental Workflows |
| **Recommendation Transitions** | **5** | $\ge 3$ Strategic State Transitions |
| **Engine vs Player Agreement** | **55.0%** | Behavioral Alignment Metric |
| **Engine vs Human Agreement** | **55.0%** | Preference Alignment Metric |
| **Player vs Human Agreement** | **90.0%** | Human Policy Concordance |
| **Human Judgment (Good / Quest / Wrong)** | **19 / 1 / 0** | Zero Untracked Decisions |
| **Avg Time per Checkpoint** | **0.50s** | Fast Manual UX Target $\le 5$s |
| **Avg Analyze Latency** | **0.0336s** | Sub-second Performance $\le 1.0$s |
| **Prediction Immutability SHA256** | `e760113a2a9862e0...` | 100% Bitwise Immutable |
| **Future Leakage in T0** | **0.0% (Zero)** | Strict T0 / T1+ Temporal Separation |

## 2. Checkpoint-by-Checkpoint Audit Table

| CP | Stage | Time | HP | Gold | Board (Key Units) | Engine Rec | Gap | Player Act | Human Pref | Judgment | Blind |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CP001 | 2-1 | 75s | 100 | 10G | Akali 1★, Camille 1★ | **SAVE_GOLD** | +0.0391 | SAVE_GOLD | SAVE_GOLD | GOOD | - |
| CP002 | 2-3 | 135s | 96 | 18G | Akali 2★, Camille 1★, Leona 1★ | **SAVE_GOLD** | +0.0231 | SAVE_GOLD | SAVE_GOLD | GOOD | - |
| CP003 | 2-5 | 195s | 88 | 28G | Akali 2★, Camille 1★, Leona 1★ | **SAVE_GOLD** | +0.0231 | SAVE_GOLD | SAVE_GOLD | GOOD | - |
| CP004 | 2-7 | 260s | 82 | 38G | Akali 2★, Camille 2★, Leona 1★ | **SAVE_GOLD** | +0.0161 | SAVE_GOLD | SAVE_GOLD | GOOD | - |
| CP005 | 3-1 | 320s | 82 | 48G | Akali 2★, Camille 2★, Leona 1★ | **SAVE_GOLD** | +0.0161 | SAVE_GOLD | SAVE_GOLD | GOOD | - |
| CP006 | 3-2 | 385s | 74 | 52G | Akali 2★, Camille 2★, Leona 2★ | **SAVE_GOLD** | +0.0050 | BUY_UNIT | SAVE_GOLD | GOOD | - |
| CP007 | 3-5 | 455s | 68 | 54G | Akali 2★, Camille 2★, Leona 2★ | **ROLL** | +0.0018 | SAVE_GOLD | SAVE_GOLD | GOOD | - |
| CP008 | 4-1 | 530s | 58 | 56G | Akali 2★, Camille 2★, Leona 2★ | **ROLL** | +0.0040 | SAVE_GOLD | SAVE_GOLD | GOOD | ✓ |
| CP009 | 4-2 | 605s | 48 | 44G | Akali 2★, Camille 2★, Leona 2★ | **SAVE_GOLD** | +0.0024 | SAVE_GOLD | ROLL | QUESTIONABLE | ✓ |
| CP010 | 4-3 | 675s | 38 | 48G | Akali 2★, Camille 2★, Leona 2★ | **SAVE_GOLD** | +0.0024 | ROLL | ROLL | GOOD | ✓ |
| CP011 | 4-5 | 740s | 32 | 32G | Akali 2★, Camille 2★, Leona 2★ | **ROLL** | +0.0685 | SAVE_GOLD | SAVE_GOLD | GOOD | ✓ |
| CP012 | 4-6 | 810s | 32 | 40G | Akali 2★, Camille 2★, Leona 2★ | **ROLL** | +0.0679 | LEVEL_UP | LEVEL_UP | GOOD | ✓ |
| CP013 | 5-1 | 890s | 32 | 22G | Akali 2★, Camille 2★, Leona 2★ | **ROLL** | +0.0324 | SAVE_GOLD | SAVE_GOLD | GOOD | ✓ |
| CP014 | 5-2 | 960s | 24 | 28G | Akali 2★, Camille 2★, Leona 2★ | **ROLL** | +0.0451 | ROLL | ROLL | GOOD | ✓ |
| CP015 | 5-3 | 1030s | 24 | 16G | Akali 2★, Camille 2★, Leona 2★ | **ROLL** | +0.0195 | SAVE_GOLD | SAVE_GOLD | GOOD | ✓ |
| CP016 | 5-5 | 1110s | 16 | 26G | Akali 2★, Camille 2★, Leona 2★ | **ROLL** | +0.0408 | ROLL | ROLL | GOOD | ✓ |
| CP017 | 5-7 | 1190s | 45 | 30G | Akali 3★, Camille 2★, Leona 2★ | **SAVE_GOLD** | +0.0015 | SAVE_GOLD | SAVE_GOLD | GOOD | ✓ |
| CP018 | 6-1 | 1270s | 45 | 40G | Akali 3★, Camille 2★, Leona 2★ | **SAVE_GOLD** | +0.0015 | SAVE_GOLD | SAVE_GOLD | GOOD | ✓ |
| CP019 | 6-2 | 1360s | 8 | 12G | Akali 3★, Camille 2★, Leona 2★ | **ROLL** | +0.0115 | ROLL | ROLL | GOOD | - |
| CP020 | 6-3 | 1450s | 8 | 4G | Akali 3★, Camille 2★, Leona 2★ | **ROLL** | +0.0001 | SAVE_GOLD | SAVE_GOLD | GOOD | - |

## 3. Final Gate Verdict

# **`REAL_GAMEPLAY_VALIDATED`**
