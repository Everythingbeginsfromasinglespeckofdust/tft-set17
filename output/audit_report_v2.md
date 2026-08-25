# TFT Set 17 경제 모듈 QA 감사 보고서 v2

- **감사 일시**: 2026-08-25
- **감사 역할**: QA 감사 담당자
- **감사 대상**:
  - `/output/pool_sizes.{json,py}`
  - `/output/economy/{interest,reroll,roll_probability,levelup}.py`
  - `/output/economy/{test_interest,test_reroll,test_pool_sizes,test_roll_probability,test_levelup}.py`

---

## 1. 종합 평가 요약

| 항목 | 감사 항목 | 결과 | 비고 |
|---|---|:---:|---|
| **[A-1]** | pytest 전체 재실행 | **PASS** | 총 138개 테스트 전수 통과 (0 failed, 0 skipped) |
| **[A-2]** | 4대 핵심 회귀 앵커 직접 호출 | **PASS** | 4건 모두 설계값과 100% 일치 |
| **[B-3]** | JSON 데이터 소스 참조 일관성 | **PASS** | 5개 모듈 전체가 동일한 `output/tft_guide/` 및 `output/pool_sizes.json` 참조 |
| **[B-4]** | 정수/불리언 검증 헬퍼 중복 여부 | **NOTICE** | `levelup`은 `roll_probability._check_int` 재사용, `interest`/`reroll`/`pool_sizes`는 인라인 중복 구현 (지적) |
| **[C-5]** | AST 기준 하드코딩 재스캔 | **PASS** | 허용 예외(`SHOP_SLOTS = 5`) 외 신규 하드코딩 부재 확인 |
| **[D-6]** | 실제 시나리오 E2E 수동 계산 | **PASS** | 골드 47/Lv6/XP0 시나리오 4단계 연속 계산 및 유효 범위 정합성 확인 |
| **[E-7]** | Git 워크트리 및 원격 동기화 | **PASS** | Clean working tree, 로컬 HEAD ↔ `origin/master` 일치 (`baa5035`) |

---

## 2. 상세 감사 결과

### [A] 전체 재실행 (Full Re-execution)

#### 1. pytest 실제 실행 결과
- **총 테스트 수**: 138개 수집 및 138개 전수 통과 (실행 시간: 0.56s)
- **테스트 파일별 상세 현황**:
  - `test_interest.py`: **29 Passed** (10골드 단위 테이블, 상한선, 복리 트래젝션, bool 거부 등)
  - `test_levelup.py`: **44 Passed** (연속 체인 무결성, 6→7레벨 30골드 앵커, 바 초과 교차 검증 등)
  - `test_pool_sizes.py`: **7 Passed** (외부 검증 확정값 {1:29, 2:22, 3:18, 4:10, 5:9}, 음수/bool 차단 등)
  - `test_reroll.py`: **20 Passed** (고정 2골드, 소모 트래젝션, 제거된 메커니즘 재발 방지 등)
  - `test_roll_probability.py`: **38 Passed** (11레벨 제외, 8.06% 정확식 앵커, 풀 고갈 및 F-R1/F-R2 검증)

> **[참고: 환경 의존성 점검]**
> `test_roll_probability.py`의 3개 테스트(`test_ddragon_fallback_extraction_matches_roster_snapshot`, `test_load_roster_falls_back_when_snapshot_missing`, `test_roster_snapshot_matches_ddragon_now`)는 untracked 벤더 미러인 `TFT_DDragon`이 존재해야 통과합니다. `.gitignore` 주석에 명시된 원격 태그(`v17.9`, commit `22fb2571`)로 체크아웃 시 138개 전수 정상 통과함을 확인했습니다.

#### 2. 4대 핵심 회귀 앵커 직접 호출 검증
실제 Python 런타임에서 각 모듈 함수를 직접 호출하여 반환값을 검증했습니다.

| 앵커 함수 호출 | 기대값 | 실제 반환값 | 판정 |
|---|---|---|:---:|
| `interest.calculate_interest_trajectory(15, 1)` | 이자 1 (종료 골드 16) | `[{'turn': 1, 'start_gold': 15, 'interest': 1, 'end_gold': 16}]` | **PASS** |
| `reroll.reroll_count(20)` | 10 | `10` | **PASS** |
| `roll_probability.unit_hit_probability("진", 5, 9, 0, 0, 1)` | prob_at_least_one ≈ 8.0601% | `0.0806014673353912` (근사식 8.3333%와 차이 확인) | **PASS** |
| `levelup.gold_to_reach_level(6, 0, 7)` | 30 | `30` (60 XP / 4 = 15회 × 2G = 30G) | **PASS** |

---

### [B] 모듈 간 일관성 (Inter-module Consistency)

#### 3. JSON 참조 경로 및 캐시 사본 확인
모든 모듈이 파일 시스템 상의 단일 진원(Single Source of Truth)을 참조하고 있는지 절대 경로 기준으로 추적했습니다.
- `pool_sizes.py`: `output/pool_sizes.json` (정상)
- `interest.py`: `output/tft_guide/05_xp_gold.json` (정상)
- `reroll.py`: `output/tft_guide/05_xp_gold.json` (정상)
- `levelup.py`: `output/tft_guide/05_xp_gold.json` (정상)
- `roll_probability.py`: `output/tft_guide/03_drop_rates.json`, `07_roster.json`, `05_xp_gold.json`, `output/pool_sizes.json` (정상)

*루트 `tft_guide/`와 `output/tft_guide/` 내 7개 JSON 파일(`01_items` ~ `07_roster`)을 바이트 단위로 비교한 결과 100% 일치함을 확인했습니다.*

#### 4. 정수/불리언 검증 헬퍼(`_check_int`) 현황 지적
- **공유 상태**:
  - `roll_probability.py`에서 `_check_int(name, value)` 및 `_is_int(value)` 정의
  - `levelup.py`는 `from roll_probability import _check_int`로 직접 import하여 공유
- **중복 구현 지적**:
  - `interest.py`: `calculate_interest` 및 `calculate_interest_trajectory` 내에서 `if not isinstance(x, int) or isinstance(x, bool):` 형태로 인라인 중복 구현.
  - `reroll.py`: `reroll_count` 및 `reroll_trajectory` 내에서 인라인 중복 구현.
  - `pool_sizes.py`: `load_pool_sizes` 내에서 인라인 중복 구현.
- **평가**: 모든 모듈이 `bool`을 정수로 오인하지 않는 F-R2 보안 규칙을 충족하고 있으나, 코드 중복이 존재합니다. (제약에 따라 현재 수정하지 않고 지적만 기록하며, 추후 공통 검증 유틸리티로의 리팩터링을 권장합니다.)

---

### [C] 하드코딩 재감사 (AST Scan)

#### 5. AST 기반 전체 숫자 리터럴 분석
Python AST 모듈로 `output/` 및 `output/economy/`의 5개 소스 파일을 파싱하여 숫자 리터럴을 전수 검사했습니다.

- **`pool_sizes.py`**:
  - `COSTS = (1, 2, 3, 4, 5)` (티어 정의 상수)
  - `value <= 0` (유효성 검사)
- **`interest.py`**:
  - `gold < 0`, `num_turns < 1`, `range(1, num_turns + 1)` (기본 루프 및 유효성 검사)
  - 이자 테이블 구간 및 상한선은 전량 `05_xp_gold.json`에서 파싱.
- **`reroll.py`**:
  - `cost <= 0`, `gold < 0`, `num_rerolls < 1` (기본 유효성 검사)
  - 리롤 비용(2G)은 `05_xp_gold.json`의 `reroll_cost`에서 동적 로드.
- **`levelup.py`**:
  - `buy_xp_cost_gold: int = 2`, `buy_xp_amount: int = 4` (티켓 요구 시그니처에 따른 기본 매개변수)
  - `range(2, max_level + 1)`, `range(0, max(table) + 1)` (누적 계산 인덱스)
  - XP 테이블(2/6/10/20/36/60/68/68/68)과 max_level(10)은 전량 `05_xp_gold.json`에서 동적 로드.
- **`roll_probability.py`**:
  - `SHOP_SLOTS = 5` (Line 58, 2026-08-24 감사 F-6에서 승인된 구조적 클라이언트 불변 상수)
  - `100.0` (백분율 → 소수 변환)
  - `1.0 - (1.0 - p_slot) ** SHOP_SLOTS` (이항분포 정확식)
  - 드랍률, 로스터 크기, 카피 수는 전량 JSON에서 동적 로드.

**결론**: 신규로 무단 유입된 하드코딩 매직 넘버는 0건입니다.

---

### [D] 실제 시나리오 E2E 수동 계산

**초기 상태**: 골드 47, 레벨 6, XP 0

```
[초기 상태]
골드: 47G | 레벨: 6 | XP: 0

    │
    ▼ (a) 1턴 이자 수급 (interest.py)
    │     calculate_interest(47) = 4G
    │     1턴 후 총 골드 = 47 + 4 = 51G
    │
    ▼ (b) 골드의 절반(51 // 2 = 25G)을 리롤에 투자 (reroll.py)
    │     reroll_count(25) = floor(25 / 2) = 12회
    │     리롤 비용 = 12 * 2 = 24G
    │     리롤 후 잔여 골드 = 51 - 24 = 27G
    │
    ▼ (c) 잔여 27G로 레벨 7 도달 가능 여부 (levelup.py)
    │     gold_to_reach_level(6, 0, 7) = 30G (필요 XP 60 / 4 = 15회 × 2G)
    │     27G < 30G → [도달 불가] (3G 부족, 13회/52XP만 구매 가능)
    │
    ▼ (d) 레벨 6에서 12회 리롤 동안 5코스트 기물('진') 등장 확률 (roll_probability.py)
          - 레벨 6 드랍률 테이블상 5코스트 드랍률 = 0%
          - prob_per_slot = 0.0
          - prob_at_least_one_per_roll = 0.0
          - expected_count_over_rolls = 0.0
          - gold_per_expected_unit = inf
```

- **정합성 점검 결과**:
  - 중간/최종 골드가 음수가 되지 않음 (51G → 27G).
  - 확률 값이 [0.0, 1.0] 닫힌 구간 내에 완벽히 머무름.
  - 4개 모듈 간 상태 전달 및 반환값이 논리적/상식적으로 완벽히 부합함.

---

### [E] Git 및 원격 상태

- `git status`: `nothing to commit, working tree clean`
- `git log -n 2 --oneline`:
  - `baa5035` (HEAD -> master, origin/master, origin/HEAD) Add level-up cost loader (levelup.py) with XP-purchase gold calc
  - `f7e8de2` economy module rebuild after container reset
- 로컬 HEAD와 `origin/master`가 완전히 일치함을 확인.

---

## 3. 최종 결론

### **티켓 1-4 (전략 비교기, strategy_comparator) 진행해도 안전한가?**

# 👉 **[ Y ] — 진행 안전함**

**판정 근거**:
1. 5개 경제 핵심 모듈(`pool_sizes`, `interest`, `reroll`, `levelup`, `roll_probability`)의 138개 테스트가 100% 통과했습니다.
2. 4대 핵심 회귀 앵커가 단 1의 오차도 없이 정상 작동합니다.
3. 데이터 소스가 단일 진원(`tft_guide/*.json`, `pool_sizes.json`)으로 일관되게 연결되어 있으며, 신규 하드코딩이 유입되지 않았습니다.
4. E2E 시나리오 수동 연계 검증을 통해 모듈 간 파이프라인 결합 시 수학적/논리적 결함이 발생하지 않음을 증명했습니다.
