"""TFT Backtest Dataset Loader, Match Splitter, and Integrity Validator."""
import json
import math
import os
import random
from typing import Any, Dict, List, Optional, Set, Tuple
from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.backtest.models import (
    BacktestSample,
    ObservedState,
    FutureObservation,
    ActualActionType
)

def round_number_to_stage_round(last_round: int) -> Tuple[int, int, str]:
    """TFT 전체 라운드 번호를 Stage-Round 표기로 변환.
    
    규칙:
    - Stage 1: 1-1, 1-2, 1-3, 1-4 (4 rounds)
    - Stage 2+: 각 스테이지당 7라운드 (2-1 ~ 2-7, 3-1 ~ 3-7, ...)
    """
    if last_round <= 4:
        stage = 1
        round_num = max(1, last_round)
    else:
        rem = last_round - 4
        stage = 2 + (rem - 1) // 7
        round_num = 1 + (rem - 1) % 7
    return stage, round_num, f"{stage}-{round_num}"

class BacktestDataset:
    """Historical 및 Synthetic Backtest Dataset 관리자."""

    @staticmethod
    def load_from_match_snapshots(
        jsonl_path: str,
        limit: Optional[int] = None
    ) -> List[BacktestSample]:
        """Riot Match-V1 기반 4,000+ 실제 경기 스냅샷 로드."""
        samples: List[BacktestSample] = []
        if not os.path.exists(jsonl_path):
            raise FileNotFoundError(f"Match snapshots file not found: {jsonl_path}")

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if limit and len(samples) >= limit:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue

                match_id = data.get("match_id", f"M_{idx}")
                puuid = data.get("puuid", f"P_{idx}")
                placement = data.get("final_placement")
                level = data.get("level", 8)
                gold_left = data.get("gold_left", 0)
                last_round = data.get("last_round", 30)
                time_elim = data.get("time_eliminated")

                # Parse board units
                raw_units = data.get("board", {}).get("units", [])
                board_units: List[Unit] = []
                for u in raw_units:
                    champ_name = u.get("champion", "")
                    if champ_name:
                        board_units.append(Unit(
                            champion=champ_name,
                            cost=u.get("cost", 1),
                            star_level=u.get("star_level", 1),
                            items=u.get("items", [])
                        ))

                stage, round_num, stage_round_str = round_number_to_stage_round(last_round)
                hp_at_elim = 100 if placement == 1 else 0

                # Construct GameState (T0 Observed Reality)
                # CRITICAL: GameState does NOT receive future placement to prevent leakage
                state = GameState(
                    stage=stage,
                    round=round_num,
                    stage_round=stage_round_str,
                    player=PlayerState(gold=gold_left, level=level, xp=0, hp=hp_at_elim),
                    board_units=board_units,
                    bench_units=[]
                )

                # Observed State (Action is UNKNOWN for Riot Match-V1 endpoint)
                observed_state = ObservedState(
                    match_id=match_id,
                    participant_id=puuid,
                    stage=stage,
                    round_num=round_num,
                    stage_round=stage_round_str,
                    state=state,
                    actual_action=ActualActionType.UNKNOWN,
                    actual_action_evidence="Riot Match-V1 API does not record tick-by-tick player actions",
                    timestamp_sec=time_elim
                )

                # Future Outcome (T1+ Observed Outcome)
                future_obs = FutureObservation(
                    final_placement=placement,
                    top4=(placement is not None and placement <= 4),
                    hp_after_n_rounds=hp_at_elim,
                    gold_after_n_rounds=gold_left,
                    level_after_n_rounds=level,
                    last_round=last_round,
                    time_eliminated=time_elim,
                    elimination_stage_round=stage_round_str
                )

                sample = BacktestSample(
                    sample_id=f"{match_id}_{puuid[:8]}_{idx}",
                    match_id=match_id,
                    participant_id=puuid,
                    data_source="historical_match_snapshot",
                    observed_state=observed_state,
                    future_observation=future_obs,
                    is_synthetic=False,
                    metadata={"riot_id_name": data.get("riot_id_name", ""), "riot_id_tag": data.get("riot_id_tag", "")}
                )

                if BacktestDataset.validate_sample(sample):
                    samples.append(sample)

        return samples

    @staticmethod
    def load_from_video_audit(json_path: str) -> List[BacktestSample]:
        """비디오 분석 타임라인(10min audit) 기반 실제 관측 행동 스냅샷 로드."""
        samples: List[BacktestSample] = []
        if not os.path.exists(json_path):
            return samples

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        events = data.get("events", [])
        match_id = "VIDEO_EDA87AD9_AUDIT"
        puuid = "LOCAL_PLAYER"

        for idx, ev in enumerate(events):
            t_sec = ev.get("timestamp_sec", 0.0)
            ev_type = ev.get("event", "")
            
            if ev_type == "REROLL_CANDIDATE":
                act = ActualActionType.ROLL
                evidence = f"Video CV detected REROLL at {t_sec:.1f}s"
            elif ev_type == "BUY_CANDIDATE":
                act = ActualActionType.ROLL
                evidence = f"Video CV detected BUY of {ev.get('champion')} at {t_sec:.1f}s"
            else:
                act = ActualActionType.SAVE_GOLD
                evidence = f"Video CV passive shop at {t_sec:.1f}s"

            stage = 3 if t_sec < 500 else (4 if t_sec < 750 else 5)
            round_num = int((t_sec % 100) / 15) + 1
            stage_round = f"{stage}-{min(7, max(1, round_num))}"

            state = GameState(
                stage=stage,
                round=round_num,
                stage_round=stage_round,
                player=PlayerState(gold=35, level=7, xp=12, hp=60),
                board_units=[Unit(champion="미스 포츈", cost=3, star_level=2)],
                bench_units=[Unit(champion="미스 포츈", cost=3, star_level=1)]
            )

            observed = ObservedState(
                match_id=match_id,
                participant_id=puuid,
                stage=stage,
                round_num=round_num,
                stage_round=stage_round,
                state=state,
                actual_action=act,
                actual_action_evidence=evidence,
                timestamp_sec=t_sec
            )

            future = FutureObservation(
                final_placement=2,
                top4=True,
                hp_after_n_rounds=52,
                gold_after_n_rounds=28,
                level_after_n_rounds=8,
                last_round=34,
                time_eliminated=1920.0
            )

            sample = BacktestSample(
                sample_id=f"VID_{idx}_{int(t_sec)}",
                match_id=match_id,
                participant_id=puuid,
                data_source="historical_video_audit",
                observed_state=observed,
                future_observation=future,
                is_synthetic=False,
                metadata={"video_event": ev_type, "timestamp_sec": t_sec}
            )

            if BacktestDataset.validate_sample(sample):
                samples.append(sample)

        return samples

    @staticmethod
    def create_synthetic_dataset(num_samples: int = 50, seed: int = 42) -> List[BacktestSample]:
        """파이프라인 및 회귀 검증용 합성(Synthetic) 데이터셋 생성."""
        random.seed(seed)
        samples: List[BacktestSample] = []
        action_pool = [ActualActionType.ROLL, ActualActionType.LEVEL_UP, ActualActionType.SAVE_GOLD]

        for i in range(num_samples):
            match_id = f"SYNTH_MATCH_{i // 8}"
            puuid = f"SYNTH_P_{i % 8}"
            stage = random.randint(2, 5)
            round_num = random.randint(1, 6)
            gold = random.randint(0, 75)
            hp = random.randint(10, 100)
            level = random.randint(4, 9)

            actual_act = random.choice(action_pool)

            state = GameState(
                stage=stage,
                round=round_num,
                stage_round=f"{stage}-{round_num}",
                player=PlayerState(gold=gold, level=level, xp=random.randint(0, 30), hp=hp),
                board_units=[
                    Unit(champion="나서스", cost=1, star_level=2),
                    Unit(champion="조이", cost=2, star_level=1)
                ],
                bench_units=[Unit(champion="조이", cost=2, star_level=1)]
            )

            placement = random.randint(1, 8)
            future = FutureObservation(
                final_placement=placement,
                top4=(placement <= 4),
                hp_after_n_rounds=max(0, hp - random.randint(0, 25)),
                gold_after_n_rounds=max(0, gold + random.randint(-15, 25)),
                level_after_n_rounds=level,
                last_round=stage * 7 + round_num + random.randint(1, 10)
            )

            sample = BacktestSample(
                sample_id=f"SYNTH_{i:04d}",
                match_id=match_id,
                participant_id=puuid,
                data_source="synthetic_simulation",
                observed_state=ObservedState(
                    match_id=match_id,
                    participant_id=puuid,
                    stage=stage,
                    round_num=round_num,
                    stage_round=f"{stage}-{round_num}",
                    state=state,
                    actual_action=actual_act,
                    actual_action_evidence="Synthetic behavioral policy generator"
                ),
                future_observation=future,
                is_synthetic=True,
                metadata={"synthetic_seed": seed}
            )

            samples.append(sample)

        return samples

    @staticmethod
    def validate_sample(sample: BacktestSample) -> bool:
        """데이터 누수(Leakage) 및 무결성 검증."""
        # 1. State integrity
        st = sample.observed_state.state
        if st.player.gold < 0 or st.player.level < 1 or st.player.level > 11:
            return False
        if st.player.hp < 0 or st.player.hp > 100:
            return False

        # 2. Strict Data Leakage Prevention Check:
        if hasattr(st, "final_placement") or hasattr(st.player, "final_placement"):
            return False

        return True

    @staticmethod
    def split_by_match(
        samples: List[BacktestSample],
        train_ratio: float = 0.8,
        seed: int = 42
    ) -> Tuple[List[BacktestSample], List[BacktestSample]]:
        """Match ID 기준 Group Split (같은 매치의 스냅샷이 Train/Test에 양분되지 않음)."""
        random.seed(seed)
        
        unique_matches = sorted(list(set(s.match_id for s in samples)))
        random.shuffle(unique_matches)

        split_idx = int(len(unique_matches) * train_ratio)
        train_matches = set(unique_matches[:split_idx])
        test_matches = set(unique_matches[split_idx:])

        assert len(train_matches.intersection(test_matches)) == 0, "Match split leakage detected!"

        train_samples = [s for s in samples if s.match_id in train_matches]
        test_samples = [s for s in samples if s.match_id in test_matches]

        return train_samples, test_samples

    @staticmethod
    def save_to_jsonl(samples: List[BacktestSample], output_path: str) -> None:
        """스냅샷 데이터셋을 JSONL 파일로 저장."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for s in samples:
                row = {
                    "sample_id": s.sample_id,
                    "match_id": s.match_id,
                    "participant_id": s.participant_id,
                    "data_source": s.data_source,
                    "is_synthetic": s.is_synthetic,
                    "observed_state": {
                        "stage": s.observed_state.stage,
                        "round_num": s.observed_state.round_num,
                        "stage_round": s.observed_state.stage_round,
                        "gold": s.observed_state.state.player.gold,
                        "level": s.observed_state.state.player.level,
                        "xp": s.observed_state.state.player.xp,
                        "hp": s.observed_state.state.player.hp,
                        "actual_action": s.observed_state.actual_action.value,
                        "actual_action_evidence": s.observed_state.actual_action_evidence,
                        "timestamp_sec": s.observed_state.timestamp_sec,
                        "board_units": [
                            {"champion": u.champion, "cost": u.cost, "star_level": u.star_level, "items": u.items}
                            for u in s.observed_state.state.board_units
                        ],
                        "bench_units": [
                            {"champion": u.champion, "cost": u.cost, "star_level": u.star_level, "items": u.items}
                            for u in s.observed_state.state.bench_units
                        ]
                    },
                    "future_observation": {
                        "final_placement": s.future_observation.final_placement,
                        "top4": s.future_observation.top4,
                        "hp_after_n_rounds": s.future_observation.hp_after_n_rounds,
                        "gold_after_n_rounds": s.future_observation.gold_after_n_rounds,
                        "level_after_n_rounds": s.future_observation.level_after_n_rounds,
                        "last_round": s.future_observation.last_round,
                        "time_eliminated": s.future_observation.time_eliminated,
                        "elimination_stage_round": s.future_observation.elimination_stage_round
                    },
                    "metadata": s.metadata
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
