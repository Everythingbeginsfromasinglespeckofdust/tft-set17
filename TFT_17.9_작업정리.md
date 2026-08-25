# TFT 17.9 (Set 17) 한국어 데이터 정리 — 작업 요약

최종 업데이트: 2026-08-24 · 대상: **패치 17.9 / Set 17** · 언어: 한국어(ko_KR)

---

## 1. 목표

Teamfight Tactics(TFT) Set 17(패치 17.9)의 데이터를 한국어로 "한눈에" 보여주는 스크립트를 만들고,
이어 아이템·증강체·리롤확률·라운드·경험치/골드·피해 공식까지 종합 가이드로 확장한다.

라이엇 공식 Data Dragon에는 **챔피언→시너지 매핑**, **아이템 레시피**, **경험치/골드 상수** 등이
포함되어 있지 않아, 이를 다른 소스에서 매핑하는 것이 본 작업의 핵심이었다.

---

## 2. 데이터 소스

| 소스 | 위치 | 제공 내용 |
|---|---|---|
| **noxelisdev/TFT_DDragon** (공식 Data Dragon 미러, tag `v17.9`) | `TFT_DDragon/data/ko_KR/*.json` | 한국어 챔피언/시너지/증강체/아이템 **이름·설명·코스트·티어**, 상점 드랍률, 스테이지/라운드 스케줄 |
| **Jack0Chan/TFT_Spider** | `TFT_Spider/` | 보조 스크래핑 레포. 캐시된 데이터는 Set 15 중국어라 17.9에는 미사용 |
| **중국판 TFT CDN** (`game.gtimg.cn`, season `2026.S17`) | 캐시: `.tft_cache/` | 챔피언→시너지 매핑(`chess.js`), 아이템 레시피·효과(`equip.js`), 증강체 티어(`hex.js`) |

- CDN 캐시 파일: `s17_chess.json`(156KB), `s17_equip.json`(386KB), `s17_hex.json`(129KB)
- CDN은 첫 실행 시 1회 받아 `.tft_cache/`에 캐시 → 이후 **오프라인 동작** 가능
- join 키: 로컬 Riot ID ↔ CDN `hero_EN_name`(챔피언), `augments`(증강체), `englishName`(아이템)

---

## 3. 산출물 (파일)

| 파일 | 용도 |
|---|---|
| `tft_view.py` | Set 17 한국어 **챔피언(63명)·시너지(35개)** 표 출력. `--md`/`--json`/`--refresh` 옵션 |
| `tft_set17.md` / `tft_set17.json` | 상점: 챔피언·시너지 표 (md/json) |
| `tft_mapping_17.json` | 챔피언→시너지 매핑 캐시 (CDN join 결과) |
| `tft_guide.py` | **종합 가이드** 생성기 (아래 6섹션). md + **섹션별 JSON** 동시 출력. `--refresh` 옵션 |
| `tft_set17_guide.md` | 종합 가이드 결과물 (아이템/증강체/리롤/라운드/경험치·골드/피해공식) |
| `tft_viewer.py` | **시각화 웹 뷰어** 생성기. 로컬 이미지 포함 인터랙티브 HTML + 로컬 HTTP 서버. `--port`/`--no-browser` |
| `tft_set17_viewer.html` | 뷰어 결과물 (8탭: 챔피언·시너지·증강체·아이템·리롤·라운드·경험치/골드·피해공식) |
| `tft_guide/*.json` | **섹션별 JSON** (아래 표) |
| `.tft_cache/` | CDN 3파일 캐시 |
| `TFT_DDragon/`, `TFT_Spider/` | 클론한 원본 레포 (DDragon HEAD: `22fb2571`, tag v17.9) |
| `TFT_17.9_작업정리.md` | 본 문서 |

### 섹션별 JSON (`tft_guide/`)

| 파일 | 주요 내용 (JSON 키) | 규모 |
|---|---|---|
| `01_items.json` | `basic_components`(10), `standard_items`(39, 레시피 배열), `set17_special_items`(7개 카테고리: 상징 20·유물 10·동물특공대 무기 27·그레이브즈 업그레이드 54·소나 모드 9·미스포츈 모드 3·사용품 5) | 8KB |
| `02_augments.json` | `augments`(272개: id·이름·티어·설명·`is_set17_new`), `tier_counts`(실버67/골드138/프리즘67), `set17_new_count`(32) | 102KB |
| `03_drop_rates.json` | `shop_drop_rates`(레벨 1~11, 코스트별 %, 레벨 11 `exists_in_game:false` 플래그) | 2KB |
| `04_rounds.json` | `rounds`(130개: stage·round·raw_id·한국어 label) | 14KB |
| `05_xp_gold.json` | `level_up_xp`(9단계), `max_level:10`, `gold`(이자 표·10골드당 1·최대 50), `reroll_cost:2`(2026-08-24 정정: 기존 구간별 유지율 필드는 실제 게임에 없는 메커니즘으로 확인 → 고정 2골드로 교체), `level11_note` | 2KB |
| `06_damage.json` | `base_stats`, `damage_formulas`(물리/마법/진실), `armor_mr_caps`, `other`(크리/흡혈) | 1KB |

각 JSON은 공통 메타데이터(`section`, `set`, `patch`) + `sources`/`caveat`(출처 및 주의사항) 포함.

### 종합 가이드 (`tft_set17_guide.md`) 섹션 구성
1. **아이템** — 기본 부품 10종, 표준 아이템 39종(레시피), Set 17 특수 아이템 7개 카테고리
2. **증강체** — 시즌 카루셀 풀 전체 272종 (Set 17 신규 32종 🆕 표시 포함), 실버 67 / 골드 138 / 프리즘 67
3. **리롤확률** — 레벨별(1~11, 11은 Set 14 잔재 표시) 코스트 드랍률 표
4. **라운드 정보** — 스테이지 1~19 전체 스케줄 (130 라운드)
5. **경험치/골드** — 레벨업 XP (2/6/10/20/36/60/68/68/68), 이자, 리롤 할인
6. **피해량 공식** — 물리/마법/진실 피해, 방어력 상한, 크리

---

## 4. 핵심 발견 & 해결

### 4-1. 챔피언→시너지 매핑 (Data Dragon에 없음)
- 중국 CDN `chess.js`의 챔피언 레코드에 Riot 스타일 ID(`TFT17_MissFortune` 등)가
  `hero_EN_name`으로, 시너지가 `characterid`(예: `TFT17_ADMIN`)로 존재
- 68개 CDN 엔트리 중 65개가 로컬 챔피언 매칭, 미매칭 3개는 플레이 불가 유닛
- 35개 시너지 ID 전부 로컬 `trait.json` 매칭 확인

### 4-2. 플레이 불가/특수 유닛 필터링
- 로컬 champion.json의 Set 17 66개 중 3개가 실제 상점 챔피언 아님 → **63명**으로 확정
  - `TFT17_DarkStar_FakeUnit`(소형 블랙홀), `TFT17_Enemy_Aatrox`(태고족 우두머리), `TFT17_MissFortune_TraitClone`
- `tft_view.py`에 `SPECIAL` 마커(`_TraitClone`, `_FakeUnit`, `_Enemy_`, `_PVE_`, `_Summon` 등)로 필터
- CDN의 PVE 몬스터·소환수·타임브레이커 코어 10개도 필터 대상에 포함

### 4-3. 선택형 시너지 중복 ("별돌보미" 8개)
- 별돌보미(Stargazer)는 산/뱀/늑대/쉴드 등 하위 변형 ID 8종(`TFT17_Stargazer_Huntress` 등) 존재
- 시너지 요약이 ID 단위 중복 → **베이스 ID(`TFT17_Stargazer`)로 묶어** 카운팅
- 챔피언 0개 참조의 플레이스홀더 시너지(`TFT17_MissFortuneUndeterminedTrait` = "특성 선택")는 제외

### 4-4. 아이템 레시피 (Data Dragon에 없음)
- CDN `equip.js`의 `formula` 필드가 레시피(부품 ID 조합) → 로컬 한국어 이름과 join
  - 예: `대천사의 지팡이 = 쓸데없이 큰 지팡이 + 여신의 눈물` (39종 전부 해결)
- **기본 부품 10종**: B.F. 대검, 거인의 허리띠, 곡궁, 뒤집개, 쇠사슬 조끼, 쓸데없이 큰 지팡이,
  여신의 눈물, 연습용 장갑, 음전자 망토, 프라이팬
  - 하드코딩 대신 "레시피에 쓰이지만 완성품이 아닌 아이템"으로 **동적 계산**
  - (Set 17에는 '부츠' 부품이 없음 — 과거 세트 유산 주의)

### 4-5. 증강체 티어 = 실버/골드/프리즘, 카루셀 풀 272종
- **티어 매핑 성공** (두 소스 1:1 교차 검증 일치)
  - CDN `hex.js`의 `type`: 1/2/3
  - 로컬 `augments.json`의 **이미지 파일명** 로마숫자: `Bonk_I`, `GodAugmentAhri_II`, `HeartoftheSwarm_III`
  - 매핑: **I(1)=실버, II(2)=골드, III(3)=프리즘** — Set 17은 3티어 체계
- **풀 전체**: 로컬 `TFT17_Augment*`는 31종으로 보이나, 이는 **Set 17 신규만**임.
  게임의 증강 카루셀은 이전 세트 이월 + 공용 증강까지 포함해 **272종** (hex.js 시즌 2026.S17 전체)
  - 집계: 실버 67 · 골드 138 · 프리즘 67
  - Set 17 신규 32종 (로컬 31 + `TFT17_Augment_InvaderZed`("天煞灭影：劫"), 17.9 DDragon에 아직 없음)
  - 로컬 DDragon에 없는 2종(InvaderZed, `TFT_Augment_BoosterPackPlusPlus`)은 중국어 표기로 표시
- 티어 지정 증강 아이템(`TFT17_MarketOffering_SilverAugment` = "실버 증강" 등)도 item.json에 실존

### 4-6. 레벨 11은 "Set 14 잔재"
- `shop-drop-rates-data.json`에 레벨 11 드랍률 행 존재 (1c:1 / 2c:2 / 3c:12 / 4c:50 / 5c:35)
- git 추적 결과: 이 파일은 **v14.23(Set 14)에서 처음 추가**, Set 14는 실제 최대 레벨 11 + 6코스트 존재
- v14.24~v17.9까지 레벨 11 행 값 **한 번도 변경되지 않음** → Set 15~17은 최대 레벨 10임에도
  데이터에만 남아있는 **미정리 잔재**
- 가이드에 주석으로 명시

### 4-7. 경험치/골드·피해 공식 (데이터 미포함)
- Data Dragon·CDN 어디에도 레벨업 XP/골드/피해 공식 **상수가 없음**
- 클라이언트 고정 상수(사용자 제공값 반영):
  - 레벨업 XP (매 라운드 2XP): Lv2=2, Lv3=6, Lv4=10, Lv5=20, Lv6=36, Lv7=60, Lv8=68, Lv9=68, Lv10=68
  - 최대 레벨 **10**, 골드 이자 floor(골드/5)·최대 5, 리롤 할인 100/75/50/25/0%
  - 물리피해 = AD×100/(100+방어), 마법피해 = AP×100/(100+저항), 진실피해 = AD
- 가이드 5·6번 섹션 상단에 ⚠️ "데이터에 없는 클라이언트 상수" 출처 주석 명시

### 4-8. 라운드 스케줄
- `stage-round-data.json`: 스테이지 1~19, 각 4~7 라운드
- Set 17 이벤트: 증강 카루셀(1-1), 마켓(2-4/3-4/4-4/12-7…), 크러그(2-7), 늑대(3-7),
  신의 축복(4-7), 아이템 단조(5-4~11-4), 드래곤 보스(5-7~11-7, 12-4~19-4)

---

## 5. 데이터 주의사항

1. **패치/버전 불일치**: DDragon tag는 `v17.9`인데 일부 JSON의 `version` 필드는 `16.16.1` (라이엇 버닝 방식)
2. **CDN 의존성**: 매핑·레시피·티어는 중국 CDN 기반 → 패치 변경 시 `--refresh`로 재다운로드 필요
   (Set 17은 2026-08-12 이후 패치에서 Unreal로 이전 예정 → 이후 소스 구조가 바뀔 수 있음)
3. **경험치/골드·피해 공식**: 클라이언트 상수 표준값. 터보/더블업 등 모드별 차이는 반영 안 됨
4. **레벨 11 드랍률**: Set 14 잔재 — 실제 게임 없음
5. **TFT_Spider**: Set 15 중국어 캐시라 본 작업에서 미사용 (향후 중국어 데이터 필요 시 활용 가능)

---

## 6. 실행 방법

```bash
# 챔피언·시너지 표
python3 tft_view.py            # 터미널 표
python3 tft_view.py --md --json  # + tft_set17.md / tft_set17.json 생성

# 종합 가이드 (md + 섹션별 JSON 6종)
python3 tft_guide.py           # tft_set17_guide.md + tft_guide/01~06_*.json 생성
python3 tft_guide.py --refresh # CDN 캐시 무시하고 재다운로드

# 시각화 웹 뷰어 (이미지 포함, 로컬 서버 + 브라우저 자동 열림)
python3 tft_viewer.py          # http://127.0.0.1:18080/tft_set17_viewer.html
python3 tft_viewer.py --port 9000 --no-browser
```

의존성: Python 표준 라이브러리만 사용 (`json`, `os`, `re`, `argparse`, `urllib.request`, `collections`).
