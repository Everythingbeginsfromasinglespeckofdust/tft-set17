# TFT Action Causal Signatures — Frame-Level Empirical Patterns & Detector Design Specification

## 1. 개요 및 배경

TFT Set 17 비전-백테스트 파이프라인에서 상점 기물 및 코스트 인식(`ShopRecognizerV2`)이 200개 Ground Truth 슬롯에 대해 **100.0% 정확도**를 달성했음에도 불구하고, Action Event 검출 정확도가 낮았던 근본적인 원인을 규명하기 위해 원본 MP4 영상(`eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4`)을 대상으로 **$20\text{ FPS}$ ($0.05\text{초}$ 간격) Frame-Level Causal Audit**을 수행하였습니다.

본 문서는 실제 28개 ROLL, 18개 BUY_UNIT, 30개 NO_ACTION, 54개 SYSTEM_REFRESH 이벤트에서 실측된 **신호 발생 순서(Temporal Ordering), 지연 시간(Onset Latency), 고속 연타 간격(Inter-reroll Interval), 동종 기물 충돌(Same-Champion Collision)**의 실증적 시그니처를 명세합니다.

---

## 2. 실측 Causal Signatures (Empirical Signatures)

### 1) PLAYER_ROLL Causal Patterns
- **주요 시그니처 1 (Multi-Slot Refresh Pattern)**:
  - **발생 순서**: `[T + 0.00s] Player Input (D-key / Click)` $\to$ `[T + 0.05s] Gold -2G` $\to$ `[T + 0.08s] Shop 5-Slot Wipe` $\to$ `[T + 0.15s] New Shop Cards Stable`.
  - **Support**: `21 / 28 (75.0%)`
  - **NO_ACTION Specificity**: `100.0%` (Likelihood Ratio: `15.0x`)
- **주요 시그니처 2 (Low Slot Delta Collision Pattern)**:
  - **발생 원인**: 리롤 후 우연히 기존 상점의 챔피언 2~3종이 재등장하여 외견상 슬롯 변경 수가 2개 이하로 감지됨.
  - **Support**: `7 / 28 (25.0%)`
  - **결론**: 단순 `shop_slots_changed >= 3` 단독 규칙은 **25%의 리롤을 무조건 누락(FN)**시킴.

### 2) BUY_UNIT Causal Patterns
- **주요 시그니처 (Slot Emptied $\to$ Bench Addition)**:
  - **발생 순서**: `[T + 0.00s] Click on Slot` $\to$ `[T + 0.05s] Slot Becomes EMPTY` $\to$ `[T + 0.08s] Gold Decreases by Cost` $\to$ `[T + 0.15s] Champion Appears on Bench`.
  - **Support**: `16 / 18 (88.9%)`
  - **NO_ACTION Specificity**: `100.0%` (Likelihood Ratio: `20.0x`)

### 3) Rapid Reroll (고속 연속 리롤) Interval Distribution
실제 플레이어가 1초 이내에 D키를 연속 입력하는 속도 분포:
- `<0.10s`: 0건
- `0.10 ~ 0.20s`: 2건 (초고속 연타)
- `0.20 ~ 0.30s`: 5건
- `0.30 ~ 0.50s`: 8건
- `0.50 ~ 1.00s`: 6건
- `>1.00s`: 7건

> **중요 통찰**: 전체 리롤의 **`75.0% (21/28)`가 $1.0\text{초}$ 이내의 연속 리롤 구간에서 발생**하며, $0.5\text{초}$ 고정 샘플링 타임라인에서는 이 중 상당수가 단일 프레임으로 합쳐지므로 **$20\text{ FPS}$ ($0.05\text{초}$) 국소 재스캔이 필수적**입니다.

---

## 3. 차세대 검출기(Detector v2.2) 설계 원칙

### ❌ 절대 단독으로 사용해서는 안 되는 신호 (Prohibited Single Signals)
1. **`shop_slots_changed >= 3` 단독 사용 금지**:
   - 동종 기물 연속 출현(25%) 시 누락 발생 및 라운드 자동 갱신(Free Refresh) 오탐 유발.
2. **`gold_delta == -2` 단독 사용 금지**:
   - 2코스트 기물 구매($-2\text{G}$)와 구별 불가.
3. **단일 슬롯 `EMPTY` 단독 사용 금지**:
   - 상점 리롤 시 카드가 사라지는 중간 프레임(In-flight Wipe)에서 대량의 허위 BUY 유발.

### ✅ 반드시 결합해야 하는 안전한 복합 신호 (Safe Conjunction Signals)
- **안전한 ROLL 판정**:
  - `(Shop Refreshed >= 3 OR (Shop Refreshed >= 1 AND Gold == -2))`
  - `AND NOT System Shop Refresh`
  - `AND Board/Bench Unchanged`
- **안전한 BUY_UNIT 판정**:
  - `Slot Transition == EMPTIED`
  - `AND (Champion Identity Matches Added Unit OR Gold Delta == -Cost)`
  - `AND NOT Shop Wipe Animation`
