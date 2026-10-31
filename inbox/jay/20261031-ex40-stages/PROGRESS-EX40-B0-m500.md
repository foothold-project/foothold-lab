# EX-40 B0 m500 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-10-31
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

- 완료: m500, 학습 기록 2026-10-31T07:47:00.761619+09:00, 점수 2026-10-31T13:57:35.009696+09:00
- 경과 3.54 h, 최근 25.26 s/update, 예상 끝 2026-11-02T12:24:50.971671+09:00
- 단계 B0, 그림자 판정 FAIL, 앞 저장본 m없음
- 학습 보상 32.3410, 에피소드 길이 951.06

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.723, spin_left 0.075, spin_right 0.101, stand 0.101
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.0; 실제 표본: base_com_offset_m 0.0~0.0 (n=207), actuator_gains 1.0~1.0 (n=1656), motor_strength_multiplier 1.0~1.0 (n=69), motor_effort_limit 23.5~45.43000030517578 (n=828), motor_saturation_effort 23.5~45.43000030517578 (n=828), push_velocity_delta 0.0~0.0 (n=372)

## 평가 6칸 × 지도 3모드

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 63 | 0.086 | 0.044 | 0.104 | 1.513 (64) |
| eval_gt/fwd1.0 | 61 | 0.111 | 0.080 | 0.116 | 1.608 (64) |
| eval_gt/spin+1.2 | 64 | 0.082 | 0.098 | 0.185 | 1.025 (64) |
| eval_gt/spin-1.2 | 63 | 0.071 | 0.082 | 0.221 | 1.029 (64) |
| eval_gt/stop | 64 | 0.035 | 0.027 | 0.104 | 0.825 (64) |
| eval_gt/flat_stand | 50/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 63 | 0.100 | 0.047 | 0.105 | 1.509 (64) |
| probe_prop_only/fwd1.0 | 61 | 0.112 | 0.071 | 0.116 | 1.623 (64) |
| probe_prop_only/spin+1.2 | 63 | 0.087 | 0.095 | 0.186 | 1.016 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.078 | 0.085 | 0.238 | 1.066 (64) |
| probe_prop_only/stop | 64 | 0.035 | 0.027 | 0.105 | 0.829 (64) |
| probe_prop_only/flat_stand | 51/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.089 | 0.044 | 0.104 | 1.502 (64) |
| eval_pred/fwd1.0 | 64 | 0.120 | 0.077 | 0.114 | 1.575 (64) |
| eval_pred/spin+1.2 | 64 | 0.085 | 0.096 | 0.187 | 1.033 (64) |
| eval_pred/spin-1.2 | 64 | 0.074 | 0.082 | 0.208 | 1.040 (64) |
| eval_pred/stop | 64 | 0.035 | 0.028 | 0.105 | 0.833 (64) |
| eval_pred/flat_stand | 48/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.291 | 1.96 |
| eval_gt/FR_foot | 1.000 | 0.198 | 1.97 |
| eval_gt/RL_foot | 1.000 | 0.184 | 0.98 |
| eval_gt/RR_foot | 1.000 | 0.330 | 1.16 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.279 | 1.96 |
| probe_prop_only/FR_foot | 1.000 | 0.210 | 1.95 |
| probe_prop_only/RL_foot | 1.000 | 0.203 | 1.01 |
| probe_prop_only/RR_foot | 1.000 | 0.310 | 1.13 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.300 | 1.96 |
| eval_pred/FR_foot | 1.000 | 0.188 | 1.97 |
| eval_pred/RL_foot | 1.000 | 0.171 | 0.96 |
| eval_pred/RR_foot | 1.000 | 0.342 | 1.20 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- 생존 차이 ±3/64를 넘는 칸 없음. 이 범위는 차이 없음으로 표시한다.
- eval_gt 회전 좌/우 생존 64/63/64; 요속도 오차 0.185/0.221 rad/s.
- probe_prop_only 회전 좌/우 생존 63/64/64; 요속도 오차 0.186/0.238 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.187/0.208 rad/s.
- 전진 yaw 누적: 미측 (이 평가 NPZ에 yaw 시계열 없음).

## 출처

- 저장본 SHA256 `6d0bfdde1175032bd3b51c1824f08bc1d668a2f4be9dc88e2c4388c9059706da`
- 점수 SHA256 `c87aa128cae07fe7d90413076f4f08553367675327540ca69e8edaa6a066318c`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_500_6d0bfdde1175\map64\map_modes.json`
