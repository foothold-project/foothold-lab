> 분류: A/평가 · 무작위화 장면 판 4 작업 보고
> 작성: Codex Worker · 2026-10-14 02:56
> 근거: TASK-codex-worker-17g-fix.md 1·3·4절 · VERIFY-astra-17g.md 3·5절 · 아래 CPU 원로그와 SHA256
> 요지: RAND 판 3을 보관하고 registry 분리, 밀기 기록 연결, GPU 조회 및 마감 보류를 판 4에 반영했다.
> 상태: CPU 시험 29/29 · 내부 조건 81개 · 변경 관련 변이 9/9 검출 · GPU smoke 및 ASTRA 독립 재검 미확인

# Codex Worker B · RAND 판 4

## 1. 한 줄 결론

B1~B3 코드를 고쳤고 CPU 회귀와 지정 변이를 통과했다. GPU·Isaac smoke, 실제 장치 일치, ASTRA의 독립 재검은 하지 않았다.

## 2. 파일과 SHA256

시작 전에 지정 `night-tools-20261013/rand_scenes/SHA256SUMS.txt`의 8개 해시와 운영 `_eval/rand_scenes/`의 8개 파일 해시가 모두 일치했다. 편집 전에 전체 폴더를 `_eval/rand_scenes/v3_astra17g/`에 복사했다. 보관본 8개는 마지막 재검 때도 지정 사본과 각각 같은 SHA256이었다.

| 파일 | 판 3 보관본 SHA256 | 판 4 현재 SHA256 |
|---|---|---|
| `mutate_rand_scenes.py` | `29828ac80fae9a6d6cf324efd3b8caa4c2b1c27c48856a6ddb72044ef483c231` | `10f43452a985159b68db25e002886389739ece5d135c33356345ab39da6fb227` |
| `q_rand.py` | `b4b66c6cdea38248926b715d6d0ede376e930614c30aa05d0a1e63004e333881` | 같음 |
| `rand_driver.py` | `5549b733a80c50cc0b7ca8d3e254b54de05547195797b8f4c957189f9ad49eb7` | `c97b1801499ea1d15f28f81662828c22d2699c94c063e0bd9e65c014b8b95eaf` |
| `rand_gate.py` | `f4ac4930b07bdacdbb003243a06b50a1146c27e008842b03f36b1533c6bb15b4` | 같음 |
| `rand_lib.py` | `2fcd035565b9f02d692136095c08c9fb6a8a383ca9bc9d0e7dce5e156da1ea1c` | `32d96499d2754360e2550940cbda5a6fe4d4eeb57fe69b2e417cc9c12579e99c` |
| `rand_overlay.py` | `75592dd81eca22317af9ba91c6466e4091097e27bc5947d5225ea1eac452d039` | 같음 |
| `README-rand-scenes.md` | `483910f9da6793e957be6869d87296427c996c29d3524cdfb027e382ca7ce0b7` | `0f0bb7523e8e92cc5a3c98d67b42e8583380e24242ec2a264400661dd7c31955` |
| `test_rand_scenes.py` | `2a352bf1ee8083c26c411aa34d7288906780a6c1c68c468788cd340eea2a8139` | `265a0288ed3b2295020236973324bf4aa613181eea5955a80e6c00a0d6468e87` |

작업 폴더의 새 실행 보조 파일: `run_tests.py` SHA256 `fd29ddb8430789aa2317c82d075270006e76d39ce15d12feafae51f55526ab49`, `run_mutant.py` SHA256 `b3927f37f7efef50a94190e8270d17644f889b2b6ef0f13107c229405b4a7469`. `REPORT.md` 자체의 해시는 자기 참조 문제로 본문에 넣지 않았다. 보관 폴더의 `__pycache__`도 원본과 함께 복사했다.

## 3. 시험과 첫 실패

분모를 분리했다.

| 범위 | 결과 | 종료 코드 · 원로그 |
|---|---|---|
| 판 3 시작 대조 | 시험 함수 27/27 | 0 · `baseline.log` |
| 수정 전 B1·B3 반례 | 시험 함수 0/2 | 1 · `red_b1_b3.log` |
| 수정 전 B2 반례 | 시험 함수 0/1 | 1 · `red_b2.log` |
| 판 4 첫 전체 실행 | 시험 함수 28/29 | 1 · `full_v4_first.log` |
| 판 4 최종 전체 실행 | 시험 함수 29/29 | 0 · `full_v4_verified.log` |
| `test_validate_attempt_mutations` 내부 조건 | 81개, 기존 75개와 추가 6개 | 위 29개 중 1개 함수 내부 · `results.json`의 `validate_mutation_cells=81` |
| 변경 관련 변이 | 9/9 `CAUGHT` | 0 · `mutations_verified.log`, `mutations_20261014-025241.json` |
| README 문체 재검 | 시험 함수 1/1 | 0 · `readme_check.log` |
| 실제 원자료 재검 · GPU smoke | 0회 | 미실행 |

최종 전체 시험 JSON: `out_cpu/_cpu_tests/20261014-025225-p76560/results.json`. 실패 함수는 0개다. 처음에는 `LEGACY_REGISTRY` 부재와 GPU 여유 `None`의 자식 호출이 드러났다. B2는 `request={}`가 검사를 통과해서 실패했다. B1 시험의 첫 녹색 시도는 테스트가 `registry_update()`에 집합을 넘긴 자료형 오류여서 실패했고, 실제 API의 사전형 입력으로 고쳤다. 판 4 첫 전체 실행의 1건 실패는 옛 dry-run 시험이 새 읽기 전용 검색 경로 `out/branch`까지 출력 경로로 오해한 단언이었다. 실제 `--outdir`가 격리 경로인지 확인하도록 고친 뒤 해당 시험과 전체 시험을 다시 실행했다. 실패와 수정 내역은 위 원로그에 남겼다.

전체 시험 로그에 `SKIP`, `HOLD`, `WARN` 줄은 없었다. 계획 범위 밖 밀기와 마찰을 거부하는 `PLAN PROBLEMS`, GPU 미확인에서 의도한 `STOP`은 시험 대조군의 예상 출력이다. 내부 81개 중 비차단 경고 조건을 확인하는 입력도 포함되지만 운영의 보류 판정을 대신하지 않는다. 기존 변이 전체 77개 중 변경 관련 9개만 이번에 실행했다. 나머지 68개는 미재실행이다.

## 4. 항목별 결과와 한계

- **B1:** RAND가 실제 만드는 `slot_guard_cmd()` 인자의 `--registry`는 `isaac_usd_registry_v3.json`을 가리킨다. `isaac_convert.lock`은 기존 경로 그대로다. `--scan_dirs`는 `out/branch`, `out_branch`, `out_uncr`, `out_uncr_v5`, `out_uncr_v6`, `out_ce12/native`, `out_rand`와 구형 registry가 가리키는 로그의 부모를 포함한다. 구형 JSON이 읽히지 않으면 계획 단계에서 거부한다. 임시 registry에서 공유 시 늦은 구형 작성자로 RAND 항목이 사라지는 반례와 분리 시 보존되는 정상 대조군을 실행했다. 실제 운영 registry의 동시 쓰기나 물리 기동은 미확인이다.
- **B2:** `request`의 다섯 필수 성분은 실제 숫자형이고 유한하며 일정과 일치해야 한다. `q_rand.py`의 callback은 `env.step()` 안에서 실행되고 궤적 `snap(k+1)`은 그 step 직후 저장된다. 그래서 사건 `state_j`와 같은 궤적 행의 heading을 비교한다. 수정 전에 각도 허용 오차를 `0.001 rad`로 정했고 차이는 `(a-b+π) mod 2π-π`로 계산한다. 그 방향의 세계 변화량, 사건 전후 속도, 측정 변화량과 CSV/NPZ 밀기 열을 기존 검사까지 연결한다. 정상 대조군과 ±π 경계 두 조건은 통과하고, ASTRA의 다른 heading 및 빈 요청 반례와 NaN·문자열 요청은 거절됐다. callback 시점의 Isaac 물리 상태와 궤적의 실제 일치는 smoke 전까지 미확인이다.
- **B3:** GPU 1 여유 조회 `None`은 보호 종료 코드 99와 `unverified` 사유로 자식 호출 전에 멈췄다. 정상 6,000 MiB 대조군은 가짜 자식 1회와 판 검사를 통과했다. smoke 전용은 deadline 없이 허용하고, 본 실행은 양수인 명시적 epoch deadline이 없으면 계획 단계에서 거부한다. README에 실제 장치 UUID, USD 할당, 최고 사용량, 최소 여유, 소요 시간의 smoke 후 확인 목록을 썼다. deadline은 새 시도 시작만 막으며 진행 중 자식의 종료 시각은 보장하지 않는다. GPU 1 UUID 자동 기록은 선택 사항이므로 구현하지 않았다.
- **B4:** 기존 27개 시험 함수와 추가 2개를 합쳐 29/29다. `test_validate_attempt_mutations`의 내부 조건은 75개에서 81개로 늘었다. B1~B3와 직접 연결된 6개 변이와 영향받은 기존 3개 변이가 모두 시험 실패로 검출됐다. 77개 변이 전체를 재실행한 결과는 아니다.

## 5. 설계 선택과 차이

변이 사본은 금지된 `_eval/_mut_rand_scenes_*`와 `out_rand` 대신 `codexB/mutants/` 및 `codexB/mutation_outputs/`에 만들었다. 작업서의 삭제 금지에 따라 이 사본은 삭제하지 않고 남겼다. 변이 실행기는 절대 경로 해석기에서 코드 사본을 적재하되, slot과 isolate 파일은 운영 원본을 읽기만 하고 가짜 자식만 실행했다. 정상 시험도 `run_tests.py`가 `RL.OUT_RAND`를 작업 폴더로 돌린 뒤 실행했다. 실제 GPU·Isaac 자식은 실행하지 않았다.

## 6. 실행 명령과 재실행

PowerShell에서 사용한 최종 시험 명령:

```powershell
$env:CUDA_VISIBLE_DEVICES='-1'
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe' 'C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexB/run_tests.py'
```

변이 명령:

```powershell
$env:CUDA_VISIBLE_DEVICES='-1'
$env:RAND_MUTATION_WORK_ROOT='C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexB'
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe' 'C:/isaac/ext/go2_rl_robotlab/_eval/rand_scenes/mutate_rand_scenes.py' M22 M42 M65 M73 M74 M75 M76 M77 M78
```

위 명령이 lead의 재실행 명령이다. 이 보고서와 `*.log`, `mutations_*.json`, CPU `results.json`은 모두 `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexB/` 아래다. 두 명령은 `out_rand`에 쓰지 않는다. 실제 `rand_driver.py`는 실행하지 않았다.

## 7. 금지 경로 확인

직접 쓰거나 복사한 경로는 `_eval/rand_scenes/v3_astra17g/`, `_eval/rand_scenes/`의 다섯 파일(`rand_lib.py`, `rand_driver.py`, `test_rand_scenes.py`, `mutate_rand_scenes.py`, `README-rand-scenes.md`)과 `codexB/` 아래 보고서·실행기·시험 출력뿐이다. Python import로 `_eval/rand_scenes/__pycache__/`가 갱신된 흔적은 있다. `_eval/out*`, `_eval/slot/`, `_eval/branch/`, `_eval/ce12/`, `_eval/s2/`, handover 경로의 파일을 쓰거나 옮기지 않았다. 임시 registry와 잠금은 `codexB/` 안의 가짜 시험 자료에만 만들었다. GPU 0 학습 스크립트와 프로세스, 운영 STOP·lock·registry 파일에는 쓰거나 종료하는 명령을 실행하지 않았다. `git pull`, commit, push, checkout도 하지 않았다.
