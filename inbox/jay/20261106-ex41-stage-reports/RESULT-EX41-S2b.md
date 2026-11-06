> 분류: A/평가 · EX-41 단계 분석
> 작성: analyst · 2026-11-06 17:18 대한민국 표준시
> 근거: 운영 원자료 스크립트 재계산 · OVERNIGHT-CONTRACT §2 · #555
> 요지: 강한 밀기 대응은 크게 좋아졌고 후진은 끝에서 회복했다. 전진 방향 유지와 학습률 흔들림은 남았다.
> 상태: 정식 단계 보고 v1.0 · W78 v2 조각 결과 대기 · 영상 판독 범위 제한

# EX-41 S2b · 로컬 751~2750회 단계 보고

강한 밀기 대응은 크게 좋아졌고 후진은 끝에서 회복했다. 전진 방향 유지와 학습률 흔들림은 남았다.

**무엇을 배웠나.** 단계 끝 밀기에서 이전 단계의 취약한 지형까지 기존 기준을 넘었다. 후진은 중간에 다시 나빠졌다가 끝에서 회복했으므로 계속 좋아지는 학습이었다고 표현하지 않는다.

**무너진 기술은 무엇인가.** 접촉 위상은 전진 평가에서 이전 단계보다 기준에 가까워졌다. 반면 전진 중 몸이 돌아간 양은 커졌다. 발 교대와 진행 방향은 다른 능력이며 한쪽 점수로 다른 쪽을 대신할 수 없다.

**다음 단계에 준 영향.** 점수 지연으로 DR 상승이 보류된 기간을 포함한다. 이 연장은 성능 실패 때문에 추가 학습한 통제 실험이 아니다. 다음 단계는 현재의 좋은 발 교대를 보존하며 방향 유지도 따로 감시해야 한다.

이 문서는 완료된 단계의 근거를 정리한다. 학습 승인이나 졸업 판정을 새로 만들지 않는다. 아래 수치는 원자료를 읽어 생성한 **실측**이다. 인과 설명과 다음 단계 권고는 **해석**이며 단일 시드의 결론이다.

## 영상과 비교 자료

공용 재생 목록: `C:\Users\AI-WS01\s2_lab\_playlists\EX41-ALL-stages-1106.m3u8`. 보고 시점의 이 저장본 항목은 54편이다. 전편을 사람이 재생 확인한 수가 아니다.

| 명령(정답 지도) | 원본 프레임/초 | 완전 해독·검정 | 대표 프레임과 원본 |
| --- | --- | --- | --- |
| fwd10 | 150 / 25 | 150 해독 · 검정 0 | [프레임](figs\m2750-fwd10-frames.jpg) · `D:\mai-tmp\runner\ex41_stage_video\model_2750_cc37ad8f16d7\EX41-pyramid_stairs_inv_L1-m2750-w57_fwd10_eval_gt-1x-success.mp4` |
| back10 | 150 / 25 | 150 해독 · 검정 0 | [프레임](figs\m2750-back10-frames.jpg) · `D:\mai-tmp\runner\ex41_stage_video\model_2750_cc37ad8f16d7\EX41-pyramid_stairs_inv_L1-m2750-w57_back10_eval_gt-1x-success.mp4` |
| sidem05 | 150 / 25 | 150 해독 · 검정 0 | [프레임](figs\m2750-sidem05-frames.jpg) · `D:\mai-tmp\runner\ex41_stage_video\model_2750_cc37ad8f16d7\EX41-pyramid_stairs_inv_L1-m2750-w57_sidem05_eval_gt-1x-success.mp4` |

대표 전진·후진·오른쪽 옆걸음을 고정 선택했다. 프레임 띠에서 몸을 지지하며 이동하는 모습은 확인된다. 옆걸음 후반에는 몸 방향·높이 변화가 보이므로 균일한 trot나 끌림 해소를 영상만으로 선언하지 않는다. 전 프레임 해독은 파일 검증이며 시각 판독은 아래 표본 프레임에 한정한다. 1x 실시간 전편 판독은 별도 확인 사항이다.

![S2b 전진 대표 프레임](figs/m2750-fwd10-frames.jpg)

CPU로 기존 영상 두 편을 나란히 놓은 1x CMP. 새 시뮬레이션 촬영이 아니다. 같은 이름의 지형·레벨·명령·지도 모드지만 궤적이 같은 통계적 짝 표본은 아니다.

| 비교 | 명령 | 로컬 경로 |
| --- | --- | --- |
| m750 대 m2750 | fwd10 | `D:\mai-tmp\analyst\ex41-stage-reports-1106\media\CMP-EX41-m750-m2750-fwd10-GT-1x.mp4` |
| m750 대 m2750 | back10 | `D:\mai-tmp\analyst\ex41-stage-reports-1106\media\CMP-EX41-m750-m2750-back10-GT-1x.mp4` |
| m750 대 m2750 | sidem05 | `D:\mai-tmp\analyst\ex41-stage-reports-1106\media\CMP-EX41-m750-m2750-sidem05-GT-1x.mp4` |

## 무엇을 같은 조건으로 재었나

| 항목 | 조건·단위 | 출처/한계 |
| --- | --- | --- |
| 로컬/누적 회차 | 로컬 751\~2750, 부모 학습에 이어 누적 6751\~8750 | 회차는 보고용 합산. 처음부터 학습한 새 시드가 아님 |
| 학습 출발 | EX-40 m6000 · d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5 | ex41_application.jsonl:1 |
| 고정 명령 평가 | 64 env × 13명령 × 지도 3모드 · 300 step × 0.02초 | map_modes.json. 같은 배치 해시·시드·명령·env 수 코드 단언 |
| 지도 모드 | GT=정답, Pred=복원, 지도 끔=지도 입력 가림 | 지도 끔은 별도 G0 학습 정책이 아님 |
| 오차 집계 | env마다 살아 있던 구간의 평균 절대오차, 그 64개 중앙값 | 종료 뒤 리셋 구간 제외. 짧게 산 env도 포함하므로 생존과 함께 읽음 |
| 표의 주축 | 전후·대각 vx, 옆 vy, 회전 wz, 정지 vx | 단위: vx/vy m/s, wz rad/s. 대각 vy와 정지 wz도 전체 표에 남김 |
| 보행 위상·W57 | 고정 L2, 64 env, 발 접촉 >1 N, dt=0.02초 | 고정 명령 map64 L0\~2와 다른 평가. 직접 값을 섞지 않음 |
| 평가 DR | 핵심 map64는 dr_off 기록을 가진 유지 평가 | 학습 DR 상승과 다른 조건. 강건성은 별도 밀기 표에서 확인 |

## 실제 적용한 학습 조건

| 원장 행 | 로컬 경계 | 단계 | DR 경계값 | 지형 정책/상한 | 이유 |
| --- | --- | --- | --- | --- | --- |
| 5 | 751 | S2b | 0.5000 | fixed_l02 / L2 | schedule_continue |
| 6 | 1001 | S2b | 0.5375 | fixed_l02 / L2 | schedule_continue |
| 7 | 1251 | S2b | 0.5750 | fixed_l02 / L2 | dr_hold_missing_evidence |
| 8 | 1501 | S2b | 0.5750 | fixed_l02 / L2 | dr_hold_missing_evidence |
| 9 | 1751 | S2b | 0.5750 | fixed_l02 / L2 | dr_hold_missing_evidence |
| 10 | 2001 | S2b | 0.5750 | fixed_l02 / L2 | dr_hold_recovery_1_of_2 |
| 11 | 2251 | S2b | 0.5750 | fixed_l02 / L2 | dr_resume_same_slope |
| 12 | 2501 | S2b | 0.6125 | fixed_l02 / L2 | schedule_continue |

DR은 마찰·질량·구동기 등 학습 조건을 흔드는 강도를 뜻한다. 위 값은 경계에서 적용한 값이다. 경계 사이 물리값 분포 전수 측정으로 오해하지 않는다.

| 명령 슬롯 | 학습 몫 % |
| --- | --- |
| diag_back_left | 2.5 |
| diag_back_right | 2.5 |
| diag_fwd_left | 1.5 |
| diag_fwd_right | 1.5 |
| forward | 23.0 |
| reverse | 14.0 |
| side_left | 6.0 |
| side_right | 6.0 |
| spin_left | 9.0 |
| spin_right | 9.0 |
| stand | 10.0 |
| walk_left | 7.5 |
| walk_right | 7.5 |

| 설정 | 실제 마지막 적용값 |
| --- | --- |
| ranges | {"diag_vx_abs": [0.3, 0.6], "diag_vy_abs": [0.2, 0.5], "forward_vx": [0.1, 1.5], "reverse_vx": [-1.3, -0.2], "side_vy_abs": [0.2, 0.6], "spin_wz_abs": [0.3, 1.5], "walk_vx": [0.3, 0.8], "walk_wz_abs": [0.2, 1.0]} |
| heading | {"forward_fraction": 0.3, "forward_wz_limit": 0.5, "gain": 0.5, "spin_target_fraction": 0.3, "target_wz_limit": 1.5} |
| reward_weights | {"feet_air_time": 0.0, "foot_slip": 0.0, "four_foot_contact_at_stop": 0.1, "hip_pos_penalty": -0.05, "joint_acc": -1e-07, "joint_limit_margin": 0.0, "knee_effort_margin": 0.0, "stand_gap": -0.2, "stand_load": -0.1, "stumble": -2.0, "swing": -10.0, "thigh_calf_pos_l1": -0.01, "track_ang_vel": 1.0, "track_lin_vel": 2.0, "zero_yaw": -0.5} |
| ppo | {"desired_kl": 0.01, "entropy_coef": 0.01} |
| force_gt | true |
| critic_mirror | false |
| episode_length_s | 20.0 |

명령 몫은 환경이 뽑을 확률이고 실제 방문 빈도와 같다고 단정하지 않는다. force_gt는 지도 켠 갈래의 정답 지도 강제 설정이며 지도 끔 표본 비율과 함께 해석해야 한다. 새 처방과 DR·지형 변화가 섞여 있으므로 보상항 하나의 효과로 귀속할 수 없다.

## 명령 추종과 생존

![명령 오차](figs/S2b-commands.png)

점선은 기존 경계 보고의 0.15 기록선이다. 새 합격선을 만든 것이 아니다. 값이 넘으면 어떤 명령·모드인지 확인한다. 이 선을 생존 관문의 통과/실패와 혼동하지 않는다.

| 명령 | 주축 | 직전 끝 GT | 이번 끝 GT | 차이(이번−이전) | Pred | 지도 끔 |
| --- | --- | --- | --- | --- | --- | --- |
| fwd0.5 | vx | 0.053 | 0.054 | 0.001 | 0.057 | 0.058 |
| fwd1.0 | vx | 0.082 | 0.083 | 0.001 | 0.083 | 0.092 |
| spin+1.2 | wz | 0.086 | 0.083 | -0.003 | 0.082 | 0.081 |
| spin-1.2 | wz | 0.088 | 0.083 | -0.005 | 0.083 | 0.083 |
| back0.5 | vx | 0.116 | 0.092 | -0.024 | 0.094 | 0.075 |
| back1.0 | vx | 0.153 | 0.137 | -0.015 | 0.145 | 0.131 |
| side+0.5 | vy | 0.105 | 0.067 | -0.037 | 0.070 | 0.067 |
| side-0.5 | vy | 0.129 | 0.104 | -0.025 | 0.103 | 0.082 |
| diag-fwd+side+ | vx | 0.053 | 0.046 | -0.006 | 0.048 | 0.051 |
| diag-fwd+side- | vx | 0.052 | 0.065 | 0.013 | 0.067 | 0.064 |
| diag-back+side+ | vx | 0.093 | 0.098 | 0.005 | 0.097 | 0.090 |
| diag-back+side- | vx | 0.144 | 0.089 | -0.055 | 0.092 | 0.073 |
| stop | vx | 0.018 | 0.018 | 0.000 | 0.018 | 0.019 |

![생존](figs/S2b-survival.png)

단계 중 모든 핵심 평가 칸의 최저 생존은 62/64이다. 생존은 종료까지 안 넘어진 개수이고, 명령대로 잘 이동했는지의 점수는 아니다.

### 단계 끝 전체 오차 표

| 지도 | 명령 | vx m/s | vy m/s | wz rad/s | 생존/64 |
| --- | --- | --- | --- | --- | --- |
| GT 정답 | fwd0.5 | 0.054 | 0.033 | 0.071 | 64 |
| GT 정답 | fwd1.0 | 0.083 | 0.034 | 0.070 | 64 |
| GT 정답 | spin+1.2 | 0.046 | 0.044 | 0.083 | 64 |
| GT 정답 | spin-1.2 | 0.037 | 0.044 | 0.083 | 64 |
| GT 정답 | back0.5 | 0.092 | 0.033 | 0.074 | 64 |
| GT 정답 | back1.0 | 0.137 | 0.046 | 0.077 | 64 |
| GT 정답 | side+0.5 | 0.038 | 0.067 | 0.081 | 64 |
| GT 정답 | side-0.5 | 0.043 | 0.104 | 0.080 | 64 |
| GT 정답 | diag-fwd+side+ | 0.046 | 0.059 | 0.079 | 64 |
| GT 정답 | diag-fwd+side- | 0.065 | 0.068 | 0.083 | 64 |
| GT 정답 | diag-back+side+ | 0.098 | 0.070 | 0.082 | 64 |
| GT 정답 | diag-back+side- | 0.089 | 0.087 | 0.081 | 62 |
| GT 정답 | stop | 0.018 | 0.012 | 0.071 | 64 |
| Pred 복원 | fwd0.5 | 0.057 | 0.033 | 0.071 | 64 |
| Pred 복원 | fwd1.0 | 0.083 | 0.035 | 0.071 | 64 |
| Pred 복원 | spin+1.2 | 0.044 | 0.044 | 0.082 | 64 |
| Pred 복원 | spin-1.2 | 0.037 | 0.044 | 0.083 | 64 |
| Pred 복원 | back0.5 | 0.094 | 0.033 | 0.074 | 64 |
| Pred 복원 | back1.0 | 0.145 | 0.041 | 0.077 | 64 |
| Pred 복원 | side+0.5 | 0.037 | 0.070 | 0.080 | 64 |
| Pred 복원 | side-0.5 | 0.044 | 0.103 | 0.081 | 64 |
| Pred 복원 | diag-fwd+side+ | 0.048 | 0.060 | 0.082 | 64 |
| Pred 복원 | diag-fwd+side- | 0.067 | 0.072 | 0.087 | 64 |
| Pred 복원 | diag-back+side+ | 0.097 | 0.071 | 0.083 | 64 |
| Pred 복원 | diag-back+side- | 0.092 | 0.091 | 0.083 | 63 |
| Pred 복원 | stop | 0.018 | 0.012 | 0.071 | 64 |
| 지도 끔 | fwd0.5 | 0.058 | 0.034 | 0.072 | 64 |
| 지도 끔 | fwd1.0 | 0.092 | 0.037 | 0.072 | 64 |
| 지도 끔 | spin+1.2 | 0.044 | 0.044 | 0.081 | 64 |
| 지도 끔 | spin-1.2 | 0.035 | 0.043 | 0.083 | 64 |
| 지도 끔 | back0.5 | 0.075 | 0.035 | 0.074 | 64 |
| 지도 끔 | back1.0 | 0.131 | 0.046 | 0.076 | 64 |
| 지도 끔 | side+0.5 | 0.037 | 0.067 | 0.081 | 63 |
| 지도 끔 | side-0.5 | 0.044 | 0.082 | 0.082 | 64 |
| 지도 끔 | diag-fwd+side+ | 0.051 | 0.061 | 0.080 | 64 |
| 지도 끔 | diag-fwd+side- | 0.064 | 0.052 | 0.083 | 64 |
| 지도 끔 | diag-back+side+ | 0.090 | 0.073 | 0.085 | 64 |
| 지도 끔 | diag-back+side- | 0.073 | 0.073 | 0.084 | 64 |
| 지도 끔 | stop | 0.019 | 0.014 | 0.073 | 64 |

원자료별 경로와 JSON 위치는 [command_cells.csv](data/command_cells.csv)의 source·pointer 열. 모든 경계가 들어 있어 좋은 저장본만 골라 낸 표가 아니다.

## 밀렸을 때 버티는가

![정기 밀기와 DR](figs/S2b-push-dr.png)

밀기는 속도를 순간적으로 바꾸는 시뮬 외란이다. 아래 숫자는 변위(m)가 아니라 **생존 비율**이다. 정기 검사는 걷기 명령 1.0에서, 단계 끝 판정은 걷기 명령 1.5에서 외란 1.5 m/s를 준다. 서로 같은 조건의 반복으로 합치지 않았다.

| 단계 끝 지형/지도 | 가장 약한 방향 생존 | 기존 기준 | 통과 |
| --- | --- | --- | --- |
| flat/eval_gt | 1.0000 | 0.90 | True |
| flat/eval_pred | 1.0000 | 0.90 | True |
| flat/probe_prop_only | 1.0000 | 0.90 | True |
| pyramid_stairs/eval_gt | 0.9688 | 0.90 | True |
| pyramid_stairs/eval_pred | 0.9688 | 0.90 | True |
| pyramid_stairs/probe_prop_only | 0.9688 | 0.90 | True |
| random_rough/eval_gt | 1.0000 | 0.90 | True |
| random_rough/eval_pred | 0.9688 | 0.90 | True |
| random_rough/probe_prop_only | 0.9844 | 0.90 | True |

단계 끝 등록 칸 9개 중 9개가 기존 기준을 넘었다. 반복 시드 검증 없이 차이를 확정적 일반화 성과로 부르지 않는다. [정기 전체 값](data/push250.csv) · [단계 끝 전체 값](data/push_stage_end.csv).

기록 전용 외란 2.0 m/s는 걷기 0.5 조건이다. 부모 m6000과의 차이는 [별도 표](data/push2_record.csv)에 보존했다. 이것을 걷기 1.5 판정의 개선율로 대신 쓰지 않는다.

## W57: 직진 중 방향과 돌고 멈추기

| 지도 | 명령/목표각 | 생존/64 | 시작 대비 마지막 yaw(도) | 목표 정지 오차(도) | 정지 후 wz 절댓값(rad/s) |
| --- | --- | --- | --- | --- | --- |
| GT 정답 | fwd0.5 | 64 | 7.82 | 미측정 | 미측정 |
| GT 정답 | fwd1.0 | 64 | 4.64 | 미측정 | 미측정 |
| GT 정답 | goal_left_delta000 | 64 | -3.27 | 3.30 | 0.071 |
| GT 정답 | goal_right_delta000 | 64 | -3.27 | 3.30 | 0.071 |
| GT 정답 | goal_left_delta030 | 64 | 26.38 | 3.66 | 0.076 |
| GT 정답 | goal_right_delta030 | 64 | -28.81 | 1.86 | 0.076 |
| GT 정답 | goal_left_delta060 | 64 | 56.58 | 3.42 | 0.072 |
| GT 정답 | goal_right_delta060 | 64 | -56.19 | 3.83 | 0.076 |
| GT 정답 | goal_left_delta090 | 64 | 85.71 | 4.29 | 0.078 |
| GT 정답 | goal_right_delta090 | 64 | -89.56 | 1.68 | 0.075 |
| 지도 끔 | fwd0.5 | 64 | 7.67 | 미측정 | 미측정 |
| 지도 끔 | fwd1.0 | 63 | 4.11 | 미측정 | 미측정 |
| 지도 끔 | goal_left_delta000 | 64 | -3.27 | 3.29 | 0.073 |
| 지도 끔 | goal_right_delta000 | 64 | -3.27 | 3.29 | 0.073 |
| 지도 끔 | goal_left_delta030 | 64 | 25.33 | 4.67 | 0.078 |
| 지도 끔 | goal_right_delta030 | 64 | -30.17 | 1.61 | 0.077 |
| 지도 끔 | goal_left_delta060 | 64 | 58.31 | 1.89 | 0.073 |
| 지도 끔 | goal_right_delta060 | 64 | -56.19 | 3.93 | 0.078 |
| 지도 끔 | goal_left_delta090 | 64 | 85.63 | 4.37 | 0.078 |
| 지도 끔 | goal_right_delta090 | 64 | -89.78 | 1.80 | 0.076 |
| Pred 복원 | fwd0.5 | 64 | 9.13 | 미측정 | 미측정 |
| Pred 복원 | fwd1.0 | 64 | 4.46 | 미측정 | 미측정 |
| Pred 복원 | goal_left_delta000 | 64 | -3.24 | 3.32 | 0.071 |
| Pred 복원 | goal_right_delta000 | 64 | -3.24 | 3.32 | 0.071 |
| Pred 복원 | goal_left_delta030 | 64 | 26.23 | 3.82 | 0.075 |
| Pred 복원 | goal_right_delta030 | 64 | -28.85 | 1.86 | 0.076 |
| Pred 복원 | goal_left_delta060 | 64 | 56.86 | 3.29 | 0.072 |
| Pred 복원 | goal_right_delta060 | 64 | -55.71 | 4.29 | 0.076 |
| Pred 복원 | goal_left_delta090 | 64 | 85.78 | 4.21 | 0.077 |
| Pred 복원 | goal_right_delta090 | 64 | -89.88 | 1.56 | 0.075 |

yaw는 몸이 수평으로 돌아간 각도다. 전진의 부호 있는 중앙값은 좌·우 오차가 상쇄될 수 있으므로 전원 정확하다는 뜻이 아니다. 목표 회전은 속도만 맞추는 spin 평가와 달리 목표 각도로 돌고 멈추는 검사다.

## 보행 위상과 발 기록

![접촉 막대](figs/S2b-contact.png)

![위상 분포](figs/S2b-phase.png)

| 모드/전진 | FL↔RR 오차° | FR↔RL 오차° | 대각 쌍간 오차° | R 중앙 | 주기 s | 유효 env/주기 수 | 네 발 접촉 C |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GT 정답/fwd0.5 | 49.5 | 35.2 | 13.9 | 0.760 | 0.660 | 64 / 520 | 0.066 |
| GT 정답/fwd1.0 | 36.1 | 17.9 | 5.0 | 0.914 | 0.440 | 64 / 811 | 0.035 |
| Pred 복원/fwd0.5 | 50.3 | 34.1 | 11.6 | 0.821 | 0.670 | 64 / 532 | 0.066 |
| Pred 복원/fwd1.0 | 37.4 | 19.9 | 6.1 | 0.929 | 0.440 | 64 / 799 | 0.033 |
| 지도 끔/fwd0.5 | 47.2 | 35.0 | 12.7 | 0.799 | 0.695 | 64 / 522 | 0.063 |
| 지도 끔/fwd1.0 | 39.5 | 24.4 | 10.9 | 0.920 | 0.440 | 64 / 791 | 0.033 |

| 모드/전진 | FL duty | FR duty | RL duty | RR duty |
| --- | --- | --- | --- | --- |
| GT 정답/fwd0.5 | 0.701 | 0.612 | 0.526 | 0.572 |
| GT 정답/fwd1.0 | 0.603 | 0.554 | 0.530 | 0.534 |
| Pred 복원/fwd0.5 | 0.704 | 0.617 | 0.536 | 0.564 |
| Pred 복원/fwd1.0 | 0.610 | 0.558 | 0.530 | 0.533 |
| 지도 끔/fwd0.5 | 0.693 | 0.603 | 0.523 | 0.581 |
| 지도 끔/fwd1.0 | 0.625 | 0.552 | 0.516 | 0.537 |

풀이: 대각 발 쌍 안은 동시에 딛는 0°, 쌍 사이는 번갈아 딛는 180°에서 얼마나 벗어났는지 본다. 표는 env별 원형 평균의 절대 오차 중앙값이다. R은 한 env 안의 주기들이 같은 위상으로 모이는 정도이며 1에 가까울수록 일정하다. duty는 각 발이 바닥을 딛은 시간 비율, C는 네 발이 동시에 딛은 시간 비율이다. 완전한 두 착지 사이만 세며 죽거나 기록이 끊긴 주기는 제외한다. C가 낮다는 것만으로 좋은 보행이라 할 수 없다.

식은 과거 ex35-final-audit/recompute.py의 완전 주기식을 재사용하되, 고정 200 Hz 대신 각 NPZ의 실제 dt를 썼다. 동시·반대 위상·주기 결손을 답을 아는 입력으로 확인했다. [env별 원수치](data/phase_env.csv) · [집계](data/gait_summary.json).

발 끌림·스윙 높이·무릎 부하의 학습 중 시계열도 [w86_training.csv](data/w86_training.csv)에 남겼다. 이것은 변화하는 학습 분포의 기록이므로 고정 지형 평가와 동일시하지 않는다. 발자국 XY 원자료는 이번 W57 NPZ에 없고 root_xy만 있어 새 발자국 평면도를 만들지 않았다.

## 학습 곡선: 아직 배우는가

![학습 곡선](figs/S2b-training.png)

![보상 항](figs/S2b-reward-terms.png)

| 지표 | 단계 첫 50갱신 중앙값 | 마지막 50갱신 중앙값 |
| --- | --- | --- |
| Train/mean_reward | 40.119526 | 41.835623 |
| Train/mean_episode_length | 989.795013 | 996.959991 |
| Policy/mean_noise_std | 0.494447 | 0.469960 |
| Loss/value_function | 0.020442 | 0.013327 |
| Loss/learning_rate | 0.000171 | 0.000171 |

학습률 ≤1.00001e-5는 152/2000갱신, PPO KL probe >0.05는 49/2000갱신이다. KL probe는 정책 변화의 로그값이지 실기 안정성을 직접 뜻하지 않는다. 이 횟수는 기존 경계 보고와 같은 모니터 항목이며 새 중단 기준이 아니다.

학습률(lr)은 한 번에 정책을 바꾸는 크기, std는 행동 표본의 퍼짐, value loss는 예상 보상과 실제 학습 목표의 차이다. 보상/길이는 두 평균의 비이며 모든 전이의 보상을 다시 평균한 정확한 step 보상이 아니다. 시작 직후에는 에피소드 통계가 채워지는 영향이 있으므로 초기 상승을 새 보행 습득으로 곧바로 해석하지 않는다.

보상이 내려갈 때는 과제가 어려워졌는지와 같은 고정 평가도 나빠졌는지를 같이 본다. 이 판은 DR·지형과 명령 분포가 바뀌어 보상만으로 망각을 판정할 수 없다.

## W78 v2와 남은 확인

**조각 결과 대기(scripter 진행 중)**. 전체 조합의 통과율·지형별 숙련도·P3 전체 대칭 결론은 이 문서에서 비워 둔다. 점수 파일 안의 정기 옆걸음 일부를 전체 W78 v2의 완료 결과로 대신하지 않았다.

영상은 선택한 GT 세 경우의 표본 프레임만 확인했다. 세 모드 전 명령의 실시간 판독·발자국 XY·단계 끝 전체 영상 묶음 완결성은 별도다. 따라서 N1 모든 축 완료나 다음 단계 승인을 이 보고서가 선언하지 않는다.

## 재현과 근거 등급

- 실측: JSON/NPZ/TensorBoard에서 재계산한 표와 그림. 원자료 경로·SHA256은 [source_manifest.json](data/source_manifest.json).
- 시각 관찰: 이 문서의 프레임 띠. 해독 성공과 정상 보행 판독은 구별한다.
- 코드: [generate_reports.py](generate_reports.py) · [extract_media.py](extract_media.py) · [write_reports.py](write_reports.py) · [verify_artifacts.py](verify_artifacts.py). 학습·평가 코드는 수정하지 않았다.
- 재대조: [verification.json](data/verification.json). 원자료에서 명령 오차·생존을 별도 재계산하고 평가 모듈 해시·지형 해시·배치·시간 간격의 동일성을 확인한다. dr_off는 원문에 열거된 비활성 항목이며 모든 외란·잡음이 꺼졌다는 뜻으로 확대하지 않는다.
- 해석: 무엇을 배웠나·회귀 의심·다음 단계에 준 영향. 새 원인을 확정하거나 새 문턱을 소급 적용하지 않았다.
- 미확인: 반복 시드 일반화·전체 영상 판독·W78 v2 완결 판정.

```powershell
$env:PYTHONUTF8="1"; $env:PYTHONDONTWRITEBYTECODE="1"
& C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe generate_reports.py
& C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe extract_media.py
& C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe write_reports.py
& C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe verify_artifacts.py
```

운영 원본이 자라는 동안 다시 실행하면 채집 시점과 해시가 달라진다. 본문·그림의 재현에는 커밋에 포함된 CSV/JSON을 고정 입력으로 쓰고, 원자료 재집계는 manifest의 해시와 대조한다. TensorBoard 읽기 사본은 D:/mai-tmp/analyst/ex41-stage-reports-1106에 있다. 원본 파일·프로세스·GPU·운영 원장을 변경하지 않았다.
