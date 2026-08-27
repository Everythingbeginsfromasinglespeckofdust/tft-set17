# TFT Production Calibration Shadow Mode v1 Report

**Final Gate Verdict**: **SHADOW_VALIDATED**
**Execution Date**: `2026-08-27 05:11:08 UTC`
**Production DecisionEngine Code Impact**: **`0 changes` (Frozen Engine & SHA256 Checksum Verified)**
**Production Latency Compliance**: **P95 `0.22ms` (< 50ms Goal: PASS)**

---

## 1. Executive Summary & Shadow Mode Verification

본 검증(Shadow Mode v1)은 `CALIB_C` (Percentile Risk Mapping)를 실제 Vision → GameState → Decision 실행 경로의 독립된 **Shadow Layer**로 구축하고, **사용자 화면에 표시되는 Production 추천은 100% 불변으로 유지한 채 백그라운드 실시간 로깅 및 성능 격리를 검증**하였습니다.

### Final Gate Verdict
**Verdict**: **SHADOW_VALIDATED**

* **검증 핵심 성과**:
  1. **Production 불변 유지**: 유저 화면에 표시되는 `recommended_action` 및 `ActionScore`는 Frozen Production Engine 결과를 100% 그대로 출력.
  2. **Gate v1 완벽 재현 (100%)**: 120개 실데이터 표본에서 Gate v1의 14개 Flip(11.7%) 및 방향(`SAVE_GOLD->ROLL`)이 완벽히 일치함을 확인.
  3. **초저지연 성능 (Latency Goal < 50ms 달성)**: Shadow 계산을 포함한 평균 지연 시간 **`0.15ms`**, P95 지연 시간 **`0.22ms`**로 극도로 가볍게 동작.
  4. **결함 격리 (Failure Isolation)**: Shadow 레이어 내부 예외나 데이터 누락이 발생해도 Production 의사결정은 100% 정상 실행됨을 입증.
  5. **킬스위치 (Kill-Switch) & 샘플링 레이트 지원**: `shadow_enabled=False` 및 10% ~ 100% 샘플링 레이트를 런타임 제어 가능.

---

## 2. Shadow Mode Replay Metrics Summary

| 항목 (`Metric`) | 관측값 (`Value`) | 기준 목표 (`Target`) | 적합성 판정 (`Status`) |
|---|:---:|:---:|:---:|
| **총 평가 표본 (`States Evaluated`)** | 120 | 120 (Real Gate Samples) | **PASS** |
| **추천 변동 건수 (`Flip Count`)** | 14 (11.7%) | 14 (11.7%) | **EXACT_MATCH** |
| **주요 변동 방향 (`Flip Direction`)** | `SAVE_GOLD->ROLL` (14건) | Stage 4/5 위기 리롤 촉진 | **EXPLAINABLE** |
| **평균 처리 지연 (`Mean Latency`)** | **`0.15 ms`** | < 25.0 ms | **EXCELLENT** |
| **P95 처리 지연 (`P95 Latency`)** | **`0.22 ms`** | < 50.0 ms | **EXCELLENT** |
| **Production 코드 수정 여부** | **0 lines (Frozen SHA256)** | Zero Diff | **VERIFIED** |

---

## 3. Shadow Output File Structure

```text
data/sets/set18/calibration/shadow_v1/
    ├── manifest.json
    ├── replay/
    │   └── comparison.jsonl
    ├── live/
    │   └── shadow_decisions.jsonl
    ├── flips/
    │   ├── all_flips.jsonl
    │   └── high_risk_flips.jsonl
    ├── validation/
    │   ├── gate_reproduction.json
    │   ├── performance.json
    │   └── failure_recovery.json
    ├── human_review/
    │   └── review_queue.jsonl
    └── reports/
        └── SHADOW_MODE_VALIDATION_V1.md
```
