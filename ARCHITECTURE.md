# TFT Set 17 Decision Engine — 목표 아키텍처 명세서 (ARCHITECTURE.md)

## 1. 아키텍처 비전 및 핵심 개념

TFT Set 17 Decision Engine은 단순 정보 조회를 넘어 **"실시간 게임 상태 추출 → 가치 평가 → 다중 미래 시뮬레이션 → 최적 행동 결정 → 근거 기반 설명"**을 완결하는 AI 의사결정 보조 시스템입니다.

```text
       ┌──────────────────┐
       │   Game Screen    │
       └────────┬─────────┘
                │
                ↓
       ┌──────────────────┐
       │  Vision Pipeline │
       └────────┬─────────┘
                │
                ↓
       ┌──────────────────┐
       │   Observation    │  (화면에서 인식된 물리적 관측값)
       └────────┬─────────┘
                │ [GameStateBuilder]
                ↓
       ┌──────────────────┐
       │    GameState     │  (도메인 핵심 계약: 게임의 실제 논리 상태)
       └────────┬─────────┘
                │
        ┌───────┴────────┐
        ↓                ↓
┌──────────────┐  ┌──────────────┐
│  Evaluation  │  │  Simulation  │
│    Layer     │  │    Layer     │
└───────┬──────┘  └──────┬───────┘
        │                │
        └───────┬────────┘
                │
                ↓
       ┌──────────────────┐
       │ Decision Engine  │  (Action 평가 및 최적안 결정)
       └────────┬─────────┘
                │
                ↓
       ┌──────────────────┐
       │  Recommendation  │
       └────────┬─────────┘
                │
                ↓
       ┌──────────────────┐
       │   Explanation    │  (구조화된 이유, 근거, 확신도)
       └────────┬─────────┘
                │
         ┌──────┴──────┐
         ↓             ↓
    Web API / UI    CLI Tools
```

---

## 2. 계층별 책임 및 모듈 정의

```text
src/tft/
├── domain/                  # 1. 도메인 계층 (순수 상태 및 데이터 구조, 계산 로직 배제)
│   ├── game_state.py        # GameState, PlayerState, LobbyState
│   ├── units.py             # Unit, Champion, BoardPosition
│   ├── items.py             # Item, ItemType (Component/Completed)
│   ├── traits.py            # Trait, TraitBreakpoint
│   ├── augments.py          # Augment, AugmentTier
│   └── actions.py           # Action, ActionType (ROLL, LEVEL_UP, SAVE, BUY, SELL, SLAM)
│
├── data/                    # 2. 데이터 계층 (정적 데이터 로딩, 검증 및 저장소)
│   ├── repositories.py      # StaticDataRepository (싱글톤 또는 주입 가능한 Set17 데이터 레포)
│   ├── loaders.py           # JSON 및 DDragon 로더
│   └── schemas.py           # 데이터 스키마 및 검증 규칙
│
├── vision/                  # 3. 비전 및 관측 계층 (화면 인식 -> Observation -> GameState)
│   ├── observation.py       # Observation, CardObservation, UnitObservation (물리적 인식 결과)
│   ├── pipeline.py          # VisionPipeline 추상 인터페이스
│   └── adapters.py          # ObservationToGameStateBuilder (CV -> GameState 변환기)
│
├── evaluation/              # 4. 평가 계층 (현재 상태의 다각도 가치 정량화)
│   ├── models.py            # EvaluationResult, Metric, DimensionScore
│   ├── board_evaluator.py   # 보드 파워(유닛 가치, 시너지 보너스, 3신기 점수) 평가
│   ├── economy_evaluator.py # 이자율, 골드 건전성, 템포 평가
│   ├── upgrade_evaluator.py # 2성/3성 달성 기대치 및 롤 확률 평가
│   ├── survival_evaluator.py# 현재 HP, 스테이지별 탈락 위험도 평가
│   └── lobby_evaluator.py   # 상대방 보드 파워 대비 상대적 강도 평가
│
├── simulation/              # 5. 시뮬레이션 계층 (Action 적용 시 N턴 후 미래 상태 예측)
│   ├── models.py            # SimulationResult, FutureTrajectory
│   ├── economy_simulator.py # 복리 이자 및 라운드 기본 골드 유입 예측
│   ├── roll_simulator.py    # 롤링 시 기물 획득 및 2성 완성 확률 시뮬레이션
│   ├── level_simulator.py   # 레벨업 비용 및 도달 턴수 시뮬레이션
│   └── future_state.py      # 다중 턴 전략 비교기 (Strategy Simulator)
│
├── decision/                # 6. 의사결정 계층 (가능한 Action 점수화 및 최적안 추천)
│   ├── models.py            # ActionScore, DecisionResult
│   ├── scorer.py            # Evaluation + Simulation 결과를 종합한 Action Scorer
│   └── engine.py            # DecisionEngine (GameState -> Recommendation)
│
├── explanation/             # 7. 설명 계층 (추천 사유 및 구조화된 근거 생성)
│   ├── models.py            # Reason, Evidence, Explanation
│   └── generator.py         # ExplanationGenerator (정량 지표 기반 근거 조립기)
│
├── application/             # 8. 응용 서비스 계층 (유스케이스 조율)
│   └── services.py          # DecisionService, GameAnalysisService
│
└── infrastructure/          # 9. 인프라 계층 (환경설정, 로깅, 외부 API 통신)
    ├── config.py
    └── logging.py
```

---

## 3. 핵심 계약(Contract): `GameState` & `Observation`

### 3.1 `GameState` (도메인 중심 계약)
`GameState`는 **게임의 논리적 진실 상태만을 표현**하며, UI 포맷팅이나 추천 로직을 포함하지 않습니다.

```python
@dataclass(frozen=True)
class GameState:
    stage: int                   # 예: 3
    round: int                   # 예: 2 (3-2)
    stage_round: str             # "3-2"
    player: PlayerState          # gold, level, xp, hp, streak
    board_units: List[Unit]      # 필드에 배치된 유닛들
    bench_units: List[Unit]      # 벤치에 보유한 유닛들
    shop_units: List[Optional[str]] # 상점 5칸 챔피언 이름
    items: List[Item]            # 아이템 벤치 보유 아이템
    augments: List[Augment]      # 선택된 증강체들
    opponents: List[LobbyState]  # 로비 타 플레이어 요약 상태 (선택)
```

### 3.2 `Observation` (비전 인식 결과 계약)
`Observation`은 CV 파이프라인이 화면에서 인식한 원시 관측값을 담습니다.

```python
@dataclass(frozen=True)
class Observation:
    timestamp: float             # 영상/스트림 시점 (초)
    stage_text: Optional[str]    # OCR된 스테이지 문자열
    gold_val: Optional[int]      # OCR된 골드 수치
    hp_val: Optional[int]        # OCR된 체력 수치
    shop_cards: List[CardObservation] # 상점 5슬롯 인식 결과 (신뢰도 포함)
    field_detections: List[UnitObservation] # 필드 슬롯별 인식 유닛 및 성급
    bench_detections: List[UnitObservation] # 벤치 슬롯별 인식 유닛 및 성급
    overall_confidence: float    # 관측 신뢰도 점수
```

---

## 4. 엄격한 의존성 규칙 (Dependency Rules)

1. **단방향 흐름 원칙**:
   - `Vision → Observation → GameStateBuilder → GameState`
   - `GameState → Evaluation / Simulation → Decision → Explanation → Application → API / UI`
2. **역방향 의존 금지**:
   - `Domain`은 `Evaluation`, `Decision`, `Vision`, `Web`을 절대 import하지 않는다.
   - `Evaluation`과 `Simulation`은 `Decision`이나 `UI`를 import하지 않는다.
   - `Decision`은 `UI`나 `Vision`을 import하지 않는다.
3. **외부 계층 침범 금지**:
   - `API` 및 `CLI`는 오직 `Application Service` 또는 공개 인터페이스만을 호출하며, 내부 저수준 계산기(`_load_weights` 등)를 직접 호출하지 않는다.

---

## 5. 단계별 마이그레이션 및 호환성 보장 전략

- 기존 `output/economy/`, `output/dashboard/`, `output/webapp/`의 모든 공개 함수는 새 계층(`src/tft/`)의 모듈을 위임(Delegation) 호출하는 **어댑터(Backwards Compatibility Adapter)**로 유지하여, **기존 206개 테스트 및 외부 스크립트가 100% 정상 작동**하도록 보장합니다.
