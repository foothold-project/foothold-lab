> 분류: A/정책학습 · ASTRA 의뢰 17c · 밤 실행 도구 재검사 (17b 반영분 · 실제 Isaac 확인 포함)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 18:58
> 근거: VERIFY-astra-17b.md (판정 「고쳐서 기동」) · night-tools-20261013/ · night-tools-20261013/smoke-20261013/
> 요지: 17b 가 재현한 결함 넷을 고친 도구가 반례를 실제로 막는지, 그리고 이미 띄운 두 실행 (GPU 0 학습 · GPU 1 평가) 을 계속 둬도 되는지 판정해 달라
> 상태: 의뢰

# ASTRA 17c · 밤 실행 도구 재검사와 기동 유지 판정

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. lead 가 시험을 통과시켰다고 해서 맞다고 가정하지 마십시오. 특히 이번에는 lead 의 CPU 시험이 통과했는데도 실제 Isaac 에서 실패한 경우가 한 번 있었습니다 (아래 2 절).

## 1. 이미 일어난 일 (먼저 알립니다)

17b 의 판정이 「고쳐서 기동」 이었으므로, lead 는 고친 뒤 실제 gate 확인을 통과시키고 아래 두 실행을 띄웠습니다. 17c 가 「멈춰라」 라고 하면 STOP 파일로 다음 실행을 막고, 필요하면 lead 가 띄운 프로세스를 끝냅니다.

| GPU | 무엇 | 시작 | 출력 | 멈춤 |
|---|---|---|---|---|
| 0 | `branch/night_20261013_cmdr1043_v3.sh` (CMD-R off · on 학습 · 시드 1043 · 8192 env · 4000 update · 부모 E1 20000) | 18:56:58 | `_eval/out_branch/` | `_eval/out_branch/STOP_1043` |
| 1 | `unseen_driver_cmdr.py --stages diag,post` (부모 · off · on 1042 의 diag 7 칸) | 18:57:35 | `_eval/out_uncr/` | `_eval/out_uncr/STOP` |

두 실행 모두 `isaac_slot.py` v2 → `gpu_guard.py` → `usd_isolate_run.py` v2 → Isaac 스크립트 순서로 떴습니다. 띄울 때의 해시는 `smoke-20261013/launch_1043_sha256.txt` 에 있습니다.

## 2. 실제 Isaac 확인에서 나온 결함과 고친 것

| 회 | 시각 | 결과 | 근거 파일 |
|---|---|---|---|
| gate 1 | 18:51 | branch_run 은 정상 끝 (3 update · done 줄 · guard 0) 이었지만 **USD 가 공용 `/tmp/IsaacLab/usd_20261013_185115_9514` 로 갔다.** `assigned.jsonl` 없음. isaac_slot 이 루트 밖이라 **94** 로 막음 | `smoke_gate_s1043_on.slot.json` · `.guard.json` |
| gate 2 | 18:55 | 고친 `usd_isolate_run.py` v2 로 같은 명령. USD 가 `out_smoke/branch/_usd/<attempt>/IsaacLab/usd_20261013_185542_9514` 에 생김. slot 0 · guard 0 · done 줄 · 30 초. `patched_by: loader` | `smoke_gate2_s1043_on.slot.json` · `smoke_gate2.isolate_state.json` · `smoke_gate2.assigned.jsonl` |

- **원인 (추정):** v1 은 `sys.meta_path` 맨 앞에 finder 를 넣었는데, Kit 안에서는 그 finder 가 대상 모듈에 대해 불리지 않았습니다. gate 2 의 `isolate_state.json` 에 남은 meta_path 를 보면 lead 의 finder 앞에 다른 finder 가 하나 있습니다. 어느 것이 대상 모듈을 찾았는지는 미확인입니다.
- **v1 CPU 시험이 못 잡은 까닭:** 가짜 패키지를 보통 경로로 import 해서, 앞에 끼어드는 finder 가 없었습니다.
- **v2:** 세 겹으로 감쌉니다.
  1. loader: importlib 의 `_LoaderBasics.exec_module` 을 class 수준에서 감싸, 어느 finder 가 찾았든 대상 모듈 본문이 끝나는 순간 감쌉니다 (주 경로 · 실제 Isaac 에서 이 길로 걸림).
  2. finder: v1 그대로.
  3. audit hook: 위 둘이 못 한 경우, 대상 모듈이 올라온 뒤 처음 오는 감사 사건 때 감쌉니다. 「import 직후 아무 사건 없이 바로 변환」 하면 늦습니다 (U7 초안에서 실제로 늦었음). 그때는 isaac_slot 94 가 막습니다.
- **새 시험:** `test_usd_isolate.py` 9 칸 PASS. U7 (앞에 끼어드는 finder) · U8 (로그 줄) · U9 (표준이 아닌 loader) 를 v1 에 걸면 셋 다 FAIL 합니다.
- **남은 것:** `[USD-ISOLATE] patched via loader` 줄이 gate 2 로그에는 없습니다 (첫 줄 `root` 만 있음). Kit 이 뜬 뒤 stdout 이 다른 데로 가는 것으로 추정합니다. 그래서 판정은 `isolate_state.json` 과 isaac_slot 의 폴더 대조로 합니다.

## 3. 검사할 코드 (사본과 해시: `night-tools-20261013/` · `SHA256SUMS.txt`)

실행본은 `C:/isaac/ext/go2_rl_robotlab/_eval/` 아래 같은 이름입니다 (`branch_run.py` · `validate_branch.py` · `night_*.sh` · `test_night*` · `test_validate*` · `mutate_validate*` 는 `_eval/branch/`). 사본과 해시가 같은지 먼저 보아 주십시오.

| 파일 | 17b 대비 바뀐 것 | lead 가 돌린 시험 |
|---|---|---|
| `usd_isolate_run.py` v2 | 2 절 | `test_usd_isolate.py` 9/9 |
| `isaac_slot.py` v2 | 17b 이후 안 바뀜 (86ca4171 그대로) | `test_isaac_slot.py` 15/15 · 변이 11 ALL CAUGHT (86ca4171 때) |
| `validate_branch.py` v2 | 코드는 86ca4171 그대로. 시험만 보강: 변이 18 개 중 넷 (B4b · B6e · B11 · B12) 을 처음엔 놓침. 다른 검사가 대신 걸러 줬기 때문이라, 사유 문자열까지 보는 시험 V5d · V7f · V12 · V13 으로 바꿈 | `test_validate_branch.py` 22/22 (1042 실제 체크포인트) · `mutate_validate_branch.py` 18 ALL CAUGHT |
| `night_20261013_cmdr1043_v3.sh` | 출력 루트를 `../out/branch` 에서 `../out_branch` 로 옮기고 `BRANCH_OUT` 을 export (17 §4 「기존 `_eval/out` 에 쓰지 않는다」) | `test_night_1043_v3.py` 8/8 (N8 새로 · export 를 지운 판에서 N8 FAIL 확인) |
| `branch_run.py` | 출력 줄 하나: `BRANCH_OUT` 이 있으면 그 아래, 없으면 예전 `../out/branch` | gate 2 실제 실행 |
| `unseen_driver_cmdr.py` v3 | 86ca4171 그대로 | `test_unseen_driver_cmdr.py` 9/9 |

## 4. 물음

1. 17b 의 반례 넷 (거짓 완료 · 늦은 USD 경로 · 체크포인트 내용 미검증 · 평가 짝과 post 상태) 이 지금 코드에서 실제로 막히나. 직접 사본에서 반례를 다시 걸어 보아 주십시오.
2. `usd_isolate_run.py` v2 의 loader 감싸기가 Isaac Lab 의 모든 변환 경로 (URDF · MJCF · mesh 변환기, 지형 생성) 에서 첫 변환보다 먼저 걸린다고 볼 근거가 충분한가. `_LoaderBasics` 를 감싸는 것이 학습 · 평가 결과 (난수 소비 · import 순서 · 성능) 를 바꿀 가능성은 없나. 놓친 경로가 있으면 적어 주십시오.
3. 지금 돌고 있는 두 실행을 계속 둬도 되나. 멈춰야 한다면 무엇 때문인가. 계속 둔다면 아침 보고에서 이 두 실행의 결과로 쓸 수 있는 문장의 범위와 붙여야 할 조건은 무엇인가.
4. `../out_branch` 로 옮긴 것이 17 §4 와 맞나. 1042 결과 (`_eval/out/branch`) 를 읽기만 하는 unseen 진단과 섞이지 않나.
5. 위 넷 말고 lead 가 놓친 것.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17c.md` 한 파일. 첫 줄은 한 문장 판정 (계속 · 고쳐서 계속 · 멈춤).
- 표기: 확인됨 · 추정 · 미확인.

## 지킬 것

- 코드 · 파일을 고치지 말고, GPU · Isaac 실행을 하지 마십시오. 돌고 있는 두 실행의 프로세스 · 출력 폴더 · STOP 파일을 건드리지 마십시오 (읽기는 됩니다).
- CPU 로 시험 파일을 돌려 보는 것은 됩니다. 임시 폴더만 쓰고 끝나면 지워 주십시오.
- `_eval/out` · 동결 폴더 · `_eval/out/branch` 의 기존 결과는 읽기만 합니다. 커밋 · push 를 하지 마십시오. em dash 를 쓰지 마십시오.
