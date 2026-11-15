# EX-40 B2 m3750 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-11-01
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

## 핵심

- 미달 칸: diag-back+side-(정답 생존 61, 오차 0.157), diag-back+side-(끔 생존 62, 오차 0.152)
- 앞 저장본 대비 생존 변화(±3 초과): eval_gt/diag-fwd+side+ 64→60
- 서 있기: 네 발 동시 접촉 64/64, 가장 약한 발 RL_foot 0.20 mg (RR 0.22)
- 좌우 회전 오차 0.092/0.088 (차 -0.004, +면 오른쪽이 약함)

- 완료: m3750, 학습 기록 2026-11-01T06:57:28.834982+09:00, 점수 2026-11-01T07:21:49.705202+09:00
- 경과 26.72 h, 최근 24.89 s/update, 예상 끝 2026-11-02T12:20:50.560613+09:00
- 단계 B2, 그림자 판정 HOLD, 앞 저장본 m3500
- 판정 이유: FAIL eval_gt/diag-back+side-: vy_abs_error_mean_alive_mps_above_tracking_limit · FAIL probe_prop_only/diag-back+side-: vy_abs_error_mean_alive_mps_above_tracking_limit · HOLD evidence: invalid evaluation evidence: FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\AI-WS01\\s2_lab\\ex40_main_20261031_041313\\score-watch-b\\model_3750_4d396e17122a\\axis_v2\\axis_v2.json' · HOLD evaluation_child: evaluation_failed_or_completion_receipt_missing: RuntimeError: EX-40 W57 phase failed with rc=1
- 학습 보상 44.7971, 에피소드 길이 1000.00

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.315, walk_left 0.040, walk_right 0.048, spin_left 0.085, spin_right 0.104, stand 0.107, reverse 0.120, side_left 0.075, side_right 0.059, diag_fwd_left 0.013, diag_fwd_right 0.013, diag_back_left 0.011, diag_back_right 0.011
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.24994443209602135; 실제 표본: base_com_offset_m -0.012397103942930698~0.01245022565126419 (n=243), actuator_gains 0.9750206470489502~1.0249918699264526 (n=1944), motor_strength_multiplier 0.9752891063690186~1.0247762203216553 (n=81), motor_effort_limit 22.919294357299805~46.55558395385742 (n=972), motor_saturation_effort 22.919294357299805~46.55558395385742 (n=972), push_velocity_delta -0.24991795420646667~0.2498861700296402 (n=426)

## 평가 칸 × 지도 3모드 (그림자 판정 대상은 단계에서 배운 칸)

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 64 | 0.049 | 0.033 | 0.072 | 0.988 (64) |
| eval_gt/fwd1.0 | 64 | 0.079 | 0.035 | 0.072 | 1.053 (64) |
| eval_gt/spin+1.2 | 64 | 0.038 | 0.056 | 0.092 | 0.511 (64) |
| eval_gt/spin-1.2 | 64 | 0.036 | 0.036 | 0.088 | 0.518 (64) |
| eval_gt/stop | 64 | 0.018 | 0.016 | 0.067 | 0.411 (64) |
| eval_gt/back0.5 | 64 | 0.083 | 0.032 | 0.079 | 1.243 (64) |
| eval_gt/back1.0 | 63 | 0.099 | 0.047 | 0.084 | 1.505 (64) |
| eval_gt/diag-back+side+ | 63 | 0.084 | 0.078 | 0.097 | 1.515 (64) |
| eval_gt/diag-back+side- | 61 | 0.072 | 0.157 | 0.097 | 1.524 (64) |
| eval_gt/diag-fwd+side+ | 60 | 0.056 | 0.077 | 0.098 | 1.310 (64) |
| eval_gt/diag-fwd+side- | 64 | 0.064 | 0.078 | 0.089 | 1.418 (64) |
| eval_gt/side+0.5 | 63 | 0.061 | 0.106 | 0.087 | 1.235 (64) |
| eval_gt/side-0.5 | 62 | 0.051 | 0.116 | 0.095 | 1.220 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 61 | 0.046 | 0.035 | 0.073 | 1.085 (64) |
| probe_prop_only/fwd1.0 | 62 | 0.082 | 0.037 | 0.073 | 1.095 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.043 | 0.057 | 0.094 | 0.514 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.038 | 0.036 | 0.086 | 0.515 (64) |
| probe_prop_only/stop | 64 | 0.018 | 0.015 | 0.066 | 0.415 (64) |
| probe_prop_only/back0.5 | 64 | 0.081 | 0.031 | 0.079 | 1.214 (64) |
| probe_prop_only/back1.0 | 62 | 0.094 | 0.046 | 0.092 | 1.507 (64) |
| probe_prop_only/diag-back+side+ | 63 | 0.090 | 0.069 | 0.100 | 1.505 (64) |
| probe_prop_only/diag-back+side- | 62 | 0.080 | 0.152 | 0.096 | 1.529 (64) |
| probe_prop_only/diag-fwd+side+ | 61 | 0.059 | 0.090 | 0.095 | 1.387 (64) |
| probe_prop_only/diag-fwd+side- | 63 | 0.066 | 0.071 | 0.094 | 1.449 (64) |
| probe_prop_only/side+0.5 | 62 | 0.064 | 0.110 | 0.087 | 1.229 (64) |
| probe_prop_only/side-0.5 | 63 | 0.056 | 0.103 | 0.096 | 1.241 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.048 | 0.032 | 0.073 | 1.008 (64) |
| eval_pred/fwd1.0 | 62 | 0.079 | 0.036 | 0.073 | 1.074 (64) |
| eval_pred/spin+1.2 | 64 | 0.039 | 0.057 | 0.092 | 0.519 (64) |
| eval_pred/spin-1.2 | 64 | 0.036 | 0.035 | 0.086 | 0.523 (64) |
| eval_pred/stop | 64 | 0.018 | 0.015 | 0.067 | 0.411 (64) |
| eval_pred/back0.5 | 64 | 0.090 | 0.034 | 0.080 | 1.245 (64) |
| eval_pred/back1.0 | 62 | 0.106 | 0.046 | 0.088 | 1.512 (64) |
| eval_pred/diag-back+side+ | 60 | 0.085 | 0.074 | 0.100 | 1.537 (64) |
| eval_pred/diag-back+side- | 62 | 0.076 | 0.161 | 0.102 | 1.517 (64) |
| eval_pred/diag-fwd+side+ | 62 | 0.058 | 0.080 | 0.100 | 1.321 (64) |
| eval_pred/diag-fwd+side- | 62 | 0.063 | 0.074 | 0.090 | 1.426 (64) |
| eval_pred/side+0.5 | 63 | 0.062 | 0.106 | 0.091 | 1.253 (64) |
| eval_pred/side-0.5 | 61 | 0.053 | 0.125 | 0.097 | 1.214 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.301 | 1.61 |
| eval_gt/FR_foot | 1.000 | 0.269 | 1.28 |
| eval_gt/RL_foot | 1.000 | 0.204 | 1.05 |
| eval_gt/RR_foot | 1.000 | 0.223 | 1.58 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.300 | 1.58 |
| probe_prop_only/FR_foot | 1.000 | 0.279 | 1.28 |
| probe_prop_only/RL_foot | 1.000 | 0.189 | 1.02 |
| probe_prop_only/RR_foot | 1.000 | 0.229 | 1.54 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.302 | 1.61 |
| eval_pred/FR_foot | 1.000 | 0.271 | 1.28 |
| eval_pred/RL_foot | 1.000 | 0.203 | 1.04 |
| eval_pred/RR_foot | 1.000 | 0.222 | 1.56 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- eval_gt/diag-fwd+side+: 64→60 (-4/64)
- eval_gt 회전 좌/우 생존 64/64/64; 요속도 오차 0.092/0.088 rad/s.
- probe_prop_only 회전 좌/우 생존 64/64/64; 요속도 오차 0.094/0.086 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.092/0.086 rad/s.
- 전진 yaw 누적(정답 지도, m3500 측정): 0.5 m/s 0.51° · 1.0 m/s -1.6°

## 출처

- 저장본 SHA256 `4d396e17122a5b6f1d2f2252841f1aa69aec8292574ac4a1df8ed1f27286da2d`
- 점수 SHA256 `d7b70705ca10a58139c4d13384e6a119d67b396e560fdfc4230386012a25329d`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_3750_4d396e17122a\map64\map_modes.json`
