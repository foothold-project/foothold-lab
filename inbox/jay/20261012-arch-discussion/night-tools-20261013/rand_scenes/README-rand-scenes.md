> 분류: A/정책학습 · 평가 · 무작위화 장면 영상 (코드 · CPU 시험)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 18:43
> 근거: 팀장 10/12 컨펌 권고 「무작위화 장면 영상 (밀기 · 낮은 마찰 · 높은 마찰)」 · `VERIFY-astra-17.md` 5.1 절 · E1 `params/env.yaml` (sha256 2ee0009f…, ASTRA 17 이 읽은 판과 같음) · `q_eval_cmdr.py` · `q_video.py` · `frame_audit.py` · `RECORD-HUD.md` 5-1 절 · `isaac_slot.py` v2 (sha256 90ae613b…) · `usd_isolate_run.py` (366a3c13…) · `gpu_guard.py` · lead 10/13 19:02 지시 (isaac_slot v2 계약) · Isaac Lab 0.54.2 소스 (모두 읽기만)
> 요지: 같은 체크포인트 (E1 model_20000 · student) · 같은 명령 (평지 전진 0.5 m/s · 20 s) · 같은 출발에서 교란 없음 · 밀기 · 낮은 마찰 · 높은 마찰 네 판을 프로세스 하나에 한 판씩 돌리고, 물리 실행 중에 로봇을 따라가는 카메라로 찍는다. 코드와 CPU 시험까지 했다 (시험 23/23 · 돌연변이 36/36 잡음 · 실제 isaac_slot.py v2 를 가짜 자식으로 세 번 돌려 인자 수용 확인). Isaac · GPU 는 돌리지 않았다
> 상태: 판 2 (2026-10-13 19:10) · 판 1 (18:43) 에서 바뀐 곳: isaac_slot v2 계약 (실행별 USD 루트 · attempt · usd_isolate_run · STOP · 마감 · scan 셋) · slot 검사 11 칸 · 시험 2 개 · 변이 17 개 추가 · 실행 전 (lead 신호 대기) · 커밋 안 함 · 공용 파일 수정 없음

# 무작위화 장면 영상

표기: **확인됨** = 이번에 재거나 답을 아는 입력으로 시험한 것 · **추정** = 잰 값에서 끌어낸 해석 · **미확인** = 재지 않은 것.
경로는 `C:/isaac/ext/go2_rl_robotlab/_eval/` 기준이다. 출력은 `out_rand/` 아래에만 쓴다. `out/` 과 `handover_*` 에 쓰는 경로는 코드가 거부한다 (`rand_lib.check_out_path`, 시험으로 확인).

## 0. 돌리는 법

lead 가 신호를 줄 때 한 줄 (GPU 1, 저장소 루트 `C:/isaac/ext/go2_rl_robotlab` 에서):

```
C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe _eval/rand_scenes/rand_driver.py
```

- 드라이버가 Isaac 프로세스마다 isaac_slot v2 꼴로 감싼다:
  `isaac_slot.py --watch_log <로그> --record <attempt>/slot.json --usd_root <attempt>/usd --attempt <run_id>.<scene>.a<k> --lock _eval/slot/isaac_convert.lock --registry _eval/slot/isaac_usd_registry.json --scan_dirs _eval/out_rand,_eval/out_branch,_eval/out_uncr --stop_file _eval/out_rand/STOP --deadline 0.0 -- python gpu_guard.py --gpu 1 --min_free_mib 4096 --log <로그> --summary <attempt>/guard.json -- python _eval/usd_isolate_run.py _eval/rand_scenes/q_rand.py ...`
  - USD 변환 폴더는 시도마다 `<attempt>/usd/IsaacLab/usd_*` 다 (usd_isolate_run 이 정함). 공용 `/tmp/IsaacLab` 으로 가면 isaac_slot 이 94 로 막고, 드라이버도 그 판을 받지 않는다.
  - 멈추기: `_eval/out_rand/STOP` 파일을 만들면 새 시도를 띄우지 않고 exit 98 (돌고 있는 판은 끝까지 간다). 마감은 `--deadline <epoch 초>`. isaac_slot 이 잠금 대기 중에 STOP · 마감으로 띄우지 않은 경우 (98) 에도 드라이버는 재시도하지 않고 98 로 끝낸다.
  - 실제 명령 전체는 `--dry_run` 이 찍는다 (아무것도 쓰지 않음, 시험으로 확인).
  - 환경 변수는 `label_runner.py` 와 같다: `CUDA_DEVICE_ORDER=PCI_BUS_ID` · `CUDA_VISIBLE_DEVICES=1` · `OMNI_KIT_ACCEPT_EULA=YES`. 화면용 GPU 를 가리지 않는다.
- 먼저 한 장 보고 싶으면 `--stop_after_smoke` (5 s 짜리 세 판만). 스틸은 `out_rand/<run_id>/smoke_base/a1/stills/`.
- 예상 시간: **미확인**. 추정 10~20 분 (smoke 3 판 + 본 4 판, 재시도 없을 때).
  - 근거: 같은 GPU 1 의 기록 재생 영상 프로세스가 1,001 장에 23~24 s (`q_video` kinreplay JSON) · 비슷한 평가 프로세스 전체가 85~104 s (`out/un_e1_*.guard.json`). 이번 것은 물리와 렌더를 한 프로세스에서 하므로 둘을 더한 것보다 길 수 있다.
- GPU: GPU 1 만 쓴다 (`CUDA_VISIBLE_DEVICES=1` 에서 물리 · 정책 `cuda:0` = GPU 1, 렌더도 화면용 GPU 1). GPU 0 은 쓰지 않는다.
- VRAM: **미확인**. 같은 GPU 1 의 비슷한 작업 기록은 GPU 전체 사용량 8.0~12.1 GB (화면 · 다른 프로세스 포함, `gpu_guard` max_used). 이 프로세스 혼자 쓰는 양은 재지 않았다. GPU 1 여유가 4,096 MiB 아래로 떨어지면 guard 가 멈추고 드라이버가 exit 99 로 끝난다. 같은 GPU 1 에서 다른 Isaac 이 돌고 있으면 이 하한에 걸릴 수 있다 (미확인).
- 결과: `out_rand/<run_id>/summary.json` · `summary.csv` · `manifest.json` (모든 시도와 실패 이유).

## 1. 네 판

| scene | 교란 | 값 | 학습 설정 (E1 env.yaml) |
|---|---|---|---|
| `base` | 없음 | 로봇 마찰 1.0 / 1.0 · 밀기 없음 | |
| `push_lat` | 밀기 | 4 번: 옆 +0.4 · -0.4 · +0.4 · -0.4 m/s (몸통 방향 기준, 왼쪽 +) | push_by_setting_velocity · 간격 4 s · x/y ±0.4 m/s · roll/pitch/yaw ±0.6 rad/s |
| `fric_low` | 낮은 마찰 | 로봇 모든 형상 정지 · 운동 0.2 | 로봇 재질 정지 · 운동 [0, 2] · 반발 [0, 0.5] · 64 bucket · make_consistent |
| `fric_high` | 높은 마찰 | 로봇 모든 형상 정지 · 운동 1.5 | 같음 |

공통: 평지 (학습 `flat` 계열) · 명령 (0.5, 0, 0) 고정 · 20 s (1,000 step, 50 Hz) · 평가 시드 1000 · 관측 잡음 끔 (q_eval 과 같음) · 반발 0.0 · 시작은 타일 원점 + 기본 자세 · yaw 0.
값은 `rand_driver.py` 인자로 바꾼다 (`--push` · `--fric_low` · `--fric_high` · `--cmd` · `--duration_s`). 학습 범위 밖 값은 실행 전에 거부한다 (시험으로 확인).

한 판은 미리 정한 한 episode 다. 결과를 보고 고르지 않는다. 영상 위 첫 줄에도 그렇게 적는다.

## 2. 같은 출발

- 마찰 항과 밀기 항을 **모든 판에서** 결정적인 항으로 바꿨다. 판마다 다른 것은 그 항의 값뿐이다. 그래서 질량 · 무게중심 · 게인 · 모터 영점 · 지연 같은 다른 무작위 값과 출발 자세가 판마다 같아야 한다.
- 각 판이 출발 직후의 fingerprint (출발 자세 · 관절 · 질량 · 무게중심 · 게인 · 지연 · 모터 영점의 sha256) 를 남기고, 드라이버가 판끼리 같은지 본다 (마찰 값 hash 는 뺀다).
- 기준과 밀기 판은 첫 밀기 전까지 물리가 같아야 한다. 드라이버가 그 구간의 상태 열 최대 차이를 적는다. 0 이 아니면 같은 장면을 두 프로세스에서 돌린 결과가 다르다는 뜻이다 (비트 일치는 **미확인**, smoke 에서 처음 잰다).

## 3. 밀기

- 학습 항 `push_by_setting_velocity` 와 같은 일을 한다: `root_vel_w` 에 변화량을 더해 `write_root_velocity_to_sim` 으로 쓴다. 같은 event manager 간격 (interval 4 s) 에서 불린다. 그래서 적용 위치도 학습과 같다 (env.step 안 · 물리와 reset 뒤 · 관측 계산 전).
- 다른 점은 하나다: 무작위로 뽑지 않고 `--push` 의 k 번째 값을 k 번째 발동에 쓴다.
- 몸통 방향 기준 값을 그때의 heading 으로 돌려 세계 좌표로 바꾼다. 세계 성분 하나하나를 학습 범위와 견주고, 넘으면 그 판을 멈춘다. 계획 단계에서는 모든 heading 에 대해 넘지 않는지 먼저 본다 (예: vx 0.3 + vy 0.3 은 45도에서 0.424 라 거부, 시험으로 확인).
- 기록: 발동마다 상태 번호 · 시각 · heading · 요청한 세계 변화량 · 적용 전후 `root_vel_w` 와 그 차이 (`pushes.json` · `result.json` · `record.csv` 의 push 열).
- **발동 시각** (확인됨, CPU): event manager 의 float32 계산 (`time_left -= 0.02`, `< 1e-6` 이면 발동) 을 torch 로 그대로 돌리면 상태 201 · 402 · 603 · 804, 곧 **4.02 · 8.04 · 12.06 · 16.08 s** 에 발동한다. 4 s 를 0.02 로 200 번 빼도 1e-6 아래로 내려가지 않아 한 step 늦는다. 학습 중 밀기 간격도 같은 계산이므로 실제 간격은 201 step 이다 (추정, 학습 실행 기록으로 재지 않음). 실제 시뮬 값은 실행 기록으로 확인하고, 예측과 다르면 경고로 남긴다 (판을 버리지는 않는다).

## 4. 마찰

- 학습 무작위화가 바꾸는 것은 **로봇 쪽** 재질이다. 바닥 재질은 학습 내내 정지 · 운동 1.0, 결합 모드 average 였다 (env.yaml, 확인됨). 이번에도 바닥은 그대로 두고 로봇 쪽만 바꾼다.
- 접촉에서 실제로 쓰이는 값은 PhysX 결합 규칙으로 정해진다 (average < min < multiply < max, 높은 쪽 모드가 이김). 둘 다 average 면 (로봇 + 바닥) / 2 다.
  - 로봇 0.2 → 접촉 **0.6** · 로봇 1.5 → 접촉 **1.25** (계산, 확인됨).
  - 학습 범위 [0, 2] 를 접촉 값으로 옮기면 **0.5~1.5** 다. 학습 중 접촉 마찰은 0.5 아래로 내려간 적이 없다 (추정: 결합 모드가 average 라는 전제).
  - 그래서 「낮은 마찰 0.2」 영상은 접촉 0.6 장면이다. 학습 범위의 가장 낮은 끝을 보이려면 `--fric_low 0.0` (접촉 0.5). 접촉 0.2 를 만들려면 바닥을 바꿔야 하고, 그것은 학습 분포 밖이다. 이번 코드는 바닥을 바꾸지 않는다.
- 실행 때 읽어 기록하는 것 (cfg 값으로 대신하지 않음):
  - 로봇: PhysX tensor API `get_material_properties()` 로 모든 형상의 정지 · 운동 · 반발 최소 · 최대. 요청과 1e-6 안이어야 그 판을 받는다.
  - 바닥: `/World/ground/terrain/mesh` 에 묶인 physics 재질의 USD 값과 결합 모드.
  - 로봇 collider 의 USD 재질 binding 과 physics scene 기본 재질.
  - 접촉 값: 위 값에 결합 규칙을 적용한 계산. 화면 아래 띠에 「PhysX 규칙 계산」 이라고 적는다.
- **미확인**: tensor API 로 쓴 로봇 재질의 결합 모드는 tensor API 로 읽을 수 없다. PhysX 기본값 average 로 추정한다.
- 그래서 실측을 하나 더 넣었다 (`--friction_probe`): 발과 바닥 사이만 거른 접촉 센서로 마찰력 / 수직력 비를 매 step 적는다. 미끄러질 때 이 비가 실제 운동 마찰이고, 아니면 아래 한계다. smoke S2 가 이 센서가 물리를 바꾸지 않는지 (S1 과 비트 일치) 보고, 통과할 때만 본 판에 켠다. 센서가 만들어지는지 자체가 **미확인** 이다 (정적 mesh 를 filter 로 쓰는 경로).

## 5. 넘어짐

- 학습 종료 항 `illegal_contact` (몸통 접촉 > 1 N) 를 껐다. 켜 두면 넘어지는 순간 reset 되어 로봇이 출발점으로 순간 이동한다.
- 대신 같은 함수를 같은 인자로 매 step 불러 `base_contact` 열에 적는다. 종료가 물리를 바꾸는 것은 reset 뿐이므로 첫 접촉 전의 물리는 켰을 때와 같다 (추정, Isaac Lab step 순서를 읽고).
- 판정은 Q 규칙 그대로 `q_metrics.fall_index` 다: 몸통 접촉 · 60도 넘게 0.2 s · 지지면 아래. 결과에 상태 번호 · 시각 · 이유를 적는다.
- 넘어진 뒤에도 영상은 끝까지 찍고, 화면에 「넘어짐 감지 … · 이후는 참고 화면」 을 적는다.

## 6. 기록

attempt 폴더 `out_rand/<run_id>/<scene>/a<k>/`:

| 파일 | 내용 |
|---|---|
| `record.csv` | 1,001 행 (상태 0~1000) · 54 열: 시각 · 몸통 위치 · 자세 · heading · 세계 · 몸통 속도 · 각속도 · 중력 z · 지면 높이 · 명령 · 몸통 접촉 · 넘어짐 (실시간) · 밀기 번호와 변화량 · 발 접촉 · 수직력 · 발 수평 속도 · probe 수직력 · 마찰력 · 행동 크기 |
| `traj.npz` | 같은 표의 float 값 그대로 (판끼리 비트 비교에 씀) |
| `pushes.json` | 발동마다 상태 번호 · 시각 · 적용 여부 · 요청 · 적용 전후 속도 |
| `meta.json` | 인자 · 바꾼 설정 목록 · 기본 cfg 와 학습 yaml 차이 수 · 재질 읽은 값 · fingerprint · 지형 mesh hash · 카메라 · GPU 상태 · 코드 sha256 |
| `result.json` | 위 요약 · 넘어짐 · 기술 통계 (밀기 뒤 옆 속도 최대 · 0.1 m/s 아래로 0.25 s 머무는 데 걸린 시간 · 2 s 뒤 옆 이동, 평균 속도 · 발 미끄럼 속도, probe 비) · 영상 검사 결과 |
| `<scene>_master.mp4` | 1280 × 720 · 50 fps · 1,001 장 (상태마다 한 장) |
| `<scene>_web.mp4` | 1280 × 720 · 30 fps · h264 · yuv420p · faststart · 소리 없음 · crf 28 (2 MB 를 넘으면 31 · 33) |
| `stills/` | 0 s · 밀기마다 0.2 s 뒤 · 중간 · 끝 · 넘어짐 순간 |
| `slot.json` · `guard.json` · `attempt.json` | 잠금 · GPU 감시 · 검사 결과 |

로그는 `out_rand/<run_id>__<scene>__a<k>.log` (isaac_slot 의 `--scan_dirs` 가 보는 자리).

## 7. 영상과 프레임 관문

- 카메라: 몸통 위치에서 고정 offset 으로 따라간다 (`q_video.py` 와 같은 offset). 상태마다 한 장.
- 글자: 위 상자 (y 8~180) 에 판 · 시각 · 명령 · 실제 속도 (몸통) · 넘어짐, 아래 띠 (y 622~712) 에 교란 (밀기 뒤 0.6 s 는 주황 표식 · 마찰은 로봇 · 바닥 · 결합 · 접촉 값) 과 시간 막대 (예정 밀기 회색 · 적용 주황 · 넘어짐 빨강). 3D 영역 (y 224~616) 에는 밀기 뒤 0.6 s 동안 몸통의 화살표만 그린다.
- 관문 기준은 lead 의 `audit_frames.py` 와 같다 (3D 영역 평균 밝기 < 20 · 표준편차 < 6 · 파랑 우세 > 35 %).
  1. 찍는 중: 매 장을 렌더 직후 보고, 걸리면 최대 12 번 다시 렌더한다. 투영한 몸통이 화면 안이고 그 주변이 검지 않은지도 본다. 그래도 걸리면 그 판을 멈추고 영상을 내지 않는다 (부분 파일은 `rejected/` 로 옮김).
  2. 낼 때: master 와 웹 사본의 **모든 장**을 `frame_audit.audit(fps=0)` 로 본다. 하나라도 걸리면 `rejected/` 로 옮기고 그 판을 실패로 한다. 웹 사본은 h264 · 1280 × 720 · 30 fps · faststart 도 본다.
  3. 드라이버가 받은 판의 두 영상을 한 번 더 전 장 검사한다.
- 실패한 판은 새 프로세스로 다시 찍는다 (`--tries`, 기본 3). 앞 시도의 폴더 · 로그는 그대로 둔다.
- smoke 단계가 실제 렌더러로 관문을 한 번 더 깨 본다:
  - S1: 상태 30 에 검정 한 장을 넣는다 → 다시 렌더해 회복해야 통과.
  - S3: 상태 20 의 모든 렌더를 하늘로 돌린다 → 반드시 FRAME_GATE 로 실패하고 영상이 남지 않아야 통과.
  - 둘 중 하나라도 기대와 다르면 본 판을 돌리지 않는다 (exit 5).

## 8. 드라이버가 판을 받는 조건 (모두 통과해야 함)

slot 기록 (isaac_slot v2) 이 이 시도의 것 (`attempt`) · `slot_rc` 0 · `child_rc` 0 · `state_at_release` scene_built · `usd_final` 정확히 하나 · `usd_outside_root` 빈 목록 · `conflicts` 없음 · `usd_root` 가 이 시도의 `<attempt>/usd` · 기록된 명령에 `usd_isolate_run.py` 와 `q_rand.py` · `<attempt>/usd/isolate_state.json` 의 `patched_by` 가 비어 있지 않음 · guard 정상 종료 · 로그에 Traceback 없음 · `[RAND] FAIL` 없음 · 이번 시도의 done 줄이 정확히 하나 · `result.json` 의 scene · attempt · kind · checkpoint sha256 · iteration · 시드 · 명령 · 길이가 요청과 같음 · `record.csv` 1,001 행 · 열 · step · 시각 · 핵심 열 유한 · 정책이 본 명령 = 요청 · student 경로만 씀 (teacher 입력을 흔들어도 행동 불변) · 로봇 재질 읽은 값 = 요청 · 바닥 재질 읽힘 · 밀기 적용 수 = 예정 수 · 세계 성분 학습 범위 안 · 측정 변화량 = 요청 · master 1,001 장 전부 관문 통과 · 웹 사본 ±2 장 안 · 전부 통과 · h264 · 720p · 30 fps · faststart · 스틸 있음.
경고 (판을 버리지 않음): 밀기 발동 상태가 예측과 다름.
Isaac 은 예외 뒤에도 exit 0 을 낼 수 있으므로, 종료 코드가 아니라 위 조건으로 판정한다. q_rand 는 오류 때 `os._exit(3)` 로 끝낸다.

## 9. CPU 시험 (확인됨)

`python _eval/rand_scenes/test_rand_scenes.py` → 23/23 통과 (`out_rand/_cpu_tests/20261013-190503-p50324/results.json`).

| 무엇 | 답을 아는 입력 | 결과 |
|---|---|---|
| 밀기 일정 | 해석 · 잘못된 키 · 반복 키 · 빈 칸 | 맞음 · 거부 |
| heading 회전 | heading 90도 · 왼쪽 0.4 → 세계 (-0.4, 0) | 맞음 |
| 범위 | 0.4 통과 · 0.41 거부 · z 거부 · 45도 결합 거부 | 맞음 |
| 발동 시각 | event manager 계산을 torch float32 로 재현 | 201 · 402 · 603 · 804 로 같음 |
| 학습 설정 읽기 | env.yaml 의 밀기 · 재질 · 바닥 값 | 맞음 |
| 결합 규칙 | 0.2 와 1.0 average 0.6 · min 0.2 · max 1.0 | 맞음 |
| 기록 형식 | 쓰고 되읽기 · 짧은 표 · 깨진 step · NaN | 되읽기 일치 · 셋 다 거부 |
| 넘어짐 | 접촉 123 · 기울기 10 장 (넘어짐) 과 9 장 (아님) · 지지면 아래 | 맞음 |
| 밀기 반응 통계 | 0.4 exp(-t/0.3) → 0.1 아래 머무는 시각 0.42 s | 맞음 |
| 영상 관문 | 정상 0 · 홀수 검정 50/100 · 하늘 20/100 · 검정 한 장 1/100 · 회색 한 장 1/100 | 모두 정확히 셈. 검정 한 장은 4 fps 표본 검사로는 0 (전 장 검사가 필요한 이유) |
| 찍는 중 관문 | 검정 뒤 정상 → 재렌더 1 번 회복 · 하늘 계속 → 12 번 뒤 중단 | 맞음 |
| 내기 관문 | 정상 → 웹 사본 h264 · 1280 × 720 · 30 fps · 91 장 · faststart · 44,895 B · 결함 master · 짧은 master · 웹만 결함 · faststart 없는 50 fps 사본 | 정상만 통과 |
| 글자 | 3D 영역 밖 · 검정 · 하늘 화면에 글자를 얹어도 여전히 걸림 · 한글 표시 (스틸 한 장을 눈으로 확인) | 맞음 |
| 판 검사 (변형 20 가지) | Traceback · FAIL 줄 · done 없음 · done 둘 · guard 멈춤 · 남의 result · 다른 checkpoint · 짧은 기록 · 명령 오차 · teacher 경로 · 재질 · 범위 밖 밀기 · 측정 불일치 · 밀기 빠짐 · 늦은 발동 · 웹 검정 한 장 · 웹 50 fps · master 하늘 · faststart 없음 · 스틸 없음 | 각각 자기 검사 하나만 걸림 (늦은 발동은 경고) |
| 드라이버 흐름 (가짜 Isaac) | fric_low 첫 시도 Traceback · fric_high 첫 시도 다른 attempt 의 done 줄 | 둘 다 재시도로 a2 를 받고 a1 폴더 보존 · 출발 fingerprint 같음 · 첫 밀기 전 기준 = 밀기 |
| 드라이버 멈춤 | smoke 하늘 판이 실패하지 않음 → exit 5 · guard 멈춤 → exit 99 · STOP 파일 · 지난 마감 → 아무것도 띄우지 않고 exit 98 · isaac_slot 98 → 재시도 없이 exit 98 | 맞음 |
| isaac_slot v2 기록 검사 (15 칸 추가) | attempt · slot_rc · child_rc · scene_built · USD 둘 · USD 없음 · 루트 밖 · 옛 기록 (usd_outside_root 없음) · 충돌 · 다른 루트 · 격리 실행기 없는 명령 · q_rand 없는 명령 · isolate_state 없음 · patched_by 빈 값 · slot.json 없음 | 각각 자기 검사 하나만 걸림 (slot.json 없음은 slot 검사 10 개 모두) |
| 실제 `isaac_slot.py` v2 (가짜 자식, 비공개 lock · registry) | 드라이버가 만드는 인자 그대로 · 자식이 USD 를 루트 안에 · 루트 밖 (`C:/tmp`) 에 · STOP 파일 있음 | 인자 오류 없음 · rc 0 이고 우리 slot 검사 11 개 모두 통과 · rc 94 이고 `slot_rc_zero` · `slot_usd_inside_root` 두 개만 걸림 · rc 98 이고 자식 안 띄움 |
| 실행 계획 | `--dry_run` 이 명령 7 개를 lead 꼴로 만들고 아무것도 쓰지 않음 · 범위 밖 계획은 exit 2 | 맞음 |

돌연변이 (`mutate_rand_scenes.py`): 사본 폴더에서 관문 36 곳을 하나씩 망가뜨리고 해당 시험이 실패하는지 봤다. 36/36 잡음 (판 1 의 19 + isaac_slot v2 계약 17: slot 검사 10 · 명령 꼴 4 (격리 실행기 · usd_root/attempt · scan 셋 · STOP/마감) · 드라이버 멈춤 3). 실패 줄을 열어 모두 그 돌연변이 때문인 것을 확인했다 (`out_rand/_cpu_tests/mutations_20261013-190624.json`). `--usd_root` 를 빼는 돌연변이는 실제 isaac_slot 의 argparse `usage` 오류로 잡혔다 (lead 가 알려 온 원래 결함 그대로). 원본 파일은 건드리지 않았다.

이 시험은 Isaac 실행을 대신하지 않는다. q_rand.py 의 Isaac 쪽 (환경 구성 · 센서 · 재질 읽기 · 렌더) 은 문법 검사와 Isaac Lab 0.54.2 소스 대조까지만 했다.

## 10. 페이지에 쓸 수 있는 문장

- 쓸 수 있음: 「이 설정의 교란에서 이렇게 반응했다」 (예: 「학습 범위 안의 옆 0.4 m/s 밀기 네 번에서 넘어지지 않고 x s 안에 옆 속도가 0.1 m/s 아래로 돌아왔다 (1판)」).
- 쓰지 않음: 「실제 미끄러운 바닥에서도 안전」 · 「무작위화 전체 검증」 · 「센서 없이 모든 험지에 일반화」 · 강도별 성능.
- 마찰 판에는 로봇 값과 접촉 값을 함께 적는다 (예: 「로봇 발 0.2 · 접촉 0.6 (계산)」). 「마찰 0.2 바닥」 이라고 쓰지 않는다.
- 프레임 결함 0 은 영상 품질 관문이지 보행 내성의 근거가 아니다.

## 11. 미확인

1. Isaac 에서 한 번도 돌리지 않았다. 환경 생성 · 재질 항 · 밀기 항 · 렌더 루프가 실제로 도는지.
2. 시간 · VRAM (0 절).
3. 같은 장면을 두 프로세스에서 돌렸을 때의 비트 일치 (smoke S1 대 본 base 에서 처음 잰다).
4. 밀기 실제 발동 상태 (예측 201 · 402 · 603 · 804).
5. tensor API 로 쓴 로봇 재질의 결합 모드 (average 로 추정). probe 센서가 만들어지는지 · 물리를 바꾸지 않는지 (smoke S2).
6. USD 재질 binding 을 instance proxy 에서 읽을 수 있는지 (실패하면 `robot_usd_bindings` 에 오류 문자열이 남고 판은 계속된다).
7. 실제 렌더러에서 하늘 주입이 파랑 기준에 걸리는지 (q_video 에서는 걸렸다 · smoke S3 에서 다시 본다).
8. 물리와 렌더를 한 프로세스에서 할 때 검정 · 하늘 결함이 나오는 빈도.
9. 학습 중 접촉 마찰이 0.5~1.5 였다는 것은 결합 모드 average 전제의 계산이다.
10. `usd_isolate_run.py` 가 `q_rand.py` 를 runpy 로 띄울 때 q_rand 쪽 동작 (`__file__` · `sys.path` · `os._exit(3)` · `__main__`) 은 소스를 읽어 맞춘 것이고 Isaac 으로 돌려 보지 않았다. 격리가 실제로 걸렸는지는 각 시도의 `usd/isolate_state.json` · 로그의 `[USD-ISOLATE] patched via` · slot 기록으로 판정한다.

## 12. 파일

| 파일 | 하는 일 |
|---|---|
| `q_rand.py` | Isaac 실행 한 판 (교란 하나) |
| `rand_driver.py` | smoke · 본 판 · 재시도 · 판끼리 검사 · 요약 |
| `rand_lib.py` | 밀기 일정 · 범위 · 발동 예측 · 결합 규칙 · 기록 형식 · 통계 · 판 검사 · 명령 (Isaac 없음) |
| `rand_gate.py` | 프레임 관문 · 재렌더 루프 · 웹 사본 · 내기 관문 (Isaac 없음) |
| `rand_overlay.py` | 글자 · 시간 막대 · 화살표 (Isaac 없음) |
| `test_rand_scenes.py` | CPU 시험 23 개 (실제 isaac_slot.py v2 를 가짜 자식으로 돌리는 시험 포함) |
| `mutate_rand_scenes.py` | 돌연변이 36 개 (사본에서) |

`q_eval_cmdr.py` · `q_video.py` · `frame_audit.py` · `q_metrics.py` · `isaac_slot.py` · `gpu_guard.py` 는 고치지 않았다. `frame_audit.audit` 과 `q_metrics.fall_index` 는 불러 쓰고, 실행마다 sha256 을 남긴다.
