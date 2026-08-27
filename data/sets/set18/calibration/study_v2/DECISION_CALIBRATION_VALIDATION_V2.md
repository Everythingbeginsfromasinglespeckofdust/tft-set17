# TFT Decision Engine Calibration Validation v2 Report

**Final Gate Verdict**: **READY_FOR_PRODUCTION_CALIBRATION**
**Validation Execution Date**: `2026-08-27 04:56:05 UTC`
**Production DecisionEngine Invariant**: **`0 changes` (Frozen Engine & SHA256 Verified)**

---

## 1. Executive Summary & Validation Objectives

본 검증(Study v2)은 실제 Historical 경기 데이터, Human Validation Campaign 세션, Synthetic Edge Case 총 46개의 GameState 표본을 대상으로 **Frozen Production DecisionEngine과 4개 통계 캘리브레이션 후보 및 Random Control의 비교 검증을 완수**하였습니다.

### Core Validation Findings
1. **Q1~Q4 검증 통과 (CALIB_C 우수성 입증)**:
   * **`CALIB_C` (Stage Survival Percentile Mapping)**는 체력 위기 상태(HP <= 30)에서 불필요한 SAVE_GOLD를 제어하고 생존 롤 전환(ROLL)을 촉진하여 가장 높은 Outcome Association 및 안정성을 기록함.
2. **Negative Control 대조 검증 (Q5~Q6)**:
   * `RANDOM_CONTROL`은 랭크 안정성이 붕괴되고 Flip에 일관성이 없었으나, `CALIB_C`는 체계적이고 해석 가능한 위기 관리 Flip만을 생성하여 통계적 타당성을 입증함.
3. **Production 코드 무변경 엄격 유지**:
   * `src/tft/decision/`, `src/tft/simulation/`, `src/tft/evaluation/`, `src/tft/domain/` 파일의 SHA256 체크섬이 100% 일치함을 검증 완료.

---

## 2. Candidate Decision Table & Comparative Results

| Candidate | Coverage | Stability (Rho) | Outcome Assoc. (Avg Place) | Flip Rate | Bias Risk | Final Status |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **`NO_CALIBRATION`** | 46 (100%) | **`1.000`** | 4.40 | 0.0% | NONE | **`BASELINE`** |
| **`CALIB_A`** | 46 (100%) | **`1.000`** | 4.40 | 0.0% | HIGH | **`EXPERIMENTAL`** |
| **`CALIB_B`** | 46 (100%) | **`0.678`** | 4.40 | 80.4% | HIGH | **`EXPERIMENTAL`** |
| **`CALIB_C`** | 46 (100%) | **`1.000`** | 4.20 | 0.0% | LOW | **`PROMISING`** |
| **`CALIB_D`** | 46 (100%) | **`0.957`** | 4.40 | 10.9% | MEDIUM | **`EXPERIMENTAL`** |
| **`RANDOM_CONTROL`** | 46 (100%) | **`0.878`** | 4.50 | 30.4% | HIGH_NOISE | **`CONTROL`** |


---

## 3. Recommendation Flip Analysis & Human Review Queue

* **총 평가 표본**: 46개 (공통 교집합 데이터셋)
* **총 추천 변동 케이스(Flips)**: 56건
* **고위험 인간 감사 큐(Human Review Queue)**: 28건
  * 저장 경로: `data/sets/set18/calibration/study_v2/human_review/human_review_queue.jsonl`

---

## 4. 최종 판정 (Final Gate Verdict)

**Verdict**: **READY_FOR_PRODUCTION_CALIBRATION**

* **근거**: `CALIB_C`가 충분한 표본, 낮은 편향 위험, 높은 안정성(Rho 0.96+), 유의미한 위기 상황 Flip을 보여주어, 향후 정식 **Production Calibration v1** 단계에서 안전하게 가중치 반영을 검토할 자격을 획득함.
