> 분류: A/평가 · ASTRA 의뢰 17p · v2 A1 경로 표기 후보 수정 검증과 새 tag 단회 기록 허용 여부
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 09:3x
> 근거: VERIFY-astra-17o.md 2 절 · night-tools-20261013/ce12_a1path/ (후보 · 새 시험 · 작업자 보고 · lead 재실행) · codexB4/ (작업자 원자료)
> 요지: 17o 가 권고한 후보 A (기록기 기본 경로 한 줄) 를 작업자 B 가 CPU 로 만들었다. 이 한 줄이 A1 거절 원인을 정확히 없애는지, 새 시험이 믿을 만한지, 운영 `ce12` 에 채택하고 새 tag 로 v2 를 한 번 더 기록해도 되는지 판정해 달라. 덧붙여 GPU 0 이 05:46 부터 비어 있어 1043 평가를 실행 가능한 형태로 만드는 최소 설계도 묻는다
> 상태: 의뢰 (GPU 1 · GPU 0 모두 비어 있음)

# ASTRA 17p

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5** 입니다. 작업자와 lead 의 숫자 · 해석을 평소보다 더 신중하게 원자료로 독립 대조해 주십시오. 17j · 17n · 17o 의 기준 (변이는 정상 소스의 같은 시험 통과 + 의도한 실패 위치 · 엉뚱한 실패를 검출로 세지 않기 · 수치는 장치 전체 값인지 몫인지 구분) 을 적용해 주십시오.

**분량:** `VERIFY-astra-17p.md` 한 파일. 첫 줄 한 문장 판정, 질문마다 「판정 · 근거 · 남길 미확인」. 코드 수정 · GPU · Isaac · 커밋은 하지 마십시오. `_eval/out*` · `slot/` · `handover_*` · `handover-1635` 에는 쓰지 마십시오 (읽기는 허용). 지금 GPU 는 둘 다 비어 있습니다. em dash 금지.

## 1. 대상 (해시 고정)

작업자 B (Codex Worker · gpt-6-sol · 검증자 아님) 의 후보. 보고 `ce12_a1path/REPORT-codexB4.md` · 작업 원자료 `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexB4/` (격리 사본 · `ce12_candidate/` · `fixture_real/` · `logs/` · `mutants/`).

| 파일 | SHA256 (앞 12 자) | 비고 |
|---|---|---|
| 운영 `_eval/ce12/dump_native_v2.py` (17n 판) | `251220254fc7` | 지금 운영 중 |
| 후보 `dump_native_v2.py` | `a3da62b8185f` | 운영본과 **한 줄만 다름**: 79 행 `args = parser.parse_args()` 바로 뒤 80 행 `args.env_yaml = os.path.abspath(args.env_yaml).replace("\\", "/")` |
| 새 시험 `test_v2_signature_path.py` | `f4c7ea4c7dec` | 후보 폴더에만 있음 (운영 `ce12` 에는 없음) |
| 후보 B (보관만) `candidate_B_adapter_path.py` | `dc41eab32ae4` | `adapters.py:747` 경로 정규화 코드 조각 |

후보 폴더 `ce12_candidate/` 의 `SHA256SUMS.txt` 56 항목은 lead 가 56/56 재해시 일치를 확인했다 (사본 `ce12_a1path/SHA256SUMS-candidate-full-ce12.txt`). 운영 `ce12` 의 다른 6 개 코드 파일 (validate_dump · run_dump · adapters · cells · compare_native · dump_native_cts) 은 후보 사본과 바이트가 같음을 lead 가 대조했다. 후보는 **운영 `_eval/ce12` 에 아직 반영되지 않았다.**

## 2. 작업자 보고와 lead 재실행

- 작업자: 원인은 `dump_native_v2.py:49` 의 슬래시형 `LAB` 과 `:61` `os.path.join(LAB, "models", …)` 의 혼합 구분자, `adapters.py:747` 이 입력 문자열을 그대로 `source.path` 에 기록, `validate_dump.py:263~269` `_sig_now` 는 `adapters.V2_ENV_YAML` (전부 슬래시) 사용, A1 은 JSON 전체 정확 비교. 경로 전수 열거: `meta.args.env_yaml` · `meta.env_yaml` 이 같은 혼합 표기 (A4 는 `same_path`) · `meta.args.checkpoint` 슬래시 · `meta.checkpoint` 역슬래시 (M1 `same_path`) · `meta.args.outdir` 슬래시 (A4 `same_path`) · `lab_files_sha256` 는 절대경로 없음 → **A1 과 같은 정확 문자열 불일치는 더 못 찾음.**
- r2 영향 비교: 후보 A 는 r2 도장이 가리키는 코드 파일에 **추가 변경 0 개**, 후보 B (adapters) 는 `code_adapters.py` 가 더해져 추가 1 개. 단 **r2 도장은 지금 코드로도 이미 무효**: 작업자 (격리 사본) 와 lead (실제 `_eval` 에서 r2 의 자기 체크포인트로 `--check_approval`) 모두 `APPROVAL INVALID · 승인 뒤 바뀐 파일 ['code_compare_native.py', 'code_validate_dump.py', 'code_run_dump.py']` (17i 뒤 C 고침 때문). 즉 「후보 A 가 r2 를 살린다」 가 아니다.
- 새 시험 `test_v2_signature_path.py` (P1 ~ P4): 기록기의 실제 `--env_yaml` 기본식과 파싱 후 대입식을 AST 로 꺼내 실제 `LAB` 로 평가 · 실제 08:52 `signature.json` (복사본) · 실제 `native.npz` 의 관절 이름 · YAML 내용만 바꾼 복사본은 서로 다른 서명. 작업자: 수정 전 1/4 · 수정 후 4/4 (isaac311-moects 와 isaac311 둘 다) · 작업자 변이 3/3 (되돌림 · 엉뚱한 칸 · 내용 해시 고정).
- 작업자 기존 회귀 (격리 사본 · 후보 폴더): `test_adapters` 23/23 · `test_run_dump` 139/139 · `mutate_adapters` 24/24 · `mutate_run_dump` 65/65 · `mutate_17i` 11/11 · `test_v2_load_device` (isaac311) 1/1 · 변이 로그에 MISSED · ImportError · ModuleNotFoundError 0. `test_v2_load_device` 를 isaac311-moects 로 돌린 것은 17n 이 말한 다른 러너 `alg_cfg` 로 실패 (지정 환경이 아님 · 분모에 안 섞음).
- **lead 재실행 (09:23 ~ 09:25 · CPU · `CUDA_VISIBLE_DEVICES=-1`):** (1) 후보와 운영본의 차이가 정확히 한 줄 (위 80 행) (2) 새 시험을 후보 사본에서 **isaac311-moects 4/4 PASS · isaac311 4/4 PASS** (3) lead 가 만든 변이 셋을 같은 시험에서: 한 줄 삭제 · 방향을 거꾸로 (`/` → `\`) · 드라이브 문자를 소문자로 (`c:/`) 모두 `failed [P1,P2,P3] want [P1,P2,P3]` · rc 1 · P4 통과 · import/module/구문/환경불일치 오류 없음 (3/3) (4) `test_v2_load_device.py` 를 isaac311 로 후보에서 1/1 PASS. **lead 가 다시 돌리지 않은 것:** 위 기존 회귀 (23 · 139 · 24 · 65 · 11) 는 작업자 로그만이다 (이 후보가 건드린 파일이 `dump_native_v2.py` 한 줄뿐이고 `test_run_dump.py:174, 421` 가 그 파일을 이름으로만 본다는 점을 grep 으로 봤을 뿐). 재현 근거 `ce12_a1path/lead_check/` (`leadB4_check.py` · 로그).

## 3. 물음

1. **한 줄이 맞고 충분한가.** 80 행의 위치 (`parse_args` 뒤 · 이후 `args.env_yaml` 소비처: forbidden path 검사 (`_nc` 정규화) · 메타 기록 (`meta.env_yaml` · `meta.args.env_yaml`) · `A.parse_v2_env_yaml(args.env_yaml)` · `V2Adapter.from_env_yaml(..., env_yaml=args.env_yaml)`) 에서 부작용이 없는가. `os.path.abspath` 가 상대 경로 입력을 작업 디렉터리 기준으로 바꾸는 점이 실제 기동 (기본값만 씀) 에서 무해한가. A4 · A6 이 새 표기에서 계속 통과하는가 (ASTRA 가 다른 칸이 숨어 있지 않음을 17o 에서 확인한 것을 다시 확인). 후보 B 를 쓰지 않고 A 로 가는 것이 r2 · 다른 도구 · 기존 승인과의 관계에서 옳은가.
2. **새 시험이 믿을 만한가.** AST 로 기록기의 실제 기본식을 꺼낸다는 설명이 사실인지, 실제 서명을 만드는 경로를 타는지, 시험이 후보 사본 경로 (`codexB4/`) 에 고정돼 있어 운영 `ce12` 에 그대로 넣을 수 없다는 점 (운영에는 넣지 않고 저장소 사본만 둘 계획) 이 괜찮은지, P4 가 「경로 통일이 출처 검사를 약하게 만들지 않음」 을 실제로 보이는지, 작업자 변이 3 개와 lead 변이 3 개가 의도한 시험에서만 실패하는지. 반대로 이 CPU 시험으로 못 보는 것 (실제 recorder 프로세스가 같은 서명을 만드는지) 은 새 기록이 처음으로 보이는 것이라는 구분.
3. **운영 `ce12` 에 채택해도 되는가.** lead 계획: 채택 전에 `_eval/ce12/dump_native_v2.py` 를 `_eval/ce12/v_17n/` 에 보관 (해시 확인) → 후보 한 줄만 반영 (새 해시 `a3da62b8…` 를 확인) → 그 외 파일은 건드리지 않음. 새 시험은 운영 `ce12` 에 넣지 않음. 이 순서와 보관 방식이 맞는가. 채택 직후 17n 4 절 5 항의 코드 묶음 (10 파일) 을 새 해시로 다시 만들어 기동 전에 고정한다는 계획이 맞는가.
4. **새 tag 단회 기록 허용 여부.** 허용이면 17n 4 절의 조건을 그대로 적용하는 것으로 충분한가 (기동 직전 현재 장치 · 실제 상대 로그 · 해석기 구분 (기록기 isaac311 · 도구 isaac311-moects) · 공통 lock · v3 registry · attempt 별 USD 루트 · `--expect_conversions 0` · 명시적 미래 마감 · 보호 파일 불변 · 시험용 CE12_* 환경 변수 없음). 바뀌는 점이 있으면 최종 명령과 확인 목록을 적어 달라 (작업자의 `--deadline 0` 은 쓰지 않는다). 새 기록의 승인 단계는 `--stamp` → CPU `compare_native --recompute_action` → `--approve --compare_report … --code_bundle <새 묶음>` → `--check_approval` (이번에는 A1 이 통과해야 한다). A1 이 다시 거절되거나 다른 칸이 막으면 거기서 끝 (다른 후보 · 면제로 이어가지 않음). 성공했을 때 보고서에 쓸 수 있는 문구 (17o 문구에서 APPROVED 만 갱신) 와 쓰면 안 되는 문구.
5. **(시간이 있으면 · 설계 권고만) GPU 0 이 05:46 부터 비어 있다.** 1043 쌍 학습은 두 갈래 모두 VALID 로 끝났고 (off 19280 초 · on 19659 초 · 부모 E1 20,000 · 시드 1043 · env 8192 · 각 4,000 update) 평가가 없다. ASTRA 17 은 「목표 세 칸과 등록한 회귀 칸」 이 필요하다고 했다. 현재 v6 드라이버는 `unseen_driver_cmdr_v6.py:92` 의 `INPUT_FILES` 에 `cmdr_s1042_{m}_u4000` 이 하드코딩돼 있어 1043 을 그대로 돌릴 수 없고 (승인된 코드 · 해시 묶음 `91d35be9…`), 승인 json 도 1042 의 75 실행 계획에 묶여 있다. GPU 0 에서 평가할 수 있는 최소 설계를 권고해 달라: (a) 1043 용으로 입력 경로만 인자화한 새 판 (새 승인 필요) 의 최소 변경 (b) 「목표 칸」 의 후보 (1042 에서 off 대비 on 이 눈에 띄게 달랐던 칸들 · 추측이 아니라 `UNCR-cells-v6.csv` 에서 고른 칸) 와 회귀 칸의 후보 · 통과 / 생존 / 누락 칸의 판정을 미리 적는 방식 (c) 이것이 팀장의 「CMD-R 규약 교정」 결정과 묶이는 부분 (팀장 몫으로 남길 것) 과 lead 가 먼저 준비해 둘 수 있는 것을 가르기. 이 물음은 GPU 기동 허용을 구하는 것이 아니다.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17p.md` 한 파일. 첫 줄은 한 문장 판정. 표기: 확인됨 · 추정 · 미확인.
