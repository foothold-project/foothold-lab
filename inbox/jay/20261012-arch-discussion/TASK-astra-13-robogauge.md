> 분류: 검증 의뢰 (ASTRA 13 · RoboGauge 결과 해석)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 03:31
> 근거: 하위 작업 보고 `C:/isaac/ext/go2_rl_robotlab/_eval/ROBOGAUGE-E12.md` · 결과 `_eval/out/robogauge/summary.json` · `stress/*/stress_benchmark_results.yaml` (cp949) · lead 가 yaml 의 benchmark_score 로 확인한 값 (저자 정책 0.69535 · 176k 0.69697 · E1 20000 0.52583 · E2 20499 0.61405)
> 요지: 아침 보고에 RoboGauge 점수와 「RoboGauge 에서는 20499 가 20000 보다 높고, 우리 Q (정지 · 저속) 에서는 반대」 를 싣기 전에 해석을 반박 검증한다
> 상태: 의뢰

# ASTRA 의뢰 13 · RoboGauge 결과 해석 검증

**자세:** 평생 이 분야를 탐구한 최고 전문가로서 비판적 · 냉정 · 현실적으로. 읽기 전용 · 커밋 · push · 실행 금지. 결과는 같은 폴더 `VERIFY-astra-13.md`.

1. 하위 작업이 논문에 식이 없어 **재구성한** Tracking · Safety · Quality 묶음과 Level (54 칸 L* 평균) 정의를 RoboGauge 코드 (`C:/isaac/ext/RoboGauge` · v1.1.9 add2c7e) 에서 직접 확인하라. benchmark_score 는 RoboGauge 자체 값이고 나머지 넷은 재구성이다.
2. 「20499 가 20000 보다 높다 (두 시드 +0.061 · +0.074)」 와 「우리 Q 는 20499 가 정지 · 저속에서 나쁘다」 가 어떻게 동시에 참일 수 있나. RoboGauge 가 쓰는 명령 · 속도 범위 · 지형 · DR 을 코드에서 읽고, 원인 해석 (명령 범위 확대 뒤 빠른 명령 추종이 좋아짐) 이 근거가 있는지, 다른 설명이 있는지 적어라. 시드 고정 (재실행 동일) · 시드 둘 · 체크포인트 넷이라는 표본 한계도 평가하라.
3. 이 결과로 말해도 되는 것과 말하면 안 되는 것 (sim2sim 일반화 · 실기 예측 · E1 대 E2 · 논문 정책과의 차이) 을 표로.
