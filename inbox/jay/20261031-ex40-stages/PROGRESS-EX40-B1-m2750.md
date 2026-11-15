# EX-40 B1 m2750 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-11-01
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

## 핵심

- 미달 칸: back0.5(정답 생존 64, 오차 0.151)
- 앞 저장본 대비 생존 변화(±3 초과): eval_gt/diag-back+side+ 61→51, eval_gt/diag-back+side- 64→59, eval_gt/diag-fwd+side- 64→58, eval_gt/side-0.5 64→60, probe_prop_only/diag-back+side+ 62→52, probe_prop_only/diag-back+side- 64→58, probe_prop_only/diag-fwd+side- 64→55, eval_pred/diag-back+side+ 59→51, eval_pred/diag-fwd+side- 61→57
- 서 있기: 네 발 동시 접촉 64/64, 가장 약한 발 RR_foot 0.21 mg (RR 0.21)
- 좌우 회전 오차 0.079/0.087 (차 +0.008, +면 오른쪽이 약함)

- 완료: m2750, 학습 기록 2026-10-31T23:47:35.706851+09:00, 점수 2026-11-01T00:13:20.647454+09:00
- 경과 19.55 h, 최근 25.07 s/update, 예상 끝 2026-11-02T12:21:25.316023+09:00
- 단계 B1, 그림자 판정 HOLD, 앞 저장본 m2500
- 학습 보상 45.4432, 에피소드 길이 992.45

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.398, walk_left 0.052, walk_right 0.050, spin_left 0.099, spin_right 0.102, stand 0.102, reverse 0.099, side_left 0.041, side_right 0.055
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.1388086241386975; 실제 표본: base_com_offset_m -0.0069021862000226974~0.006922570522874594 (n=216), actuator_gains 0.9861265420913696~1.0138683319091797 (n=1728), motor_strength_multiplier 0.9864159226417542~1.0135431289672852 (n=72), motor_effort_limit 23.180774688720703~46.045265197753906 (n=864), motor_saturation_effort 23.180774688720703~46.045265197753906 (n=864), push_velocity_delta -0.13661789894104004~0.13524343073368073 (n=462)

## 평가 칸 × 지도 3모드 (그림자 판정 대상은 단계에서 배운 칸)

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 64 | 0.043 | 0.035 | 0.072 | 1.058 (64) |
| eval_gt/fwd1.0 | 64 | 0.069 | 0.040 | 0.072 | 1.042 (64) |
| eval_gt/spin+1.2 | 64 | 0.030 | 0.036 | 0.079 | 0.535 (64) |
| eval_gt/spin-1.2 | 64 | 0.066 | 0.039 | 0.087 | 0.519 (64) |
| eval_gt/stop | 64 | 0.019 | 0.016 | 0.067 | 0.415 (64) |
| eval_gt/back0.5 | 64 | 0.151 | 0.032 | 0.076 | 1.063 (64) |
| eval_gt/back1.0 | 56 | 0.208 | 0.059 | 0.095 | 1.575 (64) |
| eval_gt/diag-back+side+ | 51 | 0.100 | 0.164 | 0.103 | 1.575 (64) |
| eval_gt/diag-back+side- | 59 | 0.141 | 0.162 | 0.120 | 1.460 (64) |
| eval_gt/diag-fwd+side+ | 61 | 0.074 | 0.079 | 0.106 | 1.573 (64) |
| eval_gt/diag-fwd+side- | 58 | 0.068 | 0.090 | 0.092 | 1.542 (64) |
| eval_gt/side+0.5 | 62 | 0.040 | 0.131 | 0.104 | 1.300 (64) |
| eval_gt/side-0.5 | 60 | 0.043 | 0.120 | 0.103 | 1.235 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 63 | 0.046 | 0.039 | 0.075 | 1.111 (64) |
| probe_prop_only/fwd1.0 | 63 | 0.070 | 0.040 | 0.075 | 1.112 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.030 | 0.035 | 0.079 | 0.532 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.061 | 0.041 | 0.088 | 0.529 (64) |
| probe_prop_only/stop | 64 | 0.020 | 0.017 | 0.067 | 0.425 (64) |
| probe_prop_only/back0.5 | 64 | 0.141 | 0.034 | 0.077 | 1.082 (64) |
| probe_prop_only/back1.0 | 58 | 0.185 | 0.070 | 0.103 | 1.569 (64) |
| probe_prop_only/diag-back+side+ | 52 | 0.088 | 0.132 | 0.113 | 1.527 (64) |
| probe_prop_only/diag-back+side- | 58 | 0.116 | 0.155 | 0.109 | 1.438 (64) |
| probe_prop_only/diag-fwd+side+ | 60 | 0.082 | 0.074 | 0.114 | 1.732 (64) |
| probe_prop_only/diag-fwd+side- | 55 | 0.068 | 0.088 | 0.089 | 1.536 (64) |
| probe_prop_only/side+0.5 | 62 | 0.048 | 0.127 | 0.107 | 1.319 (64) |
| probe_prop_only/side-0.5 | 61 | 0.046 | 0.117 | 0.096 | 1.248 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.045 | 0.034 | 0.072 | 1.069 (64) |
| eval_pred/fwd1.0 | 63 | 0.069 | 0.040 | 0.072 | 1.074 (64) |
| eval_pred/spin+1.2 | 64 | 0.030 | 0.036 | 0.079 | 0.538 (64) |
| eval_pred/spin-1.2 | 64 | 0.068 | 0.039 | 0.087 | 0.525 (64) |
| eval_pred/stop | 64 | 0.019 | 0.016 | 0.067 | 0.418 (64) |
| eval_pred/back0.5 | 63 | 0.150 | 0.034 | 0.078 | 1.038 (64) |
| eval_pred/back1.0 | 57 | 0.211 | 0.059 | 0.095 | 1.547 (64) |
| eval_pred/diag-back+side+ | 51 | 0.104 | 0.159 | 0.107 | 1.562 (64) |
| eval_pred/diag-back+side- | 58 | 0.139 | 0.164 | 0.118 | 1.422 (64) |
| eval_pred/diag-fwd+side+ | 61 | 0.074 | 0.077 | 0.105 | 1.633 (64) |
| eval_pred/diag-fwd+side- | 57 | 0.062 | 0.089 | 0.092 | 1.518 (64) |
| eval_pred/side+0.5 | 61 | 0.043 | 0.131 | 0.104 | 1.303 (64) |
| eval_pred/side-0.5 | 61 | 0.044 | 0.112 | 0.103 | 1.216 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.302 | 1.60 |
| eval_gt/FR_foot | 1.000 | 0.268 | 1.28 |
| eval_gt/RL_foot | 1.000 | 0.218 | 0.90 |
| eval_gt/RR_foot | 1.000 | 0.207 | 1.59 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.335 | 1.58 |
| probe_prop_only/FR_foot | 1.000 | 0.236 | 1.25 |
| probe_prop_only/RL_foot | 1.000 | 0.202 | 0.88 |
| probe_prop_only/RR_foot | 1.000 | 0.221 | 1.57 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.303 | 1.60 |
| eval_pred/FR_foot | 1.000 | 0.267 | 1.27 |
| eval_pred/RL_foot | 1.000 | 0.218 | 0.90 |
| eval_pred/RR_foot | 1.000 | 0.208 | 1.58 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- eval_gt/diag-back+side+: 61→51 (-10/64)
- eval_gt/diag-back+side-: 64→59 (-5/64)
- eval_gt/diag-fwd+side-: 64→58 (-6/64)
- eval_gt/side-0.5: 64→60 (-4/64)
- probe_prop_only/diag-back+side+: 62→52 (-10/64)
- probe_prop_only/diag-back+side-: 64→58 (-6/64)
- probe_prop_only/diag-fwd+side-: 64→55 (-9/64)
- eval_pred/diag-back+side+: 59→51 (-8/64)
- eval_pred/diag-fwd+side-: 61→57 (-4/64)
- eval_gt 회전 좌/우 생존 64/64/64; 요속도 오차 0.079/0.087 rad/s.
- probe_prop_only 회전 좌/우 생존 64/64/64; 요속도 오차 0.079/0.088 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.079/0.087 rad/s.
- 전진 yaw 누적: 미측 (이 평가 NPZ에 yaw 시계열 없음).

## 출처

- 저장본 SHA256 `9a7b236cb115fe31ff2cc80df1c3ef714cde2b473486676e863568b2590ba012`
- 점수 SHA256 `3d2a66f0c4c895939cef9d0a14b1da86184cb9ed9ffbb7d9664b8293acee6f18`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_2750_9a7b236cb115\map64\map_modes.json`
