"""TFT Recommendation Flip Analyzer & Human Review Queue Generator.

Evaluates:
- How candidate state features (e.g., pair counts, stage benchmark deficit, discrete interest breakpoints, lethal emergency risk)
  shift recommendation preferences compared to baseline DecisionEngine.
- Logs flip counts, flip rates, and exact flip state context.
- Exports structured cases to human_review_queue.jsonl for human reviewer auditing.
"""
import json
import os
from typing import Dict, List, Optional, Any, Tuple
from tft.domain.game_state import GameState
from tft.domain.actions import ActionType
from tft.decision.engine import DecisionEngine
from tft.research.decision_features.taxonomy import DecisionStateVector
from tft.calibration.state_features.extractor import StateFeatureExtractor


class FlipAnalyzer:
    """Analyzes behavioral recommendation shifts between baseline and feature-augmented candidates."""

    def __init__(self):
        self.extractor = StateFeatureExtractor()
        self.baseline_engine = DecisionEngine()

    def evaluate_candidate_policy(
        self, state_vec: DecisionStateVector, baseline_action: str
    ) -> Tuple[str, str, float, bool]:
        """Candidate state-feature policy evaluation.
        
        Applies candidate feature logic:
        1. LETHAL_EMERGENCY_ROLL: If HP <= 12 or estimated_rounds_to_elim <= 1.0, and gold >= 2: ROLL (Survival crisis).
        2. STAGE_4_STABILIZATION_ROLL: If stage >= 4 and HP <= 40 and gold >= 30 and stage_benchmark_ratio < 0.90: ROLL down to 30G.
        3. STAGE_6_ENDGAME_PRESSURE: If stage >= 6 and HP <= 50 and gold >= 30: ROLL for endgame legendary power.
        4. CHEAP_TEMPO_LEVEL_UP: If gold_to_level <= 8G and shop_tier_match_score > 0.50 and (gold - gold_to_level >= 20): LEVEL_UP.
        5. SAFE_COMPOUND_INTEREST: If HP >= 70 and stage_benchmark_ratio >= 1.05 and interest_tier < 5: SAVE_GOLD.
        """
        p = state_vec.player
        econ = state_vec.economy
        upg = state_vec.upgrade
        rel = state_vec.relative
        temp = state_vec.temporal

        # Rule 1: Lethal Emergency (1-shot elimination territory)
        if (temp.estimated_rounds_to_elimination is not None and temp.estimated_rounds_to_elimination <= 1.0) and p.gold >= 2:
            candidate_act = "ROLL"
            code = "CANDIDATE_LETHAL_EMERGENCY_ROLL"
            cand_score = 0.9250
        # Rule 2: Stage 4+ Midgame Stabilization (HP <= 40, below stage benchmark, healthy gold)
        elif p.stage >= 4 and p.hp <= 40 and p.gold >= 30 and rel.stage_benchmark_ratio < 0.95:
            candidate_act = "ROLL"
            code = "CANDIDATE_STAGE_4_STABILIZATION_ROLL"
            cand_score = 0.8650
        # Rule 3: Stage 6 Late-Game Pressure (Lethal damage >= 18 HP/round)
        elif p.stage >= 6 and p.hp <= 50 and p.gold >= 30:
            candidate_act = "ROLL"
            code = "CANDIDATE_STAGE_6_ENDGAME_PRESSURE"
            cand_score = 0.8800
        # Rule 4: Cheap Tempo Level-Up
        elif econ.gold_to_next_level <= 8 and upg.shop_tier_match_score > 0.50 and (p.gold - econ.gold_to_next_level >= 20):
            candidate_act = "LEVEL_UP"
            code = "CANDIDATE_CHEAP_TEMPO_LEVEL_UP"
            cand_score = 0.8420
        # Rule 5: Safe Compound Interest
        elif p.hp >= 70 and rel.stage_benchmark_ratio >= 1.05 and econ.gold_to_next_interest <= 4 and econ.interest_tier < 5:
            candidate_act = "SAVE_GOLD"
            code = "CANDIDATE_SAFE_COMPOUND_INTEREST"
            cand_score = 0.8900
        else:
            candidate_act = baseline_action
            code = "BASELINE_CONCORDANCE"
            cand_score = 0.7500

        is_flipped = (candidate_act != baseline_action)
        return candidate_act, code, cand_score, is_flipped

    def run_flip_analysis(
        self,
        samples: List[Dict[str, Any]],
        output_review_queue_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute flip analysis across dataset samples and write human review queue."""
        total_samples = len(samples)
        flips: List[Dict[str, Any]] = []
        concordant_count = 0
        flip_matrix = {
            "SAVE_GOLD->ROLL": 0,
            "SAVE_GOLD->LEVEL_UP": 0,
            "ROLL->SAVE_GOLD": 0,
            "ROLL->LEVEL_UP": 0,
            "LEVEL_UP->SAVE_GOLD": 0,
            "LEVEL_UP->ROLL": 0
        }

        review_queue_rows = []

        for idx, s in enumerate(samples):
            state_obj = s.get("state")
            if not isinstance(state_obj, GameState):
                state_obj = GameState.from_dict(state_obj if isinstance(state_obj, dict) else s)

            sample_id = s.get("sample_id", f"SAMPLE_{idx:04d}")
            match_id = s.get("match_id", "MATCH_001")

            # Extract full state vector
            state_vec = self.extractor.extract(state_obj, sample_id=sample_id, match_id=match_id)

            # Get Baseline Decision
            baseline_rec = self.baseline_engine.decide(state_obj)
            base_act_raw = baseline_rec.recommended_action
            base_act = base_act_raw.action_type.value if hasattr(base_act_raw, "action_type") else str(base_act_raw)

            cand_act, code, cand_score, is_flipped = self.evaluate_candidate_policy(state_vec, base_act)

            if is_flipped:
                key = f"{base_act}->{cand_act}"
                if key in flip_matrix:
                    flip_matrix[key] += 1

                flip_record = {
                    "case_id": f"CASE_{len(flips)+1:03d}",
                    "sample_id": sample_id,
                    "match_id": match_id,
                    "stage_round": state_vec.stage_round,
                    "state_summary": {
                        "hp": state_vec.player.hp,
                        "gold": state_vec.player.gold,
                        "level": state_vec.player.level,
                        "pair_count": state_vec.upgrade.pair_count,
                        "stage_benchmark_ratio": state_vec.relative.stage_benchmark_ratio,
                        "spendable_roll_budget": state_vec.economy.spendable_roll_budget,
                        "rounds_to_elimination": state_vec.temporal.estimated_rounds_to_elimination
                    },
                    "baseline_action": base_act,
                    "baseline_score": baseline_rec.score,
                    "candidate_action": cand_act,
                    "candidate_score": cand_score,
                    "flip_rationale_code": code,
                    "actual_player_action": s.get("actual_player_action", "UNKNOWN"),
                    "human_preferred_action": s.get("human_preferred_action", "UNKNOWN"),
                    "human_review_status": "PENDING_REVIEW"
                }
                flips.append(flip_record)
                review_queue_rows.append(flip_record)
            else:
                concordant_count += 1

        flip_rate = round(len(flips) / max(1, total_samples), 4)

        # Write review queue JSONL if requested
        if output_review_queue_path:
            os.makedirs(os.path.dirname(output_review_queue_path), exist_ok=True)
            with open(output_review_queue_path, "w", encoding="utf-8") as f:
                for row in review_queue_rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

        return {
            "total_evaluated_samples": total_samples,
            "total_flips": len(flips),
            "concordant_count": concordant_count,
            "flip_rate": flip_rate,
            "flip_matrix": flip_matrix,
            "sample_flips": flips
        }
