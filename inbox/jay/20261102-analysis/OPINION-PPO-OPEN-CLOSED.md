> 분류: A/정책학습
> 작성: 오흥재 (analyst 정리) · 2026-11-02
> 근거: EX-40 저장 env.yaml·agent.yaml · 설치 rsl_rl PPO/GAE · 공식 PPO 설명
> 요지: PPO 두 손잡이만 제한적으로 여는 안에 동의한다. 종료·길이 변경은 경고만으로 같은 과제라고 볼 수 없다.
> 상태: 의견 v0.1 · 코드·설정·실행 변경 없음

# EX-41 PPO와 제어 설정의 변경 범위 의견

**엔트로피 계수와 목표 KL만 명시된 단계 경계에서 열고 나머지 PPO 값과 명목 Kp/Kd는 고정하는 안에 동의한다.** 다만 열린 두 값도 안전한 값이라는 뜻은 아니다. 보행 결과를 보고 성과 규칙과 원장을 통해 바꾸며, 현재 자동 조절이 구현됐다는 뜻도 아니다.

| 항 | 현재 값 · 소비 근거 | 권고와 이유 |
|---|---|---|
| 엔트로피 계수 | 0.01, `agent.yaml:45`; `ppo.py:313` 손실에서 entropy를 빼 탐색 장려 | 제한적으로 열기. 갑자기 높이면 좋은 평균 행동도 표본 행동의 변동으로 깨질 수 있다. action std·평균 행동/표본 행동·명령별 생존을 함께 읽기. 단조 감소가 항상 정답은 아님 |
| 목표 KL | 0.01, `agent.yaml:46`; `ppo.py:259~292` | 제한적으로 열기. KL이 목표 2배를 넘으면 lr/1.5, 절반 미만이면 lr×1.5, 범위 1e−5~1e−2. 목표는 강제 제약이나 조기 종료선이 아니다. 목표만 바꿔도 실제 lr과 갱신 폭이 바뀌므로 둘 다 기록 |
| clip·γ·λ·epoch·minibatch | 0.2·0.99·0.95·5·4, `agent.yaml:39~50` | 이번 처치에서는 고정. clip은 정책/값 갱신, γ·λ는 return/advantage 시간 범위, epoch/분할은 같은 표본의 재사용·노이즈를 바꾼다. 두 열린 값과 동시에 움직이면 원인 구분이 어려움 |
| 종료 조건 | timeout과 실제 종료를 구별, `ppo.py:177~180` timeout bootstrap | 열되 **바뀐 과제임을 경계에서 기록하고 기준 축은 고정**. 알림만 띄워 기존 성공률과 섞으면 안 됨. 넘어짐 판정 완화로 생존이 올라간 경우를 능력 향상으로 읽지 않기 |
| 에피소드 길이 | 20 s, `env.yaml:1887` | 열되 timeout·명령 체류·보상 합·길이 정규화·reset 분포까지 변화한다는 경고. 같은 checkpoint로 변경 전후 고정 길이 평가를 함께 남길 것. 단계 중간 임의 변경 권고 안 함 |
| 명목 Kp·Kd | 25·0.5, hip/thigh와 calf `env.yaml:328~329,343~344` | 고정. 정책 출력에서 토크가 만들어지는 실제 동역학을 바꿔 별도 처치가 됨. 기존 DR의 이득 배율 0.9~1.1은 보존. 명목값 고정은 실제 모든 env가 항상 Kp25라는 뜻이 아님 |

위 권고는 실험 해석과 안정성을 위한 판단이지 원문이 이 목록을 영구 봉인한다는 주장은 아니다. task/curriculum 변경과 PPO 두 손잡이를 한꺼번에 자동 확대하지 않는 쪽을 권한다. 각 변경의 입력 수치·전후 값·저장본·되돌림 조건을 먼저 기록한다.

학습 기록 원문: `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/params/{env,agent}.yaml`. 이 값은 시작 설정이며 현재 optimizer lr 실측은 별도다. GAE의 γ·λ 소비는 `C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/rsl_rl/storage/rollout_storage.py:130~142`, PPO는 같은 site-packages `rsl_rl/algorithms/ppo.py`다. EX-40 고정 코드 `foothold_s2/curriculum/ex40.yaml:21~22`의 gain DR도 대조했다.

PPO-Clip은 비율 clipping으로 과도한 변경의 유인을 줄이지만 KL을 엄격하게 제한하지 않는다. [공식 PPO 설명](https://spinningup.openai.com/en/latest/algorithms/ppo.html#key-equations). 설치본 adaptive lr의 작동은 [rsl_rl v3.1.2 PPO](https://github.com/leggedrobotics/rsl_rl/blob/v3.1.2/rsl_rl/algorithms/ppo.py#L259)와 대조했다. 새 허용 범위의 수치와 실제 보행 효과는 미측정이며 여기서 임의 확정하지 않는다.
