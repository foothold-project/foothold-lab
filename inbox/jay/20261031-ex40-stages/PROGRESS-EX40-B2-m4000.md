# EX-40 B2 m4000 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-11-01
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

## 핵심

- 미달 칸: diag-back+side-(끔 생존 63, 오차 0.160)
- 앞 저장본 대비 생존 변화(±3 초과): eval_gt/diag-fwd+side+ 60→64
- 서 있기: 네 발 동시 접촉 64/64, 가장 약한 발 RR_foot 0.19 mg (RR 0.19)
- 좌우 회전 오차 0.079/0.091 (차 +0.012, +면 오른쪽이 약함)

- 완료: m4000, 학습 기록 2026-11-01T08:44:05.533879+09:00, 점수 2026-11-01T09:11:05.389915+09:00
- 경과 28.49 h, 최근 25.01 s/update, 예상 끝 2026-11-02T12:31:06.811459+09:00
- 단계 B2, 그림자 판정 HOLD, 앞 저장본 m3750
- 판정 이유: FAIL probe_prop_only/diag-back+side-: vy_abs_error_mean_alive_mps_above_tracking_limit · HOLD evidence: invalid evaluation evidence: FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\AI-WS01\\s2_lab\\ex40_main_20261031_041313\\score-watch-b\\model_4000_5103db13eac8\\axis_v2\\axis_v2.json' · HOLD evaluation_child: evaluation_failed_or_completion_receipt_missing: RuntimeError: EX-40 W57 phase failed with rc=1
- 학습 보상 45.7984, 에피소드 길이 1000.00

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.283, walk_left 0.035, walk_right 0.051, spin_left 0.088, spin_right 0.120, stand 0.115, reverse 0.128, side_left 0.067, side_right 0.061, diag_fwd_left 0.016, diag_fwd_right 0.013, diag_back_left 0.013, diag_back_right 0.008
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.2777283840853523; 실제 표본: base_com_offset_m -0.013617416843771935~0.01351359486579895 (n=216), actuator_gains 0.9722538590431213~1.0277533531188965 (n=1728), motor_strength_multiplier 0.9723018407821655~1.0260565280914307 (n=72), motor_effort_limit 22.849092483520508~46.613746643066406 (n=864), motor_saturation_effort 22.849092483520508~46.613746643066406 (n=864), push_velocity_delta -0.27128952741622925~0.27543413639068604 (n=426)

## 평가 칸 × 지도 3모드 (그림자 판정 대상은 단계에서 배운 칸)

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 64 | 0.045 | 0.034 | 0.073 | 1.013 (64) |
| eval_gt/fwd1.0 | 64 | 0.072 | 0.033 | 0.074 | 1.038 (64) |
| eval_gt/spin+1.2 | 64 | 0.037 | 0.027 | 0.079 | 0.514 (64) |
| eval_gt/spin-1.2 | 64 | 0.053 | 0.037 | 0.091 | 0.523 (64) |
| eval_gt/stop | 64 | 0.018 | 0.014 | 0.061 | 0.454 (64) |
| eval_gt/back0.5 | 64 | 0.099 | 0.028 | 0.078 | 1.007 (64) |
| eval_gt/back1.0 | 63 | 0.135 | 0.039 | 0.085 | 1.335 (64) |
| eval_gt/diag-back+side+ | 63 | 0.101 | 0.086 | 0.100 | 1.421 (64) |
| eval_gt/diag-back+side- | 62 | 0.121 | 0.140 | 0.085 | 1.397 (64) |
| eval_gt/diag-fwd+side+ | 64 | 0.059 | 0.126 | 0.081 | 1.210 (64) |
| eval_gt/diag-fwd+side- | 64 | 0.055 | 0.065 | 0.085 | 1.304 (64) |
| eval_gt/side+0.5 | 64 | 0.069 | 0.105 | 0.091 | 1.190 (64) |
| eval_gt/side-0.5 | 64 | 0.055 | 0.095 | 0.089 | 1.233 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 64 | 0.045 | 0.035 | 0.073 | 1.037 (64) |
| probe_prop_only/fwd1.0 | 64 | 0.072 | 0.036 | 0.077 | 1.056 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.038 | 0.026 | 0.079 | 0.514 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.050 | 0.040 | 0.093 | 0.521 (64) |
| probe_prop_only/stop | 64 | 0.020 | 0.014 | 0.062 | 0.453 (64) |
| probe_prop_only/back0.5 | 64 | 0.090 | 0.029 | 0.081 | 1.081 (64) |
| probe_prop_only/back1.0 | 64 | 0.104 | 0.045 | 0.090 | 1.357 (64) |
| probe_prop_only/diag-back+side+ | 63 | 0.079 | 0.078 | 0.099 | 1.445 (64) |
| probe_prop_only/diag-back+side- | 63 | 0.131 | 0.160 | 0.083 | 1.418 (64) |
| probe_prop_only/diag-fwd+side+ | 64 | 0.061 | 0.121 | 0.081 | 1.225 (64) |
| probe_prop_only/diag-fwd+side- | 63 | 0.060 | 0.070 | 0.085 | 1.323 (64) |
| probe_prop_only/side+0.5 | 64 | 0.064 | 0.095 | 0.096 | 1.207 (64) |
| probe_prop_only/side-0.5 | 64 | 0.058 | 0.110 | 0.084 | 1.222 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.045 | 0.034 | 0.074 | 1.014 (64) |
| eval_pred/fwd1.0 | 64 | 0.073 | 0.033 | 0.075 | 1.037 (64) |
| eval_pred/spin+1.2 | 64 | 0.038 | 0.026 | 0.079 | 0.514 (64) |
| eval_pred/spin-1.2 | 64 | 0.053 | 0.039 | 0.092 | 0.519 (64) |
| eval_pred/stop | 64 | 0.018 | 0.014 | 0.062 | 0.453 (64) |
| eval_pred/back0.5 | 64 | 0.112 | 0.028 | 0.077 | 1.032 (64) |
| eval_pred/back1.0 | 62 | 0.145 | 0.042 | 0.087 | 1.315 (64) |
| eval_pred/diag-back+side+ | 63 | 0.093 | 0.083 | 0.100 | 1.447 (64) |
| eval_pred/diag-back+side- | 64 | 0.133 | 0.145 | 0.086 | 1.414 (64) |
| eval_pred/diag-fwd+side+ | 64 | 0.058 | 0.125 | 0.083 | 1.215 (64) |
| eval_pred/diag-fwd+side- | 64 | 0.057 | 0.066 | 0.084 | 1.286 (64) |
| eval_pred/side+0.5 | 64 | 0.067 | 0.100 | 0.093 | 1.200 (64) |
| eval_pred/side-0.5 | 63 | 0.055 | 0.103 | 0.090 | 1.257 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.228 | 1.65 |
| eval_gt/FR_foot | 1.000 | 0.305 | 1.35 |
| eval_gt/RL_foot | 1.000 | 0.272 | 1.42 |
| eval_gt/RR_foot | 1.000 | 0.192 | 1.63 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.230 | 1.67 |
| probe_prop_only/FR_foot | 1.000 | 0.302 | 1.38 |
| probe_prop_only/RL_foot | 1.000 | 0.282 | 1.44 |
| probe_prop_only/RR_foot | 1.000 | 0.189 | 1.64 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.228 | 1.67 |
| eval_pred/FR_foot | 1.000 | 0.305 | 1.35 |
| eval_pred/RL_foot | 1.000 | 0.271 | 1.42 |
| eval_pred/RR_foot | 1.000 | 0.192 | 1.62 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- eval_gt/diag-fwd+side+: 60→64 (+4/64)
- eval_gt 회전 좌/우 생존 64/64/64; 요속도 오차 0.079/0.091 rad/s.
- probe_prop_only 회전 좌/우 생존 64/64/64; 요속도 오차 0.079/0.093 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.079/0.092 rad/s.
- 전진 yaw 누적(정답 지도, m3750 측정): 0.5 m/s -6.02° · 1.0 m/s -7.14°

## 출처

- 저장본 SHA256 `5103db13eac8c48b827850b6d0f71044702603af61dd0735a78951cadab9e4e7`
- 점수 SHA256 `ff0d56bf2264d02d0c9abd92a7ab796fd8a49140a8fc8dc7ab3567baa175cde0`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_4000_5103db13eac8\map64\map_modes.json`
