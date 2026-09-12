> 분류: 운영
> 작성: Claude 세션 (오흥재 지시) · 2026-09-11 18:27
> 근거: 우리 raw CSV 27열 실측 · 임석헌 episodes.csv 45열·obstacles.csv 27열 (S3 원본) · 시계열 parquet 93열 실측 (foothold-trace/2 · 2026-09-11 에 `yaw_deg` 가 붙어 92 -> 93)
> 요지: 두 CSV 를 합쳐 FOOTHOLD 판 하나로. 59열을 구현했고 센서는 하나도 안 붙였다. 장애물 묶음만 v1.1 로 남았다
> 상태: 확정 (2026-09-11 구현 · 59열이 실제로 나온다)
> 판: v1.0

# FOOTHOLD 평가 CSV 설계 v1

## 왜 지금인가

접촉 센서를 붙이려면 **다시 돌려야** 합니다. 어차피 한 번 돌릴 거라면
**CSV 를 먼저 확정하고 한 번만** 돌리는 것이 맞습니다. 지금 돌리면 두 번 돌립니다.

## 지금 두 벌이 무엇을 재고 있나

| | 우리 `generalization_raw.csv` | 임석헌 `episodes.csv` |
|---|---|---|
| 열 | 27 | 45 |
| 성격 | **판정** | **진단** |
| 이름이 겹치는 열 | `duration_s` 하나뿐 | |

**서로 다른 것을 재고 있습니다.** 우리는 「통과했나」를, 그는 「어떻게 통과했나」를 봅니다.
합치면 **판정은 우리 것, 진단은 그의 것**입니다.

---

## FOOTHOLD 판 v1 · 네 묶음

### 묶음 1 · 판정 (우리 것 그대로 · 27열)

바꾸지 않습니다. 지금 성적표의 근거입니다.

```
terrain · env_id · episode
start_x_offset_m · start_y_offset_m · start_yaw_deg
overall_success
survival_success · progress_success · tracking_success · direction_success
traversal_success
termination_reason · duration_s
forward_progress_m · ideal_distance_m · progress_ratio
lateral_drift_m · peak_lateral_drift_m · gate_lateral_drift_m
velocity_mae_mps · mean_reward_per_step
gate_speed_mps · speed_drop_ratio
head_contact_count · head_contact_peak_n · head_contact_first_s
```

| `head_contact_*` 세 열 | **검증 전까지 인용 금지.** 규격 2 에서 `first_s` 값 25,296 행 중 5,979(23.6 %)이 0.0 인데, 그것만으로 오염 여부를 판별할 수 없다. 정본 7절 |

### 묶음 2 · 자세와 제어 (8열 · 지금 신호로 계산됨)

| 열 | 뜻 | 어느 신호에서 |
|---|---|---|
| `roll_abs_p95_deg` | 좌우 기울기 95분위 | `base_qw..qz` |
| `pitch_abs_p95_deg` | 앞뒤 기울기 95분위 | `base_qw..qz` |
| `surface_relative_pitch_abs_p95_deg` | 지면 기준 앞뒤 기울기 | 위 + 지형 높이 |
| `forward_velocity_rmse_mps` | 명령 대비 전진 속도 오차 RMS | `base_vx_w_mps` · `cmd_vx_mps` |
| `lateral_velocity_rms_mps` | 좌우 속도 RMS | `base_vy_w_mps` |
| `joint_torque_rms_nm` | 관절 토크 RMS | `joint_torque` 12 |
| `action_delta_rms` | 명령이 프레임마다 얼마나 바뀌나 | `joint_target` 12 |
| `foot_slip_distance_proxy_m` | 발이 땅에 닿은 채 미끄러진 거리 | `foot_x/y` 12 + `foot_contact` 4 |

### 묶음 3 · 부위별 접촉 (16열)

| 부위 | 열 넷 | 센서 |
|---|---|---|
| `foot_` | `peak_force_n` · `impulse_proxy_ns` · `contact_time_s` · `contact_events` | **있음** (`foot_contact_*_n`) |
| `thigh_` | 같음 | **붙여야 함** |
| `calf_` | 같음 | **붙여야 함** |
| `base_` | 같음 | **있음** (머리 접촉 센서 확장) |

> **허벅지와 종아리 접촉이 이 묶음의 값어치입니다.** 「몸통이 닿았다」만으로는
> 틈을 넘다 긁힌 것과 그냥 쓰러진 것을 못 가릅니다.

### 묶음 4 · 장애물 단위 (5열 + 별도 파일)

| 열 | 뜻 |
|---|---|
| `obstacles_total` | 이 지형에 장애물이 몇 개인가 |
| `obstacles_attempted` | 몇 개에 손을 댔나 |
| `obstacles_passed` | 몇 개를 넘었나 |
| `first_unpassed_obstacle` | 처음 막힌 것이 몇 번째인가 |
| `body_impulse_per_attempted_obstacle_ns` | 장애물 하나당 몸통 충격량 |

**그리고 별도 파일 `obstacles_raw.csv` 를 만듭니다.** 장애물마다 한 줄입니다.

```
episode_id · obstacle_index · kind · start_m · end_m · passed
entry_time_s · pass_time_s · entry_speed_mps
leading_front_foot                         어느 앞발로 먼저 디뎠나
FL/FR/RL/RR_first_landing_time_s           발마다 첫 착지 시각
FL/FR/RL/RR_landing_edge_margin_m          착지가 가장자리에서 몇 m 떨어졌나
edge_support_feet                          가장자리를 디딘 발이 몇 개인가
entry_roll_deg · entry_pitch_deg
recovery_time_proxy_s                      넘고 나서 자세를 되찾는 데 몇 초
```

> **영상에서 보이는 「앞발을 턱에 걸치는 동작」을 숫자로 재는 자리입니다.**
> `leading_front_foot` 과 `landing_edge_margin_m` 이 그것입니다.

### 묶음 5 · 재현 추적 (5열)

| 열 | 뜻 |
|---|---|
| `episode_id` | `<지형>_<규격>_d<난이도>_v<속도>_e<번호>` |
| `eval_spec_version` | 1 또는 2. **지금은 manifest 에만 있다** |
| `policy_sha256` | manifest 에서 옮긴다 |
| `seed` | 같음 |
| `run_id` | 실행 폴더 이름 |

**manifest 를 안 열어도 한 줄로 출처를 알 수 있게** 합니다. 여러 실행의 CSV 를
한 표로 합칠 때 이것이 없으면 섞입니다.

---

## 합치면

**2026-09-11 에 구현했다. 지금 나오는 것은 59열이다.**

```
27 (판정)  +  8 (자세·제어)  +  16 (접촉)  +  3 (험지 참여)  +  5 (추적)  =  59열
```

| 묶음 | 계획 | 지금 | 비고 |
|---|--:|--:|---|
| 1 판정 | 27 | **27** | 한 자리도 안 건드렸다 |
| 2 자세·제어 | 8 | **8** | |
| 3 접촉 | 16 | **16** | 센서를 새로 안 붙였다. 아래를 보라 |
| 4 장애물 | 5 + 별도 파일 | 0 | **아직이다.** 장애물마다 발 착지를 봐야 한다 |
| 5 추적 | 5 | **5** | |
| 신설 험지 참여 | . | **3** | 팀장 지시. 정본 7-2절 |

**묶음 3 은 센서를 안 붙여도 됐다.** 이 문서가 「허벅지·종아리는 붙여야 함」이라 적은 것은 틀렸다. `contact_forces` 가 `prim_path=".../Robot/.*"` 라 이미 강체 19개를 전부 덮고 있다 `확인됨`. 발 4 · 허벅지 4 · 종아리 4 · 몸통 3 으로 갈라 쓰면 된다.

**묶음 4 만 남았다.** 장애물 하나하나의 자리를 알아야 하고 걸음마다 착지 가장자리 여유를 재야 해서 따로 붙는다. v1.1 이다.

## 무엇이 다시 돌려야 하고 무엇이 아닌가

| 묶음 | 다시 돌려야 하나 | 왜 |
|---|---|---|
| 1 · 판정 | 아니오 | 이미 있다 |
| 2 · 자세·제어 8열 | **시계열이 있는 칸은 아니오** | `base_q*` · `joint_*` 로 계산 |
| 3 · 접촉 16열 중 발·몸통 8열 | **시계열이 있는 칸은 아니오** | `foot_contact_*_n` 이 있다 |
| 3 · 허벅지·종아리 8열 | **아니오** | ~~센서를 안 붙였다~~ `contact_forces` 가 이미 덮고 있었다 (2026-09-11 정정) |
| 4 · 장애물 | **예** | 발 착지 판정을 매 걸음 봐야 한다 |
| 5 · 추적 | 아니오 | manifest 에서 옮기면 된다 |

**그런데 시계열은 4,800 에피소드에만 있습니다.** 나머지는 계산할 재료가 없습니다.

> **결론: 한 번 다시 돌립니다.** 180칸 = 18,000 에피소드 · GPU 두 대로 약 5시간.
> 옛 규격 결과를 지우지 않으니 그것까지 다시 뽑을 필요는 없습니다.

---

## 어떻게 구현하나

**원칙 하나.** 새 열은 **에피소드가 끝날 때 한 번** 계산합니다. 시계열을 켜지
않아도 나와야 합니다. 하네스는 이미 걸음마다 자료를 들고 있습니다.

**원칙 둘.** 시계열 parquet 은 **원신호** 그대로 둡니다. 새 열은 그걸 접은 것이라
두 벌을 만들지 않습니다.

**원칙 셋.** `--legacy_csv` 로 27열만 내는 길을 남깁니다. 옛 도구가 안 깨지게.

### 단계

| | 무엇 | 다시 돌리나 |
|---|---|---|
| 1 | 묶음 2·5 (13열) 구현 · 시험 | 아니오 |
| 2 | 발·몸통 접촉 8열 구현 · 시험 | 아니오 |
| 3 | 허벅지·종아리 접촉 센서 붙이기 | |
| 4 | 장애물 단위 + `obstacles_raw.csv` | |
| 5 | `head_contact_first_s` 오염 고치기 | |
| 6 | **본 데이터 한 번에** 180칸 | **예** |

## 임석헌에게 물을 것

그의 열 정의를 모르면 이름만 같고 뜻이 다른 것이 생깁니다.

- `impulse_proxy_ns` 를 어떻게 계산하는가 (힘 x 시간의 합인가, 최대값 x 지속인가)
- `contact_events` 의 「한 번」을 어떻게 세는가 (문턱값과 최소 간격)
- `foot_slip_distance_proxy_m` 의 접촉 판정 문턱
- `surface_relative_pitch` 의 「지면」을 무엇으로 잡는가
- `recovery_time_proxy_s` 의 「되찾았다」 기준
- `edge_support_feet_proxy` 의 「가장자리」 폭

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v1.0 | 2026-09-11 | 처음 씀. 59열을 구현했고 장애물 묶음만 v1.1 로 남겨 두었다. 머리의 시각 `18:27` 은 **이 문서의 첫 커밋 시각**이다 (`21748a5`). 세션이 쓰고 같은 자리에서 커밋한 문서라 그렇게 적는다 | git 이력 |
