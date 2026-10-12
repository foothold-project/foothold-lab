> 분류: 설계 의뢰 (ASTRA 12 · 공통 평가 계약)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 03:01
> 근거: `VERIFY-astra-11.md` 2 · 3 절 (v2 공통 비교를 먼저) · `PLAN-next-after-astra11.md` 의 10/13 ~ 14 단계 · 팀장 10/13 01:10 「v2 와 견줘 왜 새로 접근하고 무엇을 얻었나」
> 요지: 동결 v2 · CMD-R 후보 · 앞으로의 A/B 를 같은 시험지로 재는 평가 계약을 구체적으로 설계한다 (구현은 lead · 실행은 Linux 이전 뒤)
> 상태: 의뢰

# ASTRA 의뢰 12 · v2 · CMD-R · A/B 공통 평가 계약

**자세:** 이 분야를 평생 탐구한 최고 전문가로서 비판적 · 냉정 · 현실적으로. 읽기 전용 · 커밋 · push · 학습 · 평가 금지 (GPU 두 장 사용 중). 결과는 같은 폴더 `DESIGN-astra-12-common-eval.md` 하나. 너의 VERIFY-astra-11 3.3 절 표가 출발점이다.

## 재료

- v2: `models/foothold-v2.json` (관측 235 = 몸 48 + 지도 187 · 명령 · 판 2 잣대 · 지형 시드별 기록) · `sim/eval/` 의 v2 평가 코드 (generalization_env_cfg.py · eval_generalization.py 등)
- MoE-CTS 평가기: `C:/isaac/ext/go2_rl_robotlab/_eval/q_eval_cmdr.py` · `q_metrics.py` · `q_post.py` (span · q1a 정의) · 미경험 지형 `unseen_post.py`
- 앱 요구: `inbox/jay/20261013-go2-app-study/APP-PLAN-facts.md` (자율 0.5 · 감속 구역 0.2 ~ 0.3 m/s · STOP)

## 정할 것

1. **실행 계약:** 같은 물리 · 충돌 지형 · 제어 주기 · 초기 상태 · DR · 명령 시퀀스를 두 계열 (v2 의 235 관측 MLP · MoE-CTS student 의 45 × 10 이력) 에 주는 adapter 설계. v2 의 heading 명령 처리를 어떻게 맞출지.
2. **칸 정의:** 기존 능력 (gap · rails · rough · 0.5 / 1.0 / 1.5 m/s) · 새 저속 (0.1 · 0.2 · 0.3 · 0.5 m/s · 명령 크기에 맞춘 시간 · 거리 · 상대 오차) · 횡 · 후진 · 회전 · STOP (정지 시간 · 거리 · 잔류 이동 · 위험 구간 진입 전 정지 가능 범위) · 장애물 조우 기록 (조우 · 우회 · 도착 · 추락 · 정체, 보행 능력 시험과 앱 운용 시험 분리).
3. **표본과 통계:** 지형 시드 · 출발 조건 수, 짝 비교, 지형 군집과 학습 시드 변동을 반영한 구간.
4. **최소 구현 순서:** 지금 있는 코드에서 무엇을 고치고 무엇을 새로 써야 하나, 그리고 각 단계의 알려진 입력 시험.

형식: 맨 위 다섯 줄 머리 · 각 줄 `확인됨 (파일 · 행) · 추정 · 미확인`.
