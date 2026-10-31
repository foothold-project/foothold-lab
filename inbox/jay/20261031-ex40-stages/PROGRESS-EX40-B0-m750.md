# EX-40 B0 m750 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-10-31
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

- 완료: m750, 학습 기록 2026-10-31T09:33:00.094837+09:00, 점수 2026-10-31T14:21:40.025698+09:00
- 경과 5.31 h, 최근 24.89 s/update, 예상 끝 2026-11-02T11:40:12.725607+09:00
- 단계 B0, 그림자 판정 PASS, 앞 저장본 m500
- 학습 보상 40.6854, 에피소드 길이 985.29

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.750, spin_left 0.083, spin_right 0.083, stand 0.083
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.0; 실제 표본: base_com_offset_m 0.0~0.0 (n=213), actuator_gains 1.0~1.0 (n=1704), motor_strength_multiplier 1.0~1.0 (n=71), motor_effort_limit 23.5~45.43000030517578 (n=852), motor_saturation_effort 23.5~45.43000030517578 (n=852), push_velocity_delta 0.0~0.0 (n=468)

## 평가 6칸 × 지도 3모드

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 64 | 0.071 | 0.034 | 0.084 | 1.413 (64) |
| eval_gt/fwd1.0 | 64 | 0.094 | 0.036 | 0.080 | 1.369 (64) |
| eval_gt/spin+1.2 | 64 | 0.036 | 0.077 | 0.143 | 0.939 (64) |
| eval_gt/spin-1.2 | 64 | 0.056 | 0.045 | 0.130 | 0.712 (64) |
| eval_gt/stop | 64 | 0.024 | 0.024 | 0.083 | 0.592 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 64 | 0.073 | 0.036 | 0.082 | 1.436 (64) |
| probe_prop_only/fwd1.0 | 63 | 0.098 | 0.034 | 0.082 | 1.399 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.040 | 0.090 | 0.142 | 0.917 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.058 | 0.050 | 0.132 | 0.707 (64) |
| probe_prop_only/stop | 64 | 0.025 | 0.025 | 0.083 | 0.587 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.068 | 0.034 | 0.084 | 1.416 (64) |
| eval_pred/fwd1.0 | 64 | 0.092 | 0.039 | 0.082 | 1.391 (64) |
| eval_pred/spin+1.2 | 64 | 0.037 | 0.076 | 0.145 | 0.931 (64) |
| eval_pred/spin-1.2 | 64 | 0.054 | 0.045 | 0.128 | 0.718 (64) |
| eval_pred/stop | 64 | 0.024 | 0.024 | 0.083 | 0.596 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.262 | 1.94 |
| eval_gt/FR_foot | 1.000 | 0.176 | 1.84 |
| eval_gt/RL_foot | 1.000 | 0.266 | 1.02 |
| eval_gt/RR_foot | 1.000 | 0.301 | 1.52 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.269 | 1.93 |
| probe_prop_only/FR_foot | 1.000 | 0.175 | 1.81 |
| probe_prop_only/RL_foot | 1.000 | 0.264 | 0.91 |
| probe_prop_only/RR_foot | 1.000 | 0.294 | 1.46 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.263 | 1.94 |
| eval_pred/FR_foot | 1.000 | 0.175 | 1.84 |
| eval_pred/RL_foot | 1.000 | 0.264 | 1.01 |
| eval_pred/RR_foot | 1.000 | 0.304 | 1.53 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- 생존 차이 ±3/64를 넘는 칸 없음. 이 범위는 차이 없음으로 표시한다.
- eval_gt 회전 좌/우 생존 64/64/64; 요속도 오차 0.143/0.130 rad/s.
- probe_prop_only 회전 좌/우 생존 64/64/64; 요속도 오차 0.142/0.132 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.145/0.128 rad/s.
- 전진 yaw 누적: 미측 (이 평가 NPZ에 yaw 시계열 없음).

## 출처

- 저장본 SHA256 `e5d53d9bc92728f174a324e6d8189716dc14affe0a070b1fb41a039ce15359dc`
- 점수 SHA256 `5ebfa0f7b4d81daca9cc770cfb54066037d1fc8d5bc6515f73215bffa115a424`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_750_e5d53d9bc927\map64\map_modes.json`
