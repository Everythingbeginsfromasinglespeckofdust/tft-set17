#!/usr/bin/env python3
"""test_train_placement_model.py — M2B 머신러닝 파이프라인 단위 테스트."""
import os
import sys
import tempfile
import joblib
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ECONOMY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "economy")
if _ECONOMY not in sys.path:
    sys.path.insert(0, _ECONOMY)

import train_placement_model as tpm


def _create_mock_records(num_matches=10):
    records = []
    for m in range(num_matches):
        mid = f"KR_MOCK_{m}"
        for p in range(1, 9):
            star = 2 if p <= 4 else 1
            cost = 5 if p <= 2 else (4 if p <= 4 else 1)
            records.append({
                "match_id": mid,
                "puuid": f"puuid_{m}_{p}",
                "final_placement": p,
                "level": 9 if p <= 4 else 7,
                "gold_left": 10 * p,
                "board": {
                    "units": [
                        {"champion": "진" if cost == 5 else ("나미" if cost == 4 else "나서스"), "cost": cost, "star_level": star, "items": ["무한의 대검"] if p <= 4 else []}
                    ]
                }
            })
    return records


def test_extract_dataset():
    records = _create_mock_records(2)
    df = tpm.extract_dataset(records)
    assert len(df) == 16
    for col in tpm.FEATURE_COLUMNS:
        assert col in df.columns
    assert "final_placement" in df.columns
    assert "match_id" in df.columns


def test_split_by_match_group_leak_free():
    records = _create_mock_records(20)
    df = tpm.extract_dataset(records)
    train_df, test_df = tpm.split_by_match_group(df, test_ratio=0.2, random_state=42)

    train_mids = set(train_df["match_id"])
    test_mids = set(test_df["match_id"])

    assert len(train_mids & test_mids) == 0
    assert len(test_mids) == 4
    assert len(train_mids) == 16
    assert len(train_df) == 16 * 8
    assert len(test_df) == 4 * 8


def test_baseline_correlation_negative():
    records = _create_mock_records(20)
    df = tpm.extract_dataset(records)
    stats = tpm.analyze_baseline(df)
    assert stats["spearman_corr"] < 0.0
    assert stats["rank_diff"] > 0.0


def test_train_and_evaluate_pipeline():
    records = _create_mock_records(25)
    df = tpm.extract_dataset(records)
    train_df, test_df = tpm.split_by_match_group(df, test_ratio=0.2, random_state=42)

    model = tpm.train_placement_model(train_df)
    metrics = tpm.evaluate_model(model, test_df)

    assert metrics["mae_ranked"] >= 0.0
    assert 0.0 <= metrics["top4_accuracy"] <= 100.0
    assert len(metrics["feature_importances"]) == len(tpm.FEATURE_COLUMNS)


def test_saved_model_artifact_loadable():
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_v1.pkl")
    if os.path.exists(model_path):
        artifact = joblib.load(model_path)
        assert "model" in artifact
        assert "feature_columns" in artifact
        assert "eval_metrics" in artifact
        
        dummy_df = pd.DataFrame(np.zeros((1, len(artifact["feature_columns"]))), columns=artifact["feature_columns"])
        pred = artifact["model"].predict(dummy_df)
        assert len(pred) == 1
