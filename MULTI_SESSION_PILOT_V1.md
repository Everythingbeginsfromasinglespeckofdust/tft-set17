# TFT Multi-Session Pilot v1 — Specification & Architecture

## 1. 개요 및 설계 목적

`TFT Multi-Session Pilot v1`은 단일 세션(`SESSION_A`)에서 구축 및 검증된 Vision → Gold → Action Pipeline을 **서로 다른 3개의 실제 TFT 경기 영상(`SESSION_A`, `SESSION_B`, `SESSION_C`)**에 완전히 동일한 설정과 Frozen 파이프라인으로 교차 적용하여 일반화 성능을 객관적으로 평가하는 파일럿 벤치마크입니다.

---

## 2. Freeze Rules (동결 규칙)

1. `ShopRecognizerV2`, `GoldRecognizer`, `GoldTimelineV1`, `ActionEventDetectorV22`, `DecisionEngine` 일절 수정 금지.
2. 세션별 threshold 또는 휴리스틱 조정 금지.
3. 세션 간 코드 차등 실행 금지 (동일 파이프라인 일괄 적용).

---

## 3. Pilot Sessions Metadata

| Session ID | Video File | Match ID | Placement | Economic Archetype | Duration |
|---|---|---|---|---|---|
| **`SESSION_A`** | `eda87ad9-...-2026-07-29-02-41-03.mp4` | `MATCH_EDA87AD9` | `2nd` | `BALANCED_STANDARD` | `1931.4s` |
| **`SESSION_B`** | `831ad7ce-...-2026-07-29-02-01-39.mp4` | `MATCH_831AD7CE` | `1st` | `FAST_LEVELUP` | `2238.6s` |
| **`SESSION_C`** | `6e831624-...-2026-08-16-00-24-31.mp4` | `MATCH_6E831624` | `4th` | `REROLL_HEAVY` | `2032.1s` |

---

## 4. 엄격한 Gold 지표 분리 원칙

* `raw_ocr_valid_rate`: 원본 Tesseract OCR이 즉시 유효한 골드를 파싱한 프레임 비율.
* `carried_forward_rate`: 순간적 OCR 결손으로 인해 이전 유효 상태를 순방향 유지한 비율.
* `stabilized_accuracy`: 온라인 안정화 후 최종 유효 골드의 정확도.
* `gold_delta_accuracy`: $\Delta G == -2, -\text{Cost}$ 등의 전이 이벤트 추출 정밀도.

---

## 5. Action-Gold Lineage Tracking

모든 Ground Truth 행동은 다음 인과 사슬을 통해 추적됩니다:
$$\text{GT Action} \longrightarrow \text{GoldObs}_{T-1} \longrightarrow \text{GoldObs}_T \longrightarrow \text{GoldDeltaEvent} \longrightarrow \text{ActionEvent}$$

* 신호 손실 단계 분류 (`LineageLossStage`):
  - `NONE`: 완전 보존 및 검출 성공
  - `OCR_MISSING`: 골드 OCR 인식 실패
  - `COARSE_SAMPLING_MERGE`: 0.5초 간격 내 연속 다중 행동 압축
  - `ANIMATION_BLUR`: 상점/골드 애니메이션 중 프레임 흐림
  - `THRESHOLD_FILTER`: 규칙 임계치 미달

---

## 6. Acceptance Gate 기준

* **`GREEN`**: 모든 세션에서 Shop/Gold 안정, $F_1 \ge 0.70$, $FP = 0$, Production $\approx$ Rule Replay 달성.
* **`YELLOW`**: 일부 세션에서 성능 저하가 있으나 원인이 명확하고 국소적임.
* **`RED`**: 세션 간 일반화 실패 또는 인식 붕괴.
* **`INSUFFICIENT_DATA`**: 유효 세션 부족 또는 행동 다양성 미달.

---

## 7. CLI 실행 가이드

```bash
# 1. 파일럿 세션 등록
python register_pilot_session.py --manifest data/backtest/pilot/pilot_manifest.json --init-default

# 2. 전체 세션 파이프라인 일괄 실행
python run_multi_session_pilot.py \
    --config data/backtest/pilot/pilot_manifest.json \
    --output data/backtest/pilot

# 3. 교차 세션 종합 평가 및 리포트 생성
python evaluate_multi_session.py \
    --manifest data/backtest/pilot/pilot_manifest.json \
    --input data/backtest/pilot \
    --annotations data/vision_audit/annotations \
    --output data/backtest/pilot/reports
```
