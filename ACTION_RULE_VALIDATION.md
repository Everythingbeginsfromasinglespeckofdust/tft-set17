# TFT Action Rule Validation v1 — 실측 Causal Signature의 규칙 후보 검증 Specification

## 1. 개요 및 배경

TFT Set 17 비전 파이프라인에서 Causal Audit v1을 통해 실측된 프레임 레벨 시그니처를 기반으로, **후보 규칙군(`ROLL_A` ~ `ROLL_D`, `BUY_A` ~ `BUY_C`, `SYSTEM_REFRESH_A`, `SHOP_ANIMATION`)**을 정의하고 동일한 Ground Truth 데이터셋(`gt_session_01.json`)에 대해 정량적 Replay 평가를 수행하였습니다.

본 단계에서는 Production Detector(`ActionEventDetectorV2.1`)나 `DecisionEngine`을 수정하지 않으며, 오직 **규칙의 통계적 유효성(Precision, Recall, F1, Coverage, Likelihood Ratio, Failure Modes, Conflict)**을 엄밀히 검증하여 차세대 검출기(v2.2)의 설계 근거를 확립합니다.

---

## 2. 후보 규칙군 정의 (Rule Candidate Definitions)

### 1) ROLL 후보 규칙
- **`ROLL_A` (보수적 규칙)**:
  $$\text{gold\_delta} == -2 \land \text{shop\_changed} \ge 1 \land \neg \text{system\_refresh} \land \text{board\_unchanged} \land \text{bench\_unchanged}$$
- **`ROLL_B` (구매 배제 규칙)**:
  $$\text{gold\_delta} == -2 \land \text{shop\_changed} \ge 1 \land \neg \text{system\_refresh} \land \neg \text{has\_buy\_evidence}$$
- **`ROLL_C` (보드/벤치 제약 완화 규칙)**:
  $$\text{gold\_delta} == -2 \land \text{shop\_changed} \ge 1 \land \neg \text{system\_refresh}$$
- **`ROLL_D` (동종 기물 충돌 대응 규칙)**:
  $$\text{gold\_delta} == -2 \land \text{shop\_transition\_detected} \land \neg \text{system\_refresh}$$

### 2) BUY_UNIT 후보 규칙
- **`BUY_A` (3중 증거 결합 규칙)**:
  $$\text{shop\_slot\_emptied} \land \text{matching\_champion\_added} \land \text{gold\_delta} == -\text{cost} \land \neg \text{shop\_animation}$$
- **`BUY_B` (벤치 추가 미확인 규칙)**:
  $$\text{shop\_slot\_emptied} \land \text{gold\_delta} == -\text{cost} \land \neg \text{shop\_animation}$$
- **`BUY_C` (골드 미확인 규칙)**:
  $$\text{shop\_slot\_emptied} \land \text{matching\_champion\_added} \land \neg \text{shop\_animation}$$

### 3) 시스템 및 과도기 규칙
- **`SYSTEM_REFRESH_A`**:
  $$\text{shop\_changed} \ge 3 \land \text{gold\_delta} == 0 \land \text{round\_transition}$$
- **`SHOP_ANIMATION`**:
  $$\text{partial\_empty\_state} \land \text{duration} \le 0.15\text{s} \land \text{followed\_by\_stable\_shop}$$

---

## 3. 검증 지표 및 통계적 정의

- **정밀도 (Precision)**: $\frac{TP}{TP + FP}$
- **재현율 (Recall / Coverage)**: $\frac{TP}{TP + FN} = P(\text{Rule} \mid \text{Target})$
- **위양성률 (FPR)**: $\frac{FP}{FP + TN} = P(\text{Rule} \mid \text{Non-Target})$
- **특이도 (Specificity)**: $1 - \text{FPR} = \frac{TN}{TN + FP}$
- **우도비 (Likelihood Ratio)**:
  $$LR = \frac{P(\text{Rule} \mid \text{Target})}{P(\text{Rule} \mid \text{Non-Target})}$$
  *(단, 분모가 0인 경우 $\infty$로 표기하며, Laplace Smoothing $\alpha=1.0$ 적용값을 병기)*

---

## 4. CLI 실행 가이드

```bash
# 1. 후보 규칙 정량 검증 및 커버리지 매트릭스 생성
python validate_action_rules.py \
    --video "C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings\eda87ad9-7e10-46f5-904e-8f10084bf706-2026-07-29-02-41-03.mp4" \
    --ground-truth data/vision_audit/annotations/gt_session_01.json \
    --output data/vision_audit/rule_validation
```
