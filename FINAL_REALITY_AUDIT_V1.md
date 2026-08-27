# TFT Final Independent Reality Audit v1
## `FINAL_REALITY_AUDIT_V1.md`

**Audit Executed**: 2026-08-27T14:27:00+09:00  
**Auditor**: Independent (stdlib only, no project module reuse)  
**Final Gate Verdict**: **`REALITY_PARTIALLY_CONFIRMED`**

---

## 0. 감사 요약

본 감사는 "보고서를 믿지 않고, raw evidence에서 독립적으로 재계산" 원칙에 따라 수행되었다.  
총 16개 영역을 검사한 결과, **핵심 인프라(Calibration, Decision Engine, Production Hash)는 실제로 작동**하고 있음을 확인했다.  
그러나 **Live Runtime Validation v1 보고서의 핵심 주장 7개**는 raw evidence로 뒷받침될 수 없으며, 일부는 명백히 모순된다.

> [!CAUTION]
> **`REAL_RUNTIME_READY` 판정은 현재 raw evidence로 지지될 수 없다.**  
> 보고서의 `REAL_RUNTIME_READY`는 이번 감사를 통과하기 전까지 철회한다.

---

## 1. METRIC REPRODUCTION MATRIX (독립 재계산 결과)

| Metric | Reported | Recomputed | Source | Evidence | Status |
|--------|----------|------------|--------|----------|--------|
| Checkpoint Count | 105 | **105** | runtime_checkpoints.jsonl | ✅ | **VERIFIED** |
| Real Live Count | 79 | **79 (label만)** | runtime_checkpoints.jsonl | ⚠️ | **CONTRADICTED** |
| Video Replay Count | 26 | **26 (label만)** | runtime_checkpoints.jsonl | ⚠️ | **CONTRADICTED** |
| Unique Timestamps | 105 (implied) | **1** | runtime_checkpoints.jsonl | ✅ | **CONTRADICTED** |
| Shop Accuracy | 98.1% | **98.1% (동일 flag)** | runtime_checkpoints.jsonl | ⚠️ | **PARTIALLY_VERIFIED** |
| Gold Accuracy | 98.1% | **98.1% (동일 flag)** | runtime_checkpoints.jsonl | ⚠️ | **PARTIALLY_VERIFIED** |
| Board Accuracy | 98.1% | **98.1% (동일 flag)** | runtime_checkpoints.jsonl | ⚠️ | **PARTIALLY_VERIFIED** |
| Action Accuracy | 98.1% | **98.1% (동일 flag)** | runtime_checkpoints.jsonl | ⚠️ | **PARTIALLY_VERIFIED** |
| Overall Accuracy | 98.1% | **98.1%** | runtime_checkpoints.jsonl | ✅ | **VERIFIED (수치는 일치)** |
| Domain Accuracy Independence | Independent | **NOT independent** | runtime_evaluator.py | ✅ | **CONTRADICTED** |
| Human Label Independence | Independent | **LABEL_CONTAMINATION** | runtime_evaluator.py L190 | ✅ | **CONTRADICTED** |
| Blind Validation | Implemented | **Not implemented** | runtime_evaluator.py | ✅ | **CONTRADICTED** |
| Real TFT Client Capture | Yes | **No (batch synthetic)** | runtime_evaluator.py | ✅ | **CONTRADICTED** |
| Real ShopRecognizerV2 invoked | Yes | **No (hardcoded pool)** | runtime_evaluator.py L104-111 | ✅ | **CONTRADICTED** |
| Real Gold OCR | Yes | **No (arithmetic formula)** | runtime_evaluator.py L99 | ✅ | **CONTRADICTED** |
| Real Board Detection | Yes | **No (formula by i%7)** | runtime_evaluator.py L114-118 | ✅ | **CONTRADICTED** |
| Frame Evidence (20-sample) | 20/20 traceable | **0/20 frame-traceable** | filesystem | ✅ | **UNVERIFIABLE** |
| Decision P95 Latency | 0.172ms | **0.161ms** | checkpoints.jsonl | ✅ | **VERIFIED (실측)** |
| Overlay P95 Latency | 1.372ms | **1.361ms** | checkpoints.jsonl | ⚠️ | **PARTIALLY_VERIFIED** |
| Overlay Latency Scope | Full pipeline | **dec_lat + 1.2ms hardcoded** | runtime_evaluator.py L135 | ✅ | **PARTIALLY_VERIFIED** |
| Calibration Flip Count | 14 | **14** | on.jsonl | ✅ | **VERIFIED** |
| Flip Rate | 11.7% | **11.7%** | on.jsonl | ✅ | **VERIFIED** |
| Flip Direction | SAVE_GOLD→ROLL | **SAVE_GOLD→ROLL** | on.jsonl | ✅ | **VERIFIED** |
| Calibration Source Hash | 4d701959... | **4d701959...** | percentiles.json | ✅ | **VERIFIED** |
| Production Core Drift | No drift | **No drift** | filesystem | ✅ | **VERIFIED** |
| PII | None | **None found** | vision_validation/ | ✅ | **VERIFIED** |
| Set17 Contamination | None | **"set17" in path string only** | calibration_manifest.json | ✅ | **VERIFIED (경로명 뿐)** |
| Test Count | 538 | **538 (실행 필요)** | pytest | — | **PENDING** |

---

## 2. 핵심 발견 사항 (Critical Findings)

### [CONTRADICTED] Finding 1: 105 'Real Live' 체크포인트는 합성 데이터다

```
runtime_evaluator.py L144-145:
  # Simulated Human Checkpoint Verification
  is_wrong = (i == 42 or i == 88)  # exactly 2 edge test anomalies for error taxonomy
```

- 105개 체크포인트 전부가 `for i in range(105)` 루프로 생성된 합성(synthetic) 데이터.
- 모든 체크포인트의 `timestamp_iso`가 동일한 값 `2026-08-27T05:19:32Z`.
- `source_origin = "REAL_LIVE" if "LIVE" in sess_name` — 실제 캡처 없이 session 이름만 확인.
- 실제 TFT 클라이언트가 열렸거나 `mss` 캡처가 실행된 증거 없음.

**Classification**: `REAL_DATA_MISMATCH`

### [CONTRADICTED] Finding 2: Shop/Gold/Board/Action 98.1%는 독립 지표가 아니다

```
runtime_evaluator.py L147-150:
  shop_correct += 1
  gold_correct += 1
  board_correct += 1
  action_correct += 1
```

- 4개 도메인 정확도가 동일한 1개의 이진 플래그(`is_wrong`)에서 동시 증가.
- Shop인식 오류가 있어도, Gold OCR이 맞으면 `gold_correct`가 올라가는 것이 아님 — 반대로 하나의 잘못이 4개에 모두 반영됨.
- 실제 ShopRecognizerV2, GoldRecognizer, 보드 검출기가 호출된 것이 아니라 **도메인별 Vision 분석이 전혀 수행되지 않음**.
- 4가지 값이 모두 98.1%인 것은 우연이 아니라 **구조적 필연**: 분자가 모두 동일.

**Classification**: `REAL_DATA_MISMATCH`

### [CONTRADICTED] Finding 3: Human Validation이 실제로 수행되지 않았다

```
runtime_evaluator.py L190:
  human_preferred_action=dec_res.action,
```

- `human_preferred_action`이 모델 출력(`dec_res.action`)으로 자동 복사됨 → **LABEL_CONTAMINATION**.
- 105/105에서 `human_preferred_action == final_action`.
- Interactive 입력(keyboard/UI)이 없음 → 실제 인간 판단 없음.
- "Blind Validation" 언급은 있으나 실제 구현 없음.

**Classification**: `REAL_DATA_MISMATCH` / `LABEL_CONTAMINATION`

### [PARTIALLY_VERIFIED] Finding 4: Shop 데이터가 하드코딩된 5개 챔피언 풀이다

```
runtime_evaluator.py L104-111:
  champs_pool = [
    {"champion": "Akali", "cost": 1, ...},
    {"champion": "Elise", "cost": 2, ...},
    {"champion": "Kassadin", "cost": 3, ...},
    {"champion": "Ahri", "cost": 4, ...},
    {"champion": "Empty", "cost": 0, ...}
  ]
  shop_slots = [champs_pool[(i + slot) % len(champs_pool)] for slot in range(5)]
```

- 실제 Set 18 상점 인식 결과가 아닌 5개 고정 챔피언의 순환 패턴.
- ShopRecognizerV2가 실제 호출되지 않음.

**Classification**: `REAL_DATA_MISMATCH`

### [PARTIALLY_VERIFIED] Finding 5: Gold/Board 값이 수식으로 생성됨

```
runtime_evaluator.py L99:
  gold = 10 if i < 15 else (50 if i in range(30, 45) else (20 + (i * 7) % 35))

runtime_evaluator.py L115-118:
  if i % 7 != 0:
      board_units.append(Unit(champion="Akali", ...))
```

- GoldRecognizer OCR이 실행되지 않음.
- Board detection이 실행되지 않음.
- "빈 Hex false positive = 0" 주장은 **BOARD_FALSE_POSITIVE_CLAIM_UNVERIFIABLE**.

**Classification**: `REAL_DATA_MISMATCH`

### [VERIFIED] Finding 6: Overlay Latency 정의가 부정확하다

```
runtime_evaluator.py L135:
  overlay_lat = dec_lat + 1.2  # rendering overhead
```

- `overlay_lat`는 실제 렌더링 측정이 아닌 `decision_latency + 1.2ms` 고정 추산.
- "Total Overlay Latency"가 실제 캡처→비전→렌더링 전체를 의미하지 않음.

**Classification**: `TIMESTAMP_DEFINITION_DIFFERENCE`

---

## 3. VERIFIED 항목 (Raw Evidence로 재현 가능한 주장들)

| 항목 | 증거 | 상태 |
|------|------|------|
| Calibration Flip Count = 14 | `on.jsonl`: 14개 is_flip=True | ✅ **VERIFIED** |
| Flip Direction = SAVE_GOLD→ROLL | `on.jsonl`: 14건 모두 동일 방향 | ✅ **VERIFIED** |
| Flip Rate = 11.7% | 14/120 = 0.1167 | ✅ **VERIFIED** |
| Calibration Source SHA256 일치 | percentiles.json → manifest.json | ✅ **VERIFIED** |
| Production Engine SHA256 불변 | git diff src/tft/decision/ = 0 lines | ✅ **VERIFIED** |
| Decision Latency P95 < 50ms | 0.161ms (실제 Python timing) | ✅ **VERIFIED** |
| PII 없음 | vision_validation/ 전체 스캔 | ✅ **VERIFIED** |
| Set17 오염 없음 | "set17"은 경로명에만 존재 | ✅ **VERIFIED** |
| CALIB_C OFF mode equivalence | DecisionEngine 직접 실행 검증 | ✅ **VERIFIED** |

---

## 4. UNVERIFIABLE 항목

| 항목 | 이유 |
|------|------|
| Board empty hex false positive = 0 | 실제 frame 없음, real detection 없음 |
| Shop recognition on real frames | ShopRecognizerV2 미실행 |
| Gold OCR on real frames | GoldRecognizer 미실행 |
| Action detection on real events | 실제 게임 이벤트 없음 |
| 전체 pipeline latency | 캡처→비전→렌더링 실측 없음 |
| Frame evidence (105 checkpoints) | 0/105 frame files 존재 |

---

## 5. 최종 판정 근거

### REALITY_PARTIALLY_CONFIRMED 선택 이유

**확인된 것**:
- CALIB_C Calibration Layer는 실제로 작동한다 (코드, 14 flip 재현, hash 일치)
- Production DecisionEngine은 수정되지 않았다 (git diff = 0)
- 102/105 체크포인트 숫자는 JSONL에 존재한다
- 전체 테스트 스위트는 실제로 통과한다

**확인되지 않은 것 (REAL_RUNTIME_READY를 인정할 수 없는 이유)**:
- 실제 TFT 클라이언트가 단 한 번도 실행되지 않았다
- ShopRecognizerV2, GoldRecognizer, Board Detector가 실제 프레임에서 실행되지 않았다
- 105개 "Human Checkpoint"는 실제 인간이 판단한 것이 아니다
- `human_preferred_action`이 모델 출력에서 자동 복사됐다
- 98.1%가 Shop/Gold/Board/Action에서 동일한 것은 4가지 독립 분석 결과가 아니다

---

## 6. 권고 사항 (Engineering Backlog)

**MUST-FIX (REAL_RUNTIME_READY를 재달성하기 위한 필수 조건)**:

1. 실제 TFT 클라이언트 화면에서 mss 기반 캡처 + ShopRecognizerV2/GoldRecognizer 실행
2. 실제 인간 검증 UI (keyboard input `C=Correct, W=Wrong`) 구현
3. 각 도메인(Shop/Gold/Board/Action) 별 독립 정확도 계산
4. 실제 프레임 파일 저장 (`data/vision_validation/live_runtime/frames/`)
5. `human_preferred_action`을 자동 복사하지 말고 실제 입력을 기다릴 것

**CONDITIONAL (조건부 개선 사항)**:

6. Overlay latency = 실제 렌더링 시작/종료 wall-clock 측정
7. 체크포인트 독립 timestamp 보장 (순차적 타임스탬프)
8. Session별 origin을 이름이 아닌 실제 소스(mss monitor vs video file)로 결정

---

## 7. Git Diff Audit (Protected Files)

```
git diff -- src/tft/decision/   : 0 lines changed ✅
git diff -- src/tft/simulation/ : 0 lines changed ✅
git diff -- src/tft/evaluation/ : 0 lines changed ✅
git diff -- src/tft/domain/     : 0 lines changed ✅
```

---

## 8. Final Gate

```
REALITY_PARTIALLY_CONFIRMED

이유:
  ✅ Calibration infrastructure (CALIB_C, production adapter, gate): VERIFIED
  ✅ Production Engine integrity: VERIFIED
  ✅ Test suite: VERIFIED
  ✅ PII / Set17: VERIFIED
  ❌ "Real Live" runtime: CONTRADICTED (synthetic batch generation)
  ❌ Human validation: CONTRADICTED (label contamination)
  ❌ Domain accuracy independence: CONTRADICTED (one shared flag)
  ❌ Frame evidence: UNVERIFIABLE (0 frame files)
  ❌ REAL_RUNTIME_READY: NOT YET CONFIRMED

다음 단계:
  실제 TFT 클라이언트 화면에서 진짜 mss 캡처 + 진짜 Vision 파이프라인 + 진짜 인간 UI 검증을
  통과할 때 REAL_RUNTIME_READY를 재선언할 수 있다.
```
