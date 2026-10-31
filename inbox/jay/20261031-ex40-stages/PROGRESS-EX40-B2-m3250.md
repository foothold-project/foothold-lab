# EX-40 B2 m3250 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-11-01
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

## 핵심

- 미달 칸: back1.0(정답 생존 62, 오차 0.187), back1.0(끔 생존 63, 오차 0.173)
- 앞 저장본 대비 생존 변화(±3 초과): probe_prop_only/back1.0 59→63, probe_prop_only/diag-back+side+ 55→63, eval_pred/diag-back+side+ 55→61
- 서 있기: 네 발 동시 접촉 64/64, 가장 약한 발 RL_foot 0.22 mg (RR 0.25)
- 좌우 회전 오차 0.086/0.084 (차 -0.002, +면 오른쪽이 약함)

- 완료: m3250, 학습 기록 2026-11-01T03:24:07.110596+09:00, 점수 2026-11-01T03:48:13.487679+09:00
- 경과 23.16 h, 최근 24.89 s/update, 예상 끝 2026-11-02T12:14:47.832759+09:00
- 단계 B2, 그림자 판정 HOLD, 앞 저장본 m3000
- 판정 이유: FAIL eval_gt/back1.0: vx_abs_error_mean_alive_mps_above_tracking_limit · FAIL probe_prop_only/back1.0: vx_abs_error_mean_alive_mps_above_tracking_limit · HOLD evidence: invalid evaluation evidence: FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\AI-WS01\\s2_lab\\ex40_main_20261031_041313\\score-watch-b\\model_3250_8dc39f16306e\\axis_v2\\axis_v2.json' · HOLD evaluation_child: evaluation_failed_or_completion_receipt_missing: RuntimeError: EX-40 W57 phase failed with rc=1
- 학습 보상 43.9344, 에피소드 길이 986.63

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.290, walk_left 0.070, walk_right 0.038, spin_left 0.080, spin_right 0.121, stand 0.110, reverse 0.107, side_left 0.072, side_right 0.051, diag_fwd_left 0.005, diag_fwd_right 0.016, diag_back_left 0.013, diag_back_right 0.027
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.19437652811735942; 실제 표본: base_com_offset_m -0.009633179754018784~0.009489966556429863 (n=222), actuator_gains 0.9806196093559265~1.0194146633148193 (n=1776), motor_strength_multiplier 0.9822018146514893~1.0181528329849243 (n=74), motor_effort_limit 23.081743240356445~46.25468444824219 (n=888), motor_saturation_effort 23.081743240356445~46.25468444824219 (n=888), push_velocity_delta -0.19433322548866272~0.18385550379753113 (n=408)

## 평가 칸 × 지도 3모드 (그림자 판정 대상은 단계에서 배운 칸)

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 64 | 0.050 | 0.037 | 0.077 | 1.025 (64) |
| eval_gt/fwd1.0 | 64 | 0.075 | 0.041 | 0.074 | 1.028 (64) |
| eval_gt/spin+1.2 | 64 | 0.054 | 0.042 | 0.086 | 0.550 (64) |
| eval_gt/spin-1.2 | 64 | 0.071 | 0.040 | 0.084 | 0.545 (64) |
| eval_gt/stop | 64 | 0.018 | 0.016 | 0.061 | 0.394 (64) |
| eval_gt/back0.5 | 63 | 0.136 | 0.033 | 0.081 | 1.007 (64) |
| eval_gt/back1.0 | 62 | 0.187 | 0.050 | 0.090 | 1.405 (64) |
| eval_gt/diag-back+side+ | 62 | 0.067 | 0.075 | 0.101 | 1.555 (64) |
| eval_gt/diag-back+side- | 63 | 0.086 | 0.122 | 0.091 | 1.345 (64) |
| eval_gt/diag-fwd+side+ | 64 | 0.072 | 0.078 | 0.093 | 1.249 (64) |
| eval_gt/diag-fwd+side- | 64 | 0.074 | 0.089 | 0.088 | 1.329 (64) |
| eval_gt/side+0.5 | 64 | 0.068 | 0.107 | 0.092 | 1.272 (64) |
| eval_gt/side-0.5 | 64 | 0.036 | 0.098 | 0.086 | 1.132 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 64 | 0.051 | 0.036 | 0.080 | 1.030 (64) |
| probe_prop_only/fwd1.0 | 63 | 0.077 | 0.042 | 0.078 | 1.084 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.063 | 0.040 | 0.085 | 0.560 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.073 | 0.045 | 0.085 | 0.557 (64) |
| probe_prop_only/stop | 64 | 0.019 | 0.017 | 0.062 | 0.401 (64) |
| probe_prop_only/back0.5 | 64 | 0.131 | 0.033 | 0.081 | 1.012 (64) |
| probe_prop_only/back1.0 | 63 | 0.173 | 0.048 | 0.099 | 1.442 (64) |
| probe_prop_only/diag-back+side+ | 63 | 0.069 | 0.069 | 0.114 | 1.570 (64) |
| probe_prop_only/diag-back+side- | 63 | 0.092 | 0.109 | 0.091 | 1.345 (64) |
| probe_prop_only/diag-fwd+side+ | 63 | 0.077 | 0.066 | 0.095 | 1.273 (64) |
| probe_prop_only/diag-fwd+side- | 64 | 0.073 | 0.087 | 0.089 | 1.335 (64) |
| probe_prop_only/side+0.5 | 63 | 0.069 | 0.085 | 0.095 | 1.309 (64) |
| probe_prop_only/side-0.5 | 64 | 0.034 | 0.099 | 0.085 | 1.148 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.051 | 0.037 | 0.079 | 1.026 (64) |
| eval_pred/fwd1.0 | 63 | 0.078 | 0.043 | 0.076 | 1.039 (64) |
| eval_pred/spin+1.2 | 64 | 0.051 | 0.044 | 0.087 | 0.550 (64) |
| eval_pred/spin-1.2 | 64 | 0.071 | 0.040 | 0.083 | 0.549 (64) |
| eval_pred/stop | 64 | 0.018 | 0.016 | 0.061 | 0.396 (64) |
| eval_pred/back0.5 | 64 | 0.139 | 0.034 | 0.082 | 1.021 (64) |
| eval_pred/back1.0 | 62 | 0.180 | 0.049 | 0.093 | 1.429 (64) |
| eval_pred/diag-back+side+ | 61 | 0.067 | 0.072 | 0.106 | 1.551 (64) |
| eval_pred/diag-back+side- | 64 | 0.090 | 0.119 | 0.094 | 1.341 (64) |
| eval_pred/diag-fwd+side+ | 64 | 0.072 | 0.076 | 0.090 | 1.249 (64) |
| eval_pred/diag-fwd+side- | 63 | 0.074 | 0.089 | 0.090 | 1.347 (64) |
| eval_pred/side+0.5 | 64 | 0.067 | 0.103 | 0.095 | 1.268 (64) |
| eval_pred/side-0.5 | 64 | 0.036 | 0.104 | 0.087 | 1.150 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.268 | 1.62 |
| eval_gt/FR_foot | 1.000 | 0.263 | 1.42 |
| eval_gt/RL_foot | 1.000 | 0.217 | 1.22 |
| eval_gt/RR_foot | 1.000 | 0.254 | 1.69 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.289 | 1.59 |
| probe_prop_only/FR_foot | 1.000 | 0.248 | 1.38 |
| probe_prop_only/RL_foot | 1.000 | 0.203 | 1.17 |
| probe_prop_only/RR_foot | 1.000 | 0.258 | 1.67 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.266 | 1.61 |
| eval_pred/FR_foot | 1.000 | 0.263 | 1.41 |
| eval_pred/RL_foot | 1.000 | 0.216 | 1.22 |
| eval_pred/RR_foot | 1.000 | 0.253 | 1.70 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- probe_prop_only/back1.0: 59→63 (+4/64)
- probe_prop_only/diag-back+side+: 55→63 (+8/64)
- eval_pred/diag-back+side+: 55→61 (+6/64)
- eval_gt 회전 좌/우 생존 64/64/64; 요속도 오차 0.086/0.084 rad/s.
- probe_prop_only 회전 좌/우 생존 64/64/64; 요속도 오차 0.085/0.085 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.087/0.083 rad/s.
- 전진 yaw 누적(정답 지도, m2750 측정): 0.5 m/s 1.15° · 1.0 m/s 2.53°

## 출처

- 저장본 SHA256 `8dc39f16306ef383c117a181b262d2c8e65eca59ee812eff8c3a41032991e691`
- 점수 SHA256 `9fa2a2cfce665618e7ceefc47cfcad1c011fb2b076e827426d5e36fa6db0b01a`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_3250_8dc39f16306e\map64\map_modes.json`
