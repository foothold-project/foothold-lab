# EX-40 B1 m2250 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-10-31
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

## 핵심

- 미달 칸: side-0.5(끔 생존 58, 오차 0.108)
- 앞 저장본 대비 생존 변화(±3 초과): 없음
- 서 있기: 네 발 동시 접촉 64/64, 가장 약한 발 RR_foot 0.21 mg (RR 0.21)
- 좌우 회전 오차 0.087/0.085 (차 -0.002, +면 오른쪽이 약함)

- 완료: m2250, 학습 기록 2026-10-31T20:13:11.013530+09:00, 점수 2026-10-31T20:37:31.531875+09:00
- 경과 15.98 h, 최근 25.19 s/update, 예상 끝 2026-11-02T12:26:53.086909+09:00
- 단계 B1, 그림자 판정 HOLD, 앞 저장본 m2000
- 학습 보상 43.7927, 에피소드 길이 983.96

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.404, walk_left 0.041, walk_right 0.062, spin_left 0.089, spin_right 0.122, stand 0.119, reverse 0.062, side_left 0.057, side_right 0.043
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.08324072016003556; 실제 표본: base_com_offset_m -0.0041182804852724075~0.004149474203586578 (n=216), actuator_gains 0.9916799664497375~1.0083030462265015 (n=1728), motor_strength_multiplier 0.9918237328529358~1.0080492496490479 (n=72), motor_effort_limit 23.307857513427734~45.795677185058594 (n=864), motor_saturation_effort 23.307857513427734~45.795677185058594 (n=864), push_velocity_delta -0.08145493268966675~0.08235883712768555 (n=528)

## 평가 칸 × 지도 3모드 (그림자 판정 대상은 단계에서 배운 칸)

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 64 | 0.049 | 0.028 | 0.071 | 1.095 (64) |
| eval_gt/fwd1.0 | 63 | 0.075 | 0.038 | 0.070 | 1.192 (64) |
| eval_gt/spin+1.2 | 64 | 0.038 | 0.048 | 0.087 | 0.623 (64) |
| eval_gt/spin-1.2 | 64 | 0.058 | 0.034 | 0.085 | 0.535 (64) |
| eval_gt/stop | 64 | 0.019 | 0.017 | 0.057 | 0.562 (64) |
| eval_gt/back0.5 | 63 | 0.119 | 0.033 | 0.075 | 1.152 (64) |
| eval_gt/back1.0 | 56 | 0.128 | 0.049 | 0.108 | 1.709 (64) |
| eval_gt/diag-back+side+ | 58 | 0.106 | 0.162 | 0.104 | 1.695 (64) |
| eval_gt/diag-back+side- | 57 | 0.102 | 0.210 | 0.118 | 1.551 (64) |
| eval_gt/diag-fwd+side+ | 63 | 0.103 | 0.070 | 0.083 | 1.542 (64) |
| eval_gt/diag-fwd+side- | 61 | 0.057 | 0.073 | 0.091 | 1.504 (64) |
| eval_gt/side+0.5 | 64 | 0.067 | 0.121 | 0.095 | 1.455 (64) |
| eval_gt/side-0.5 | 62 | 0.044 | 0.104 | 0.095 | 1.282 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 62 | 0.049 | 0.030 | 0.073 | 1.180 (64) |
| probe_prop_only/fwd1.0 | 64 | 0.080 | 0.046 | 0.070 | 1.306 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.042 | 0.052 | 0.086 | 0.639 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.053 | 0.034 | 0.087 | 0.549 (64) |
| probe_prop_only/stop | 64 | 0.020 | 0.017 | 0.057 | 0.563 (64) |
| probe_prop_only/back0.5 | 63 | 0.110 | 0.033 | 0.078 | 1.188 (64) |
| probe_prop_only/back1.0 | 58 | 0.130 | 0.052 | 0.105 | 1.712 (64) |
| probe_prop_only/diag-back+side+ | 58 | 0.115 | 0.141 | 0.115 | 1.748 (64) |
| probe_prop_only/diag-back+side- | 59 | 0.103 | 0.212 | 0.103 | 1.547 (64) |
| probe_prop_only/diag-fwd+side+ | 63 | 0.102 | 0.078 | 0.092 | 1.573 (64) |
| probe_prop_only/diag-fwd+side- | 61 | 0.056 | 0.077 | 0.090 | 1.554 (64) |
| probe_prop_only/side+0.5 | 64 | 0.070 | 0.111 | 0.095 | 1.473 (64) |
| probe_prop_only/side-0.5 | 58 | 0.048 | 0.108 | 0.093 | 1.284 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.049 | 0.029 | 0.071 | 1.121 (64) |
| eval_pred/fwd1.0 | 64 | 0.073 | 0.038 | 0.070 | 1.211 (64) |
| eval_pred/spin+1.2 | 64 | 0.039 | 0.049 | 0.087 | 0.635 (64) |
| eval_pred/spin-1.2 | 64 | 0.058 | 0.033 | 0.085 | 0.545 (64) |
| eval_pred/stop | 64 | 0.019 | 0.017 | 0.057 | 0.565 (64) |
| eval_pred/back0.5 | 62 | 0.109 | 0.035 | 0.076 | 1.177 (64) |
| eval_pred/back1.0 | 57 | 0.127 | 0.050 | 0.108 | 1.715 (64) |
| eval_pred/diag-back+side+ | 59 | 0.107 | 0.157 | 0.110 | 1.713 (64) |
| eval_pred/diag-back+side- | 60 | 0.103 | 0.202 | 0.114 | 1.573 (64) |
| eval_pred/diag-fwd+side+ | 63 | 0.105 | 0.074 | 0.085 | 1.564 (64) |
| eval_pred/diag-fwd+side- | 60 | 0.059 | 0.069 | 0.093 | 1.544 (64) |
| eval_pred/side+0.5 | 64 | 0.069 | 0.105 | 0.096 | 1.469 (64) |
| eval_pred/side-0.5 | 60 | 0.047 | 0.102 | 0.093 | 1.285 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.265 | 1.67 |
| eval_gt/FR_foot | 1.000 | 0.282 | 1.41 |
| eval_gt/RL_foot | 1.000 | 0.241 | 1.16 |
| eval_gt/RR_foot | 1.000 | 0.213 | 1.59 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.271 | 1.70 |
| probe_prop_only/FR_foot | 1.000 | 0.281 | 1.37 |
| probe_prop_only/RL_foot | 1.000 | 0.250 | 1.09 |
| probe_prop_only/RR_foot | 1.000 | 0.197 | 1.59 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.267 | 1.69 |
| eval_pred/FR_foot | 1.000 | 0.283 | 1.40 |
| eval_pred/RL_foot | 1.000 | 0.241 | 1.14 |
| eval_pred/RR_foot | 1.000 | 0.210 | 1.59 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- 생존 차이 ±3/64를 넘는 칸 없음. 이 범위는 차이 없음으로 표시한다.
- eval_gt 회전 좌/우 생존 64/64/64; 요속도 오차 0.087/0.085 rad/s.
- probe_prop_only 회전 좌/우 생존 64/64/64; 요속도 오차 0.086/0.087 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.087/0.085 rad/s.
- 전진 yaw 누적: 미측 (이 평가 NPZ에 yaw 시계열 없음).

## 출처

- 저장본 SHA256 `1fe47f971f51db7609ad312910440e9b8d3db75de210a8e3c6ba060897b23b66`
- 점수 SHA256 `85408019eeed8df9fc085f7cf01ffea02b2f38907dcad4abafc3b71846b2400f`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_2250_1fe47f971f51\map64\map_modes.json`
