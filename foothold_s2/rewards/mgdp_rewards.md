> 분류: A/정책학습 · 보상 구현 메모
> 작성: Claude sonnet-code (lead 의뢰 SONNET-X13)
> 근거: MGDP legged_gym random_dog.py:803 · 1004, base/legged_robot.py:237 · 1099, random_dog_config_stage1.py:17 · 187~192, foothold_s2/rewards/mgdp_core.py
> 요지: EX-13(MGDP 보상 넷)과 EX-14(feet_air_time 하나)의 식, 원문에서 고친 두 곳, 게이트 값, 기록 방법
> 상태: 구현 · CPU 시험 완료 · Kit 이름 확인(smoke)은 lead 가 한다

# MGDP 보상 묶음 (EX-13 · EX-14)

| 항 | 가중치 | 식 (원문 그대로 / 고친 곳) |
|---|---:|---|
| feet_air_time | +1.0 | 원문 그대로: 발 접촉 첫 순간에 합(공중 시간 - 0.5). 접촉 = Fz > 1 N 또는 직전 접촉(OR), 공중 시간은 보상 계산 앞에서 dt 를 더한 값, \|cmd_xy\| > 0.1 일 때만. Isaac Lab `mdp.feet_air_time` 과 달리 직전 접촉과의 OR 을 쓴다 |
| motion_trot | -0.1 | 대각 다리(FL-RR, FR-RL)의 hip · thigh · calf 각각 관절 차의 합. **고친 곳 1:** 관절각 q 대신 (q - q_default). 이유: Go2 기본 자세의 hip 이 왼쪽 +0.1 · 오른쪽 -0.1 이라 원식 그대로면 서 있기만 해도 상수 벌점 0.4 (FL-RR 0.2 + FR-RL 0.2). 관절 짝은 번호가 아니라 이름으로 맺는다(Isaac Lab 은 hip 4 · thigh 4 · calf 4 순서) |
| stand_still | -0.1 | 합 \|q - q_default\|. **고친 곳 2:** 원식의 문 \|cmd_xy\| < 0.1 만 쓰면 START 제자리 회전(vx = 0, wz != 0)에서 켜져 회전을 막는다. 그래서 \|cmd_xy\| < 0.1 그리고 \|wz\| < 0.1 일 때만 켠다 |
| only_positive_rewards | (보상 합 처리) | 한 step 의 보상 합을 0 아래로 자른다(원문 legged_robot.py:237). 우리 env 에는 termination 보상 항이 없다 |

## 게이트 (motion_trot)

- 지형 단계 > 3 이면 0 (MGDP stage1 의 env_gait = 3 과 같은 부등호).
- 전체 step 이 2e4 를 넘으면 0 (원문 `common_step_counter > 2e4`). 우리 env 에서는 `env.common_step_counter`(env.step 호출 수, rollout 한 update 에 24)가 같은 뜻이고, update 약 833 회에 해당한다.

## stand_still 이 START 명령에서 하는 일 (정확히)

START 명령에는 «0 명령» 이 없지만(걷기 가지 vx >= 0.3, 회전 가지 vx = 0 · wz ~ U[-1.2, 1.2]) 회전 가지의 wz 가 0 근처로 뽑히면 |cmd_xy| < 0.1 그리고 |wz| < 0.1 이 켜진다.
확률은 회전 가지 안에서 0.1 / 1.2 = 약 8.3 %, 회전 가지가 전체의 20 % 이므로 표집의 약 1.7 % 다(시험으로 확인). 즉 «완전히 꺼짐» 이 아니라 «거의 꺼짐» 이다.

## 기록

- 항별 값은 Episode_Reward/feet_air_time · motion_trot · stand_still 로 보이고(보상 관리자 기본 기록), 이 값과 reward_split 의 항별 값은 **자르기 전** 값이다.
- 얼마나 잘렸는지: reward_split 의 only_positive_clipped_frac(전체와 움직임/멈춤 집단별), Episode_Reward/only_positive_clipped_fraction(에피소드 평균).
- EX-13 task: FootholdS2-Go2-S2-X13-v0 (env 클래스 FootholdS2PosRewardEnv), EX-14: FootholdS2-Go2-S2-X14-v0. 둘 다 agent cfg S2X13PPORunnerCfg(est_mode zero, 나머지는 EX-11 과 같다).
