# EX-40 B2 m3500 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-11-01
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

## 핵심

- 미달 칸: back1.0(정답 생존 61, 오차 0.185), diag-back+side-(정답 생존 63, 오차 0.176), back1.0(끔 생존 63, 오차 0.152), diag-back+side-(끔 생존 64, 오차 0.179)
- 앞 저장본 대비 생존 변화(±3 초과): 없음
- 서 있기: 네 발 동시 접촉 64/64, 가장 약한 발 RL_foot 0.19 mg (RR 0.22)
- 좌우 회전 오차 0.092/0.090 (차 -0.001, +면 오른쪽이 약함)

- 완료: m3500, 학습 기록 2026-11-01T05:10:53.225657+09:00, 점수 2026-11-01T05:37:29.841940+09:00
- 경과 24.94 h, 최근 24.99 s/update, 예상 끝 2026-11-02T12:25:17.334053+09:00
- 단계 B2, 그림자 판정 HOLD, 앞 저장본 m3250
- 판정 이유: FAIL eval_gt/back1.0: vx_abs_error_mean_alive_mps_above_tracking_limit · FAIL eval_gt/diag-back+side-: vy_abs_error_mean_alive_mps_above_tracking_limit · FAIL probe_prop_only/back1.0: vx_abs_error_mean_alive_mps_above_tracking_limit · FAIL probe_prop_only/diag-back+side-: vy_abs_error_mean_alive_mps_above_tracking_limit · HOLD evidence: invalid evaluation evidence: FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\AI-WS01\\s2_lab\\ex40_main_20261031_041313\\score-watch-b\\model_3500_fa32414a417f\\axis_v2\\axis_v2.json' · HOLD evaluation_child: evaluation_failed_or_completion_receipt_missing: RuntimeError: EX-40 W57 phase failed with rc=1
- 학습 보상 45.2439, 에피소드 길이 994.81

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.330, walk_left 0.066, walk_right 0.055, spin_left 0.102, spin_right 0.094, stand 0.069, reverse 0.100, side_left 0.066, side_right 0.047, diag_fwd_left 0.028, diag_fwd_right 0.011, diag_back_left 0.014, diag_back_right 0.017
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.22216048010669037; 실제 표본: base_com_offset_m -0.010944860056042671~0.011024655774235725 (n=231), actuator_gains 0.9777860641479492~1.0221593379974365 (n=1848), motor_strength_multiplier 0.9788640737533569~1.0215214490890503 (n=77), motor_effort_limit 23.003305435180664~46.407718658447266 (n=924), motor_saturation_effort 23.003305435180664~46.407718658447266 (n=924), push_velocity_delta -0.22011779248714447~0.21910716593265533 (n=378)

## 평가 칸 × 지도 3모드 (그림자 판정 대상은 단계에서 배운 칸)

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 64 | 0.049 | 0.034 | 0.075 | 1.035 (64) |
| eval_gt/fwd1.0 | 64 | 0.070 | 0.034 | 0.076 | 1.058 (64) |
| eval_gt/spin+1.2 | 64 | 0.037 | 0.031 | 0.092 | 0.541 (64) |
| eval_gt/spin-1.2 | 64 | 0.053 | 0.039 | 0.090 | 0.513 (64) |
| eval_gt/stop | 64 | 0.016 | 0.015 | 0.062 | 0.438 (64) |
| eval_gt/back0.5 | 64 | 0.121 | 0.034 | 0.079 | 1.026 (64) |
| eval_gt/back1.0 | 61 | 0.185 | 0.045 | 0.087 | 1.444 (64) |
| eval_gt/diag-back+side+ | 61 | 0.076 | 0.108 | 0.093 | 1.418 (64) |
| eval_gt/diag-back+side- | 63 | 0.087 | 0.176 | 0.087 | 1.399 (64) |
| eval_gt/diag-fwd+side+ | 64 | 0.057 | 0.075 | 0.091 | 1.282 (64) |
| eval_gt/diag-fwd+side- | 64 | 0.060 | 0.122 | 0.085 | 1.275 (64) |
| eval_gt/side+0.5 | 64 | 0.059 | 0.098 | 0.096 | 1.263 (64) |
| eval_gt/side-0.5 | 64 | 0.043 | 0.123 | 0.083 | 1.154 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 64 | 0.047 | 0.036 | 0.074 | 1.068 (64) |
| probe_prop_only/fwd1.0 | 64 | 0.072 | 0.037 | 0.076 | 1.092 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.038 | 0.031 | 0.092 | 0.540 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.054 | 0.040 | 0.089 | 0.517 (64) |
| probe_prop_only/stop | 64 | 0.018 | 0.016 | 0.061 | 0.442 (64) |
| probe_prop_only/back0.5 | 63 | 0.096 | 0.035 | 0.080 | 1.080 (64) |
| probe_prop_only/back1.0 | 63 | 0.152 | 0.048 | 0.091 | 1.469 (64) |
| probe_prop_only/diag-back+side+ | 62 | 0.072 | 0.082 | 0.095 | 1.446 (64) |
| probe_prop_only/diag-back+side- | 64 | 0.083 | 0.179 | 0.090 | 1.408 (64) |
| probe_prop_only/diag-fwd+side+ | 64 | 0.061 | 0.068 | 0.089 | 1.318 (64) |
| probe_prop_only/diag-fwd+side- | 64 | 0.063 | 0.127 | 0.084 | 1.295 (64) |
| probe_prop_only/side+0.5 | 64 | 0.065 | 0.077 | 0.094 | 1.287 (64) |
| probe_prop_only/side-0.5 | 63 | 0.040 | 0.118 | 0.083 | 1.177 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.048 | 0.035 | 0.075 | 1.046 (64) |
| eval_pred/fwd1.0 | 64 | 0.070 | 0.032 | 0.076 | 1.057 (64) |
| eval_pred/spin+1.2 | 64 | 0.039 | 0.031 | 0.092 | 0.542 (64) |
| eval_pred/spin-1.2 | 64 | 0.053 | 0.039 | 0.091 | 0.516 (64) |
| eval_pred/stop | 64 | 0.016 | 0.016 | 0.063 | 0.439 (64) |
| eval_pred/back0.5 | 63 | 0.121 | 0.036 | 0.079 | 1.009 (64) |
| eval_pred/back1.0 | 63 | 0.191 | 0.045 | 0.088 | 1.479 (64) |
| eval_pred/diag-back+side+ | 60 | 0.081 | 0.110 | 0.095 | 1.442 (64) |
| eval_pred/diag-back+side- | 62 | 0.092 | 0.180 | 0.089 | 1.399 (64) |
| eval_pred/diag-fwd+side+ | 63 | 0.059 | 0.072 | 0.092 | 1.298 (64) |
| eval_pred/diag-fwd+side- | 63 | 0.063 | 0.126 | 0.088 | 1.291 (64) |
| eval_pred/side+0.5 | 63 | 0.062 | 0.097 | 0.102 | 1.242 (64) |
| eval_pred/side-0.5 | 64 | 0.043 | 0.120 | 0.084 | 1.172 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.345 | 1.51 |
| eval_gt/FR_foot | 1.000 | 0.250 | 1.22 |
| eval_gt/RL_foot | 1.000 | 0.190 | 0.89 |
| eval_gt/RR_foot | 1.000 | 0.215 | 1.58 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.356 | 1.50 |
| probe_prop_only/FR_foot | 1.000 | 0.243 | 1.20 |
| probe_prop_only/RL_foot | 1.000 | 0.182 | 0.87 |
| probe_prop_only/RR_foot | 1.000 | 0.219 | 1.57 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.339 | 1.51 |
| eval_pred/FR_foot | 1.000 | 0.256 | 1.23 |
| eval_pred/RL_foot | 1.000 | 0.192 | 0.91 |
| eval_pred/RR_foot | 1.000 | 0.213 | 1.57 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- 생존 차이 ±3/64를 넘는 칸 없음. 이 범위는 차이 없음으로 표시한다.
- eval_gt 회전 좌/우 생존 64/64/64; 요속도 오차 0.092/0.090 rad/s.
- probe_prop_only 회전 좌/우 생존 64/64/64; 요속도 오차 0.092/0.089 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.092/0.091 rad/s.
- 전진 yaw 누적(정답 지도, m3250 측정): 0.5 m/s 1.84° · 1.0 m/s 3.99°

## 출처

- 저장본 SHA256 `fa32414a417f5948a300b903482ffd83e2d15ed47f13fa68373c98e99b1474a3`
- 점수 SHA256 `fe74a5fa109bee2530756e6287f6e212ac08c4980a00cd10c16c7793de0cc525`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_3500_fa32414a417f\map64\map_modes.json`
