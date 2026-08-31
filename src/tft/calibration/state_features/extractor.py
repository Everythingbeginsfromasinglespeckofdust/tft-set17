"""TFT State Feature Extractor (Calibration Layer).

Translates a runtime GameState into a fully structured DecisionStateVector
using the research feature modules (BoardPowerModel, SurvivalRiskModel,
EconomyReserveModel, UpgradeOpportunityModel, LevelUpOpportunityModel).

Guarantees:
- Pure T0 Temporal Causality (No future outcomes or final placement injected).
- Unobserved fields default to None / UNKNOWN, NEVER 0.
"""
from typing import Dict, List, Optional, Any
from tft.domain.game_state import GameState, LobbyState
from tft.data.repositories import StaticDataRepository, get_data_repository
from tft.research.decision_features.taxonomy import (
    DecisionStateVector,
    PlayerStateVector,
    EconomyStateVector,
    BoardStateVector,
    UpgradeStateVector,
    OpponentStateVector,
    TemporalStateVector,
    RelativeStateVector
)
from tft.research.decision_features.board_power import BoardPowerModel
from tft.research.decision_features.survival_risk import SurvivalRiskModel
from tft.research.decision_features.economy_reserve import EconomyReserveModel
from tft.research.decision_features.upgrade_opportunity import UpgradeOpportunityModel
from tft.research.decision_features.level_up_cost import LevelUpOpportunityModel


class StateFeatureExtractor:
    """Extracts DecisionStateVector from standard GameState."""

    def __init__(self, data_repo: Optional[StaticDataRepository] = None):
        self.data_repo = data_repo or get_data_repository()
        self.board_model = BoardPowerModel(self.data_repo)
        self.upgrade_model = UpgradeOpportunityModel(self.data_repo)
        self.level_model = LevelUpOpportunityModel(self.data_repo)

    def extract(
        self,
        state: GameState,
        sample_id: str = "T0_SAMPLE",
        match_id: str = "MATCH_LIVE",
        previous_state: Optional[GameState] = None,
        opponent_focus_id: Optional[str] = None
    ) -> DecisionStateVector:
        """Extract full state feature vector with temporal safety."""
        # 1. Player Vector
        p = state.player
        stage = state.stage
        rnd = state.round
        sr = state.stage_round or f"{stage}-{rnd}"
        
        player_vec = PlayerStateVector(
            hp=p.hp,
            gold=p.gold,
            level=p.level,
            xp=p.xp,
            streak=p.streak,
            stage=stage,
            round_num=rnd,
            stage_round=sr
        )

        # 2. Board Vector & Decomposition
        board_data = self.board_model.decompose_board(state)
        board_vec = BoardStateVector(
            raw_board_power=board_data["total_power"],
            unit_count=board_data["unit_count"],
            max_units=p.level,
            avg_unit_cost=board_data["avg_unit_cost"],
            star_distribution=board_data["star_distribution"],
            completed_items_count=int(board_data["item_score"] // 10.0),
            component_items_count=int((board_data["item_score"] % 10.0) // 3.0),
            active_traits_count=board_data["active_traits_count"],
            frontline_power_ratio=board_data["frontline_power_ratio"],
            backline_power_ratio=board_data["backline_power_ratio"]
        )

        # 3. Economy Vector
        lvl_table = self.data_repo.get_levelup_cost_table()
        econ_data = EconomyReserveModel.evaluate_economy(
            gold=p.gold,
            hp=p.hp,
            stage=stage,
            level=p.level,
            xp=p.xp,
            levelup_cost_table=lvl_table
        )
        econ_vec = EconomyStateVector(
            spendable_gold=p.gold,
            interest_tier=econ_data["interest_tier"],
            gold_to_next_interest=econ_data["gold_to_next_interest"],
            gold_to_next_level=econ_data["gold_to_next_level"],
            spendable_roll_budget=econ_data["spendable_roll_budget"],
            economy_reserve_target=econ_data["economy_reserve_target"],
            interest_opportunity_cost_roll=econ_data["interest_loss_10g_roll"],
            interest_opportunity_cost_level=econ_data["interest_loss_level"]
        )

        # 4. Upgrade Vector
        upg_data = self.upgrade_model.evaluate_upgrades(state)
        lvl_data = self.level_model.evaluate_level_up_tradeoff(state)
        
        upgrade_vec = UpgradeStateVector(
            pair_count=upg_data["pair_count"],
            two_star_count=upg_data["two_star_count"],
            three_star_candidate_count=upg_data["three_star_candidate_count"],
            missing_copies_summary=upg_data["missing_copies_summary"],
            immediate_shop_upgrades=upg_data["immediate_shop_upgrades_count"],
            shop_matching_units_count=upg_data["shop_matching_units_count"],
            expected_roll_upgrade_count_10g=upg_data["expected_roll_upgrade_prob_10g"],
            shop_tier_match_score=lvl_data["marginal_level_value_score"]
        )

        # 5. Opponent & Lobby Vector
        opponents = state.opponents
        lobby_data = self.board_model.compute_lobby_relative_metrics(
            my_power=board_data["total_power"],
            opponents=opponents
        )
        
        cur_opp_power = None
        cur_opp_gap = None
        if opponent_focus_id and opponents:
            found = next((op for op in opponents if op.player_id == opponent_focus_id), None)
            if found and found.estimated_board_power > 0:
                cur_opp_power = found.estimated_board_power
                cur_opp_gap = round(board_data["total_power"] - cur_opp_power, 2)

        opp_vec = OpponentStateVector(
            known_opponents_count=lobby_data["known_opponents_count"],
            lobby_mean_board_power=lobby_data["lobby_mean_board_power"],
            lobby_median_board_power=lobby_data["lobby_median_board_power"],
            lobby_min_board_power=lobby_data["lobby_min_board_power"],
            lobby_max_board_power=lobby_data["lobby_max_board_power"],
            current_opponent_power=cur_opp_power,
            current_opponent_power_gap=cur_opp_gap
        )

        # 6. Temporal Vector (Deltas from previous state if available)
        hp_delta = (p.hp - previous_state.player.hp) if previous_state else None
        pwr_delta = (board_data["total_power"] - self.board_model.decompose_board(previous_state)["total_power"]) if previous_state else None
        gold_delta = (p.gold - previous_state.player.gold) if previous_state else None

        stage_bench_ratio = self.board_model.compute_stage_benchmark_ratio(board_data["total_power"], stage)
        surv_data = SurvivalRiskModel.evaluate_risk(
            hp=p.hp,
            stage=stage,
            round_num=rnd,
            recent_hp_delta=hp_delta,
            stage_benchmark_ratio=stage_bench_ratio
        )

        temporal_vec = TemporalStateVector(
            stage_numeric=round(stage + rnd / 10.0, 1),
            recent_hp_delta=hp_delta,
            recent_hp_slope_3turns=float(hp_delta) if hp_delta is not None else None,
            recent_board_power_delta=pwr_delta,
            recent_gold_delta=gold_delta,
            estimated_rounds_to_elimination=surv_data["rounds_to_elimination"]
        )

        # 7. Relative Vector
        rel_vec = RelativeStateVector(
            relative_board_power_to_mean=lobby_data["relative_board_power_to_mean"],
            board_power_percentile=lobby_data["board_power_percentile"],
            hp_percentile=None, # UNKNOWN unless full lobby HP is available
            economy_percentile=None,
            distance_to_top4_boundary=lobby_data["distance_to_top4_boundary"],
            stage_benchmark_ratio=stage_bench_ratio
        )

        return DecisionStateVector(
            sample_id=sample_id,
            match_id=match_id,
            stage_round=sr,
            player=player_vec,
            economy=econ_vec,
            board=board_vec,
            upgrade=upgrade_vec,
            opponent=opp_vec,
            temporal=temporal_vec,
            relative=rel_vec,
            metadata={"extracted_from": "GameState", "has_prev_state": previous_state is not None}
        )
