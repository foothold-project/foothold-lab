# W65 EX-42 stage-zero 진행 인계

> 분류: C/운영 · 자동화
> 작성: runner · 2026-11-08
> 근거: W65 lead 결정, EX-41 model_6000 manifest 및 SHA, isaac311 CPU 검사
> 요지: W65 stage-zero 검증과 Linux 이어 가기 장치 기록 기준을 정리했다
> 상태: CPU 확인 완료 · GPU0 Kit 5 update 재개 스모크 완료 · 본 학습 미승인

## 결정과 범위

W65는 EX-42 T0-prime stage zero만 최대 1000 update 허용한다. E0+ 및 전체 EX-42 계획은 계속 막혀 있으며, 본 기동 허용 플래그도 false다. EX-41 자기 재개 경로는 사용하지 않는다.

부모는 `C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/model_6000.pt` 이고 manifest가 가리키는 SHA는 `1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613`이다. 이 파일은 EX-41 로컬 6000, 누적 12000이다. 정책 입력 차원 98, critic 666, pose_cmd 폭 2이며 재구성 지도 입력을 사용한다.

## 구현 진척

승인 파일에 W65 결정 ID, 제한된 단계 범위, 1000 update 상한, 부모 SHA, 승인 시각을 고정했다. 승인 SHA가 EX-42 준비 계획에서 검증되며 stage-zero 외 경로는 계속 차단된다.

시작 경로에는 명시 승인 스위치, 정확한 task/device/env/update 제한, 부모 manifest와 파일 SHA 검증, 새 출력 폴더 검사, T0-prime 설정 이식 및 stage-zero runtime/부모 상태 이전을 연결했다. M91에서 fresh와 resume 장치를 모두 cuda:0으로 통일했다. GPU0의 별도 Kit 5 update 재개 스모크는 통과했다. 이는 bounded smoke이며 본 학습 승인이 아니다.

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

다음 CPU 재현 명령은 실제 시작 스크립트의 bounded preflight를 사용한다. EX-42 학습 장치는 fresh와 resume 모두 cuda:0이다. GPU1은 평가와 영상에 사용한다. dry-run 해제나 본 학습 기동은 이 문서의 CPU 확인만으로 승인되지 않는다.

```powershell
$env:TMP='D:/mai-tmp/runner'; $env:TEMP='D:/mai-tmp/runner'
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe foothold_s2/scripts/train_start.py --task=FootholdS2-Go2-S2-SB-v0 --device=cuda:0 --num_envs=3072 --max_iterations=1000 --headless --ex42_plan=foothold_s2/curriculum/ex42-prep.yaml --ex42_approvals=foothold_s2/curriculum/ex42-approvals.yaml --ex42_parent_manifest=C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/manifest.json --ex42_queue_path=D:/mai-tmp/gpu/queue.json --ex42_dispatch_path=D:/mai-wt/foothold-lab/runner-ex42-v016/_out/tools/gpu_jobs/dispatch.py --ex42_p1_score_argv_json='["python","-m","foothold_s2.ex42_score_watch","--table","foothold_s2/curriculum/ex42-prep.yaml","--approvals","foothold_s2/curriculum/ex42-approvals.yaml","--checkpoint-iteration","{iteration}"]' --ex42_source_ref=origin/runner/ex42-v016 --ex42_log_dir=D:/mai-tmp/runner/ex42_w65_preflight_20261108_1025 --ex42_stage_zero_approved --ex42_stage_zero_dry_run
```

이 CPU preflight는 승인 경로와 parser까지만 검증하며 score-watch 숫자와 dispatcher 등록을 증명하지 않는다. 실제 Kit smoke 결과와 증거 경로는 `_out/reports/REPORT-ex42-resume-h1-l1-1108.md`의 2026-11-08 17:12 KST 부록을 참조한다.


## M91 · Linux 이어 가기 장치 기록

EX-42 학습은 Windows와 Linux 모두 `--device=cuda:0`으로 시작하고 이어 간다. GPU1은 평가와 영상 용도다. Linux에서 이어 가기 전, 같은 실행 환경에서 아래 명령을 기록한다.

```bash
nvidia-smi --query-gpu=index,uuid,name --format=csv,noheader
```

이어 가기 영수증에는 `device=cuda:0`, 선택된 index 0의 실제 GPU UUID와 이름, `CUDA_VISIBLE_DEVICES` 값(미설정이면 `unset`), checkpoint 경로와 SHA를 함께 남긴다. 장치 UUID는 호스트에서 조회한 실측값을 기록하며 Windows UUID를 복사하지 않는다. 시작과 재개 모두 동일한 manifest 고정 checkpoint와 EX-42 plan/approval SHA 검증을 유지한다.

CPU 회귀시험은 fresh, full self-resume, bounded resume smoke에서 `cuda:0`을 허용하고 각 경로의 `cuda:1`을 거절한다. 전용 파일 8 passed, 전체 `test_ex42*.py` 118 passed, 1 skipped.
