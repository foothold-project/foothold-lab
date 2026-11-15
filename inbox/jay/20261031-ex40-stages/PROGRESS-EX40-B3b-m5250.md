# EX-40 B3b m5250 저장본 진행 보고

> 분류: 실험 평가
> 작성: scripter · 2026-11-01
> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra
> 요지: 저장본 평가와 학습 진행을 원자료에서 기록
> 상태: 자동 생성 · 그림자 판정 · 독립 평가

## 핵심

- 미달 칸: diag-back+side+(끔 생존 58, 오차 0.101)
- 앞 저장본 대비 생존 변화(±3 초과): probe_prop_only/diag-back+side+ 63→58, eval_pred/diag-back+side+ 61→57
- 서 있기: 네 발 동시 접촉 64/64, 가장 약한 발 RR_foot 0.17 mg (RR 0.17)
- 좌우 회전 오차 0.081/0.086 (차 +0.004, +면 오른쪽이 약함)

- 완료: m5250, 학습 기록 2026-11-01T17:45:15.830135+09:00, 점수 2026-11-01T18:16:28.870845+09:00
- 경과 37.51 h, 최근 25.72 s/update, 예상 끝 2026-11-02T13:24:00.027492+09:00
- 단계 B3b, 그림자 판정 HOLD, 앞 저장본 m5000
- 판정 이유: FAIL probe_prop_only/diag-back+side+: survival_below_60_of_64 · HOLD evidence: invalid evaluation evidence: FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\AI-WS01\\s2_lab\\ex40_main_20261031_041313\\score-watch-b\\model_5250_45d94fed21ad\\axis_v2\\axis_v2.json' · HOLD evaluation_child: evaluation_failed_or_completion_receipt_missing: RuntimeError: EX-40 W57 phase failed with rc=1
- 학습 보상 44.6444, 에피소드 길이 992.61

## 설정과 실현

- 명령 비율 (학습 실현): forward 0.299, walk_left 0.079, walk_right 0.079, spin_left 0.079, spin_right 0.130, stand 0.118, reverse 0.090, side_left 0.048, side_right 0.042, diag_fwd_left 0.014, diag_fwd_right 0.011, diag_back_right 0.011
- 보상 시작 가중: track_lin_vel 2, track_ang_vel 1, lin_vel_z -2, ang_vel_xy -0.05, flat_orientation -1, joint_torques -1e-05, action_rate -0.01, action_smoothness -0.01, joint_power -2e-05, joint_acc -1e-07, joint_deviation -0.01, collision -10, stumble -1, foot_edge 0, basic_hip_pos_penalty_l1 -0.05, ex39_thigh_calf_pos_l1 -0.01, ex39_four_foot_stop 0.1, ex40_stand_gap -0.2, ex40_stand_load -0.1
- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.
- DR 배율 0.4166481440320071; 실제 표본: base_com_offset_m -0.020256904885172844~0.020662451162934303 (n=183), actuator_gains 0.9583473801612854~1.0415849685668945 (n=1464), motor_strength_multiplier 0.9628568291664124~1.0416228771209717 (n=61), motor_effort_limit 22.62713623046875~47.320926666259766 (n=732), motor_saturation_effort 22.62713623046875~47.320926666259766 (n=732), push_velocity_delta -0.40890416502952576~0.41078126430511475 (n=474)

## 평가 칸 × 지도 3모드 (그림자 판정 대상은 단계에서 배운 칸)

| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |
|---|---:|---:|---:|---:|---:|
| eval_gt/fwd0.5 | 63 | 0.055 | 0.029 | 0.078 | 1.045 (64) |
| eval_gt/fwd1.0 | 63 | 0.101 | 0.036 | 0.073 | 1.158 (64) |
| eval_gt/spin+1.2 | 64 | 0.044 | 0.032 | 0.081 | 0.567 (64) |
| eval_gt/spin-1.2 | 64 | 0.031 | 0.030 | 0.086 | 0.548 (64) |
| eval_gt/stop | 64 | 0.017 | 0.016 | 0.064 | 0.618 (64) |
| eval_gt/back0.5 | 64 | 0.102 | 0.031 | 0.079 | 1.147 (64) |
| eval_gt/back1.0 | 62 | 0.128 | 0.046 | 0.084 | 1.460 (64) |
| eval_gt/diag-back+side+ | 62 | 0.093 | 0.058 | 0.086 | 1.477 (64) |
| eval_gt/diag-back+side- | 63 | 0.093 | 0.105 | 0.102 | 1.494 (64) |
| eval_gt/diag-fwd+side+ | 61 | 0.052 | 0.057 | 0.078 | 1.355 (64) |
| eval_gt/diag-fwd+side- | 64 | 0.098 | 0.100 | 0.087 | 1.294 (64) |
| eval_gt/side+0.5 | 63 | 0.043 | 0.062 | 0.083 | 1.245 (64) |
| eval_gt/side-0.5 | 64 | 0.039 | 0.120 | 0.094 | 1.163 (64) |
| eval_gt/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| probe_prop_only/fwd0.5 | 64 | 0.057 | 0.030 | 0.080 | 1.059 (64) |
| probe_prop_only/fwd1.0 | 64 | 0.097 | 0.038 | 0.076 | 1.166 (64) |
| probe_prop_only/spin+1.2 | 64 | 0.050 | 0.032 | 0.082 | 0.577 (64) |
| probe_prop_only/spin-1.2 | 64 | 0.031 | 0.032 | 0.086 | 0.538 (64) |
| probe_prop_only/stop | 64 | 0.019 | 0.016 | 0.064 | 0.616 (64) |
| probe_prop_only/back0.5 | 64 | 0.117 | 0.034 | 0.080 | 1.176 (64) |
| probe_prop_only/back1.0 | 63 | 0.137 | 0.045 | 0.087 | 1.470 (64) |
| probe_prop_only/diag-back+side+ | 58 | 0.101 | 0.059 | 0.090 | 1.427 (64) |
| probe_prop_only/diag-back+side- | 63 | 0.096 | 0.096 | 0.102 | 1.573 (64) |
| probe_prop_only/diag-fwd+side+ | 64 | 0.056 | 0.052 | 0.080 | 1.314 (64) |
| probe_prop_only/diag-fwd+side- | 64 | 0.091 | 0.105 | 0.089 | 1.300 (64) |
| probe_prop_only/side+0.5 | 63 | 0.052 | 0.067 | 0.082 | 1.307 (64) |
| probe_prop_only/side-0.5 | 64 | 0.042 | 0.109 | 0.094 | 1.152 (64) |
| probe_prop_only/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |
| eval_pred/fwd0.5 | 64 | 0.057 | 0.029 | 0.079 | 1.047 (64) |
| eval_pred/fwd1.0 | 63 | 0.102 | 0.037 | 0.075 | 1.155 (64) |
| eval_pred/spin+1.2 | 64 | 0.042 | 0.032 | 0.082 | 0.565 (64) |
| eval_pred/spin-1.2 | 64 | 0.031 | 0.032 | 0.086 | 0.551 (64) |
| eval_pred/stop | 64 | 0.017 | 0.016 | 0.064 | 0.617 (64) |
| eval_pred/back0.5 | 64 | 0.099 | 0.032 | 0.083 | 1.184 (64) |
| eval_pred/back1.0 | 62 | 0.117 | 0.045 | 0.089 | 1.543 (64) |
| eval_pred/diag-back+side+ | 57 | 0.085 | 0.059 | 0.086 | 1.449 (64) |
| eval_pred/diag-back+side- | 63 | 0.094 | 0.110 | 0.102 | 1.501 (64) |
| eval_pred/diag-fwd+side+ | 64 | 0.052 | 0.057 | 0.078 | 1.330 (64) |
| eval_pred/diag-fwd+side- | 64 | 0.096 | 0.092 | 0.088 | 1.320 (64) |
| eval_pred/side+0.5 | 62 | 0.045 | 0.067 | 0.086 | 1.245 (64) |
| eval_pred/side-0.5 | 64 | 0.039 | 0.114 | 0.096 | 1.163 (64) |
| eval_pred/flat_stand | 64/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |

복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.

## 서 있기 네 발

| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |
|---|---:|---:|---:|
| eval_gt/FL_foot | 1.000 | 0.278 | 1.68 |
| eval_gt/FR_foot | 1.000 | 0.303 | 1.29 |
| eval_gt/RL_foot | 1.000 | 0.248 | 1.14 |
| eval_gt/RR_foot | 1.000 | 0.171 | 1.52 |
| eval_gt/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| probe_prop_only/FL_foot | 1.000 | 0.270 | 1.68 |
| probe_prop_only/FR_foot | 1.000 | 0.309 | 1.29 |
| probe_prop_only/RL_foot | 1.000 | 0.249 | 1.15 |
| probe_prop_only/RR_foot | 1.000 | 0.170 | 1.51 |
| probe_prop_only/네 발 동시 접촉 ≥90% env | 64/64 |  |  |
| eval_pred/FL_foot | 1.000 | 0.278 | 1.69 |
| eval_pred/FR_foot | 1.000 | 0.301 | 1.28 |
| eval_pred/RL_foot | 1.000 | 0.251 | 1.14 |
| eval_pred/RR_foot | 1.000 | 0.170 | 1.52 |
| eval_pred/네 발 동시 접촉 ≥90% env | 64/64 |  |  |

## 변화와 좌우

- probe_prop_only/diag-back+side+: 63→58 (-5/64)
- eval_pred/diag-back+side+: 61→57 (-4/64)
- eval_gt 회전 좌/우 생존 64/64/64; 요속도 오차 0.081/0.086 rad/s.
- probe_prop_only 회전 좌/우 생존 64/64/64; 요속도 오차 0.082/0.086 rad/s.
- eval_pred 회전 좌/우 생존 64/64/64; 요속도 오차 0.082/0.086 rad/s.
- 전진 yaw 누적(정답 지도, m4750 측정): 0.5 m/s 12.25° · 1.0 m/s 21.71°

## 출처

- 저장본 SHA256 `45d94fed21ad0e956cfff9bf6864135bdb20b7515c873d530d7ffe687404251b`
- 점수 SHA256 `9e36766d8341b68e55384d6eaddcf477f35ae7028be37399ed23f7f00d8fe8f3`
- 평가 원자료: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\score-watch-b\model_5250_45d94fed21ad\map64\map_modes.json`
