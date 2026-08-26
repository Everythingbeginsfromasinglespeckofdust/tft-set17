# TFT Set 17 Decision Engine — 점진적 리팩터링 및 마이그레이션 계획서 (MIGRATION_PLAN.md)

## 1. 마이그레이션 기본 원칙

1. **점진적 전환 (Zero Downtime / Zero Breakage)**:
   - 새 패키지 `src/tft/`를 독립적으로 구축하고, 기존 `output/economy/`, `output/dashboard/`, `output/webapp/` 파일들은 새 모듈을 위임 호출하는 어댑터 형태로 전환.
   - 기존의 206개 테스트 케이스가 단 하나도 깨지지 않고 100% 통과하도록 유지.
2. **책임 분리 우선 (Architecture First)**:
   - 각 계층 간의 데이터 계약(Interface / Dataclass)을 먼저 정의하고 구현을 채움.

---

## 2. 세부 실행 단계

### [단계 1] 데이터 계층 (`src/tft/data/`)
- `StaticDataRepository`: Set 17 챔피언, 특성, 아이템(부품/완성품), 드랍률, 레벨업 테이블, 보드 파워 가중치 v2의 단일 로더 구현.
- 싱글톤/의존성 주입 패턴으로 파일 I/O 중복 제거.

### [단계 2] 도메인 계층 (`src/tft/domain/`)
- `Unit`, `Item`, `Trait`, `Augment`, `PlayerState`, `LobbyState` 불변(frozen) 데이터클래스 정의.
- `GameState`: 순수 게임 상태 컨테이너 구현 (`from_dict`, `to_dict` 직렬화 지원).
- `actions.py`: `ActionType` (ROLL, LEVEL_UP, SAVE, BUY_UNIT, SELL_UNIT, SLAM_ITEM) 및 `Action` 모델 정의.

### [단계 3] 비전 및 관측 계층 (`src/tft/vision/`)
- `observation.py`: `Observation`, `CardObservation`, `UnitObservation` 정의.
- `adapters.py`: `ObservationToGameStateBuilder` (관측 데이터로부터 정규화된 `GameState` 생성).

### [단계 4] 평가 계층 (`src/tft/evaluation/`)
- `BoardEvaluator`: 기존 `board_power.py`의 휴리스틱 v2 계산 로직을 `GameState` 기반으로 정제.
- `EconomyEvaluator`: 이자율, 50G 도달 가능성, 템포 평가.
- `UpgradeEvaluator`: 핵심 유닛 2성/3성 롤링 확률 및 풀 상태 평가.
- `SurvivalEvaluator`: HP 잔여량 및 탈락 리스크 평가.
- `EvaluationResult`: 정량 점수(score) 및 세부 메트릭 딕셔너리 표준화.

### [단계 5] 시뮬레이션 계층 (`src/tft/simulation/`)
- `future_state.py`: 기존 `strategy_comparator.py`의 다중 턴 롤/업/이자 시뮬레이션을 `(GameState, Action, Horizon)` 기반 객체 지향 시뮬레이터로 캡슐화.
- `SimulationResult`: N턴 후 예상 골드, 레벨, 파워, 2성 달성 확률 반환.

### [단계 6] 의사결정 및 설명 계층 (`src/tft/decision/`, `src/tft/explanation/`)
- `ActionScorer`: 평가 및 시뮬레이션 결과를 결합하여 각 Action의 효용 점수 계산.
- `DecisionEngine`: `GameState`를 입력받아 최적 `Recommendation` 도출.
- `ExplanationGenerator`: 추천에 대한 구조화된 근거(Reason, Evidence, Confidence) 생성.

### [단계 7] 응용 서비스 및 어댑터 계층 (`src/tft/application/`, 레거시 호환)
- `DecisionService`: 단일 진입점 (`evaluate_and_decide(game_state)`).
- 기존 `output/economy/board_power.py`, `interest.py`, `levelup.py`, `reroll.py`, `roll_probability.py`, `strategy_comparator.py`가 새 `src/tft/` 모듈을 위임 호출하도록 브릿지 구성.
- `output/dashboard/report.py` 및 `output/webapp/backend/main.py` 리팩터링.

### [단계 8] 계층화된 신규 테스트 구축 및 회귀 검증 (`tests/`)
- `tests/unit/domain/`, `tests/unit/evaluation/`, `tests/unit/simulation/`, `tests/unit/decision/`, `tests/unit/explanation/` 신규 테스트 작성.
- 전체 206개 레거시 테스트 + 신규 테스트 전체 실행 및 100% 통과 확인.
