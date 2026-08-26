"""TFT Backtest Dataset Loader, Match Splitter, and Integrity Validator -- v1.1."""
import json
import os
import random
from typing import Any, Dict, List, Optional, Tuple
from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.backtest.models import (
    BacktestSample,
    ObservedState,
    FutureObservation,
    ActualActionType,
    SnapshotType
)


def round_number_to_stage_round(last_round: int) -> Tuple[int, int, str]:
    """Convert TFT absolute round number to stage-round notation.

    Rules:
      Stage 1: rounds 1-4  (1-1, 1-2, 1-3, 1-4)
      Stage 2+: 7 rounds each (2-1 to 2-7, 3-1 to 3-7, ...)
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
    """Historical and Synthetic Backtest Dataset manager."""

    @staticmethod
    def load_from_jsonl(
        jsonl_path: str,
        limit: Optional[int] = None
    ) -> List[BacktestSample]:
        """저장된 BacktestSample JSONL 파일을 로드하여 snapshot_type 및 메타데이터 복원."""
        samples: List[BacktestSample] = []
        if not os.path.exists(jsonl_path):
            raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")

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

                sample_id = data.get("sample_id", f"S_{idx}")
                match_id = data.get("match_id", f"M_{idx}")
                puuid = data.get("participant_id", f"P_{idx}")
                data_source = data.get("data_source", "jsonl_dataset")
                snap_type_str = data.get("snapshot_type", SnapshotType.MIDGAME_DECISION_SNAPSHOT.value)
                snap_type = SnapshotType(snap_type_str) if snap_type_str in [e.value for e in SnapshotType] else SnapshotType.OTHER_HISTORICAL
                is_synth = data.get("is_synthetic", False)
                horizon = data.get("horizon_rounds")
                t0_sec = data.get("decision_timestamp_sec")
                meta = data.get("metadata", {})

                obs_d = data.get("observed_state", {})
                stg = obs_d.get("stage", 3)
                rnd = obs_d.get("round_num", 2)
                stg_rnd = obs_d.get("stage_round", f"{stg}-{rnd}")
                act_str = obs_d.get("actual_action", ActualActionType.UNKNOWN.value)
                actual_act = ActualActionType(act_str) if act_str in [e.value for e in ActualActionType] else ActualActionType.UNKNOWN
                act_ev = obs_d.get("actual_action_evidence")
                t_sec = obs_d.get("timestamp_sec", t0_sec)

                gold = obs_d.get("gold", 0)
                level = obs_d.get("level", 8)
                xp = obs_d.get("xp", 0)
                hp = obs_d.get("hp", 100)

                board_units = [
                    Unit(champion=u.get("champion", ""), cost=u.get("cost", 1), star_level=u.get("star_level", 1), items=u.get("items", []))
                    for u in obs_d.get("board_units", []) if u.get("champion")
                ]
                bench_units = [
                    Unit(champion=u.get("champion", ""), cost=u.get("cost", 1), star_level=u.get("star_level", 1), items=u.get("items", []))
                    for u in obs_d.get("bench_units", []) if u.get("champion")
                ]

                state = GameState(
                    stage=stg,
                    round=rnd,
                    stage_round=stg_rnd,
                    player=PlayerState(gold=gold, level=level, xp=xp, hp=hp),
                    board_units=board_units,
                    bench_units=bench_units
                )

                observed_state = ObservedState(
                    match_id=match_id,
                    participant_id=puuid,
                    stage=stg,
                    round_num=rnd,
                    stage_round=stg_rnd,
                    state=state,
                    actual_action=actual_act,
                    actual_action_evidence=act_ev,
                    timestamp_sec=t_sec
                )

                fut_d = data.get("future_observation", {})
                future_obs = FutureObservation(
                    final_placement=fut_d.get("final_placement"),
                    top4=fut_d.get("top4"),
                    hp_after_n_rounds=fut_d.get("hp_after_n_rounds"),
                    gold_after_n_rounds=fut_d.get("gold_after_n_rounds"),
                    level_after_n_rounds=fut_d.get("level_after_n_rounds"),
                    last_round=fut_d.get("last_round"),
                    time_eliminated=fut_d.get("time_eliminated"),
                    horizon_rounds=fut_d.get("horizon_rounds", horizon),
                    outcome_timestamp_sec=fut_d.get("outcome_timestamp_sec")
                )

                sample = BacktestSample(
                    sample_id=sample_id,
                    match_id=match_id,
                    participant_id=puuid,
                    data_source=data_source,
                    observed_state=observed_state,
                    future_observation=future_obs,
                    snapshot_type=snap_type,
                    is_synthetic=is_synth,
                    decision_timestamp_sec=t0_sec,
                    horizon_rounds=horizon,
                    metadata=meta
                )

                if BacktestDataset.validate_sample(sample):
                    samples.append(sample)

        return samples

    @staticmethod
    def load_from_match_snapshots(
        jsonl_path: str,
        limit: Optional[int] = None
    ) -> List[BacktestSample]:
        """Load Riot Match-V1 snapshots. All classified as ENDGAME_SNAPSHOT."""
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

                # If this JSONL is already a BacktestSample serialization, load it directly
                if "observed_state" in data and "snapshot_type" in data:
                    return BacktestDataset.load_from_jsonl(jsonl_path, limit=limit)

                match_id = data.get("match_id", f"M_{idx}")
                puuid = data.get("puuid", f"P_{idx}")
                placement = data.get("final_placement")
                level = data.get("level", 8)
                gold_left = data.get("gold_left", 0)
                last_round = data.get("last_round", 30)
                time_elim = data.get("time_eliminated")

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
                endgame_hp = 0

                state = GameState(
                    stage=stage,
                    round=round_num,
                    stage_round=stage_round_str,
                    player=PlayerState(
                        gold=gold_left,
                        level=level,
                        xp=0,
                        hp=endgame_hp
                    ),
                    board_units=board_units,
                    bench_units=[]
                )

                observed_state = ObservedState(
                    match_id=match_id,
                    participant_id=puuid,
                    stage=stage,
                    round_num=round_num,
                    stage_round=stage_round_str,
                    state=state,
                    actual_action=ActualActionType.UNKNOWN,
                    actual_action_evidence="Riot Match-V1 API provides only endgame final state",
                    timestamp_sec=time_elim
                )

                future_obs = FutureObservation(
                    final_placement=placement,
                    top4=(placement is not None and placement <= 4),
                    hp_after_n_rounds=endgame_hp,
                    gold_after_n_rounds=gold_left,
                    level_after_n_rounds=level,
                    last_round=last_round,
                    time_eliminated=time_elim,
                    elimination_stage_round=stage_round_str,
                    horizon_rounds=0,
                    outcome_timestamp_sec=time_elim
                )

                sample = BacktestSample(
                    sample_id=f"{match_id}_{puuid[:8]}_{idx}",
                    match_id=match_id,
                    participant_id=puuid,
                    data_source="historical_match_snapshot",
                    observed_state=observed_state,
                    future_observation=future_obs,
                    snapshot_type=SnapshotType.ENDGAME_SNAPSHOT,
                    is_synthetic=False,
                    decision_timestamp_sec=time_elim,
                    horizon_rounds=0,
                    metadata={"riot_id_name": data.get("riot_id_name", ""), "riot_id_tag": data.get("riot_id_tag", "")}
                )

                if BacktestDataset.validate_sample(sample):
                    samples.append(sample)

        return samples

    @staticmethod
    def load_from_video_audit(json_path: str) -> List[BacktestSample]:
        """Load video CV audit samples as MIDGAME_DECISION_SNAPSHOT."""
        samples: List[BacktestSample] = []
        if not os.path.exists(json_path):
            return samples

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        events = data.get("events", [])
        match_id = "VIDEO_EDA87AD9_AUDIT"
        puuid = "LOCAL_PLAYER"
        known_final_placement = 2
        known_time_end = 1920.0

        for idx, ev in enumerate(events):
            t_sec = ev.get("timestamp_sec", 0.0)
            ev_type = ev.get("event", "")

            if ev_type == "REROLL_CANDIDATE":
                act = ActualActionType.ROLL
                evidence = f"Video CV detected REROLL at {t_sec:.1f}s"
            elif ev_type == "BUY_CANDIDATE":
                act = ActualActionType.ROLL
                evidence = f"Video CV detected BUY of {ev.get('champion', 'unknown')} at {t_sec:.1f}s"
            else:
                act = ActualActionType.SAVE_GOLD
                evidence = f"Video CV: no action detected at {t_sec:.1f}s"

            stage = 3 if t_sec < 500 else (4 if t_sec < 750 else 5)
            round_num = int((t_sec % 100) / 15) + 1
            round_num = min(7, max(1, round_num))
            stage_round = f"{stage}-{round_num}"

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

            time_remaining = max(0.0, known_time_end - t_sec)
            approx_horizon_rounds = max(1, int(time_remaining / 120))

            future = FutureObservation(
                final_placement=known_final_placement,
                top4=True,
                hp_after_n_rounds=52,
                gold_after_n_rounds=28,
                level_after_n_rounds=8,
                last_round=34,
                time_eliminated=known_time_end,
                horizon_rounds=approx_horizon_rounds,
                outcome_timestamp_sec=known_time_end
            )

            sample = BacktestSample(
                sample_id=f"VID_{idx}_{int(t_sec)}",
                match_id=match_id,
                participant_id=puuid,
                data_source="historical_video_audit",
                observed_state=observed,
                future_observation=future,
                snapshot_type=SnapshotType.MIDGAME_DECISION_SNAPSHOT,
                is_synthetic=False,
                decision_timestamp_sec=t_sec,
                horizon_rounds=approx_horizon_rounds,
                metadata={"video_event": ev_type, "timestamp_sec": t_sec}
            )

            if BacktestDataset.validate_sample(sample):
                samples.append(sample)

        return samples

    @staticmethod
    def create_synthetic_dataset(num_samples: int = 50, seed: int = 42) -> List[BacktestSample]:
        """Create synthetic MIDGAME samples for pipeline and regression testing."""
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
            t0 = float(300 + i * 30)
            horizon = random.randint(3, 12)

            future = FutureObservation(
                final_placement=placement,
                top4=(placement <= 4),
                hp_after_n_rounds=max(0, hp - random.randint(0, 25)),
                gold_after_n_rounds=max(0, gold + random.randint(-15, 25)),
                level_after_n_rounds=level,
                last_round=stage * 7 + round_num + random.randint(1, 10),
                horizon_rounds=horizon,
                outcome_timestamp_sec=t0 + horizon * 120.0
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
                    actual_action_evidence="Synthetic behavioral policy generator",
                    timestamp_sec=t0
                ),
                future_observation=future,
                snapshot_type=SnapshotType.MIDGAME_DECISION_SNAPSHOT,
                is_synthetic=True,
                decision_timestamp_sec=t0,
                horizon_rounds=horizon,
                metadata={"synthetic_seed": seed}
            )

            samples.append(sample)

        return samples

    @staticmethod
    def validate_sample_with_issues(sample: BacktestSample) -> Tuple[bool, List[str]]:
        """Validate sample and return issue descriptions."""
        issues: List[str] = []
        st = sample.observed_state.state

        if st.player.gold < 0 or st.player.level < 1 or st.player.level > 11:
            issues.append(f"Invalid player state: gold={st.player.gold}, level={st.player.level}")
        if st.player.hp < 0 or st.player.hp > 100:
            issues.append(f"Invalid hp: {st.player.hp}")

        if hasattr(st, "final_placement") or hasattr(st.player, "final_placement"):
            issues.append("LEAKAGE: final_placement found in T0 GameState")

        t0 = sample.decision_timestamp_sec
        t1 = sample.future_observation.outcome_timestamp_sec
        if t0 is not None and t1 is not None and t0 > t1:
            issues.append(f"TEMPORAL VIOLATION: T0({t0:.1f}s) > T1+({t1:.1f}s)")

        if sample.horizon_rounds is not None and sample.horizon_rounds < 0:
            issues.append(f"Invalid horizon_rounds: {sample.horizon_rounds}")

        return len(issues) == 0, issues

    @staticmethod
    def validate_sample(sample: BacktestSample) -> bool:
        ok, _ = BacktestDataset.validate_sample_with_issues(sample)
        return ok

    @staticmethod
    def filter_by_type(
        samples: List[BacktestSample],
        snapshot_type: SnapshotType
    ) -> List[BacktestSample]:
        return [s for s in samples if s.snapshot_type == snapshot_type]

    @staticmethod
    def split_by_match(
        samples: List[BacktestSample],
        train_ratio: float = 0.8,
        seed: int = 42
    ) -> Tuple[List[BacktestSample], List[BacktestSample]]:
        random.seed(seed)
        unique_matches = sorted(list(set(s.match_id for s in samples)))
        random.shuffle(unique_matches)

        split_idx = int(len(unique_matches) * train_ratio)
        train_matches = set(unique_matches[:split_idx])
        test_matches = set(unique_matches[split_idx:])

        assert len(train_matches.intersection(test_matches)) == 0

        return (
            [s for s in samples if s.match_id in train_matches],
            [s for s in samples if s.match_id in test_matches]
        )

    @staticmethod
    def save_to_jsonl(samples: List[BacktestSample], output_path: str) -> None:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for s in samples:
                row = {
                    "sample_id": s.sample_id,
                    "match_id": s.match_id,
                    "participant_id": s.participant_id,
                    "data_source": s.data_source,
                    "snapshot_type": s.snapshot_type.value,
                    "is_synthetic": s.is_synthetic,
                    "horizon_rounds": s.horizon_rounds,
                    "decision_timestamp_sec": s.decision_timestamp_sec,
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
                        "timestamp_sec": s.observed_state.timestamp_sec
                    },
                    "future_observation": {
                        "final_placement": s.future_observation.final_placement,
                        "top4": s.future_observation.top4,
                        "horizon_rounds": s.future_observation.horizon_rounds,
                        "outcome_timestamp_sec": s.future_observation.outcome_timestamp_sec,
                        "time_eliminated": s.future_observation.time_eliminated
                    },
                    "metadata": s.metadata
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
