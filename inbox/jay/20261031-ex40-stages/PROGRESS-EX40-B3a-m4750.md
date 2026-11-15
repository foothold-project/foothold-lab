# EX-40 B3a m4750 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-11-01
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

## 핵심

- 미달 칸: 없음 (생존 ≥60 · 오차 ≤0.15)
- 앞 저장본 대비 생존 변화(±3 초과): 없음
- 서 있기: 네 발 동시 접촉 64/64, 가장 약한 발 RL_foot 0.23 mg (RR 0.23)
- 좌우 회전 오차 0.093/0.091 (차 -0.001, +면 오른쪽이 약함)

- 완료: m4750, 학습 기록 2026-11-01T14:06:37.552908+09:00, 점수 2026-11-01T14:36:02.600841+09:00
- 경과 33.87 h, 최근 25.60 s/update, 예상 끝 2026-11-02T13:13:28.122500+09:00
- 단계 B3a, 그림자 판정 HOLD, 앞 저장본 m4500
- 판정 이유: HOLD evidence: invalid evaluation evidence: FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\AI-WS01\\s2_lab\\ex40_main_20261031_041313\\score-watch-b\\model_4750_314ea3dabc35\\axis_v2\\axis_v2.json' · HOLD evaluation_child: evaluation_failed_or_completion_receipt_missing: RuntimeError: EX-40 W57 phase failed with rc=1
- 학습 보상 46.1794, 에피소드 길이 990.69

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.216, walk_left 0.060, walk_right 0.077, spin_left 0.105, spin_right 0.111, stand 0.128, reverse 0.122, side_left 0.048, side_right 0.065, diag_fwd_left 0.023, diag_fwd_right 0.017, diag_back_left 0.020, diag_back_right 0.009
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.3610802400533452; 실제 표본: base_com_offset_m -0.018016615882515907~0.018045533448457718 (n=180), actuator_gains 0.9639062285423279~1.0360721349716187 (n=1440), motor_strength_multiplier 0.9641075730323792~1.0359981060028076 (n=60), motor_effort_limit 22.65652847290039~47.06539535522461 (n=720), motor_saturation_effort 22.65652847290039~47.06539535522461 (n=720), push_velocity_delta -0.3600504398345947~0.35671550035476685 (n=366)

## 평가 칸 × 지도 3모드 (그림자 판정 대상은 단계에서 배운 칸)

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 64 | 0.045 | 0.031 | 0.079 | 0.975 (64) |
| eval_gt/fwd1.0 | 64 | 0.077 | 0.040 | 0.092 | 1.055 (64) |
| eval_gt/spin+1.2 | 64 | 0.044 | 0.047 | 0.093 | 0.526 (64) |
| eval_gt/spin-1.2 | 64 | 0.036 | 0.033 | 0.091 | 0.463 (64) |
| eval_gt/stop | 64 | 0.015 | 0.016 | 0.067 | 0.399 (64) |
| eval_gt/back0.5 | 64 | 0.082 | 0.033 | 0.098 | 1.115 (64) |
| eval_gt/back1.0 | 63 | 0.102 | 0.059 | 0.103 | 1.425 (64) |
| eval_gt/diag-back+side+ | 64 | 0.088 | 0.091 | 0.106 | 1.503 (64) |
| eval_gt/diag-back+side- | 64 | 0.056 | 0.081 | 0.123 | 1.431 (64) |
| eval_gt/diag-fwd+side+ | 64 | 0.059 | 0.061 | 0.093 | 1.283 (64) |
| eval_gt/diag-fwd+side- | 64 | 0.049 | 0.081 | 0.081 | 1.285 (64) |
| eval_gt/side+0.5 | 64 | 0.064 | 0.084 | 0.101 | 1.312 (64) |
| eval_gt/side-0.5 | 64 | 0.035 | 0.066 | 0.103 | 1.195 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 63 | 0.048 | 0.032 | 0.081 | 1.043 (64) |
| probe_prop_only/fwd1.0 | 61 | 0.082 | 0.044 | 0.096 | 1.142 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.050 | 0.052 | 0.091 | 0.527 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.040 | 0.032 | 0.092 | 0.469 (64) |
| probe_prop_only/stop | 64 | 0.015 | 0.015 | 0.066 | 0.394 (64) |
| probe_prop_only/back0.5 | 64 | 0.102 | 0.032 | 0.097 | 1.089 (64) |
| probe_prop_only/back1.0 | 64 | 0.119 | 0.053 | 0.105 | 1.377 (64) |
| probe_prop_only/diag-back+side+ | 63 | 0.101 | 0.079 | 0.105 | 1.499 (64) |
| probe_prop_only/diag-back+side- | 64 | 0.063 | 0.080 | 0.122 | 1.478 (64) |
| probe_prop_only/diag-fwd+side+ | 62 | 0.060 | 0.061 | 0.090 | 1.291 (64) |
| probe_prop_only/diag-fwd+side- | 64 | 0.051 | 0.081 | 0.083 | 1.304 (64) |
| probe_prop_only/side+0.5 | 64 | 0.072 | 0.081 | 0.099 | 1.314 (64) |
| probe_prop_only/side-0.5 | 63 | 0.037 | 0.070 | 0.102 | 1.185 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.047 | 0.031 | 0.079 | 0.982 (64) |
| eval_pred/fwd1.0 | 64 | 0.078 | 0.040 | 0.094 | 1.065 (64) |
| eval_pred/spin+1.2 | 64 | 0.043 | 0.049 | 0.092 | 0.530 (64) |
| eval_pred/spin-1.2 | 64 | 0.037 | 0.032 | 0.091 | 0.468 (64) |
| eval_pred/stop | 64 | 0.015 | 0.016 | 0.067 | 0.400 (64) |
| eval_pred/back0.5 | 64 | 0.091 | 0.032 | 0.098 | 1.117 (64) |
| eval_pred/back1.0 | 62 | 0.107 | 0.059 | 0.103 | 1.445 (64) |
| eval_pred/diag-back+side+ | 64 | 0.094 | 0.092 | 0.106 | 1.488 (64) |
| eval_pred/diag-back+side- | 64 | 0.059 | 0.085 | 0.126 | 1.447 (64) |
| eval_pred/diag-fwd+side+ | 64 | 0.060 | 0.061 | 0.094 | 1.287 (64) |
| eval_pred/diag-fwd+side- | 64 | 0.051 | 0.079 | 0.083 | 1.284 (64) |
| eval_pred/side+0.5 | 63 | 0.066 | 0.082 | 0.100 | 1.347 (64) |
| eval_pred/side-0.5 | 64 | 0.036 | 0.069 | 0.106 | 1.232 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.298 | 1.68 |
| eval_gt/FR_foot | 1.000 | 0.250 | 1.23 |
| eval_gt/RL_foot | 1.000 | 0.227 | 1.28 |
| eval_gt/RR_foot | 1.000 | 0.228 | 1.58 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.296 | 1.67 |
| probe_prop_only/FR_foot | 1.000 | 0.260 | 1.21 |
| probe_prop_only/RL_foot | 1.000 | 0.210 | 1.18 |
| probe_prop_only/RR_foot | 1.000 | 0.233 | 1.57 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.299 | 1.68 |
| eval_pred/FR_foot | 1.000 | 0.250 | 1.23 |
| eval_pred/RL_foot | 1.000 | 0.224 | 1.27 |
| eval_pred/RR_foot | 1.000 | 0.227 | 1.54 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- 생존 차이 ±3/64를 넘는 칸 없음. 이 범위는 차이 없음으로 표시한다.
- eval_gt 회전 좌/우 생존 64/64/64; 요속도 오차 0.093/0.091 rad/s.
- probe_prop_only 회전 좌/우 생존 64/64/64; 요속도 오차 0.091/0.092 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.092/0.091 rad/s.
- 전진 yaw 누적(정답 지도, m4250 측정): 0.5 m/s 1.01° · 1.0 m/s 7.14°

## 출처

- 저장본 SHA256 `314ea3dabc35bbe4033f9d32255957a421a732399447c2a60784bb916824d5f2`
- 점수 SHA256 `36254ff7474f982d0c7945ca3aaadae7aa3c23a892d3a42cf8a3da0c714abd25`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_4750_314ea3dabc35\map64\map_modes.json`
