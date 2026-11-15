> 분류: A/정책학습 · 보상 구현 메모
> 작성: Claude sonnet-code (lead 의뢰 SONNET-X15)
> 근거: leggedrobotics/legged_gym master legged_robot.py(_process_dof_props · _reward_dof_pos_limits · _reward_collision) · a1_config.py, Isaac Lab articulation.py:767 · envs/mdp/rewards.py joint_pos_limits, foothold_s2/rewards/lg_core.py
> 요지: EX-15 = EX-11 + legged_gym A1 기저 묶음 다섯. dof_pos_limits 의 soft 0.9 적용 방식과 calf 충돌 확인 방법
> 상태: 구현 · CPU 시험 완료 · 몸체 이름 확인은 첫 update 의 run.log 한 줄([X15] 충돌 벌점 확인 통과)로 lead 가 한다

# legged_gym A1 기저 묶음 (EX-15)

| 항 | 값 | 구현 |
|---|---|---|
| feet_air_time | +1.0 | EX-14 와 같은 구현(MGDP 식, mgdp_core.py) |
| only_positive_rewards | 켬 | EX-13 의 FootholdS2PosRewardEnv 재사용(보상 합을 0 아래로 자름, 항별 기록은 자르기 전 값) |
| joint_torques | -1e-5 → -2e-4 | a1_config torques, 식은 합 τ² 로 같다 |
| dof_pos_limits | -10 | Isaac Lab `mdp.joint_pos_limits` |
| collision 몸체 | base · thigh · **calf** · Head | 가중치 START -10 · 문턱 0.1 N 그대로 |

## dof_pos_limits 의 soft 0.9

legged_gym `_reward_dof_pos_limits` 는 `-(q - lo).clip(max=0) + (q - hi).clip(min=0)` 의 관절 합이고, lo · hi 는 `_process_dof_props` 가 `m ∓ 0.5 r 0.9` 로 만든 soft 한계다.
Isaac Lab `mdp.joint_pos_limits` 는 같은 식을 `soft_joint_pos_limits` 에 적용하고, 그 값은 articulation 이 `joint_pos_mean ∓ 0.5 x range x soft_joint_pos_limit_factor` 로 만든다.
Go2 의 `UNITREE_GO2_CFG` 가 이미 `soft_joint_pos_limit_factor=0.9` 이고 우리 `GO2_S1_CFG` 는 그 값을 바꾸지 않는다. 그래서 새 항 없이 Isaac 항을 그대로 쓰며 로봇 cfg 도 reset 클램프도 달라지지 않는다.
시험(test_x15.py)이 두 식의 같음과 위 소스 줄의 존재를 확인한다.

## collision 에 calf 추가

START 충돌 항(`collision_term`)을 그대로 쓰고 몸체만 ["base", ".*_thigh", ".*_calf", "Head_.*"] 로 넓힌다. calf 와 foot 이 같은 강체이면 정상 접지가 벌점이 된다.
Go2 USD 에서는 foot 이 별도 강체로 쓰이고 있다(발 접촉 · 발 위치를 `.*_foot` 강체로 읽는 기존 코드 전부가 그렇다). 이것을 Kit 이름으로 직접 확인하려고 `lg_terms.collision_checked` 가 첫 호출에서
calf 4 개 · foot 4 개가 서로 다른 강체이고 calf 는 모두 벌점 대상, foot 은 하나도 아님을 검사하고 run.log 에 이름표를 한 줄 찍는다. 어긋나면 예외로 멈춘다(조용히 벌점을 주지 않는다).

## 넣지 않은 것

motion_trot · stand_still(MGDP 고유), 몸통 접촉 종료(START 대로 없음).
