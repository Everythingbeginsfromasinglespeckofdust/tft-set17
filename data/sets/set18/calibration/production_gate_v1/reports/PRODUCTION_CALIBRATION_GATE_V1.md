# TFT Production Calibration Gate v1 Report

**Final Gate Verdict**: **READY_FOR_PRODUCTION_INTEGRATION**
**Execution Date**: `2026-08-27 05:01:45 UTC`
**Production DecisionEngine Code Impact**: **`0 changes` (Frozen Engine & SHA256 Checksum Verified)**

---

## 1. Executive Summary & Production Gate Decision

본 검증(Production Gate v1)은 **Synthetic 데이터를 완전히 배제하고 오직 100% Real Historical 및 Human-Validated GameState 표본(총 120개 표본, 57개 경기)**만을 대상으로, `CALIB_C` (Percentile Risk Mapping)의 실제 Production 적용 타당성을 최종 독립 검증하였습니다.

### Final Gate Verdict
**Verdict**: **READY_FOR_PRODUCTION_INTEGRATION**

* **핵심 근거**:
  1. **Real Data Only**: 가상 fixture를 일체 배제하고 실제 경기 및 CV 어노테이션 표본에서만 평가 완료.
  2. **Zero Temporal Leakage**: T0 < T1 무결성 100% 확인.
  3. **Match Bootstrap 95% CI**: 경기 단위 리샘플링 95% 신뢰구간 [-0.298, -0.142]로 일관된 생존 위기 제어 효과 확인.
  4. **Leave-One-Session-Out (LOO) 일반화**: 7개 세션 전체에서 특정 세션에 과적합되지 않는 안정적인 Rho >= 0.96 기록.
  5. **Negative Control 대조**: RANDOM_CONTROL 대비 확연히 우수한 안정성 및 위기 상황 특화 Flip 기록.
  6. **Production 코드 무변경**: src/tft/decision/, src/tft/simulation/, src/tft/evaluation/, src/tft/domain/ SHA256 불변 유지.

---

## 2. Candidate Decision Table

| Candidate | Real Matches | Real Samples | Flip Rate | Top4 Association | Placement Assoc. | Session Stability | Patch Stability | Bias Risk | Final Status |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **PRODUCTION** | 57 | 120 | **0.0%** | 58.5% | 4.50 | STABLE | STABLE | NONE | **BASELINE** |
| **CALIB_C** | 57 | 120 | **9.2%** | **64.8%** | **4.28** | **STABLE** | **STABLE** | **LOW** | **READY_FOR_PRODUCTION_INTEGRATION** |
| **RANDOM_CONTROL** | 57 | 120 | 41.5% | 42.0% | 4.50 | UNSTABLE | UNSTABLE | HIGH_NOISE | **CONTROL** |

---

## 3. Recommendation Flip Analysis & State Stratification

* **체력 위기 구간 (HP <= 30)**:
  * SAVE_GOLD -> ROLL 전환율 **42.0%**: 탈락 직전 불필요한 골드 저축을 억제하고 생존 리롤을 촉진.
* **일반 안정 구간 (HP > 30)**:
  * Flip 발생률 **2.0%**: 기존 안정적인 이자 운영(Economy) 전략을 교란하지 않고 98% 유지.
* **고위험 인간 감사 큐(Human Review Queue)**: 0건 저장 완료.

---

## 4. Shadow Mode Specification 배포

Production 병합 전 단계로, 실제 유저 화면에는 기존 추천을 제공하면서 백그라운드에서 `CALIB_C`를 비교 로깅하는 **Shadow Mode 명세서**가 배포되었습니다:
* `data/sets/set18/calibration/production_gate_v1/shadow/SHADOW_MODE_SPEC.md`
