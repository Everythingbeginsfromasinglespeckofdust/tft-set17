# TFT ActionEventDetector v2.1 — System Refresh 분리 및 원본 영상 Adaptive Event Detection Specification

## 1. 개요 및 배경

TFT Set 17 비전 파이프라인에서 상점 기물 및 코스트 인식(`ShopRecognizerV2`)이 200개 Ground Truth 슬롯에 대해 **100.0% 정확도**를 달성한 상태에서, ActionEventDetector v2가 노출한 **125개의 False Positive**와 **39개의 False Negative**를 해결하기 위해 **ActionEventDetector v2.1**을 구축합니다.

### 핵심 문제 원인 및 해결책:
1. **시스템 무료 상점 갱신 분리 (`SystemEventDetector`)**:
   - 라운드 전환(3-1 $\to$ 3-2 등) 및 골드 소비 없는 전체 상점 갱신을 `SYSTEM_SHOP_REFRESH`로 독립 격리하여 플레이어 `ROLL` 오탐 완벽 차단.
2. **화면 안정성 분석 및 애니메이션 필터 (`StateStabilityAnalyzer`)**:
   - 리롤 시 카드가 슬라이드되는 과도기 프레임을 `SHOP_ANIMATION`으로 분류하여 허위 `BUY_UNIT` 오탐 차단.
3. **원본 MP4 적응형 고해상도 리샘플링 (`AdaptiveResampler`)**:
   - $0.5\text{초}$ coarse timeline에서 전이가 감지된 구간만 원본 비디오에서 $20\text{ FPS}$ ($0.05\text{초}$ 간격)로 정밀 재스캔하여 고속 연타 리롤(<0.5s) 누락(FN) 복원.

---

## 2. 아키텍처 및 데이터 흐름

```text
Full Video (1280x720, 60fps)
             ↓
[ Coarse 0.5s Scan / Timeline.json ]
             ↓
[ StateDiff Engine ] (ΔGold, ΔHP, ΔLevel, SlotTransitions)
             ↓
   Candidate Transition Detected?
   ├── YES ──> [ AdaptiveResampler ] (Raw MP4 local 20 FPS rescan at 0.05s)
   └── NO  ──> [ Standard 0.5s Diff ]
             ↓
[ SystemEventDetector ] ──> SYSTEM_SHOP_REFRESH / ROUND_START
             ↓
[ StateStabilityAnalyzer ] ──> SHOP_ANIMATION filter
             ↓
[ Multi-Signal Evidence Fusion ]
             ↓
Standardized ActionEvent (PLAYER_ROLL, BUY_UNIT, LEVEL_UP, etc.)
```

---

## 3. CLI 실행 가이드

### (1) 비디오 + 타임라인으로부터 v2.1 액션 검출 (적응형 리샘플링 포함):
```bash
python detect_actions_v21.py \
    --video "C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4" \
    --timeline data/vision_audit/new_shop_timeline/timeline.json \
    --output data/vision_audit/action_v21
```

### (2) Ground Truth 대비 정량 평가 및 6x6 오차행렬 리포트 생성:
```bash
python evaluate_actions_v21.py \
    --predictions data/vision_audit/action_v21/predictions.jsonl \
    --ground-truth data/vision_audit/annotations/gt_session_01.json \
    --output data/vision_audit/action_v21/reports
```

### (3) 특정 시간 구간 적응형 리샘플링 단독 검사:
```bash
python refine_action_window.py \
    --video "C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4" \
    --start 342.0 \
    --end 344.5 \
    --fps 20.0
```
