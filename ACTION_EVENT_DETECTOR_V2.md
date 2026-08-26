# TFT ActionEventDetector v2 — 상태 변화 기반 실제 행동 검출 및 Ground Truth 재검증 Specification

## 1. 개요 및 배경

TFT Set 17 비전 파이프라인에서 상점 기물 및 코스트 인식(`ShopRecognizerV2`)이 200개 Ground Truth 슬롯에 대해 **100.0% 정확도**를 달성함에 따라, 비전-백테스트 파이프라인의 핵심 과제는 **상태 변화(State Transition) 기반의 정확한 플레이어 행동 검출(`ActionEventDetectorV2`)**입니다.

기존 v1 방식:
- 단순 슬롯 문자열 변경 개수(`diff >= 3`) $\to$ `ROLL` 단순 판정
- 단일 슬롯 빈자리 $\to$ `BUY_UNIT` 단순 판정
- 골드 증감액, 유닛 코스트 매칭, 벤치/필드 기물 증감, 레벨/경험치 변화 등의 다중 증거 융합 부재

신규 v2 방식:
```text
Previous Observation (T0) + Current Observation (T1)
                         ↓
                  [ StateDiff Engine ]
     (ΔGold, ΔHP, ΔLevel, ΔXP, SlotTransitions, Bench/Board Diff)
                         ↓
               [ Multi-Signal Evidence ]
   (GOLD_DECREASE_2, MULTI_SLOT_REFRESH, CHAMPION_ADDED_TO_BENCH, ...)
                         ↓
             [ ActionEventDetectorV2 ]
     (ROLL, BUY_UNIT, LEVEL_UP, BUY_XP, SELL_UNIT, MULTI_ACTION)
                         ↓
      Standardized ActionEvent (with Full Evidence Trail)
```

---

## 2. 핵심 아키텍처 및 규칙

1. **StateDiff 중간 계층 분리 (`src/tft/vision/state_diff.py`)**:
   - `SlotTransitionType`: `UNCHANGED`, `EMPTIED`, `FILLED`, `REFRESHED`
   - 골드, HP, 레벨, 경험치, 벤치/필드 유닛 변화를 독립 계산.
2. **독립 행동 증거 (Evidence Fusion)**:
   - `ROLL`: $\ge 3$ 슬롯 동시 갱신 + $\Delta G == -2\text{G}$ + 벤치/보드 안정성.
   - `BUY_UNIT`: 슬롯 $\to$ `EMPTY` + 해당 챔피언 벤치/보드 추가 + $\Delta G == -\text{Cost}$.
   - `LEVEL_UP`: $\Delta \text{Level} \ge 1$ 및 레벨업 골드 소비.
   - `BUY_XP`: 레벨 유지 상태에서 경험치 증가 및 4G 배수 골드 소비.
3. **엄격한 인과성 및 미래 정보 배제 (Online Causality)**:
   - $T_0 \to T_1$ 순방향 탐지만 수행하며 미래 프레임을 이용한 사후 보정(Hindsight) 절대 금지.
4. **Ground Truth 완전 독립성**:
   - 정답 데이터(`gt_session_01.json`)는 탐지기에 절대 주입되지 않으며, 오직 사후 정량 평가(`evaluate_actions_v2.py`)에서만 사용.

---

## 3. CLI 실행 가이드

### (1) 타임라인으로부터 행동 이벤트 검출:
```bash
python detect_actions_v2.py \
    --timeline data/vision_audit/new_shop_timeline/timeline.json \
    --output data/vision_audit/action_v2
```

### (2) Ground Truth 대비 정량 평가 및 리포트 생성:
```bash
python evaluate_actions_v2.py \
    --predictions data/vision_audit/action_v2/predictions.jsonl \
    --ground-truth data/vision_audit/annotations/gt_session_01.json \
    --output data/vision_audit/action_v2/reports
```

### (3) 특정 시점 상태 전이 심층 진단:
```bash
python inspect_action_transition.py \
    --timeline data/vision_audit/new_shop_timeline/timeline.json \
    --timestamp 343.0
```
