# EX-42 평가 전용 메시 · D44 계단참 우선

> 분류: A/지형씬제작
> 작성: 오흥재 · analyst-lx · 2026-11-11
> 근거: 팀장 11:43 · 11:47 · 11:51 카드 · CURRICULUM-GATES 368d03e2 · #636
> 요지: 학습 메시를 그대로 두고 계단참 1 · 계단 4 · 경사 3 · START 변형 12 열을 CPU로 생성했다.
> 상태: CPU 검증 완료 · 독립 리뷰 요청 · Kit 장착 검사는 E1 종료 뒤 lead 슬롯 대기

## 확인된 범위

- 같은 seed로 반복 생성한 NPZ 파일 바이트가 같다. #636의 NumPy·Torch 상태 기록과 복원을 사용한다. CPU 생성기는 GPU가 보이면 실행을 거절한다.
- 관련 CPU 시험 **54 PASS**, 0 SKIP. 실제 저장 메시를 광선으로 재서 계단참 크기, 계단 단 높이, 경사 각도, 틈 폭, 평균대 폭, 시작점의 0.70 × 0.50 m 받침을 확인했다.
- 설치된 Isaac `TerrainImporter._compute_env_origins_curriculum` 메서드를 CPU에서 직접 실행해 1행 · 64 env 배정을 확인했다. Kit 전체 실행을 대신하는 증거는 아니다.
- 생성·예비 장착 경로는 평가 전용 `V` 묶음이다. 고정 치수는 1행이며 START 명목 L9는 열의 설명값이다. 가짜 10개 난이도 행을 만들지 않는다.
- 기존 학습용 메시 preflight는 이 평가 메시를 거절한다. 학습 메시·설정·해시·프로세스는 변경하지 않았다.
- GPU는 실행하지 않았다. 팀장 11:47 결정대로 E1 종료 직후, 경계 평가 전에 lead가 Kit 검사를 실행한다. 현재는 장착 성공 판정이 아니다.

## 치수와 출처

정본은 [CURRICULUM-GATES](https://github.com/foothold-project/foothold-lab/blob/368d03e2061b505fc72ad73e9cd2527a766e7738/inbox/jay/20261026-experiments/CURRICULUM-GATES.md)다. 아래 과제 치수와 별개인 배치 선택은 manifest의 `layout_assumptions`에 남겼다.

| 열 | 과제 치수 | 출처·등급 | 배치 선택과 한계 |
|---|---|---|---|
| `eval_stairs_landing_016` | 단 0.16 m · 참 깊이 1.2 m | CG229·394·600, 결정 | 참 폭도 1.2 m인 정사각형으로 구성(가정). 8×8 운반 타일·피라미드 형태는 기존 stage_stairs 계열. 단 너비 0.30 m는 CG394·기존 코드. 실제 참을 1.2로 만들기 위해 안에서 밖으로 생성 |
| `eval_stairs_010/015/020/025` | 단 0.10/0.15/0.20/0.25 m · 디딤면 0.30 m | CG394, 결정 | 기존 코드의 중앙 평지 3 m와 8×8 타일 사용. 고정 계단이며 학습 난이도와 별개 |
| `eval_slope_30/35/45` | 30/35/45도 | CG394, 결정 | 해석적인 평면 삼각형. 수직 절벽으로 바꾸는 heightfield 임계 미사용. 평평한 시작 1 m · 오름 수평길이 2 m · 정상 평지 2 m · 내리막 2 m · 끝 평지 1 m(배치 가정). 45도 성공률은 마찰 조건부이며 여기서 판정하지 않음 |
| START 12열 | 틈만 ×1.15 · 지지면만 ×0.85 · 둘 다 × 네 종류 | CG393, 결정 | 원본 명목 L9에 Go2 축척 x1.108/y0.885 적용. 반올림 전 곱을 사용. 돌은 L9 고무작위 한 종류이고 low/high로 중복하지 않음 |

계단참 기본 원점은 참 중앙이다. 참 높이는 배치로부터 계산된 1.44 m이며 **논문이 발표한 높이가 아니다**. 계단 올라오기용 `approach`, 참 중앙, 참 경계, 중간 정지 구간을 따로 제공한다. 정지·재출발은 접근 원점에서 시작해 중간 계단에서 멈추는 평가기의 몫이며, 이번 생성기가 성공률을 판정하지 않는다.

START 평균대 평가는 **명목 L9 폭 0.154875 m**가 기준이다. 학습 L9의 별도 덮어쓰기 0.09 m와 혼동하지 않는다. 따라서 지원면 축소 폭은 0.13164375 m다. 0.09/0.0765 m 추가 사다리는 이번 요청한 12열에 포함하지 않는다. 틈 지형의 지지면 축과 평균대의 틈 축은 N/A라 해당 변형이 원형과 같을 수 있다. 돌의 무작위 배치가 포함되므로 실제 간격은 명목 간격과 다를 수 있다. 같은 종류·seed의 변형은 같은 난수 시작점을 쓰지만 돌 개수가 달라지면 모든 후속 돌의 잡음까지 일대일로 대응하는 것은 아니다.

## 파일과 소비 계약

실제 산출물 목록·전체 SHA는 [evidence/ex42-eval-mesh-1111.json](evidence/ex42-eval-mesh-1111.json)에 있다. 큰 NPZ는 저장소에 넣지 않는다.

| 묶음 | 폴더(공통 뿌리 `/mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/`) | 열 수 |
|---|---|---:|
| E1 우선 | `landing_seed42_v1` | 1 |
| 계단·경사 | `paper_seed42_v1` | 7 |
| START 변형 | `start_seed42_v1` | 12 |

- CPU 생성: `CUDA_VISIBLE_DEVICES='' <isaac311-python> -m foothold_s2.scripts.ex42_eval_mesh_build --group landing --seed 42 --out <새 폴더>`.
- 각 폴더: `terrain_mesh.npz` · `mesh_manifest.json` · `cpu_origin_check.json`. 기존 폴더 덮어쓰기 거절.
- manifest 형식 `foothold-ex42-evaluation-mesh/1`, `training_allowed=false`. 각 열에 ID · nominal level · 출처 · 실제 치수 · 배치 가정 · 원점 · reset 범위. 파일 SHA는 원점/열 배열까지 덮는다.
- 평가기: `foothold_s2.eval.ex42_eval_mesh.attach(env_cfg, mesh_dir)`를 **gym.make 이전** 호출한다. 1행 장착·열별 0 reset·난이도 커리큘럼 끔. `preflight`가 파일 SHA·열 이름·순서·원점을 대조한다.
- `anchors_local_m`은 타일 좌표다. 월드 좌표는 `tile_offset_m`을 더한다. 참 spin과 접근→정지→재출발은 서로 다른 시작점이다. 영상/점수 소비자가 명시적으로 선택해야 한다.
- 기존 `ex42_mesh_mount_check`는 manifest 형식으로 평가 전용 adapter를 선택한다. A~E 학습 메시 분기는 유지했다.
- D44 6초·±1.2 rad/s·성공식, 정책 로드, 지도 세 모드 평가의 연결은 평가기 소유자 몫이다. **메시 생성 완료와 E1 졸업 평가 완료는 다르다.**

## Kit 실행 대기

고정 HEAD와 한 줄 명령은 함께 제공하는 `COMMAND-EX42-EVAL-MOUNT-1111.md`를 사용한다. lead가 E1 학습 종료를 확인하고 실행한다. 먼저 landing만, 통과 후 나머지 두 묶음.

기대: rc 0 · JSON `state=passed` · `evaluation_only=true` · landing `columns=1` · `per_column.checked=1` · `failed_count=0` · `assignment_kept=true` · `checks.scanner_checked=true`. 각 발 지지면 확인은 CPU와 별도로 실제 Kit에서 남아 있다. 실패하면 JSON `error`·`failed_criteria`를 보고 장착 문제를 먼저 고친다.

## 재현

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -m pytest -q foothold_s2/tests/test_ex42_eval_terrains_cpu.py foothold_s2/tests/test_ex42_mesh_rng_cpu.py foothold_s2/tests/test_ex42_mesh_mount_cpu.py foothold_s2/tests/test_ex42_mount_all_columns_cpu.py -p no:cacheprovider --basetemp=/home/jay/mai/tmp/analyst-lx/eval-mesh-reproduce
```

CPU 로그: `/home/jay/mai/tmp/analyst-lx/eval-mesh-regression-final.log`. 첫 새 시험은 모듈 미구현으로 실패한 뒤 구현 후 통과했다. 검토에 필요한 반례: 단을 한 번 더 잘라 참이 0.6 m가 되는 경우, 경사 45도가 절벽으로 바뀌는 경우, manifest 원점과 NPZ가 다른 경우, 평가 메시를 학습 기준선 경로로 넣는 경우.
