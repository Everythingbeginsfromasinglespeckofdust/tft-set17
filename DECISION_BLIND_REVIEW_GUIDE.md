# TFT Blind Decision Review Guide

## 1. Concept & Methodology
To prevent human confirmation bias from anchoring to the `DecisionEngine`'s recommendations, **Blind Decision Review Mode** enforces an independent judgment protocol:
1. Video pauses at target decision timestamp.
2. Reviewer inspects the observed GameState (HP, Gold, Level, Shop, Board, Bench).
3. Engine recommendation is **hidden**.
4. Reviewer selects their independent preferred action (`[R] ROLL`, `[L] LEVEL_UP`, `[S] SAVE_GOLD`).
5. Selection is recorded as `human_preference`.
6. Engine recommendation is revealed.
7. Automated comparison is performed:
   - Agreement $\to$ Marked `REASONABLE`
   - Disagreement $\to$ Marked `QUESTIONABLE` or `WRONG`, diagnostic failure case created if flagged.

---

## 2. Keyboard Controls in Overlay

- `[1]`: Mark Recommendation as `REASONABLE`
- `[2]`: Mark Recommendation as `QUESTIONABLE`
- `[3]`: Mark Recommendation as `WRONG`
- `[4]`: Mark Recommendation as `UNKNOWN`
- `[B]`: Toggle Blind Mode ON / OFF
- `[R]`: Input Blind Preference `ROLL`
- `[L]`: Input Blind Preference `LEVEL_UP`
- `[S]`: Input Blind Preference `SAVE_GOLD`
