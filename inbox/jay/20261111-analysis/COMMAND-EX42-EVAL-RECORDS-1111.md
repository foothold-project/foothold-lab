# 평가 메시 Kit 명령 · E1 뒤 lead 슬롯

> 분류: A/평가
> 작성: 오흥재 · analyst-lx · 2026-11-11 12:21
> 근거: lead 11:47·11:51 실행 슬롯 지시 · CPU 87 통과
> 요지: GPU 학습 종료 뒤 lead가 실행할 한 줄 명령. 파일에는 명령만 있고 실행하지 않았다.
> 상태: bash -n 통과 · Kit 미실행

학습 중 실행하지 않는다. 먼저 landing, 그 다음 paper·start·surface·records. 각 파일은 한 줄 명령이며 코드 tree와 출력 덮어쓰기를 검사한다.

| 묶음 | 한 줄 명령 파일 | 결과 JSON |
|---|---|---|
| landing | `/home/jay/mai/tmp/analyst-lx/mount-eval-landing-v3-1111.sh` | `/mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_landing_cuda0_v3.json` |
| paper | `/home/jay/mai/tmp/analyst-lx/mount-eval-paper-v3-1111.sh` | `/mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_paper_cuda0_v3.json` |
| start | `/home/jay/mai/tmp/analyst-lx/mount-eval-start-v3-1111.sh` | `/mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_start_cuda0_v3.json` |
| surface | `/home/jay/mai/tmp/analyst-lx/mount-eval-surface-v3-1111.sh` | `/mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_surface_cuda0_v3.json` |
| records | `/home/jay/mai/tmp/analyst-lx/mount-eval-records-v3-1111.sh` | `/mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/mount_records_cuda0_v3.json` |

기대: rc 0 · state=passed · evaluation_only=true · per_column 실패 0 · scanner_checked=true. 이는 생성·시작점 장착 확인이지 정책의 과제 성공 판정이 아니다. 실패하면 JSON과 log를 보존하고 같은 출력 경로에 재실행하지 않는다.
