> 분류: A/정책학습 · 운영 · Linux 이전 매니페스트
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-12 23:20
> 근거: 팀장 10/12 23:00 「리눅스 넘어가기 위한 매니페스트 정리 시작 · 아직 확정 아님」 · 이 기계 실측 (아래 「Windows 실측」 칸) · 시스템 런북 mai-os `os/linux-runbook.md` (super · 6c37e44 · vfxpedia/mai-os#34)
> 요지: FOOTHOLD RL (트랙 A 시뮬) 을 Ubuntu 로 옮겨 같은 숫자를 다시 낼 수 있게, 코드 · 환경 · 체크포인트 · 데이터 · 실행 명령 · 다시 세울 기준선을 한곳에 적는다. 시스템 셋업은 super 런북이 맡고 여기는 RL 만 적는다
> 상태: 초안 (확정 아님 · 팀장 · super · pipeline 검토 전) · 설치 시기는 팀장이 정함

# RL 재현 매니페스트 (Linux 이전용)

표기: `확인됨` = 이 기계에서 잼 · `미확인` = 안 잼 · `Linux 에서 잴 것` = 옮긴 뒤 다시 잴 칸. 비밀값은 적지 않는다.

## 1. 옮길 것 (재고)

| 무엇 | Windows 자리 | 크기 (확인됨) | 판 · 해시 | Linux 자리 (제안 · 런북 0-4 와 맞춤) | 옮기는 법 |
|---|---|---|---|---|---|
| foothold-lab 저장소 | `Desktop/jay/인공지능사관학교/foothold-lab` | git | 브랜치 `feature/verify-v2-mvp-jay` | `~/mai/project/foothold-lab` | 새로 clone (한글 경로 문제 사라짐) |
| MoE-CTS 학습 코드 | `C:/isaac/ext/go2_rl_robotlab` | 코드 | 공식 `wertyuilife2/go2_rl_robotlab @28b4516d` · 추적 파일 무수정 (git status: `_eval/` · `_smoke/` 만 추적 밖) | 미정 (`~/mai/project/ext/go2_rl_robotlab` 제안) | clone @28b4516d + 아래 추적 밖 폴더 복사 |
| 우리 평가 · 분기 도구 | `go2_rl_robotlab/_eval/` (코드) | 코드는 작음 · 결과 `_eval/out` 74 GB | 추적 밖 | 같은 상대 경로 | 코드는 foothold-lab 사본 (`inbox/jay/20261008-546-design/eval-*/code/`) 과 대조 뒤 복사 |
| 학습 기록 · 체크포인트 | `go2_rl_robotlab/logs/` | 2.3 GB | 아래 3 절 해시 | 같은 상대 경로 | NAS 경유 복사 · 해시 대조 |
| 평가 결과 · 기록 영상 · CSV | `go2_rl_robotlab/_eval/out/` | **74 GB** | 결함본은 `_bad/` 에 따로 | NAS 우선 · 필요한 것만 Linux | **NAS 백업 먼저** (지금 백업 없음) |
| 학습 실행 로그 | `go2_rl_robotlab/_runs/` | 99 MB | E1 · E2 로그 | 같은 상대 경로 | 복사 |
| Isaac Lab | `C:/isaac/IsaacLab` | (C:/isaac 합 161 GB 의 일부) | `37ddf62` (v2.3.2) · editable 설치 | Linux 에서 새로 설치 | 같은 커밋으로 clone |
| 공개 체크포인트 | `C:/isaac/checkpoints/` | 미확인 (나눠 안 잼) | NVIDIA 공식 Go2 rough · RoboGauge 4 종 (8/12) | 같은 이름 | 복사 · 해시 대조 |
| RoboGauge | `C:/isaac/ext/RoboGauge` (10/13 밤 하위 작업이 옮기는 중) | 미확인 | v1.1.9 add2c7e | 같은 상대 경로 | clone 같은 커밋 |
| v1 · v2 모델 | foothold-lab `models/` | git | v2 sha256 `e5c21321…` | 저장소와 함께 | clone 으로 따라옴 |

C:/isaac 전체 161 GB (확인됨). 10/12 아침 lead 가 말한 「약 23 GB」 는 낡은 값이다. 오늘 기록 영상 · CSV 로 `_eval/out` 만 74 GB 가 됐다.

## 2. 환경

| 칸 | Windows 실측 (확인됨) | Linux 에서 잴 것 |
|---|---|---|
| conda 환경 | `isaac311-moects` (isaac311 복제 · 원본은 건드리지 않음) | 같은 이름으로 새로 만듦 |
| Python | 3.11.15 | 같은 판 |
| torch | 2.7.0+cu128 (torch 안의 CUDA 런타임 12.8) | 같은 판 · `torch.cuda.is_available()` · 두 장 보임 |
| Isaac Sim | pip `isaacsim==5.1.0.0` (+ 하위 패키지) | 같은 판 · Linux wheel |
| Isaac Lab | editable `@37ddf626` (v2.3.2) | 같은 커밋 |
| robot_lab · rsl_rl | editable `go2_rl_robotlab@28b4516d` | 같은 커밋 |
| 그 밖 | numpy 1.26.0 · tensorboard 2.21.0 · warp-lang 1.15.0 · 전체 240 줄 `pip-freeze-isaac311-moects.txt` (같은 폴더) | freeze 를 견줘 다른 줄만 기록 |
| NVIDIA 드라이버 | 591.86 (Windows) | Linux 드라이버 판 (런북 3-5) |

**런북 3-5 CUDA 판에 대한 답 (lead 의견):** 학습은 pip wheel 안의 CUDA 12.8 런타임을 쓴다. 그래서 시스템 CUDA toolkit 은 학습에 꼭 필요하지 않고, **드라이버가 CUDA 12.8 과 Isaac Sim 5.1 Linux 요구를 함께 만족하면 된다.** 그 최소 드라이버 판은 문서에서 아직 확인하지 않았다 (미확인 · Isaac Sim 5.1 · CUDA 12.8 공식 표로 확인할 것). 시스템 nvcc 는 3DGS 같은 컴파일 도구에 필요하다 (`ws-3dgs-toolchain-limits`). RTX 5080 은 Blackwell (sm_120) 이라 드라이버가 그 세대를 지원해야 한다.

## 3. 체크포인트 (확인됨 · sha256 앞 16 자리 · 크기 26,367,183 B)

| 무엇 | 파일 | sha256 |
|---|---|---|
| E1 시드 42 · 20,000 | `logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192/model_20000.pt` | `c8951b797dbe4157` |
| E1 · 20,499 | 같은 폴더 `model_20499.pt` | `7e52a50260866603` |
| E2 시드 43 · 20,000 | `…/2026-10-11_12-39-32_e2_seed43_n8192/model_20000.pt` | `d75bfd12c59c15e7` |
| E2 · 20,499 | 같은 폴더 `model_20499.pt` | `ac4c9240704aa083` |
| 오늘 밤 CMD-R 쌍 (학습 중) | `_eval/out/branch/cmdr_s1042_{off,on}_u4000/model_*.pt` | 끝난 뒤 적음 |

## 4. 실행 명령 (Windows · Linux 에서 다시 확인)

| 무엇 | 명령 (Windows 실측) | 확인 (답을 아는 결과) |
|---|---|---|
| E1 학습 | `OMNI_KIT_ACCEPT_EULA=YES CUDA_VISIBLE_DEVICES=0 python scripts/rsl_rl/train.py --task=RobotLab-Go2-v0 --headless --num_envs 8192 --seed 42 --max_iterations 20500 --run_name e1_seed42_n8192` (저장된 `params/agent.yaml` 의 seed 42 · max_iterations 20500 · run_name 에서 재구성) | iteration 약 4.2~4.5 s (8,192 env · RTX 5080 한 장) |
| 분기 학습 (CMD-R 등) | `_eval/branch/night_20261012_cmdr.sh` · `branch_run.py --parent … --seed 1042 --num_envs 8192 --updates 4000 --cmdr off|on` (`BRANCH_CONTRACT_CONFIRMED` 필요) | 관문 a · b · c · cmdr (`BRANCH-CMDR-tools.md`) 다시 통과 |
| Q 평가 | `_eval/q_eval.py` (Q 주 실행 1100 env · noise 끔 · 평가 시드 1000) | E1 model_20000 의 기존 Q 표와 같은 값 |
| 기록 재생 영상 | `_eval/q_video.py` · `hud_make.py` (전 프레임 관문 둘) | 결함 0 · `video_frame_audit.py` 0 |
| 두 GPU 학습 (Linux 만) | Isaac Lab 분산 학습 (`torch.distributed.run --nproc_per_node=2 … --distributed`) · 이 저장소 runner 의 분산 지원 여부 | **미확인** · Linux 에서 처음 시험 |

## 5. Linux 에서 다시 세울 기준선 (순서)

1. **E0 재현:** 10 iteration smoke 가 돈다. Isaac URDF 변환이 빈 USD 를 내지 않는다 (Windows 한글 경로 문제의 재발 확인).
2. **같은 숫자 확인:** E1 `model_20000` 을 Linux 에서 Q 평가 (같은 평가 시드 · 같은 env 수) 해 Windows 표와 견준다. OS 가 바뀌어도 평가가 같은지 먼저 본다.
3. **한 장 학습 처리량:** 8,192 env 로 100 iteration. Windows 4.2~4.5 s 와 견준다.
4. **두 장 학습:** 16,384 env (저장소 기본값) 분산 학습 smoke. 되면 기준선을 「16,384 env 로 다시 E1」 로 세울지 팀장이 정한다. 그러면 Windows 8,192 부모와는 갈라 비교하지 않는다 (env 수가 두 번째 변수가 된다).
5. **화면 GPU:** Windows 에서 GPU 1 이 화면을 맡아 약 5~6 GB 를 쓰고 8,192 env 학습이 안 들어갔다. Linux 에서 어느 GPU 가 화면을 맡을지 정한다 (런북 3 절 · Xorg).

## 6. 알려진 함정 (Windows 에서 겪은 것)

- 한글 경로에서 Isaac URDF importer 가 빈 USD 를 내고 종료 0 (10/10 E0) → Linux 는 영문 경로만.
- 16,384 env 한 장은 VRAM 을 넘쳐 Windows 에서는 공유 메모리로 새며 iteration 96 s (오류 없음). Linux 에서는 OOM 으로 죽을 수 있다 (미확인).
- 이어 학습은 가중치 · Adam 만 되살리고 명령 · 보상 일정 · 지형 레벨은 처음으로 → 분기 실행기로만 잇는다.
- Isaac 렌더는 화면용 GPU 를 쓴다. `CUDA_VISIBLE_DEVICES` 로 가리면 창 생성에서 조용히 멈춘다.
- 기록 재생 렌더가 일부 프로세스에서 빈 프레임을 낸다 (10/12 · 기전 미확인) → 렌더 · 발행 관문 둘을 그대로 가져간다.

## 7. 열린 것

- 이 매니페스트는 확정 아님. 팀장 · super · pipeline 검토 뒤 고친다.
- `C:/isaac/checkpoints/` 와 Isaac Lab 폴더 크기를 나눠 재기 · NAS 백업 계획 (74 GB `_eval/out` 포함) 은 super 런북 1 절과 맞춘다.
- 두 GPU 분산 학습이 이 저장소 runner 로 되는지 (미확인).
