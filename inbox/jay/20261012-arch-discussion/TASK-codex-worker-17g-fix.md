> 분류: A/평가 · Codex Worker 작업서 · ASTRA 17g 가 요구한 고침 두 건 (A 미경험 v5 · B 무작위화 판 4)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 02:3x
> 근거: VERIFY-astra-17g.md 전문 · VERIFY-astra-17f.md §3 · VERIFY-astra-17h.md §3 · night-tools-20261013/uncr_v5/ · night-tools-20261013/rand_scenes/ · lead 분석 job tmp x01env/
> 요지: ASTRA 가 재현해 보인 결함 (A: GPU 대기 뒤 코드 재검사 공백 · 환경 지문 없음 / B: 구형 registry 공유 · 밀기 방향 연결 · 요청 누락) 을 CPU 시험과 변이 시험으로 고친다. 고친 코드는 ASTRA 가 따로 검증하므로 너는 검증자가 아니라 작성자다
> 상태: 의뢰 (lead 가 Sonnet 5.5 로 내려간 뒤 처음 맡기는 코딩)

# Codex Worker 작업서 · 17g 고침

## 0. 너의 자리

- 너는 **Codex Worker (gpt-6-sol)** 다. 검증 세션 (ASTRA) 이 아니다. **고쳤다고 「검증됐다」 라고 쓰지 마라.** 「시험이 통과했다」 와 「ASTRA 가 확인했다」 는 다르다. ASTRA 는 이 작업서를 모르는 독립 검증자다.
- 이 세션은 **승인 창이 없는 모드 (YOLO)** 다. 실수가 바로 반영되니 아래 「금지」 를 지켜라. 밤새 사람이 없다.
- 일은 두 부분이다. 세션 이름에 A 가 있으면 **A 만**, B 가 있으면 **B 만** 한다. 다른 부분의 파일은 읽기만 한다.
- 모르면 모른다고 쓴다. 추측으로 채우지 않는다. 막히면 멈추고 막힌 곳을 보고서에 쓴다.

## 1. 공통 규칙 (어기면 그 일은 무효)

**금지 (읽기만 허용):**
- `C:/isaac/ext/go2_rl_robotlab/_eval/` 안의 기존 `out*` 폴더 (`out_uncr` · `out_uncr_reval` · `out_uncr_v5` · `out_branch` · `out_ce12` · `out_rand` · `out_smoke` · `out`), `handover_*` · `handover-1635`, `slot/`, `branch/`, `ce12/`, `s2/`. 그 안의 파일을 수정 · 삭제 · 이동 · 새로 쓰기 하지 않는다. (`branch/night_20261013_cmdr1043_v3.sh` 는 지금 GPU 0 에서 돌고 있는 학습 스크립트다. **절대 건드리지 마라.**)
- ASTRA 가 해시로 검증한 파일을 그 자리에서 고치지 않는다 (아래 A 는 새 파일로, B 는 보관 뒤 판 4 로).
- GPU · Isaac · Kit · 학습 · 평가 실행. `nvidia-smi` 조회는 읽기라 허용. `CUDA_VISIBLE_DEVICES=-1` 로 시험한다.
- 프로세스 종료 · `taskkill` · STOP 파일 만들기 · 잠금 · registry 파일 수정.
- 패키지 설치 · 환경 수정 (`pip install` · `conda` 등). `isaac311` · `isaac311-moects` 환경을 건드리지 않는다.
- **삭제.** 변수 경로로 `rm` 하지 마라. 임시 파일은 지우지 말고 작업 폴더에 남겨라 (아래).
- git commit · push · pull · checkout · reset. 저장소 (`foothold-lab`) 안에 파일을 쓰지 않는다. 보고서는 아래 작업 폴더에만 쓴다.
- 키 · 토큰 · 비밀번호를 다루거나 출력하지 않는다.
- em dash (긴 줄표) 를 어디에도 쓰지 않는다. 쉼표 · 마침표 · 가운뎃점을 쓴다.

**작업 폴더 (쓰기 허용):** `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexA/` (A) · `.../codexB/` (B). 새 코드는 아래에 지정한 `_eval` 안의 새 파일 이름에만 쓴다.

**해석기:** 시험은 모두 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe` (절대 경로) 로 돌린다. 기본 PATH 의 python 을 쓰지 마라 (3.13 이라 결과가 다르다). 시험 앞에 `CUDA_VISIBLE_DEVICES=-1`.

**시험을 쓰는 법:**
- 기대값은 **손으로** 적는다. 구현 코드를 복제해 기대값을 계산하지 마라 (ASTRA 가 이미 두 번 이 허점을 짚었다).
- 모든 새 검사에 **답을 아는 정상 대조군** 과 **ASTRA 가 보인 반례** 를 같이 둔다. 반례는 거절돼야 하고 대조군은 통과해야 한다.
- 새 검사마다 **변이 시험** 을 둔다: 그 검사를 끈 사본 (변이) 을 만들어 시험이 실제로 실패하는지 본다. 변이 사본은 시험 뒤 같은 작업 안에서 지우는 코드를 쓰되, 임의 경로를 지우는 명령은 쓰지 마라 (기존 변이 스크립트의 방식을 따른다).
- 처음 돌렸을 때 실패한 것도 보고서에 쓴다 (고치기 전 숫자). 통과만 적지 않는다.
- 시험 개수를 세는 분모를 구분해 적는다 (시험 함수 수 · 내부 변형 수 · 실행 수는 서로 다른 분모다. 하나로 합치지 마라).

**먼저 읽을 것 (끝까지):** `C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20261012-arch-discussion/VERIFY-astra-17g.md` 전문. 줄 번호는 ASTRA 가 지정 사본 (`night-tools-20261013/` 아래) 기준으로 적었다. 같은 바이트의 실제 위치는 `C:/isaac/ext/go2_rl_robotlab/_eval/`.

## 2. A · 미경험 v5 고침 (세션 이름에 A)

**대상 (ASTRA 가 해시로 검증한 판. 고치지 말고 복사해서 새 이름으로):**

| 원본 (읽기만) | sha256 앞 12 자 |
|---|---|
| `_eval/unseen_driver_cmdr_v5.py` | df0cf1e0a1df |
| `_eval/uncr_revalidate_v2.py` | 089574adfa10 |
| `_eval/test_uncr_v5.py` | 983d7b434634 |
| `_eval/mutate_uncr_v5.py` | ff1ef3fdac09 |

먼저 네 파일의 해시가 위와 같은지 확인하고, 다르면 멈추고 보고한다. **새 파일** (같은 `_eval/` 폴더): `unseen_driver_cmdr_v6.py` · `test_uncr_v6.py` · `mutate_uncr_v6.py` · `frozen_exec.py`. 재검사기를 고쳐야 하면 `uncr_revalidate_v3.py` (v2 의 복사 + 변경). 새 출력 루트는 `_eval/out_uncr_v6` (v5 의 `out_uncr_v5` 를 쓰지 않는다). 옛 묶음 `out_uncr` 는 읽기만.

**A1 (ASTRA 2.1 P1) 실행 직전 재검사:** v5 의 `run_one()` 은 `frozen_now()` 뒤에 `gpu_ready()` (최대 600 초 대기) 를 부르고 그 뒤 해시를 다시 안 본다. 고칠 것: GPU 대기 완료와 시도 폴더 보존 처리 뒤, **자식 호출 직전** 에 STOP · 마감 · 코드 · 입력을 다시 검사하고, 바뀌었으면 자식을 부르지 않는다. 시험 (ASTRA 의 반례 그대로): 실제 `run_one()` · `freeze()` · `frozen_now()` 를 쓰고 GPU 함수와 자식 실행만 메모리 안 가짜로 바꾼 뒤, `code_sha()` 반환값이 `gpu_ready()` 안에서 바뀌게 한다. 기대: 자식 호출 **0 회**, 분류 `frozen`. 대조군 (안 바뀜): 자식 호출 1 회 · `cls=ok`.

**A2 (ASTRA 2.1 두 번째 항목) 잠금 대기 뒤 동결:** v3 slot 은 OS 잠금을 얻을 때까지 기다린 뒤 자식을 띄운다. 그 대기 사이에도 코드가 바뀔 수 있다. slot 은 ASTRA 가 해시로 검증했으니 고치지 않는다. 대신 `frozen_exec.py` 를 새로 만들어 **slot 이 띄우는 첫 자식** 으로 둔다: slot 명령의 `--` 뒤가 `python frozen_exec.py --manifest <등록 manifest 파일> -- <기존 guard 명령 ...>` 가 되게 한다. `frozen_exec.py` 는 시작하자마자 (잠금을 얻은 직후) 등록한 코드 · 입력 해시를 지금 파일과 대조하고, 다르면 **종료 코드 92** 로 끝나며 아래 자식을 띄우지 않는다. 같으면 아래 명령으로 넘어간다 (종료 코드 그대로 전달). 92 가 기존 코드 (`isaac_slot_v3.py` · `usd_isolate_run_v3.py` · `gpu_guard.py` · v5 의 분류) 와 겹치지 않는지 `grep` 으로 먼저 확인하고, 겹치면 안 쓰는 번호를 골라 보고서에 적는다. v6 의 실패 분류에서 이 코드는 **보호 오류 (HALT, 재시도 없음, 다음 단계 중단)** 다. `frozen_exec.py` 자체도 등록 코드 목록에 넣는다. 시험: 변경 있음 → 92 이고 아래 자식이 한 번도 실행되지 않음 · 변경 없음 → 아래 자식이 실행되고 종료 코드가 전달됨.

**A3 (ASTRA 4 절) 환경 지문:** 재검 보고 · 기동 기록 (stamp · manifest) 에 아래를 남긴다: `sys.executable` · python 전체 버전 · `numpy.__version__` · `numpy.__file__` · BLAS 이름과 버전 (`numpy.show_config(mode="dicts")`) · OpenBLAS 커널 이름 (numpy 에 들어 있는 libopenblas 의 `openblas_get_corename` 을 ctypes 로. 방법은 `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/x01env/scripts/recompute.py` 를 참고) · 환경 변수 `OPENBLAS_CORETYPE` · `MKL_CBWR` · `MKL_ENABLE_INSTRUCTIONS` · CPU 이름 · 판정 코드 (`q_post.py` · `q_metrics.py`) 해시. 「검증된 환경」 지문은 `x01env/py311_np126/result.json (isaac311-moects 의 결과) 와 x01env/mech_isaac311-moects.json` 의 값에서 가져와 코드 상수로 등록한다 (python 3.11.15 · numpy 1.26.0 · OpenBLAS 0.3.23.dev · 커널 Cooperlake 가 기대값. 원본 파일을 읽고 실제 값을 쓴다). **full 단계와 post 의 재계산 대조 전에** 지금 환경의 지문을 검증된 지문과 비교하고, 다르면 바이트 대조로 들어가지 않고 별도 종료 코드 **3** (지원하지 않는 환경) 과 한 줄 이유 `[post-env] 다른 칸: ...` 로 끝낸다. 바이트 검사를 느슨하게 하지 마라. 이것이 목적이 아니다. 시험: (a) 정상 환경에서는 실제 `out_uncr` 읽기 전용 재검이 **valid 23** (b) 같은 환경에 `OPENBLAS_CORETYPE=Nehalem` 만 주는 하위 프로세스에서는 hold 15 가 아니라 **`[post-env]` 한 줄 + 종료 코드 3** (이전 분석에서 이 설정은 hold 15 를 재현했다) (c) 지문 필드를 하나씩 바꾼 변조 대조군 (필드마다 거절 확인). 재검사기 호출은 반드시 `--no_write` 이거나 쓰기 함수를 부르지 않는 방식으로 (기존 `out_uncr_reval` 에 쓰지 마라). 임시 재생성 폴더는 작업 폴더 안.

**A4 새 manifest:** 등록 코드 목록 (`REGISTERED_CODE` · `REGISTERED_INPUTS`) 을 v6 파일 (새 파일들 포함) 로 갱신해 `python unseen_driver_cmdr_v6.py --stages manifest` 만 돌려 새 manifest 와 `code_manifest_sha256` 을 만든다. 옛 승인 값 `ac09c264...` 을 재사용하거나 새 해시를 예외 처리하지 마라. **`--stages full` 은 절대 돌리지 마라 (Isaac 이 뜬다).** 승인 json 은 쓰지 마라 (ASTRA 몫).

**A5 시험:** `test_uncr_v6.py` 는 v5 시험을 포팅한 것 (기존 50 + 새 검사). `UNCR_TEST_SKIP_REAL=1` 로 돌린 합성 시험과, 실제 `out_uncr` 읽기 전용 시험을 따로 센다. `mutate_uncr_v6.py` 는 v5 변이 38 개를 포팅하고 A1 ~ A3 의 새 검사마다 변이를 더한다 (변이가 시험을 실패시켜야 한다). 변이가 하나라도 안 잡히면 시험을 고쳐라.

**A 보고서:** `codexA/REPORT.md`. 아래 4 절의 형식.

## 3. B · 무작위화 판 4 고침 (세션 이름에 B)

**대상:** `_eval/rand_scenes/` (`rand_driver.py` · `rand_lib.py` · `q_rand.py` · `rand_gate.py` · `rand_overlay.py` · `test_rand_scenes.py` · `mutate_rand_scenes.py` · `README-rand-scenes.md`). ASTRA 가 해시로 검증한 판이다 (`night-tools-20261013/rand_scenes/SHA256SUMS.txt` 와 같아야 한다. 먼저 대조하고 다르면 멈추고 보고). **고치기 전에** 이 폴더 전체를 `_eval/rand_scenes/v3_astra17g/` 로 복사해 두고 해시가 같은지 확인한 뒤 원래 자리에서 판 4 로 고친다. (같은 방식으로 S2 를 고친 선례가 있다.) 새 출력은 기존 `out_rand` 가 아니라 시험 중에는 작업 폴더만 쓴다. `out_rand` 는 읽기만.

**B1 (ASTRA 3.1 P1) 구형 registry 쓰기 금지:** `rand_lib.py` 의 slot v3 호출 (ASTRA 줄 번호 863 ~ 875 부근) 이 `--registry _eval/slot/isaac_usd_registry.json` (구형) 을 넘긴다. 고칠 것: v3 참가자는 `_eval/slot/isaac_usd_registry_v3.json` 만 쓰고, 구형 `isaac_usd_registry.json` 은 **읽기만** 한다. 변환 잠금 (`isaac_convert.lock`) 은 구형과 같은 파일을 쓴다 (나누지 마라). 검색 경로 (`--scan_dirs`) 에 `out/branch` (구형 branch 경로) · `out_branch` · `out_uncr` · `out_uncr_v5` · `out_uncr_v6` · `out_ce12/native` · `out_rand` 와, 구형 registry 가 가리키는 로그들의 부모 폴더를 넣는다. 구형 registry 를 읽다 실패하면 빈 목록으로 조용히 넘어가지 말고 **기동 전 실패** 로 드러낸다. 시험: (a) ASTRA 의 재현 그대로 (구형이 앞서 읽은 상태를 나중에 덮어쓰는 구조에서 공유하면 v3 기록이 사라지고 분리하면 보존) 를 RAND 가 **실제로 만드는 명령 인자** (명령을 만드는 함수를 불러서 `--registry` 가 `_v3.json` 으로 끝나는지 단언) 와 이어서 시험 (b) 구형 registry 읽기 실패 → 기동 전 실패 (c) 검색 경로 목록의 포함 관계. 실제 `_eval/slot/` 파일은 쓰지 말고 임시 사본으로.

**B2 (ASTRA 3.2 P1) 밀기 방향과 요청값:** `validate_attempt()` 계열 (ASTRA 줄 번호 `rand_lib.py` 694 ~ 718) 이 (i) 밀기 사건의 `heading_rad` 를 같은 시점의 궤적 `heading_rad` 와 잇지 않고 (ii) 요청 성분이 없거나 NaN 이어도 `abs(float(req.get(key, NaN)) - expected) > tol` 이 거짓이라 통과시킨다. 고칠 것: 요청의 필수 성분이 존재 · 수치형 · 유한한지 먼저 검사하고 아니면 거절. 사건 방향을 같은 시점의 궤적 방향과 잇는 시간 관계를 정한다 (push callback 이 불린 step 과 궤적 저장 step 의 관계를 코드와 기존 시험의 가짜 기록에서 읽어서 정하고, 정한 방식을 보고서에 쓴다). 각도 비교는 ±π 경계를 고려한다 (차이를 `(a - b + π) mod 2π - π` 꼴로). 허용 오차는 **결과를 보기 전에** 정해서 코드 상수에 쓰고 보고서에 적는다 (넓혀서 통과시키지 마라). 그 방향으로 독립 계산한 세계 변화량과 사건 · 전후 속도 · CSV/NPZ 밀기 열을 함께 검사한다. **시험 (ASTRA 의 반례 둘 + 대조군):** 제출된 `test_validate_attempt_mutations` 의 정상 가짜 실행 폴더를 복사해 실제 `validate_attempt()` 를 영상 전 프레임 검사까지 그대로 부른다. 대조군 (정상) 은 ok True. 반례 1: 궤적 heading 은 0 인데 밀기 사건 heading 을 π/2 로 바꾸고 그 heading 의 세계 변화량 · 전후 속도 · 측정 변화량 · CSV/NPZ 밀기 열을 모두 맞춘다 → 거절돼야 한다. 반례 2: 정상 사건의 `request` 를 빈 객체로 → 거절. 추가: 요청 성분 NaN · 문자열 → 거절 · ±π 경계 (heading π 와 -π 는 같은 방향) 는 통과 · 대조군 heading π 근처 정상 기록은 통과.

**B3 (ASTRA 5 절):** (i) `rand_driver.py` 의 GPU 여유 조회 결과가 `None` 이면 지금은 시작을 막지 않는다 (ASTRA 줄 205 ~ 207). **None 이면 시작 전 보류** (미확인) 로 바꾸고 시험한다. (ii) `--deadline` 이 기본 0 이다. 본 실행 (smoke 가 아닌 것) 에서는 명시적인 마감 (0 보다 큰 epoch 초) 이 없으면 거절하고, README 명령에 `--deadline <epoch>` 를 넣는다. 마감이 「새 시도를 시작하지 않음」 인지 「진행 중도 중단」 인지 코드가 하는 대로 README 에 한 줄로 쓴다. (iii) smoke 가 끝난 뒤 사람이 확인할 것 (NVML GPU 1 · `CUDA_VISIBLE_DEVICES=1` 뒤 논리 CUDA 0 · Kit 렌더 장치가 같은 물리 GPU/UUID 인가 · USD 할당 · 최고 사용량 · 최소 여유 · 소요 시간) 을 README 에 목록으로 쓴다. 코드로 쉬우면 smoke manifest 에 `nvidia-smi` 가 알려 주는 GPU 1 의 UUID 를 읽기만 해서 적는다.

**B4 시험:** 기존 `test_rand_scenes.py` 의 27 개 함수 (`test_validate_attempt_mutations` 안의 내부 변형 75 개 포함) 가 판 4 에서도 통과해야 한다. 새 시험을 더하고, `mutate_rand_scenes.py` 에 B1 ~ B3 의 새 검사마다 변이를 더한다.

**B 보고서:** `codexB/REPORT.md`. 아래 4 절의 형식.

## 4. 보고서 형식 (길이 제한 없음 · 숨기지 말 것)

1. 한 줄 결론 (고친 것 · 못 고친 것).
2. 바뀐 파일 목록과 sha256 (새 파일 · 고친 파일 · 보관한 원본 사본의 해시가 원본과 같은지).
3. 시험: 분모를 구분해 (시험 함수 · 내부 변형 · 변이 · 실제 읽기 전용 자료) 통과 수와 종료 코드. **처음에 실패한 것과 고친 과정.** 통과가 아닌 줄 (SKIP · HOLD · WARN) 도 전부.
4. 실행한 명령 (해석기 절대 경로 포함) 과 원로그 위치 (작업 폴더).
5. 위 2 · 3 절의 각 항목 (A1 ~ A5 또는 B1 ~ B4) 이 **ASTRA 의 반례를 어떻게 막는지 한 줄씩** 과 **막지 못한 것 · 미확인**.
6. 설계와 다르게 한 곳과 이유.
7. lead 가 다시 돌릴 명령 (시험 · 변이 각 한 줄).
8. 작업 끝 확인: 금지 폴더의 파일을 건드리지 않았다는 근거 (네가 쓴 파일 목록).

끝나면 이 창에 보고서 경로와 한 단락 요약을 남긴다. 작업을 마치지 못했으면 어디까지 했고 어디서 막혔는지 쓴다.
