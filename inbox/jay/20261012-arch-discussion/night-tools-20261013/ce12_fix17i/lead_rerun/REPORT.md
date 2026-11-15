> 분류: A/평가 · CE12 17i Codex Worker 고침 보고
> 작성: Codex Worker · 2026-10-14 04:36
> 근거: TASK-codex-worker-17i-fix.md · TASK-codex-worker-17g-fix.md 1 절 · VERIFY-astra-17i.md · 아래 CPU 실행 로그와 SHA256 대조
> 요지: 출처 승인, 묶음, 형식, 기동 전 대조, 경로 해석을 고치고 격리 사본에서 정상·반례·변이를 시험했다
> 상태: 코드와 CPU 시험 완료 · ASTRA 독립 검증 대기 · GPU 실행 없음

# CE12 17i 고침 보고

## 결과와 한계

C1~C6을 `_eval/ce12/`에 반영했다. 새 시험은 C1~C5의 정상 대조군과 반례를 포함한다. 최종 CPU 실행 결과는 adapter 시험 함수 23/23 PASS, 실행기·승인기 시험 함수 139/139 PASS, 기존 adapter 변이 24/24 CAUGHT, 기존 실행기·승인기 변이 65/65 CAUGHT, 이번 검사 변이 11/11 CAUGHT다. `CAUGHT`는 변이 사본의 지정 시험이 기대대로 실패했다는 뜻이다. 합성 시험 통과와 실제 기록 통합 시험을 같은 근거로 합치지 않는다. ASTRA의 독립 검증은 아직 받지 않았다.

GPU·Isaac·Kit·학습·실제 평가는 실행하지 않았다. 실제 `run_dump.py`는 `--dry_run` 없는 운영 경로로 실행하지 않았다. 읽기 전용 `nvidia-smi` 한 번으로 실제 명령의 네 열 형식만 확인했다. C8 선택 과제인 r2 승인 재실행은 하지 않았으므로 수정 검증기로 r2 승인 판정을 재확인한 상태가 아니다.

## 시작 해시와 격리

작업 전 CE12 12개 파일은 `inbox/jay/20261012-arch-discussion/night-tools-20261013/ce12/SHA256SUMS.txt`와 12/12 일치했다. 첫 코드로 `codexC/isolation.py`를 만들어 시험의 입출력 경로가 작업 폴더 안에 있는지 검사했다. 그 뒤 `ce12/v_astra17i/`에 원본 12개를 통째로 복사했고, 복사 직후 원본과 12/12 해시가 같았으며 끝난 뒤 지정 SHA256SUMS와도 12/12 같았다.

첫 시험 실행 전 출력한 경로 값은 `codexC/test_run_dump_release.log`의 첫 줄 `ISOLATION_PATHS`에 남아 있다. 해당 실행의 쓰기 경로는 다음과 같다. 접두는 모두 `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexC/ce12_run_1_0o3gpr/`이다.

| 변수 | 접두 아래 경로 |
|---|---|
| 출력 | `eval/out_ce12/native` |
| attempt | `eval/out_ce12/native/_attempts` |
| 구형 registry | `eval/slot/isaac_usd_registry.json` |
| lock | `eval/slot/isaac_convert.lock` |
| slot 기록 | `eval/out_ce12/native/sample.slot.json` |
| STOP | `eval/out_ce12/STOP` |
| compare 보고서 | `eval/out_ce12/native/sample/cmp.json` |

모든 시험 진입점은 작업 폴더와 시험 경로를 먼저 단언한다. `test_run_dump.py`는 실제 사용한 동적 경로도 쓰기 전에 출력한다. CE12 코드와 slot 파일은 `codexC/eval/` 아래에 복사해 시험했다. 실제 CTS 두 기록과 attempt·연결 파일은 작업 폴더로 복사해 읽었다. 끝에 사본 37개 파일과 `_eval/out_ce12/native/` 원본의 SHA256을 다시 비교해 불일치 0개였다. 실제 기록 경로가 옮겨져 달라지는 `VA-real`의 slot 명령·meta outdir 두 칸은 시험 메모리에서만 사본 위치로 맞췄다. 원자료 사본의 바이트는 바꾸지 않았다. T23과 VA-real은 사본이 없으면 실패하며 조용히 skip하지 않는다.

## 수정 내용

| 항목 | 반영과 손으로 고정한 기대값 |
|---|---|
| C1 | 필수 실행 파일 7개의 시작·종료 기록에 절대 경로와 64자 16진 SHA256이 모두 있어야 한다. 시작·종료 경로와 해시를 대조한다. 전체 CLI 시험에서 정상·대문자 16진은 APPROVED 2개, 종료 기록 부재·빈 객체·한 파일 누락·형식 오류·경로 누락·경로 변경·시작 기록 부재는 REJECTED 7개, 승인 대상 코드 파일을 읽을 수 없는 경우는 PENDING 1개다. |
| C2 | 묶음의 중복 basename·16진이 아닌 해시·빈 이름을 거절한다. 정상 1개와 반례 3개를 시험했다. 승인 stamp의 files 목록에 묶음 파일 자체를 넣었다. 묶음이 바뀌면 `--check_approval` 종료 1이다. |
| C3 | 차원 `[3, "10"]`은 30, 빈 값·0·음수·bool·소수·숫자가 아닌 문자열·잘못된 형은 invalid다. names와 dims 길이 차와 잘못된 layout 형식도 invalid다. `VA-format-synthetic`을 별도 시험으로 두고 T23·VA-real은 실제 기록 통합 시험으로 구분했다. |
| C4 | 구형 registry를 읽기만 해 기존 `--scan_dirs` 밖의 존재하는 로그 부모를 자동 추가하고, 없는 과거 로그는 별도 목록에 둔다. registry를 못 읽거나 GPU 조회 실패·대상 없음·여유 부족이면 slot 자식 전 종료 86이다. `run.json.preflight`에 시각·scan 범위·추가·누락 로그·GPU 인덱스·UUID·총량·여유 MiB를 기록한다. dry_run도 같은 조회 결과를 출력한다. 가짜 registry와 nvidia-smi에서 보류 경우 slot 기록 0개, 정상 경우 1개를 확인했다. |
| C5 | 상대 NPZ·meta·compare 보고서·묶음 경로를 활성 `_eval` 루트의 절대 경로로 해석한다. 작업 폴더 루트와 `_eval` 두 cwd에서 같은 입력의 compare 통과와 승인 CLI 통과를 확인했다. |
| C6 | README에 reset 뒤 관측 이력 30~39와 action 30~59를 별도 열로 적고, 2 환경 x 30 env-step을 명시했다. 자연 종료 reset 0, 경계 clip·height miss·1e-4 근거·기동 전 장치 확인의 과거 공백을 미확인으로 적었다. |

종료 코드 86은 `rg`로 기존 CE12·slot v3·isolate v3·guard의 83~86 사용처가 없음을 확인해 골랐다. 기존 87·88·89~91·94~99와도 다르다. 운영 구형 registry와 `slot/`, `branch/`, 기존 `out*`는 읽기만 했다.

## 실패도 포함한 시험 기록

| 순서 | 관측 |
|---|---|
| 수정 전 | 격리한 원판 사본의 `VA-end-required` 0/1. 종료 출처 키를 없앤 CLI가 종료 0 `APPROVED`를 냈다. |
| 첫 새 시험 | 5/6 PASS. `RT-preflight`의 시험 코드가 Windows 기본 cp949로 UTF-8 run.json을 읽어 `UnicodeDecodeError`가 났다. 시험 읽기를 UTF-8로 고쳐 단독 1/1 PASS를 확인했다. |
| 첫 전체 시험 | 136/138 PASS. `RT7`은 새 읽기 전용 registry fixture를 기존 기대값에 반영하지 못했고, `VA-real`은 사본 이동으로 달라진 절대 경로를 고려하지 못했다. 시험 기대값과 메모리 경로 재배치를 고쳐 139/139 PASS를 확인했다. |
| 기존 adapter 변이 첫 회 | C04의 오래된 코드 문자열을 찾지 못해 중간에 중단됐다. 새 `_dim` 호출 위치로 변이 대상을 바꿔 24/24 CAUGHT를 확인했다. |
| 새 변이 중간 회 | 경로 형식 검사를 추가한 뒤 C1 변이 한 개가 독립 경로 검사에 걸려 7/8이었다. 종료 기록 필수 검사와 경로 비교를 함께 끄는 사본으로 바꿔 8/8, 최종 추가 3개까지 11/11 CAUGHT를 확인했다. |
| 최종 실행 | `test_adapters_release.log` 23/23 PASS, `test_run_dump_release.log` 139/139 PASS, `mutate_adapters_release.log` 24/24 CAUGHT, `mutate_run_dump_verified.log` 65/65 CAUGHT, `mutate_17i_release.log` 11/11 CAUGHT. 이 다섯 로그에서 각 요약과 종료 코드를 확인했다. |

시험 분모는 시험 함수 23·139, 내부 C1 CLI 변형 10, 기존 변이 24·65, 이번 변이 11로 구분한다. 139는 기존 132개 함수와 추가 7개 함수다. 변이마다 시험 프로세스 한 번 이상을 따로 실행했으며 변이 수를 정상 시험 함수 수에 더하지 않는다. 변이의 기대 종료 코드는 1이고 정상 시험 실행기의 종료 코드는 0이었다.

## 파일과 SHA256

`_eval` 안에서 만든 것은 `ce12/v_astra17i/`의 원본 12개뿐이다. 기존 CE12 파일 중 아래 8개를 고쳤다. 다른 `_eval` 경로에는 파일을 만들지 않았다. `ce12/__pycache__`는 작업 시작 전 시각의 기존 폴더다. 그 밖의 로그·시험 사본·변이 사본·`isolation.py`·`mutate_17i.py`·이 보고서는 `codexC/` 아래에 둔다.

| 파일 | 보관본 SHA256 | 수정본 SHA256 |
|---|---|---|
| `compare_native.py` | `3a890b17fcc46876e68c484d68a5b10fdd32d468e4593762110ad410475eb196` | `c71ad42c7b55f0dde68889ab20a0478722868632348b7352f2b2637bb319c007` |
| `mutate_adapters.py` | `4ed63b4de645d6bd847cd8a63d03b1ec43268aa37c78e5adc05eb2f27fe044e2` | `5b5f39a9b2c7e2e50d611e112fa97b9ca94b78b5b1d6fb1bf7035acfe4d7f7cd` |
| `mutate_run_dump.py` | `d9c442f1eaece7da7d03f45bad529d6f0268e93861e63e6a6dcb391ed4bfe1a4` | `c0a4a5725893be912bfcd76812e1e685cc1cdcbf576de5f3adfa3dbcd49feba4` |
| `README-ce12-step1.md` | `e9feaaa048ebf717ab664a89c8da220eadea7fa8c2cc81a0a5c1929f79b0f990` | `a76c5cd05659b52f9698725abea8c6bc365c6d496342671a79c95d74925cc965` |
| `run_dump.py` | `075a7fd9760d2ccf56656eabb04d4c3e3f33fcc7be91f8cc85a46e094c600b57` | `b9438e984a3df78f9ea7ae364271fe6bd1311af4747d6295d84d3e31d3e08dda` |
| `test_adapters.py` | `65852b18bae87102a872606268a32642fcf88184c7de81f59e3f554c9ffe4516` | `61d7c531a55983758deacc64fd9d1925935f44b0cea06e671e777b96719ac866` |
| `test_run_dump.py` | `3ab9dfb3d4f6f79f021a59fb9b448bbc0cf0f123a2abbf688ed62b537848cc90` | `e5b7cc9f6aba7db3053f968749f345bcaf56633133f3992c00530256343d06c6` |
| `validate_dump.py` | `ed912af7ac8b34b130651a63d59912f9780a8cb97bd7ee6748e8bcaa94aa074c` | `dae3d93d6827903549043a58fdf20ee0ee2e7ad31780ff6e05ef36382421240e` |

## 재실행과 넘길 일

해석기: `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe`. `CUDA_VISIBLE_DEVICES=-1`, `PYTHONDONTWRITEBYTECODE=1`, `CE12_TEST_ROOT=C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexC`를 설정한 뒤 아래 경로를 `-B`와 함께 실행한다. 작업 폴더에 복사한 코드와 fixture를 대상으로 하므로 운영 `out*`에 쓰지 않는다.

- `codexC/eval/ce12/test_adapters.py`
- `codexC/eval/ce12/test_run_dump.py`
- `codexC/eval/ce12/mutate_adapters.py`
- `codexC/eval/ce12/mutate_run_dump.py`
- `codexC/mutate_17i.py`

ASTRA는 C1의 전체 승인 CLI 정상 2·거절 7·보류 1, C2 bundle stamp 변경, C3 invalid 형식, C4 기동 전 보류와 추가 scan 범위, C5 두 cwd를 독립 재확인할 수 있다. 이번 Worker의 CPU 시험은 그 독립 검증을 대신하지 않는다. r2 승인 재확인은 원본 stamp를 건드리지 않는 별도 사본 절차가 준비되면 진행한다.
