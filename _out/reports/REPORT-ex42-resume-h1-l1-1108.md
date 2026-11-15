> 분류: EX-42 재개 경로 점검
> 작성: runner · 2026-11-08
> 근거: analyst 감사 50e20f66 · EX-42 model_350 재개 경로 · isaac311 CPU 시험
> 요지: 저장된 지형 원점에 첫 reset의 root pose를 맞추고 startup receipt를 교체 전후 검증
> 상태: CPU · analyst 재감사 · GPU0 Kit 5 update 확인 완료

# EX-42 자기 재개 H1 · L1 수정

## H1 · terrain origin과 root pose

감사 50e20f66의 반례는 저장된 `terrain_levels`와 `terrain_types`를 `StartRunner.load()`가 복원한 뒤에도 root pose가 최초 reset에서 선택한 타일 원점에 남는 순서였다. EX-41 `ex41_resume.py`와 `train_start.py`도 load 후 root pose를 재배치하지 않아 이 문제의 해결 사례가 아니었다.

EX-42는 별도의 두 번째 reset을 호출하지 않는다. 기존 첫 `env.reset()` 직전에 checkpoint의 level/type 선택을 실제 terrain 텐서와 `scene.env_origins`에 적용한다. 기존 reset event가 이 원점에서 root pose를 놓고, `runner.load()` 직후이며 첫 rollout 이전에 모든 환경의 root XY와 복원 원점 간 거리 및 reset 범위 위반 수를 검사한다. 결과는 `EX42_SELF_RESUME_ROOT_XY_READBACK` 로그와 `manifest.modes.ex42_self_resume.root_xy_readback`에 남긴다.

코드 위치는 `foothold_s2/scripts/ex42_training_entry.py`의 `restore_stage_zero_resume_terrain_before_reset` 및 `build_stage_zero_resume_root_xy_readback`, `foothold_s2/scripts/train_start.py`의 reset 직전과 runner load 직후이다. CPU 회귀시험은 3072 환경, 6개 레벨과 4개 지형 유형을 사용해 저장 선택을 적용하지 않은 반례에서는 3072개 root가 원점에서 1 m 넘게 벗어나는지 확인하고, reset 뒤에는 기대 오프셋 0.2236 m와 범위 위반 0개를 확인한다. 이 시험은 CPU 모형으로 reset event의 원점 사용을 재현한 결과이며 실제 Kit 물리 배치는 아직 미확인이다.

## L1 · startup receipt 교체 전후 검증

기존 same-run 재개는 chain 생성자가 `startup_receipt.json`을 교체한 뒤에만 identity를 검사했다. 이제 생성자 호출 전 기존 receipt를 검증하고 SHA를 보관한 뒤, 생성자 실행 후 새 receipt의 experiment, state, launch 권한, plan SHA, parent checkpoint SHA를 다시 검증한다. 두 검사 결과와 전후 SHA 및 교체 여부를 `EX42_STAGE_ZERO_CHAIN_RECEIPT` 로그에 기록한다. 새 실행은 생성된 receipt를 검증하며, 일반 EX-42 경로는 기존 chain 생성 경로를 유지한다.

CPU 반례는 잘못된 기존 plan SHA를 builder가 덮어써 통과시키려는 경우와 builder가 새 receipt의 parent SHA를 바꿔 놓는 경우다. 두 경우 모두 builder 전 거절 또는 builder 후 거절을 확인했다. 정상 chain 출력 검증과 AppLauncher보다 앞선 실행 순서도 시험했다. 검증 요약은 startup 직후 로그와 `manifest.modes.ex42_stage_zero.chain_startup_receipt`에 기록된다.

## 확인 결과와 미확인

- analyst 재감사 지적을 반영했다. reset 전 원점 복원에는 부모 model_6000 대신 self-resume 대상 checkpoint(model_350)를 로드해 전달한다. root XY 결과 변수는 `main()`에서 기본 `None`으로 초기화해 새 stage-zero 시작 경로에서도 manifest 작성이 정의되지 않은 지역 변수에 접근하지 않는다.
- EX-42 전체 CPU 시험: `118 passed, 1 skipped in 27.55s`.
- 재감사 수정 후 EX-42 전체 CPU 시험: `118 passed, 1 skipped in 23.51s`.
- `compileall` 통과, `git diff --check` 통과.
- pyflakes에서 이번 변경으로 추가된 미정의 이름은 없었다. 기존 `train_start.py`의 unused import 3건과 중복 `production_launch_allowed` 키 2건은 남아 있다.
- 이 항목들은 Kit 실행 전 작성한 상태 기록이다. 아래 후속 증거에 재감사와 실제 Kit 결과를 추가했다.
- 기존 학습 run과 실행 중인 저장본은 읽기만 했다. 실제 환경 확인은 별도 출력 폴더의 5 update Kit smoke로 수행했다.


## Follow-up evidence, 2026-11-08 17:12 KST

The H1/H2 follow-up is on fixed HEAD `cc7586db9f58b4bf43ef2ce5658e40bede3e7003`. The analyst re-audit report `D:/mai-wt/foothold-lab/analyst-ex41-score-name-1102/_out/reports/REPORT-analyst-ex42-resume-recheck3-1108.md` records H1/H2 blockers 0 and 22 CPU checks passed, 0 skipped. The analyst's CPU 3072-env reset reproduction found 0 root XY reset-bound violations with the resumed checkpoint; the prior-parent substitution produced 1100 violations.

A separate actual Kit smoke ran from detached, read-only checkout `D:/mai-wt/foothold-lab/runner-ex42-h1l1-cc7586db` at the same HEAD. The source run and active learning process were not modified. The smoke command used GPU0, the `model_350.pt` checkpoint, and a fresh output folder `D:/mai-tmp/runner/w65_resume_20261108_1703kit/`. Source checkpoint SHA256 was `7c01f11657b2d66b5fe3b5324f889aea5749c0cebb00333472fb6322342ca75c`.

Evidence files:
- Launch receipt: `D:/mai-tmp/runner/w65_resume_20261108_1703kit.launch.json`
- Kit stdout: `D:/mai-tmp/runner/w65_resume_20261108_1703kit.log`
- Final checkpoint readback: `D:/mai-tmp/runner/w65_resume_20261108_1703kit/model_355_readback.json`
- Runner PID 47400 started at 17:09:14.569829 KST, completed with rc 0 at 17:12:15 KST.

Kit output confirms restored terrain was applied before first reset for all 3072 environments. The root XY readback before first rollout reported `outside_reset_bounds_count=0`, distance min 0.0160241 m, mean 0.3856410 m, p95 0.6026241 m, max 0.7016914 m. The resumed range was local 351 through 355, cumulative 12351 through 12355. `model_355.pt` SHA256 is `17da1350d9637799f67e3abd3424f579d21014b4d867e537b238bbbce56c58bc`; CPU readback reports iter 355, manifest SHA match, 17 optimizer state entries, optimizer LR 0.00038443359375000017, RNG keys cuda/numpy/python/torch, and curriculum at local 355, `EX42_0_T0_prime`, DR 1.0, push Vmax 2.0 m/s. The source `model_350.pt` remained at the same SHA after the smoke.

The smoke establishes this five-update resumed path and root placement check only. It is not a production training run and does not establish longer-run training quality.
