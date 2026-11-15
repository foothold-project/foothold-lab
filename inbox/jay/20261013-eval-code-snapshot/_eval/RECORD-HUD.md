> 분류: A/정책학습 · 평가 · 기록 규격 · HUD 영상
> 작성: 오흥재 (lead 세션 하위 작업 · Claude 실행) · 2026-10-12
> 근거: 팀장 10/12 「기존에 csv 남기는 항목을 많이 정리했는데 그 기준을 새 설계에 적용 못하나? 우리 HUD 를 활용하면 좋겠다」 · lab 저장소 `sim/eval/timeseries.py` · `overlay/trace.py` · `overlay/render.py` · `overlay/hud.py` · `eval_command_response.py` · `eval_generalization.py` · `record_terrain_demo.py` · `_out/loop/axis2_hud.py` (모두 읽기만) · `_eval/E2-and-records.md`
> 요지: full_record CSV (115 열) 를 lab 시계열 규격 93 열 parquet 과 HUD trace 17 열로 1:1 변환한다 (지시의 92 · 16 · 127 열은 재 보니 93 · 17 · 115). 같은 이름 다른 뜻 하나 (`base_z_m`) 는 우리 쪽 이름을 `base_z_w_m` 으로 바꿨다. 변환은 판정값 (MAE · 행 수) 으로 되접어 대조하고, 어긋나면 멈춘다. 1,657 편 모두 통과했다. 대표 영상 332 편에 lab HUD 를 얹고, 아래 띠에 「기록 재생」과 Q 판정을 적었다. 웹 사본 332 편은 419 MB 이고 모두 2 MB 아래다. 렌더러가 일부 프로세스에서 검정 · 하늘 프레임을 내던 결함 (24 편) 을 다시 만들었고, 렌더 · 발행 두 단계에 전 프레임 관문을 넣었다 (332 편 결함 0). 마찰력은 기록되지 않는다
> 상태: 판 2 (2026-10-12 21:40) · 판 1 (19:35) 에서 바뀐 곳: 프레임 결함 24 편 재렌더 · 렌더 · 발행 단계 프레임 관문 (5-1 절) · 웹 사본 합계 419.2 MB

# 전체 기록을 lab 기록 규격과 HUD 에 잇기

표기: **확인됨** = 이번에 재거나 답을 아는 입력으로 시험한 것 · **추정** = 잰 값에서 끌어낸 해석 · **미확인** = 재지 않은 것.
경로는 `C:/isaac/ext/go2_rl_robotlab/_eval/` 기준이다. lab 저장소 파일은 하나도 고치지 않았다. 불러서 쓰기만 했다. 커밋하지 않았다.

## 0. 규격을 재 보니 (확인됨)

| 지시에 적힌 것 | 잰 것 | 근거 |
|---|---|---|
| lab 시계열 92 열 | **93 열** (trace 17 + 몸통 · 명령 16 + 발 12 + 관절 4 × 12) | `timeseries.columns_for()` 를 Go2 관절 이름으로 돌림. 기존 parquet (`results/20260923-v2rs-axis2/.../ep0001.parquet`) 의 열 목록과 같음. `eval_command_response.py` 머리말도 「92 는 yaw_deg 가 들어오기 전 숫자」라고 적음 |
| HUD 용 trace 16 열 | **17 열** (`yaw_deg` 포함, schema foothold-trace/2) | `overlay/trace.TRACE_COLUMNS` |
| 새 full_record 127 열 | **115 열** | CSV 머리줄 |

## 1. 열 대응표

lab 의 93 열을 기준으로 적었다. 「새 열」은 full_record CSV 의 열이고, 「변환」은 `fr_to_legacy.py` 가 하는 일이다.

- 행의 뜻은 lab 시계열과 같다. k 행은 k 번째 step 을 밟기 **직전**의 상태다. full_record 의 0 행은 reset 직후다.
- 마지막 행은 마지막 step 을 밟은 뒤의 상태라서, 20 s cell 이면 lab 보다 한 행 많다 (1,001 행).
- 관절 열의 순서는 lab 과 같은 articulation 순서다 (FL · FR · RL · RR hip, … calf).
  - `q_video.py` 가 로봇에서 읽은 순서와 같다 (확인됨).
  - full_record CSV 는 action term 순서 (FL hip · thigh · calf, …) 로 적혀 있다. 이름으로 맞추므로 순서가 달라도 값은 같은 관절로 간다.

### 1-1. trace 17 열 (HUD 가 읽는 열, parquet 앞 17 열과 같다)

| lab 열 | 단위 · 좌표계 | 새 열 | 변환 |
|---|---|---|---|
| `frame` | 정수 | `step` | 그대로 |
| `t_s` | s | `t_s` | 그대로 (0.02 s 간격) |
| `cmd_vx_mps` | m/s · 몸통 | `cmd_vx_mps` | 그대로. 스텝마다 정책이 본 명령이다 (`eval_command_response.py` 와 같은 뜻. `eval_generalization.py` 는 상수를 적는다) |
| `vx_mps` · `vy_mps` | m/s · 몸통 | `linvel_body_x_mps` · `linvel_body_y_mps` | 그대로 |
| `speed_mps` | m/s | 계산 | √(vx² + vy²) |
| `vel_err_mps` | m/s | 계산 | √((vx − cmd_vx)² + (vy − cmd_vy)²). 두 시계열 하네스의 식이다. `record_terrain_demo.py` 는 \|vx − cmd_vx\| 를 적는다 (판 사이에 이미 다름) |
| `fwd_m` · `lat_m` | m · **출발 축** | 계산 | 0 행의 base xy 와 0 행 몸통 +x 축 (평면 투영 · 정규화) 을 기준으로 lab `metrics.forward_offset_m` · `lateral_offset_m` 을 그대로 부른다. 왼쪽이 + |
| `base_z_m` | m · **지면 (env origin z) 기준** | `base_z_w_m` − floor_z | floor_z = 그 env 의 지형 origin z (`eval_generalization.py` 의 뜻). origin 은 q_eval 이 `env_origins.npy` 로 남긴다 (2절) |
| `pitch_deg` · `roll_deg` | deg | `quat_*` | lab `timeseries.euler_deg_from_quat` |
| `yaw_deg` | deg · **출발 축 대비 · 왼쪽 +** | `quat_*` | `trace.py` 의 정의대로 `record_terrain_demo.py` 561~563 행 식. `eval_command_response.py` 는 이 열에 세계 yaw 를 적는다 (그 하네스는 출발 yaw 가 0 이라 같아진다) |
| `foot_z_{fl,fr,rl,rr}_m` | m · floor 기준 | `{FL,FR,RL,RR}_foot_z_m` − floor_z | 위와 같은 floor_z |

### 1-2. 몸통 · 명령 16 열

| lab 열 | 단위 · 좌표계 | 새 열 | 변환 |
|---|---|---|---|
| `base_x_m` · `base_y_m` | m · 세계 | `base_x_m` · `base_y_m` | 그대로 (같은 이름 같은 뜻) |
| `base_z_w_m` | m · 세계 | `base_z_w_m` | 그대로. **이름을 바꿨다**: full_record 는 처음에 세계 z 를 `base_z_m` 이라 불렀다. lab 에서 `base_z_m` 은 지면 기준 높이라 같은 이름 다른 뜻이 된다. CSV 1,167 개 머리줄과 `full_record.py` 를 고쳤다 (값은 그대로) |
| `base_qw` … `base_qz` | wxyz | `quat_w` … `quat_z` | 그대로 |
| `base_yaw_deg` | deg · 세계 | `quat_*` | euler yaw |
| `base_v{x,y,z}_w_mps` | m/s · 세계 | `linvel_world_{x,y,z}_mps` | 그대로 |
| `base_w{x,y,z}_rps` | rad/s · **몸통** | `angvel_body_{x,y,z}_radps` | 그대로 (lab 도 몸통 좌표계) |
| `cmd_vy_mps` | m/s · 몸통 | `cmd_vy_mps` | 그대로 |
| `cmd_wz_rps` | rad/s | `cmd_wz_radps` | 그대로 (이름만 다름) |

### 1-3. 발 12 열

| lab 열 | 단위 · 좌표계 | 새 열 | 변환 |
|---|---|---|---|
| `foot_{x,y}_{slot}_m` | m · 세계 | `{FT}_foot_{x,y}_m` | 그대로 |
| `foot_contact_{slot}_n` | N | `{FT}_foot_force_vertical_N` · `{FT}_foot_normal_force_horizontal_N` | √(Fz² + Fh²) = 그 상태 직전 5 ms substep 의 normal 접촉력 크기. **`eval_command_response.py` 와 같은 뜻 (「지금」 힘)** 이다. `eval_generalization.py` 는 같은 이름에 3 칸 이력의 최댓값을 적는다. 그 값은 full_record 로는 만들 수 없다. parquet 메타 `foot_contact_semantics` 에 적었다 |

### 1-4. 관절 48 열

| lab 열 | 단위 | 새 열 | 변환 |
|---|---|---|---|
| `joint_pos_<j>` | rad | `q_<j>_rad` | 그대로 |
| `joint_vel_<j>` | rad/s | `dq_<j>_radps` | 그대로 |
| `joint_torque_<j>` | N·m | `tau_<j>_Nm` | 그대로 (`applied_torque`) |
| `joint_target_<j>` | rad | `target_<j>_rad` | **한 행 미룬다.** lab 은 step 직전에 `joint_pos_target` 을 읽는다. 그 값은 앞 step 에서 걸린 목표, 곧 앞 행 action 의 목표다. full_record 의 `target` 은 그 행에서 계산한 action 의 목표라서, lab k 행 = 새 k − 1 행이다. 0 행은 빈 칸 |

### 1-5. 새것에만 있는 열 (27 개, lab 93 열에 자리가 없다)

- `linvel_body_z_mps` · `angvel_world_{x,y,z}_radps` · `gravity_body_{x,y,z}`
- `ground_z_m` (발밑 스캐너 평균) · `base_height_above_ground_m` (base z − ground_z)
  - lab 의 `base_z_m` 은 env origin 기준이라 뜻이 다르다. 계단 위에서는 둘이 다르다.
- `{FT}_foot_contact` (\|normal\| > 1 N 표시) · `terminated` · `time_out`
- `action_<j>` 12 개 (정책 원출력)
- 발 normal force 의 수직 · 수평 성분 따로. lab 은 크기 하나만 둔다.

### 1-6. lab 에만 있고 새것으로 못 채우는 것

- `foot_contact_*_n` 의 `eval_generalization.py` 판 뜻 (3 칸 이력 최댓값). 위 1-3.
- 그 밖의 93 열은 모두 채운다. 빈 칸은 `joint_target_*` 의 0 행 하나다.
- floor_z 를 모르는 실행에서는 `base_z_m` · `foot_z_*_m` 도 빈 칸이다 (`--no_floor`). 2절에서 모든 실행의 origin 을 받았다.

### 1-7. 마찰력은 어디에도 없다

full_record 의 발 힘은 normal force 뿐이다. Isaac Lab `net_forces_w` 가 normal force 만 담기 때문이다 (`E2-and-records.md` A 절 정정). lab 시계열도 같은 센서를 쓰므로 lab 쪽에도 마찰력은 없다 (`eval_command_response.py` 970~990 행 확인).

## 2. 변환기 `fr_to_legacy.py`

- 입력: full_record CSV 한 편 · 그 실행의 `episodes_summary.csv` · `meta.json` · 지형 원점 `env_origins.npy`.
- 출력 둘:
  - `out/legacy/<tag>/timeseries/<지형>_<cell>_ep<번호>.parquet`: 93 열. lab `timeseries.write()` 를 그대로 불러 쓴다 (zstd · byte_stream_split · 메타는 스키마 key-value).
  - `out/legacy/<tag>/trace/<…>.trace.csv`: 17 열. lab `trace.write()` 로 쓴다 (schema foothold-trace/2).
- 쓴 뒤에 lab `timeseries.read()` · `trace.read()` 로 되읽는다. 두 함수의 자체 검사 (frame 번호 · t_s 간격) 를 통과해야 한다.
- 메타에 뜻이 갈리는 열의 정의를 적는다.
  - `foot_contact_semantics` · `yaw_deg_semantics` · `joint_target_semantics` · `floor_z_m` 과 그 출처
  - 원본 CSV 경로 · checkpoint · lab HEAD 와 lab 파일 sha256
- **판정값과 어긋나면 소리를 낸다.** `verify_against_row()` 와 같은 뜻으로, 변환한 줄을 다시 접어 그 episode 의 q_post 값과 견준다.
  - 견주는 것: MAE vx · vy · wz (같은 창: 첫 1 s 제외, 정지 cell 은 전환까지, 넘어지기 직전까지) · 행 수.
  - 어긋나면 `ConversionError` 로 멈추고, 그 episode 는 쓰지 않는다.
- 20000 · 20499 실행은 원점을 따로 받았다 (`run_org.sh`: 같은 인자의 `--fingerprint_only` 실행 36 개).
  - `convert_all.py` 가 원래 실행과 짝 fingerprint · 메시 · 인자 · origin 표 hash 가 같은지 먼저 본다. 다르면 멈춘다. 36/36 같았다.
  - 19500 실행 18 개는 실행이 원점을 직접 남겼다.

### 시험 (확인됨, `fr_to_legacy_test.py` · `legacy_checks.py`)

| 시험 | 답 | 결과 |
|---|---|---|
| 합성 행: 출발 (0,0) +x, 다음 (1,0) 왼쪽 90도, 다음 (0,1) | fwd 1 · lat 0 / fwd 0 · lat +1 (왼쪽 +) / yaw_deg 90 · base_yaw_deg 90 | 모두 맞음 (1e-5 안) |
| 합성 행: 속도 (0.3, 0.4) · 명령 (0.3, 0) | speed 0.5 · vel_err 0.4 | 맞음 |
| 합성 행: 수직력 30 N · 수평 40 N | foot_contact 50 N | 맞음 |
| 합성 행: floor 0.1 · 세계 z 0.5 | base_z_m 0.4 · base_z_w_m 0.5 | 맞음 |
| 합성 행: target 0.11 · 0.22 · 0.33 | joint_target 빈칸 · 0.11 · 0.22 (한 행 미룸) | 맞음 |
| 서 있기 (E1 20499 flat stand 2 편) | 네 발 접촉력 합 / mg = 1 | 1.0005 · 1.0016 |
| 걷기 (fwd05 · yawL05 5 편): 토크 = Kp (joint_target − q) − Kd dq | 한 행 미룬 쪽이 잔차가 작아야 | 5/5 미룬 쪽이 작음 (예: 0.013 대 0.052 N·m). 잔차가 0 이 아닌 것은 actuator 지연 0~4 substep 때문 (추정) |
| 판정값 대조가 실제로 울리는가 | mae_vx 를 0.001 바꾸면 실패 | 울림 |
| 전 episode 되읽기 | 54 tag · 1,657 편, 93 열, lab read 통과, 판정값 대조 실패 0 | 맞음 |
| 지면 기준 높이 | 0 행 base_z_m 이 출발 높이 0.40 m (GO2_CFG_UNITREE) + 균등 0~0.20 m 안 | 1,657 편 모두 0.4005~0.5982. 원점을 일부러 0 으로 주면 계단에서 −0.90 이 나와 걸린다 |
| 열 순서 | lab 기존 parquet 의 93 열 목록과 같음 | 같음 |

크기 (확인됨): parquet 1,657 개 428,363,637 B (0.43 GB) · trace CSV 1,657 개 370,959,951 B (0.37 GB).

## 3. HUD 얹기

### 방법

- HUD 용 원본 영상을 다시 찍었다 (`q_video.py --overlay label`).
  - 기존 기록 재생 영상은 왼쪽 위 글상자가 HUD 자리 (화면 위 28 %) 와 겹친다.
  - 같은 기록 재생에서 글자를 아래 띠로 옮겼다. 띠는 세 줄이다.
    1. 「기록 재생 (운동학 · 물리 재계산 아님)」 · tag · episode
    2. **Q 판정** 한 줄. 그 episode 의 `episodes.csv` 값을 그대로 읽는다 (lead 10/12 지시).
       - 예: 「Q 판정: 미달 · MAE vx 0.151 > 0.15 (Q-E1 임시 조건 · 현행 정의)」
       - 예: 「Q 판정: 미달 · 정지까지 1.54 s (> 1 s)」
       - 넘어진 경우: 「넘어짐 t s (몸통 접촉 · 60도 넘게 0.2 s 기울어짐 · 지지면 아래)」
    3. 명령 vx · vy · wz 와 실제 vx · vy · wz
  - PhysX 는 CPU, 렌더는 GPU 1 이고 감시를 걸었다. 메시 hash · 발 위치 대조는 기록 재생 영상과 같다.
- HUD 는 lab `overlay/render.py` 의 `render()` 를 그대로 불렀다 (`hud_make.py`).
  - `mode="flat"`, `trace_obj` 는 93 열 parquet 을 감싼 trace 다. `_out/loop/axis2_hud.py` 의 `build_trace` 와 같은 방법이다.
  - 영상과 자료의 정렬 검사 (fps · 길이 · 장수) 는 render.py 가 한다. 전 편 통과했고, 장수와 행 수가 같았다.
- **모든 cell 을 flat 모드로 했다** (lead 동의).
  - terrain 모드의 판정 램프 넷은 축 1 판정 (통과선 · MAE 0.25 · 이탈 0.05 m) 이다. Q 와 다른 통과 · 실패를 화면에 말하게 되어 뺐다.
  - Q 판정은 아래 띠에 적는다.
- 좌우 이탈 게이지의 기준선만 Q corridor 0.30 m 로 넣었다 (trace 메타 `max_lateral_drift_m`). 기본값 0.05 m 는 축 1 기준이다.
- HUD 제목은 HUD 글꼴 부분집합 안의 글자 34 자 이하다 (lab `hud.validate_title` 로 확인). 예: 「E2 19500 B:stairs_up yawL05 ep12」. `B:` 는 띠 출발이다.

### 페이지 범례에 적어야 할 HUD 의 읽는 법 (lead 가 적는다)

- 속도 점의 빨강은 「명령 최대값 대비 느림」이다. 정지 구간에서는 뜻이 없다. render.py 에 기준을 바꾸는 인자가 없어 그대로 두었다 (`render()` 인자 확인).
- HUD 에는 vy 명령 칸이 없다. right03 같은 횡이동 cell 은 HUD 에 「명령 vx 0」으로 보인다. 아래 띠에서 읽는다.
- 횡이동 cell 의 좌우 이탈 게이지는 명령된 옆걸음 거리를 그대로 보여 준다 (예: −2.27 m, 끝에 붙음). lab 정의 (출발 축 기준 좌우) 대로라 값은 맞지만 이탈이 아니다.

### 한 편 먼저 (확인됨)

- 첫 편은 E1 20499 stairs_up 중앙 stop03 ep1 이다. 프레임 4 장을 lead 가 직접 봤다 (f0225 · f0450).
  - 확인 받은 것: 발이 디딤판 위에 있다 · 5 s 전환이 보인다 · 아래 띠가 맞다.
- 그 뒤 Q 판정 줄을 더해 다시 만들었다. 경로는 같다.
- 첫 묶음 안에서는 띠 셋째 줄과 횡이동 게이지를 프레임으로 다시 봤다 (e2_m20499 flat back03 ep29 · e2fr_m19500 stairs_up right03 ep0).

## 4. 웹 사본

- `hud_make.py` 가 HUD 영상에서 ffmpeg (imageio-ffmpeg 7.1 바이너리) 로 만든다. 원본은 그대로 둔다.
  - 형식: H.264 · yuv420p · `+faststart` · 소리 없음 · 높이 720 이하.
  - crf 28 로 시작한다. 2 MB 를 넘으면 crf 31 · 33 · (540p) 31 · 34 · 36 순으로 올린다.
- 고른 목록 (`hud_select.py` → `out/hud_sel.json` · 칸 표 `out/hud_sel_slots.csv`)
  - E1 · E2 × model_20499 · model_19500
  - 지형 8 종 중앙 × stop03 · fwd01 · fwd05 · back03 · right03 · yawL05
  - 띠 출발 stairs_up · stairs_down · slope_up · slope_down × stop03 · yawL05 (띠 출발 실행의 cell 이 stand · stop03 · yawL05 · yawR05 라서)
  - 칸마다 첫 성공 · 첫 실패. 실패가 없는 칸은 비운다.
  - 448 칸 가운데 332 편이고, 빈 116 칸은 그 cell 에 실패 episode 가 없던 자리다.
- 19500 은 기록이 없어서 새로 돌렸다. E1 · E2 model_19500 Q 주 실행 noise 끔 `--full_record` 18 실행이고, 저장된 실행과 traj 9/9 · 9/9 bitwise 같다.

## 5. 결과와 크기 (확인됨)

### 첫 묶음 (18:00 보고, lead 가 페이지에 올림)

- 범위: E1 · E2 × 20499 · 19500 × (평지 중앙 · stairs_up 중앙 6 cell, stairs_up 띠 출발 2 cell) × 첫 성공 · 첫 실패
- 112 칸 가운데 85 편이 나왔다. 빈 27 칸은 실패 episode 가 없던 자리다.
- 웹 사본 합계 106.9 MB · 가장 큰 것 1,991,208 B. 목록은 `out/web_list_batch1.md` · `.csv`.
- lead 재측정 (lead 가 알려 온 값):
  - E12 표 16 칸과 116 cell 평균 6 개가 episodes.csv 직접 집계와 같았다.
  - 85 편 아래 띠의 판정 줄이 전부 episodes.csv 의 판정 열과 같았다.
  - E1 GPU 1 대 GPU 0 재실행 3 묶음이 bitwise 같았다.

### 전체

| 무엇 | 편 · 파일 | 크기 |
|---|---|---|
| 웹 사본 (`out/web/<tag>/…_kinreplay_hud_web.mp4`) | 332 | 419.2 MB (24 편 재렌더 뒤) · 가장 큰 것 1,999,210 B · 2 MB 넘는 것 0 |
| HUD 영상 원본 (`out/video_hud/<tag>/…_kinreplay_hud.mp4`, 1280 × 720 · 50 fps · crf 20) | 332 | 1,253.6 MB |
| HUD 용 기록 재생 원본 (`out/video_hud_src/<tag>/…_kinreplay.mp4`, 아래 띠 판) | 332 | 5,488.8 MB |
| lab 규격 parquet (`out/legacy/<tag>/timeseries/*.parquet`, 93 열) | 1,657 | 428.4 MB |
| lab 규격 trace CSV (`out/legacy/<tag>/trace/*.trace.csv`, 17 열) | 1,657 | 371.0 MB |

- 실행별 편 수: E1 20499 91 · E2 20499 87 · E1 19500 76 · E2 19500 78.
- 웹 사본 인코딩: crf 28 · 720p 302 편, crf 31 · 720p 30 편. 540p 로 내려간 것은 없다.
- 검사 (`hud_sizes.py` · `web_list.py`):
  - HUD 332 편 모두 영상 장수 = 자료 행 수 · 50 fps.
  - 웹 사본 332 편 모두 h264 · 높이 720 · faststart.
    - faststart 는 파일 앞 4 KiB 에 moov 가 mdat 보다 먼저 있는지로 본다.
    - 이 판별이 실제로 가르는지도 봤다: PyAV 로 쓴 HUD 원본은 「아님」으로 걸린다.
  - 332 편 모두 아래 띠 판정 줄 (통과 · 미달) 이 episodes.csv 의 판정 열과 같다. 고른 이유 (첫 성공 · 첫 실패) 와도 같다.
- 전체 목록: `out/web_list.md` · `out/web_list.csv`.
  - 열: 실행 · model · HUD 제목 · 고른 이유 · Q 판정 줄 · 웹 사본 경로 · 크기 · crf · HUD 원본 경로.
  - 칸 표 (빈 칸 포함): `out/hud_sel_slots.csv`.

### 5-1. 프레임 결함 24 편과 관문 (20:00 팀장 지적 · lead 전수 검사)

- 지적: 웹 사본 가운데 24 편에 의미 없는 프레임이 있었다.
  - 다시 센 값 (확인됨): fr_m20499_slope_up 8 · e2fr_m19500_slope_up 7 · e2fr_m19500_stairs_down 9 편. 지시의 8 · 8 · 8 과 칸 배분은 다르고 합은 같다.
  - 「하늘」: 3D 영역이 지형도 로봇도 없는 하늘 그라데이션뿐인 프레임이 연속 구간으로 나온다. 36~62 % 프레임.
  - 「검정」: 정확히 홀수 프레임 전부가 3D 영역 검정이다 (500/1001).
- 원인 (확인됨 · 추정 · 미확인을 나눈다)
  - 확인됨: 결함은 HUD · 인코딩 전, 아래 띠 기록 재생 원본에 이미 있었다. 원본 24 편이 모두 같은 검사에 걸렸다.
  - 확인됨: 같은 CSV 행을 다른 프로세스에서 찍으면 깨끗하다.
    - fr_m20499_slope_up back03 ep0 의 기록 재생 영상 (B 판, 다른 프로세스) 은 전 프레임 결함 0 이다.
    - 결함 편 둘을 다시 찍으니 전 프레임 0 이다.
    - 재생한 발 위치 대 CSV (2.0e-5 m) · 메시 hash 는 결함 판과 정상 판이 같다.
    - 그래서 카메라 자세나 지형 쪽 문제가 아니다.
    - 카메라는 몸통을 고정 오프셋으로 따라가므로, 몸통의 투영 화소가 모든 프레임에서 (584.1, 331.2) 다 (hfov 60°). 로봇은 기하적으로 언제나 화면 안에 있다.
  - 확인됨: 한 q_video 프로세스가 찍은 편이 통째로 걸린다 (프로세스 단위).
  - 확인됨: 같은 결함이 기록 재생 영상 (B) 에도 있었다 (`E2-and-records.md` B 절). PhysX GPU · CPU, 렌더 프로세스 1 개 · 2 개 동시, GPU 메모리 여유와 무관하게 나왔다.
  - 추정: Isaac RTX 렌더러의 viewport 캡처가 일부 프로세스에서 빈 버퍼 (검정) 나 기하가 그려지지 않은 프레임 (하늘) 을 돌려준다. 기전은 미확인이다.
  - 확인됨: 지금까지 못 잡은 까닭.
    - 제 PNG 확인은 0 · 25 · 50 · 75 · 100 % 행, 곧 0 · 250 · 500 · 750 · 1000 이라 모두 짝수 프레임이었다.
    - 영상별 JSON 검사는 운동학 (FK · 메시 · 발 높이) 만 보고 화소를 보지 않았다.
- 고친 것: 관문 둘. 둘 다 먼저 결함을 넣어 깨 보고 넣었다.
  1. 렌더 단계 (`q_video.py`)
     - 매 프레임 3D 영역 (y 224~616) 을 lead `audit_frames.py` 와 같은 기준으로 본다: 평균 밝기 < 20 · 밝기 표준편차 < 6 · 파랑 우세 화소 > 35 %.
     - 투영한 몸통 화소가 화면 안이고 그 주변 창이 검정이 아닌지도 본다.
     - 실패한 프레임은 최대 12 번 다시 렌더한다. 그래도 실패하면 그 영상을 쓰지 않고 (`.rejected`) 프로세스를 멈춘다.
     - 실행기 (`rerender_runner.py`) 는 그 tag 를 새 프로세스로 최대 3 번 다시 돌린다.
     - 깨 보기 (확인됨):
       - 하늘 1 프레임 주입 → 1 회 재렌더로 회복.
       - 검정 1 프레임 주입 → 1 회 재렌더로 회복.
       - 하늘 계속 주입 → 12 회 뒤 중단, 영상 없음.
     - 오검출 하나를 고쳤다. 처음에는 몸통 주변 창에도 파랑 검사를 걸었다.
       - 넘어지며 뒤집힌 로봇의 그늘진 배를 하늘로 읽어 정상 프레임을 거부했다 (e2_m20499_rough_slope fwd01 ep83 frame 168, 프레임을 열어 확인).
       - 창의 색 검사는 뺐다. 하늘만 남은 프레임은 영역 전체 파랑 검사가 잡는다.
  2. 발행 단계 (`hud_make.py`)
     - HUD 영상과 웹 사본의 **모든 프레임**을 `frame_audit.audit` 로 검사한다.
     - 결함이 한 장이라도 있으면 그 파일을 `out/_rejected/` 로 옮기고, 웹 사본을 내지 않고, exit 3 으로 끝난다. 다른 편은 계속 만든다.
     - 깨 보기 (확인됨): 정상 판은 통과했다. 홀수 검정 250/501 · 하늘 구간 60/501 · 검정 한 장 1/501 은 모두 거절됐다.
     - 검정 한 장은 4 fps 표본 검사로는 0 으로 나왔다. 그래서 관문은 모든 프레임을 본다.
- 다시 만든 결과 (확인됨)
  - 24 편의 아래 띠 원본 · HUD · 웹 사본을 새 렌더러로 다시 만들었다. 같은 경로 · 같은 이름이다.
  - 재렌더된 프레임은 0 이었다 (건강한 프로세스).
  - 옛 파일은 `out/_bad/` 아래 같은 상대 경로에 그대로 두었다 (목록 `out/_bad/moved.json`).
  - 332 편 전 프레임 검사:
    - 웹 사본 결함 0 · HUD 결함 0 (`out/frame_audit_web_allframes_after.json` · `out/frame_audit_hud_allframes_after.json`)
    - 4 fps 검사 0
    - lead `audit_frames.py` 사본을 고치지 않고 돌린 결과도 332 편 · flagged 0
  - 정상 판의 여유: 결함 아닌 332 편 전 프레임에서 표준편차 최소 12.1 · 파랑 우세 최대 0.052 · 평균 밝기 최소 126 이다. 기준과 거리가 멀다.
  - `web_list.csv` · `.md` 를 다시 만들었다.

## 6. 못 한 것 · 한계

- **마찰력 (접선력) 은 기록되지 않는다** (1-7 절). 필요하면 sensor 설정을 바꿔 평가를 다시 돌려야 한다.
- `eval_generalization.py` 뜻의 `foot_contact_*_n` (3 칸 이력 최댓값) 은 만들 수 없다. 우리 열은 `eval_command_response.py` 뜻이다.
- HUD 의 vy 명령 칸 · 속도 색 기준 · 횡이동 cell 의 좌우 게이지는 lab HUD 그대로다 (3 절 범례). lab 파일을 고치지 않는다는 원칙에 따랐다.
- HUD 판정 램프 (축 1) 는 그리지 않는다. Q 판정은 아래 띠 한 줄이다.
- 기록 재생 영상은 운동학 재생이다. 물리를 다시 돌린 것이 아니고, 판정에 쓰지 않는다.
- 웹 사본은 페이지용이다. 분석에는 HUD 원본 · CSV · parquet 를 쓴다.

## 7. 파일

| 무엇 | 파일 |
|---|---|
| 변환기 · 시험 | `fr_to_legacy.py` · `fr_to_legacy_test.py` · `legacy_checks.py` · `convert_all.py` (결과 `out/fr_to_legacy_test.json` · `out/legacy_checks.json` · `out/convert_all.json`) |
| 지형 원점 | `run_org.sh` (`out/org_*/env_origins.npy`) · q_eval 이 직접 남긴 `out/<tag>/env_origins.npy` |
| 19500 전체 기록 | `run_hud_prep.sh` (`out/fr_m19500_*` · `out/e2fr_m19500_*`) |
| 아래 띠 기록 재생 | `q_video.py --overlay label --out_root video_hud_src` · `label_runner.py` |
| HUD · 웹 사본 | `hud_make.py` · `hud_follow.py` · `hud_select.py` · `web_list.py` · `hud_sizes.py` |
| E1 대 E2 페이지 표 | `e12_page.py` → `out/E12-page.md` · `.csv` |
