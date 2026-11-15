> 분류: EX-42 운영 인계
> 작성: runner · 2026-11-08 15:56 KST
> 근거: 2b3e504f CPU 시험 및 잠금 소스 검사
> 요지: model_350 자기 이어 가기 5 update Kit 확인용 명령과 검수 순서
> 상태: analyst 독립 점검 대기

# W65 자기 이어 가기 Kit 확인 인계

> 상태 갱신: 이 문서의 2b3e504f 명령은 analyst 감사 H1/L1 수정 전 기준이라 사용하지 않는다. 최신 구현과 CPU 증거는 `REPORT-ex42-resume-h1-l1-1108.md`를 따른다. 실제 Kit 5 update는 analyst 막음 0 확인과 lead의 GPU0 대기열 배정 뒤에만 실행한다.

## 상태

- 구현 HEAD: `2b3e504f75abe524474d992afa4f0ca5f4e08318` (`runner/ex42-resume-w65`), `origin/runner/ex42-resume-w65`에 push 완료. 작업 사본은 clean.
- 별도 고정 소스: `D:/mai-wt/foothold-lab/r42lock`, detached HEAD `2b3e504f`; source audit에서 launch HEAD와 원격 ref가 일치하고 writable 파일 0개로 확인됨. `experiments/EX-42.yaml`도 read-only 처리.
- CPU 확인: `test_ex42*.py` 114 passed, 1 skipped (`D:/mai-tmp/runner/pytest-w65-final-cpu`); `test_start_runner.py` 및 stage-zero 시험 14 passed (`D:/mai-tmp/runner/pytest-w65-runner-unit-r2`); compileall 및 pyflakes 정의 안 된 이름 검사 통과. pyflakes의 기존 unused import/중복 키 경고는 남아 있음.
- isaac311 실제 parser/preflight DRY는 Kit을 띄우지 않고 통과. 모델 경로, model_350 SHA와 update 매핑을 확인했으며 `app_launcher_started:false`.
- 원본 학습 run은 읽기 전용. 기존 학습 PID 93176 및 원본 run에 쓰기/종료하지 말 것. Kit 확인은 analyst의 막음 0 확인 후 lead가 GPU0 대기열에 넣는다. GPU0은 약 16:25 무렵 비는 것으로 예상됐으며 현재 비어 있는지는 미확인.

## 고정 입력

- 이어 받을 run: `C:/Users/AI-WS01/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914`
- 선택 checkpoint: `model_350.pt`, SHA-256 `7c01f11657b2d66b5fe3b5324f889aea5749c0cebb00333472fb6322342ca75c`
- CPU preflight 당시 manifest SHA-256 `c79d8cc177ba3d007c25d8cc19bd8ad1b14949bcbdce5638fab632ab680e2fe3`, completed_updates 400. 실행 직전 manifest는 학습 진행으로 바뀔 수 있으므로 고정값으로 강제하지 않고, 선택한 model_350 파일 SHA와 저장 상태를 다시 검증한다.
- 부모 m6000 SHA-256 `1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613`
- 계획 SHA-256 `2406e1c2de9f35bdb83ef4b7c4586c6ab2c5b7961d67ce8b4b31b203bae47fd6`; 승인 SHA-256 `694782ce7efeb99b3c6ee6fe197bf90ab552a6f5809ee4c4c81b47eb206afa5e`.
- 임시 출력 run: `D:/mai-tmp/runner/w65_resume_20261108_1625` (확인 당시 미존재). 사용 전 재확인하고, 이미 생겼으면 새 시각 이름 사용.

## lead가 대기열에 넣을 Kit 명령

PowerShell에서 아래 한 줄을 사용한다. `r42lock`은 위에서 audit한 읽기 전용 detached checkout이다. 출력은 새 임시 run에만 기록한다.

```powershell
$env:OMNI_KIT_ACCEPT_EULA='YES'; $env:TMP='D:/mai-tmp/runner'; $env:TEMP='D:/mai-tmp/runner'; Set-Location 'D:/mai-wt/foothold-lab/r42lock'; & 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' -m foothold_s2.scripts.train_start --task=FootholdS2-Go2-S2-SB-v0 --device=cuda:0 --num_envs=3072 --max_iterations=1000 --headless --map_input=reconstruction --ex42_plan='D:/mai-wt/foothold-lab/r42lock/foothold_s2/curriculum/ex42-prep.yaml' --ex42_approvals='D:/mai-wt/foothold-lab/r42lock/foothold_s2/curriculum/ex42-approvals.yaml' --ex42_parent_manifest='C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/manifest.json' --ex42_log_dir='D:/mai-tmp/runner/w65_resume_20261108_1625' --ex42_queue_path='D:/mai-tmp/gpu/queue.json' --ex42_dispatch_path='_out/tools/gpu_jobs/dispatch.py' --ex42_p1_score_argv_json='["C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe","-m","foothold_s2.ex42_score_watch","--table","D:/mai-wt/foothold-lab/r42lock/foothold_s2/curriculum/ex42-prep.yaml","--approvals","D:/mai-wt/foothold-lab/r42lock/foothold_s2/curriculum/ex42-approvals.yaml","--checkpoint-iteration","{iteration}"]' --ex42_source_ref=origin/runner/ex42-resume-w65 --ex42_stage_zero_approved --ex42_resume_from='C:/Users/AI-WS01/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914/model_350.pt' --ex42_resume_smoke --ex42_resume_updates=5
```

This is a five-update smoke resume into a new temporary run. It is not a production-resume command and does not authorize extending the existing training run. The source checkpoint and run remain untouched.

## 확인 순서와 통과 증거

1. 대기열이 실제 시작한 뒤 PID, 프로세스 시작 시각, 명령행, 새 출력 경로를 기록한다. GPU0 사용 승인은 lead가 확인한다.
2. 초기 영수증에서 `EX42_STAGE_ZERO_RESUME` 및 `EX42_SELF_RESUME_READBACK`를 확인한다. model_350 SHA, 부모/계획/승인 SHA가 핀과 일치해야 한다. 복원된 optimizer, RNG, curriculum clock/stage/DR, map-switch 상태를 읽어 일치 여부를 기록한다.
3. 첫 update는 local 351, 누적 12351이어야 한다. 이어서 정확히 5 update 수행: local 351–355, 누적 12351–12355.
4. 완료 후 새 run의 저장본과 manifest를 CPU로 되읽는다. model_355 SHA, 저장 회차 및 manifest 연결, optimizer/RNG/curriculum 상태를 확인한다. model_350 SHA가 원본과 같고 원본 run의 manifest 및 저장본이 수정되지 않았는지 다시 확인한다.
5. 첫 증거가 잘못되면 lead가 이 smoke 프로세스만 중단하고 원본 학습 PID 93176은 건드리지 않는다.

아직 Kit 실행, GPU 실행 및 5 update 결과는 미확인이다. analyst 독립 점검 결과가 0 막음일 때에만 lead가 GPU0 대기열에 넣는다.
