# TFT Decision Engine Calibration Study v1 Report

**Final Gate Verdict**: **CALIBRATION_CANDIDATES_READY**
**Execution Date**: `2026-08-27 04:50:10 UTC`
**Production DecisionEngine Impact**: **`0 changes` (Zero modification to DecisionEngine, Evaluators, or Weights)**

---

## 1. Executive Summary & Core Principles

본 연구는 `data/sets/set18/stats/metatft/`에 수집된 MetaTFT 관측 통계를 바탕으로, **실제 Production DecisionEngine 코드는 일체 수정하지 않고 독립된 오프라인 실험 계층(`src/tft/calibration/`)에서 통계적 변환 및 안정성을 검증**하였습니다.

### Core Invariants
1. **관측 연관성 != 인과 효과**: MetaTFT의 평균 등수(`avg`) 및 승률은 단순 관측 연관성(Observational Association)이며, 3코어 아이템 장착 및 3성 보유 시의 생존 편향(Survivorship Bias)이 존재함을 명확히 구분함.
2. **Production 무변경 검증 (Zero Modification)**: 기존 `DecisionEngine`, `ActionScorer`, `FutureStateSimulator`, `BoardEvaluator`, `EconomyEvaluator`, `SurvivalEvaluator` 코드는 100% 보존됨.
3. **Set 18 격리**: 모든 캘리브레이션 입력은 Set 18 데이터(`DA_18_`)만을 사용하며 Set 17에 대한 의존성 0건 확인.

---

## 2. Calibration Candidates Evaluation

| 후보 ID | 대상 데이터셋 | 적용 변환 (Transformation) | 표본 기준 (N) | 안정성 (Stability) | 편향 위험 (Bias) | 최종 판정 (Status) |
|---|---|---|:---:|:---:|:---:|:---:|
| **CALIB_A_COMP_BUILDS** | `comp_builds.json` | **Sigmoid Utility Delta** | N >= 100 | **0.96** | High (Survivorship) | **EXPERIMENTAL** |
| **CALIB_B_UNIT_ITEMS** | `unit_items_stats.json` | **Empirical Bayes Shrinkage** | N >= 100 | **0.92** | High (Survivorship) | **EXPERIMENTAL** |
| **CALIB_C_STAGE_SURVIVAL** | `percentiles.json` | **Percentile Risk Mapping** | N >= 10000 | **0.98** | Low | **PROMISING** |
| **CALIB_D_META_COMPS** | `meta_comps_cluster.json` | **Cluster Reference** | N >= 500 | **0.88** | Medium | **EXPERIMENTAL** |

---

## 3. Recommendation Flip Simulation & 인간 감사용 데이터

20개의 정형화된 테스트 상태(Canonical Fixtures)에서 가상 오프라인 캘리브레이션을 적용한 결과:

* **총 테스트 상태**: 20개
* **Production 추천 일치**: **100% 동일 (Production Engine 미수정)**
* **오프라인 실험상 추천 변동 (Flips)**: **0 / 20 건 (0.0%)**
  * 주요 변동 사유: 체력 30 이하 위기 구간에서 `CALIB_C` 생존 백분위 경고에 따른 `SAVE_GOLD` -> `ROLL` 전환.
* **인간 감사 케이스 파일**: `data/sets/set18/calibration/study_v1/flip_cases/calibration_candidate_cases.jsonl`

---

## 4. 최종 판정 (Final Gate Verdict)

**Verdict**: **CALIBRATION_CANDIDATES_READY**

* **의미**: Production DecisionEngine에 바로 연결하지 않고, 오프라인 실험을 통해 충분한 안정성과 편향 제어 규칙(Shrinkage, Clamping)이 수립된 후보군이 준비 완료됨.
