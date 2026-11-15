> 분류: A/평가 · Codex Worker 17g A 작업 보고
> 작성: Codex Worker · 2026-10-14 04:56 (초기 기록 02:44)
> 근거: TASK-codex-worker-17g-fix.md · VERIFY-astra-17g.md · 원본 SHA256 대조 · test-initial.log · 출력 폴더 읽기 조사
> 요지: 초기 금지 폴더 쓰기 사고를 보존하고, 재개 뒤 A1~A5 코드와 CPU 대조군·반례·변이 시험 결과를 기록한다.
> 상태: A 코드 작성 및 CPU 시험 완료 · ASTRA 독립 검증 대기 · 보호 폴더 전역 차이 11건 기록

# 17g A 작업 보고

## 초기 중단 기록

당시 A1~A5는 고치지 못했다. 원본을 새 파일 이름으로 복사하고 시험을 포팅하던 중, 복사된 `unseen_driver_cmdr_v6.py`가 여전히 `UNCR_V5_ROOT`와 `out_uncr_v5`를 참조하는 상태에서 합성 시험을 실행했다. 시험의 가짜 자식은 GPU와 Isaac을 실행하지 않았으나, 드라이버는 실제 `_eval/out_uncr_v5`에 기록했다. 이는 작업서 §1 금지를 어긴 것이다. 발견 직후 시험과 수정을 멈췄다. 금지 폴더의 파일을 지우거나 되돌리거나 옮기지 않았다.

## 원본과 새 파일

원본 네 파일의 시작 SHA256은 작업서의 앞 12자와 일치했다. 종료 시에도 네 원본의 SHA256 앞 12자가 각각 `df0cf1e0a1df`, `089574adfa10`, `983d7b434634`, `ff1ef3fdac09`로 같았다.

| 새 파일 | 현재 SHA256 | 상태 |
|---|---|---|
| `_eval/unseen_driver_cmdr_v6.py` | `df0cf1e0a1dfd3e2917cf5ba6df3cce14a792ecdc2348bf7a2e6a3d0240a7762` | v5와 같은 바이트. 사용 금지 |
| `_eval/uncr_revalidate_v3.py` | `089574adfa102ee8d83e7d7414ae5f028c8c66b2be19e7820772524d30553e93` | v2와 같은 바이트. 사용 금지 |
| `_eval/test_uncr_v6.py` | `0bb265896a21e15b4368e1b93fed90cd100a147e89f60b915d80134d61e87fd3` | 포팅 중. 시험 전체 미완료 |
| `_eval/mutate_uncr_v6.py` | `4be58c4561c973253567b8a7070fb1ca5b893821c93823eb42b60360dae7d552` | 포팅 중. 실행하지 않음 |

`frozen_exec.py`는 만들지 않았다. v6 manifest, 승인 JSON, 변이 실행 자료도 만들지 않았다.

## 초기 시험과 실패

해석기는 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe`였고 `CUDA_VISIBLE_DEVICES=-1`, `UNCR_TEST_SKIP_REAL=1`, `PYTHONDONTWRITEBYTECODE=1`로 실행했다. 명령은 다음과 같다.

```powershell
$env:CUDA_VISIBLE_DEVICES='-1'
$env:UNCR_TEST_SKIP_REAL='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe' -B 'C:/isaac/ext/go2_rl_robotlab/_eval/test_uncr_v6.py' *> 'C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexA/test-initial.log'
```

첫 실행 종료 코드는 1이다. 완주한 시험이 아니므로 분모 50의 통과율로 읽으면 안 된다. 중단 전 출력은 `PASS` 20줄, `FAIL` 1줄이다. F03은 재검사기 파일명 포팅 불일치로 실패했다. 이어 D01의 가짜 slot 종료 코드 94가 보호 오류로 분류되었고 실제 `out_uncr_v5`에 `HALT_v5.json`을 남겼다. 다음 D02에서 앞선 HALT 때문에 실행 기록이 없어 `IndexError`로 중단했다. 새 A1 대조군과 반례인 D11은 코드에 적었지만 도달하지 못했다. 변이 38개와 추가 변이는 0개 실행했다. 실제 `out_uncr` 재검은 0회다. A2 종료 코드 92의 겹침은 `rg`로 확인한 범위에서 발견되지 않았으나 전체 구현과 시험은 하지 않았다.

원로그: `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexA/test-initial.log`, SHA256 `c1f5f2dbb02d36ab63fd32bd50a4b5d0562e58ce5a95f5ba0cd94fb0a262a6f6`. 합성 자료는 `codexA/test-fixtures/`에 남겼다. 그 폴더의 시험 함수별 내부 변형 총수는 세지 못했다.

## 금지 폴더 영향, 읽기 조사

`_eval/out_uncr_v5`의 최상위에서 2026-10-14 02:42:26 수정 시각을 가진 파일 네 개를 확인했다. 이 파일들이 시험 전에 존재했는지의 기준 목록은 확보하지 못했다. 아래의 생성 또는 덮어쓰기 가능성을 모두 영향으로 취급한다.

| 파일 | 현재 SHA256 |
|---|---|
| `driver_v5.json` | `9e3baea4d5cd61c54694bc511c9f344df1a78845dd56c1eb463b75701e9e7199` |
| `HALT_v5.json` | `a1cd4d79ee9d23e6e3554f6eef503f121d7dfe29661648766a3797a5b04e6167` |
| `uncr_par_gap_fwd05.guard.json` | `75d39dac91335b61264b7f70e43f20169ce53cf74f273663c27b4afe6e232389` |
| `uncr_par_gap_fwd05.slot.json` | `fb8c98747e2f63f41b49a273cbea9c29f443d5996f7800955aa6b31dc1d3351d` |

`manifest_v5.json`은 최상위 읽기 조사에서 수정 시각 00:43:32였으며 이번 실행으로 바뀐 증거는 없다. `out_uncr_v5` 안의 이동 여부는 실행 전 목록이 없어 미확인이다. 학습 스크립트 `branch/night_20261013_cmdr1043_v3.sh`, GPU 프로세스, `out_uncr`, slot, registry에는 의도적으로 쓰거나 종료 명령을 내리지 않았다. 새 시험의 합성 작업 폴더 외 쓰기는 위 네 파일이 확인된 범위다.

## A 항목별 상태

| 항목 | 상태 | ASTRA 반례 차단 여부 |
|---|---|---|
| A1 GPU 대기 뒤 재검사 | D11 시험만 작성, 미실행 | 미확인. 드라이버는 v5 바이트 그대로라 차단하지 못함 |
| A2 잠금 뒤 `frozen_exec.py` | 미구현 | 차단하지 못함 |
| A3 환경 지문 | 원자료 값 읽기만 완료, 미구현 | 차단하지 못함 |
| A4 새 manifest | 미생성 | 미확인 |
| A5 시험과 변이 | 초기 시험 중단, 변이 미실행 | 미확인 |

설계와 달리 시험 대상의 `HERE`와 출력 루트를 먼저 격리하지 않은 것이 직접 원인이다. 재개할 때는 새 드라이버의 기본 출력 루트와 환경 변수, HALT 이름을 먼저 바꾸고, 시험이 로드한 모듈의 `ROOT`가 작업 폴더 안인지 시작 전에 단언해야 한다. 금지 폴더의 네 파일은 담당자가 실행 전 기준과 대조해 처리해야 한다. 이 보고서는 원상 복구 승인이나 완료 판정이 아니다.

lead 재실행 명령은 아직 제시할 수 없다. 현재 `test_uncr_v6.py`와 `mutate_uncr_v6.py`는 안전하게 완성되지 않았다. `--stages full`은 실행하지 않았다.

## 03:58 재개 뒤 진행 기록

위 사고 기록은 당시 상태다. lead 재개 지시 뒤 `out_uncr_v5`의 네 파일은 건드리지 않았다. v6 기본 출력 루트와 HALT 이름, 환경 변수 이름을 먼저 고쳤고, 시험의 모듈 적재 직후 네 경로가 `codexA` 아래인지 단언하도록 했다. 출력 루트만 읽는 `preflight_paths.py`는 종료 코드 0이었다.

현재 측정: 최종 합성 시험 `test-synthetic-final.log`에서 기존 50개와 추가 22개, 합계 PASS 72 · FAIL 0 · 종료 코드 0. 처음의 `test-synthetic-1.log`는 D05b 1건 실패 뒤 호출 시점 보정을 했고, 출력 이름을 고치기 전 `test-name-red.log`는 P03 1건 실패했다. 둘 다 과정에 남긴다. 실제 `out_uncr`는 `--no_write`로 재검해 valid 23 · diag 21 · diag cell 7, hold 0 · invalid 0, 종료 코드 0. `OPENBLAS_CORETYPE=Nehalem`은 `[post-env] 다른 칸: openblas_kernel, OPENBLAS_CORETYPE` 한 줄과 종료 코드 3이었다. 실제 OLD_ROOT 예외 시험 `real-old-readonly.log`는 쓰기 함수 호출을 막은 상태에서 원본 418개 파일의 목록·크기·수정 시각 불변과 valid 23을 확인했다.

새 코드 다섯 파일에 대한 `rg` 전수 검색에서 `out_uncr_v5` · `UNCR_V5_ROOT` · `HALT_v5` · `driver_v5` · `manifest_v5` · `post_v5` 참조는 0줄이다. v6 드라이버의 `out_uncr_reval/20261013-201422/revalidate.json`은 과거 승인 보고서의 읽기 전용 참조다.

최종 manifest는 `manifest-run/manifest_v6.json`, `code_manifest_sha256=91d35be9c6a7f65bba573d414b76aa359f58567924bb4bbf501e7c04c83c8e52`, `registered_ok=true`, 새 실행 계획 75개다. 등록 목록에 v6 드라이버·v3 재검사기·v6 시험·v6 변이·`frozen_exec.py`가 포함됐다. 실제 manifest를 읽은 `frozen_exec.py` 정상 대조군은 자식 종료 코드 7을 그대로 전달했다. `full`과 GPU·Isaac은 실행하지 않았고 승인 JSON은 만들지 않았다.

기존 변이 38개와 새 변이 6개의 1차 실행은 44/44 검출했다 (`mutate-1.log`). 이후 출력 이름 수정까지 반영한 최종 코드로 다시 실행했고 44/44 검출했다 (`mutate-final.log`).

## 최종 결론과 파일 SHA256

**A1~A5의 코드 작성과 지정 CPU 시험은 완료했다. ASTRA 독립 검증과 실제 GPU·Isaac 실행은 미착수다.** `--stages full`은 실행하지 않았다. 승인 JSON을 만들지 않았다. 처음의 금지 폴더 사고는 위에 남겼고, 재개 이후 `out_uncr_v5`에는 쓰지 않았다. 보호 폴더 전체는 병행 변경 11건이 있어 전역 불변이라고 주장할 수 없다.

| 파일 | 최종 SHA256 |
|---|---|
| `_eval/unseen_driver_cmdr_v6.py` | `c0114134210475a88c12f61299790681db8d6cc750bbfbe4eddf79ea7bdd8b85` |
| `_eval/uncr_revalidate_v3.py` | `3bd8ae4dc64535277bb9ce1d522575b09fe2f32c191304ab733406aebad93701` |
| `_eval/test_uncr_v6.py` | `a87d84a4e195266e0e88390bdef5bca356a1bf473b9a2bb6a8742447c1a18433` |
| `_eval/mutate_uncr_v6.py` | `e9cf763965f470299e328a61d22d0bc8df40e42d7b468ddc272fa726c53e6cf5` |
| `_eval/frozen_exec.py` | `df111075449485c388bbe51087f6a3ff1614a9398a7b91912ba288067ea9403a` |

읽기 전용 원본 네 파일의 종료 SHA256은 시작과 같다: v5 드라이버 `df0cf1e0a1df...`, v2 재검사기 `089574adfa10...`, v5 시험 `983d7b434634...`, v5 변이 `ff1ef3fdac09...`. 원본 사본은 위 다섯 새 파일 중 초기 v6·v3로 복사했으나 지금은 수정한 판이다. 별도 보관 사본은 만들지 않았다.

새 manifest는 `codexA/manifest-run/manifest_v6.json`, 파일 SHA256 `5c46f20fd2c67ffb56fc5d1b8d2541bed321b933ba4150afdff42b46303e5636`, `code_manifest_sha256=91d35be9c6a7f65bba573d414b76aa359f58567924bb4bbf501e7c04c83c8e52`다. 등록 일치 `true`, 새 실행 계획 75개이며 위 다섯 코드 파일이 등록 목록에 있다. 옛 `ac09...`를 재사용하지 않았다.

## 최종 시험 분모와 과정

| 시험 단위 | 측정 결과 | 로그 |
|---|---|---|
| 합성 시험 스크립트 1회, 내부 `check` 72개 | PASS 72 · FAIL 0 · 종료 0. 기존 50개와 추가 22개 | `test-synthetic-final.log` |
| 변이 스크립트 1회, 변이 44개 | 기존 38개와 A1~A3 관련 추가 6개 모두 해당 시험을 실패시켜 검출 · 종료 0 | `mutate-final.log` |
| 실제 원본 `out_uncr` 읽기 전용 재검 1회 | 실행 23 valid · 0 hold · 0 invalid, 진단 실행 21 valid, 진단 칸 7 valid, 묶음 해시 `e55975172405901a0178a8e2bd3541ce7e13b118d0a9ab723fb6028d69ef2b58`, 종료 0 | `reval-real-final.log` |
| `OPENBLAS_CORETYPE=Nehalem` 하위 프로세스 1회 | `[post-env] 다른 칸: openblas_kernel, OPENBLAS_CORETYPE` 한 줄 · 종료 3. hold 15를 계산하지 않음 | `reval-nehalem-final.log` |
| 실제 `OLD_ROOT` 읽기 전용 예외 시험 1회 | 쓰기 함수 차단, 원본 418개 파일 목록·크기·시각 불변, valid 23 · 종료 0 | `real-old-readonly.log` |
| 실제 v6 manifest를 쓴 `frozen_exec` 대조군 1회 | 등록 파일 일치 후 가짜 자식 실행, 자식 종료 코드 7 전달 | `frozen-manifest-control.log` |
| v6 manifest 단계 1회 | 등록 일치 · 계획 75개 · 종료 0 | `manifest-final.log` |

합성 시험의 `W02`, `W03`, `G05b`에 있는 `hold`는 의도한 반례의 판정이며 통과로 세지 않았다. 실제 재검의 hold는 0이다. 합성 로그에 SKIP·WARN 상태는 없다. 최종 변이 파일은 작업 폴더에서 0개 남았고, 시험 자료와 재계산 임시 자료는 `codexA`에 남겼다.

합성 실행 D03의 `driver_stamp.json`도 다시 읽어 `environment.python_version=3.11.15 ...`, `environment.numpy_version=1.26.0`, `environment.openblas_kernel=Cooperlake`, `environment.q_post_sha256=f90aaa97a50c...`가 기록된 것을 확인했다. 최종 manifest의 `environment`도 NumPy 1.26.0과 Cooperlake를 기록했다.

실패한 과정도 남긴다. 첫 시험 `test-initial.log`는 PASS 20 · FAIL F03 1 뒤 D02에서 예외로 중단됐고 금지 폴더 사고를 일으켰다. 재개 뒤 `test-synthetic-1.log`는 D05b 1건 실패했다. 실행 직전 검사가 하나 늘며 해시 변경 주입 시점이 앞당겨져 주입 호출 수를 2에서 3으로 바로잡았다. `test-name-red.log`는 의도한 P03 1건 실패로 `revalidate_v5_*` 이름을 확인하고 `revalidate_v6_*`로 고쳤다. 이 실패들을 최종 PASS에 섞지 않았다. 변이 1차와 최종 재실행은 모두 44/44였다.

## A1~A5와 남은 확인

| 항목 | ASTRA 반례를 막는 코드와 시험 | 남은 확인 |
|---|---|---|
| A1 | `run_one()`이 GPU 대기와 시도 폴더 보존 뒤 STOP·마감·해시를 다시 보고 자식을 호출한다. D11 대조군은 자식 1회 `ok`, 대기 중 해시 변경은 자식 0회 `frozen`. 새 검사를 끈 변이가 D11에서 실패했다. | 실제 GPU 대기와 파일 시스템 경합은 미실행 |
| A2 | slot의 첫 자식이 `frozen_exec.py`이고, 등록 manifest의 코드·입력을 잠금 획득 뒤 재해시한다. 변경이면 자식 0회 · 종료 92, 일치하면 자식 종료 코드를 전달한다. v6은 92를 보호 오류로 HALT하며 재시도하지 않는다. 92는 기존 slot·isolate·guard·v5 코드 검색에서 발견되지 않았다. | 실제 slot 잠금 경계와 Isaac 실행은 ASTRA 재확인 대상 |
| A3 | 재검사기와 full·post 기동 전 환경 지문을 비교해 다른 경우 `[post-env]`와 종료 3으로 멈춘다. 정상 원본 valid 23, Nehalem 종료 3, 비교 필드 13개 각각 변조 거절을 시험했다. stamp·manifest·보고서에 지문을 기록한다. | 환경 차이의 물리·수치 원인은 미확인. 다른 환경 지원도 미확인 |
| A4 | v6 다섯 파일과 기존 코드·입력 해시로 새 manifest를 만들었다. 등록 일치와 실제 `frozen_exec` 대조군을 확인했다. | ASTRA 승인 JSON 미작성, full 관문 미실행 |
| A5 | 50개 기존 검사와 22개 추가 검사, 변이 38개와 추가 6개를 분리해 세고 모두 통과·검출했다. | GPU·Isaac·영상은 이 CPU 시험의 범위 밖 |

## 설계 판단과 실행 명령

자기 파일의 최종 SHA256을 자기 소스 상수에 넣을 수 없으므로 v6 새 코드 다섯 파일은 모듈 적재 때 해시를 등록한다. full의 승인 파일은 이 해시를 포함한 manifest SHA256에 결합되며, `frozen_exec`가 잠금 뒤 다시 읽는다. 이 동적 등록은 ASTRA의 독립 승인과 같지 않다. 환경 기대값의 Python·NumPy·BLAS 버전과 판정 코드 해시는 `x01env/py311_np126/result.json`에서, 커널·CPU·세 환경 변수의 현재값은 같은 해석기 로컬 조회에서 고정했다. CPU 기대값의 이전 검증 이력은 미확인이다. 재검사 임시 파일은 삭제 금지에 맞춰 `UNCR_V6_WORK` 아래 남긴다.

아래 명령은 PowerShell 기준이다. 시험의 루트 검사는 모듈 적재 직후 실행되고 임시 쓰기는 `codexA` 안으로 제한된다.

```powershell
$env:CUDA_VISIBLE_DEVICES='-1'; $env:UNCR_TEST_SKIP_REAL='1'; $env:PYTHONDONTWRITEBYTECODE='1'
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe' -B 'C:/isaac/ext/go2_rl_robotlab/_eval/test_uncr_v6.py'
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe' -B 'C:/isaac/ext/go2_rl_robotlab/_eval/mutate_uncr_v6.py'
```

실제 원본 재검은 `UNCR_V6_WORK=C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexA/recompute-real-final`로 둔 뒤 다음 명령으로 수행했다. 출력 보고서를 원본 경로에 쓰지 않았다.

```powershell
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe' -B 'C:/isaac/ext/go2_rl_robotlab/_eval/uncr_revalidate_v3.py' --root 'C:/isaac/ext/go2_rl_robotlab/_eval/out_uncr' --no_write
```

manifest는 `UNCR_V6_ROOT=C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexA/manifest-run`, `UNCR_V6_OLD_ROOT=C:/isaac/ext/go2_rl_robotlab/_eval/out_uncr`, `UNCR_V6_SLOT=C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexA/manifest-slot`, `UNCR_V6_REVAL_ROOT=C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexA/manifest-reval`, `CUDA_VISIBLE_DEVICES=-1`을 준 뒤 다음 명령으로 만들었다.

```powershell
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe' -B 'C:/isaac/ext/go2_rl_robotlab/_eval/unseen_driver_cmdr_v6.py' --stages manifest
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe' -B 'C:/isaac/ext/go2_rl_robotlab/_eval/frozen_exec.py' --manifest 'C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexA/manifest-run/manifest_v6.json' --expected-sha '91d35be9c6a7f65bba573d414b76aa359f58567924bb4bbf501e7c04c83c8e52' -- 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe' -B 'C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexA/exit7.py'
```

## 보호 폴더 직접 목록 대조

재개 뒤 04:06에 `_eval`의 기존 `out*` · `slot` · `branch` · `ce12` · `s2` · `handover*` 14개 루트, 파일 76,228개의 경로·크기·수정 시각을 `protected-before.json`에 남겼다. 종료 시 `protected-after.json`은 파일 76,229개다. `protected-diff.json` 대조 결과 추가 1개, 제거 0개, 수정 시각 또는 크기 차이 10개였다. 추가는 학습 출력 `out_branch/cmdr_s1043_on_u4000/model_23000.pt`, 변경 10개는 같은 실행의 로그·이벤트 2개와 `ce12/`의 8개 코드·문서 파일이다. 이 11개는 전역 불변 조건의 예외이며 어느 병행 세션이 썼는지는 이 작업자가 측정하지 않았다. 따라서 **보호 폴더 전체가 변경 없었다고 말할 수 없다.**

반면 이번 재개 범위에서 `out_uncr_v5`·`out_uncr`·`slot`·`s2`·`handover*`의 목록 차이는 0개였다. 학습 스크립트 `branch/night_20261013_cmdr1043_v3.sh`는 시작과 종료 목록에서 크기 4,237바이트와 수정 시각 `1791884989154073200`이 같고 종료 SHA256은 `c53dd90cfb1eaa7102168d6424a2e4364bedad5ff95a89b311877433bd57df9e`다. `out_uncr_v5/HALT_v5.json`도 두 목록에서 같은 크기·수정 시각이었다. 이 목록 대조는 모든 파일의 바이트를 재해시한 검사가 아니다. 본 작업자가 쓴 경로는 위 다섯 새 코드 파일과 `codexA` 작업 폴더뿐이며, 금지 폴더의 11개 병행 차이를 지우거나 옮기지 않았다. 이전 사고 네 파일의 처리는 lead 몫으로 남겼다.
