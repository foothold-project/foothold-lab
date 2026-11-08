# EX-40 B1 m2000 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-10-31
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

- 완료: m2000, 학습 기록 2026-10-31T18:26:41.171097+09:00, 점수 2026-10-31T18:52:35.667951+09:00
- 경과 14.20 h, 최근 25.04 s/update, 예상 끝 2026-11-02T12:10:58.084549+09:00
- 단계 B1, 그림자 판정 HOLD, 앞 저장본 m1750
- 학습 보상 43.5393, 에피소드 길이 987.74

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.383, walk_left 0.066, walk_right 0.042, spin_left 0.094, spin_right 0.079, stand 0.123, reverse 0.089, side_left 0.073, side_right 0.050
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.0554567681707046; 실제 표본: base_com_offset_m -0.0027375989593565464~0.0027488586492836475 (n=210), actuator_gains 0.994469404220581~1.0055396556854248 (n=1680), motor_strength_multiplier 0.9944692254066467~1.0054535865783691 (n=70), motor_effort_limit 23.370027542114258~45.677757263183594 (n=840), motor_saturation_effort 23.370027542114258~45.677757263183594 (n=840), push_velocity_delta -0.05340567231178284~0.054286837577819824 (n=354)

## 평가 6칸 × 지도 3모드

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 62 | 0.054 | 0.033 | 0.075 | 1.209 (64) |
| eval_gt/fwd1.0 | 63 | 0.081 | 0.039 | 0.072 | 1.089 (64) |
| eval_gt/spin+1.2 | 64 | 0.049 | 0.050 | 0.088 | 0.657 (64) |
| eval_gt/spin-1.2 | 64 | 0.051 | 0.036 | 0.101 | 0.588 (64) |
| eval_gt/stop | 64 | 0.019 | 0.020 | 0.074 | 0.515 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 64 | 0.052 | 0.036 | 0.077 | 1.210 (64) |
| probe_prop_only/fwd1.0 | 64 | 0.085 | 0.042 | 0.074 | 1.119 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.052 | 0.052 | 0.088 | 0.672 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.045 | 0.036 | 0.102 | 0.581 (64) |
| probe_prop_only/stop | 64 | 0.020 | 0.019 | 0.072 | 0.490 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.055 | 0.033 | 0.075 | 1.231 (64) |
| eval_pred/fwd1.0 | 64 | 0.082 | 0.037 | 0.073 | 1.099 (64) |
| eval_pred/spin+1.2 | 64 | 0.051 | 0.052 | 0.089 | 0.672 (64) |
| eval_pred/spin-1.2 | 64 | 0.053 | 0.035 | 0.099 | 0.591 (64) |
| eval_pred/stop | 64 | 0.019 | 0.020 | 0.073 | 0.521 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.330 | 1.58 |
| eval_gt/FR_foot | 1.000 | 0.226 | 1.40 |
| eval_gt/RL_foot | 1.000 | 0.196 | 1.21 |
| eval_gt/RR_foot | 1.000 | 0.249 | 1.60 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.296 | 1.62 |
| probe_prop_only/FR_foot | 1.000 | 0.250 | 1.45 |
| probe_prop_only/RL_foot | 1.000 | 0.214 | 1.23 |
| probe_prop_only/RR_foot | 1.000 | 0.238 | 1.60 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.326 | 1.59 |
| eval_pred/FR_foot | 1.000 | 0.227 | 1.40 |
| eval_pred/RL_foot | 1.000 | 0.196 | 1.22 |
| eval_pred/RR_foot | 1.000 | 0.249 | 1.60 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- 생존 차이 ±3/64를 넘는 칸 없음. 이 범위는 차이 없음으로 표시한다.
- eval_gt 회전 좌/우 생존 64/64/64; 요속도 오차 0.088/0.101 rad/s.
- probe_prop_only 회전 좌/우 생존 64/64/64; 요속도 오차 0.088/0.102 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.089/0.099 rad/s.
- 전진 yaw 누적: 미측 (이 평가 NPZ에 yaw 시계열 없음).

## 출처

- 저장본 SHA256 `55d1339fd2f281d9ad22d365f25ae3f506c8190d78d804a5d593331fe9451bd9`
- 점수 SHA256 `ff09779356a6e2194067f009a86221381ec92ea8ba6dec53fa077b06e7e6f8c2`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_2000_55d1339fd2f2\map64\map_modes.json`
