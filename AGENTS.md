# AGENTS.md — TFT Set 17 (17.9) 가이드 프로젝트

## 구조
- `tft_guide.py` — Data Dragon(`TFT_DDragon/data/ko_KR`) 기반 가이드 생성기. `python3 tft_guide.py` 로 `tft_guide/01~06.json` + `TFT_17.9_가이드.md` 재생성. **가이드 JSON 수정은 생성기에서 하면 재생성 시 회귀하지 않음.**
- `tft_viewer.py` — 로컬 이미지(`TFT_DDragon/img`) 뷰어. `python3 tft_viewer.py --no-browser` → `tft_set17_viewer.html` 재생성 후 서버 실행(포트 18080).
- `output/economy/` (git 추적 — 루트 `/output` 은 여기로 심볼릭 링크) — 이자·리롤·롤확률 계산 모듈 + pytest (`interest.py`, `reroll.py`, `roll_probability.py`, `test_*.py`). 규칙은 `output/tft_guide/05_xp_gold.json`·`03_drop_rates.json`·`07_roster.json`에서 로드(하드코딩 금지).
- `output/pool_sizes.{py,json}` — 코스트별 1종 카피 수 K_c = {1:29, 2:22, 3:18, 4:10, 5:9}. 외부 검증 확정값이며 DDragon/CDN에 없어 JSON에 직접 저장.
- `TFT_DDragon/`, `TFT_Spider/` — 벤더 업스트림 미러 (untracked, 재클론 핀은 .gitignore 주석). DDragon = tag v17.9 (22fb2571), Spider = 11fc6ca (Set 15 중국어 캐시, 17.9에 미사용).
- `verification_needed.md` — 미검증 클라이언트 상수 목록(P0 경제 → P1 피해). **2026-08-25 컨테이너 리셋으로 소실 — 재작성 필요.**

## 2026-08-25 컨테이너 리셋 재건 기록
- `/output/economy/` 전체 소실 → 문서(AGENTS/audit/review)의 검증된 규칙 기준으로 처음부터 재작성, git 첫 커밋 `8b78bba`.
- 회귀 앵커 4건(91 테스트 통과): `calculate_interest_trajectory(15,1)`→이자 1 / `reroll_count(20)`→10 / `unit_hit_probability("진",5,9,0,0,1)`→8.0601% / `tier_taken=80`→ValueError.
- 재건 시 반영: F-1(docstring 5골드 예시 제거+테스트), F-2(주석), F-3(formula 무시·테이블 단일 진원), F-4(35골드 앵커), F-R1(교차검증), F-R2(bool 검증). `reroll_discount` 계열 필드가 JSON에 재발하면 `reroll.load_reroll_rules()`가 ValueError.
- 컨테이너가 다시 죽으면: 이 git 레포 checkout + .gitignore 주석대로 2개 벤더 미러 재클론 + `sudo ln -sfn <repo>/output /output`.

## 검증된 경제 규칙 (2026-08-24 교차검증 완료)
- **이자**: `floor(보유 골드 / 10)`, 최대 5골드, 50골드 이상 시 상한. 매 턴 종료 시 지급.
- **리롤**: 항상 **고정 2골드**. "비용별 드랍률 유지율" 메커니즘은 존재하지 않음(2026-08-24 제거됨). 가능 횟수 = `floor(골드/2)`.
- **XP**: 매 라운드 2. 레벨업: Lv2=2, 3=6, 4=10, 5=20, 6=36, 7=60, 8/9/10=68(사용자 제공, 제3자 재확인 권장).
- 최대 레벨 10(레벨 11 드랍률 행은 Set 14 잔재 — `exists_in_game:false`, 로드 시 제외).
- 상점 드랍률·라운드 구조는 Data Dragon 공식 데이터(검증 불필요).

## 주의
- Data Dragon CDN 직접 접근은 403 → 로컬 `TFT_DDragon/` 사용.
- `tft_viewer.py`는 `--no-browser` 없이 실행하면 serve_forever로 블로킹.
