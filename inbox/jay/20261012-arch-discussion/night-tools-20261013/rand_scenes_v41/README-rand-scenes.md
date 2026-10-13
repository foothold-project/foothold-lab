> 분류: A/정책학습 · 평가 · 무작위화 장면 영상 (코드 · CPU 시험)
> 작성: 오흥재 (판 3) · Codex Worker (판 4) · 2026-10-14
> 근거: 팀장 10/12 컨펌 권고 「무작위화 장면 영상 (밀기 · 낮은 마찰 · 높은 마찰)」 · `VERIFY-astra-17d.md` · `VERIFY-astra-17g.md` 3 절 · E1 `params/env.yaml` · CPU 회귀 및 변이 시험
> 요지: 같은 체크포인트 (E1 model_20000 · student) · 같은 명령 (평지 전진 0.5 m/s · 20 s) 으로 교란 없음 · 밀기 · 낮은 마찰 · 높은 마찰 네 판을 프로세스 하나에 한 판씩 돌리고 물리 실행 중에 찍는다. ASTRA 17d 의 반례 다섯 (모두 rc 0 이던 것) 이 이제 모두 0 이 아닌 rc 로 끝난다. 「같은 출발 · 교란만 다름」 은 영상에 박지 않고, 판끼리 검사가 통과했을 때만 summary 가 허용한다. Isaac · GPU 는 돌리지 않았다
> 상태: 판 4 (2026-10-14) · CPU 시험 29/29 · 변경 관련 변이 9/9 검출 · 실제 smoke 미확인 · ASTRA 재검 미착수
> 판: v4

# 무작위화 장면 영상

표기: **확인됨** = 이번에 재거나 답을 아는 입력으로 시험한 것 · **추정** = 잰 값에서 끌어낸 해석 · **미확인** = 재지 않은 것.
경로는 `C:/isaac/ext/go2_rl_robotlab/_eval/` 기준이다. 출력은 `out_rand/` 아래에만 쓴다. `out/` 과 `handover_*` 에 쓰는 경로는 코드가 거부한다 (`rand_lib.check_out_path`, 시험으로 확인).

## 0. 돌리는 법

ASTRA 17d 3 절 순서대로, 먼저 smoke 만 (GPU 1, 저장소 루트 `C:/isaac/ext/go2_rl_robotlab` 에서):

```
C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe _eval/rand_scenes/rand_driver.py --stop_after_smoke
```

스틸 (`out_rand/<run_id>/smoke_base/a1/stills/`) 과 `manifest.json` 의 smoke 칸을 사람이 본 뒤, 본 판:

```
C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe _eval/rand_scenes/rand_driver.py --deadline <epoch 초>
```

한 판씩 돌리려면 `--scenes base` 처럼 준다. 다만 판끼리 검사 (2 절) 는 한 번의 실행 안에서만 하므로, 짝 비교 문구가 필요하면 네 판을 한 실행으로 돌린다.
본 실행은 양수인 명시적 `--deadline` 없이는 계획 단계에서 거부한다. 이 시각은 새 시도 시작을 막으며 이미 실행 중인 자식의 종료 시각을 보장하지 않는다.

smoke 뒤 사람이 `manifest.json`, 관문 기록, 로그, 스틸과 시스템 조회에서 확인할 것:

- NVML 물리 GPU 1의 UUID와 `CUDA_VISIBLE_DEVICES=1` 뒤 논리 CUDA 0의 물리 UUID, Kit 렌더 장치의 물리 UUID가 같은가.
- `slot.json`의 USD가 해당 시도 루트에 한 개 할당되고 루트 밖 또는 공유 폴더가 없는가.
- `guard.json`의 최고 GPU 사용량, 최소 GPU 여유, 소요 시간과 manifest의 실행 시간을 실제로 읽었는가.

- 드라이버가 Isaac 프로세스마다 실행 관문으로 감싼다:
  `isaac_slot_v3.py --watch_log <로그> --record <attempt>/slot.json --usd_root <attempt>/usd --attempt <run_id>.<scene>.a<k> --lock _eval/slot/isaac_convert.lock --registry _eval/slot/isaac_usd_registry_v3.json --scan_dirs <기본 로그 폴더와 구형 registry 로그 부모> --stop_file _eval/out_rand/STOP --deadline <epoch 초> --expect_conversions 1 -- python gpu_guard.py --gpu 1 --min_free_mib 4096 --log <로그> --summary <attempt>/guard.json -- python usd_isolate_run_v3.py q_rand.py ...`
  - 관문 두 파일의 경로는 `rand_lib.SLOT_SCRIPT` · `rand_lib.ISOLATE_SCRIPT` 상수 하나씩이다. 이름이 바뀌면 그 줄만 고친다.
  - 예상 변환은 1 개 (Go2 URDF 의 USD 변환) 다. 생성 평지는 mesh 라 변환기를 거치지 않는다.
  - 실제 명령 전체는 `--dry_run` 이 찍는다 (아무것도 쓰지 않음, 시험으로 확인).
  - 환경 변수는 `label_runner.py` 와 같다: `CUDA_DEVICE_ORDER=PCI_BUS_ID` · `CUDA_VISIBLE_DEVICES=1` · `OMNI_KIT_ACCEPT_EULA=YES`.
- **보호 중단 (ASTRA 17d 2.1)**: 어느 호출 경로든 (smoke_probe 포함) 시도 하나가 끝나는 공통 경계에서 본다. 아래면 재시도도 다음 장면도 띄우지 않고 그 코드로 끝난다.
  - 99: GPU guard 가 멈춤, 띄우기 전에 잰 GPU 1 여유가 하한 (4,096 MiB) 아래이거나 조회 실패로 미확인.
  - 98: STOP 파일 (`_eval/out_rand/STOP`) · 마감 (`--deadline <epoch 초>`) 으로 띄우지 않음.
  - 97 · 96 · 95 · 94 · 91 · 90 · 89: 관문의 변환 상한 · 공유 폴더 · 폴더 수 · 루트 밖 · 미할당 · 판정 불가 · 예상 밖 변환.
  - q_rand 의 실패 (exit 3 · 프레임 관문 · 크래시) 만 새 프로세스로 재시도한다 (`--tries`, 기본 3). 모든 시도 폴더와 로그는 남는다.
  - probe 센서 API 를 못 쓰는 실패는 probe 없이 계속한다. GPU 여유 하한 침범과는 다르게 다룬다.
- 종료 코드: 0 모든 판 통과이고 짝이 성립 · 2 계획 거부 · 4 판 실패 · 5 smoke 실패 · 6 짝 불성립 · 89~99 보호 중단.
- 예상 시간: **미확인**. 추정 smoke 3~6 분 · 본 판 10~20 분 (재시도 없을 때). 근거: 같은 GPU 1 의 기록 재생 영상 1,001 장에 23~24 s · 비슷한 평가 프로세스 전체 85~104 s. 물리와 렌더를 한 프로세스에서 하므로 더 길 수 있다.
- GPU: GPU 1 만 쓴다 (`CUDA_VISIBLE_DEVICES=1`). 실제 물리 · 렌더 장치가 guard 의 GPU 1 과 같은 UUID 인지는 첫 실행 로그에서 확인한다 (**미확인**).
- VRAM: **미확인**. 같은 GPU 1 의 비슷한 작업 기록은 GPU 전체 사용량 8.0~12.1 GB (화면 · 다른 프로세스 포함). 4,096 MiB 는 실행 중 유지할 하한이지 그만큼 비어 있으면 뜬다는 용량 예측이 아니다 (ASTRA 17d 3 절).

## 1. 네 판

| scene | 교란 | 값 | 학습 설정 (E1 env.yaml) |
|---|---|---|---|
| `base` | 없음 | 로봇 모든 shape 재질 1.0 / 1.0 · 밀기 없음 | |
| `push_lat` | 밀기 | 4 번: 옆 +0.4 · -0.4 · +0.4 · -0.4 m/s (몸통 방향 기준, 왼쪽 +) | push_by_setting_velocity · 간격 4 s · x/y ±0.4 m/s · roll/pitch/yaw ±0.6 rad/s |
| `fric_low` | 낮은 마찰 | 로봇 모든 shape 재질 정지 · 운동 **0.0** | 로봇 재질 정지 · 운동 [0, 2] · 반발 [0, 0.5] · 64 bucket · make_consistent |
| `fric_high` | 높은 마찰 | 로봇 모든 shape 재질 정지 · 운동 1.5 | 같음 |

공통: 평지 (학습 `flat` 계열) · 명령 (0.5, 0, 0) 고정 · 20 s (1,000 step, 50 Hz) · 평가 시드 1000 · 관측 잡음 끔 · 반발 0.0 · 시작은 타일 원점 + 기본 자세 · yaw 0 · 낙상 뒤 자동 reset 없음 (5 절).
값은 `rand_driver.py` 인자로 바꾼다 (`--push` · `--fric_low` · `--fric_high` · `--cmd` · `--duration_s`). 학습 범위 밖 값은 실행 전에 거부한다 (시험으로 확인).

`--fric_low` 기본을 0.2 에서 **0.0** 으로 바꾼 까닭 (ASTRA 17d 5 절 의견):
- 0.0 은 **로봇 쪽 학습 설정 범위의 낮은 끝**이다. 0.2 는 범위 안의 임의 값이었다.
- 접촉 계수는 바닥 1.0 과 결합 average 를 가정하면 0.5 다 (0.2 였으면 0.6). 접촉 무마찰 0 을 보여 주는 장면이 아니다.
- 학습의 64 bucket 이 정확히 0 을 뽑았다는 뜻이 아니고, 모든 shape 에 같은 끝값을 준 장면은 학습의 무작위 공간 분포와도 다르다.

한 판은 미리 정한 한 episode 다. 결과를 보고 고르지 않는다. 렌더 결함으로 다시 찍은 경우 모든 시도와 고른 이유 (처음으로 모든 검사를 통과한 시도) 가 `summary.json` 에 남는다.

## 2. 같은 출발과 짝 비교 (ASTRA 17d 2.2)

- 마찰 항과 밀기 항을 **모든 판에서** 결정적인 항으로 바꿨다. 판마다 다른 것은 그 항의 값뿐이다. 그래서 다른 무작위 값과 출발 자세가 판마다 같아야 한다.
- 판마다 먼저 검사한다: fingerprint 의 필수 열쇠 (출발 자세 · 관절 · 질량 · 무게중심 · 모터 영점 · 재질, actuator stiffness · damping) 가 모두 있고 값이 sha256 인지, 지형 항목에 `/World/ground/terrain/mesh` 가 있고 점 · 면 수 · 국소 기하 hash · **world 변환 4 × 4 · world 좌표 점 hash** 가 있는지. 빈 지문은 「같음」 이 아니라 실패다.
- 판끼리 검사 (드라이버, 허용 오차 없음 · 사후에 넓히지 않음):
  1. 출발 fingerprint 가 완전하고 서로 같음 (재질 hash 만 뺀다)
  2. 지형 항목이 유효하고 서로 같음
  3. 기준과 밀기 판이 첫 밀기 전까지 정확히 같음
  4. 같은 기준 장면 (smoke_base 와 본 base) 이 smoke 길이 동안 정확히 같음
- 하나라도 어긋나면 드라이버는 exit 6 으로 끝나고 `summary.json` 의 `pairing.valid` 가 false, 문구는 「단독 시연만」 이다. 각 영상은 남는다.
- 영상에는 「같은 출발 · 교란만 다름」 을 **박지 않는다**. 판끼리 검사는 모든 판이 끝난 뒤에야 하므로, 그 문구는 `pairing.valid` 가 true 일 때 페이지에서만 쓴다.

## 3. 밀기

- 학습 항 `push_by_setting_velocity` 와 같은 일을 한다: `root_vel_w` 에 변화량을 더해 `write_root_velocity_to_sim` 으로 쓴다 (설치된 `events.py:1065` 와 같은 덧셈). 같은 event manager 간격 (interval 4 s) 에서 불린다.
- 실제 힘 N 이나 일정 시간 외력이 아니라 **순간 속도 변화** 다. 방향도 학습의 world 축 무작위 표본과 달리 heading 기준 고정 순서다.
- 몸통 방향 기준 값을 그때의 heading 으로 돌려 세계 좌표로 바꾸고, 세계 성분 하나하나를 학습 범위와 견준다.
- **판마다 밀기 대조 (ASTRA 17d 2.4)**: 드라이버가 동결한 schedule 과 기록된 heading 으로 세계 변화량을 따로 계산해, 사건마다 순서 (k 번째 발동 = k 번째 항목) · 요청과 좌표계 · 방향 (여섯 성분 형식 · 유한성) · 적용 전후 차 = 측정 = 계산 · 학습 범위 · CSV/NPZ 의 그 행 (push 번호와 변화량, 다른 행에는 없음) 을 맞춘다. 순서 · 방향은 필수 조건이다.
- **발동 시각** (확인됨, CPU): event manager 의 float32 계산을 torch 로 그대로 돌리면 상태 201 · 402 · 603 · 804, 곧 **4.02 · 8.04 · 12.06 · 16.08 s** 다. 실제 상태는 기록으로 확인하고, 예측과 다르면 경고만 남긴다 (순서 · 방향 조건은 따로 필수).

## 4. 마찰

- 이 코드가 바꾸는 것은 **로봇의 모든 shape** 재질 (정지 · 운동 · 반발) 이다. 발만이 아니다. 바닥 재질은 학습 그대로 정지 · 운동 1.0, 결합 average (env.yaml, 확인됨).
- 접촉 계수는 PhysX 결합 규칙으로 정해진다 (모드가 다르면 우선순위 높은 쪽, average 일 때만 (a + b) / 2). 바닥 1.0 · average 가정에서 로봇 0.0 → 0.5 · 1.5 → 1.25 (계산). 학습 범위 [0, 2] 는 접촉 0.5~1.5 에 해당한다 (같은 가정).
- 실행 때 읽어 기록하는 것: 로봇 재질 (PhysX tensor API, 요청과 1e-6 안이어야 받음) · 바닥 재질과 결합 모드 (USD) · 로봇 collider binding · physics scene 기본 재질.
- **미확인**: tensor API 로 쓴 로봇 런타임 재질의 결합 모드. 그래서 영상 아래 띠에 「접촉 0.50 / 0.50 (average 가정 · 런타임 결합 미확인)」 이라고 적는다.
- probe (`--friction_probe`) 의 |마찰력 합| / |법선력 합| 은 **힘의 기술 통계** 로만 적는다 (`probe_force_ratio_*`). 미끄럼 여부 · 여러 접촉 · 적분 시간이 섞이므로 마찰 계수 측정이 아니다. probe 를 끈 판의 probe 열 NaN 은 「미사용」 표시로, 켠 판의 NaN 은 측정 실패로 구분해 검사한다.

## 5. 넘어짐

- 학습 종료 항 `illegal_contact` (몸통 접촉 > 1 N) 를 껐다. 켜 두면 넘어지는 순간 reset 되어 로봇이 출발점으로 순간 이동한다. 같은 함수를 같은 인자로 매 step 불러 `base_contact` 열에 적는다.
- 판정은 Q 규칙 `q_metrics.fall_index` (몸통 접촉 · 60도 넘게 0.2 s · 지지면 아래) 다. 학습의 접촉 종료와 같은 정의가 아니다 (Q 가 기울기 · 지지면 조건을 더함).
- **판정 자료 검증 (ASTRA 17d 2.3)**: 드라이버가 NPZ 로 낙상을 다시 계산해 result.json 과 맞춘다. 낙상 전 구간에서 위치 · 자세 · 속도 · 지지면 높이 (`ground_z_m` · `base_height_above_ground_m`) · 접촉 · 수직력 · 발 속도 · 명령이 모두 유한해야 한다. 낙상 전에 지지면 높이가 없으면 「낙상 없음」 이 아니라 판 실패다. 낙상 뒤의 결측은 참고 화면용으로 허용한다.
- 넘어진 뒤에도 영상은 끝까지 찍고 「넘어짐 감지 … · 이후는 참고 화면 (판정 밖)」 을 적는다.

## 6. 기록

attempt 폴더 `out_rand/<run_id>/<scene>/a<k>/`:

| 파일 | 내용 |
|---|---|
| `record.csv` | 1,001 행 (상태 0~1000) · 54 열 |
| `traj.npz` | 같은 표의 값 그대로. 드라이버가 CSV 와 NaN 위치 · 값 (CSV 의 7 유효숫자 안) 을 맞춘다 |
| `pushes.json` | 발동마다 상태 번호 · 시각 · 적용 여부 · 요청 · 좌표계 · heading · 적용 전후 속도 |
| `meta.json` | 인자 · 바꾼 설정 · **학습 계약 대조** (평가 cfg 대 학습 env.yaml 의 observations · actions · decimation · sim · scene/robot 차이 전부) · **평가 env** (physics dt · step dt · decimation · 행동 관절 순서와 scale) · 재질 읽은 값 · fingerprint · 지형 항목 · 코드 sha256 |
| `result.json` | 위 요약 · 넘어짐 · 기술 통계 · 영상 검사 결과 |
| `<scene>_master.mp4` · `<scene>_web.mp4` | 1280 × 720 · 50 fps · 1,001 장 / 30 fps · h264 · faststart |
| `stills/` | 0 s · 밀기마다 0.2 s 뒤 · 중간 · 끝 · 넘어짐 순간 |
| `slot.json` · `guard.json` · `attempt.json` · `usd/` | 관문 기록 · GPU 감시 · 검사 결과 · 이 시도의 USD 변환 폴더와 `isolate_state.json` · `assigned.jsonl` |

학습 계약에서 허용하는 차이는 이 도구가 일부러 만드는 것뿐이다: 관측 잡음 끔 (`enable_corruption` 둘) · `scene/robot/prim_path` 표기. 그 밖의 차이 (예: sim dt · 관측 scale) 가 하나라도 있으면 판 실패다.

## 7. 영상과 프레임 관문

- 카메라: 몸통 위치에서 고정 offset 으로 따라간다. 상태마다 한 장.
- 위 상자: 「E1 student · model_20000 · 평지 · 시드 1000 · 사전 정한 1판 (결과로 고르지 않음) · 관측 잡음 끔」 · 판 · 시각 · 명령 · 실제 속도 · 넘어짐.
- 아래 띠: 밀기 뒤 0.6 s 는 주황 표식, 마찰 판은 「재질: 로봇 모든 shape 0.00 / 0.00 · 바닥 1.00 / 1.00 · 접촉 0.50 / 0.50 (average 가정 · 런타임 결합 미확인)」, 시간 막대.
- 관문은 lead 의 `audit_frames.py` 기준 (3D 영역 평균 밝기 < 20 · 표준편차 < 6 · 파랑 우세 > 35 %): 찍는 중 매 장 (재렌더 최대 12 번) · 낼 때 master 와 웹 사본 모든 장 · 드라이버가 한 번 더.
- smoke 가 실제 렌더러로 관문을 깨 본다: S1 상태 30 검정 한 장 → 회복해야 함 · S3 상태 20 하늘 강제 → 반드시 실패하고 영상이 남지 않아야 함.
- 프레임 관문은 넘어져 가려진 로봇을 거절할 수 있다 (ASTRA 17d 7). 렌더 불량과 물리 실패를 구분하려고 실패 시도의 기록 · 영상 조각 · 이유를 지우지 않는다. 자동 관문은 사람이 스틸을 보는 검사를 대신하지 않는다.

## 8. 드라이버가 판을 받는 조건 (모두 통과해야 함)

- 관문 기록 (v3): `slot_version` v3 · 이 시도의 attempt · `slot_rc` 0 · `child_rc` 0 · scene_built · `expect_conversions` 1 이고 `expect_violation` false · USD 폴더 정확히 하나이고 `<attempt>/usd/isaaclab/usd_*` · 루트 밖 없음 (사용 · 할당 둘 다) · 미할당 없음 · 할당 목록 = 사용 폴더 · 충돌 없음 · registry 오류 없음 · 강제 종료 없음 · 기록의 `usd_root` = 이 시도 · 명령에 `usd_isolate_run_v3.py` 와 `q_rand.py` · `isolate_state.json` 의 `patched_by` 있음 · version v3 · blocked 없음 (warnings 는 경고).
- guard 정상 종료 · 로그에 Traceback · `[RAND] FAIL` 없음 · 이번 시도의 done 줄 하나.
- result 가 요청 묶음과 같음: scene · attempt · kind · checkpoint sha256 · iteration · 시드 · probe 여부 · 명령 · 길이 · `train_yaml_sha256` · 학습 계약 · 평가 env · fingerprint 완전 · 지형 완전.
- 기록: CSV 와 NPZ 구조 · 둘의 대조 · step 과 시각 · 낙상 전 판정 열 유한 · 의미 (0/1 · 단위 quaternion · |중력 z| ≤ 1 · 힘과 속도 ≥ 0 · heading 범위 · 높이 = 몸통 z - 지면 z · 명령 = 요청) · NaN 표시 열 · probe 열 · 낙상 재계산 = result.
- 정책이 본 명령 = 요청 · student 경로만 씀 · 로봇 재질 읽은 값 = 요청 · 바닥 재질 읽힘.
- 밀기: 적용 수 · 순서와 요청 · 방향 재계산 · 전후 차와 측정 · 학습 범위 · 기록 행. 경고 (판을 버리지 않음): 발동 시각이 예측과 다름.
- 영상: master 1,001 장과 웹 사본 모든 장 관문 통과 · h264 · 720p · 30 fps · faststart · 스틸.

## 9. CPU 시험 (확인됨)

판 3 당시 `python _eval/rand_scenes/test_rand_scenes.py` → **27/27 통과** (`out_rand/_cpu_tests/20261013-235540-p152556/results.json`). 판 4는 작업 폴더 출력에서 **시험 함수 29/29 통과**, `test_validate_attempt_mutations`의 내부 변형 **81개**를 확인했다. 변경 관련 변이 9/9 검출. 판 4의 명령과 로그는 `codexB/REPORT.md`에 있다.

ASTRA 17d 8 절의 반례 다섯 (모두 rc 0 이던 것) 을 같은 절차로 넣었다 (`test_astra17d_counterexamples_not_rc0`, 확인됨):

| 반례 | 지금 rc |
|---|---|
| smoke_probe 에서만 guard 중단 | 99 · smoke_skyfail 과 본 판을 띄우지 않음 |
| push 지형 지문 변경 + 첫 밀기 전 상태 10 의 x + 0.02 (NPZ 만) | 4 (CSV ≠ NPZ) |
| 같은 반례를 나눠서: 지형 world hash 만 | 6 (지형 불일치) |
| 같은 반례를 나눠서: x + 0.02 를 CSV 와 NPZ 둘 다 | 6 (첫 밀기 전 궤적 불일치, 최대 차 0.02) |
| 모든 판의 지문 `{}` · 지형 `[]` | 4 (`fingerprint_complete` · `terrain_complete`) |
| 두 판의 CSV · NPZ 지지면 높이 전부 NaN | 4 (`record_judge_finite_before_fall`) |
| 첫 밀기를 world +x 로 바꿈 (계획은 heading +vy) | 4 (`push_direction`) |

그 밖의 주요 시험:

- 공통 경계 보호 중단: 본 판 guard 99 · 관문 94 · 91 · 96 · 90 · 97 · 95 · 89 · 띄우기 전 여유 1,000 MiB → 각각 그 코드로 끝나고 다음 장면 없음. STOP · 지난 마감 · 관문 98 → 98.
- 기록 결함 13 가지 (지지면 NaN · 한 상태 높이 NaN · 접촉 2 · quaternion 0.9 · 높이 ≠ z 차 · 명령 다름 · step · NPZ 만 변경 · probe 켰는데 NaN · probe 껐는데 값 · 밀기 없는 행의 변화량 · 행동 NaN · 낙상 결론 다름) 이 각각 자기 부분만 걸리고, 낙상 뒤의 NaN 은 허용됨.
- 회복 시간: 다음 밀기 · 낙상에서 검열, 0.25 s 는 t_s 범위로 (13 표본 0.24 s 는 불충분 · 14 표본 0.26 s 는 충족).
- `compare_rows`: 두 NaN 은 같지 않음 (NaN 표시 열 제외).
- 판 검사 변형: 관문 v3 · 요청 묶음 · 학습 계약 · 지문 · 지형 · 기록 · 밀기 · 영상 변형이 각각 자기 검사만 걸림.
- `cross_checks` 단독: 빈 지문 · 다른 지문 · 기준 장면 반복 불일치 (1e-6 차이) → 짝 불성립.
- 실제 관문: `isaac_slot_v3.py` 의 **사본**을 가짜 자식으로 다섯 번 (루트 안 rc 0 이고 우리 관문 검사 17 개 통과 · 루트 밖 94 · 미할당 91 · 거절된 둘째 변환 89 · STOP 98). 공용 lock · registry 대신 비공개 파일. 원본은 다른 하위 작업이 마무리 중이라 실행 때의 sha256 을 결과 파일에 남긴다.
- 실행 계획: `--dry_run` 명령 7 개가 v3 꼴 · `--expect_conversions 1` · 낮은 마찰 0.0 · 아무것도 쓰지 않음.

판 3 돌연변이 (`mutate_rand_scenes.py`): 사본 폴더에서 관문 71 곳을 하나씩 망가뜨렸다. **71/71 잡음** (`out_rand/_cpu_tests/mutations_20261013-235724.json`). 이는 판 3 기록이며 판 4 전체 재실행 수치가 아니다. 판 4 변이는 `RAND_MUTATION_WORK_ROOT` 작업 폴더의 `run_mutant.py`를 통해서만 실행하며 복사본과 로그를 그 안에 남긴다.

이 시험은 Isaac 실행을 대신하지 않는다. q_rand.py 의 Isaac 쪽 (환경 구성 · 센서 · 재질 읽기 · 지형 world 변환 · 학습 계약 기록 · 렌더) 은 문법 검사와 Isaac Lab 0.54.2 소스 대조까지만 했다.

## 10. 페이지에 쓸 수 있는 문장 (ASTRA 17d 5 절)

- 쓸 수 있음: 「E1 student 의 사전 지정한 평지 1판에서, 학습 설정 범위 안의 고정 속도 교란 / 로봇 재질 변경에 대한 반응을 시연했다.」 · 「관측 잡음을 끄고, 낙상 후에는 자동 reset 대신 화면을 이어 기록했다. 낙상 이후는 성능 판정에서 제외했다.」
- 「같은 출발에서 교란만 바꿨다」 는 `summary.json` 의 `pairing.valid` 가 true 일 때만.
- 마찰 판: 「로봇 모든 shape 재질 0.0 · 바닥 1.0 · 접촉 0.5 (average 가정 · 런타임 결합 미확인)」. 「발만 0.2」 · 「바닥 마찰 0.2」 라고 쓰지 않는다.
- 회복 시간 수치는 검열 규칙 (다음 밀기 · 낙상) 과 함께 1판 기술 통계로만. 검열된 경우 숫자를 쓰지 않는다.
- 쓰지 않음: 「무작위화 범위의 강건성을 입증」 · 「실제 미끄러운 바닥에서도 안전」 · 「v2 보다 우수」 · 「같은 시험지 비교 완료」 · 「GPU native 와 CPU 가 비트 동일」 · probe 비를 「마찰 계수 측정」 으로.
- 프레임 결함 0 은 영상 품질 관문이지 보행 내성의 근거가 아니다.

## 11. 미확인

1. Isaac 에서 한 번도 돌리지 않았다. 환경 생성 · 재질 항 · 밀기 항 · 학습 계약 기록 (`class_to_dict` 이 이 cfg 에서 도는지) · 지형 world 변환 읽기 · 렌더 루프.
2. 시간 · VRAM · 물리와 렌더의 실제 GPU UUID.
3. 같은 장면을 두 프로세스에서 돌렸을 때의 비트 일치 (smoke S1 대 S2 · smoke_base 대 base). 일치하지 않으면 짝 비교는 성립하지 않고 exit 6 이다.
4. 밀기 실제 발동 상태 (예측 201 · 402 · 603 · 804).
5. tensor API 로 쓴 로봇 재질의 결합 모드. probe 센서가 만들어지는지 · 물리를 바꾸지 않는지 (smoke S2).
6. USD 재질 binding 을 instance proxy 에서 읽을 수 있는지.
7. 실제 렌더러에서 하늘 주입이 파랑 기준에 걸리는지 (smoke S3).
8. 물리와 렌더를 한 프로세스에서 할 때 검정 · 하늘 결함 빈도.
9. 학습 중 접촉 마찰 0.5~1.5 는 결합 average 가정의 계산이다.
10. `usd_isolate_run_v3.py` 가 q_rand 를 runpy 로 띄울 때의 q_rand 쪽 동작과, 그 실행기 · `isaac_slot_v3.py` 의 최종판과 이 검사의 호환. 두 파일은 다른 하위 작업이 마무리 중이라 시험은 그 시각의 사본으로 했다. 최종판이 기록 칸 이름이나 종료 코드를 바꾸면 rand 검사를 다시 맞춰야 한다.

## 12. 파일

| 파일 | 하는 일 |
|---|---|
| `q_rand.py` | Isaac 실행 한 판 (교란 하나) |
| `rand_driver.py` | smoke · 본 판 · 공통 경계 보호 중단 · 재시도 · 판끼리 검사 · 요약 |
| `rand_lib.py` | 밀기 일정 · 범위 · 발동 예측 · 결합 규칙 · 기록 형식 · CSV/NPZ 검증 · 통계 · 판 검사 · 명령 · 관문 경로 상수 (Isaac 없음) |
| `rand_gate.py` | 프레임 관문 · 재렌더 루프 · 웹 사본 · 내기 관문 (Isaac 없음) |
| `rand_overlay.py` | 글자 · 시간 막대 · 화살표 (Isaac 없음) |
| `test_rand_scenes.py` | CPU 시험 함수 29 개 (판 4) |
| `mutate_rand_scenes.py` | 변이 77 개 정의, 판 4 변경 관련 9 개 실행 |

`q_eval_cmdr.py` · `q_video.py` · `frame_audit.py` · `q_metrics.py` · `isaac_slot*.py` · `usd_isolate_run*.py` · `gpu_guard.py` 는 고치지 않았다.

## 판 이력

| 판 | 날짜 | 변경 |
|---|---|---|
| v3 | 2026-10-13 | 관문 v3와 17d 반례 수정 |
| v4 | 2026-10-14 | registry 분리 · 밀기 방향과 요청 검증 · GPU 조회 실패와 마감 보류 · CPU 회귀 시험 |
