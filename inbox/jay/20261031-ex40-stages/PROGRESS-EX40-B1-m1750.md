# EX-40 B1 m1750 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-10-31
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

- 완료: m1750, 학습 기록 2026-10-31T16:40:21.955723+09:00, 점수 2026-10-31T17:07:40.038412+09:00
- 경과 12.43 h, 최근 25.17 s/update, 예상 끝 2026-11-02T12:22:18.318879+09:00
- 단계 B1, 그림자 판정 HOLD, 앞 저장본 m1500
- 학습 보상 40.9627, 에피소드 길이 992.28

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.414, walk_left 0.051, walk_right 0.041, spin_left 0.105, spin_right 0.118, stand 0.093, reverse 0.075, side_left 0.051, side_right 0.051
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.027672816181373638; 실제 표본: base_com_offset_m -0.0013574399054050446~0.001368773402646184 (n=198), actuator_gains 0.9972327947616577~1.002764344215393 (n=1584), motor_strength_multiplier 0.997383177280426~1.00263512134552 (n=66), motor_effort_limit 23.438505172729492~45.549713134765625 (n=792), motor_saturation_effort 23.438505172729492~45.549713134765625 (n=792), push_velocity_delta -0.027230827137827873~0.02748006209731102 (n=438)

## 평가 6칸 × 지도 3모드

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 64 | 0.052 | 0.032 | 0.073 | 1.108 (64) |
| eval_gt/fwd1.0 | 63 | 0.081 | 0.038 | 0.075 | 1.152 (64) |
| eval_gt/spin+1.2 | 64 | 0.040 | 0.047 | 0.103 | 0.607 (64) |
| eval_gt/spin-1.2 | 64 | 0.032 | 0.038 | 0.100 | 0.619 (64) |
| eval_gt/stop | 64 | 0.021 | 0.022 | 0.066 | 0.523 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 64 | 0.051 | 0.032 | 0.074 | 1.154 (64) |
| probe_prop_only/fwd1.0 | 63 | 0.086 | 0.039 | 0.078 | 1.192 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.046 | 0.045 | 0.106 | 0.615 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.036 | 0.038 | 0.101 | 0.589 (64) |
| probe_prop_only/stop | 64 | 0.021 | 0.023 | 0.067 | 0.514 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.053 | 0.032 | 0.075 | 1.128 (64) |
| eval_pred/fwd1.0 | 64 | 0.084 | 0.037 | 0.076 | 1.169 (64) |
| eval_pred/spin+1.2 | 64 | 0.039 | 0.045 | 0.103 | 0.607 (64) |
| eval_pred/spin-1.2 | 64 | 0.034 | 0.039 | 0.099 | 0.637 (64) |
| eval_pred/stop | 64 | 0.021 | 0.022 | 0.066 | 0.524 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.167 | 1.68 |
| eval_gt/FR_foot | 1.000 | 0.387 | 1.35 |
| eval_gt/RL_foot | 1.000 | 0.320 | 1.05 |
| eval_gt/RR_foot | 1.000 | 0.118 | 1.40 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.179 | 1.72 |
| probe_prop_only/FR_foot | 1.000 | 0.390 | 1.29 |
| probe_prop_only/RL_foot | 1.000 | 0.328 | 1.00 |
| probe_prop_only/RR_foot | 1.000 | 0.093 | 1.32 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.170 | 1.68 |
| eval_pred/FR_foot | 1.000 | 0.382 | 1.35 |
| eval_pred/RL_foot | 1.000 | 0.313 | 1.04 |
| eval_pred/RR_foot | 1.000 | 0.124 | 1.40 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- 생존 차이 ±3/64를 넘는 칸 없음. 이 범위는 차이 없음으로 표시한다.
- eval_gt 회전 좌/우 생존 64/64/64; 요속도 오차 0.103/0.100 rad/s.
- probe_prop_only 회전 좌/우 생존 64/64/64; 요속도 오차 0.106/0.101 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.103/0.099 rad/s.
- 전진 yaw 누적: 미측 (이 평가 NPZ에 yaw 시계열 없음).

## 출처

- 저장본 SHA256 `651a9e64e7e651fc86e292c640edbeb4ad8936577f9beff868d2856af1a722ed`
- 점수 SHA256 `cfbb2ecf47e4fc7156191b0ef3b4dc261962346f76edb8b40d1bef48e47773a9`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_1750_651a9e64e7e6\map64\map_modes.json`
