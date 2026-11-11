> 분류: A/정책학습 · 단계 이어 가기
> 작성: sonnet-code-lx · 2026-11-11 (lead-lx 12:08 ③)
> 근거: ex42_stage_handoff.start_launcher 가 넘기는 EX42_AUTO_* · 실제 E1 학습 PID 3119663 의 인자 · 실제 E0 m250 부모 · c333 메시
> 요지: 자동 기동이 부르는 launcher 셸 한 개, 알림 송신 한 줄, E1 예행 명령. 트레이너를 exec 해서 대기열에 등록된 PID 가 학습 자체다.
> 상태: CPU 확인됨 (시험 + 실제 E1 예행 rc 0, Kit · GPU 안 씀) · 실제 두 rank 기동 · 알림 실제 도착은 미확인

# EX-42 단계 launcher 셸

## 무엇이 생겼나

| 자리 | 내용 |
|---|---|
| `foothold_s2/scripts/ex42_stage_launcher.sh` | `--next-stage-launcher` 에 줄 절대경로 실행 파일. 프로필(`~/mai/foothold-linux.env`)을 읽고 파이썬 모듈을 exec |
| `foothold_s2/scripts/ex42_stage_launcher.py` | `EX42_AUTO_*` + 프로필 값으로 `torch.distributed.run ... train_start.py` 한 줄을 만들고, 알림을 보낸 뒤 `os.execvpe` 로 트레이너가 이 프로세스를 대체 |

- 단계 값은 이름을 박지 않고 plan 단계 표(`E_STAGE_SPECS`)에서 읽는다: 상한 회차(`--max_iterations`), 부모 핀이 없는 단계(E1F 이후)는 거절(rc 2).
- `next_stage`: 실행 폴더 `$EX42_MAIN_ROOT/EX-42-B-<단계>_<시각>`. `continue`: 체크포인트가 있는 폴더 그대로 (manifest.json 이 없으면 거절), `--ex42_resume_from` · `--ex42_segment_end`.
- 프로필에서 와야 하는 값 (없으면 rc 2, 추측 없음): `ISAAC311_PYTHON` · `GPU_JOBS_QUEUE` (프로필), `EX42_MESH_DIR` · `EX42_MESH_SHA256` (단계별은 `_<단계>` 꼬리, 예 `EX42_MESH_DIR_E2`), `EX42_SOURCE_REF`, `EX42_MAIN_ROOT` (next_stage 만). 선택: `EX42_NUM_ENVS`(3072) · `EX42_SEED`(42) · `EX42_P1_DEVICE`(cuda:1) · `EX42_P1_SPLIT_DEVICE` · `EX42_EVAL_SEED`(42).
- plan · 승인 파일 · 대기열 배정기 경로는 launcher 가 들어 있는 작업 사본 기준 (lead 가 잠근 기동 사본 안에서 부르면 그 사본의 파일).

## 알림 송신 한 줄

launcher 가 exec 직전에 (`EX42_NOTIFY_TO` 와 `ORCA_CLI_COMMAND` 가 둘 다 있을 때만, 실패해도 기동은 계속):

```
$ORCA_CLI_COMMAND orchestration send --to "$EX42_NOTIFY_TO" --subject "(HH:MM) EX-42 <다음 단계 X 자동 기동 | X 이어 가기 N 까지> · 실행 폴더 ... · 관문 영수증 ..." --body (같은 글) --type status
```

`EX42_NOTIFY_TO` 는 프로필에 `run:run_5283fa2c059b` 처럼 적는다 (기본값 없음). 시각은 `date` 와 같은 시계. 둘 중 하나가 없으면 stderr 에 「notice not sent」 만 남는다 (next_stage_launcher.log).

## 단계별 Kit 첫 update 예행 명령 (CPU, Kit 안 띄움)

launcher 가 `--dry-run` 이면 한 rank (`WORLD_SIZE=2 RANK=0`) 로 `train_start.py` 를 `--ex42_stage ID --ex42_stage_approved --ex42_stage_dry_run` 으로 돌려 승인 · 부모 · 메시 · 출력 폴더 안 만듦까지 본다. **예행에도 승인 스위치가 같이 필요하다** (처음 만든 판은 dry-run 만 줘서 실제 예행에서 걸렸고 고쳤다).

E1 (실제 E0 m250 부모 · c333 메시로 돌려 rc 0, `EX42_STAGE_E1_PREFLIGHT` 출력, 폴더 안 만듦 확인):

```
E=/home/jay/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218
M=/home/jay/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333
cd <기동 사본> && CUDA_VISIBLE_DEVICES= \
EX42_AUTO_ACTION=next_stage EX42_AUTO_TARGET_STAGE=E1 EX42_AUTO_PARENT_MANIFEST=$E/manifest.json \
EX42_AUTO_PARENT_CHECKPOINT=$E/model_250.pt EX42_AUTO_GATE_RECEIPT=/nonexistent EX42_AUTO_GATE_SHA256=0 \
EX42_MESH_DIR=$M EX42_MESH_SHA256=88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95 \
EX42_SOURCE_REF=$(git rev-parse HEAD) EX42_MAIN_ROOT=/tmp/ex42_dry_main \
foothold_s2/scripts/ex42_stage_launcher.sh --dry-run
```

바꿔 끼울 것: `TARGET_STAGE` · `PARENT_*` (그 단계 부모 실행의 manifest · 체크포인트) · 메시 칸 (`EX42_MESH_DIR_<단계>`). **E1F 이후 단계는 지금 plan 에 부모 핀이 없어 예행도 「no pinned parent」 로 거절된다** (verifier 가 핀을 쓰면 같은 명령이 된다). 실제 기동 전 확인 명령은 `--print` (명령만 보임).

## 확인한 것 (CPU)

- 시험 24 건 (`test_ex42_stage_launcher_cpu.py`) + 기존 handoff 시험: 단계 값이 plan 에서 오는 것, continue, 예행, 단계 꼬리 값, 거절 10 가지, 알림 순서 (알림 → exec, 예행은 알림 없음, 거절은 exec 없음), 알림 실패가 기동을 막지 않음, 셸 → 파이썬 → 트레이너가 같은 PID, `start_launcher` 가 넘기는 환경 이름 = launcher 가 읽는 이름.
- 돌연변이 5 모두 걸림: 파이썬에서 exec 대신 자식 띄움 · 셸에서 exec 뺌 · 단계 표 검사 끔 · 예행에도 알림 · segment_end 검사 끔.
- 실제 E1 예행 (위 명령) rc 0.

## 미확인 · 손대지 않은 것

- 실제 두 rank 기동 · 자동 기동 사슬 끝까지 · 알림이 run 받은편지함에 실제 도착하는지 (orca 환경 변수가 학습 프로세스에 남아 있는지 포함).
- 프로필에 `EX42_*` 값을 쓰는 일과 `EX42_NOTIFY_TO` 는 lead 몫. GPU · Kit · 병합 · 승인 파일은 건드리지 않았다.
