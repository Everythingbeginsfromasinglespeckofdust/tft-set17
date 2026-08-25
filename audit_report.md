# TFT Set 17 경제 코드 감사 보고서

- **작성일**: 2026-08-24
- **감사 범위**: `/output/tft_guide/05_xp_gold.json`, `/output/pool_sizes.{json,py}`, `/output/economy/{interest,reroll,test_interest,test_reroll,test_pool_sizes}.py`
- **정책**: 보고만 함. 수정은 별도 티켓.
- **메서드**: 테스트 "통과" 기록 무시, 전 파일 정독 + grep/AST 리터럴 감사 + **지금 이 순간** 재실행 검증.

---

## 항목별 결과

### [A-1] 05_xp_gold.json interest_table 10골드 단위 + 5골드 잔재 grep → **PASS (부수 발견 2건)**

**본체 PASS**:
- `/output/tft_guide/05_xp_gold.json` L62-84: `interest_table` = `0-9→0, 10-19→1, 20-29→2, 30-39→3, 40-49→4, 50-99→5` — 10골드 단위 정확.
- `tft_guide.py` 생성기 (build_xp_gold, L343-349): 동일 10골드 단위 테이블 생성.
- `tft_set17_guide.md` L560-565: 동일 10골드 단위 표.
- `tft_set17_viewer.html` L278-279: 이자 표는 **table-driven**(`D.gold.interest_table.map`)이라 JSON에 종속 — 잔재 없음.
- 워크스페이스 `tft_guide/05_xp_gold.json`과 `/output` 복사본: `diff` 결과 **완전 일치**.

**부수 발견 (본 항목은 10골드 단위 잔재가 아니므로 PASS 유지, 별도 항목으로 기록)**:

> **F-1 (중간)**: `interest.py` L9-19 모듈 docstring에 **구 5골드 단위 테이블**이 그대로 남아 있음.
> ```
> L10:   "interest": "floor(보유 골드 / 5), 최대 5골드",
> L13:   {"gold": "1-5",  "interest": 1},
> L14:   {"gold": "6-10", "interest": 2},
> L15:   {"gold": "11-15","interest": 3},
> L16:   {"gold": "16-20","interest": 4},
> L17:   {"gold": "21-50","interest": 5}
> ```
> - **영향**: 실행 코드 아님(docstring). 로직은 L52-67에서 JSON `interest_table`을 파싱하므로 **동작에는 영향 0**.
> - **위험**: docstring이 "JSON의 gold 구조"라고 주장하므로, 향후 개발자가 docstring을 믿고 5골드 단위로 JSON을 "복원"할 위험. L23-25의 "테이블을 따른다" 해설도 구 구조 기준.
> - **수정 방법**: L9-19 예시를 현재 JSON(10골드 단위, "0-9" 시작)으로 갱신, L23-25 해설도 10골드 기준 재작성.

> **F-2 (경미)**: `test_interest.py` L109 주석 `# JSON 테이블에서 47골드 구간(21-50)의 이자값을 직접 재추출해 비교` — `21-50`은 구 5골드 단위 표의 구간. 로직은 구분을 파싱해서 재추출하므로 **동작 영향 없음**, 주석만 stale.
> - **수정 방법**: L109 주석을 `40-49 구간`으로 수정.

### [A-2] `reroll_discount` 전체 grep → **PASS (단, 정의 확인 필요)**

전체 grep(`.py/.json/.md/.html`, `__pycache__` 제외). **필드(키)·변수·JS 라이브 참조는 0건**이지만, **문자열 리터럴로 7건** 존재:

| # | 위치 | 성격 |
|---|---|---|
| 1 | `tft_guide/05_xp_gold.json` L88 (`reroll_cost_note` 값) | **티켓이 명문화한 "정정 주석" — 의도된 잔존** |
| 2 | `tft_guide.py` L351 (위 note 생성 문자열) | 동일 note의 생성기 소스 |
| 3 | `tft_set17_viewer.html` L127 (내장 JSON) | #1의 사본 |
| 4 | `TFT_17.9_작업정리.md` L55 | 정정 기록 |
| 5 | `/output/verification_needed.md` L31 | 정정 기록 |
| 6 | `test_reroll.py` L31 | `assert "reroll_discount" not in raw` — **제거 검증용 부정 어설션(의도됨)** |
| 7 | `test_reroll.py` L37 | 동일 |
| 8 | `/output/economy/reroll.py` | **없음** (L5는 '구간별 유지율'로 토큰 회피) |
| 9 | `tft_viewer.py` | **없음** |

- **PASS 근거**: 필드(키), 변수, `D.reroll_discount` JS 참조는 전부 0건. 잔존은 전부 (a) 티켓 지시된 정정 주석, (b) 제거 검증 어설션, (c) 문서 기록.
- **주의 (판단 요청 F-5)**: 티켓의 "단 하나도 안 남아있는가"가 **문자열까지 포함**이면 7건으로 **FAIL**. 그러나 `reroll_cost_note`의 정정 주석은 이전 티켓에서 "추가" 지시로 받았고, 그 주석 내용이 구 필드명을 포함합니다. 토큰만 회피하는 표현('구간별 유지율 필드')으로 다듬을지, 아니면 7건을 허용할지 **사용자 판단** 필요. `interest.py` docstring처럼 "이름 언급 = 재출현 위험" 논리를 적용하면 토큰 회피가 더 안전.

### [A-3] pool_sizes.json vs pool_sizes.py **지금 이 순간** 재실행 → **PASS**

    $ python3 -c "import pool_sizes; pool_sizes.load_pool_sizes()"
    py  : {1: 29, 2: 22, 3: 18, 4: 10, 5: 9}
    json: {1: 29, 2: 22, 3: 18, 4: 10, 5: 9}
    일치: True

(재실행 시점 확인, 캐시/통과 기록 무시)

### [B] 로직 코드 숫자 리터럴 감사 (economy/) → **PASS (예외 1건 명시)**

AST 감사 결과(`ast.Constant` int/float, 주석·문자열 제외):

| 파일 | 리터럴 | 판정 |
|---|---|---|
| `interest.py` | `0`(검증/초기값), `1`/`2`(인덱스/턴 번호) | OK — 이자율(5/10) 없음 |
| `reroll.py` | `0`(검증), `1`(range 시작) | OK — 리롤비용(2) 없음 |
| `pool_sizes.py` | `0`(양수 검증) | OK — 풀사이즈(29/22/18/10/9) 없음 |
| `roll_probability.py` | `5`(L44 `SHOP_SLOTS`), `1..5`(L91/L128 코스트 범위), `100.0`(L91 %→소수), `0.0/1.0`(확률 연산) | **예외 1건 명시** |

- **예외 (F-6)**: `roll_probability.py` L44 `SHOP_SLOTS = 5` — 상점 슬롯 수 5. **이 값은 어떤 데이터 파일(DDragon/CDN/03_drop_rates.json)에도 존재하지 않는 클라이언트 구조 상수**이며, JSON에 추가할 소스도 없음. 5슬롯은 TFT의 구조적 사실(데이터가 아닌 규칙)이므로 하드코딩 허용. 상수명+주석으로 명시되어 추적 가능.
- **결론**: 이자율·리롤비용·풀사이즈 리터럴이 로직에 박힌 것은 **0건**. `SHOP_SLOTS`만 구조 상수로 예외.

### [C-5] interest.py ↔ reroll.py 골드 흐름 가정 충돌 → **PASS (합치 시 계약 문서화 필요)**

- 두 모듈 모두 **상호 import 없음** (grep 확인), 공통 골드 상태 없음. 각자 독립 함수:
  - `interest.calculate_interest_trajectory(start_gold, n_turns)`: 매 턴 `end_gold = start + interest`, 다음 턴 시작 = 이전 종료 (**라운드 종료 시 이자, 복리** — docstring L28 명시).
  - `reroll.reroll_trajectory(gold, n_rerolls)`: 고정 2골드 선형 차감, 이자 미반영.
- **충돌 없음**: 어느 쪽도 "라운드 시작 시" 가정을 쓰지 않음. interest는 종료 시 지급, reroll은 시점 무관 순수 차감.
- **주의 (F-7, 향후 strategy_comparator 계약)**: 두 트래젝션은 **같은 라운드 안의 순서(리롤 → 전투 → 이자)를 가정하지 않음**. 합칠 때 (a) 1라운드당 리롤 횟수, (b) 이자는 라운드 종료 골드에 1회만 — 이 2가지를 comparator에서 명시해야 이중 계산/누락 방지. 현재 comparator가 없어서 **잠재 리스크**만 보고.
- **부수 발견 F-3 (중간)**: `05_xp_gold.json`의 `interest` 필드는 공식 문자열(`floor(보유 골드 / 10)`)이고, `interest.py` docstring L23-25는 "공식은 표기용, 테이블이 기준"이라고 함. **두 JSON 필드(formula vs table)가 상수일 수 있는 구조적 취약점** — 현재는 둘이 일치(10골드/상한 5)하지만, 패치 갱신 시 한쪽만 수정하면 불일치. `load_interest_rules()`가 테이블만 쓰고 formula는 계산에 미사용(L62)하므로 **동작 영향 0**이나, (a) JSON에서 `formula` 필드 제거, 또는 (b) 로드 시 formula와 테이블 일치 검증 — 중 하나 권장. **판단 요청**.

### [C-6] test_reroll.py "20골드→10회" 예시의 시그니처 일치 → **PASS**

- `reroll.py`의 실제 시그니처 (로컬 모델이 임의로 바꾼 것):
  - `reroll_count(gold: int, rules=None) -> int` — 20골드 → 10 (`floor(20/2)`)
  - `reroll_trajectory(gold: int, num_rerolls: int, rules=None) -> list[dict]`
- `test_reroll.py` L57-59 `test_example_20_gold_is_10_rerolls`: `reroll_count(20) == 10` — **실제 함수와 일치**. 반환값 구조(int)도 문서("1회 리롤 비용", "가능한 리롤 횟수")와 일치.
- **판정**: "20골드→10회"는 `reroll_count`의 올바른 예시. 시그니처 임의 변경 없음. **PASS**.
- **부수**: `test_reroll.py`의 `rules` fixture(L17-19)는 일부 테스트에서 미사용 — 위생 문제, 기능 영향 0.

### [D-7] "우연히 통과하는" 케이스 / 상한 외 중간 구간 커버리지 → **PASS (부족 1건 지적)**

`test_interest.py` 커버리지 분석:

| 골드 | 테스트? | 어설션 값 |
|---|---|---|
| 0 | ✓ L68 | 0 |
| 9 | ✓ L85 | 0 |
| 10 | ✓ L86 | 1 |
| **15** | ✓ L87 | **1** (구 5골드 단위면 3) — **핵심 변별값** |
| 25 | ✓ L88 | 2 |
| **35** | **✗ 없음** | — |
| 49 | ✓ L89 | 4 |
| 50 | ✓ L90 | 5 (상한 시작) |
| 52 | ✓ L91 | 5 |
| 51/1000 | ✓ L74-76 | cap |

- **핵심 변별값 15골드**: 10골드 단위(정답)에서는 1, 구 5골드 단위(틀림)에서는 3 → **잘못된 5골드 로직을 잡아냄**. PASS.
- **부족 F-4 (경미)**: **30-39 밴드(35골드) 하드코딩 앵커 없음**. L168의 `{"gold": "30-39", "interest": 3}`은 `test_rules_follow_updated_json`의 **임시 JSON 생성 문자열**이지, `calculate_interest(35) == 3` 어설션이 아님. 30-39 구간은 경계값(30, 39) 테스트로만 커버되고 **35 같은 중간값에 대한 독립 하드코딩 검증이 없음**.
  - **영향**: 현재 테이블(30-39→3)이 JSON과 일치하므로 실질 리스크 낮음. 단 30-39 구간이 실수로 변형되면 경계값 테스트만으로는 감지 어려울 수 있음.
  - **수정 방법(권장)**: `test_corrected_boundary_values` parametrize에 `(35, 3)` 추가.
- **상한만 테스트로 숨겨지는 문제**(티켓 우려): **현재는 해당 없음**. 15(1), 25(2), 49(4) 등 상한 **아래**의 서로 다른 값(0/1/2/3/4)을 모두 하드코딩으로 검증하므로 중간 구간 로직도 구별됨. **PASS**.

---

## 발견 항목 종합 (우선순위)

| ID | 심각도 | 파일:라인 | 내용 | 수정 방법 |
|---|---|---|---|---|
| **F-1** | 중간 | `interest.py` L9-19, L23-25 | docstring에 구 5골드 단위 테이블 + "테이블 기준" 해설이 stale | docstring 예시를 10골드 단위("0-9" 시작)로 갱신, 해설 재작성 |
| **F-3** | 중간 | `05_xp_gold.json` L51 vs `interest.py` L62 | formula(공식 문자열)와 interest_table이 동일 진원 구조 없음. 한쪽만 갱신 시 불일치 | formula 필드 제거 또는 로드 시 일치 검증 assert (사용자 판단) |
| **F-2** | 경미 | `test_interest.py` L109 | 주석 `21-50`이 구 5골드 단위 구간 | `40-49 구간`으로 수정 |
| **F-4** | 경미 | `test_interest.py` | 30-39 밴드(35골드) 하드코딩 앵커 없음 | parametrize에 `(35, 3)` 추가 |
| **F-5** | 판단 | `reroll_discount` 토큰 7건 (A-2) | 정정 주석/문서/테스트에서 토큰 잔존 | 토큰 회피 표현으로 다듬을지/허용할지 사용자 결정 |
| **F-6** | 정보 | `roll_probability.py` L44 | `SHOP_SLOTS = 5` 하드코딩 (데이터에 없는 구조 상수) | 허용. 주석 명시됨 |
| **F-7** | 정보 | `interest.py`/`reroll.py` | strategy_comparator 합치 시 1라운드 순서(리롤→전투→이자) 계약 미문서화 | comparator 작성 시 명시 |

---

## 전체 결론

**다음 단계(롤 확률 계산기) 진행해도 안전한가: Y (Yes)**

근거:
1. **실행 경로에 5골드 단위 잔재 0건** — JSON/생성기/MD/HTML 전부 10골드 단위. 잔존은 docstring/주석(F-1, F-2)으로 **동작 영향 0**.
2. **`reroll_discount` 필드/변수 0건** — 잔존은 의도된 정정 주석/검증 어설션/문서.
3. **pool_sizes.json ↔ py 지금 이 순간 일치** (29/22/18/10/9).
4. **로직 리터럴 0건** (SHOP_SLOTS 예외, 구조 상수).
5. **interest ↔ reroll 골드 흐름 충돌 없음** (독립, 순서 계약만 comparator에서 명시 필요).
6. **테스트가 5골드 잔재를 실제로 잡아낼 변별력 보유** (15골드→1, 상한 외 0/1/2/4 커버).

**단, 진행 전 권장 (블로커 아님)**: F-1(docstring 갱신)과 F-4(35골드 앵커)는 수 분 수준 — "통과한 테스트를 신뢰한다"는 전제의 위신을 지키려면 다음 티켓에서 함께 처리 권장. F-3(formula/table 이중 진원)은 패치 갱신 시 불일치 원인이 될 수 있어 중기 과제로 등록 권장.

---
*이 보고서는 수정을 하지 않고 감사만 수행했습니다. 모든 수정은 별도 티켓에서 진행하세요.*
