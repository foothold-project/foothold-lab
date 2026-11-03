# goal1r3 동결 설정 - goal-MLP 교사 첫 학습 (10-07)

**기술 정본(실값은 이 파일들이 정답):** `code-goal1r3-20261007/foothold_lla/spec.py` · `env_cfg.py` · `core.py` · `agent_cfg.py` · `policy.py` · `terrain_meshes.py` + 지형 자산 `s0/asset_try4.json`(Pod 작업 폴더 `<pod-work>/24-perceptive-first-env-20261007/s0/asset_try4.json`).
이 문서는 그 값을 옮겨 적은 사본이다. 서로 다르면 위 파일이 정답이다. sha 값은 맨 아래 표에 있다.

## 0. 목적과 하지 않는 것
- 속도 명령 교사(LL-A s1)와 같은 지형·로봇·물리·망·PPO 를 쓰고, **명령과 보상만 몸좌표 local waypoint 목표로 바꿔** 무작위 초기화부터 1 seed 를 학습한다.
- 이 학습은 상위 최단경로 능력, 센서 학생, 도달 불가 목표 판단을 **얻었다고 주장하지 않는다.** 목표는 도달 가능한 0.8–2.0 m local waypoint 뿐이다.
- 후속으로 미룬 것: goal+CNN/attention 비교, C2(비용 mock/학생 unknown), seed2.

## 1. 입출력·망
| 그룹 | 차원 | 내용 | 누가 씀 |
|---|---|---|---|
| proprio | 42 | joint_pos 12, joint_vel 12, base_ang_vel 3, projected_gravity 3, last_action 12 | actor·critic |
| command | 6 | 몸좌표 목표 [dx_b, dy_b](길이를 2.0 m 로 자르되 방향 유지), sin Δψ, cos Δψ, v_cap, h. **남은 시간은 actor 에 없음** | actor·critic |
| goal_critic | 2 | clamp(t_left,0,20)/20, clamp(d,0,6)/6 | critic 만 |
| privileged | 26 | 질량·마찰·지지면 등(부모와 같음) | critic 만 |
| gt_terrain | 1222 | 몸 격자 33×17(0.05 m, x −0.5…1.1, y ±0.4) 높이 561 + 상태(부모와 같음) | actor·critic |
- 망: TerrainEncoderActorCritic(부모와 같음). 지형 잠재 64, actor·critic MLP [512,256,128] elu, 머리 입력 actor 112, critic 140. init_noise_std 1.0, obs 정규화 없음.
- 출력: 관절 위치 12, action_scale 0.25.

## 2. 목표 계약
- 분류 확률: stop 0.10 / low 0.20 / turn 0.10 / general 0.60
- 예산(목표 1개의 시간): 먼저 U[4,8] s 를 뽑는다. 이동 목표는 max(그 값, d0/(0.7·v_cap)+2.0) 로 늘리고, 상한은 20 s 다.
- stop: 목표 = 현재 자세(정확히 p0, 상자 자름 없음), Δψ 0, v_cap 0
- turn: 목표 = p0, |Δψ| ~ U[30°,180°], 부호는 무작위, v_cap 0
- low: v_cap U[0.15,0.3] m/s, d0 U[0.8,1.2] m
- general: v_cap U[0.5,1.0] m/s, d0 U[0.8,2.0] m
- 이동 목표 최소거리 0.8 m: 성공반경 0.5 m·정지반경 0.25 m 보다 크다. 출발할 때부터 성공 범위 안에 있는 목표는 없다.
- 방위 U(−π,π]. heading = 방위 + U(±45°). h 는 25% 만 U[h_min,h_nom], 나머지는 h_nom.
- **평지·요철·경사** 이동 목표는 타일 중심 기준 |x|,|y| ≤ 4.0 으로 자른다.
  - 잘려서 0.8 m 미만이 되면 반대 방위로 한 번 다시 놓는다(heading 도 +π).
  - 그래도 0.8 m 미만이면 stop 목표로 바꾼다.
  - 로그: goal_clamped·goal_flip·goal_to_stop
- **계단·턱** 이동 목표는 참조선(출발점, reset yaw) 위에 놓는다. heading 은 선의 yaw 다.
  - general: cheb = min(end_r+0.8, 4.1) 에 처음 닿는 점(끝발판 위)
  - low: min(그 점, 현재 진행 + d0)
  - 예산 = clamp(거리/(0.7·v_cap)+2, 4, 20)
  - 0.8 m 미만이면(이미 도착) stop 으로 바꾼다.
- 재샘플: 예산 만료 시 현재 자세 기준으로 다시 뽑는다. reset 된 env 는 reset 자세 기준이다.

## 3. 보상 18항 (dt 0.02 s 마다 weight×값×dt)
| 항 | 가중치 | 정의 |
|---|---|---|
| goal_pos | 10.0 | 𝟙(t_left<2)/2 · 1/(1+d²) |
| goal_heading | 5.0 | 𝟙(t_left<1)/1 · 1/(1+Δψ²) · 𝟙(d<0.5) |
| goal_move | 1.0 | 𝟙(d<0.5 ∨ (cos(목표방향, 속도)>0.5 ∧ 0.5·v_cap ≤ \|v_xy\| ≤ v_cap+0.1 ∧ v_cap>0)) |
| goal_overspeed | −1.0 | max(0, \|v_xy\|−v_cap) |
| track_height_cmd | 0.5 | 부모와 같음 |
| lin_vel_z_l2 | −2.0 | 부모와 같음 |
| ang_vel_xy_l2 | −0.05 | 부모와 같음 |
| joint_torques_l2 | −2e-4 | 부모와 같음 |
| joint_acc_l2 | −2.5e-7 | 부모와 같음 |
| action_rate_l2 | −0.01 | 부모와 같음 |
| joint_pos_limits | −1.0 | 부모와 같음 |
| feet_air_time | 0.01 | 부모와 같음, 문턱 0.5 s. 켜는 조건 = 자른 목표벡터 길이 > 0.1 |
| swing_clearance | −0.5 | 부모와 같음, 목표 0.05 m |
| feet_slip_contact | −0.25 | 부모와 같음 |
| feet_stumble | −0.5 | 부모와 같음 |
| undesired_contacts | −1.0 | base·head·thigh·calf 접촉 > 1 N(부모와 같음, 종아리 포함) |
| stand_still_goal | −0.5 | 부모 stand_still 식, 켜는 조건 = d<0.25 ∧ \|Δψ\|<0.3 |
| termination | −5 | 종료 1회에 정확히 −5 |
- 부모에서 뺀 항: track_lin_vel_xy, track_ang_vel_z, stand_still_cmd
- 쓰지 않는 항(부모와 같음): foot_forbidden_surface, foot_support_landing, track_roll_cmd, base_height_low_v4b, mech_work_abs, flat_orientation_l2, alive_bonus
- 가중치 근거:
  - 에피소드당 양의 보상 상한 ≈ 70(부모는 추종 45 + 높이 10).
  - AME-2 의 비율(위치 100 / heading 50 / move 5)을 줄여 썼고, 그대로 복사하지 않았다. AME-2 창 4·2 s 는 예산 4–8 s 에 맞춰 2·1 s 로 줄였다.
  - move 1.0 은 처음부터 학습할 때 탐색을 돕는 항이다(Rudin 2022 bias 항 취지).
- 없는 것: 정체 종료, 정체 벌점.

## 4. 그대로 둔 것 (부모 lla-20261007-s1 과 같음)
- **지형:** 40열 × 4레벨, 타일 10 m. 열 배치는 flat 12, rough_noise 5, rough_boxes 5, slope_down 4, slope_up 4, stairs_up 4, stairs_down 4, curb 2 = 30/25/20/10/10/5%. 레벨별 치수는 spec.LEVEL_PLAN 에 있다. 시작은 L1, 그 밖의 설정은 spec·asset_try4.json 을 따른다.
- **로봇·물리:** sim dt 0.005, decimation 4(제어 0.02 s), 에피소드 20 s.
- **무작위화:**
  - 몸통 질량 +U[−1,3] kg
  - 마찰 U[max(0.4, 타일 μ_min), 1.2], 0.0125 격자, reset 마다 새로 뽑음
  - push 10 s 마다 ±0.5 m/s
  - 관절 초기값 scale 1.0, 속도 0
- **종료:** pit_fall(첫 항), time_out, base_contact, bad_orientation(1.0 rad).
- **커리큘럼:** 승급 진척 ≥ 0.8, 강등 < 0.3 또는 낙상·금지 접촉. 최고 레벨에서 승급하면 IsaacLab 기본 무작위 재배정.
  - 진척 정의 - 계단·턱: 참조선 진척 / ref_len(= 끝발판 목표 거리). 평지류: 끝까지 살아남은 general 목표의 Σ(d0−d_end)/Σd0, Σd0 ≥ 1.0 m 일 때만 적격.
- **PPO(rsl_rl 3.1.2):**
  - num_steps_per_env 24, epochs 5, mini_batches 4
  - lr 1e-3 adaptive, desired_kl 0.01
  - γ 0.99, λ 0.95, clip 0.2, entropy 0.01
  - value_loss_coef 1.0, clipped value loss, max_grad_norm 1.0
- **부모 뒤 ft1(10-07)에서 들어와 goal1 에도 남은 변경** (부모 s1 코드에는 없음):
  - 계단·턱 도착 latch: ARRIVE_EDGE_M 4.5, ARRIVE_MARGIN_M 0.5, update_arrival, edge guard, arrived_gen 적격
  - 강등 사유 기록 demote_reasons, calf/other 접촉 분리 기록 - 기록만, 판정 불변
  - 마찰을 reset 마다 재샘플
  - 원물: `goal1-20261007/goal1_vs_parent.diff`

## 5. 학습 예산·실행
- 단일 첫 run `goal1r3-20261007-s1`: seed 1, 4096 env, 3000 it, save_interval 100, resume 없음(무작위 초기화).
- 기존 ft(500 it 미세조정)와 다른 처음부터의 전체 학습이다.
- 예상 ≈ 3 h. R1 이 4096 env 에서 3.6 s/it 였던 것에서 나온 추정이고, 실측은 시작 증거에 적는다.
- checkpoint 31개 ≈ 0.42 GB. 볼륨 여유 입력값 12 GB 는 추정치다.
- 실패해도 자동 재시도·seed 변경·연장은 없다.

## 6. 판정 계약 (학습 시작 전 동결)
**A. 학습 보조 로그 `goal_{cls}_survend_*`**
- 예산이 만료될 때까지 살아남은 목표의 끝 시점 위치오차(d<0.5, +|Δψ|<0.5)만 센다.
- 낙상·타임아웃으로 잘린 목표는 분모에 없고, 안정·접촉 조건도 없다. **이것으로 안전 도달 통과율을 주장하지 않는다.**

**B. 신규 목표도달 평가 `spec.EVAL_GOAL`**
- ARRIVE_M 0.5, STABLE_S 1.0, V_XY 0.15 m/s, W_Z 0.3 rad/s, TILT 0.5 rad, H_RATIO 0.75, FEET_MIN 3, CONTACT_N 1.0 N, STOP_DRIFT_M 0.25, HEAD_PSI 0.5
- 분모는 평가에서 낸 모든 목표다. 목표마다 아래 중 **하나만** 배정해 직접 센다(뺄셈 금지).
  1. fall: 구간 안 비시간 종료
  2. cut_timeout: 구간 끝 전 time_out
  3. contact: 금지 몸 접촉 > 1 N
  4. safe_reach: 첫 도착 t_arr ≤ 예산−1 s 이고, 그 뒤 1 s 동안 매 step 다음을 지킴 - d<0.5, \|v_xy\|≤0.15, \|ω_z\|≤0.3, 기울기≤0.5 rad, 지형 기준 몸높이 ≥ 0.75·h_cmd, 접지 발 ≥ 3
  5. reach_unstable: 도착했지만 4 의 창 조건 실패
  6. not_reached: 그 밖
- stop: 구간 내내 d<0.25, 마지막 1 s 는 위 속도·자세 조건.
- turn: 끝에서 \|Δψ\|<0.5, 구간 내내 d<0.5, 마지막 1 s 는 위 조건.
- heading 성공은 safe_reach 중 창 끝에서 \|Δψ\|<0.5 인 것만 따로 센다.
- **「첫 도착 직후 1 s 안정」은 엄격한 제안 기준이다.** 학습 뒤 평가에서 부적합하다고 드러나도 이번 run 의 판정을 소급해 고치지 않는다. 고친 기준은 새 이름으로 따로 보고한다.

**C. 회귀 판정**
- 부모 s1 model_2999 와 같은 표에서 비교한다: rough, 계단 up/down, stop, 저속. B 와 별도 열이다.

## 7. 확인 결과
- **로컬 CPU:**
  - test_goal 29/29
  - static_check 9/9
  - test_policy_runner 22/22
  - test_policy_runner_fake rc 0
- **Pod smoke:**
  - smoke1(r1): 재샘플 카운터 셈 버그로 FAIL. IsaacLab command_counter 가 reset 때 0 이 되기 때문이다.
  - smoke2(r2): OK(timed_resamples 148, reset_resample_once True).
  - smoke3(r3): OK - 정지·회전 목표 오차 0.0(n 10, 상자 밖 출발 0 → 경계 cheb 4.1 은 CPU 검사로 확인), timed_resamples 148, 10 it 512 env 정상(model_9 sha256 492ae220…).
- **toy 수익(γ 1.0, 6 s 구간):**
  - 1.5 m 목표: 정지 3.077 · 직진 도착 20.937 · ±0.2 m 왕복 5.840 · 절반 7.900
  - 저속 cap 0.25: 0.25 m/s 22.969 > 1.0 m/s 21.620
  - 가까운 목표 0.8 m 도착 뒤: 정지 20.937 > 반경 안 왕복 20.638(차이 작음. 관절속도 0 을 가정해 정지 벌점을 과소평가한 값이고, 평가 B 의 V_XY 창이 이 경우를 잡는다)
- **남은 위험:**
  - 저속 cap 여유가 작다.
  - γ 0.99 의 지평(약 2 s)이 2 s 위치창과 겹친다.
  - 처음부터 학습이 수렴하는지는 미검증이다.
  - 정체 종료가 없다.
  - 볼륨 여유는 추정치다.

## 8. 파일 sha256 (r3, 앞 16자)
| 파일 | sha256[:16] |
|---|---|
| foothold_lla/spec.py | 386c1dcadb2225b0 |
| foothold_lla/core.py | a68c95c7f034abae |
| foothold_lla/env_cfg.py | cbb492a42a8ffb7f |
| foothold_lla/agent_cfg.py | 5046c49e601c486e |
| foothold_lla/policy.py | 315c98cd62c6cdfd |
| foothold_lla/terrain_meshes.py | 31e193665b64181b |
| foothold_lla/__init__.py | 37fbde0edb1f851d |
| foothold_lla/runner_hooks.py | a80f307770abeca6 |
| scripts/train.py | 1cc65daf121ec57e |
| scripts/launch_goal.sh | 20a927c4e49d1014 |
| scripts/preflight.py | 67b96a3bf36ca5b5 |
| scripts/terrain_audit.py | c98b5526693b90bb |
| s0/asset_try4.json | c869bf9788800e31 |

## 9. 시작 증거 (2026-10-07 17:06 KST 실측)
- run `goal1r3-20261007-s1`, launcher 시작 08:04:25 UTC (17:04 KST), train 08:04:42 UTC 시작
- 프로세스 train.py PID <가림> (GPU 7851 MiB), 다른 GPU 프로세스는 PID <가림> 1개뿐
- metrics.jsonl it 0→14 (08:06:16 UTC), 18 줄 (08:06:30 UTC). 4.04 s/it → 남은 시간 ≈ 3.35 h(추정)
- manifest.json 08:05:14 UTC 생성: resume None · checks.no_resume True · init random · seed 1 · num_envs 4096 · max_iterations 3000 · save_interval 100 · version env-v0.1.2+goal1r3 · task Foothold-Go2-Goal1-Teacher-v0 · asset sha c869bf97…
- manifest source_sha256 의 spec·core·env_cfg·agent_cfg·train 값 = 8 절 표와 같음
- 원본 보존: R1 eval_only.log 「끝 - OK」, 부모 model_2999.pt·R1 videos 그대로, 아무것도 지우지 않음
