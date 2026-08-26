# TFT Set 17 Decision Engine — 현행 구조 분석 보고서 (CURRENT_STRUCTURE.md)

## 1. 개요 및 저장소 실사 요약

본 문서는 TFT Set 17 프로젝트를 **"실시간 의사결정 보조 시스템 (Real-time Decision Support System)"**으로 전환하기 위한 1단계 저장소 실사(Repository Audit) 및 의존성/책임 분석 결과입니다.

- **분석 일자**: 2026-08-26
- **대상 파일**: Python 소스 34개, 테스트 12개, 정적 데이터 및 가이드 파일 10개
- **기존 테스트 통과 현황**: 206/206 테스트 Pass (100%)

---

## 2. 현행 디렉터리 및 모듈 구조

```text
tft-set17/
├── tft_guide/                    # TFT 가이드 및 정적 JSON 데이터 (아이템, 드랍률, 경험치 등)
│   ├── 01_items.json
│   ├── 02_augments.json
│   ├── 03_drop_rates.json
│   ├── 04_rounds.json
│   ├── 05_xp_gold.json
│   ├── 06_damage.json
│   └── 07_roster.json
├── TFT_DDragon/                  # Riot Data Dragon 에셋 (챔피언, 아이템, 시너지 PNG/JSON)
├── tft_set17.json                # Set 17 정식 챔피언 및 특성 정의 파일 (63명)
├── tft_mapping_17.json           # DDragon - Set 17 매핑 테이블
├── tft_guide.py                  # 가이드 데이터 조회 CLI/유틸리티
├── tft_view.py / tft_viewer.py   # 정적 데이터 뷰어 스크립트
├── output/
│   ├── economy/                  # 경제, 보드 파워, 롤 확률 및 전략 비교 모듈
│   │   ├── board_power.py        # 보드 파워 휴리스틱 v2 (성급/아이템/시너지)
│   │   ├── interest.py           # 이자 계산
│   │   ├── levelup.py            # 레벨업 비용 및 테이블
│   │   ├── reroll.py             # 리롤 비용 및 횟수
│   │   ├── roll_probability.py   # 챔피언 등장 확률 및 누적 확률
│   │   ├── strategy_comparator.py# 다중 턴 롤/업/이자 전략 시뮬레이션
│   │   └── test_*.py             # 경제 모듈 단위 테스트 (7개 파일)
│   ├── ml/                       # 배치 예측 머신러닝 학습 파이프라인
│   │   ├── train_placement_model.py # LightGBM 회귀/랭킹 모델
│   │   └── test_train_placement_model.py
│   ├── data_collection/          # Riot API 데이터 수집기
│   │   ├── riot_client.py        # Riot API Client (Rate Limit, Retry)
│   │   ├── collect_match_ids.py
│   │   ├── collect_match_details.py
│   │   └── test_riot_client.py
│   ├── video_analysis/           # 컴퓨터 비전 (CV) 및 영상 프레임 분석
│   │   ├── board_recognizer.py   # 필드/벤치/성급 인식기
│   │   ├── shop_recognizer.py    # 상점 5칸 인식기
│   │   ├── hybrid_shop_recognizer.py # 텍스트 OCR 융합 상점 인식기
│   │   ├── timeline_smoother.py  # 시간축 노이즈 제거기
│   │   ├── generate_shop_timeline.py # 구매 이벤트 추출 및 성급 추론
│   │   └── test_video_analysis.py
│   ├── dashboard/                # 종합 리포트 생성기
│   │   ├── report.py             # 게임 상태 종합 분석 리포트 CLI
│   │   └── test_report.py
│   └── webapp/                   # 대시보드 웹 애플리케이션
│       ├── backend/ (main.py, test_api.py) # FastAPI 백엔드
│       └── frontend/ (index.html, app.js, style.css)
```

---

## 3. 주요 모듈별 책임 및 의존성 분석

| 모듈 경로 | 주요 책임 | 현재 의존성 | 발견된 구조적 문제점 | 이동 대상 계층 |
|---|---|---|---|---|
| `output/economy/board_power.py` | Set 17 보드 가치(파워) 수치화 (유닛, 아이템, 시너지) | `roll_probability`, `tft_set17.json`, `01_items.json` | 데이터 로딩(`_load_weights`, `_load_items_db`)과 평가 로직이 한 파일에 혼재 | `evaluation/board/` & `data/loaders/` |
| `output/economy/interest.py`, `levelup.py`, `reroll.py` | TFT 기본 경제 규칙 연산 | `tft_guide/05_xp_gold.json` | 순수 함수 형태이나 전역 경로 참조 | `evaluation/economy/` & `data/loaders/` |
| `output/economy/roll_probability.py` | 레벨별/풀 크기별 유닛 등장 확률 | `tft_guide/03_drop_rates.json` | 확률 계산과 데이터 파싱 결합 | `evaluation/upgrades/` |
| `output/economy/strategy_comparator.py` | 다중 턴 롤/업/이자 전략 시뮬레이션 | `interest`, `reroll`, `levelup`, `roll_probability` | Action/Simulation 추상화 없이 dict 입출력으로 결합 | `simulation/future_state/` |
| `output/video_analysis/board_recognizer.py` | 게임 화면에서 기물/성급/아이템 검출 | OpenCV, Tesseract, `tft_set17.json`, DDragon | 비전 인식 결과와 게임 상태 생성이 강결합 (Observation 계층 부재) | `vision/pipeline/` & `vision/adapters/` |
| `output/dashboard/report.py` | 종합 리포트 및 전략 코멘트 생성 | `board_power`, `interest`, `levelup`, `strategy_comparator` | 상태 평가(Evaluation), 룰 기반 코멘트(Explanation)가 CLI와 혼재 | `explanation/` & `application/services/` |
| `output/webapp/backend/main.py` | FastAPI 웹 엔드포인트 | `report`, `board_power` | API 계층이 저수준 평가 함수 및 내부 데이터 로더 직접 호출 | `api/` & `application/` |
| `output/ml/train_placement_model.py` | 보드 상태 기반 최종 순위 예측 | `board_power`, LightGBM, Pandas | 피처 엔지니어링이 `board_power` dict 구조에 직접 의존 | `evaluation/models/` or `simulation/` |

---

## 4. 현행 아키텍처의 핵심 결함

1. **단일한 `GameState` 도메인 모델의 부재**:
   - `board_power.py`는 `{"units": [...]}`를 입력받음.
   - `strategy_comparator.py`는 `(gold, level, xp)` 인자들을 개별로 받음.
   - `report.py`는 임의의 dict `state`를 파싱함.
   - `board_recognizer.py`는 `{"field_units": [...], "bench_units": [...]}`를 반환함.
   - **결과**: 모듈 간 데이터 교환 시 필드명 오타나 누락에 취약함.

2. **비전(CV)과 도메인의 강결합 및 Observation 계층 누락**:
   - 비전 인식기가 화면에서 "무엇을 보았는가(좌표, 픽셀, 템플릿 점수)"와 "게임 상 실제 상태(1성/2성, 덱 구성)"를 구분하지 않고 즉시 도메인 객체로 변환.

3. **의사결정(Decision) 및 설명(Explanation) 계층 부재**:
   - `report.py` 내의 `generate_tactical_comment`가 단순 문자열 포맷팅으로 하드코딩되어 있어, 구조화된 근거(Evidence)와 확신도(Confidence)를 제공하지 못함.

4. **외부 계층(Web API / CLI)의 내부 모듈 직접 침범**:
   - `main.py`가 `bp._load_champions_db()`와 같은 내부 헬퍼 함수를 직접 import하여 사용 중.
