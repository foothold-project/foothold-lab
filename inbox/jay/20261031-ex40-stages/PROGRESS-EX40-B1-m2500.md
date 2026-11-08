# EX-40 B1 m2500 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-10-31
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

## 핵심

- 미달 칸: 없음 (생존 ≥60 · 오차 ≤0.15)
- 앞 저장본 대비 생존 변화(±3 초과): eval_gt/diag-back+side- 57→64, probe_prop_only/diag-back+side+ 58→62, probe_prop_only/diag-back+side- 59→64, probe_prop_only/side-0.5 58→64, eval_pred/side+0.5 64→59, eval_pred/side-0.5 60→64
- 서 있기: 네 발 동시 접촉 64/64, 가장 약한 발 RR_foot 0.18 mg (RR 0.18)
- 좌우 회전 오차 0.095/0.083 (차 -0.011, +면 오른쪽이 약함)

- 완료: m2500, 학습 기록 2026-10-31T22:00:16.489862+09:00, 점수 2026-10-31T22:27:39.616740+09:00
- 경과 17.76 h, 최근 25.13 s/update, 예상 끝 2026-11-02T12:23:36.860765+09:00
- 단계 B1, 그림자 판정 HOLD, 앞 저장본 m2250
- 학습 보상 44.3831, 에피소드 길이 986.44

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.413, walk_left 0.050, walk_right 0.064, spin_left 0.080, spin_right 0.105, stand 0.078, reverse 0.114, side_left 0.050, side_right 0.047
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.11102467214936652; 실제 표본: base_com_offset_m -0.005532403942197561~0.005527620669454336 (n=228), actuator_gains 0.9889203310012817~1.0110825300216675 (n=1824), motor_strength_multiplier 0.9890590906143188~1.0109297037124634 (n=76), motor_effort_limit 23.242889404296875~45.926536560058594 (n=912), motor_saturation_effort 23.242889404296875~45.926536560058594 (n=912), push_velocity_delta -0.10991793870925903~0.10981512069702148 (n=360)

## 평가 칸 × 지도 3모드 (그림자 판정 대상은 단계에서 배운 칸)

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 64 | 0.047 | 0.028 | 0.071 | 1.077 (64) |
| eval_gt/fwd1.0 | 63 | 0.072 | 0.034 | 0.072 | 1.147 (64) |
| eval_gt/spin+1.2 | 64 | 0.031 | 0.047 | 0.095 | 0.603 (64) |
| eval_gt/spin-1.2 | 64 | 0.058 | 0.036 | 0.083 | 0.576 (64) |
| eval_gt/stop | 64 | 0.016 | 0.018 | 0.064 | 0.533 (64) |
| eval_gt/back0.5 | 63 | 0.143 | 0.031 | 0.078 | 1.122 (64) |
| eval_gt/back1.0 | 57 | 0.170 | 0.058 | 0.093 | 1.676 (64) |
| eval_gt/diag-back+side+ | 61 | 0.062 | 0.188 | 0.099 | 1.527 (64) |
| eval_gt/diag-back+side- | 64 | 0.140 | 0.173 | 0.115 | 1.516 (64) |
| eval_gt/diag-fwd+side+ | 63 | 0.066 | 0.073 | 0.098 | 1.508 (64) |
| eval_gt/diag-fwd+side- | 64 | 0.055 | 0.106 | 0.094 | 1.444 (64) |
| eval_gt/side+0.5 | 64 | 0.044 | 0.115 | 0.102 | 1.421 (64) |
| eval_gt/side-0.5 | 64 | 0.040 | 0.142 | 0.096 | 1.303 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 64 | 0.048 | 0.030 | 0.074 | 1.114 (64) |
| probe_prop_only/fwd1.0 | 63 | 0.075 | 0.038 | 0.076 | 1.172 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.031 | 0.044 | 0.095 | 0.594 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.064 | 0.037 | 0.083 | 0.599 (64) |
| probe_prop_only/stop | 64 | 0.017 | 0.019 | 0.064 | 0.545 (64) |
| probe_prop_only/back0.5 | 63 | 0.121 | 0.033 | 0.080 | 1.173 (64) |
| probe_prop_only/back1.0 | 59 | 0.144 | 0.073 | 0.095 | 1.747 (64) |
| probe_prop_only/diag-back+side+ | 62 | 0.066 | 0.144 | 0.106 | 1.601 (64) |
| probe_prop_only/diag-back+side- | 64 | 0.128 | 0.169 | 0.114 | 1.590 (64) |
| probe_prop_only/diag-fwd+side+ | 60 | 0.075 | 0.081 | 0.105 | 1.660 (64) |
| probe_prop_only/diag-fwd+side- | 64 | 0.060 | 0.102 | 0.092 | 1.498 (64) |
| probe_prop_only/side+0.5 | 61 | 0.051 | 0.089 | 0.095 | 1.499 (64) |
| probe_prop_only/side-0.5 | 64 | 0.045 | 0.139 | 0.094 | 1.300 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 63 | 0.050 | 0.029 | 0.072 | 1.089 (64) |
| eval_pred/fwd1.0 | 64 | 0.072 | 0.035 | 0.072 | 1.107 (64) |
| eval_pred/spin+1.2 | 64 | 0.032 | 0.048 | 0.095 | 0.608 (64) |
| eval_pred/spin-1.2 | 64 | 0.056 | 0.036 | 0.082 | 0.579 (64) |
| eval_pred/stop | 64 | 0.016 | 0.018 | 0.064 | 0.526 (64) |
| eval_pred/back0.5 | 64 | 0.143 | 0.032 | 0.078 | 1.124 (64) |
| eval_pred/back1.0 | 58 | 0.159 | 0.060 | 0.096 | 1.727 (64) |
| eval_pred/diag-back+side+ | 59 | 0.063 | 0.191 | 0.102 | 1.592 (64) |
| eval_pred/diag-back+side- | 61 | 0.130 | 0.160 | 0.115 | 1.534 (64) |
| eval_pred/diag-fwd+side+ | 61 | 0.071 | 0.083 | 0.101 | 1.575 (64) |
| eval_pred/diag-fwd+side- | 61 | 0.056 | 0.103 | 0.096 | 1.493 (64) |
| eval_pred/side+0.5 | 59 | 0.045 | 0.103 | 0.100 | 1.414 (64) |
| eval_pred/side-0.5 | 64 | 0.042 | 0.137 | 0.094 | 1.327 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.279 | 1.68 |
| eval_gt/FR_foot | 1.000 | 0.281 | 1.35 |
| eval_gt/RL_foot | 1.000 | 0.254 | 1.02 |
| eval_gt/RR_foot | 1.000 | 0.184 | 1.73 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.283 | 1.71 |
| probe_prop_only/FR_foot | 1.000 | 0.273 | 1.36 |
| probe_prop_only/RL_foot | 1.000 | 0.269 | 1.07 |
| probe_prop_only/RR_foot | 1.000 | 0.173 | 1.73 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.278 | 1.69 |
| eval_pred/FR_foot | 1.000 | 0.283 | 1.34 |
| eval_pred/RL_foot | 1.000 | 0.255 | 1.01 |
| eval_pred/RR_foot | 1.000 | 0.182 | 1.73 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- eval_gt/diag-back+side-: 57→64 (+7/64)
- probe_prop_only/diag-back+side+: 58→62 (+4/64)
- probe_prop_only/diag-back+side-: 59→64 (+5/64)
- probe_prop_only/side-0.5: 58→64 (+6/64)
- eval_pred/side+0.5: 64→59 (-5/64)
- eval_pred/side-0.5: 60→64 (+4/64)
- eval_gt 회전 좌/우 생존 64/64/64; 요속도 오차 0.095/0.083 rad/s.
- probe_prop_only 회전 좌/우 생존 64/64/64; 요속도 오차 0.095/0.083 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.095/0.082 rad/s.
- 전진 yaw 누적: 미측 (이 평가 NPZ에 yaw 시계열 없음).

## 출처

- 저장본 SHA256 `86a22c3f5f9b8a3fbade6ef46dde8ae543a6491ba55d44e4cf85317c4ed15e1c`
- 점수 SHA256 `d8d63fadd82356f3af7781cb75250af86b467c1c9d4a7d6222f538b6772302ab`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_2500_86a22c3f5f9b\map64\map_modes.json`
