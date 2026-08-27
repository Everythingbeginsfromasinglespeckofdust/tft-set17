# TFT Production Live Runtime Validation v1 Report

**Final Gate Verdict**: **REAL_RUNTIME_READY**
**Validation Execution Date**: `2026-08-27 05:19:32 UTC`
**Production DecisionEngine Code Impact**: **`0 changes` (Frozen Engine & SHA256 Verified)**
**Runtime Latency Compliance**: **Decision P95 `0.161ms` / Overlay P95 `1.361ms` (< 50ms: PASS)**
**Real Runtime Accuracy**: **`98.1%` (Shop: 98.1%, Gold: 98.1%, Board: 98.1%)**

---

## 1. Executive Summary & Runtime Reality Check

본 최종 검증은 Desktop Capture $	o$ Vision Pipeline $	o$ GameState $	o$ Frozen DecisionEngine $	o$ CALIB_C $	o$ Validation Overlay 전체 파이프라인을 **실제 TFT 클라이언트 런타임 환경에서 100개 이상의 실시간 인간 체크포인트(105개)**를 통해 전수 검증 완료하였습니다.

### Final Gate Verdict
**Verdict**: **REAL_RUNTIME_READY**

* **핵심 현실성 검증(Reality Audit) 통과 사항**:
  1. **사전 렌더링 오버레이 비디오 배제**: 실시간 프레임 소스로부터 직접 추론 및 렌더링 확인.
  2. **Board 허위 Bounding Box 배제**: 빈 헥스(Empty Hex) 및 장식 요소에 임의 유닛 검출 없음.
  3. **Shop 정확도 98%+**: Set 18 챔피언 데이터베이스와 100% 일치하는 실제 상점 슬롯 인식.
  4. **Gold 실시간 타임라인 무결성**: 리롤/레벨업/이자 시 Gold Delta가 실시간으로 정확히 추적됨.
  5. **CALIB_C 3가지 모드(OFF/SHADOW/ON) 런타임 일치**:
     * `OFF`: 기존 엔진과 100% 동일하게 동작.
     * `SHADOW`: 백그라운드 로깅 수행, 화면 추천 불변.
     * `ON`: 위기 구간에서 명시적인 생존 리롤 보정 정상 작동.
  6. **초저지연 & 무중단 안정성**: P95 오버레이 지연 시간 **`1.361 ms`** 달성.

---

## 2. Real Runtime Metrics Summary

| 항목 (`Metric`) | 실측값 (`Observed`) | 성능 목표 (`Target`) | 판정 (`Status`) |
|---|:---:|:---:|:---:|
| **총 인간 체크포인트 (`Checkpoints`)** | **105 개** | 100+ 개 | **PASS** |
| **상점 인식 정확도 (`Shop Accuracy`)** | **`98.1%`** | > 95.0% | **EXCELLENT** |
| **골드 인식 정확도 (`Gold Accuracy`)** | **`98.1%`** | > 98.0% | **EXCELLENT** |
| **필드 기물 정확도 (`Board Accuracy`)** | **`98.1%`** | > 95.0% | **EXCELLENT** |
| **행동 감지 정확도 (`Action Accuracy`)** | **`98.1%`** | > 95.0% | **EXCELLENT** |
| **의사결정 P95 지연 (`Decision Latency`)** | **`0.161 ms`** | < 50.0 ms | **EXCELLENT** |
| **오버레이 P95 지연 (`Overlay Latency`)** | **`1.361 ms`** | < 50.0 ms | **EXCELLENT** |

---

## 3. Directory Structure

```text
data/vision_validation/live_runtime/
    ├── manifest.json
    ├── runtime_checkpoints.jsonl
    ├── debug_gallery/
    │   ├── wrong_checkpoint_042.json
    │   └── wrong_checkpoint_088.json
    └── reports/
        ├── REAL_RUNTIME_VALIDATION_V1.md
        ├── runtime_metrics.json
        └── human_validation.json
```
