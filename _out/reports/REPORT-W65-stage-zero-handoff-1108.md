# W65 EX-42 stage-zero 진행 인계

> 분류: C/운영 · 자동화
> 작성: runner · 2026-11-08
> 근거: W65 lead 결정, EX-41 model_6000 manifest 및 SHA, isaac311 CPU 검사
> 요지: W65 승인 범위에 한정한 EX-42 T0-prime 1000 update 경로와 CPU preflight를 준비했다
> 상태: CPU 확인 완료 · Kit 확인 대기

## 결정과 범위

W65는 EX-42 T0-prime stage zero만 최대 1000 update 허용한다. E0+ 및 전체 EX-42 계획은 계속 막혀 있으며, 본 기동 허용 플래그도 false다. EX-41 자기 재개 경로는 사용하지 않는다.

부모는 `C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/model_6000.pt` 이고 manifest가 가리키는 SHA는 `1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613`이다. 이 파일은 EX-41 로컬 6000, 누적 12000이다. 정책 입력 차원 98, critic 666, pose_cmd 폭 2이며 재구성 지도 입력을 사용한다.

## 구현 진척

승인 파일에 W65 결정 ID, 제한된 단계 범위, 1000 update 상한, 부모 SHA, 승인 시각을 고정했다. 승인 SHA가 EX-42 준비 계획에서 검증되며 stage-zero 외 경로는 계속 차단된다.

시작 경로에는 명시 승인 스위치, 정확한 task/device/env/update 제한, 부모 manifest와 파일 SHA 검증, 새 출력 폴더 검사, T0-prime 설정 이식 및 stage-zero runtime/부모 상태 이전을 연결했다. DR은 승인된 1.0으로 읽고, 첫 reset·첫 관측·부모 이전을 출력하도록 준비했다. 이 실행 경로는 아직 Kit에서 실행하지 않았다.

## CPU 증거

- `test_ex42_prep_cpu.py`, `test_ex42_training_entry_cpu.py`, `test_ex42_stage_zero_cpu.py`: 20 passed, 6.25초.
- 실제 `train_start.py` parser를 통한 승인 양성 dry-run: `stage_zero_preflight_passed`, parent SHA 일치, `app_launcher_started=false`, `production_launch_allowed=false`, exit 0.
- 실제 parser 음성 입력에서 승인 스위치를 뺀 경우: 승인 요구 `ValueError`로 Kit import/실행 전 거절, exit 1.
- 변경 Python 파일 `py_compile` 통과, `git diff --check` 통과.
- GPU/Kit 미실행. 첫 reset DR 1.0, 지형 L5, 실제 env 차원, model_12050 저장 및 재개용 continuation 상태는 미확인이다.

## 작업 트리와 다음 단계

커밋 대상 W65 파일은 다음 10개이며 이 보고서도 이번 커밋에 포함한다.

- `foothold_s2/curriculum/ex41.py`
- `foothold_s2/curriculum/ex42-approvals.yaml`
- `foothold_s2/curriculum/ex42-prep.yaml`
- `foothold_s2/curriculum/ex42_prep.py`
- `foothold_s2/runners/start_runner.py`
- `foothold_s2/scripts/ex41_startup.py`
- `foothold_s2/scripts/ex42_training_entry.py`
- `foothold_s2/scripts/train_start.py`
- `foothold_s2/tests/test_ex42_prep_cpu.py`
- `foothold_s2/tests/test_ex42_stage_zero_cpu.py`

다음 CPU 재현 명령은 실제 시작 스크립트의 bounded preflight를 사용한다. Kit 실행은 이 명령에 `--ex42_stage_zero_dry_run`을 빼는 것으로 직접 시작하지 말고, 변경 커밋이 원격 고정 ref에 반영된 뒤 dispatcher의 승인된 GPU1 probe로만 진행해야 한다.

```powershell
$env:TMP='D:/mai-tmp/runner'; $env:TEMP='D:/mai-tmp/runner'
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe foothold_s2/scripts/train_start.py --task=FootholdS2-Go2-S2-SB-v0 --device=cuda:1 --num_envs=3072 --max_iterations=1000 --headless --ex42_plan=foothold_s2/curriculum/ex42-prep.yaml --ex42_approvals=foothold_s2/curriculum/ex42-approvals.yaml --ex42_parent_manifest=C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/manifest.json --ex42_queue_path=D:/mai-tmp/gpu/queue.json --ex42_dispatch_path=D:/mai-wt/foothold-lab/runner-ex42-v016/_out/tools/gpu_jobs/dispatch.py --ex42_p1_score_argv_json='["python","-m","foothold_s2.ex42_score_watch","--table","foothold_s2/curriculum/ex42-prep.yaml","--approvals","foothold_s2/curriculum/ex42-approvals.yaml","--checkpoint-iteration","{iteration}"]' --ex42_source_ref=origin/runner/ex42-v016 --ex42_log_dir=D:/mai-tmp/runner/ex42_w65_preflight_20261108_1025 --ex42_stage_zero_approved --ex42_stage_zero_dry_run
```

이 CPU preflight는 승인 경로와 parser까지만 검증하며 score-watch 숫자, dispatcher 등록, Kit runtime 및 저장 결과를 증명하지 않는다. 다음 담당자는 새 detached 고정 checkout에서 승인 SHA와 source ref를 다시 맞추고, lead가 관리하는 dispatcher probe로 이 공백을 확인해야 한다.
