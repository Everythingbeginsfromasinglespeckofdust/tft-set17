# TFT Decision Validation Overlay v1 Specification

## 1. Overview & Architecture
**TFT Decision Validation Overlay v1** connects the verified, frozen production Vision Pipeline with the frozen `DecisionEngine` (`ActionScorer`, `FutureStateSimulator`, `ExplanationGenerator`), providing a real-time visual validation environment for evaluating engine recommendations against actual player actions, independent human preferences, and observed future outcomes.

```text
Real TFT Video / Desktop Capture
            ↓
Verified Vision Pipeline
            ↓
Reconstructed GameState at T0
            ↓
Frozen DecisionEngine.decide(state)
            ↓
Decision Overlay HUD
            ↓
Three-Way Comparison (Player vs Engine vs Human Preference)
            ↓
Independent Human Review ([REASONABLE] / [QUESTIONABLE] / [WRONG] / [UNKNOWN])
            ↓
Observed Future Outcomes (T1+) Linkage (Non-Causal Descriptive Stats)
            ↓
Decision Failure Cases & Engineering Backlog (P0~P3)
```

---

## 2. Information State Partitioning

| Layer | Source | Contents |
|---|---|---|
| **Observed (T0)** | Real Vision Pipeline | HP, Gold, Level, XP, Stage, Shop 5 slots, Board units, Bench units, Actual Player Action |
| **Simulated (T0)** | `DecisionEngine` | Recommendation, Action Scores, `action_score_gap`, traceable Score Breakdowns, Reasons |
| **Human Review** | Human Auditor | `human_judgment` (`REASONABLE`, `QUESTIONABLE`, `WRONG`), `human_preference` (Blind mode) |
| **Future Outcome (T1+)**| Post-Decision Gameplay | HP after N rounds, Gold after N rounds, Level after N rounds, Final Placement |

> [!IMPORTANT]
> $T_0$ GameState, Engine Recommendation, Human Preference, and $T_{1+}$ Future Outcomes are strictly isolated into distinct data models and append-only JSONL logs. Zero future information is passed to `DecisionEngine.decide()`.

---

## 3. Three Independent Evaluation Metrics

1. **Behavioral Agreement**: Engine Recommendation vs Actual Player Action ($\%$)
2. **Human Preference Agreement**: Engine Recommendation vs Human Preference in Blind Review ($\%$)
3. **Outcome Association**: Average placement and HP/Gold trajectories associated with recommendations (purely descriptive; non-causal).
