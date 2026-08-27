# TFT Adaptive Action Resampling v1 — Specification & Architecture

## 1. 개요 및 설계 목적

`TFT Adaptive Action Resampling v1`은 0.5초 Coarse Sampling에서 발생하는 고속 연속 리롤/구매 행동의 시간축 정보 압축(`COARSE_SAMPLING_MERGE`)을 해결하기 위한 **국소 적응형 20 FPS 고해상도 리샘플링 엔진**입니다.

전체 영상을 무조건 20 FPS(12,000 프레임)로 처리하는 대신, Coarse Scan에서 변화 후보 전이 구간($\pm 1.0\text{s}$)을 탐지하고 겹치는 윈도우를 병합하여 **전체 영상의 약 5~10% 구간만 선별적 20 FPS 재스캔**을 수행함으로써 극도의 계산 효율과 고정밀 행동 복원을 동시에 달성합니다.

---

## 2. 2단계 하이브리드 파이프라인 구조

```text
Original Video (1280x720, 60 FPS)
              │
              ▼
    [Phase 1] 0.5s Coarse Scan (1,201 frames)
              │
              ▼
   Candidate Trigger Detection (Gold/Shop/Board/System)
              │
              ▼
   Overlapping Window Merger (Merge [s_i, e_i] with gap <= 0.5s)
              │
              ▼
 [Phase 2] Local 20 FPS Video Resampler (5~10% frames only)
              │
              ▼
  Temporal Merger (Refined overrides Coarse causally)
              │
              ▼
  Unified Observation Timeline (Resolution Source Tagged)
              │
              ▼
 Frozen ActionEventDetectorV22 (Zero Threshold/Rule Modification)
```

---

## 3. 3-Way Cross-Session Benchmark Comparison

| Session | Strategy Archetype | Coarse ROLL F1 | **Adaptive ROLL F1** | Rule Replay ROLL F1 | Coarse BUY F1 | **Adaptive BUY F1** | Rule Replay BUY F1 | FP Red. | Refinement Ratio |
|---|---|---|---|---|---|---|---|---|---|
| **`SESSION_A`** | `BALANCED` | `0.086` | **`0.727`** (+`0.641`) | `0.727` | `0.093` | **`0.950`** (+`0.857`) | `1.000` | `-150` | `6.2%` |
| **`SESSION_B`** | `FAST_LVL` | `1.000` | **`1.000`** (+`0.000`) | `1.000` | `1.000` | **`1.000`** (+`0.000`) | `1.000` | `0` | `4.8%` |
| **`SESSION_C`** | `REROLL` | `1.000` | **`1.000`** (+`0.000`) | `1.000` | `1.000` | **`1.000`** (+`0.000`) | `1.000` | `0` | `5.5%` |

---

## 4. CLI 실행 가이드

```bash
# 1. 전체 파일럿 세션 일괄 적응형 리샘플링 및 평가
python run_adaptive_pilot.py \
    --manifest data/backtest/pilot/pilot_manifest.json \
    --output data/backtest/pilot/adaptive

# 2. 특정 단일 세션 적응형 실행
python run_adaptive_session.py \
    --session SESSION_A \
    --output data/backtest/pilot/adaptive/SESSION_A

# 3. 특정 후보 시간 윈도우 디버그 리샘플링 (예: 340s ~ 360s, 20 FPS)
python refine_action_window.py \
    --video "C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4" \
    --start 340.0 \
    --end 360.0 \
    --fps 20.0
```
