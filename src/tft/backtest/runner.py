"""TFT Backtest Runner."""
from typing import Dict, List, Optional, Tuple, Any
from tft.domain.game_state import GameState
from tft.domain.actions import ActionType
from tft.decision.engine import DecisionEngine
from tft.decision.models import Recommendation
from tft.backtest.models import (
    BacktestSample,
    BacktestDecision,
    ActualActionType
)
from tft.backtest.baselines import (
    BaseStrategy,
    AlwaysSaveBaseline,
    HPThresholdBaseline,
    RuleEngineBaseline
)

class BacktestRunner:
    """Backtest 실행기: Decision Engine 및 Baseline 전략 일괄 평가."""

    def __init__(
        self,
        decision_engine: Optional[DecisionEngine] = None,
        random_seed: Optional[int] = 42
    ):
        self.decision_engine = decision_engine or DecisionEngine(random_seed=random_seed)
        self.baselines: Dict[str, BaseStrategy] = {
            "AlwaysSave": AlwaysSaveBaseline(),
            "HPThreshold": HPThresholdBaseline(hp_threshold=35),
            "RuleEngine": RuleEngineBaseline()
        }

    def run_sample(
        self,
        sample: BacktestSample
    ) -> Tuple[BacktestDecision, Dict[str, BacktestDecision]]:
        """단일 스냅샷 샘플에 대해 Decision Engine 및 Baseline 실행."""
        state = sample.observed_state.state
        actual_act = sample.observed_state.actual_action

        # 1. Run Decision Engine
        rec: Recommendation = self.decision_engine.decide(state)
        engine_act = rec.recommended_action.action_type

        agreement = (
            (engine_act.value == actual_act.value)
            if actual_act != ActualActionType.UNKNOWN
            else None
        )

        sim_summaries = rec.metadata.get("simulation_summaries", {})
        score_breakdowns = {}
        for s in rec.all_scores:
            score_breakdowns[s.action.action_type.value] = {
                k: b.contribution for k, b in s.breakdown.items()
            }

        engine_decision = BacktestDecision(
            sample_id=sample.sample_id,
            strategy_name="DecisionEngine_v1.1",
            recommended_action=engine_act,
            decision_margin=rec.decision_margin,
            confidence=rec.confidence,
            action_scores={s.action.action_type.value: s.score for s in rec.all_scores},
            score_breakdown=score_breakdowns,
            simulated_expectations=sim_summaries,
            reasons=[r.summary for r in rec.reasons],
            actual_action=actual_act,
            agreement=agreement
        )

        # 2. Run Baselines
        baseline_decisions: Dict[str, BacktestDecision] = {}
        for b_name, b_strat in self.baselines.items():
            b_act = b_strat.decide_action(state)
            b_agreement = (
                (b_act.value == actual_act.value)
                if actual_act != ActualActionType.UNKNOWN
                else None
            )
            baseline_decisions[b_name] = BacktestDecision(
                sample_id=sample.sample_id,
                strategy_name=b_name,
                recommended_action=b_act,
                decision_margin=0.0,
                confidence=0.50,
                action_scores={b_act.value: 1.0},
                score_breakdown={},
                simulated_expectations={},
                reasons=[f"Rule-based policy decision: {b_act.value}"],
                actual_action=actual_act,
                agreement=b_agreement
            )

        return engine_decision, baseline_decisions

    def run_batch(
        self,
        samples: List[BacktestSample]
    ) -> Tuple[List[BacktestDecision], Dict[str, List[BacktestDecision]]]:
        """데이터셋 전체에 대해 배치 실행."""
        engine_decisions: List[BacktestDecision] = []
        baseline_decisions: Dict[str, List[BacktestDecision]] = {
            name: [] for name in self.baselines.keys()
        }

        for sample in samples:
            eng_dec, base_decs = self.run_sample(sample)
            engine_decisions.append(eng_dec)
            for b_name, b_dec in base_decs.items():
                baseline_decisions[b_name].append(b_dec)

        return engine_decisions, baseline_decisions
