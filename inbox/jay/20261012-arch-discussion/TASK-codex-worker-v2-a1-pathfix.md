> 분류: A/평가 · Codex Worker 작업서 · v2 기록 승인 A1 거절 (서명 경로 표기 불일치) 후보 수정
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 08:5x
> 근거: NIGHT-PLAN-20261014.md 「v2 단회 재시도 결과」 · night-tools-20261013/ce12_mapfix/v2_run_17n/ (콘솔 · 보고서 · signature.json · run.json) · VERIFY-astra-17n.md · TASK-codex-worker-17i-fix.md 0 절 (격리 단언)
> 요지: 실제 GPU 기록은 성공했는데 승인기 A1 이 "서명이 지금 adapter 와 다름 (source, signature_sha256)" 으로 거절했다. 서명 안의 env.yaml 경로가 기록 때는 슬래시와 역슬래시가 섞였고 승인기가 다시 만들 때는 전부 슬래시였다. 이 불일치를 없애는 가장 작은 후보 수정과 시험을 만든다
> 상태: 의뢰

# Codex Worker 작업서 · v2 A1 경로 표기 후보 수정

## 0. 먼저 읽을 것과 자리

- 너는 **Codex Worker (gpt-6-sol)** 이고 검증자가 아니다. **고쳤다고 「검증됐다」 라고 쓰지 마라.** ASTRA 가 따로 검증한다. 결과는 **후보**일 뿐이고 채택은 ASTRA 판정 뒤 lead 가 한다.
- 규칙은 `TASK-codex-worker-17g-fix.md` 1 절 「공통 규칙」 과 `TASK-codex-worker-17i-fix.md` 0 · 0.1 절 (격리 단언) 을 그대로 따른다. 이 세션은 YOLO 모드다. 커밋 금지 · 삭제 금지 · `_eval/out*` · `slot` · `branch` · `s2` · `handover*` · `rand_scenes` 에 쓰기 금지 · GPU · Isaac 실행 금지 · 시험은 `CUDA_VISIBLE_DEVICES=-1` · 키 · 토큰 안 다룸 · em dash 금지.
- **`C:/isaac/ext/go2_rl_robotlab/_eval/ce12/` 는 이번에 고치지 않는다 (읽기만).** 이 폴더가 지금 ASTRA 17n 이 본 바이트이고 v2 기록 묶음 `night-tools-20261013/ce12_mapfix/v2_bundle_17n.sha256` 에 묶여 있다. 후보는 전부 새 작업 폴더 `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexB4/` 안의 `ce12_candidate/` (원본 폴더를 통째 복사한 사본) 에서 만든다.
- **격리 단언 (첫 번째 일):** 어떤 쓰기도 하기 전에 시험이 쓰는 출력 · 입력 경로 변수 전부가 `codexB4/` 아래인지 코드로 확인하고 출력한다. 그 사본에서 읽는 실제 자료 (`out_ce12/native/v2_native_17n_mapfix_20261014_085039/` 의 `signature.json` · `meta.json` · `native.npz`, `models/foothold-v2.env.yaml`) 는 `codexB4/fixture_real/` 로 **복사한 뒤** 복사본으로만 쓴다 (원본은 읽기만).
- 해석기: 승인기 · 비교기는 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe` (ASTRA 17n: 기록기는 `isaac311`, 도구는 `isaac311-moects`). 시험 시작에서 `sys.executable` · 불러온 `adapters.py` 의 `__file__` 과 SHA256 을 출력하고, 기대와 다르면 「환경 불일치」 로 끝낸다. 환경 둘에서 모두 도는 시험인지, 한쪽에서만 도는지 보고서에 적는다.

## 1. 확인된 사실 (이미 lead 가 읽기로 확인한 것 · 너도 다시 재라)

- 실제 v2 기록 (08:52) 은 성공했다. 승인기 `validate_dump.py --approve` 가 A1 만 FAIL: `서명이 지금 adapter 와 다름 · 다른 칸 ['signature_sha256', 'source']`.
- 기록된 `signature.json` 의 `source."foothold-v2.env.yaml".path` 는 `C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab\models\foothold-v2.env.yaml` (섞임). `validate_dump._sig_now` 가 `V2Adapter.from_env_yaml(..., env_yaml=기본값 V2_ENV_YAML)` 로 다시 만든 서명의 경로는 전부 슬래시. 내용 해시 `a5ef31d626f8cabe850de37bae0aa26782e14e9db3ba61d678dd1210105323e7` 은 같다. 서명 해시는 경로 문자열을 포함해서 달라진다 (`2f1b0c2b…` 대 `dfc1410f…`).
- 의심 위치: `ce12/dump_native_v2.py:61` `--env_yaml` 기본값 `os.path.join(LAB, "models", "foothold-v2.env.yaml")` (Windows 에서 `LAB` 이 슬래시라 역슬래시가 붙음) · `ce12/adapters.py:747` 의 `source` 기록 · `adapters.py` 의 `V2_ENV_YAML` 상수 · `ce12/validate_dump.py:263~269` `_sig_now`. CTS 경로 (`adapters.py:679~680`) 는 슬래시 상수라 r2 승인에서 문제 없었다.

## 2. 해야 할 일

**D1. 원인 확정.** 위 의심 위치를 실제로 읽어 경로가 어디서 섞이는지 줄 번호와 함께 적는다. 기록기가 기록하는 경로 중 승인기가 다른 방식으로 다시 만드는 값이 더 있는지 (예: `meta.json` 의 `env_yaml` · `lab_files_sha256` · 체크포인트 경로) 를 전수 목록으로 적는다. 목록의 판별식을 같이 적는다 (「signature 또는 meta 에 들어가는 경로 문자열 중 `_sig_now` 또는 승인기가 비교하는 것」).

**D2. 후보 수정 둘을 비교하고 작은 쪽을 구현한다.**
- 후보 A (기록기만): `dump_native_v2.py` 가 기본 `--env_yaml` (필요하면 `--checkpoint` 도) 를 `abspath` 뒤 역슬래시를 슬래시로 통일한 문자열로 만든다. 건드리는 파일은 `dump_native_v2.py` 하나.
- 후보 B (adapter 쪽): `adapters.py` 가 서명의 `source` 에 넣는 경로를 슬래시로 통일한다. (승인기 · 기록기 양쪽에 적용되지만 `adapters.py` 와 `compare_native` · `validate_dump` 의 해시, 그리고 r2 승인 도장이 가리키는 코드 해시가 바뀐다.)
- **각 후보가 이미 있는 r2 승인 (`out_ce12/native/cts_e1_m20000_r2` 의 `approval_stamp.json`) 의 `--check_approval` 재확인에 미치는 영향** 을 격리 사본에서 실제로 재 본다 (도장이 가리키는 코드 파일에 어느 후보가 닿는지 먼저 목록으로). 둘을 나란히 표로 적고 **영향이 작은 쪽을 `ce12_candidate/` 에 구현**한다. 구현하지 않은 후보도 코드 조각으로 보고서에 남긴다.

**D3. 시험 (손으로 적은 기대값 · 정상 대조군과 반례).** 새 시험 파일 `test_v2_signature_path.py` (후보 사본 안):
1. **재현 (수정 전 FAIL):** 실제 기록기 코드의 기본 경로 식을 AST 로 꺼내 (식을 복사해 쓰지 말 것) 실제 `LAB` 값으로 평가하고, 그 경로로 `V2Adapter.from_env_yaml` 서명을 만들어 `validate_dump._sig_now` 와 비교한다. 수정 전에 `source` 와 `signature_sha256` 만 다르다는 것을 확인한다 (D1 의 실제 자료와 같은 칸).
2. **실제 자료 대조:** `fixture_real/signature.json` (08:52 의 실제 기록) 에 대해 수정 전 코드는 불일치, 후보 코드가 만든 서명은 `_sig_now` 와 일치함을 보인다. 실제 기록을 고쳐 쓰지 말 것.
3. **정상 대조군:** 경로가 이미 전부 슬래시인 입력 · 전부 역슬래시인 입력 · 섞인 입력 모두에서 후보가 같은 서명을 만든다 (표기만 다르고 내용 해시가 같으면 같은 서명). 내용 해시가 다른 파일은 **여전히 달라야 한다** (경로 통일이 출처 검사를 약하게 만들지 않음을 반례로).
4. **변이:** (a) 후보 수정을 되돌림 (b) 통일을 `source` 한 칸만 하고 `path` 대신 다른 칸에 적용 (c) 내용 해시를 서명에서 빼는 변이. 정상 소스에서 새 시험이 먼저 통과한 뒤, 각 변이는 **지정한 시험이 실제로 실패할 때만** CAUGHT 로 센다 (import · module 오류, 시험 파일 구문 오류는 CAUGHT 가 아님 · `failed [..] want [..]` 로 기록). 17j 의 규칙.
5. 기존 회귀를 후보 사본의 격리 복사에서 돌려 분모와 함께 적는다: `test_adapters.py` 23 · `test_run_dump.py` 139 · `mutate_adapters.py` 24 · `mutate_run_dump.py` 65 · `mutate_17i.py` 11 · `test_v2_load_device.py` 1 (`isaac311` python). 기대와 다르면 숨기지 말고 그대로 적는다.

**D4. 하지 말 것.** `_eval/ce12/` 를 고치기 · 기록된 `signature.json` · `approval_stamp.json` 을 고쳐 쓰기 · A1 검사를 느슨하게 (경로 검사 자체를 빼거나 경로가 다른 파일을 같다고 보기) · 승인 도장 만들기 · GPU · Isaac · `run_dump.py` 실행.

## 3. 보고서 `codexB4/REPORT.md`

머리 다섯 줄 (분류 · 작성 · 근거 · 요지 · 상태) 뒤에: 격리 단언 출력 · 해석기와 러너 해시 · D1 전수 목록과 판별식 · D2 비교 표 (r2 재확인 결과 포함) · 후보 코드 diff · D3 시험 (예정 대비 실행 · skip · hold · 종료 코드 · 변이 CAUGHT 의 want 일치 확인) · 처음 실패한 것도 (분모에 섞지 말고) · 끝났을 때 `_eval` 안에서 네가 만든 파일 목록 (없어야 정상) · 후보 사본의 `SHA256SUMS.txt` · lead 가 다시 돌릴 명령 · **미확인** (실제 GPU 재기록은 이 CPU 작업으로 확인되지 않음). 끝나면 #550 에 요약 댓글을 남기고 되읽어 확인한다 (🤖 꼬리말 금지).
