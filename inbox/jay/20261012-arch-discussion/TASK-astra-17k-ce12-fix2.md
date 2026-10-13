> 분류: A/평가 · ASTRA 의뢰 17k · 같은 시험지 (CE12) 고침 재확인 (17i 의 요구를 Codex Worker C 가 고침)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 05:18
> 근거: VERIFY-astra-17i.md 3 · 4 · 5 절 · night-tools-20261013/ce12_fix17i/ (사본 · SHA256SUMS · 작업자 보고 lead_rerun/REPORT.md) · lead 재실행 job tmp codexw/leadC/
> 요지: 17i 가 요구한 A9 종료 출처 누락 · 묶음 파서와 묶음 해시 · 형식 시험 분리 · 기동 전 대조 · 경로 의존 · README 를 고친 판이 그 반례를 실제로 막는지, 그리고 v2 expect 0 기록을 허용할 수 있는지 판정해 달라
> 상태: 의뢰 (17j 다음 · 범위는 17i 가 지정한 후속 재확인)

# ASTRA 17k · CE12 고침 재확인

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5 로 내려가 일하고 있으니** lead 와 작업자의 보고 · 재실행 숫자 · 조건 해석을 평소보다 더 신중하게 원자료로 독립 대조해 주십시오. 17h 의 기준과 17j 에서 짚으신 기준 (변이는 정상 소스에서 같은 시험이 통과함과 의도한 실패 위치까지 확인 · import 오류 같은 엉뚱한 실패를 검출로 세지 않기) 을 적용해 주십시오.

## 1. 대상 (해시 고정)

`night-tools-20261013/ce12_fix17i/SHA256SUMS.txt` 의 12 개 (실행본 `C:/isaac/ext/go2_rl_robotlab/_eval/ce12/` 와 바이트가 같음. 작업자가 시험한 격리 사본과도 12/12 같음을 lead 가 대조). 17i 가 검증한 판은 `night-tools-20261013/ce12/` (커밋 214056ae) 이고 작업자가 고치기 전에 `_eval/ce12/v_astra17i/` 에 통째 보관했다 (12/12 해시 일치를 lead 가 확인).

| 파일 | 17i 판 앞 12 자 | 이번 판 앞 12 자 |
|---|---|---|
| `validate_dump.py` | ed912af7ac8b | dae3d93d6827 |
| `run_dump.py` | 075a7fd9760d | b9438e984a31 |
| `compare_native.py` | 3a890b17fcc4 | c71ad42c7b55 |
| `test_adapters.py` | 65852b18bae8 | 61d7c531a559 |
| `test_run_dump.py` | 3ab9dfb3d4f6 | e5b7cc9f6aba |
| `mutate_adapters.py` · `mutate_run_dump.py` | 4ed63b4de645 · d9c442f1eaec | 5b5f39a9b2c7 · c0a4a5725893 |
| `README-ce12-step1.md` | e9feaaa048eb | a76c5cd05659 |
| `adapters.py` · `cells.py` · `dump_native_cts.py` · `dump_native_v2.py` | 같음 | 같음 |

작성자는 **Codex Worker (gpt-6-sol)** 이고 검증자가 아닙니다. 작업서 `TASK-codex-worker-17i-fix.md` · 작업자 보고 `ce12_fix17i/lead_rerun/REPORT.md`.

## 2. 작업자 보고 요지와 lead 재실행

- C1 (A9): 필수 7 개 파일의 시작 · 종료 기록이 모두 올바른 형식으로 있어야 하고 (절대 경로 · 64 자 16 진 SHA256) 그 뒤 해시를 비교. 전체 CLI 시험: 정상 · 대문자 16 진은 APPROVED 2 · 종료 기록 부재 · 빈 객체 · 한 파일 누락 · 형식 오류 · 경로 누락 · 경로 변경 · 시작 기록 부재는 REJECTED 7 · 승인 대상 코드 파일을 읽을 수 없으면 PENDING 1.
- C2: 묶음의 중복 basename · 16 진 아닌 해시 · 빈 이름 거절 · stamp 의 files 목록에 묶음 파일 자체를 넣음 (묶음이 바뀌면 `--check_approval` 종료 1).
- C3: 차원 `[3, "10"]` 은 30, 빈 값 · 0 · 음수 · bool · 소수 · 숫자 아닌 문자열 · 잘못된 형 · names 와 dims 길이 차는 invalid. `VA-format-synthetic` 을 따로 두고 T23 · VA-real 은 실제 기록 통합 시험 (사본이 없으면 실패하며 skip 하지 않음).
- C4 (실제 실행 경로 `run_dump.py`): 구형 registry 를 읽기만 해 기존 `--scan_dirs` 밖의 존재하는 로그 부모를 자동으로 더하고 없는 과거 로그는 별도 목록 · registry 를 못 읽거나 GPU 조회 실패 · 대상 없음 · 여유 부족이면 slot 자식 전에 **종료 86** · `run.json.preflight` 에 시각 · scan 범위 · 추가 · 누락 로그 · GPU 인덱스 · UUID · 총량 · 여유 MiB 를 기록.
- C5: 상대 NPZ · meta · compare 보고서 · 묶음 경로를 활성 `_eval` 루트 기준 절대 경로로 해석 (두 작업 디렉터리에서 같은 결과).
- C6: README 에 reset 뒤 관측 이력 30 ~ 39 와 action 30 ~ 59 를 별도 열로 · 2 환경 x 30 env-step 명시 · 미확인 목록 보강.
- 작업자 시험 (격리 사본): adapters 23/23 · run_dump 139/139 (기존 132 + 새 7) · 기존 변이 24/24 · 65/65 · 이번 변이 11/11. **C8 (수정 검증기로 r2 재검) 은 하지 않았다.**
- **lead 재실행 (05:00 ~ 05:16 · isaac311-moects · `CUDA_VISIBLE_DEVICES=-1`):** 작업자 사본에서 같은 명령. adapters 23/23 (종료 0) · run_dump 139/139 (종료 0) · mutate_adapters 24/24 · mutate_run_dump 65/65 · mutate_17i 11/11. 변이 출력은 「failed [시험 이름] want [같은 이름]」 꼴로 의도한 시험이 실패했음을 확인한 줄 (예: `C06 ... failed ['T23'] want ['T23']`). PASS 가 아닌 줄 · skip · hold 없음. 원로그 `ce12_fix17i/lead_rerun/*.txt`. 변이 11 개 (이번) 의 정상 소스 대조는 작업자 보고에 있고 lead 는 변이 스크립트가 출력하는 want 일치만 확인했다.
- **보호 대조:** 작업 전 기준선과 비교해 `_eval/ce12/` 외 보호 대상 (옛 기록 · `out_ce12` · branch · s2 · handover · 검증된 코드 · python 환경) 변화 없음. `slot/isaac_usd_registry_v3.json` 은 04:57 RAND smoke 가 정상 갱신했고 `out_rand` 에 smoke 실행 폴더가 생김 (17j 허용 범위).

## 3. 물음

1. **C1 ~ C5 가 17i 의 반례를 실제로 막나.** 17i 3 절의 정상 1 + 누락 3 반례를 전체 CLI 로 다시 돌려 주십시오. 작업자의 7 + 2 + 1 변형 중 빠진 경로가 있나.
2. **C4 가 실제 실행 경로에 있나.** 17i 5 절의 「실제 상대 로그 · 구형 registry 읽기 전용 대조 · 기동 전 장치와 여유」 가 `run_dump.py` 의 자식 호출 전에 실제로 있고 (코드를 읽어서), 시험이 이를 실제 명령 인자와 이어 확인하나. 조회 실패 · 읽기 실패가 정말 보류인가. 종료 86 이 겹치지 않나.
3. **r2 원자료의 수정 검증기 재검.** 작업자가 안 한 C8 을 ASTRA 가 원본 stamp 를 쓰지 않는 사본 절차로 해 주실 수 있나 (17i 가 요구한 「r2 는 원본 유지 · 수정 검증기로 재검한 결과를 따로」).
4. **v2 expect 0 기록 허용 여부.** 17i 4 절의 최소 조건 4 개 (A9 고침 · 기동 전 preflight 실제 경로 · 기동 전 장치 · 여유 · 조건 충족 뒤 v2 짧은 진단 1 회) 가 충족됐나. 허용이면 명령 · 중단 조건 · 사전 확인 (17j 처럼) 을, 아니면 먼저 할 일을. 17f §3 의 「상대 실행의 실제 로그를 기동 직전에 직접 읽어 대조」 가 이번 preflight 로 대체되나 아니면 17j 처럼 lead 의 직접 읽기 기록이 따로 필요한가.
5. 허용 오차 · 미확인 목록 · 결과 문구 (17i 6 절) 가 이번 README 에서 빠지지 않았나.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17k.md` 한 파일. 첫 줄은 한 문장 판정. 표기: 확인됨 · 추정 · 미확인.
- 코드 수정 · GPU · Isaac · 커밋은 하지 마십시오. `_eval/out*` · `handover_*` · `handover-1635` · `slot/` 에 쓰지 마십시오. em dash 를 쓰지 마십시오.
