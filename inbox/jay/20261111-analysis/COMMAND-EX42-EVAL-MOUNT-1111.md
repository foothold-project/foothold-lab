# EX-42 평가 메시 Kit 검사 명령

> 분류: A/지형씬제작
> 작성: 오흥재 · analyst-lx · 2026-11-11
> 근거: 팀장 11:47 · 11:51, CPU 54 PASS
> 요지: E1 종료 뒤 lead가 landing부터 실행할 고정 코드 명령
> 상태: 실행 대기 · Kit 미측정

코드 커밋 `0ad299283babce40a4572c8c56a800064351a008`, `foothold_s2` 트리 `847f8abf8e88be7690b00e73b6258e2f3a3708b4`. 현재 학습 중 GPU에서 실행하지 않는다. **E1 종료 확인 뒤 lead 실행**이다. GPU0 기준이며 다른 GPU를 쓰면 `--device`와 출력 이름을 함께 바꾼다. 원본 학습 메시 경로는 인자에 없다.

순서 landing → paper → start. 각 명령은 한 줄이다. 다른 산출물을 덮지 않으며 실행 폴더의 코드 트리가 달라지면 거절한다.

## landing · 1열

```bash
cd /home/jay/mai/wt/foothold-lab/analyst-lx-terrain-d && test "$(git rev-parse HEAD:foothold_s2)" = 847f8abf8e88be7690b00e73b6258e2f3a3708b4 && git diff --quiet HEAD -- foothold_s2 && test ! -e /mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_landing_cuda0_v1.json && env -u CUDA_VISIBLE_DEVICES CONDA_PREFIX=/home/jay/miniforge3/envs/isaac311 PATH=/home/jay/miniforge3/envs/isaac311/bin:"$PATH" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -m foothold_s2.scripts.ex42_mesh_mount_check --headless --device cuda:0 --mesh-dir /mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/landing_seed42_v1 --out /mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_landing_cuda0_v1.json > /mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_landing_cuda0_v1.log 2>&1
```

기대: rc 0, `state=passed`, `evaluation_only=true`, `columns=1`, `per_column.checked=1`, `failed_count=0`, `assignment_kept=true`, `checks.scanner_checked=true`. 결과 `/mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_landing_cuda0_v1.json`.
## paper · 7열

```bash
cd /home/jay/mai/wt/foothold-lab/analyst-lx-terrain-d && test "$(git rev-parse HEAD:foothold_s2)" = 847f8abf8e88be7690b00e73b6258e2f3a3708b4 && git diff --quiet HEAD -- foothold_s2 && test ! -e /mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_paper_cuda0_v1.json && env -u CUDA_VISIBLE_DEVICES CONDA_PREFIX=/home/jay/miniforge3/envs/isaac311 PATH=/home/jay/miniforge3/envs/isaac311/bin:"$PATH" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -m foothold_s2.scripts.ex42_mesh_mount_check --headless --device cuda:0 --mesh-dir /mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/paper_seed42_v1 --out /mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_paper_cuda0_v1.json > /mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_paper_cuda0_v1.log 2>&1
```

기대: rc 0, `state=passed`, `evaluation_only=true`, `columns=7`, `per_column.checked=7`, `failed_count=0`, `assignment_kept=true`, `checks.scanner_checked=true`. 결과 `/mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_paper_cuda0_v1.json`.
## start · 12열

```bash
cd /home/jay/mai/wt/foothold-lab/analyst-lx-terrain-d && test "$(git rev-parse HEAD:foothold_s2)" = 847f8abf8e88be7690b00e73b6258e2f3a3708b4 && git diff --quiet HEAD -- foothold_s2 && test ! -e /mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_start_cuda0_v1.json && env -u CUDA_VISIBLE_DEVICES CONDA_PREFIX=/home/jay/miniforge3/envs/isaac311 PATH=/home/jay/miniforge3/envs/isaac311/bin:"$PATH" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -m foothold_s2.scripts.ex42_mesh_mount_check --headless --device cuda:0 --mesh-dir /mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/start_seed42_v1 --out /mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_start_cuda0_v1.json > /mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_start_cuda0_v1.log 2>&1
```

기대: rc 0, `state=passed`, `evaluation_only=true`, `columns=12`, `per_column.checked=12`, `failed_count=0`, `assignment_kept=true`, `checks.scanner_checked=true`. 결과 `/mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_start_cuda0_v1.json`.

검사 범위: 64 env · 일반 reset 3번 · 열별 지정 reset 1번 · 네 발과 몸통 지지면 · 높이 스캔. 1행 고정 지형이라 같은 명목 난이도를 여러 레벨인 것처럼 세지 않는다. 이 결과는 생성기 장착 진단이며 정책 보행·D44 성공률은 별도 평가다.

모델/체크포인트를 인자로 주지 않는다. 기존 예행 명령과 같이 실제 Isaac task를 만들되 학습은 하지 않는다. `state=error` 또는 `failed_criteria`면 JSON traceback/실패행을 보존하고 평가 전에 수정한다.
