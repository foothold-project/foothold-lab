(20:05)
# EX-42 D44 계단참 영상 소비기 준비

> 분류: 리서치 · 평가 도구
> 작성: runner-lx · 2026-11-11
> 근거: EX-42 D44 평가 코드 · 팀장 지시 2026-11-11 19:40 · 19:44 · 19:49
> 요지: m1000 저장본으로 D44 과제 세 종류를 eval_gt와 eval_pred로 기록하고 전 프레임을 검사하는 소비기를 준비한다.
> 상태: CPU 사전검사 통과 · 실제 촬영은 사슬 종료와 GPU 유휴 확인 대기

## 구현

새 `foothold_s2.eval.ex42_d44_video` 모듈은 실제 D44 평가 계획·단일 타일 메시·m1000 체크포인트 SHA를 사전검사하고, Kit 실행 시 체크포인트 내장 회차가 1000인지 확인한다. 한 환경만 만들고 세 과제를 `eval_gt`와 `eval_pred` 각각 기록한다.

| 과제 | 지도 모드 | 시작 위치 | 명령 순서 | 길이 |
|---|---|---|---|---:|
| `turn_left` | eval_gt · eval_pred | 계단참 중앙 | 제자리 좌회전 6초 | 각 6초 |
| `turn_right` | eval_gt · eval_pred | 계단참 중앙 | 제자리 우회전 6초 | 각 6초 |
| `stop_restart` | eval_gt · eval_pred | 접근 지점 | 접근 최대 4초 · 정지 띠 2초 정지 · 꼭대기 재출발 최대 6초 | 각 12초 |

요청 명령 대 실제 vx/wz, 현재 단계(세부 phase), 과제 이름을 위 HUD에 쓰고, 아래 띠에 과제 · 시작 위치 · 명령 순서를 표기한다. 결과는 D44 평가기와 같은 접근 · 정지 · 착지 · 회전 기준으로 자체 판정해 전 프레임에 PASS/FAIL을 넣으며, 영상의 결과와 D44 64환경 집계를 혼동하지 않도록 각 sidecar에 1환경 결과와 실제 명령/속도 요약을 따로 기록한다.

전 프레임 검사는 기존 `c_layer_frame_audit.audit_video`로 디코딩해 검정·단색·멈춤·화면 밖 투영을 확인하고, 매 프레임 instance mask로 로봇 픽셀 존재와 타 로봇 0개를 확인한다. 화면 렌더만으로 물리 tick 또는 명령이 변하면 실패시킨다.

## CPU 사전검사

실제 저장 메시 `/home/jay/data/foothold/s2_lab/ex42_eval_mesh_1111/landing_seed42_v2`와 고정 평가 계획 `foothold_s2/curriculum/ex42-prep.yaml`을 사용했다. 답을 아는 임시 파일 `model_1000.pt`는 계획기 형식 시험에만 썼고, 실제 체크포인트로 간주하지 않았다. plan-only가 계획에서 mesh SHA `baa59af3…`와 평가 계획 SHA `a2007c8f…`를 확인해 세 eval_gt 과제 · 순서 · 7/7/13초 · envs=1 을 출력했다.

- `compileall`: 통과
- `pyflakes`: 통과
- `test_ex42_d44_video_cpu.py`: 6 passed
- 실제 D44 Kit 영상 실행: 미실행, 아래 실행 사슬이 m1000에 도달하고 GPU가 비면 수행

## 경로 사용 대조

| 용도 | 현재 사용 경로 | 읽기 확인 | 의미 |
|---|---|---|---|
| D44 plan의 source mesh | `/home/jay/data/foothold/.../ex42_eval_mesh_1111/landing_seed42_v2` | plan-only가 실제 폴더·manifest·mesh SHA 통과 | 별칭 경로 |
| E1 chain의 run | `/home/jay/data/foothold/s2_lab/ex42_main_20261111_114505/...` | chain PID 1136161의 argv | 별칭 경로 |
| P1 checkpoint/output | `/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261111_114505/...` | eval child PID 1258862의 argv | 실제 마운트 경로 |
| source worktree | `/home/jay/mai/wt/foothold-lab/ex42-post-e1-dd453688` | chain argv | Linux worktree |
| recorder worktree | `/home/jay/mai/wt/foothold-lab/runner-ex42-d44-video-lx` | 이번 코드 작업 자리 | Linux worktree |

`/home/jay/data/foothold`와 `/mnt/win-d/mai/data/foothold`는 모두 `/mnt/win-d/mai/data/foothold`로 해석된다. 실제 m750 파일 양쪽 `stat`은 같은 device/inode `66311:4559543`, 같은 크기 24,965,899 bytes였고 SHA-256은 `f97b2f0a…`로 같았다. 실제 D44 메시도 양쪽 device/inode `66311:4550389`, 크기 1,730 bytes, SHA-256 `86231d2f…`로 같았다. D:는 `/dev/nvme2n1p2`의 `ntfs3` 마운트다.

향후 새 데이터 참조의 정규 경로는 `/mnt/win-d/mai/data/foothold`로 두고, 기존 manifest와 스크립트 호환을 위해 `/home/jay/data/foothold` 심볼릭 링크는 유지하는 안을 제안한다. 기존 기록의 경로를 일괄 치환하거나 파일을 이동하지 않는다. 입력을 받은 도구는 resolve된 경로와 SHA를 영수증에 남긴다.

## 촬영 대기 상태

20:05 readback에서 E1 사슬 PID 1136161은 m750 평가 중이었고 eval child PID 1258862도 남아 있었다. GPU0 UUID `c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b`와 GPU1 UUID `315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f`가 각각 5.8 GB 사용 중이었다. 따라서 여기서는 Kit이나 GPU를 시작하지 않았다. m1000 저장본의 존재·SHA와 촬영 결과는 아직 확인하지 않았다.

## 팀장 명령 확정 반영

19:49 추가 지시에 맞춰 회전 영상의 선행 정지 구간을 제거했다. 좌·우 회전은 계단참 중앙에서 시작해 해당 방향으로 6초만 회전한다. 정지 후 재출발 영상은 접근 → 정지 띠에서 2초 정지 → 꼭대기로 재출발 순서이며 회전 구간은 없다. CPU 시험은 회전 첫 tick부터 회전 명령임과 영상 길이 6/6/12초를 확인한다. 이 명령 변경 커밋 뒤에도 실제 Kit 영상 촬영은 E1 사슬 종료 및 GPU 유휴 확인 전까지 하지 않는다.

20:15 readback에서 E1 사슬 PID 1136161은 m1000 평가 중이고, eval child PID 1325654가 cuda:1 및 cuda:0을 사용하고 있었다. `model_1000.pt` SHA-256은 `7f3b08089462eb077d74e90afa02e6d35fcde8001735fba748a0b30274570e81`이다. 평가 receipt 상태는 아직 `running`이며 사슬은 m1000 완료 마커를 쓰지 않았다. 촬영은 시작하지 않았다.
