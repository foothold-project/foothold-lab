# EX-40 B0 m1000 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-10-31
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

- 완료: m1000, 학습 기록 2026-10-31T11:18:13.566998+09:00, 점수 2026-10-31T14:45:23.162503+09:00
- 경과 7.06 h, 최근 24.85 s/update, 예상 끝 2026-11-02T11:37:25.213097+09:00
- 단계 B0, 그림자 판정 PASS, 앞 저장본 m750
- 학습 보상 43.2150, 에피소드 길이 984.60

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.745, spin_left 0.095, spin_right 0.082, stand 0.079
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.0; 실제 표본: base_com_offset_m 0.0~0.0 (n=210), actuator_gains 1.0~1.0 (n=1680), motor_strength_multiplier 1.0~1.0 (n=70), motor_effort_limit 23.5~45.43000030517578 (n=840), motor_saturation_effort 23.5~45.43000030517578 (n=840), push_velocity_delta 0.0~0.0 (n=348)

## 평가 6칸 × 지도 3모드

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 64 | 0.057 | 0.031 | 0.076 | 1.285 (64) |
| eval_gt/fwd1.0 | 62 | 0.076 | 0.034 | 0.075 | 1.186 (64) |
| eval_gt/spin+1.2 | 64 | 0.046 | 0.033 | 0.114 | 0.774 (64) |
| eval_gt/spin-1.2 | 60 | 0.031 | 0.040 | 0.114 | 0.831 (64) |
| eval_gt/stop | 64 | 0.022 | 0.021 | 0.071 | 0.573 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 64 | 0.058 | 0.033 | 0.076 | 1.300 (64) |
| probe_prop_only/fwd1.0 | 64 | 0.078 | 0.034 | 0.075 | 1.173 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.050 | 0.034 | 0.108 | 0.792 (64) |
| probe_prop_only/spin-1.2 | 61 | 0.031 | 0.041 | 0.109 | 0.806 (64) |
| probe_prop_only/stop | 63 | 0.021 | 0.021 | 0.071 | 0.619 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.057 | 0.032 | 0.077 | 1.287 (64) |
| eval_pred/fwd1.0 | 64 | 0.078 | 0.035 | 0.075 | 1.177 (64) |
| eval_pred/spin+1.2 | 64 | 0.048 | 0.033 | 0.114 | 0.778 (64) |
| eval_pred/spin-1.2 | 60 | 0.033 | 0.041 | 0.116 | 0.843 (64) |
| eval_pred/stop | 64 | 0.022 | 0.021 | 0.071 | 0.589 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.247 | 1.93 |
| eval_gt/FR_foot | 1.000 | 0.199 | 1.67 |
| eval_gt/RL_foot | 1.000 | 0.275 | 0.96 |
| eval_gt/RR_foot | 1.000 | 0.281 | 1.73 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.255 | 1.92 |
| probe_prop_only/FR_foot | 1.000 | 0.178 | 1.69 |
| probe_prop_only/RL_foot | 1.000 | 0.267 | 1.02 |
| probe_prop_only/RR_foot | 1.000 | 0.303 | 1.74 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.247 | 1.93 |
| eval_pred/FR_foot | 1.000 | 0.200 | 1.67 |
| eval_pred/RL_foot | 1.000 | 0.272 | 0.95 |
| eval_pred/RR_foot | 1.000 | 0.284 | 1.72 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- eval_gt/spin-1.2: 64→60 (-4/64)
- eval_pred/spin-1.2: 64→60 (-4/64)
- eval_gt 회전 좌/우 생존 64/60/64; 요속도 오차 0.114/0.114 rad/s.
- probe_prop_only 회전 좌/우 생존 64/61/64; 요속도 오차 0.108/0.109 rad/s.
- eval_pred 회전 좌/우 생존 64/60/64; 요속도 오차 0.114/0.116 rad/s.
- 전진 yaw 누적: 미측 (이 평가 NPZ에 yaw 시계열 없음).

## 출처

- 저장본 SHA256 `64f24758990e0a28e3a8f08a4fac3d65214c4a6d804e96318556fe239214e57e`
- 점수 SHA256 `8a1ed0e260b3dd915009f027e8c3f3fd9c914a07a870f0503e1643d1d38e9a26`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_1000_64f24758990e\map64\map_modes.json`
