"""TFT Multi-turn Future State Simulator (ROLL / LEVEL_UP / SAVE_GOLD)."""
import copy
import math
import random
from typing import Any, Dict, List, Optional, Tuple
from tft.domain.game_state import GameState, PlayerState
from tft.domain.actions import Action, ActionType
from tft.domain.units import Unit
from tft.simulation.models import SimulationResult, TurnDetail
from tft.data.repositories import StaticDataRepository, get_data_repository
from tft.evaluation.board_evaluator import BoardEvaluator

class FutureStateSimulator:
    """TFT 미래 상태 다중 턴 시뮬레이터 (Future Trajectory Simulator).
    
    원칙:
    - 원본 GameState는 절대 변형하지 않음 (Immutable State).
    - Set 17 실제 드랍률, 레벨업 테이블, 보드 파워 가중치 v2 재사용.
    - 확률적 요소(ROLL 획득 확률, 승패 기대 데미지)를 명시적으로 모델링.
    - Deterministic mode 지원 (random_seed).
    """

    def __init__(self, data_repo: Optional[StaticDataRepository] = None, random_seed: Optional[int] = None):
        self.data_repo = data_repo or get_data_repository()
        self.board_evaluator = BoardEvaluator(self.data_repo)
        self.random_seed = random_seed
        if random_seed is not None:
            random.seed(random_seed)

    def simulate(self, state: GameState, action: Action, horizon: int = 3) -> SimulationResult:
        """지정된 Action과 Horizon(1~N턴)에 대한 미래 상태 시뮬레이션 실행."""
        if action.action_type == ActionType.SAVE_GOLD:
            return self.simulate_save_gold(state, action, horizon)
        elif action.action_type == ActionType.LEVEL_UP:
            return self.simulate_level_up(state, action, horizon)
        elif action.action_type == ActionType.ROLL:
            return self.simulate_roll(state, action, horizon)
        else:
            return self.simulate_save_gold(state, action, horizon)

    def simulate_strategy(self, state: GameState, strategy: dict, horizon: int = 3) -> SimulationResult:
        """레거시 dict 기반 전략 비교 인터페이스 호환용 어댑터."""
        act_str = strategy.get("action", "save_interest")
        if act_str in ["save_interest", "SAVE_GOLD"]:
            action = Action(ActionType.SAVE_GOLD)
        elif act_str in ["levelup", "LEVEL_UP"]:
            action = Action(ActionType.LEVEL_UP, target_level=strategy.get("target_level"))
        elif act_str in ["roll", "ROLL"]:
            action = Action(ActionType.ROLL, budget_gold=strategy.get("gold_per_turn"))
        else:
            action = Action(ActionType.SAVE_GOLD)
        return self.simulate(state, action, horizon=horizon)

    # -------------------------------------------------------------------------
    # 1. SAVE_GOLD SIMULATION
    # -------------------------------------------------------------------------
    def simulate_save_gold(self, state: GameState, action: Action, horizon: int = 3) -> SimulationResult:
        """SAVE_GOLD: 지출 없이 이자 극대화 및 자연 XP 축적 시뮬레이션."""
        cur_gold = state.player.gold
        cur_level = state.player.level
        cur_xp = state.player.xp
        cur_hp = state.player.hp
        cur_stage = state.stage
        cur_round = state.round

        base_eval = self.board_evaluator.evaluate(state)
        cur_board_power = base_eval.score

        lvl_table = self.data_repo.get_levelup_cost_table()
        max_lvl = 10

        turn_details: List[TurnDetail] = []
        upgrade_prob_cumulative = 0.0

        for t in range(1, horizon + 1):
            start_gold = cur_gold
            spent_gold = 0
            start_lvl = cur_level
            start_xp = cur_xp

            # 1. Passive XP (+2) and natural levelup check
            cur_xp += 2
            while cur_level < max_lvl and cur_xp >= lvl_table.get(cur_level + 1, 999):
                cur_xp -= lvl_table[cur_level + 1]
                cur_level += 1

            # 2. Economy calculation (Interest + Base round gold 5)
            interest = min(5, start_gold // 10)
            end_gold = start_gold + interest + 5

            # 3. Combat damage & HP loss (Heuristic estimation)
            stage_expected_power, stage_base_damage = self._get_stage_combat_params(cur_stage)
            loss_prob, hp_loss = self._calculate_combat_outcome(cur_board_power, stage_expected_power, stage_base_damage)
            cur_hp = max(0, cur_hp - hp_loss)

            # Natural 1 free shop roll upgrade probability
            free_roll_prob, _, _, _ = self._calculate_roll_upgrades(state, cur_level, num_rolls=1)
            upgrade_prob_cumulative = 1.0 - (1.0 - upgrade_prob_cumulative) * (1.0 - free_roll_prob)

            turn_details.append(TurnDetail(
                turn=t,
                action_executed="SAVE_GOLD",
                start_gold=start_gold,
                spent_gold=spent_gold,
                end_gold=end_gold,
                start_level=start_lvl,
                end_level=cur_level,
                start_xp=start_xp,
                end_xp=cur_xp,
                interest_earned=interest,
                base_gold_earned=5,
                hp_loss=hp_loss,
                resulting_hp=cur_hp,
                board_power=cur_board_power,
                hit_probability=free_roll_prob,
                notes=f"Interest +{interest}G, XP +2"
            ))

            cur_gold = end_gold
            cur_round += 1
            if cur_round > 7:
                cur_stage += 1
                cur_round = 1

        survival_score = self._calculate_survival_score(cur_hp)

        return SimulationResult(
            action=action,
            horizon=horizon,
            expected_gold=float(cur_gold),
            expected_hp=float(cur_hp),
            expected_board_power=cur_board_power,
            any_upgrade_probability=round(upgrade_prob_cumulative, 4),
            target_upgrade_probabilities={},
            expected_upgrade_count=round(upgrade_prob_cumulative, 4),
            survival_score=round(survival_score, 4),
            estimated_placement=None,
            turn_by_turn=turn_details,
            metadata={"strategy": "SAVE_GOLD", "final_level": cur_level, "final_xp": cur_xp}
        )

    # -------------------------------------------------------------------------
    # 2. LEVEL_UP SIMULATION
    # -------------------------------------------------------------------------
    def simulate_level_up(self, state: GameState, action: Action, horizon: int = 3) -> SimulationResult:
        """LEVEL_UP: XP 구매로 즉각적 레벨업 및 보드 정원 확대 시뮬레이션."""
        cur_gold = state.player.gold
        cur_level = state.player.level
        cur_xp = state.player.xp
        cur_hp = state.player.hp
        cur_stage = state.stage
        cur_round = state.round

        base_eval = self.board_evaluator.evaluate(state)
        cur_board_power = base_eval.score

        lvl_table = self.data_repo.get_levelup_cost_table()
        max_lvl = 10

        target_level = action.target_level or min(max_lvl, cur_level + 1)
        turn_details: List[TurnDetail] = []
        upgrade_prob_cumulative = 0.0

        for t in range(1, horizon + 1):
            start_gold = cur_gold
            start_lvl = cur_level
            start_xp = cur_xp
            spent_gold = 0

            # Turn 1: Execute Level Up purchase
            if t == 1:
                if cur_level < target_level and cur_level < max_lvl:
                    req_xp = lvl_table.get(target_level, 0)
                    needed_xp = max(0, req_xp - cur_xp)
                    clicks_needed = (needed_xp + 3) // 4
                    gold_needed = clicks_needed * 4

                    if action.budget_gold is not None:
                        spend_cap = min(action.budget_gold, start_gold)
                    else:
                        spend_cap = min(gold_needed, start_gold)

                    clicks_bought = spend_cap // 4
                    spent_gold = clicks_bought * 4
                    cur_xp += clicks_bought * 4

                    while cur_level < max_lvl and cur_xp >= lvl_table.get(cur_level + 1, 999):
                        cur_xp -= lvl_table[cur_level + 1]
                        cur_level += 1

                    if cur_level > start_lvl:
                        added_units = cur_level - start_lvl
                        added_power = self._evaluate_level_up_power_gain(state, cur_level) * added_units
                        cur_board_power += added_power
            else:
                cur_xp += 2
                while cur_level < max_lvl and cur_xp >= lvl_table.get(cur_level + 1, 999):
                    cur_xp -= lvl_table[cur_level + 1]
                    cur_level += 1

            # Economy
            remaining_gold = start_gold - spent_gold
            interest = min(5, remaining_gold // 10)
            end_gold = remaining_gold + interest + 5

            # Combat damage
            stage_expected_power, stage_base_damage = self._get_stage_combat_params(cur_stage)
            loss_prob, hp_loss = self._calculate_combat_outcome(cur_board_power, stage_expected_power, stage_base_damage)
            cur_hp = max(0, cur_hp - hp_loss)

            free_roll_prob, _, _, _ = self._calculate_roll_upgrades(state, cur_level, num_rolls=1)
            upgrade_prob_cumulative = 1.0 - (1.0 - upgrade_prob_cumulative) * (1.0 - free_roll_prob)

            turn_details.append(TurnDetail(
                turn=t,
                action_executed="LEVEL_UP" if t == 1 else "PASSIVE",
                start_gold=start_gold,
                spent_gold=spent_gold,
                end_gold=end_gold,
                start_level=start_lvl,
                end_level=cur_level,
                start_xp=start_xp,
                end_xp=cur_xp,
                interest_earned=interest,
                base_gold_earned=5,
                hp_loss=hp_loss,
                resulting_hp=cur_hp,
                board_power=cur_board_power,
                hit_probability=free_roll_prob,
                notes=f"Lv.{cur_level} (Board Power: {cur_board_power:.1f})"
            ))

            cur_gold = end_gold
            cur_round += 1
            if cur_round > 7:
                cur_stage += 1
                cur_round = 1

        survival_score = self._calculate_survival_score(cur_hp)

        return SimulationResult(
            action=action,
            horizon=horizon,
            expected_gold=float(cur_gold),
            expected_hp=float(cur_hp),
            expected_board_power=cur_board_power,
            any_upgrade_probability=round(upgrade_prob_cumulative, 4),
            target_upgrade_probabilities={},
            expected_upgrade_count=round(upgrade_prob_cumulative, 4),
            survival_score=round(survival_score, 4),
            estimated_placement=None,
            turn_by_turn=turn_details,
            metadata={"strategy": "LEVEL_UP", "final_level": cur_level, "final_xp": cur_xp}
        )

    # -------------------------------------------------------------------------
    # 3. ROLL SIMULATION
    # -------------------------------------------------------------------------
    def simulate_roll(self, state: GameState, action: Action, horizon: int = 3) -> SimulationResult:
        """ROLL: 리롤을 통한 2성/3성 기물 업그레이드 및 보드 파워 즉각 상승 시뮬레이션."""
        cur_gold = state.player.gold
        cur_level = state.player.level
        cur_xp = state.player.xp
        cur_hp = state.player.hp
        cur_stage = state.stage
        cur_round = state.round

        base_eval = self.board_evaluator.evaluate(state)
        cur_board_power = base_eval.score

        lvl_table = self.data_repo.get_levelup_cost_table()
        max_lvl = 10

        # Determine roll spend budget
        if action.budget_gold is not None:
            spend_budget = min(action.budget_gold, cur_gold)
        else:
            if cur_hp <= 35:
                spend_budget = max(0, cur_gold - 10)
            else:
                spend_budget = max(0, cur_gold - 50)

        num_rolls = max(1, spend_budget // 2) if spend_budget >= 2 else 0
        spent_on_rolls = num_rolls * 2

        # 1. Mathematically sound upgrade probabilities & whole-board power delta
        any_upgrade_prob, target_probs, exp_upg_count, power_gain = self._calculate_roll_upgrades(state, cur_level, num_rolls)
        turn_1_board_power = cur_board_power + power_gain

        turn_details: List[TurnDetail] = []
        upgrade_prob_cumulative = any_upgrade_prob

        for t in range(1, horizon + 1):
            start_gold = cur_gold
            start_lvl = cur_level
            start_xp = cur_xp

            if t == 1:
                spent_gold = spent_on_rolls
                board_pwr = turn_1_board_power
            else:
                spent_gold = 0
                cur_xp += 2
                while cur_level < max_lvl and cur_xp >= lvl_table.get(cur_level + 1, 999):
                    cur_xp -= lvl_table[cur_level + 1]
                    cur_level += 1
                board_pwr = turn_1_board_power

            # Economy
            remaining_gold = start_gold - spent_gold
            interest = min(5, remaining_gold // 10)
            end_gold = remaining_gold + interest + 5

            # Combat damage (with improved board power!)
            stage_expected_power, stage_base_damage = self._get_stage_combat_params(cur_stage)
            loss_prob, hp_loss = self._calculate_combat_outcome(board_pwr, stage_expected_power, stage_base_damage)
            cur_hp = max(0, cur_hp - hp_loss)

            turn_details.append(TurnDetail(
                turn=t,
                action_executed=f"ROLL ({num_rolls} rolls)" if t == 1 else "PASSIVE",
                start_gold=start_gold,
                spent_gold=spent_gold,
                end_gold=end_gold,
                start_level=start_lvl,
                end_level=cur_level,
                start_xp=start_xp,
                end_xp=cur_xp,
                interest_earned=interest,
                base_gold_earned=5,
                hp_loss=hp_loss,
                resulting_hp=cur_hp,
                board_power=board_pwr,
                hit_probability=any_upgrade_prob if t == 1 else 0.05,
                notes=f"Rolls: {num_rolls}, Expected Power: +{power_gain:.1f}" if t == 1 else ""
            ))

            cur_gold = end_gold
            cur_round += 1
            if cur_round > 7:
                cur_stage += 1
                cur_round = 1

        survival_score = self._calculate_survival_score(cur_hp)

        return SimulationResult(
            action=action,
            horizon=horizon,
            expected_gold=float(cur_gold),
            expected_hp=float(cur_hp),
            expected_board_power=turn_1_board_power,
            any_upgrade_probability=round(upgrade_prob_cumulative, 4),
            target_upgrade_probabilities=target_probs,
            expected_upgrade_count=round(exp_upg_count, 3),
            survival_score=round(survival_score, 4),
            estimated_placement=None,
            turn_by_turn=turn_details,
            metadata={"strategy": "ROLL", "num_rolls": num_rolls, "power_gain": power_gain}
        )

    # -------------------------------------------------------------------------
    # HELPER FORMULAS & COMBAT MODELING
    # -------------------------------------------------------------------------
    def _get_stage_combat_params(self, stage: int) -> Tuple[float, int]:
        """스테이지별 기대 기준 보드 파워 및 기본 패배 데미지 반환."""
        stage_powers = {1: 8.0, 2: 18.0, 3: 35.0, 4: 55.0, 5: 75.0, 6: 95.0, 7: 120.0}
        stage_losses = {1: 2, 2: 4, 3: 7, 4: 10, 5: 14, 6: 18, 7: 24}
        return stage_powers.get(stage, 55.0), stage_losses.get(stage, 10)

    def _calculate_combat_outcome(self, current_power: float, target_power: float, base_damage: int) -> Tuple[float, int]:
        """보드 파워 비교에 따른 패배 확률 및 기대 HP 감소량 산출."""
        diff = target_power - current_power
        loss_prob = 1.0 / (1.0 + math.exp(-diff / 12.0))
        loss_prob = min(0.95, max(0.05, loss_prob))

        if current_power >= target_power:
            damage_mult = max(0.0, 1.0 - (current_power - target_power) / max(1.0, target_power))
            expected_damage = int(round(loss_prob * base_damage * damage_mult * 0.5))
        else:
            power_ratio = max(0.1, current_power / max(1.0, target_power))
            damage_mult = min(1.3, max(0.5, 1.4 - power_ratio))
            expected_damage = int(round(loss_prob * base_damage * damage_mult))

        return loss_prob, max(0, expected_damage)

    def _calculate_survival_score(self, final_hp: int) -> float:
        """최종 HP 기반 생존 휴리스틱 점수 산출 (통계적 확률이 아닌 정량화된 지표)."""
        if final_hp <= 0:
            return 0.0
        elif final_hp <= 12:
            return 0.20
        elif final_hp <= 25:
            return 0.55
        elif final_hp <= 50:
            return 0.80
        else:
            return 0.98

    def _evaluate_level_up_power_gain(self, state: GameState, new_level: int) -> float:
        """레벨업 시 Whole-Board Power 증가분 산출 (BoardEvaluator 활용)."""
        base_power = self.board_evaluator.evaluate(state).score
        if state.bench_units:
            # Pick strongest bench unit to place on board
            sorted_bench = sorted(
                state.bench_units,
                key=lambda u: u.cost * (2.2 if u.star_level == 2 else 1.0),
                reverse=True
            )
            promoted_unit = sorted_bench[0]
            simulated_board_units = list(state.board_units) + [promoted_unit]
            simulated_state = state.with_updates(board_units=simulated_board_units)
            new_power = self.board_evaluator.evaluate(simulated_state).score
            return max(1.0, round(new_power - base_power, 2))
        
        # Empty bench: standard tier average
        avg_cost = 1 if new_level <= 4 else (2 if new_level <= 6 else (3 if new_level <= 7 else 4))
        return float(avg_cost * 1.0 + 2.0)

    def _calculate_roll_upgrades(
        self, state: GameState, level: int, num_rolls: int
    ) -> Tuple[float, Dict[str, float], float, float]:
        """수학적으로 엄밀한 유닛별/통합 업그레이드 확률 및 Whole-Board Power 증가분 산출.
        
        Returns:
            (any_upgrade_prob, target_upgrade_probs, expected_upgrade_count, expected_power_gain)
        """
        if num_rolls <= 0:
            return 0.0, {}, 0.0, 0.0

        slots = 5 * num_rolls
        base_board_power = self.board_evaluator.evaluate(state).score

        # 1. Count copies across board & bench
        champ_counts: Dict[str, Tuple[int, int]] = {} # name -> (total_copies, cost)
        for u in state.board_units + state.bench_units:
            copies = 3 if u.star_level == 2 else (1 if u.star_level == 1 else 9)
            if u.champion in champ_counts:
                prev_copies, cost = champ_counts[u.champion]
                champ_counts[u.champion] = (prev_copies + copies, cost)
            else:
                cinfo = self.data_repo.get_champion(u.champion)
                cost = cinfo["cost"] if cinfo else u.cost
                champ_counts[u.champion] = (copies, cost)

        target_probs: Dict[str, float] = {}
        expected_power_gain = 0.0
        exp_upgrade_count = 0.0
        combined_1need_p_slot = 0.0

        for name, (copies, cost) in champ_counts.items():
            n_variety = self.data_repo.get_champion_count_by_cost(cost)
            drop_rate = self.data_repo.get_drop_rate(level, cost)
            if drop_rate <= 0:
                continue

            k_c = self.data_repo.get_pool_size(cost)
            # Pool depletion tracking (copies already held)
            rem_target = max(0, k_c - copies)
            rem_tier = max(1, (k_c * n_variety) - copies)
            p_slot = drop_rate * (rem_target / rem_tier)

            if copies == 2: # Pair -> 1 copy needed for 2★
                # Exact analytical single target probability: 1 - (1 - p_slot)^slots
                p_hit = 1.0 - ((1.0 - p_slot) ** slots)
                target_probs[name] = round(p_hit, 4)
                combined_1need_p_slot += p_slot
                exp_upgrade_count += p_hit

                # Calculate whole-board power delta by simulating 2★ upgrade
                simulated_board_units = []
                upgraded = False
                for u in state.board_units:
                    if u.champion == name and u.star_level == 1 and not upgraded:
                        simulated_board_units.append(Unit(champion=name, cost=cost, star_level=2, items=list(u.items)))
                        upgraded = True
                    else:
                        simulated_board_units.append(u)
                if not upgraded: # Champion was on bench
                    simulated_board_units.append(Unit(champion=name, cost=cost, star_level=2))

                sim_state = state.with_updates(board_units=simulated_board_units)
                upgraded_board_power = self.board_evaluator.evaluate(sim_state).score
                power_delta = max(1.0, upgraded_board_power - base_board_power)
                expected_power_gain += p_hit * power_delta

            elif copies == 1: # Single copy -> 2 copies needed
                # Binomial approx for >= 2 hits in slots
                p_hit_1 = 1.0 - ((1.0 - p_slot) ** slots)
                p_hit_2 = max(0.0, p_hit_1 * p_hit_1 * 0.65)
                target_probs[name] = round(p_hit_2, 4)
                exp_upgrade_count += p_hit_2
                power_delta = cost * 1.2
                expected_power_gain += p_hit_2 * power_delta

        if not target_probs:
            # Baseline 4-cost / 5-cost hit probability if no explicit pairs exist
            p_4cost = self.data_repo.get_drop_rate(level, 4)
            p_slot_4 = p_4cost / 13.0
            p_hit = 1.0 - ((1.0 - p_slot_4) ** slots)
            return round(p_hit, 4), {"4-Cost Carry": round(p_hit, 4)}, round(p_hit, 3), round(p_hit * 5.0, 2)

        # Joint Probability of hitting at least one upgrade:
        # Mathematically exact joint probability for collision in same slots:
        # P(any of 1-need targets) = 1 - (1 - sum(p_slot))^slots
        if combined_1need_p_slot > 0:
            any_upgrade_prob = 1.0 - ((1.0 - min(0.9999, combined_1need_p_slot)) ** slots)
        else:
            prob_miss_all = 1.0
            for p in target_probs.values():
                prob_miss_all *= (1.0 - p)
            any_upgrade_prob = 1.0 - prob_miss_all

        return (
            round(min(1.0, any_upgrade_prob), 4),
            target_probs,
            round(exp_upgrade_count, 3),
            round(expected_power_gain, 2)
        )
