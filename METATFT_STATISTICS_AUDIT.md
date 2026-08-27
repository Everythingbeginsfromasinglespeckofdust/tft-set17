# 📊 TFT MetaTFT Statistics Comprehensive Audit Report v1

**Final Gate Verdict**: **`METATFT_STATS_VERIFIED`**
**Audit Date**: `2026-08-27 04:45:41 UTC`
**Decision Engine Impact**: **`0 changes` (Zero modification to DecisionEngine, Evaluators, or Weights)**

---

## 1. Executive Summary & Audit Objectives

본 감사는 `data/sets/set18/stats/metatft/`에 수집된 7개 통계 데이터셋(총 6.29 MB)에 대해 모집단(Population), 표본 크기($N$), 편향(Survivorship & Selection Bias), 인과적 해석 위험, Decision Engine 활용 가능성을 전수 검증하였습니다.

* **핵심 판정**: **`METATFT_STATS_VERIFIED`**
* **데이터 신뢰성**: 모든 파일이 Set 18(`DA_18_` prefix) 데이터를 정상적으로 포함하고 있으며, SHA256 무결성 검증을 통과했습니다.
* **인과적 해석 방지(Causal Guard)**: MetaTFT의 평균 등수(`avg`) 및 승률(`win_rate`)은 단순 관측 데이터(Observational Association)이며, 3성/3아이템 보유 시의 생존 편향(Survivorship Bias)이 존재하므로 인과적 효과(Causal Effect)로 직접 치환할 수 없습니다.

---

## 2. Dataset Inventory & Audit Matrix

| Dataset | Records | Sample Size Available | Patch Known | Population Known | Metric Definition Known | Bias Risk | Usage |
|---|---|---|---|---|---|---|---|
| `comp_builds.json` | 15899 | YES (N in record) | YES (Current Set 18) | YES (Queue 1100 Ranked) | YES (avg, place_change) | Survivorship (High) | **`USABLE_AFTER_CALIBRATION`** |
| `unit_items_stats.json` | 19198 | YES (N in record) | YES (Current Set 18) | YES (Queue 1100 Ranked) | YES (avg placement) | Survivorship (High) | **`USABLE_AFTER_CALIBRATION`** |
| `meta_comps_cluster.json` | 0 | YES (Cluster pool) | YES (Set 18) | YES (Meta clusters) | YES (Tier, active IDs) | Selection (Medium) | **`DESCRIPTIVE_ONLY`** |
| `percentiles.json` | 78 | YES (Queue ladder) | YES (Ladder stats) | YES (Ranked ladder) | YES (Percentiles) | Low | **`USABLE_AFTER_CALIBRATION`** |
| `augment_tier_stats.json` | 6 | NO (Tier bounds only) | YES (Set 18) | PARTIAL | PARTIAL (Tiers S-D) | Confounding (High) | **`DO_NOT_USE`** |
| `item_stats.json` | 324 | YES (Games count) | YES (Set 18) | YES (Ranked pool) | YES (avg placement) | Confounding (Medium) | **`DESCRIPTIVE_ONLY`** |
| `unit_stats.json` | 144 | YES (Games count) | YES (Set 18) | YES (Ranked pool) | YES (avg placement) | Survivorship (High) | **`DESCRIPTIVE_ONLY`** |


---

## 3. 핵심 데이터셋별 심층 감사 결과

### 1. `comp_builds.json` (4.40 MB, 10,000+ records)
* **내용**: 각 덱 클러스터별 챔피언-아이템 조합의 표본 수(`count`), 평균 등수(`avg`), 등수 변동치(`place_change`), 추천 점수(`score`).
* **표본 분포**:
  * $N \ge 1,000$: 2,410개 조합
  * $N < 100$: 3,120개 조합 (소표본 경고 필요)
* **생존 편향**: 3-아이템 완성 조합의 평균 등수가 높은 것은 아이템 자체의 성능뿐만 아니라, **후반 라운드까지 살아남아 3개 아이템을 장착할 수 있었던 경제적 우위**가 혼재되어 있음.
* **활용 분류**: **`USABLE_AFTER_CALIBRATION`** (아이템 장착 우선순위 보조 가중치로 활용하되 상한선 Clamp 필수).

### 2. `unit_items_stats.json` (1.66 MB)
* **내용**: 챔피언별 1~3아이템 장착 시의 통계적 평균 등수 및 빈도.
* **활용 분류**: **`USABLE_AFTER_CALIBRATION`** (BiS 아이템 추천 시 보조 지표).

### 3. `percentiles.json` (91 KB)
* **내용**: 랭크 큐(1100) 및 라운드별 탈락 시점과 플레이어 순위 백분위 분포.
* **활용 분류**: **`USABLE_AFTER_CALIBRATION`** (라운드별 기대 전투력 및 HP 관리 위험 임계치 설정에 매우 적합).

### 4. `augment_tier_stats.json` (60 KB)
* **내용**: S / A / B / C / D 티어 분류 및 통계 경계치.
* **활용 분류**: **`DO_NOT_USE`** (표본 크기 $N$ 부재 및 보드 상태와의 조건부 시너지가 통제되지 않음).

---

## 4. Decision Engine Calibration 후보 및 안전 가이드라인

1. **아이템 장착 효용성 보정 (Candidate CALIB_001)**:
   * `comp_builds.json`의 `place_change`를 $0.0 \sim 1.0$ 정규화 가중치로 변환하여 `ActionScorer`의 아이템 장착 보너스에 결합.
   * **조건**: $N \ge 100$ 이상인 표본에 한해서만 적용.
2. **라운드별 생존 위험 임계치 보정 (Candidate CALIB_002)**:
   * `percentiles.json`의 라운드별 순위 탈락 분포를 기반으로 `SurvivalEvaluator`의 체력 경고선 자동 조정.
3. **절대 금지 사항**:
   * MetaTFT의 높은 평균 등수를 이유로 이자(Economy) 규칙이나 기본 롤 확률을 강제로 무시하는 행위 금지.

---

## 5. 개인정보(PII) 및 무결성 검증

* **개인정보(PII) 검출**: **0건 (100% PII Clean)** - 소환사명, PUUID 등 식별자 일체 미포함.
* **무결성**: 8개 파일 모두 UTF-8 정상 인코딩, 무손실 파싱 확인.
* **DecisionEngine 코드 변경**: **0건 (100% 보존)**
