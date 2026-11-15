> 분류: A/평가
> 작성: 오흥재 (scripter 반영) · 2026-10-29
> 근거: EX-39 Kit smoke try04 `launch_args.txt` · `276bd30b` · `af1cb811` · CPU 시험
> 요지: smoke 인자를 자식 기동 전에 단언하고 A cuda:0, B cuda:1 시작을 분리한다.
> 상태: CPU 검증 완료 · Kit 재실행 미확인

# EX-39 Kit smoke 인자 고침

## 반례와 원인

try04 영수증 `C:/Users/AI-WS01/s2_lab/basic_gait_runs/ex39a_kit_smoke/try04/receipts/ex39/A_20261029_231711_1003946/launch_args.txt`에는 `--max_iterations 4502`, `--basic-stage main`이 있었고 `--smoke-updates`가 없었다. 확인기가 `EX39_SMOKE_UPDATES=2`를 전달했으나 실행 스크립트는 `EX39_KIT_SMOKE_UPDATES`를 읽었다. 기존 CPU 시험은 이미 만들어진 영수증의 판독을 가짜 입력으로 시험했고, 확인기에서 실제 Bash 실행 스크립트까지 환경 변수가 전달되는 경로를 돌리지 않아 누락을 발견하지 못했다.

## 고침

- 확인기가 `EX39_KIT_SMOKE_UPDATES=2`와 `EX39_REQUIRE_KIT_SMOKE=1`을 전달한다.
- 실행 스크립트가 학습 자식을 띄우기 전에 실제 `launch_args.txt`에서 `--smoke-updates 2`, `--basic-stage smoke`, `--max_iterations 3004`를 검사한다. 값이 없거나 중복되거나 다르면 실패 영수증을 쓰고 종료 코드 5로 끝난다. 자식 프로세스를 죽이는 동작은 없다.
- 확인기도 같은 영수증과 `smoke_args_checked.json`을 대조한다.
- 확인기는 `--device cuda:0 --device cuda:1`을 받으면 A와 B를 각 GPU에서 시작한다. B는 A 시작에서 30초 뒤에 시작하며 각 자식의 `TEMP`, `TMP`, `TMPDIR`은 서로 다른 `kit_tmp` 폴더를 가리킨다. 한 번만 `--device cuda:0`을 주면 같은 GPU에서 직렬로 돌린다. `CUDA_VISIBLE_DEVICES`가 설정돼 있으면 ordinal 재매핑 위험 때문에 거절한다. B 평가에는 B의 cuda:1과 임시 폴더가 전달된다. 촬영 경로의 GPU 선택 규칙은 바꾸지 않았다.

## CPU 증거

고정 코드 `af1cb811`의 깨끗한 worktree에서 `isaac311-moects` Python으로 `test_ex39_kit_smoke_cpu.py`와 `test_ex39_cpu.py`를 실행해 **28 passed**를 얻었다. 이 시험에는 실제 `run_ex39.sh`를 Bash `LIVE=0`으로 A cuda:0과 B cuda:1 각각 실행해 생성된 인자 영수증을 읽는 경우가 포함된다. 가짜 자식으로 병렬 시작 순서와 30초 간격, 임시 폴더 분리를 확인했다. 옛 변수 이름만 주고 보호 표지를 켠 실제 Bash DRY 반례는 **종료 코드 5**와 `smoke_preflight_fail.txt`를 냈다. `ruff check --select F`, `bash -n`, `py_compile`, `git diff --check`도 통과했다. GPU 및 Kit는 실행하지 않았다.

코드 4개 파일의 SHA-256은 `SHA256SUMS-scripter-EX39-smoke.txt`에 있다. 병렬 Kit의 실제 임시 저장 경로와 캐시 경합 여부, A·B의 실제 Kit 짧은 확인은 lead 재실행 전까지 미확인이다. 실행 중이던 A·B worktree는 수정하지 않았다.
