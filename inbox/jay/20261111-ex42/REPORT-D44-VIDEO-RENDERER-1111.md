(20:52)
# EX-42 D44 계단참 영상 소비기 준비

> 분류: 리서치 · 평가 도구
> 작성: runner-lx · 2026-11-11
> 근거: EX-42 D44 평가 코드 · 팀장 지시 2026-11-11 19:40 · 19:44 · 19:49
> 요지: m1000 저장본으로 D44 과제 세 종류를 eval_gt와 eval_pred로 기록하고 전 프레임을 검사하는 소비기를 준비한다.
> 상태: 여섯 영상 촬영 완료 · 각 MP4 전 프레임 검수 통과 · SHA-256 기록 완료

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
- `test_ex42_d44_video_cpu.py` + `test_ex42_promotion_size_cpu.py`: 22 passed
- `compileall` · `pyflakes` · `git diff --check`: 통과
- 실제 D44 Kit 영상: 수정 전 실패 1회, 수정 후 재시도 중

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

## 촬영 사전 확인과 초기 실패

20:05 readback에서 E1 사슬 PID 1136161은 m750 평가 중이었고 eval child PID 1258862도 남아 있었다. GPU0 UUID `c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b`와 GPU1 UUID `315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f`가 각각 5.8 GB 사용 중이었다. 따라서 여기서는 Kit이나 GPU를 시작하지 않았다. m1000 저장본의 존재·SHA와 촬영 결과는 아직 확인하지 않았다.

## 팀장 명령 확정 반영

19:49 추가 지시에 맞춰 회전 영상의 선행 정지 구간을 제거했다. 좌·우 회전은 계단참 중앙에서 시작해 해당 방향으로 6초만 회전한다. 정지 후 재출발 영상은 접근 → 정지 띠에서 2초 정지 → 꼭대기로 재출발 순서이며 회전 구간은 없다. 이후 두 지도 입력 모드를 요청받아 세 과제 각각 `eval_gt`와 `eval_pred`를 기록하게 확장했다. 정지 띠 HUD는 실제 띠 진입 여부 · 정지 속도 문턱 통과 여부 · 4발 중 접촉 발 수 · 실제 수평 속도를 출력한다.

20:15 readback에서 E1 사슬 PID 1136161은 m1000 평가 중이고, eval child PID 1325654가 cuda:1 및 cuda:0을 사용하고 있었다. `model_1000.pt` SHA-256은 `7f3b08089462eb077d74e90afa02e6d35fcde8001735fba748a0b30274570e81`이다. 평가 receipt 상태는 아직 `running`이며 사슬은 m1000 완료 마커를 쓰지 않았다. 촬영은 시작하지 않았다.

20:20 m1000 P1은 `FAIL`로 끝났고 네 개 평가 경계(250·500·750·1000)가 모두 완료돼 사슬 프로세스가 종료됐다. 첫 Kit 촬영 시도 중 저장공간은 충분했으나 원본 D44 메시의 `origins=(1,1,3)`을 `mesh_file_generator_cfg`가 거부해 환경 생성 전에 끝났다. 단일 타일 경로에서만 manifest의 `tile_size_m`을 받아 크기를 지정하도록 수정했고, 원본 메시 파일은 변경하지 않았다.

20:28 Kit에서 단일 타일 크기 문제로 실패한 뒤 `mesh_file_generator_cfg`에 명시적 `single_tile_size` 경로를 넣고 D44 캡처 소비기가 manifest 크기를 전달하도록 고쳤다. 다음 시도는 EX-41 pose-loader import 이름을 잘못 적어 env와 정책 로드 후 끝났다. 이후에는 `rgb_array` 경로가 첫 `raw.render()`까지 render product를 늦게 만들고 있는데 마스크 attach가 먼저 실행되어 실패했다. 마지막으로 첫 녹화가 완료된 뒤 intentional stationary command 구간이 73프레임 저동작 검수에 걸렸다. 오류별 수정은 별도 커밋으로 남겼다. 실패한 출력 디렉터리는 보존했고, 완성본은 새 경로에 기록했다.

## 최종 촬영 결과

20:47~20:51에 GPU1 (`315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f`)에서 고정 checkpoint를 촬영했다. m1000 파일 SHA는 `7f3b08089462eb077d74e90afa02e6d35fcde8001735fba748a0b30274570e81`, 계획 SHA는 `a2007c8f00fd1a0b5cab8aeaf425e08cfdd8b6e0401d858b39d680bc9a6e45fa`, 메시 SHA는 `baa59af3347c53c2cdeae674ddc873f26d4b9e38cffdbce4a4dc73cf94febb82`다. 촬영은 1 env · seed 42 · 1280×720 · 25fps · `eval_gt`와 `eval_pred` 각각 수행했다.

| MP4 | 프레임 | 결과 SHA-256 | 전 프레임 검사 | 1-env 판정 |
|---|---:|---|---|---|
| `D44-turn_left_eval_gt-m1000.mp4` | 150 | `2d8d67f8b703356ef8a4ab9c04fe6c8719c3f29547f94aa34cd2c03581c1fa31` | 통과 · 이슈 0 · 로봇 mask 프레임 전부 확인 | 실패: 계단참 이탈 · 회전량 부족 |
| `D44-turn_left_eval_pred-m1000.mp4` | 150 | `0a2067479d124edcfe1ae221ea15e477f542dfef1665c2f83f9edb1e21d943be` | 통과 · 이슈 0 · 로봇 mask 프레임 전부 확인 | 실패: 계단참 이탈 |
| `D44-turn_right_eval_gt-m1000.mp4` | 150 | `6e467fda6793f88be94a2166de0fd7845c642465adff42b00e05aa584ffff382` | 통과 · 이슈 0 · 로봇 mask 프레임 전부 확인 | 실패: 계단참 이탈 · 회전량 부족 |
| `D44-turn_right_eval_pred-m1000.mp4` | 150 | `0f96891d5cd79cc8f67689399ca7ed1282817b06af88660a1670428ee1b32620` | 통과 · 이슈 0 · 로봇 mask 프레임 전부 확인 | 실패: 계단참 이탈 |
| `D44-stop_restart_eval_gt-m1000.mp4` | 300 | `6383353f20a582ffae7fa87e3550576c3e8b6d8ed0c2b3d4884bd77d82a48d44` | 통과 · 이슈 0 · 로봇 mask 프레임 전부 확인 | 실패: 꼭대기 착지 유지 |
| `D44-stop_restart_eval_pred-m1000.mp4` | 300 | `df4d9644af59027331512d1329cd0d2f2d87e05a62eb92eff400e3d488967ad8` | 통과 · 이슈 0 · 로봇 mask 프레임 전부 확인 | 실패: 꼭대기 착지 유지 |

출력 폴더: `/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261111_114505/main/EX-42-B-E1_20261111_114505/eval/d44-video-m1000-20261111-2045`. 각 MP4 옆 JSON에 명령 trace, 화면 증거, per-frame instance mask 증거, 판정과 SHA가 있고, `d44_video_receipt.json`은 6/6 상태 `done`이다 (SHA-256 `6fdee56a5f85eada68eae08f42e53bfe55f02be2bc6d187c833b8eb6609e20ea`). MP4 6개는 OpenCV로 처음부터 끝까지 다시 디코딩했고 sidecar 프레임 수와 일치함을 확인했다.

정지 띠 프레임 100의 화면을 두 모드에서 직접 확인했다. eval_gt는 `stop-band=in · stopped=yes · feet contact=4/4 · speed_xy=0.017 m/s`, eval_pred는 같은 상태에 `speed_xy=0.010 m/s`였다. sidecar에는 의도된 zero-command 프레임이 각각 98/92개라고 기록되어 있다. 이들은 정지 동작의 기록일 뿐, 꼭대기 착지 실패를 성공으로 바꾸지 않는다. 영상 판정은 1환경 결과이며 64환경 D44 집계가 아니다.

## 변경 커밋과 CPU 검증

최종 원격 HEAD `02042b77a8a97dfa8c002f981a4edfdd57c71deb` (`origin/feature/ex42-d44-video-runner-lx-final`). 변경은 RGB render product 생성, 단일 메시 크기 전달, 평가 pose-loader 참조, 정지 명령 구간을 검수기가 인지하는 수정과 각 회귀시험이다. 해당 CPU 묶음은 22 passed; compileall · pyflakes · diff-check 통과.
