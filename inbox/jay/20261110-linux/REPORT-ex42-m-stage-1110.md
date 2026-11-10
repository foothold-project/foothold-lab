# EX-42 M1~M4 Linux 속도 측정 실행기

> 분류: A/정책학습
> 작성: 오흥재 (lead · scripter-lx 반영) · 2026-11-10
> 근거: `LINUX-DAY-EXPERIMENT-ORDER.md` M절 · lead-lx 의뢰 카드 · PR #593의 `--ex42_speed_probe` · Linux L1 NCCL 실측
> 요지: 20·50회 제한 경로로 M1~M4를 순서대로 재고 원자료에서 속도 표를 만든다.
> 상태: 실제 train_start CPU 사전검사 9건 통과 · GPU 미실행 · 실제 시작은 lead-lx 담당

## 구현

- `foothold_s2/scripts/train_start.py`: 속도 재기이며 분산 실행일 때만 `NCCL_SHM_DISABLE=1` 기본값을 넣는다. 스위치가 꺼진 경로는 이 줄을 지나도 환경을 바꾸지 않는다. 사용자가 이미 둔 값은 덮지 않는다.
- `foothold_s2/scripts/ex42_m_stage_linux.sh`와 같은 이름의 `.py`: M1 3072×1×20, M2 1536×2×20, M3 3072×2×20, M4 단일 3072×1×50 두 번과 분산 1536×2×50 한 번을 순서대로 실행한다. `LIVE=1`을 주기 전에는 명령 계획만 출력한다. 소스의 detached·원격 HEAD·읽기 전용 잠금, m12000 SHA, Python 모듈, 실제 `train_start.py --ex42_stage_zero_dry_run`을 모두 확인한 뒤에만 GPU 자식을 시작한다. 첫 update 줄 300초 무응답이면 자기 자식 그룹만 정리하고 실패로 기록한다. 정상 판은 기존 20·50회 제한이 자연 종료한다.
- 판마다 `train.log`, 분산 rank1 로그, `gpu.csv`(1초 표본), `stage.json`을 남긴다. M3 메모리 부족은 별도 `oom`으로 표에 남기고 M4로 진행한다.
- `foothold_s2/scripts/ex42_m_table.py`: 첫 두 회를 제외한 학습 시간 중앙값, GPU별 관측 최대 사용률·메모리, rank1 별도 출력 경로와 파일 수, Windows 27.8초 대비 배수, ORDER의 11/14·11/21 필요 속도를 원문에서 읽어 `summary.csv`, `summary.json`, `summary.md`로 쓴다. M3는 6144 env이므로 3072 env 전이 수 기준으로 시간을 절반으로 환산한다.

## CPU 증거

- `CUDA_VISIBLE_DEVICES=`에서 `test_ex42_m_stage_linux_cpu.py`와 기존 `test_ex42_speed_probe_e0_cpu.py`: **73 passed**. 실제 전처리 스위치, 가짜 `nvidia-smi`, 설치 모듈 `find_spec`, 300초 무응답, 두 rank 가짜 자식 완주, 손으로 만든 로그의 중앙값·정규화·OOM을 시험했다.
- `bash -n` 통과. `LIVE=0` 셸 DRY는 6판을 출력했고 산출 디렉터리를 만들지 않았다.
- 실제 m12000 `model_6000.pt` SHA는 `1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613`으로 확인했다.
- 첫 CPU 사전검사는 `/home/jay/mai/tmp/runner` 기준 자료가 없어 rc1이었다. 원문: `/home/jay/mai/tmp/scripter-lx/m-actual-preflight.log`.
- lead-lx가 `~/data/foothold`와 `~/mai/tmp/runner`를 D: 자료에 심볼릭 링크로 연결한 뒤 실제 `train_start.py --ex42_stage_zero_dry_run`을 재실행했다. M1~M4의 rank 조합 **9건 모두 rc0**, 각 로그에 `EX42_STAGE_ZERO_PREFLIGHT` 및 `app_launcher_started=false`가 있다. 영수증: `/home/jay/mai/tmp/scripter-lx/m-actual-preflights-6/preflight/receipt.json`. GPU·Kit은 실행하지 않았다.
- `~/mai/wt/foothold-lab/m-probe-locked`를 원격 `a87824c0`에서 detached로 만들고 잠갔다. 소스 감사 실측: detached=true · clean=true · writable_count=0 · 보호 파일 15개. 이 잠긴 사본의 `LIVE=0` DRY도 6판을 출력했다.

## 실제 시작 계약

1. `origin/scripter/m-launch-1110` HEAD의 별도 detached 사본 `~/mai/wt/foothold-lab/m-probe-locked`를 만들고 `_out/tools/ex41/lock_checkout.py lock`과 `chmod a-w experiments/EX-42.yaml`을 적용했다. 다시 만들 때는 같은 순서로 하되 기존 폴더를 덮지 않는다. 원본 작업 가지와 같은 디렉터리에서 학습을 돌리지 않는다.
2. `~/mai/foothold-linux.env`는 아직 없다. 만들려면 `cp -n ~/mai/wt/foothold-lab/m-probe-locked/machines/AI-WS01-linux.env.example ~/mai/foothold-linux.env`로 복사한 뒤 실제 값과 경로를 재검사한다. 부모 manifest와 `model_6000.pt`는 연결된 Linux 경로에서 읽힌다. L-8 통과 전달 전에는 실행하지 않는다.
3. 다음 한 줄을 lead-lx가 잠근 사본에서 실행한다. `EX42_M_PARENT_MANIFEST`는 실제 Linux 부모 경로로 바꾼다.

```bash
LIVE=1 FOOTHOLD_LINUX_ENV="$HOME/mai/foothold-linux.env" EX42_M_PARENT_MANIFEST="$HOME/data/foothold/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/manifest.json" bash "$HOME/mai/wt/foothold-lab/m-probe-locked/foothold_s2/scripts/ex42_m_stage_linux.sh"
```

분산 rank1의 별도 임시 출력 경로가 공유 run 아래가 아닌 것과 파일 존재를 확인한다. 공유 폴더의 파일별 작성 PID 추적은 하지 않았으므로 표의 `rank1_shared_path_count=0`은 경로 분리 계약 확인값이다. M4 model_50의 SHA는 남지만 정책 결과 같음은 W15 독립 평가를 따로 해야 하며, 속도 표만으로 판정하지 않는다. 일정 기준은 평가·영상에 쓰는 GPU 시간을 포함하지 않는다.
