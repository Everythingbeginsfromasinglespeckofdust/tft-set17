# TFT Video Replay Human Review Guide v1.1

## 1. 개요
본 문서는 실제 TFTAcademy 녹화 MP4 경기 영상 기반 Event-Stratified Human Validation의 검토 절차 및 키 바인딩 규격을 정의합니다.

## 2. 키 바인딩 (Keyboard Controls)
- `C`: 전체 예측 일치 (Correct)
- `W`: 오인식 또는 불일치 (Wrong -> errors/ 디렉터리에 크롭 및 스냅샷 자동 저장)
- `R`: 실제 행동이 ROLL (Reroll)
- `B`: 실제 행동이 BUY_UNIT (상점 유닛 구매)
- `L`: 실제 행동이 LEVEL_UP (레벨업)
- `S`: 실제 행동이 SYSTEM_REFRESH (라운드 시작 자동 상점 갱신)
- `N`: 실제 행동이 NO_ACTION (행동 없음 / 골드 절약)
- `X`: 판단 불가 또는 스킵 (Unknown)

## 3. 블라인드 평가 모드 (Blind Review Mode)
1. 시스템은 화면에 Video Frame + Observed GameState(Gold, HP, Shop, Board)만 표시하고 DecisionEngine의 추천 행동을 숨김.
2. 검토자가 주관적인 선호 행동(R/L/S)을 먼저 선택.
3. 선택 완료 후 모델 추천 행동이 공개(REVEAL)되며, `human_decision_time < reveal_time` 시퀀스를 타임스탬프로 보존.

## 4. 도메인별 검증 체크리스트
1. **Shop**: 5개 슬롯 각각의 챔피언 이름, 코스트(1~5), 빈 슬롯(EMPTY) 여부 확인.
2. **Gold**: 실제 Gold HUD 숫자와 OCR 결과 비교 (Forward Carry 여부 확인).
3. **Board**: 체스판 유닛 바운딩 박스 및 챔피언/성급 확인 (빈 헥스 허위 검출 탐지).
4. **Action**: 행동 이벤트 발생 순간(T0)과 전후 전이 일치 확인.
