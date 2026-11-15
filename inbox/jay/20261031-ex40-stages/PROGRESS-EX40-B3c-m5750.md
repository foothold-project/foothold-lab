# EX-40 B3c m5750 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-11-01
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

## 핵심

- 미달 칸: back1.0(정답 생존 62, 오차 0.170), back1.0(끔 생존 64, 오차 0.155)
- 앞 저장본 대비 생존 변화(±3 초과): eval_pred/diag-back+side+ 58→63, eval_pred/side+0.5 60→64
- 서 있기: 네 발 동시 접촉 64/64, 가장 약한 발 RR_foot 0.20 mg (RR 0.20)
- 좌우 회전 오차 0.085/0.088 (차 +0.003, +면 오른쪽이 약함)

- 완료: m5750, 학습 기록 2026-11-01T21:22:46.126986+09:00, 점수 2026-11-01T22:06:55.763152+09:00
- 경과 41.14 h, 최근 25.66 s/update, 예상 끝 2026-11-02T13:24:54.669235+09:00
- 단계 B3c, 그림자 판정 HOLD, 앞 저장본 m5500
- 판정 이유: FAIL eval_gt/back1.0: vx_abs_error_mean_alive_mps_above_tracking_limit · FAIL probe_prop_only/back1.0: vx_abs_error_mean_alive_mps_above_tracking_limit · HOLD evidence: invalid evaluation evidence: FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\AI-WS01\\s2_lab\\ex40_main_20261031_041313\\score-watch-b\\model_5750_66703482678c\\axis_v2\\axis_v2.json' · HOLD evaluation_child: evaluation_failed_or_completion_receipt_missing: RuntimeError: EX-40 W57 phase failed with rc=1
- 학습 보상 46.4367, 에피소드 길이 985.13

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.297, walk_left 0.057, walk_right 0.082, spin_left 0.096, spin_right 0.082, stand 0.088, reverse 0.116, side_left 0.062, side_right 0.057, diag_fwd_left 0.014, diag_fwd_right 0.020, diag_back_left 0.014, diag_back_right 0.014
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.472216048010669; 실제 표본: base_com_offset_m -0.023422593250870705~0.0234073456376791 (n=192), actuator_gains 0.952843189239502~1.0472133159637451 (n=1536), motor_strength_multiplier 0.9537835121154785~1.0461264848709106 (n=64), motor_effort_limit 22.413911819458008~47.52552795410156 (n=768), motor_saturation_effort 22.413911819458008~47.52552795410156 (n=768), push_velocity_delta -0.4686301648616791~0.44472816586494446 (n=384)

## 평가 칸 × 지도 3모드 (그림자 판정 대상은 단계에서 배운 칸)

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 64 | 0.044 | 0.031 | 0.072 | 1.000 (64) |
| eval_gt/fwd1.0 | 63 | 0.072 | 0.036 | 0.072 | 1.049 (64) |
| eval_gt/spin+1.2 | 64 | 0.030 | 0.032 | 0.085 | 0.546 (64) |
| eval_gt/spin-1.2 | 64 | 0.069 | 0.037 | 0.088 | 0.499 (64) |
| eval_gt/stop | 64 | 0.016 | 0.014 | 0.065 | 0.468 (64) |
| eval_gt/back0.5 | 64 | 0.116 | 0.031 | 0.081 | 1.001 (64) |
| eval_gt/back1.0 | 62 | 0.170 | 0.039 | 0.090 | 1.275 (64) |
| eval_gt/diag-back+side+ | 64 | 0.078 | 0.089 | 0.117 | 1.402 (64) |
| eval_gt/diag-back+side- | 64 | 0.100 | 0.119 | 0.087 | 1.324 (64) |
| eval_gt/diag-fwd+side+ | 64 | 0.053 | 0.081 | 0.086 | 1.301 (64) |
| eval_gt/diag-fwd+side- | 64 | 0.054 | 0.117 | 0.081 | 1.190 (64) |
| eval_gt/side+0.5 | 64 | 0.042 | 0.099 | 0.091 | 1.183 (64) |
| eval_gt/side-0.5 | 64 | 0.041 | 0.132 | 0.081 | 1.064 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 64 | 0.047 | 0.033 | 0.076 | 1.022 (64) |
| probe_prop_only/fwd1.0 | 64 | 0.075 | 0.037 | 0.075 | 1.061 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.028 | 0.035 | 0.085 | 0.555 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.065 | 0.040 | 0.089 | 0.497 (64) |
| probe_prop_only/stop | 64 | 0.016 | 0.015 | 0.065 | 0.468 (64) |
| probe_prop_only/back0.5 | 64 | 0.111 | 0.032 | 0.081 | 1.014 (64) |
| probe_prop_only/back1.0 | 64 | 0.155 | 0.043 | 0.089 | 1.280 (64) |
| probe_prop_only/diag-back+side+ | 64 | 0.076 | 0.079 | 0.113 | 1.438 (64) |
| probe_prop_only/diag-back+side- | 63 | 0.093 | 0.121 | 0.093 | 1.369 (64) |
| probe_prop_only/diag-fwd+side+ | 63 | 0.055 | 0.069 | 0.087 | 1.278 (64) |
| probe_prop_only/diag-fwd+side- | 64 | 0.056 | 0.108 | 0.080 | 1.216 (64) |
| probe_prop_only/side+0.5 | 64 | 0.046 | 0.084 | 0.091 | 1.176 (64) |
| probe_prop_only/side-0.5 | 64 | 0.045 | 0.128 | 0.083 | 1.051 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.045 | 0.031 | 0.074 | 1.014 (64) |
| eval_pred/fwd1.0 | 63 | 0.071 | 0.036 | 0.072 | 1.046 (64) |
| eval_pred/spin+1.2 | 64 | 0.029 | 0.034 | 0.085 | 0.548 (64) |
| eval_pred/spin-1.2 | 64 | 0.069 | 0.038 | 0.087 | 0.498 (64) |
| eval_pred/stop | 64 | 0.016 | 0.014 | 0.065 | 0.469 (64) |
| eval_pred/back0.5 | 64 | 0.112 | 0.032 | 0.082 | 1.003 (64) |
| eval_pred/back1.0 | 61 | 0.161 | 0.042 | 0.092 | 1.265 (64) |
| eval_pred/diag-back+side+ | 63 | 0.079 | 0.083 | 0.115 | 1.458 (64) |
| eval_pred/diag-back+side- | 64 | 0.097 | 0.118 | 0.094 | 1.349 (64) |
| eval_pred/diag-fwd+side+ | 64 | 0.053 | 0.083 | 0.086 | 1.309 (64) |
| eval_pred/diag-fwd+side- | 64 | 0.057 | 0.107 | 0.080 | 1.196 (64) |
| eval_pred/side+0.5 | 64 | 0.042 | 0.096 | 0.093 | 1.174 (64) |
| eval_pred/side-0.5 | 64 | 0.042 | 0.132 | 0.083 | 1.057 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.272 | 1.56 |
| eval_gt/FR_foot | 1.000 | 0.304 | 1.32 |
| eval_gt/RL_foot | 1.000 | 0.215 | 1.13 |
| eval_gt/RR_foot | 1.000 | 0.202 | 1.55 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.271 | 1.56 |
| probe_prop_only/FR_foot | 1.000 | 0.308 | 1.33 |
| probe_prop_only/RL_foot | 1.000 | 0.207 | 1.06 |
| probe_prop_only/RR_foot | 1.000 | 0.208 | 1.55 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.267 | 1.59 |
| eval_pred/FR_foot | 1.000 | 0.303 | 1.36 |
| eval_pred/RL_foot | 1.000 | 0.219 | 1.17 |
| eval_pred/RR_foot | 1.000 | 0.205 | 1.52 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- eval_pred/diag-back+side+: 58→63 (+5/64)
- eval_pred/side+0.5: 60→64 (+4/64)
- eval_gt 회전 좌/우 생존 64/64/64; 요속도 오차 0.085/0.088 rad/s.
- probe_prop_only 회전 좌/우 생존 64/64/64; 요속도 오차 0.085/0.089 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.085/0.087 rad/s.
- 전진 yaw 누적(정답 지도, m5250 측정): 0.5 m/s -0.11° · 1.0 m/s 1.57°

## 출처

- 저장본 SHA256 `66703482678c3f61ea4b215995d4157504fc02c28e2ed71bf239f1300e598cf9`
- 점수 SHA256 `5d1ecb4ab7e554c3e7471c56a120038711a82ef00b309826f4dc14f706162279`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_5750_66703482678c\map64\map_modes.json`
