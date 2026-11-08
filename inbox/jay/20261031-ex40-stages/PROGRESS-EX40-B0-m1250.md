# EX-40 B0 m1250 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-10-31
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

- 완료: m1250, 학습 기록 2026-10-31T13:04:00.799153+09:00, 점수 2026-10-31T15:09:05.134235+09:00
- 경과 8.83 h, 최근 25.22 s/update, 예상 끝 2026-11-02T12:21:03.259611+09:00
- 단계 B0, 그림자 판정 PASS, 앞 저장본 m1000
- 학습 보상 43.4049, 에피소드 길이 990.31

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.691, spin_left 0.100, spin_right 0.090, stand 0.120
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.0; 실제 표본: base_com_offset_m 0.0~0.0 (n=225), actuator_gains 1.0~1.0 (n=1800), motor_strength_multiplier 1.0~1.0 (n=75), motor_effort_limit 23.5~45.43000030517578 (n=900), motor_saturation_effort 23.5~45.43000030517578 (n=900), push_velocity_delta 0.0~0.0 (n=456)

## 평가 6칸 × 지도 3모드

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 64 | 0.052 | 0.039 | 0.070 | 1.153 (64) |
| eval_gt/fwd1.0 | 64 | 0.075 | 0.034 | 0.071 | 1.121 (64) |
| eval_gt/spin+1.2 | 64 | 0.046 | 0.037 | 0.106 | 0.631 (64) |
| eval_gt/spin-1.2 | 64 | 0.061 | 0.034 | 0.091 | 0.691 (64) |
| eval_gt/stop | 64 | 0.024 | 0.022 | 0.072 | 0.550 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 64 | 0.054 | 0.040 | 0.071 | 1.156 (64) |
| probe_prop_only/fwd1.0 | 64 | 0.074 | 0.036 | 0.072 | 1.131 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.051 | 0.035 | 0.108 | 0.625 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.053 | 0.035 | 0.090 | 0.688 (64) |
| probe_prop_only/stop | 64 | 0.023 | 0.023 | 0.072 | 0.559 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.053 | 0.039 | 0.070 | 1.156 (64) |
| eval_pred/fwd1.0 | 64 | 0.076 | 0.036 | 0.072 | 1.128 (64) |
| eval_pred/spin+1.2 | 64 | 0.046 | 0.037 | 0.112 | 0.645 (64) |
| eval_pred/spin-1.2 | 64 | 0.062 | 0.033 | 0.091 | 0.698 (64) |
| eval_pred/stop | 64 | 0.024 | 0.023 | 0.073 | 0.552 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.254 | 1.79 |
| eval_gt/FR_foot | 1.000 | 0.234 | 1.47 |
| eval_gt/RL_foot | 1.000 | 0.244 | 1.09 |
| eval_gt/RR_foot | 1.000 | 0.270 | 1.67 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.265 | 1.78 |
| probe_prop_only/FR_foot | 1.000 | 0.225 | 1.43 |
| probe_prop_only/RL_foot | 1.000 | 0.238 | 1.08 |
| probe_prop_only/RR_foot | 1.000 | 0.273 | 1.68 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.256 | 1.78 |
| eval_pred/FR_foot | 1.000 | 0.233 | 1.46 |
| eval_pred/RL_foot | 1.000 | 0.241 | 1.08 |
| eval_pred/RR_foot | 1.000 | 0.274 | 1.67 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- eval_gt/spin-1.2: 60→64 (+4/64)
- eval_pred/spin-1.2: 60→64 (+4/64)
- eval_gt 회전 좌/우 생존 64/64/64; 요속도 오차 0.106/0.091 rad/s.
- probe_prop_only 회전 좌/우 생존 64/64/64; 요속도 오차 0.108/0.090 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.112/0.091 rad/s.
- 전진 yaw 누적: 미측 (이 평가 NPZ에 yaw 시계열 없음).

## 출처

- 저장본 SHA256 `728d8517f973692f43459545ae20483cfe5b5c3ce67424094e00c7c0045a4e5e`
- 점수 SHA256 `5efc6dc6888be8a20710ac106eb22f72dfae4dda188127156c45069b3897468a`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_1250_728d8517f973\map64\map_modes.json`
