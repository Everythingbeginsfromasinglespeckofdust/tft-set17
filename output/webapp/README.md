# TFT Set 17 전략 대시보드 웹 애플리케이션 (`output/webapp`)

TFT Set 17의 경제 시뮬레이션(`interest`, `levelup`, `reroll`, `roll_probability`, `strategy_comparator`)과 실측 기반 보드 가치평가 v2(`board_power`)를 웹 UI 환경에서 직관적으로 사용할 수 있도록 구축된 풀스택 웹 애플리케이션입니다.

---

## 1. 아키텍처 및 모듈 연동

- **백엔드 (`output/webapp/backend/main.py`)**:
  - **FastAPI** 기반 경량 REST API 서버
  - `output/dashboard/report.py`의 `generate_dashboard_report()` 내부 함수를 재사용하여 계산 로직의 중복 없이 CLI와 100% 동일한 결과 도출
  - 도메인 유효성 검증 예외(`ValueError`)를 사용자 친화적인 HTTP 400 에러 메시지로 변환
  - CORS 미들웨어 적용 (`allow_origins=["*"]`)
  - 정적 파일 마운트(`/static`) 및 루트(`/`) 접속 시 프론트엔드 UI 자동 서빙
- **프론트엔드 (`output/webapp/frontend/`)**:
  - Vanilla HTML5 / CSS3 / JavaScript (외부 프레임워크 종속성 없음)
  - 다크 테마 기반 반응형 대시보드 UI
  - 챔피언 및 완성/부품 아이템 동적 드롭다운 보드 빌더
  - 예시 시나리오 3종 1-클릭 로드 및 5단계 리포트 렌더링

---

## 2. API 엔드포인트 명세

| Method | Endpoint | 설명 |
|---|---|---|
| `POST` | `/api/report` | 게임 상태(골드, 레벨, XP, 라운드, 보드, 전략)를 전달받아 5단계 종합 분석 리포트 JSON 반환 |
| `GET` | `/api/champions` | Set 17 챔피언 전체 목록(이름, 코스트, 시너지) 반환 |
| `GET` | `/api/items` | 기본 부품 및 완성 아이템 목록 반환 |
| `GET` | `/api/scenarios` | 3가지 사전 정의된 예시 시나리오 데이터 반환 |
| `GET` | `/` | 프론트엔드 웹 대시보드 메인 페이지 서빙 |

---

## 3. 로컬 실행 방법

### 1) 의존성 설치
```bash
pip install fastapi uvicorn httpx
```

### 2) 백엔드 및 웹 서버 실행
프로젝트 루트 또는 `output/webapp/backend` 디렉토리에서 다음 명령을 실행합니다:

```bash
cd output/webapp/backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3) 웹 브라우저 접속
브라우저를 열고 다음 URL에 접속합니다:
👉 **`http://localhost:8000`**

---

## 4. 테스트 및 검증

백엔드 API 및 전체 프로젝트 통합 테스트는 pytest로 실행할 수 있습니다:

```bash
# 전체 테스트 실행 (198개 테스트 통과)
python -m pytest -v
```
