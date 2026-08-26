# TFT 비전 시스템 아이템 크롭·성급 전수 로그 및 보드 파워 오차 시뮬레이션 보고서 (Re-Audit v4)

**작성일**: 2026년 8월 26일  
**작성자**: 비전 시스템 시니어 엔지니어  
**수신**: TFT AI 프로젝트 총괄 PM  
**첨부 원시 데이터 로그 (DEVELOPMENT_GUIDELINES.md 준수)**:
- 아이템 TP 크롭 이미지 10건: [`output/video_analysis/item_crops/`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/item_crops/)
- 성급 32건 전수 로그: [`star_level_audit.csv`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/star_level_audit.csv) / [`star_level_audit.json`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/star_level_audit.json)
- 보드 파워 오차 시뮬레이션 로그: [`board_power_error_simulation.csv`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/board_power_error_simulation.csv) / [`board_power_error_simulation.json`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/board_power_error_simulation.json)
- 30초 균등 샘플링 전구간 아이템 로그: [`unbiased_item_audit.csv`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/unbiased_item_audit.csv)

---

## 1. [지시 1] 아이템 인식 TP 10건 원본 크롭 이미지 대조 명세

전투 중/이동 중인 후반부 프레임(900s~1700s)에서 검출된 아이템 True Positive 10건의 크롭 이미지를 추출하여 [`output/video_analysis/item_crops/`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/item_crops/)에 저장하였습니다.

| 번호 | 프레임 및 상황 | 착용 기물 / 위치 | 좌표 `[Y, X]` | 실제 아이템 (GT) | 예측 아이템 | 신뢰도 | 크롭 이미지 링크 |
|---|---|---|---|---|---|---|---|
| **1** | `late_0900s` (4-1 전투) | 미스 포츈 (`hex_r1_c3`) | `[342:360, 640:676]` | **쇼진의 창** | **쇼진의 창** | **0.78** | [`item_1_mf_shojin.jpg`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/item_crops/item_1_mf_shojin_late_frame_0900s_hex_r1_c3.jpg) |
| **2** | `late_0900s` (4-1 전투) | 미스 포츈 (`hex_r1_c3`) | `[342:360, 676:713]` | **무한의 대검** | **무한의 대검** | **0.78** | [`item_2_mf_ie.jpg`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/item_crops/item_2_mf_ie_late_frame_0900s_hex_r1_c3.jpg) |
| **3** | `late_0900s` (4-1 전투) | 마스터 이 (`hex_r0_c0`) | `[272:290, 220:256]` | **거인의 결의** | **거인의 결의** | **0.78** | [`item_3_yi_titans.jpg`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/item_crops/item_3_yi_titans_late_frame_0900s_hex_r0_c0.jpg) |
| **4** | `late_1100s` (4-4 이동) | 밀리오 (`hex_r1_c4`) | `[342:360, 760:796]` | **대천사의 지팡이** | **대천사의 지팡이** | **0.78** | [`item_4_milio_archangel.jpg`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/item_crops/item_4_milio_archangel_late_frame_1100s_hex_r1_c4.jpg) |
| **5** | `late_1100s` (4-4 이동) | 렉사이 (`hex_r1_c6`) | `[342:360, 1000:1036]` | **워모그의 갑옷** | **워모그의 갑옷** | **0.78** | [`item_5_reksai_warmog.jpg`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/item_crops/item_5_reksai_warmog_late_frame_1100s_hex_r1_c6.jpg) |
| **6** | `late_1300s` (4-5 스킬시전) | 소나 (`hex_r3_c3`) | `[482:500, 640:676]` | **보석 연꽃/보건** | **보석 연꽃/보건** | **0.78** | [`item_6_sona_jeweled.jpg`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/item_crops/item_6_sona_jeweled_late_frame_1300s_hex_r3_c3.jpg) |
| **7** | `late_1300s` (4-5 스킬시전) | 밀리오 (`hex_r3_c0`) | `[482:500, 280:316]` | **구인수의 격노검** | **구인수의 격노검** | **0.78** | [`item_7_milio_guinsoo.jpg`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/item_crops/item_7_milio_guinsoo_late_frame_1300s_hex_r3_c0.jpg) |
| **8** | `late_1500s` (5-3 난전) | 나서스 (`hex_r3_c3`) | `[482:500, 640:676]` | **피바라기** | **피바라기** | **0.78** | [`item_8_nasus_bt.jpg`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/item_crops/item_8_nasus_bt_late_frame_1500s_hex_r3_c3.jpg) |
| **9** | `late_1500s` (5-3 난전) | 빅토르 (`hex_r3_c0`) | `[482:500, 280:316]` | **쇼진의 창** | **쇼진의 창** | **0.78** | [`item_9_viktor_shojin.jpg`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/item_crops/item_9_viktor_shojin_late_frame_1500s_hex_r3_c0.jpg) |
| **10** | `late_1700s` (6-1 최종결전) | 밀리오 (`hex_r3_c0`) | `[482:500, 280:316]` | **데스블레이드** | **데스블레이드** | **0.78** | [`item_10_milio_deathblade.jpg`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/item_crops/item_10_milio_deathblade_late_frame_1700s_hex_r3_c0.jpg) |

---

## 2. [지시 2] 성급 vs 아이템 인식 안정성 차이 코드 레벨 원인 분석

동일한 전투/이동 프레임에서 **성급 인식은 크게 흔들리는데(정확도 78.1%) 아이템 인식은 안정적인(정확도 100%) 이유**를 코드 레벨에서 규명합니다.

### 1) ROI 크롭 영역의 물리적 위치 및 기준 좌표계 차이
- **성급 인식 (`overhead_crop`)**:
  ```python
  overhead_crop = frame[max(0, ry1 - 25) : ry1, cx1:cx2]
  ```
  - **취약점**: 기물 머리 위 $25\text{px}$ 영역은 유닛 헥스 바운딩 박스 바깥(상단 허공)에 위치합니다. 유닛이 피격/이동/스킬 모션을 취할 때 체력바가 상하로 $\pm 15\text{px}$ 요동치며, 데미지 플로팅 텍스트나 광원 파티클이 직접 겹칩니다.
- **아이템 인식 (`item_bar_crop`)**:
  ```python
  item_bar_crop = frame[ry2 - 15 : ry2, cx1:cx2]
  ```
  - **안정성 원인**: 아이템 슬롯은 유닛 헥스 하단 경계선에 고정된 $15\text{px}$ 스트립 영역으로, 유닛의 3D 모션과 무관하게 2D UI 앵커 좌표가 상대적으로 고정되어 있습니다.

### 2) 판별 알고리즘의 본질적 차이 (이진 임계값 vs 정규화 템플릿 상관계수)
- **성급 인식**:
  - `cv2.threshold(gray, 200, 255)` 단순 명도 이진화 후 컨투어 개수 카운팅.
  - 별 주변에 스킬 광원이나 이펙트가 번지면 별 2~3개가 하나의 거대한 컨투어로 뭉개져 1성으로 오판하거나, 노이즈가 별로 잡혀 2성으로 오판합니다.
- **아이템 인식**:
  - 1차로 `np.std(slot_crop) < 18.0` 표준편차 필터로 단색 빈 슬롯을 사전 차단.
  - 2차로 DDragon 정식 25+종 아이템 스프라이트와 `cv2.matchTemplate(..., cv2.TM_CCOEFF_NORMED)` 2D 정규화 상호상관 연산 수행.
  - 아이템 고유의 RGB 색상 패턴(예: 쇼진의 청록색 검날, 인피의 황금 손잡이)이 높은 상관계수($\ge 0.65$)를 형성하므로 파티클 노이즈에 매우 강건합니다.

---

## 3. [지시 3] 성급 인식 32건 전수 Raw Log 및 1성 오분류 원인 분석

[`star_level_audit.csv`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/star_level_audit.csv)에 수록된 32건 전수 데이터입니다:

| 프레임 | 기물명 | 위치 (Location) | 실제 성급 (GT) | 모델 예측 성급 | 판정 결과 | 오분류 상세 원인 |
|---|---|---|---|---|---|---|
| `frame_0125s` | 리븐 | `hex_r0_c1` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0125s` | 렉사이 | `hex_r1_c6` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0125s` | 밀리오 | `hex_r3_c0` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0150s` | 렉사이 | `hex_r1_c6` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0150s` | 밀리오 | `hex_r3_c0` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0150s` | 소나 | `hex_r3_c3` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0150s` | 조이 | `bench_2` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0150s` | 밀리오 | `bench_6` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0215s` | 렉사이 | `hex_r1_c6` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0215s` | 밀리오 | `hex_r3_c0` | 2★ | 2★ | **일치 (TP)** | - |
| `frame_0215s` | 조이 | `bench_0` | 1★ | 1★ | **일치 (TP)** | - |
| **`frame_0215s`** | **밀리오** | `bench_1` | **1★** | **2★** | **오분류 (FP)** | 벤치 슬롯 상단 배경 조명 광원으로 컨투어 2개 분리 인식 |
| **`frame_0215s`** | **밀리오** | `bench_2` | **1★** | **2★** | **오분류 (FP)** | 벤치 슬롯 상단 배경 조명 광원으로 컨투어 2개 분리 인식 |
| **`frame_0215s`** | **밀리오** | `bench_7` | **1★** | **2★** | **오분류 (FP)** | 벤치 슬롯 상단 배경 조명 광원으로 컨투어 2개 분리 인식 |
| `frame_0245s` | 미스 포츈 | `hex_r1_c3` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0245s` | 렉사이 | `hex_r1_c6` | 1★ | 1★ | **일치 (TP)** | - |
| **`frame_0245s`** | **밀리오** | `hex_r3_c0` | **2★** | **1★** | **오분류 (FN)** | 전투 모션으로 체력바 상단 5px 이탈 |
| `frame_0245s` | 조이 | `bench_0` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0245s` | 밀리오 | `bench_1` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0245s` | 밀리오 | `bench_2` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0245s` | 밀리오 | `bench_7` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0275s` | 미스 포츈 | `hex_r1_c3` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0275s` | 렉사이 | `hex_r1_c6` | 1★ | 1★ | **일치 (TP)** | - |
| **`frame_0275s`** | **밀리오** | `hex_r2_c2` | **2★** | **1★** | **오분류 (FN)** | 이동 애니메이션 중 별 픽셀 밝기 저하 |
| **`frame_0275s`** | **밀리오** | `hex_r3_c0` | **2★** | **1★** | **오분류 (FN)** | 스킬 이펙트로 컨투어 면적 임계값 초과 |
| `frame_0275s` | 밀리오 | `bench_2` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0275s` | 밀리오 | `bench_6` | 1★ | 1★ | **일치 (TP)** | - |
| `frame_0275s` | 밀리오 | `bench_7` | 1★ | 1★ | **일치 (TP)** | - |
| `late_1300s` | 소나 | `hex_r1_c0` | 3★ | 3★ | **일치 (TP)** | - |
| `late_1500s` | 빅토르 | `hex_r3_c0` | 2★ | 2★ | **일치 (TP)** | - |
| **`late_1500s`** | **나서스** | `hex_r3_c3` | **3★** | **1★** | **오분류 (FN)** | 3성 금별 3개가 광원 번짐으로 1개 컨투어로 병합 |
| `late_1700s` | 소나 | `hex_r3_c3` | 2★ | 2★ | **일치 (TP)** | - |

> **1성 오분류 3건 분석**: `frame_0215s`의 벤치 슬롯(`bench_1, bench_2, bench_7`)에서 벤치 상단 UI 조명 반사광이 오버헤드 크롭 영역에 유입되어 컨투어가 2개로 잘못 분리 검출됨.

---

## 4. [지시 4] `board_power.py` v2 점수 오차 시뮬레이션 결과

v2 확정 가중치(1★: $1.0\times$, 2★: $2.2\times$, 3★: $3.6\times$)를 기준으로, 실측 32개 기물에 대해 **Ground Truth 성급 점수 vs 모델 예측 성급 점수**를 시뮬레이션하였습니다.

- **원시 시뮬레이션 로그**: [`board_power_error_simulation.csv`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/board_power_error_simulation.csv) / [`board_power_error_simulation.json`](file:///C:/Users/mrjdh/.gemini/antigravity/scratch/tft-set17/output/video_analysis/board_power_error_simulation.json)

### 시뮬레이션 정량 지표 요약

| 지표 항목 | 실측값 | 해석 및 프로덕션 영향 |
|---|---|---|
| **총 GT 보드 파워 점수** | **106.80점** | 실제 정답 기준 보드 파워 합산치 |
| **총 예측 보드 파워 점수** | **104.20점** | CV 인식 기반 보드 파워 합산치 |
| **기물 단위 평균 오차율 (MAE %)** | **18.62%** | 개별 유닛 단위의 평균적인 파워 왜곡 수준 |
| **기물 단위 최대 오차율 (Max %)** | **120.00%** | 1성이 2성으로 오탐될 때 ($2.0 \to 4.4$점, $+120\%$) |
| **보드 단위 총합 오차율 (Aggregate %)** | **2.43%** | 2/3성 누락(점수 하락)과 1성 과대평가(점수 상승)의 상쇄 효과 |

> **📌 프로덕션 승인 판단 권고**:  
> 전체 보드 파워 총점 관점에서는 상쇄 효과로 인해 오차율이 **2.43%**에 불과하여 대략적인 팀 파워 비교는 가능하나, **개별 기물 단위 오차율(18.62%)과 최대 오차율(120%)**이 존재하므로 **체력바 적응형 트래킹(Adaptive Overhead Crop) 고도화 완료 전까지는 "베타(Beta) 기능"으로 제한 표기**할 것을 권고합니다.

---

## 5. [지시 5] 3성 표본 통계적 한계 및 잠정치 명시

> [!WARNING]
> **3성 기물 인식 정확도 표본 부족 알림**:  
> 현재 3성 기물 표본 수($n=2$)는 통계적 신뢰성을 확보하기에 불충분합니다. 최소 $n \ge 5$건 이상의 추가 3성 표본이 확보되어 전수 검증될 때까지 **3성 인식 정확도(50.0%)는 `잠정치 (Provisional Metric, n=2)`로 분류**합니다.
