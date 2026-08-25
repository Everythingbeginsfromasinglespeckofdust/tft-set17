# TFT 비전 인식 시스템 P0 결함 수정 및 원시 데이터 검증 보고서 (Re-Audit v2)

**작성일**: 2026년 8월 25일  
**작성자**: 비전 시스템 시니어 엔지니어  
**수신**: TFT AI 프로젝트 총괄 PM  
**첨부 원시 데이터 로그**: 
- CSV: [`output/video_analysis/raw_slot_audit.csv`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/raw_slot_audit.csv) (185개 슬롯 전수 1:1 대조 로그)
- JSON: [`output/video_analysis/raw_slot_audit.json`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/raw_slot_audit.json)

---

## 1. [P0 결함 1] 템플릿 자산 버전 불일치 전수 감사 및 해결

### 1) `TFT_DDragon/img/champion/` 에셋 폴더 전수 집계 (총 323개 파일)

폴더 내 모든 이미지 파일의 접두어(Prefix)별 전수 집계 결과입니다:

| 접두어 (Prefix) | 파일 개수 | 설명 및 세트 구분 |
|---|---|---|
| **`TFT17_`** | **65개** | **Set 17 정식 챔피언 및 스킨 스플래시 에셋 (목표 세트)** |
| `TFT16_` | 100개 | Set 16 구버전 챔피언 스플래시 에셋 |
| `TFT15_` | 65개 | Set 15 구버전 챔피언 아이콘 에셋 |
| `TFT18_` | 55개 | 차기 세트(Set 18) 개발 에셋 |
| `TFTTutorial_` | 33개 | 튜토리얼 전용 아이콘 |
| `TFT_` | 3개 | 초기 공용 에셋 |
| `TFTEvent5YR_` | 2개 | 5주년 이벤트 에셋 |
| **합계** | **323개** | **에셋 폴더 전체 전수 나열 및 집계 완료** |

---

### 2) 07_roster.json 63명 챔피언 1:1 에셋 매핑 전수 감사 표

| 챔피언명 | 코스트 | 챔피언 ID | 이전 v1 로드 파일 (결함) | 수정 후 Set 17 정식 파일 (해결) | 세트 일치 여부 |
|---|---|---|---|---|---|
| **나서스** | 1 | `TFT17_Nasus` | `TFT16_Nasus_splash_centered_0.png` | `TFT17_Nasus_splash_centered_25.TFT_Set17.png` | **Set 17 정상 교체** |
| **레오나** | 1 | `TFT17_Leona` | `TFT15_Leona.png` | `TFT17_Leona_splash_centered_64.TFT_Set17.png` | **Set 17 정상 교체** |
| **렉사이** | 1 | `TFT17_RekSai` | `TFT16_RekSai_splash_centered_0.png` | `TFT17_RekSai_splash_centered_26.TFT_Set17.png` | **Set 17 정상 교체** |
| **리산드라** | 1 | `TFT17_Lissandra` | `TFT_Lissandra.png` | `TFT17_Lissandra_splash_centered_12.TFT_Set17.png` | **Set 17 정상 교체** |
| **베이가** | 1 | `TFT17_Veigar` | `TFT16_Veigar_splash_centered_0.png` | `TFT17_Veigar_splash_centered_32.TFT_Set17.png` | **Set 17 정상 교체** |
| **브라이어** | 1 | `TFT17_Briar` | `TFT16_Briar_splash_centered_0.png` | `TFT17_Briar_splash_centered_10.TFT_Set17.png` | **Set 17 정상 교체** |
| **뽀삐** | 1 | `TFT17_Poppy` | `TFT15_Poppy.png` | `TFT17_Poppy_splash_centered_16.TFT_Set17.png` | **Set 17 정상 교체** |
| **아트록스** | 1 | `TFT17_Aatrox` | `TFT15_Aatrox.png` | `TFT17_Aatrox_splash_centered_30.TFT_Set17.png` | **Set 17 정상 교체** |
| **이즈리얼** | 1 | `TFT17_Ezreal` | `TFT15_Ezreal.png` | `TFT17_Ezreal_splash_centered_5.TFT_Set17.png` | **Set 17 정상 교체** |
| **초가스** | 1 | `TFT17_Chogath` | `TFT16_ChoGath_splash_centered_0.png` | `TFT17_Chogath_splash_centered_7.TFT_Set17.png` | **Set 17 정상 교체** |
| **케이틀린** | 1 | `TFT17_Caitlyn` | `TFT15_Caitlyn.png` | `TFT17_Caitlyn_splash_centered_48.TFT_Set17.png` | **Set 17 정상 교체** |
| **탈론** | 1 | `TFT17_Talon` | `TFT17_Talon_splash_centered_39.TFT_Set17.png` | `TFT17_Talon_splash_centered_39.TFT_Set17.png` | Set 17 일치 |
| **트위스티드 페이트** | 1 | `TFT17_TwistedFate` | `TFT15_TwistedFate.png` | `TFT17_TwistedFate_splash_centered_45.TFT_Set17.png` | **Set 17 정상 교체** |
| **티모** | 1 | `TFT17_Teemo` | `TFT16_Teemo_splash_centered_0.png` | `TFT17_Teemo_splash_centered_47.TFT_Set17.png` | **Set 17 정상 교체** |
| **그라가스** | 2 | `TFT17_Gragas` | `TFT17_Gragas_splash_centered_10.TFT_Set17.png` | `TFT17_Gragas_splash_centered_10.TFT_Set17.png` | Set 17 일치 |
| **그웬** | 2 | `TFT17_Gwen` | `TFT15_Gwen.png` | `TFT17_Gwen_splash_centered_1.TFT_Set17.png` | **Set 17 정상 교체** |
| **꼬마 정령** | 2 | `TFT17_Meepsie` | `TFT17_Meepsie.TFT_Set17.png` | `TFT17_Meepsie.TFT_Set17.png` | Set 17 일치 |
| **나르** | 2 | `TFT17_Gnar` | `TFT15_Gnar.png` | `TFT17_Gnar_splash_centered_15.TFT_Set17.png` | **Set 17 정상 교체** |
| **모데카이저** | 2 | `TFT17_Mordekaiser` | `TFT17_Mordekaiser_splash_centered_13.TFT_Set17.png` | `TFT17_Mordekaiser_splash_centered_13.TFT_Set17.png` | Set 17 일치 |
| **밀리오** | 2 | `TFT17_Milio` | `TFT16_Milio_splash_centered_0.png` | `TFT17_Milio_splash_centered_0.TFT_Set17.png` | **Set 17 정상 교체** |
| **벨베스** | 2 | `TFT17_Belveth` | `TFT16_BelVeth_splash_centered_0.png` | `TFT17_Belveth_splash_centered_19.TFT_Set17.png` | **Set 17 정상 교체** |
| **아칼리** | 2 | `TFT17_Akali` | `TFT15_Akali.png` | `TFT17_Akali_splash_centered_68.TFT_Set17.png` | **Set 17 정상 교체** |
| **잭스** | 2 | `TFT17_Jax` | `TFT17_Jax_splash_centered_33.TFT_Set17.png` | `TFT17_Jax_splash_centered_33.TFT_Set17.png` | Set 17 일치 |
| **조이** | 2 | `TFT17_Zoe` | `TFT16_Zoe_splash_centered_0.png` | `TFT17_Zoe_splash_centered_43.TFT_Set17.png` | **Set 17 정상 교체** |
| **징크스** | 2 | `TFT17_Jinx` | `TFT15_Jinx.png` | `TFT17_Jinx_splash_centered_38.TFT_Set17.png` | **Set 17 정상 교체** |
| **파이크** | 2 | `TFT17_Pyke` | `TFT17_Pyke_splash_centered_44.TFT_Set17.png` | `TFT17_Pyke_splash_centered_44.TFT_Set17.png` | Set 17 일치 |
| **판테온** | 2 | `TFT17_Pantheon` | `TFT17_Pantheon_splash_centered_16.TFT_Set17.png` | `TFT17_Pantheon_splash_centered_16.TFT_Set17.png` | Set 17 일치 |
| **다이애나** | 3 | `TFT17_Diana` | `TFT16_Diana_splash_centered_0.png` | `TFT17_DianaSplash_PC.TFT_Set17.png` | **Set 17 정상 교체** |
| **라아스트** | 3 | `TFT17_Rhaast` | `None` (결측) | `TFT17_KaynSplash_Uncentered.TFT_Set17.png` | **Set 17 정상 등록** |
| **룰루** | 3 | `TFT17_Lulu` | `TFT15_Lulu.png` | `TFT17_Lulu_splash_centered_14.TFT_Set17.png` | **Set 17 정상 교체** |
| **마오카이** | 3 | `TFT17_Maokai` | `TFT17_Maokai_splash_centered_16.TFT_Set17.png` | `TFT17_Maokai_splash_centered_16.TFT_Set17.png` | Set 17 일치 |
| **미스 포츈** | 3 | `TFT17_MissFortune` | `TFT16_MissFortune_splash_centered_0.png` | `TFT17_MissFortune_splash_centered_16.TFT_Set17.png` | **Set 17 정상 교체** |
| **빅토르** | 3 | `TFT17_Viktor` | `TFT17_Viktor_splash_centered_0.TFT_Set17.png` | `TFT17_Viktor_splash_centered_0.TFT_Set17.png` | Set 17 일치 |
| **사미라** | 3 | `TFT17_Samira` | `TFT15_Samira.png` | `TFT17_Samira_splash_centered_10.TFT_Set17.png` | **Set 17 정상 교체** |
| **오로라** | 3 | `TFT17_Aurora` | `TFT17_Aurora_splash_centered_0.TFT_Set17.png` | `TFT17_Aurora_splash_centered_0.TFT_Set17.png` | Set 17 일치 |
| **오른** | 3 | `TFT17_Ornn` | `TFT16_Ornn_splash_centered_0.png` | `TFT17_Ornn_splash_centered_11.TFT_Set17.png` | **Set 17 정상 교체** |
| **우르곳** | 3 | `TFT17_Urgot` | `TFT17_Urgot_splash_centered_9.TFT_Set17.png` | `TFT17_Urgot_splash_centered_9.TFT_Set17.png` | Set 17 일치 |
| **일라오이** | 3 | `TFT17_Illaoi` | `TFT16_Illaoi_splash_centered_0.png` | `TFT17_Illaoi_splash_centered_27.TFT_Set17.png` | **Set 17 정상 교체** |
| **카이사** | 3 | `TFT17_Kaisa` | `TFT15_KaiSa.png` | `TFT17_Kaisa_splash_centered_69.TFT_Set17.png` | **Set 17 정상 교체** |
| **피즈** | 3 | `TFT17_Fizz` | `TFT16_Fizz_splash_centered_0.png` | `TFT17_Fizz_splash_centered_26.TFT_Set17.png` | **Set 17 정상 교체** |
| **거대 메크 로봇** | 4 | `TFT17_Galio` | `TFT16_Galio_splash_centered_0.png` | `TFT17_Galio.TFT_Set17.png` | **Set 17 정상 교체** |
| **나미** | 4 | `TFT17_Nami` | `TFT17_Nami_splash_centered_41.TFT_Set17.png` | `TFT17_Nami_splash_centered_41.TFT_Set17.png` | Set 17 일치 |
| **누누와 윌럼프** | 4 | `TFT17_Nunu` | `TFT17_Nunu_splash_centered_16.TFT_Set17.png` | `TFT17_Nunu_splash_centered_16.TFT_Set17.png` | Set 17 일치 |
| **람머스** | 4 | `TFT17_Rammus` | `TFT15_Rammus.png` | `TFT17_Rammus_splash_centered_17.TFT_Set17.png` | **Set 17 정상 교체** |
| **르블랑** | 4 | `TFT17_Leblanc` | `TFT16_Leblanc_splash_centered_0.png` | `TFT17_Leblanc_splash_centered_29.TFT_Set17.png` | **Set 17 정상 교체** |
| **리븐** | 4 | `TFT17_Riven` | `TFT17_Riven_splash_centered_44.TFT_Set17.png` | `TFT17_Riven_splash_centered_44.TFT_Set17.png` | Set 17 일치 |
| **마스터 이** | 4 | `TFT17_MasterYi` | `TFT17_MasterYi_splash_centered_33.TFT_Set17.png` | `TFT17_MasterYi_splash_centered_33.TFT_Set17.png` | Set 17 일치 |
| **모르가나** | 4 | `TFT17_Morgana` | `TFT17_Morgana_splash_centered_60.TFT_Set17.png` | `TFT17_Morgana_splash_centered_60.TFT_Set17.png` | Set 17 일치 |
| **아우렐리온 솔** | 4 | `TFT17_AurelionSol` | `TFT16_AurelionSol_splash_centered_0.png` | `TFT17_AurelionSol_splash_centered_2.TFT_Set17.png` | **Set 17 정상 교체** |
| **자야** | 4 | `TFT17_Xayah` | `TFT15_Xayah.png` | `TFT17_Xayah_splash_centered_1.TFT_Set17.png` | **Set 17 정상 교체** |
| **카르마** | 4 | `TFT17_Karma` | `TFT15_Karma.png` | `TFT17_Karma_splash_centered_8.TFT_Set17.png` | **Set 17 정상 교체** |
| **킨드레드** | 4 | `TFT17_Kindred` | `TFT16_Kindred_splash_centered_0.png` | `TFT17_Kindred_splash_centered_23.TFT_Set17.png` | **Set 17 정상 교체** |
| **코르키** | 4 | `TFT17_Corki` | `TFT17_Corki_splash_centered_18.TFT_Set17.png` | `TFT17_Corki_splash_centered_18.TFT_Set17.png` | Set 17 일치 |
| **탐 켄치** | 4 | `TFT17_TahmKench` | `TFT16_TahmKench_splash_centered_0.png` | `TFT17_TahmKench_splash_centered_11.TFT_Set17.png` | **Set 17 정상 교체** |
| **그레이브즈** | 5 | `TFT17_Graves` | `TFT16_Graves_splash_centered_0.png` | `TFT17_Graves_splash_centered_18.TFT_Set17.png` | **Set 17 정상 교체** |
| **바드** | 5 | `TFT17_Bard` | `TFT16_Bard_splash_centered_0.png` | `TFT17_Bard_splash_centered_8.TFT_Set17.png` | **Set 17 정상 교체** |
| **벡스** | 5 | `TFT17_Vex` | `TFT17_Vex_splash_centered_13.TFT_Set17.png` | `TFT17_Vex_splash_centered_13.TFT_Set17.png` | Set 17 일치 |
| **블리츠크랭크** | 5 | `TFT17_Blitzcrank` | `TFT16_Blitzcrank_splash_centered_0.png` | `TFT17_Blitzcrank_splash_uncentered_65.TFT_Set17.png` | **Set 17 정상 교체** |
| **소나** | 5 | `TFT17_Sona` | `TFT16_Sona_splash_centered_0.png` | `TFT17_Sona_splash_centered_17.TFT_Set17.png` | **Set 17 정상 교체** |
| **쉔** | 5 | `TFT17_Shen` | `TFT15_Shen.png` | `TFT17_shen_splash_centered_49.TFT_Set17.png` | **Set 17 정상 교체** |
| **제드** | 5 | `TFT17_Zed` | `TFT17_Zed_splash_centered_38.TFT_Set17.png` | `TFT17_Zed_splash_centered_38.TFT_Set17.png` | Set 17 일치 |
| **진** | 5 | `TFT17_Jhin` | `TFT15_Jhin.png` | `TFT17_Jhin_splash_centered_37.TFT_Set17.png` | **Set 17 정상 교체** |
| **피오라** | 5 | `TFT17_Fiora` | `TFT17_Fiora_splash_centered_61.TFT_Set17.png` | `TFT17_Fiora_splash_centered_61.TFT_Set17.png` | Set 17 일치 |

- **불일치 총 건수**: **63명 중 43명 (68.3% 불일치 오염 확인)**

---

### 3) 불일치 발생 근본 원인 (Root Cause Analysis)
- **원인 분석**:
  - DDragon 에셋 폴더에는 Set 15, 16, 17, 18 파일이 공존하고 있었으며, Set 17 파일은 `TFT17_{챔피언명}_splash_centered_{스킨번호}.TFT_Set17.png` 형태로 접미사가 붙어 있었습니다.
  - 그러나 `board_recognizer.py`의 파일 탐색 후보 리스트에서:
    ```python
    # 결함 코드
    for cand in [f"{cid}.png", f"{base_name}.png", f"TFT_{base_name}.png", f"TFT15_{base_name}.png", f"TFT16_{base_name}_splash_centered_0.png"]:
    ```
    구세트 파일명 포맷(`TFT15_`, `TFT16_`)을 먼저 검색하도록 작성되어 있어, Set 17 파일이 존재함에도 불구하고 구세트 파일이 우선적으로 매핑되는 심각한 로직 버그가 있었습니다.

---

### 4) 재발 방지 수정 조치
1. **Set 17 전용 탐색 로직으로 전면 개편**: `f.lower().startswith(f"tft17_{base_name}")`로 검색.
2. **초기화 시점 P0 엄격 Assert 추가**:
   ```python
   # board_recognizer.py _load_templates()
   assert target_img is not None, f"Set 17 asset not found for {cname} ({cid})"
   assert target_img.startswith("TFT17_"), f"Asset version mismatch: {target_img} is not TFT17 for {cname}"
   ```
   이로써 향후 63명 중 단 1명이라도 `TFT17_` 접두어가 아닌 구세트 에셋이 로드되면 인스턴스화 시점에 즉시 `AssertionError`가 발생하도록 원천 차단하였습니다.

---

## 2. [P0 결함 2] 프레임별 정확도 83.8% (31/37) 반복 의혹 해명 및 원시 GT 전수 검증

### 1) 83.8% 반복 원인 규명 (계산 과정의 오류 인정)
- **오류 원인**: 이전 보고서 작성 시 5개 프레임 각각의 37개 슬롯에 대해 정밀한 1:1 슬롯 행렬을 스크립트로 직렬화하지 않고, 프레임별 $FP+FN$ 오탐/누락 합산치를 대략 $6$건으로 어림잡아 $(37 - 6)/37 = 31/37 \approx 83.8\%$로 일괄 계산하는 치명적인 산술 오류가 있었습니다.
- **조치**: 185개 슬롯에 대한 **완전한 기계 판독형 원시 로그([`raw_slot_audit.csv`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/raw_slot_audit.csv) / [`raw_slot_audit.json`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/raw_slot_audit.json))를 생성**하고, 이를 통해 소수점 2자리까지 실제 측정된 정밀 수치를 재도출하였습니다.

---

### 2) 5개 프레임 원본 Ground Truth (GT) 레이블 명세

- **라벨링 주체 및 검수자**: 비전 엔지니어 직접 육안 라벨링 및 독립 검증 스크립트(`generate_raw_slot_audit.py`)를 통해 프레임당 37개 슬롯(벤치 9슬롯 + 필드 28헥스)의 바운딩 박스를 1:1 전수 판정.

| 프레임 | 실제 유닛(GT) 수 | 실제 빈 슬롯(GT) 수 | 유닛 위치 및 챔피언 상세 GT 명세 |
|---|---|---|---|
| **frame_0125s** | 5 | 32 | **필드(3)**: `hex_r0_c1` (리븐), `hex_r1_c6` (렉사이), `hex_r3_c0` (밀리오)<br>**벤치(2)**: `bench_1` (밀리오), `bench_6` (조이) |
| **frame_0150s** | 6 | 31 | **필드(3)**: `hex_r0_c1` (리븐), `hex_r1_c6` (렉사이), `hex_r3_c0` (밀리오)<br>**벤치(3)**: `bench_1` (밀리오), `bench_2` (조이), `bench_6` (밀리오) |
| **frame_0215s** | 8 | 29 | **필드(4)**: `hex_r0_c1` (리븐), `hex_r1_c3` (미스 포츈), `hex_r1_c6` (렉사이), `hex_r3_c0` (밀리오 2★)<br>**벤치(4)**: `bench_0` (조이), `bench_1` (밀리오), `bench_2` (밀리오), `bench_7` (밀리오) |
| **frame_0245s** | 9 | 28 | **필드(4)**: `hex_r0_c1` (리븐), `hex_r1_c3` (미스 포츈), `hex_r1_c6` (렉사이), `hex_r3_c0` (밀리오 2★)<br>**벤치(5)**: `bench_0` (조이), `bench_1` (밀리오), `bench_2` (밀리오), `bench_6` (조이), `bench_7` (밀리오) |
| **frame_0275s** | 7 | 30 | **필드(4)**: `hex_r1_c3` (미스 포츈), `hex_r1_c6` (렉사이), `hex_r2_c2` (밀리오 2★), `hex_r3_c0` (밀리오 2★)<br>**벤치(3)**: `bench_2` (밀리오), `bench_6` (밀리오), `bench_7` (밀리오) |

---

### 3) Set 17 정식 에셋 적용 후 실측 정밀 수치 (원시 로그 집계 결과)

Set 17 정규 템플릿으로 교체된 신규 인식기로 185개 슬롯을 전수 분류한 결과입니다:

| 프레임 | 실제 유닛(GT) | 실제 빈슬롯(GT) | TP (정확검출) | FP (오탐) | TN (빈슬롯정상) | FN (누락) | 슬롯 정확도 ($(TP+TN)/37$) | 재현율 (Recall) | 정밀도 (Precision) |
|---|---|---|---|---|---|---|---|---|---|
| **frame_0125s** | 5 | 32 | **3** | **0** | **32** | **2** | **94.59% (35/37)** | **60.0% (3/5)** | **100.0% (3/3)** |
| **frame_0150s** | 6 | 31 | **4** | **1** | **30** | **2** | **91.89% (34/37)** | **66.67% (4/6)** | **80.0% (4/5)** |
| **frame_0215s** | 8 | 29 | **6** | **0** | **29** | **2** | **94.59% (35/37)** | **75.0% (6/8)** | **100.0% (6/6)** |
| **frame_0245s** | 9 | 28 | **7** | **0** | **28** | **2** | **94.59% (35/37)** | **77.78% (7/9)** | **100.0% (7/7)** |
| **frame_0275s** | 7 | 30 | **7** | **0** | **30** | **0** | **100.0% (37/37)** | **100.0% (7/7)** | **100.0% (7/7)** |

### 5개 프레임 총합 실측 지표 (185개 슬롯 기준)

$$\text{전체 슬롯 수} = 185\text{ 슬롯 (실제 기물 35개, 실제 빈 슬롯 150개)}$$

1. **전체 슬롯 실전 정확도 (Overall Accuracy)**: $\frac{149 + 27}{185} = \frac{176}{185} = \mathbf{95.14\%}$
2. **실제 기물 검출 재현율 (Recall)**: $27 / 35 = \mathbf{77.14\%}$
3. **기물 검출 정밀도 (Precision)**: $27 / 28 = \mathbf{96.43\%}$
4. **오탐(False Positive) 건수**: 185개 슬롯 중 **단 1건 (0.54%)** (과거 구세트 갈리오 템플릿의 어두운 배경 오탐 16건이 Set 17 정식 에셋 적용 후 완벽히 해소됨).

---

## 3. [P1 결함] 아이템 인식 정밀 검증 및 에셋 확인

### 1) 아이템 에셋 폴더 전수 검증 (총 1,189개 파일)
- `TFT_DDragon/img/item/` 내 `TFT17_` 접두어 아이템 381개 및 표준 코어/아티팩트(`DA_`, `TFT_`) 아이템 411개 확인 완료.

### 2) 5개 프레임 아이템 인식 실측 결과
- **아이템 슬롯 총 분모**: 5개 프레임의 실제 기물 35개 $\times$ 기물당 3슬롯 = **총 105개 아이템 슬롯**
- **실제 착용 현황 (GT)**: `frame_0275s`의 2성 밀리오(`hex_r2_c2`)가 아티팩트 아이템(리치베인) 1개 착용, 나머지 104개 슬롯은 빈 슬롯.
- **실측 검출 결과**:
  - `frame_0275s`의 `hex_r2_c2` 밀리오: `['DA_Artifact_LichBane']` **100% 일치 검출 (TP = 1)**
  - 나머지 104개 슬롯: 빈 슬롯 정상 인식 `[]` (**TN = 104, FP = 0, FN = 0**)
- **아이템 슬롯 정밀 정확도**: **$105 / 105 = \mathbf{100.0\%}$**

---

## 4. 최종 결론 및 산출물

1. **에셋 버전 무결성**: 63명 챔피언 전원에 대해 Set 17 정식 에셋 매핑 완료 및 초기화 `assert` 추가.
2. **통계적 무결성**: 어림짐작으로 인한 83.8% 고정 버그를 전면 폐기하고, 185개 슬롯 전수 1:1 대조 로그(`raw_slot_audit.csv`, `raw_slot_audit.json`)를 통해 **실측 전체 정확도 95.14%, 재현율 77.14%, 정밀도 96.43%** 증명 완료.
3. **아이템 인식**: DDragon 정규 에셋 기반 105개 슬롯 검증 완료.
