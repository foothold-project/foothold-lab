# EX-40 B2 m4250 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-11-01
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

## 핵심

- 미달 칸: 없음 (생존 ≥60 · 오차 ≤0.15)
- 앞 저장본 대비 생존 변화(±3 초과): 없음
- 서 있기: 네 발 동시 접촉 64/64, 가장 약한 발 RL_foot 0.21 mg (RR 0.22)
- 좌우 회전 오차 0.087/0.090 (차 +0.003, +면 오른쪽이 약함)

- 완료: m4250, 학습 기록 2026-11-01T10:30:48.837481+09:00, 점수 2026-11-01T10:55:15.475271+09:00
- 경과 30.27 h, 최근 24.97 s/update, 예상 끝 2026-11-02T12:31:44.713009+09:00
- 단계 B2, 그림자 판정 HOLD, 앞 저장본 m4000
- 판정 이유: HOLD evidence: invalid evaluation evidence: FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\AI-WS01\\s2_lab\\ex40_main_20261031_041313\\score-watch-b\\model_4250_4c0f5aac3954\\axis_v2\\axis_v2.json' · HOLD evaluation_child: evaluation_failed_or_completion_receipt_missing: RuntimeError: EX-40 W57 phase failed with rc=1
- 학습 보상 46.6193, 에피소드 길이 988.13

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.284, walk_left 0.057, walk_right 0.054, spin_left 0.111, spin_right 0.114, stand 0.089, reverse 0.108, side_left 0.046, side_right 0.062, diag_fwd_left 0.014, diag_fwd_right 0.032, diag_back_left 0.016, diag_back_right 0.014
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.30551233607468326; 실제 표본: base_com_offset_m -0.014971542172133923~0.015252606943249702 (n=189), actuator_gains 0.9695871472358704~1.0305500030517578 (n=1512), motor_strength_multiplier 0.9697537422180176~1.0270463228225708 (n=63), motor_effort_limit 22.789213180541992~46.658714294433594 (n=756), motor_saturation_effort 22.789213180541992~46.658714294433594 (n=756), push_velocity_delta -0.3006148934364319~0.30253639817237854 (n=348)

## 평가 칸 × 지도 3모드 (그림자 판정 대상은 단계에서 배운 칸)

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 64 | 0.044 | 0.035 | 0.075 | 0.973 (64) |
| eval_gt/fwd1.0 | 64 | 0.067 | 0.039 | 0.072 | 1.030 (64) |
| eval_gt/spin+1.2 | 64 | 0.051 | 0.037 | 0.087 | 0.558 (64) |
| eval_gt/spin-1.2 | 64 | 0.029 | 0.029 | 0.090 | 0.479 (64) |
| eval_gt/stop | 64 | 0.015 | 0.015 | 0.059 | 0.404 (64) |
| eval_gt/back0.5 | 64 | 0.101 | 0.036 | 0.079 | 1.015 (64) |
| eval_gt/back1.0 | 64 | 0.121 | 0.049 | 0.085 | 1.299 (64) |
| eval_gt/diag-back+side+ | 64 | 0.086 | 0.079 | 0.088 | 1.381 (64) |
| eval_gt/diag-back+side- | 64 | 0.110 | 0.121 | 0.083 | 1.369 (64) |
| eval_gt/diag-fwd+side+ | 64 | 0.049 | 0.075 | 0.082 | 1.184 (64) |
| eval_gt/diag-fwd+side- | 63 | 0.058 | 0.083 | 0.081 | 1.290 (64) |
| eval_gt/side+0.5 | 64 | 0.046 | 0.085 | 0.088 | 1.193 (64) |
| eval_gt/side-0.5 | 64 | 0.048 | 0.107 | 0.085 | 1.113 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 64 | 0.045 | 0.036 | 0.077 | 1.001 (64) |
| probe_prop_only/fwd1.0 | 64 | 0.068 | 0.043 | 0.075 | 1.111 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.061 | 0.035 | 0.086 | 0.563 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.030 | 0.031 | 0.090 | 0.479 (64) |
| probe_prop_only/stop | 64 | 0.016 | 0.015 | 0.059 | 0.404 (64) |
| probe_prop_only/back0.5 | 64 | 0.100 | 0.039 | 0.079 | 1.010 (64) |
| probe_prop_only/back1.0 | 63 | 0.108 | 0.055 | 0.085 | 1.348 (64) |
| probe_prop_only/diag-back+side+ | 63 | 0.087 | 0.078 | 0.088 | 1.349 (64) |
| probe_prop_only/diag-back+side- | 64 | 0.112 | 0.111 | 0.088 | 1.402 (64) |
| probe_prop_only/diag-fwd+side+ | 62 | 0.050 | 0.080 | 0.085 | 1.273 (64) |
| probe_prop_only/diag-fwd+side- | 64 | 0.052 | 0.092 | 0.086 | 1.310 (64) |
| probe_prop_only/side+0.5 | 62 | 0.043 | 0.091 | 0.088 | 1.195 (64) |
| probe_prop_only/side-0.5 | 64 | 0.048 | 0.105 | 0.090 | 1.128 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.045 | 0.035 | 0.076 | 0.986 (64) |
| eval_pred/fwd1.0 | 64 | 0.067 | 0.040 | 0.072 | 1.034 (64) |
| eval_pred/spin+1.2 | 64 | 0.053 | 0.037 | 0.087 | 0.559 (64) |
| eval_pred/spin-1.2 | 64 | 0.030 | 0.029 | 0.090 | 0.484 (64) |
| eval_pred/stop | 64 | 0.015 | 0.015 | 0.059 | 0.401 (64) |
| eval_pred/back0.5 | 64 | 0.102 | 0.036 | 0.080 | 1.019 (64) |
| eval_pred/back1.0 | 64 | 0.113 | 0.048 | 0.085 | 1.329 (64) |
| eval_pred/diag-back+side+ | 62 | 0.091 | 0.077 | 0.089 | 1.402 (64) |
| eval_pred/diag-back+side- | 64 | 0.105 | 0.115 | 0.089 | 1.387 (64) |
| eval_pred/diag-fwd+side+ | 64 | 0.051 | 0.077 | 0.083 | 1.185 (64) |
| eval_pred/diag-fwd+side- | 63 | 0.056 | 0.082 | 0.083 | 1.282 (64) |
| eval_pred/side+0.5 | 63 | 0.047 | 0.088 | 0.088 | 1.208 (64) |
| eval_pred/side-0.5 | 64 | 0.048 | 0.106 | 0.087 | 1.131 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.285 | 1.65 |
| eval_gt/FR_foot | 1.000 | 0.279 | 1.21 |
| eval_gt/RL_foot | 1.000 | 0.214 | 1.04 |
| eval_gt/RR_foot | 1.000 | 0.220 | 1.63 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.288 | 1.64 |
| probe_prop_only/FR_foot | 1.000 | 0.286 | 1.17 |
| probe_prop_only/RL_foot | 1.000 | 0.204 | 0.99 |
| probe_prop_only/RR_foot | 1.000 | 0.220 | 1.58 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.288 | 1.64 |
| eval_pred/FR_foot | 1.000 | 0.279 | 1.21 |
| eval_pred/RL_foot | 1.000 | 0.213 | 1.03 |
| eval_pred/RR_foot | 1.000 | 0.221 | 1.64 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- 생존 차이 ±3/64를 넘는 칸 없음. 이 범위는 차이 없음으로 표시한다.
- eval_gt 회전 좌/우 생존 64/64/64; 요속도 오차 0.087/0.090 rad/s.
- probe_prop_only 회전 좌/우 생존 64/64/64; 요속도 오차 0.086/0.090 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.087/0.090 rad/s.
- 전진 yaw 누적(정답 지도, m4000 측정): 0.5 m/s 3.0° · 1.0 m/s 8.23°

## 출처

- 저장본 SHA256 `4c0f5aac39542ca1900ed3cf22b1fae889935a9b4a58527275c2b9d4f33a0a7f`
- 점수 SHA256 `ee99c2bdfd3427fd71b29ad7e12d3962fd14ce26e51125f77ed41072eceb26cd`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_4250_4c0f5aac3954\map64\map_modes.json`
