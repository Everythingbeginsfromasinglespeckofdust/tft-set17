# 🛰️ TFT Decision Engine Production Shadow Mode Specification v1

## 1. 목적 (Purpose)
`CALIB_C` (Percentile Risk Mapping)가 독립 검증을 통과하여 `READY_FOR_PRODUCTION_INTEGRATION` 판정을 획득함에 따라, **실제 Production UI 추천을 변경하지 않고 백그라운드 로그로만 기록하는 Shadow Mode**를 배포할 수 있는 표준 명세를 정의합니다.

## 2. Shadow Architecture
```text
Real GameState (Vision Pipeline)
        │
        ├──▶ Production DecisionEngine ──▶ Visible Recommendation (Overlay UI)
        │
        └──▶ CALIB_C Experimental Layer ──▶ Shadow Recommendation ──▶ shadow_logs.jsonl
```

## 3. Shadow Logging Schema
```json
{
  "timestamp_iso": "2026-08-27T05:00:00Z",
  "match_id": "MATCH_LOCAL_01",
  "stage_round": "4-1",
  "player_state": {"gold": 32, "hp": 24, "level": 7},
  "production_action": "SAVE_GOLD",
  "production_scores": {"ROLL": 0.42, "LEVEL_UP": 0.12, "SAVE_GOLD": 0.46},
  "shadow_action": "ROLL",
  "shadow_scores": {"ROLL": 0.51, "LEVEL_UP": 0.10, "SAVE_GOLD": 0.39},
  "is_flip": true,
  "calibration_evidence": "Stage survival percentile risk threshold exceeded (HP <= 30)"
}
```
