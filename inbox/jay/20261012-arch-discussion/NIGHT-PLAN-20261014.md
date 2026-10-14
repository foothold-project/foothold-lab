> 분류: 운영 · 밤 작업 순서 (10/14 00:06 → 아침 보고)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 00:06 · 판 2 00:57 (ASTRA 17h 반영)
> 근거: #550 인계 6148371113 · VERIFY-astra-17c ~ 17f · 17f2 · 17h · AGENTS 7 절 (mai-os 0699447)
> 요지: 깨어나면 「읽기 · 재개 규칙」 → 「진행 중 실행」 → 「판정 조건」 → 「일 표」 순으로 복원하고, 의존 · 자원 조건을 채운 일부터 한다. 검증 대기는 까닭과 다음 확인을 남기고 독립 일은 계속한다
> 상태: 진행 중 (바뀔 때마다 이 파일을 먼저 고친다)

## 목표와 금지 범위

- **목표:** 아침까지 GPU 두 장을 쓴다 (팀장 10/13 · 10/14 00:05). 아침 보고는 페이지 7판 (렌더 확인 포함) · #550 · #546 · 채팅.
- **위임 범위:** 팀장 10/13 「제안 · 권고 대로 진행」 + 각 ASTRA 판정이 허용한 단계만. ASTRA 판정은 새 권한을 만들지 않는다 (17h 4 절).
- **금지:** `_eval/out` · `handover_*` · `handover-1635` 에 쓰기 · 남의 커밋 안 된 변경 커밋 · 시스템 설정 변경 · 변수 경로 `rm` · 돌고 있는 셸 스크립트 수정 · isaac311 / isaac311-moects 에 설치 · 검증 대기 단계 기동.

## 진행 중 실행

| 실행 | 식별 | 로그 · 진행 확인 방법 | 마지막 관측 | 예상 끝 · 다음 확인 |
|---|---|---|---|---|
| GPU 0 · CMD-R 1043 쌍 | **끝 05:46:03 (`PAIR 1043 DONE`)**: off 00:18:17 끝 (19280 초) · on 05:45:59 끝 (19659 초) · 둘 다 `VALID` · 학습 회차 24000/24001 · Traceback 0 · night exit 0 | 콘솔 `_eval/out_smoke/night_1043_v3.console.txt` · `_eval/out_branch/cmdr_s1043_*` | **GPU 0 은 05:46 부터 빔** (15 MiB). 이유: 1043 후속 평가는 ASTRA 17 이 「사전 등록한 평가 (목표 세 칸 + 회귀 칸)」 가 필요하다고 했고 등록안과 검증된 평가 계획이 없음. S2 smoke 는 학습 루프 연결 전이라 보류. 판단이 필요한 일이라 Sonnet lead 가 혼자 만들어 띄우지 않음 | 팀장 · Opus 에서 평가 등록안 → ASTRA → 기동 (놀았던 시간은 아침 보고에 적음) |
| GPU 1 | 01:16:26 CTS r2 기록이 끝난 뒤 **빔** (이유: 띄울 수 있는 일이 모두 검증 · 고침 대기 · 17g 와 17i 가 요구한 고침이 끝나기 전에는 허용된 기동이 없음) | job tmp `ce12fix/r2_*.txt` | r2 COLLECTED · 대조 ALL PASS · A9 PASS (그 시점 승인기) · 재확인 유효. ASTRA 17i: r2 수치만 제한 채택, 승인기 일반 채택 보류 | 17j 가 RAND smoke 를 허용하면 smoke · 아니면 계속 빔. 놀았던 시간은 아침 보고에 적는다 (01:16 부터) |
| 감시 스크립트 (사용 한도 대비) | 셸 bd8y4zrp0 · job tmp `arm_v5_full.sh` | `arm_v5.log` | **끝 01:33:48 · 승인 json 이 없어 아무것도 띄우지 않음** (17g 판정 파일이 10 분 지나도 승인 없음 · 설계대로) | 더는 필요 없음 · v5 full 은 v6 로 대체 |
| 하위 작업 · CE12 대조기 고침 + 17f 4.2 ~ 4.4 | 00:29 맡김 · 01:02 보고 · 끝 | job tmp `ce12fix/` | lead 재실행 01:15: 시험 23/23 · 132/132 · 변이 24/24 · 65/65 · 해시 그대로 · 저장소 사본 22b97fe3 | ASTRA 17i 로 검증됨 → 남은 고침은 Codex Worker C |
| 하위 작업 · S2 판 3 | 00:40 맡김 · 01:27 보고 · 끝 | job tmp `s2v3/lead/` | lead 재실행 01:35: 시험 14/14 · 변이 69/69 · 해시 그대로 · 저장소 사본 db7c3e7b | 학습 루프 연결 · smoke 등록이 남아 S2 학습은 여전히 보류 |
| heartbeat 예약 | `eaa6843f` (매시 :27 · 세션 안에서만 · 7 일 만료) · 02:39 등록 · 옛 25e8a2a3 · 2b1bfe25 · b698612f 지움 · CronList 에 하나만 | 이 문구로 깨어난 기록 | 옛 문구 (25e8a2a3) 로 02:41 도착 · 새 문구 (eaa6843f) 로 03:54 도착 확인 | 매 도착 |
| ASTRA 17i | 02:40 보냄 · **끝** (`VERIFY-astra-17i.md` · 03:54 이전에 도착) | 아래 「판정 조건」 17i | 제한 채택 · A9 P1 · v2 보류 | Codex Worker C 고침 뒤 17k |
| Codex Worker A (미경험 v6 · `term_602208c0`) | 02:38 접수 · 02:44 사고로 멈춤 · 03:57 격리 조건으로 재개 · **04:56 끝 보고** (A1 ~ A5) · 컨텍스트 18 % | `codexA/REPORT.md` | **lead 재실행 통과 (04:58 ~ 05:16): 합성 72/72 · 변이 44/44 (want 일치) · 실제 `out_uncr` v3 재검 valid 23 · manifest 91d35be9 (75 실행 · 등록 일치)** · 재개 뒤 `out_uncr_v5` 변화 없음 · 저장소 사본 5dfd8e7c | 17l |
| Codex Worker B (무작위화 판 4 · `term_223a8374`) | 02:38 접수 · 02:56 끝 · 04:59 smoke 실패 수정 추가 작업 (환경 2 개 이상 · 보관 `rand_scenes/v4_smokefail/`) | `codexB/REPORT.md` · `codexB2/REPORT.md` | 일하는 중 (추가 작업) · 컨텍스트 35 % 에서 시작 | 끝나면 lead 재실행 → 17m |
| Codex Worker C (CE12 고침 · `term_766933da`) | 03:58 접수 · **04:36 끝 보고** (C1 ~ C6 · C8 은 안 함) · 컨텍스트 10 % | `codexC/REPORT.md` | **lead 재실행 통과 (05:00 ~ 05:16): adapters 23/23 · run_dump 139/139 · 변이 24 · 65 · 11 (want 일치)** · 격리 사본과 `_eval/ce12` 12/12 같음 · 저장소 사본 `ce12_fix17i/` | 17k |
| ASTRA 17j | 03:59 보냄 · **끝 04:17** (`VERIFY-astra-17j.md`): RAND v4 smoke 만 조건부 허용 · lead 변이 오집계 정정 | 위 「RAND smoke 기동 기록」 | smoke 는 04:57 에 실행되어 S1 실패 | 17m |
| ASTRA 17k · 17l | 05:19 보냄 (한 메시지 · 17k 먼저) · 터미널 term_fe1daede · ASTRA 컨텍스트 19 % 남음 (재시작은 팀장 승인 대기 · 못 하면 압축에 맡김) | `VERIFY-astra-17k.md` · `VERIFY-astra-17l.md` · (승인 시) `uncr_v6/approval-astra-17l.json` | 검사 중 | 판정 전문 → v2 기록 · v6 full |
| ASTRA 17g (끝) | 00:54 보냄 · 터미널 term_fe1daede | `VERIFY-astra-17g.md` · (승인 시) `night-tools-20261013/uncr_v5/approval-astra-17g.json` | 검사 중 · 00:59 터미널 제목에 「Context 11% left」 (17g 도중 자동 압축 또는 중단 위험 · super2 상태판에 「팀장: ASTRA 재시작 승인」 대기가 있음 · 17g 끝나기 전 재시작은 17g 를 잃음) | 파일 생김 · 다음 의뢰 전에 ASTRA 컨텍스트 처리 (새 세션 또는 압축) 를 팀장 · super2 와 맞춤 |

부팅 기준: **09/17 21:16 KST** (`Win32_OperatingSystem.LastBootUpTime`). 다르면 위 PID · 실행을 그대로 믿지 않고 새 기동을 보류한 채 다시 확인하고 #550 · 채팅에 보고한다. 적법한 재부팅이 확인되면 이 기준값을 고친다.

## 판정 조건 (대상별 · 조건마다 지금 상태와 증거)

**17f (00:17 · 고쳐서 기동)**

| 절 | 조건 | 지금 |
|---|---|---|
| §1 | 야간 셸 시험 호출은 Git Bash 실제 경로와 PATH 를 고정 (기본 PATH 는 `system32/bash.exe` 를 집어 rc 127) | 미반영. 운영 1043 은 Git Bash 안에서 돌고 있어 해당 없음 (추정). 시험 `test_night_1043_v3b.py` 를 다시 돌릴 때 PATH 고정 |
| §3 | CE12 는 v3 전용 registry · v2 registry 무수정 · 같은 변환 잠금 · attempt 마다 USD 루트 · dry-run 확인 · **실제 상대 로그가 scan 범위에 들어가는지 · 구형 registry 가 가리키는 범위 밖 로그의 읽기 전용 대조 · 읽기 실패를 충돌 없음으로 보지 않기** | **일부만 충족** (ASTRA 17i 가 짚음: 내가 적은 「충족」 은 원문보다 좁았음). 충족: v3 registry (`run_dump.py:63`) · 같은 lock · attempt USD 루트 · dry-run. **빠진 것:** 상대 로그 포함 확인 · 구형 registry 읽기 전용 대조 · 읽기 실패 보류 → Codex Worker C (C4). 기동 전 여유는 guard 가 보지 않음 (guard 숫자는 실행 중 요약) → C4 |
| §4.2 | 승인 재확인이 which · checkpoint · tag · attempt 를 대조 (다른 모델이면 실패) | 하위 작업 고침 (01:02 · stamp 에 대상 · VA-ck-target) · lead 재실행 중 · ASTRA 17i 검증 전에는 채택 안 함 |
| §4.3 | 실행 당시 코드 해시를 승인 묶음과 연결 | 하위 작업 고침 (provenance 시작 · 끝 · 실행 중 변경 87 · A9). 00:25 첫 기록은 guard 해시 미기록 · 기록 뒤 수정으로 A9 REJECTED. **「실행 중 변경 없음」 은 종료 해시 근거가 없어 미확인.** r2 는 시작 · 종료 해시 7 개 모두 있음. A9 에 P1 결함 (종료 기록 누락이 승인됨) → C1 |
| §4.4 | `switch_step <= T-1` · 전환 뒤 action 비교 횟수 · miss 미측정과 0 구분 | 하위 작업 고침 (1..T-1 · reset 뒤 60 · 전환 뒤 20 action step 셈 · miss None 은 미측정) · ASTRA 17i 전에는 채택 안 함 |
| §4.5 | 1 고정 · 2 짧은 기록 · 3 COLLECTED 와 출처 확인 · 4 `compare_native --recompute_action` (1e-6 · 1e-4 사후 완화 금지) · 5 CTS 승인 뒤 v2 expect 0 | 1 · 2 끝 · 3 COLLECTED 22 PASS · 4 고친 대조기로 ALL PASS (보고서 `out_ce12/native/cts_e1_m20000/compare_report_20261014-005010.json`) · 5 대기 (CTS 승인 뒤) |
| §5 | S2 학습 기동 보류 (센서 · rollout 저장소 · 학습기 연결 · 사전 등록 전) | 보류 유지 |

**17f-2 (00:33 · 다른 안)**: 첫 S2 A/B 는 encoder 전 구간 실제 고정 (팀장 확정 대기) · r=0 은 실제 고정이 아님 (판 3 이 고침) · smoke 기준 (cosine 0.9 · 평지 −10%p) 자동 전환 금지 · 사전 등록 5.3 의 1 ~ 6 미충족 · S2 자체 갱신 번호 · adaptive LR 이 group LR 덮어쓰기 검사. S2 학습 기동 없음.

**17h (00:49 · 고쳐서 채택)**: 아래 「읽기 · 재개 규칙」 과 하트비트 문구로 반영 (00:57). 수용 기준 (17h 7 절) 은 실제로 지키는지 아침까지 관측한다.

**17i (CTS r2 수치는 제한 채택 · 일반 승인 관문과 v2 기동은 보류)**

| 대상 | 판정 | 지금 |
|---|---|---|
| r2 수치 | 제한 채택: E1 model_20000 한 체크포인트 · 평지 3 명령 x 4 환경 · 60 step · 강제 reset 2 · 전환 1 · 관측 · target · last action 차 0 · CPU action 2.15e-6 | 결과 문구는 17i 6 절 끝의 권장 문구. 자연 종료 reset 0 · 경계 clip · height miss · v2 는 미검증 |
| 승인기 A9 | P1: `provenance_end` 가 없거나 `{}` 이면 APPROVED (ASTRA 가 전체 CLI 로 재현) | Codex Worker C (C1) |
| 묶음 파서 · bundle 해시 | `read_bundle` 느슨 · `--check_approval` 이 bundle 파일을 다시 해시하지 않음 | C2 |
| dims 형식 | 합성 형식 시험과 실제 기록 통합 시험을 분리 · skip 은 드러내기 | C3 |
| 기동 전 대조 · 장치 · 여유 | 상대 로그 · 구형 registry 읽기 전용 대조 · 기동 전 장치와 여유 확인 (guard 숫자는 실행 중 요약이지 기동 전 확인이 아님 · 조회 실패는 보류) | C4 |
| 경로 의존 · README | 작업 디렉터리에 따라 A6 이 달라짐 · reset 표 열 구분 | C5 · C6 |
| **v2 기록 (expect 0)** | **보류.** C 고침 · lead 재실행 · ASTRA 17k · 기동 전 확인 뒤 짧은 진단 1 회로 제한 | 대기 |
| r2 | 원본 유지 · 수정된 검증기로 재검한 결과를 따로 | C8 |
| 내 기록 정정 | 17f §3 행은 원문보다 좁았음 · 첫 기록의 「실행 중 변경 없음」 은 미확인 · guard 숫자는 기동 전 확인이 아님 | 위 17f 표에 고침 |

**17g (01:26 · 고쳐서 기동 · 승인 json 없음)**

| 대상 | 조건 | 지금 |
|---|---|---|
| A v5 §2.1 P1 | GPU 대기 (최대 600 초) 뒤 자식 호출 직전에 STOP · 마감 · 코드 · 입력 재검사 (대기 중 변경이면 자식 0 회) · slot 잠금 대기 뒤 실행 바이트 보장 · 새 manifest (옛 ac09 재사용 금지) | 미반영 |
| A v5 §4 | 재검 보고 · 기동 기록에 sys.executable · python 전체 버전 · numpy 판과 경로 · 판정 코드 해시 · 검증 환경과 다르면 보류 | 미반영 · 원인은 lead 쪽에서 BLAS FMA 로 분리됨 (7c · 17g 는 미분석으로 둠) → BLAS 이름 · 커널도 기록 대상 |
| A v5 §5 | 결과 표 곁에 해석 범위 문장 (seed 1042 한 짝 · 조건부 회귀) · 통과 · 생존 · 건넘 분리 | 아침 7판에 반영 |
| B RAND §3.1 P1 | v3 를 부르면서 구형 registry (`isaac_usd_registry.json`) 를 씀 (RL:863~875) → `_v3.json` · 구형은 읽기만 · `out/branch` 등 실제 로그 위치를 scan 에 · 구형 읽기 실패는 기동 전 실패 · 공유 시 유실 · 분리 시 보존 CPU 시험 | 미반영 · **smoke 도 보류** |
| B RAND §3.2 P1 | 밀기 사건 heading 을 궤적 heading 과 잇기 (±π) · 요청 성분 누락 · NaN 거절 · ASTRA 반례 둘이 `validate_attempt` 에서 거절돼야 | 미반영 |
| 공통 §5 | 순서: 고침 · CPU 반례 → RAND smoke 만 → 장치 UUID · 기록 · 영상 · 자원 실측 → 네 장면 한 실행 → v5 full. smoke 실패 뒤 자동 시작 예약 금지 · RAND 에 `--deadline` 명시 · 여유 조회 None 은 미확인 | |

그래서 GPU 1 은 고침과 재확인 (17g 6 절 1 ~ 4) 까지 빈다. 감시 스크립트는 승인 json 이 없어 10 분 뒤 띄우지 않고 끝남 (설계대로).

## 일 표 (우선순위 순 · 의존과 자원을 보고 고른다)

| 순서 | 일 | 의존 · 자원 | 상태 | 다음 행동 |
|---|---|---|---|---|
| 1 | GPU 0: 1043 off → 검증 → on | 스크립트 | 단계 끝 (off VALID · on 00:18:20 START) · 실행은 「진행 중 실행」 | iteration 관측 |
| 2 | ASTRA 17f | | 끝 00:17 (b77106d2) | 조건은 위 표 |
| 2b | ASTRA 17f-2 → 팀장 채팅 · #550 | | 끝 00:33 · 채팅 · #550 6149317273 (df9e89f9) | 팀장 확정 대기 |
| 2c | ASTRA 17h | | 끝 00:49 (7d24517a) · 반영 00:57 | 관측 |
| 3 | GPU 1: 같은 시험지 CTS E1 20000 짧은 기록 | 17f §3 일부 충족 | 00:25 첫 기록: COLLECTED · 대조 ALL PASS · A9 REJECTED (출처). 01:16 r2: 수치 제한 채택 (17i) | 3b |
| 3b | GPU 1: CTS 재기록 r2 | 17f §4.5 의 짧은 진단 범위 | **끝 01:16:26** · lead 재실행 통과 · 수치 제한 채택 (17i) | 수정 검증기로 r2 재검 (C8) |
| 3c | ASTRA 17i | | **끝** · 제한 채택 · A9 P1 · v2 보류 | 17k (C 끝난 뒤) |
| 4 | GPU 1: 같은 시험지 v2 기록 (expect 0) | **17i 가 보류**: C1 · C4 고침 · lead 재실행 · ASTRA 17k · 기동 전 확인 뒤 짧은 진단 1 회 | 대기 | |
| 5 | 미경험 v5 · 무작위화 lead 재실행 | | 끝 00:43 · v5 isaac311-moects 51/51 · 변이 38/38 · 옛 루트 재검사 23 valid · 묶음 e5597517 · manifest 75 · base python 3.13 은 X01 hold (원인은 BLAS FMA 여부 · 7c) · 무작위화 27/27 | |
| 6 | ASTRA 17g | 5 끝 · ASTRA 한 번에 하나 | 끝 01:26 · 고쳐서 기동 (A v5 full 미승인 · B RAND smoke 보류) · 조건은 위 표 | 6b |
| 6b | 17g 고침: A 미경험 v6 (Codex Worker A) · B 무작위화 판 4 (Codex Worker B) | 작업서 `TASK-codex-worker-17g-fix.md` | A: 사고 후 재개 중 · B: 끝 (lead 재실행 통과) | A 보고 → 17j 와 별도로 17l (v6) |
| 6c | ASTRA 17j: 무작위화 판 4 재확인 (B1 · B2 · B3 · smoke 허용 여부) | B 끝 · lead 재실행 통과 | **03:59 보냄** | `VERIFY-astra-17j.md` 전문 → smoke 조건 |
| 7 | GPU 1: 무작위화 smoke → 스틸 · 영상 전 프레임 확인 → 네 판 한 실행 → 미경험 v5 full 75 | 17g 허용 · GPU 1 에 Isaac 하나 · 여유 6,144 MiB 이상 | 대기 | |
| 7b | S2 판 3 (CPU) | 17f-2 | 01:27 보고 (시험 14/14 · 292 칸 · 변이 69/69 · 첫 실행 T13 기대 상수 1 ulp FAIL · 변이 1 차 68/69 (q28) 를 고쳐 다시 돎 · 학습 루프 연결 · smoke 등록 5.3 의 2 ~ 6 · 난수 상태 · 센서 관문은 안 됨) · lead 재실행 백그라운드 bjwaki7me (job tmp `s2v3/lead/`) | lead 재실행 01:35: 시험 14/14 · 변이 69/69 (BASELINE 14/14 · 원본 해시 시작 == 끝) · 네 파일 해시 그대로 · 저장소 사본 night-tools s2/ (판 3) | ASTRA (17i 뒤) |
| 7c | 미경험 X01 환경 차이 분석 (CPU) | 독립 · 임시 폴더에서만 | 끝 01:06 (하위 작업 · 산출물 job tmp `x01env/`): 원인은 python · numpy 가 아니라 **BLAS gemv · ddot 의 FMA 여부** (q_metrics.py:224 `xy @ e` · :249 norm). MKL · OpenBLAS Nehalem 은 두 번 반올림, OpenBLAS 기본 (Cooperlake) 은 FMA · 원본 23 실행 바이트는 FMA 쪽. 차이는 progress_m 150 · disp_m 12 값 · 1 ULP · 서식 차 0 · 판정 열은 이 자료에서 같음 (일반 보장은 미확인 · 4.0 m 경계에서 뒤집힐 수 있음). lead 확인 01:10: 같은 isaac311-moects 에 `OPENBLAS_CORETYPE=Nehalem` 만 주니 X01 valid 8 · hold 15 (job tmp uncr_v5_lead_test_nehalem.txt). 「통과 환경」 도 CPU 커널에 기댐 · Linux 이전 때 다시 잼 | 17g 판정에 보탬 · 관문 고침 (환경 지문 · `[post-env]`) 은 ASTRA 검토 뒤 |
| 8 | 아침 7판 (조각 job tmp `e12page/`) → 렌더 1920 · 1366 · 390 · 라이트 · 다크 → 게시 → #550 · #546 · 채팅 | 아침 · 밤 결과 | 대기 | |
| 9 | super2 에 「GPU 1 out_* 실행 끝」 | 7 끝 | 대기 (Windows 업데이트 알림은 00:45 보냄) | |

## 사용 한도 (super2 01:13 전달)

5 시간 한도 88 % (01:30 무렵 100 % · 해제 04:20) · 주간 81 %. 한도에 걸리면 lead 는 04:20 까지 멈춘다. 그동안: GPU 0 1043 on 은 스크립트가 끝까지 (05:40 무렵) · GPU 1 은 위 감시 스크립트만. 새 하위 작업은 띄우지 않는다 (super2 요청). 돌고 있는 하위 작업: S2 판 3. 깨면 (04:20 뒤 첫 heartbeat) 17g 전문 → 감시 스크립트 로그 → 17i 보내기 (ASTRA 컨텍스트 처리 먼저) → 무작위화 smoke → 아침 7판.

## 작업자 사고 기록 (04:00 확인)

- **무엇이:** Codex Worker A (미경험 v5 고침) 가 02:42:26 에 합성 시험을 돌렸는데, v5 를 복사한 `unseen_driver_cmdr_v6.py` 의 출력 루트가 아직 실제 `_eval/out_uncr_v5` 를 가리켜 가짜 자식 시험이 거기에 썼다. 작업자는 즉시 멈추고 정직하게 보고했다 (A1 ~ A5 모두 미완료).
- **영향 (lead 가 기준선 대조로 확인):** `out_uncr_v5` 만 2 개 → 5 개 파일. `driver_v5.json` 은 lead 의 00:43 manifest 단계 기록이 가짜 시험 기록으로 덮였다 (단계 기록일 뿐 · `manifest_v5.json` 은 00:43:32 그대로). 새 파일 `HALT_v5.json` · `uncr_par_gap_fwd05.slot.json` · `uncr_par_gap_fwd05.guard.json`. 그 밖의 보호 묶음 (out_uncr · out_uncr_reval · slot · branch · out_ce12 · handover · ce12 · s2 · out_smoke · 나머지 out_branch · 검증된 코드 · isaac311-moects 환경) 은 변화 없음. GPU 1 에 python 프로세스 0 (Isaac 은 뜨지 않음).
- **처리:** 지우지 않고 둔다 (증거 보존 · 변수 경로 삭제 금지). v5 는 17g 가 승인하지 않았고 새 루트 `out_uncr_v6` 의 v6 로 대체되므로 `HALT_v5.json` 이 v5 full 을 막는 것은 무해. 새 기준선 `codexw/protect_baseline2.txt`. A 는 03:57 에 격리 조건 (기본 루트 · 환경변수 · HALT 이름 변경 · 시험 시작부 단언) 으로 재개. **같은 사고가 한 번 더 나면 A 결과를 채택하지 않는다.**
- **교훈:** 복사해 만든 새 도구는 첫 실행 전에 출력 루트가 작업 폴더 안인지 단언한다 (C 작업서 0.1 에 반영). YOLO 와 기준선 대조의 조합에서 첫 사고는 기준선 대조로 잡혔다.

## GPU 0 이 놀기 시작한 때 (05:47)

- 05:46 1043 쌍 학습이 끝나 GPU 0 이 비었다. 허용된 다음 일이 없다: (1) 1043 후속 평가 · 등록안과 검증 없음 (2) S2 smoke · 학습 루프 연결 전 (3) RAND smoke · 17j 허용은 GPU 1 · 고정 바이트 (4) v2 기록 · 17k 대기 (5) v6 full · 17l 대기 · 승인 json 대기.
- 놀았던 자원과 시작 시각 (아침 보고용): GPU 1 은 01:16:26 ~ 04:57 (3 시간 41 분) 그리고 04:58 부터 계속 · GPU 0 은 05:46 부터. 이유는 위와 같음 (검증 대기 · 판단 필요).
- 풀리는 순서: ASTRA 17k 가 v2 기록 허용 → GPU 1 v2 짧은 진단 · 17l 이 v6 full 승인 (승인 json) → GPU 1 full 75 · 작업자 B 수정 → lead 재실행 → 17m → RAND smoke. 1043 평가는 팀장이 깨신 뒤 등록안 (CMD-R 규약 교정 결정과 묶임).

## GPU 1 기동 기록 (06:50 · ASTRA 17k v2 조건부 허용 · 17l v6 full 승인)

- **근거:** `VERIFY-astra-17k.md` 5 절 (v2 expect 0 짧은 진단 **한 번**) · `VERIFY-astra-17l.md` 5 절 + 승인 json (`night-tools-20261013/uncr_v6/approval-astra-17l.json` · by ASTRA 17l · 05:56). 둘 다 「기동 직전 수동 확인」 이 조건. 한 번에 하나의 Isaac 만 (GPU 1) · 순서는 v2 먼저 (약 1 분) 그다음 v6 full · RAND smoke 재시도는 17m 대상이라 이번 기동에 포함하지 않음.
- **기동 전 확인 기록 (job tmp `codexw/prelaunch_check_0650.json` · 06:49:35):** 환경 변수 덮어쓰기 0 · GPU 0 UUID `GPU-c08e23b0-...` 여유 16288 MiB (비어 있음) · GPU 1 UUID `GPU-315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f` 총 16303 · 사용 5739 · 여유 10564 MiB (시작 기준 6144 이상) · python · Kit 계산 프로세스 0 (눈에 띄는 것은 `tail -F unseen_driver.log` 10 개 · 계산 아님) · 구형 registry 27/27 로그 존재 · 읽힘 · v3 registry 4/4 · v6 코드 5 개가 17l 사본과 같음 · CE12 12 개가 17k 사본과 같음 · 승인 json 값 · 재검 보고 해시 `ec69b809...` · manifest `91d35be9...` · 새 실행 75 · reuse_partial no 가 현재 파일과 모두 일치 · `out_uncr_v6` 에 STOP · HALT 없음 · v2 체크포인트 `models/foothold-v2.pt` sha256 `e5c21321...`.
- **v2 (17k):** 새 tag · 고정 코드 해시 · dry-run 으로 명령 · expect 0 · 장치 · scan 범위 · 체크포인트 경로와 해시 확인 뒤 같은 인자에서 `--dry_run` 만 빼 한 번 실행 · 성공이면 COLLECTED → CPU `--recompute_action` → A1 ~ A9 승인 → 재확인 · 어디서든 비정상이면 거기서 끝 (자동 재시도 · 다른 모델 · full 로 안 넘어감).
- **v6 full (17l):** `unseen_driver_cmdr_v6.py --stages full,post --manifest all --reuse_partial no --deadline <2026-10-14 09:00 KST epoch> --reval out_uncr_v6/reval/20261014-051704/revalidate.json --approval approval-astra-17l.json`. 마감은 새 시도 기동 마감이지 완료 시각이 아님. 92 · 기타 보호 종료 · 루트 참조 · 공유 오류 · 등록 코드 · 입력 변경 · STOP · 마감 · 자료 invalid 면 추가 기동 없음. 시작 뒤 실제 실행 시간과 여유를 재서 수용량을 추정. GPU guard 99 의 추가 재시도만 코드가 제한한 2 회.
- **하지 않는 것:** 기존 STOP · HALT 를 지우기 · 다른 작업 종료로 조건 만들기 · RAND 와 CE12 · v6 를 동시에 띄우기 · 승인 범위 확대.

## GPU 1 기동 결과 (06:52)

- **v2 expect 0 짧은 진단 (17k 허용 · 06:50:26 ~ 06:50:49): 실행기가 종료 코드 88 로 거절.** tag `v2_native_17k_0650` · attempt `v2_native_17k_0650-20261014-065026-35316` · slot rc 0 · guard rc 0 (min_free 7723 · max_used 8579 MiB) · `usd=[]` (변환 0 = 예상 0 과 일치) · 충돌 없음 · 자식 rc 0 인데 `native.npz` · `meta.json` · `signature.json` 이 없음 (`output_problem`). **원인:** `ce12/dump_native_v2.py:242` `runner.load(ckpt)` 가 `map_location` 없이 읽어 `models/foothold-v2.pt` 의 CUDA 1 번 텐서를 장치 1 개만 보이는 실행에서 복원하지 못함 (`RuntimeError: Attempting to deserialize object on CUDA device 1 but torch.cuda.device_count() is 1`). CPU 시험은 CPU 로 읽어 못 본 결함. 17k 규칙대로 **여기서 끝** (자동 재시도 · 다른 모델 · full 로 안 넘어감 · 원자료 보존). 고치면 `dump_native_v2.py` 바이트가 바뀌므로 17k 허용 밖 → 작업자 B 가 최소 수정 (06:52 · 보관 `ce12/v_17k/` · `codexB3/REPORT.md`) → lead 재실행 → ASTRA 17n → 다시.
- **미경험 v6 full 75 (17l 승인 · 06:51:59 시작):** 기동 직전 확인을 한 번 더 06:51:47 에 반복 (같은 결과 · v2 실행 뒤에도 STOP · HALT 없음 · GPU 1 에 다른 계산 프로세스 없음) · `full_gate_v6.json` 통과 · 첫 실행 `uncr_par_discrete_obstacles_fwd05` 시작. 콘솔 job tmp `codexw/v6_full_console.txt` · 출력 `_eval/out_uncr_v6/` · 마감은 새 시도 기동 마감 09:00 KST. 감시: 보호 오류 (HALT) · FAIL 줄 · 드라이버 종료가 생기면 알림.
- **GPU 0:** 05:46 부터 계속 빔 (허용된 일이 없음 · 위 「GPU 0 이 놀기 시작한 때」). **GPU 1:** 01:16:26 ~ 04:57 · 04:58 ~ 06:50 비었고 06:51:59 부터 v6 full.

## 진행 기록 (07:53)

- **v6 full:** 47 번째 실행까지 전부 종료 코드 0 · 한 실행 약 72 ~ 77 초 · guard 최소 여유 6643 MiB (47 번째까지의 중간 관측 · 75 개 전체 값은 아래 「ASTRA 17o 판정」 절) · HALT · STOP 없음. 남은 약 28 개 · 실측 간격으로 추정하면 08:27 무렵 끝 (보장 아님 · 마감 09:00 은 새 시도 기동 마감).
- **ASTRA 17m (무작위화 v4.1) 07:52 보냄.** lead 재실행: 시험 31/31 · 변이 11/11 (각 항목이 의도한 시험의 AssertionError · import 오류 없음 · 새 변이 5 개가 정적 소스 검사 한 시험에 몰린다는 점을 의뢰문에 알림). 사본 `rand_scenes_v41/` (17ee58ed).
- **작업자 B 의 v2 기록기 수정 (`dump_native_v2.py:242` `runner.load(ckpt, map_location=dev)`):** 07:27 보고. lead 확인: 새 시험 `test_v2_load_device.py` 는 **v2 기록기의 해석기 `isaac311` python 에서는 통과** (CONTROL 로 수정 전 CUDA:1 실패 재현 · PASS) 하고 `isaac311-moects` 에서는 다른 `rsl_rl` (저장소 source) 이 불려 `AttributeError: alg_cfg` 로 실패. 작업자 보고서는 해석기를 `isaac311-moects` 라고 적어 어긋남 (시험은 실제 기록기의 해석기로 돌려야 함). CE12 회귀 (23 · 139 · 24 · 65 · 11) lead 재실행 진행 중. 끝나면 17n.
- **v2 다시 시도:** 17n 허용 + v6 가 끝나 GPU 1 이 비고 + 기동 직전 확인 (17k 5 절) 이 있어야. 그 전에는 안 함.

## v6 full 결과와 RAND smoke 2 기동 기록 (08:31)

- **v6 full 끝 (06:51:59 ~ 08:29:45):** 75 개 실행 모두 종료 코드 0 · 한 실행 guard wall 67.6 ~ 104.9 초 (stepping_stones/fwd10 세 실행은 102 ~ 105 초) · 75 개 guard 를 전부 세면 최소 여유 6505 MiB · 최고 사용 9797 MiB (ASTRA 17o 재계산. 이 줄의 앞 판 6643 · 9659 · 70 ~ 77 초는 틀린 값이었음) · HALT · STOP 없음 · 새 시도 마감 09:00 안. 드라이버 종료 코드 1 은 마지막 후처리의 「새 재검 보고서 파일을 쓰지 못함」 때문: v6 기본 보고서 위치 (`out_uncr_v6/reval`) 가 입력 루트 안이라 재검기가 쓰기를 거절 (작업자 시험은 경로를 작업 폴더로 덮어써 못 봄 · **승인된 v6 코드의 기본 경로 결함**). 후처리가 메모리에서 낸 결과: 32 칸 · 완전 32 · 요청 칸 누락 · 불완전 · invalid · hold · 짝 불일치 0 · 동결 확인 · 옛 묶음 일치 · 표 `UNCR-cells-v6.csv` · `post_v6.json` 은 써짐.
- **lead 가 재검기 v3 명령줄로 새 루트를 읽기 전용으로 다시 검사 (08:30 · 보고서를 루트 밖 `out_uncr_reval/20261014-083045/revalidate.json` 에 씀 · 재검기 코드 수정 없음 · **재계산 작업 폴더를 환경 변수 `UNCR_V6_WORK` 로 `codexw/v6work_new` 에 지정함** (앞 판의 「환경 변수 덮어쓰기 없음」 은 틀린 문장이었음 · 정확한 명령 원문은 기록하지 않아 `--root c:/isaac/ext/go2_rl_robotlab/_eval/out_uncr_v6` · `--out_base out_uncr_reval` · 위 환경 변수로 재구성한 것 · ASTRA 17o 가 이 보고서의 `q_post.recompute_folder` 로 확인):** 실행 75 valid · hold 0 · invalid 0 · 새 칸 25 valid · 불완전 0 · 새 묶음 `9e2f6dba…` (후처리의 값과 같음) · 동결 확인 · 입력 825. 명령줄 종료 코드 1 은 「진단 칸 7 개 없음」 (진단 칸은 옛 묶음에 있고 새 루트에는 없음) 때문으로 **추정** (확인은 ASTRA).
- **RAND smoke 2 (ASTRA 17m 조건부 허용 · v4.1):** 기동 직전 확인 (job tmp `codexw/rand_smoke2_preflight.json` · `prelaunch_check_0833.json` · dry-run `rand_smoke2_dry.txt`): v6 끝 · GPU 1 에 python · Kit 계산 프로세스 없음 · GPU 1 UUID `GPU-315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f` 총 16303 · 사용 5754 · 여유 10549 MiB (하한 4096 · 과거 값 재사용 안 함) · v4.1 8 개 코드 해시 17m 사본과 8/8 같음 · slot · isolate · guard · frame_audit · q_metrics 해시 17m 때와 같음 · E1 체크포인트 `c8951b79…` · train yaml `2ee0009f…` · python 3.11.15 · numpy 1.26.0 (isaac311-moects) · 구형 registry 27/27 · v3 registry 79/79 로그 읽힘 · 상대 실행 프로세스 없음 · 환경 변수 덮어쓰기 0 · STOP · HALT 없음 · v3 registry · 변환 lock · attempt 별 USD 루트 · 변환 예상 1. 명령은 17m 그대로 (`--stop_after_smoke --probe auto --smoke_s 5 --min_free_mib 4096 --deadline <지금 + 20 분>`).

## RAND smoke 2 결과 (08:32)

- **08:31:37 ~ 08:32:01 · run `astra17m-smoke-20261014-083137` · 보호 종료 99 (GPU guard 중단):** S1 a1 에서 guard `stopped=True` · min_free **3374 MiB** (하한 4096 미만) · max_used **12928 MiB** (총 16303) · USD 한 개 (`usd_20261014_083154_7028`) · 충돌 `{}`. 드라이버 `STOP: GPU guard: free memory under the floor ... no retry, no next scene` · 종료 99 (17m: 보호 코드 89 ~ 99 는 다음으로 안 넘김). **이번에는 S1 의 초기화 단언 오류가 아님** (v4.1 의 학습기 초기화는 통과해서 더 진행됨). 원인 (**ASTRA 17o 로 정정**): **GPU 전체 사용량이 중단 시점까지 최고 12,928 MiB 로 올라 여유가 하한 밑으로 내려간 것.** 이 값은 장치 전체 값이라 데스크톱 앱의 몫이 이미 들어 있다. 내가 앞서 「2 환경 12.9 GB + 데스크톱 5.7 GB」 로 더해 쓴 것은 중복 합산으로 틀렸다. 프로세스별 몫과 완료에 필요한 피크는 미확인. S1 의 실제 통과 · S2 · S3 · 영상은 아직 없음.
- **하지 않은 것:** 하한 (`--min_free_mib`) 을 낮추기 · 재시도 · GPU 0 으로 옮기기 · 데스크톱 앱 종료. 하한은 안전 관문이고 (ASTRA: 용량 예측이 아님) GPU 0 은 17m 허용 밖 (렌더는 화면용 GPU 필요 · 메모리 `isaac-render-needs-display-gpu`). 다른 사람의 프로세스는 종료하지 않음.
- **풀어야 할 것 (팀장 · ASTRA 판단):** GPU 1 의 여유를 늘리는 방법 (데스크톱 앱 정리 · 렌더 해상도 · 환경 설정) 과 하한의 근거 재검토 · 또는 GPU 0 에서 렌더가 되는지 실측. 17m 후속 재확인 (17o) 에 이 결과를 넣는다.

## ASTRA 17m 판정과 다음 GPU 1 순서 (08:10)

- **17m (08:07 · RAND v4.1): smoke 한 번만 조건부 허용 · 본 실행 미승인.** 수정이 S1 실패 원인 (환경 1 개에서 teacher 목록이 빔) 을 고쳤다고 확인 (실제 `MoECTS` 클래스로 n=1 실패 · n=2 통과 · 단 n=3, 4, 5 는 teacher 목록이 달라 「2 개 이상이면 항상 [1]」 은 틀림 · 이번 설정은 정확히 2 개). **조건:** (1) v6 의 GPU 1 사용이 끝나고 자식 Isaac 도 종료된 것을 실제 프로세스와 GPU 로 확인 (2) 새 8 개 코드 · slot · isolate · guard · frame_audit · q_metrics · 체크포인트 · train YAML · 실제 자식 python 환경의 해시와 절대 경로 (3) GPU 1 NVML UUID · 총량 · 여유를 새로 읽음 (최소 4096 MiB · 과거 4417 · 4442 MiB 재사용 금지) (4) 상대 실행의 실제 로그가 scan 에 포함되고 읽히고 USD 경로가 풀림 (수동 읽기 필수) · v3 registry · 변환 lock · 새 run_id. 명령: `rand_driver.py --run_id <astra17m-smoke-...> --stop_after_smoke --probe auto --smoke_s 5 --min_free_mib 4096 --deadline <지금 + 20 분>` (`--skip_smoke` · `--probe on` · 무기한 deadline 금지 · S1 은 `tries=2` 로 최대 두 시도 · invocation 하나가 최대 네 native 시도). S1 이 같은 오류로 두 번 실패하면 종료 5 로 멈추고 재시작하지 않음.
- **설명 정정 (17m 2 절):** env 1 은 「teacher 정책을 돌린다」 가 아니라 runner 초기화에 필요한 **보조 환경**이고 두 로봇 모두 student 추론을 쓰며 **평가는 env 0 하나**. 결과 문구는 17m 6 절 문장 그대로. 새 변이 5 개 (M79 ~ M84) 가 한 시험에 몰린다는 lead 설명은 정정됨: M84 는 실제 `eval_env_problems` 를 부르고 나머지 4 개 (M79 · M81 · M82 · M83) 만 문자열 정적 검사. 내가 17m 의뢰문에서 보조 환경을 「teacher」 로 쓴 것이 그 점을 흐렸다.
- **smoke 후 볼 것:** S1 (2 환경 · judged 0 · 보조 1 · state 30 black 주입 뒤 재렌더 회복 · env 0 연속 궤적 · 영상 전체에서 보조 로봇 · 그림자 · 반사 · 카메라 대상 변경 없음 · 1 환경 영상과 이어 붙이지 않음) · S2 (probe 지원 여부와 S1 과 같은 251 상태를 나눠서) · S3 (`FRAME_GATE frame 20` 의도한 재렌더 실패 · 다른 예외를 성공으로 안 셈) · 보조 환경 실제 좌표 · 메모리 최고와 최저 · 시도 시간. smoke 의 세 장면은 교란 없는 base 라 실제 밀기와 마찰 반응은 검증하지 않음.
- **순서:** v6 full 이 끝남 (59/75 · 08:09 · 약 08:30 추정) → v6 자식 종료 확인 → RAND smoke (위 조건) → ASTRA 17n 이 v2 재시도를 허용하면 v2 단회 (17k 5 절 조건 · 새 tag) → 한 번에 하나의 Isaac 으로. 둘은 서로 겹치지 않게.
- **ASTRA 컨텍스트 9 % 남음 (08:09):** 17n 을 보냄 (08:10 · 범위를 좁힘). 재시작은 팀장 승인 (super2) 대기.

## ASTRA 17n 판정과 v2 단회 재시도 기동 기록 (08:51)

- **17n (08:22 판정 · 전문 읽음): 수정 한 줄은 맞다 · v2 짧은 진단 한 번만 조건부 허용.** `dump_native_v2.py:242` `runner.load(ckpt, map_location=dev)` 가 06:50 실패 원인 (CUDA:1 태그 텐서 복원) 에 맞고 `isaac311` 의 실제 러너 (site-packages · 309 행) 와 PyTorch 복원 경로에서 ASTRA 가 재현 (현재 소스 통과 · 이전 소스와 map_location 삭제 변이는 같은 시험에서 의도한 실패). **한계 (그대로 인용):** 새 시험은 CPU 회귀 시험으로는 유효하나 환경 독립 시험이나 GPU 장치 전달 전체 시험으로는 불충분. `map_location="cpu"` 고정 변이가 통과함 (시험이 dev 대입식을 실행하지 않고 AST 존재만 봄). 작업자 보고 정정 셋: (1) 해석기 · 러너 경로 표기가 틀림 (기록기는 `isaac311` · `isaac311-moects` 는 저장소 source 의 다른 러너 152 행) (2) `device_count` 만이 아니라 `is_available=True` 도 모의 (3) dev 대입식을 실행했다는 설명은 틀림. 실제 GPU 로드 · optimizer 복원 · rollout · 기록 저장은 **미확인**.
- **17n 4 절 조건 대조 (job tmp `codexw/prelaunch_v2.py` → `prelaunch_v2_dryA.json` 08:49:43 · dry-run `v2_dry2.txt` 08:50:39 · 모두 읽기만):**
  1. v6 full 끝 08:29:45 (마지막 실행 로그 08:29:26) · RAND smoke 2 끝 08:32:01 · nvidia-smi 의 python · Kit 계산 프로세스 0 · 상대 실행 프로세스 0 (python 4 개는 `awslabs.aws_api_mcp_server` 로 무관) · 구형 registry 27/27 · v3 registry 80/80 로그 존재 · 읽힘 · 마지막 5 개 로그 끝을 직접 읽음 (v6 마지막 실행과 smoke 2 가 정상 종료) · STOP · HALT 없음. 17k 3 절의 깊은 경로 누락: 이번 기동의 상대 실행이 없어 해당 없음 (필수 로그는 자기 로그 `out_ce12/native/<tag>.log` 이고 scan 범위 안).
  2. GPU 1 UUID `GPU-315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f` 총 16303 · 사용 5726 · 여유 10577 MiB (08:49:43) · dry-run preflight 여유 10250 (08:50:39) · 기동 직전에 다시 잼. 06:50 실패 실행의 min_free 7723 · max_used 8579 는 사후 관측이지 정상 rollout 의 상한이 아님. 하한 4096 은 안전 관문이고 피크 보장이 아님. 지난 RAND smoke 2 가 이 관문으로 멈췄으니 이번에도 멈출 수 있고, 그러면 그것도 결과로 적는다.
  3. 기록기 `isaac311` python · 도구 `isaac311-moects` (3.11.15) · 환경 덮어쓰기 0 (python 과 셸 둘 다 확인) · `isaac311` 러너 `Lib/site-packages/rsl_rl/runners/on_policy_runner.py` sha256 `6ffaee7e154a…` (ASTRA 값과 같음) · 저장소 source 러너 `bc79dd286…` 는 다른 파일 (기록기가 안 읽음 · 06:50 로그 310 행이 site-packages).
  4. 새 tag `v2_native_17n_mapfix_20261014_085039` (충돌 0) · 공통 lock `slot/isaac_convert.lock` · v3 registry · attempt 별 USD 루트 · `--expect_conversions 0` · 미래 마감 epoch `1791942639` (10:50:39 · `--deadline 0` 쓰지 않음) · 체크포인트 `models/foothold-v2.pt` sha256 `e5c21321…` (ASTRA 값과 같음). 보호 대조 08:49:58 (`codexw/protect_now_0850.txt`): 달라진 것은 out_uncr_reval (내 새 루트 재검) · slot (registry v3) · out_ce12 (06:50 v2 시도 5 개) · out_rand (smoke 2) · ce12 (작업자 B3 보관 · 새 시험) · out_smoke · eval 맨 위 항목 +1 뿐. out_uncr · out_uncr_v5 · branch · handover · s2 · 동결 py · conda-meta 는 그대로.
  5. **새 코드 묶음 10 파일 (CE12 7 + slot + isolate + guard) 을 기동 전에 고정:** `night-tools-20261013/ce12_mapfix/v2_bundle_17n.sha256` (파일 sha256 `e417dc6fec36…` · 기록기 `251220254fc7…`). A9 가 필수 대조하는 것은 그중 7 (기록기 · adapters · cells · run_dump · slot · isolate · guard). 사후에 결과에 맞춰 다시 만들지 않는다.
- **명령 (17n 4 절 그대로 · dry-run 종료 0 확인 뒤 `--dry_run` 만 뺌 · 한 번):** `isaac311-moects` python `-B ce12/run_dump.py --which v2 --checkpoint models/foothold-v2.pt --tag v2_native_17n_mapfix_20261014_085039 --gpu 1 --min_free_mib 4096 --deadline 1791942639 -- --cells stand,fwd03,yawL05 --envs_per_cell 4 --steps 60 --reset_envs 1,6 --reset_step 30 --switch_env 0 --switch_step 40 --switch_cell fwd03`. 콘솔 `codexw/v2_run2.txt`.
- **끝난 뒤:** 86 · 87 · 88 등 비정상 · 예상 밖 변환 · 장치 불일치 · NaN · 출력 누락 · PENDING 이면 거기서 끝 (자동 재시도 · 다른 모델 · full 로 안 넘어감 · 원자료 보존). 성공이면 run.json · 로그 · slot · guard · isolate · 필수 3 파일 확인 → `validate_dump.py --which v2 --tag <tag> --checkpoint ... --attempt <실제 attempt> --stamp` (COLLECTED) → CPU 에서 `compare_native.py --dump ... --recompute_action --report <새 보고서>` → 같은 대상에 `--approve --compare_report ... --code_bundle <위 묶음>` (A1 ~ A9) → `--check_approval`. COLLECTED 만으로 APPROVED 라 쓰지 않는다. 결과 문구: 평면 3 명령 × 4 환경 × 60 step = 720 env-step 이며 독립 시행 720 회가 아님 · 평면이라 height ray miss 경로 못 봄 · 험지 성능 · 정책 우열 · 이식 동등성을 말하지 않음 · v2 기록의 첫 실제 증거.
- **하지 않는 것:** STOP · HALT 지우기 · 다른 프로세스 종료 · 하한 낮추기 · RAND smoke 와 겹치기 (한 번에 하나) · 실패 원인을 바꿔 가며 반복.

## v2 단회 재시도 결과 (08:54 · 08:52:06 ~ 08:52:23)

- **기록은 성공했고 승인은 A1 에서 거절됐다.** tag `v2_native_17n_mapfix_20261014_085039` · attempt `...-20261014-085206-93076` · 기동 직전 확인 14/14 통과 (`codexw/prelaunch_v2_final.json` 08:51:56 · GPU 1 여유 10573 MiB) · 실행기 rc 0 · slot rc 0 · guard rc 0 (`stopped_by_guard` false · min_free 7697 · max_used 8605 MiB · 74 표본 · 14.8 초) · `usd=[]` (변환 0 = 예상 0) · 충돌 `{}` · 자식 rc 0 · `native.npz` · `meta.json` · `signature.json` 있음 (06:50 의 `output_problem` 해소: `map_location=dev` 수정이 실제 GPU 1 실행에서 통과). 기록기 자체 검사: `obs_cmd_vs_command_max_abs` 0 · `command_vs_schedule_max_abs` 0 · 비유한 값 0 · ray miss 0 · reset 2 · 관측 순서 · 행동 순서 일치 (N 12 · T 60).
- **validate_dump `--stamp` (COLLECTED):** R1 ~ R4 · S1 ~ S11 · G1 · L1 · L2 · N1 · N2 · M1 · M2 전부 PASS (`v2_validate_stamp.txt`).
- **CPU `compare_native.py --recompute_action` (isaac311-moects · `CUDA_VISIBLE_DEVICES=-1`): ALL PASS.** 관측 `obs.policy` max_abs 0 · `joint_target` 0 · 행동 재계산 `max_abs 2.86e-06` (n_bad 0) · 선 높이 격자 `1.49e-08` (`v2_compare.txt` · 보고서 `compare_report_20261014-085309.json`). 여기서 말할 수 있는 것은 CPU 재계산과 GPU 출력의 차이가 2.86e-06 으로 관측됐다는 사실뿐이고, 이 크기가 충분한지는 따로 정한 적이 없다.
- **승인 (`--approve --compare_report ... --code_bundle ce12_mapfix/v2_bundle_17n.sha256`): `REJECTED` · A1 FAIL, A2 ~ A9 PASS** (A9 도 PASS: 기록 당시 코드 7 개가 묶음과 같음). 이어서 한 `--check_approval` 은 `APPROVAL INVALID: approval_stamp.json 없음` (승인 도장이 만들어지지 않았다 = 승인 안 됨). A1 의 실패 문구: `서명이 지금 adapter 와 다름 · 다른 칸 ['signature_sha256', 'source']`.
- **A1 원인 (lead 가 읽기 전용으로 확인 · 고치지 않음):** 기록된 `signature.json` 의 `source."foothold-v2.env.yaml".path` 는 `C:/Users/.../foothold-lab\models\foothold-v2.env.yaml` (슬래시와 역슬래시가 섞임) 이고, 승인기가 지금 다시 만든 서명 (`_sig_now` → `V2Adapter.from_env_yaml`) 의 경로는 `C:/Users/.../foothold-lab/models/foothold-v2.env.yaml` (전부 슬래시). **env.yaml 내용 해시는 두 쪽 모두 `a5ef31d626f8…` 로 같고**, 서명 해시가 경로 문자열을 포함해서 달라진다 (`2f1b0c2b…` 대 `dfc1410f…`). 출처: `dump_native_v2.py:61` 의 기본 `env_yaml = os.path.join(LAB, "models", ...)` 가 Windows 에서 `LAB` 의 슬래시 뒤에 역슬래시를 붙이고, 승인기는 `adapters.V2_ENV_YAML` 상수 (전부 슬래시) 를 쓴다. 합성 시험은 모두 같은 상수를 써서 이 어긋남을 못 봤다 (CTS r2 는 슬래시 상수 경로라 통과). 즉 **자료 문제가 아니라 경로 표기 불일치로 거절하는 관문 문제**로 보이지만, 이 판단 (A1 면제 · 서명 재정의 · 기록기 수정 후 재기록 중 무엇이 맞는가) 은 ASTRA 몫이고 lead 가 서명을 고치거나 승인 도장을 만들지 않는다.
- **17n 규칙대로 거기서 끝:** 자동 재시도 없음 · 다른 모델 · full 로 안 넘어감 · 원자료 보존 (`out_ce12/native/v2_native_17n_mapfix_20261014_085039/`). 같은 코드로 다시 돌려도 같은 A1 거절이므로 의미 없다. 고치면 기록기 또는 서명 정의의 바이트가 바뀌어 17n 허용 밖이고 새 ASTRA 허용이 필요하다.
- **보호 대조 (08:54 · `codexw/protect_now_0854.txt`):** 기동 전 (08:49:58) 과 달라진 것은 `out_ce12` 한 곳뿐 (42 → 52 파일 · 이번 실행의 산출물). 사본 `night-tools-20261013/ce12_mapfix/v2_run_17n/` (스크립트 · 콘솔 · 보고서 · slot · guard · run.json · 해시).
- **미확인 (17n 5 절을 그대로):** 이 한 번으로 말할 수 있는 것은 평면 3 명령 × 4 환경 × 60 step = 720 env-step 의 입출력 정합이다. 독립 시행 720 회가 아니다. 평면이라 height ray miss (+1) 경로를 못 봤다 (ray miss 0). CPU 재계산과 GPU 출력의 오차 2.86e-06 이 충분한지의 tolerance 는 정하지 않았다. 험지 성능 · 정책 우열 · 이식 동등성 · 17k r2 CTS 승인과의 동치는 말하지 않는다. 실제 GPU 장치: `CUDA_VISIBLE_DEVICES=1` · 논리 `cuda:0` · guard 가 GPU 1 에서 최고 8605 MiB (기동 전 약 5.7 GB 에서 약 2.9 GB 늘어남) 를 관측했고 GPU 0 은 15 MiB 로 그대로였다는 정황이지, CUDA 와 Kit 의 물리 UUID 를 직접 대조한 것은 아니다 (Kit 로그에는 06:50 과 같은 `Skipping NVIDIA GPU due CUDA being in bad state` 경고가 있다).
- **GPU 가 놀기 시작한 때 (아침 보고용):** GPU 1 은 08:52:23 부터 빔 (이유: 허용된 다음 일이 없음 · RAND smoke 재시도는 메모리 여유 문제로 ASTRA 판단 대기 · v2 재기록은 고침과 새 허용 필요). GPU 0 은 05:46 부터 계속 빔 (1043 후속 평가 등록안 대기).
- **다음:** 작업자 B 에게 A1 경로 표기 최소 수정 후보와 시험을 맡김 (CPU 만 · 후보일 뿐 채택은 ASTRA) · ASTRA 17o 에 v6 새 자료 · v6 보고서 위치 결함 · RAND smoke 2 · v2 A1 거절을 한 번에 묻는다 (ASTRA 컨텍스트가 9 % 라 한 메시지로).

## ASTRA 17o 판정 (09:15 · 전문 읽음)

- **한 줄:** v6 신규 75 는 정해진 조건의 유효 자료로 쓰되 종료 오류와 옛 진단 출처를 병기 · v2 는 A1 거절 상태 유지 · RAND 는 메모리 원인 설명을 바로잡고 다음 기동 보류.
- **v6 (질문 1):** 신규 75/75 valid · hold · invalid 0 · 25/25 칸 valid · 짝 불일치 0 · 원자료 825 파일에서 상태 · 명령 · 판정 구간 · 초기 궤적 · origins 를 읽고 매 실행의 `q_post` 출력 두 파일을 다시 만들어 원본과 **바이트 대조** · 32 행 CSV 의 n · surv · cross · alive_cross · zone_end 도 일치 · 코드 manifest `91d35be9…` · 승인 재검 `ec69b809…` · 옛 묶음 `e5597517…` · 새 묶음 `9e2f6dba…` (독립 계산도 같음) · 검사 전후 825 파일 해시 불변. **드라이버 rc 1 은 `unseen_driver_cmdr_v6.py:53,543` 의 기본 `ROOT/reval` 과 `uncr_revalidate_v3.py:883` 의 입력 루트 쓰기 금지가 충돌한 것이고 17l 이 `full,post` 를 허용하면서 놓친 결함.** 별도 CLI rc 1 은 재검기 928 줄이 **진단 7 칸의 valid 개수**로 종료 코드를 정하기 때문 (새 루트에 진단 7 칸이 없어 1 · 진단이 충족된 합성 대조군 0 · 동결 실패 대조군 2 를 재현) → 둘 다 자료 실패와 동일시할 수 없고 rc 0 만으로 전체 자료를 승인할 수도 없음. 내 보완 재검은 **사후 보완 증거** (원래 실패 기록이나 승인 json 을 고쳐 성공으로 만들면 안 됨) · 보고서 SHA256 `a760a8f2989f…`. **정정 셋:** (1) 75 개 guard 전체: 최소 여유 6505 MiB · 최고 사용 9797 MiB (극값 `uncr_on_star_fwd10`) · guard wall 67.6 ~ 104.9 초 (내가 쓴 6643 · 9659 · 70 ~ 77 초는 틀림) (2) 「환경 변수 덮어쓰기 없음」 은 사실이 아님 (`UNCR_V6_WORK` 지정) (3) 진단 7 칸은 수집 당시 q_post 해시가 없어 「기존 자료 재사용 · 수집 당시 q_post 해시 미기록 · 현재 재계산 일치」 로 행마다 표시해야 함. 각 실행 로그에 시각 자산 unresolved reference 경고가 남아 있어 valid 는 영상 · 외형 승인을 뜻하지 않음. 범위 문장은 17l 6 절 그대로 + 17o 의 새 문단 (신규 25 조건 x 3 체크포인트 = 75 회 · 각 100 episode · 총 32 조건 · 새 루트만 볼 때의 진단 7 조건 missing 은 기존 자료를 합치지 않은 결과 · 수치는 이 표본의 기술통계). cross 를 네 발 안전 통과나 명령 준수로 읽거나 후진 진단의 양의 x 횡단을 후진 성공률이라 부르면 안 됨.
- **v2 (질문 2):** 경로 구분자 진단은 맞음 (`_sig_now` 와의 재귀 비교 차이가 정확히 `source.foothold-v2.env.yaml.path` 와 `signature_sha256` 둘뿐 · 경로 구분자 하나만 바꿔 해시를 다시 계산하면 서명이 동일). **A1 면제와 원본 서명 덮어쓰기는 불가.** 가장 좁은 수정은 후보 A (기록기 기본 경로만 기존 adapter 상수와 일치) → **17p 로 그 수정과 시험을 확인한 뒤 새 tag 로 단회 기록**. 이번 판정은 새 GPU 기동을 허용하지 않음. 기존 기록 구제는 기술적으로 가능하나 별도 버전 있는 승인 규칙 + 검증 (정상 슬래시 기록과 이번 기록의 동등성 · 다른 파일 · 내용 해시 · 관절 순서 · layout · 척도 · 서명 자기 해시 훼손의 거절 · A2 ~ A9 · CTS r2 회귀) 이 필요하고 아직 구현 · 검증 안 됨. 기록기 v2 만 바꾸면 r2 stamp 의 코드 집합에 직접 닿지 않지만 adapters · validate · compare 까지 바꾸면 r2 도장이 현재 코드에 유효하다고 볼 수 없음. 허용 문구: 「v2 단회 GPU 기록은 수집 관문을 통과했고 CPU 관측 · 행동 재계산도 일치했다. 그러나 서명 경로 표기 불일치로 A1 승인이 거절되어 자료는 COLLECTED 상태다. APPROVED 및 공통 평가 사용 승인에는 이르지 않았다.」 쓰지 말 것: 「v2 승인 완료」 · 「v2 와 CTS 성능 비교 가능」 · 「모든 입력 경로 검증 완료」. CPU 행동 재계산 직접 반복 PASS (8,640 성분 최대 절대오차 `2.86102294921875e-06`).
- **RAND smoke 2 (질문 3):** rc 99 는 보호 중단이며 「S1 같은 초기화 오류 두 번이면 rc 5」 와 다른 경로 · a2 · 다음 장면 · 자동 재기동 불허. **「두 환경 12.9 GB + 데스크톱 5.7 GB」 설명은 틀림 (사용량은 GPU 전체 값이라 중복 합산).** 108 회 관측 중 최소 여유 3,374 MiB · 최대 사용 12,928 MiB · 21.45 초에 하한 위반으로 중단 · 시작 전 여유 10,223 MiB (모두 장치 전체 값). 이번에는 초기화 단언을 넘은 근거가 있음 (a1 `meta.json`: 체크포인트 20,000 로드 · `act_inference` · 환경 2 개 · 평가 env 0 · 보조 env 1 · teacher 입력 변경 및 수동 student 경로 대조 오차 0) 이지만 결과 JSON · 완료 로그 · 영상이 없어 **S1 smoke 통과는 아님**. v2 12 환경 무렌더와 RAND 2 환경 렌더는 조건이 달라 환경 수나 렌더 하나를 원인으로 확정할 대조가 아님. 허용 문구: 「2 환경 렌더 구성을 초기화하고 student 추론 사전 검사를 지난 뒤, GPU 전체 여유가 3,374 MiB 로 떨어져 S1 도중 보호 중단됐다」. 순서 권고 4 단계는 위 「팀장 결정 대기」 의 smoke 항목에 옮겨 둠.
- **내 쪽 조치:** 이 절을 쓰면서 위 정정 셋을 NIGHT-PLAN 해당 줄에 고침 · #550 의 앞 댓글 (6157416630 v6 결과 · 6157432100 인계) 의 같은 문장을 고치고 정정 댓글을 남김 · 아침 페이지 7판의 v6 절 · 무작위화 절 · 결정 목록에 17o 문구를 반영 · 작업자 B 의 후보 수정 (A 우선) 이 오면 17p 로 검증을 의뢰 (GPU 기동은 17p 판정이 새 tag 단회를 허용하고 17n §4 조건을 다시 채운 뒤에만).

## 작업자 B4 후보 수정과 ASTRA 17p 의뢰 (09:27)

- **작업자 B (v2 A1 경로 표기 후보 · 09:22 보고):** 후보 A = `dump_native_v2.py` 의 80 행에 `args.env_yaml = os.path.abspath(args.env_yaml).replace("\\", "/")` 한 줄 추가 (원본 `251220254fc7…` → 후보 `a3da62b8185f…`). 새 시험 `test_v2_signature_path.py` (`f4c7ea4c7dec…`) P1 ~ P4: 수정 전 1/4 · 후 4/4 (두 환경) · 작업자 변이 3/3. 후보 B (adapter 쪽) 는 r2 도장이 가리키는 `code_adapters.py` 까지 건드려 보관만 (코드 조각). 경로 전수에서 A1 과 같은 다른 정확 문자열 불일치는 못 찾음. **r2 도장은 후보와 무관하게 이미 무효** (작업자 격리 사본과 lead 의 실제 `_eval` 확인 모두: 승인 뒤 바뀐 파일 `compare_native` · `validate_dump` · `run_dump`).
- **lead 재실행 (09:23 ~ 09:25 · CPU):** 후보와 운영본의 차이 정확히 한 줄 · 새 시험 isaac311-moects 4/4 · isaac311 4/4 · lead 변이 셋 (삭제 · 방향 거꾸로 · 드라이브 소문자) 3/3 `failed [P1,P2,P3] want [P1,P2,P3]` · 오류 없음 · `test_v2_load_device` isaac311 1/1 · 후보 SHA256SUMS 56/56 일치 · 다른 6 개 코드 파일 운영본과 바이트 같음. **lead 가 다시 돌리지 않은 것:** 기존 회귀 23 · 139 · 24 · 65 · 11 (작업자 로그만 · 후보가 건드린 것이 한 줄뿐). 후보는 **운영 `_eval/ce12` 에 아직 반영하지 않았다** (ASTRA 판정 전).
- **ASTRA 17p 보냄 (09:27 · `TASK-astra-17p-v2-a1path.md`):** (1) 한 줄이 맞고 충분한가 (2) 새 시험이 믿을 만한가 (3) 운영 채택 순서 (보관 `ce12/v_17n/` → 한 줄 반영 → 새 10 파일 묶음 고정) (4) 새 tag 단회 기록 허용 여부와 조건 (5) 설계 권고만: GPU 0 이 05:46 부터 비어 있는 1043 평가 (v6 드라이버의 `unseen_driver_cmdr_v6.py:92` 1042 하드코딩 · 승인 json 도 1042 의 75 실행에 묶임). 사본 `night-tools-20261013/ce12_a1path/` (9d824e6b).
- **GPU:** 두 장 모두 비어 있음 (GPU 1 08:52:23 부터 · GPU 0 05:46 부터). 17p 허용 전에는 기동 없음.

## ASTRA 17p 판정과 v2 새 tag 단회 기록 기동 기록 (09:39)

- **17p (09:38 · 전문 읽음): 후보 A (한 줄) 채택과 새 tag 의 v2 단회 기록을 아래 기동 전 조건을 충족할 때만 허용 · 기존 CTS r2 승인 복구와 1043 평가 기동은 별도 판정.** 한 줄은 해당 기본 경로에 유효 (허용 범위는 CE12_* 시험 변수 없이 기본 env.yaml 을 쓰는 이번 단회 · Windows 의 모든 동등 경로 일반 정규화로 확대 안 함 · `c:/` 소문자 드라이브는 여전히 A1 기준과 다름) · 실제 A1 · A4 · A6 함수에 새 서명 · 환경 경로를 넣어 PASS (CPU fixture · 새 GPU 기록의 APPROVED 는 아님) · P1 ~ P4 는 경로 문자열과 서명 생성 회귀 시험으로만 유효 (실행 흐름 전체 시험이 아님) · **시험의 실제 허점:** 정규화 대입을 `if False:` 안으로 옮겨도 P1 ~ P4 전부 PASS (AST 로 식을 찾기만 해서 실행 여부 · 순서를 모름) → 이 시험을 배포 관문으로 쓰려면 최상위 위치 · parse_args 이후 · 최초 소비 이전 조건도 검사해야 함 (이번 후보는 ASTRA 가 위치를 직접 확인) · 시험은 `codexB4/fixture_real` 과 고정 경로에 의존해 저장소 사본만으로 재현 가능한 정본은 아직 아님 (fixture 목록 · 해시 · 보관 위치 · 실행 방법을 남길 일) · r2 도장은 후보와 무관하게 이미 INVALID (ASTRA 도 읽기 전용 재현). **17p 가 쓰라고 한 성공 문구 (전부 통과한 뒤에만):** 「새 v2 단회 기록은 COLLECTED, CPU 관측 · 행동 대조, A1 ~ A9 및 승인 도장 재검을 통과했다. 승인 범위는 고정된 평지 세 명령과 reset · 전환 fixture다.」 (ray miss 가 여전히 0 이면 그 경로 미확인을 이어 적음). 쓰면 안 되는 문구: 「CE12 전체 완료」 · 「CTS 와 공통 성능 비교 승인」 · 「미경험 험지 성능 검증」.
- **채택 (09:38:35 · 17p 3 절 순서 그대로):** 채택 직전 운영 `ce12/dump_native_v2.py` 해시 `251220254fc7…` 확인 · 상대 recorder 프로세스 없음 (python · Kit 계산 프로세스 0) · `ce12/v_17n/` 에 그 바이트만 보관 (`251220254fc7…` 일치 · 보관 폴더가 이미 있으면 덮지 않는 조건으로 새로 만듦) · 작업자 후보 (`codexB4/ce12_candidate/dump_native_v2.py`) 한 파일만 복사해 `a3da62b8185f…` 확인 · 나머지 코드 9 개는 17n 묶음 해시와 같음 (후보 폴더 56 개를 통째로 복사하지 않음).
- **새 10 파일 코드 묶음 (기동 전 고정 · 17n 묶음은 그대로 둠):** `night-tools-20261013/ce12_a1path/v2_bundle_17p.sha256` (파일 sha256 `46fc5d315699…`). 17n 묶음과 다른 항목은 `ce12/dump_native_v2.py` 하나 (`251220254fc7…` → `a3da62b8185f…`). A9 가 필수 대조하는 것은 그중 7.
- **기동 전 확인 (job tmp `codexw/prelaunch_v2b_dry.json` 09:38:59 · dry-run `v2b_dry.txt` 09:39:13):** 환경 덮어쓰기 0 (python 과 셸) · GPU 1 UUID `GPU-315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f` 총 16303 · 사용 5686 · 여유 10617 MiB (dry-run preflight 여유 10282 · 기동 직전 한 번 더 잼) · GPU 0 비어 있음 · python · Kit 계산 프로세스 0 · 상대 실행 프로세스 0 (python 4 개는 aws mcp 서버) · 구형 registry 27/27 · v3 registry 80/80 읽힘 · `v2_native_17n_mapfix` 이후 새 실행 없음 · STOP · HALT 없음 · 새 tag `v2_native_a1path_20261014_093859` (충돌 0) · 체크포인트 `models/foothold-v2.pt` sha256 `e5c21321…` · `isaac311` 러너 `6ffaee7e154a…` · 기록기 `isaac311` · 도구 `isaac311-moects` · 공통 `slot/isaac_convert.lock` · v3 registry · attempt 별 USD 루트 · `--expect_conversions 0` · 미래 마감 `1791945539` (11:38:59 · `--deadline 0` 쓰지 않음) · 보호 대조는 기동 직후 `protect.sh`. super2 의 RL 백업 마무리 회차는 09:20 에 끝남 (mai-os#34 · 새 파일은 다음 회차가 가져감).
- **명령 (17p 4 절 그대로 · dry-run 종료 0 확인 뒤 `--dry_run` 만 뺌 · 한 번):** `isaac311-moects` python `-B ce12/run_dump.py --which v2 --checkpoint models/foothold-v2.pt --tag v2_native_a1path_20261014_093859 --gpu 1 --min_free_mib 4096 --deadline 1791945539 -- --cells stand,fwd03,yawL05 --envs_per_cell 4 --steps 60 --reset_envs 1,6 --reset_step 30 --switch_env 0 --switch_step 40 --switch_cell fwd03`. 콘솔 `codexw/v2b_run.txt`. 이어서 `--stamp` → CPU `compare_native --recompute_action` → `--approve --compare_report ... --code_bundle v2_bundle_17p.sha256` → `--check_approval` (중간 단계를 건너뛰지 않음 · A1 재거절 · 다른 검사 실패 · PENDING · 보호 중단이면 거기서 끝 · 다른 후보 · 면제 · 반복 · full 로 안 감 · 08:52 거절 기록 보존).
- **17p 5 절 (1043 평가 최소 설계 · 기동 허용 아님):** 목표 세 칸은 **평지 stop03 · fwd01 · fwd02** (ASTRA 17 3.2 ~ 4 절 · 16 1 절) 이고 UNCR 에서 on 이 잘 나온 지형으로 바꾸면 다른 실험. v6 의 입력 경로 하나만 인자화해서는 부족 (driver · 재검기 · 집계가 1042 MODELS · checkpoint · 등록 해시 · 옛 자료 재사용 · CUDA 가림 · GPU 1 고정에 묶임 → 새 판 + 새 승인 · 1042 등록 해시 완화 금지 · 별도 출력 · 보고 · 작업 루트 · 기존 post 저장 경로 결함 제거 · GPU 인자를 물리 장치 하나로). 목표 세 칸은 기존 CMD-R 수집 · 집계 규약 (평가 seed 1000 ~ 1004 · 각 100 쌍 · 세 칸 모두 짝 95 % 구간 하한 > 0 · 동일 가중 평균 ≥ +10 %p · 부모 대비 손실 별도 표시) 을 유지. 지형 재현 · 회귀 후보 (1042 결과를 보고 고른 것이라 선택 경위를 기록하고 1043 결과 전에 고정): `floating_ring` 전진 0.5 (alive_cross 69 / 45 / 91) · `rails` 전진 0.3 (67 / 38 / 72) · `gap` 전진 0.3 (surv 37 / 16 / 9). 합격 / 퇴행 이분 판정은 결과 전에 별도 확정해야 하고 90 % · 95 % · +10 %p 를 지형에 이식하지 않음. 학습 시드 둘을 episode 1,000 개로 합쳐 일반 효과라고 쓰지 않음. **lead 가 지금 준비할 수 있는 것** (팀장의 「CMD-R 규약 교정」 결정을 바꾸지 않는 것): manifest · 입력 해시 · 현재 시험 규약 · 실패 fixture · 예상 실행 수와 시간 · 별도 출력 경로. 규약 교정의 의미 · 부모 승격 · 위험 허용선 · GPU 배정과 기동은 팀장 결정.

## v2 새 tag 단회 기록 결과 (09:42 · 09:40:19 ~ 09:40:37)

- **기록 성공 · 승인 통과 (A1 ~ A9 · 도장 재확인 유효).** tag `v2_native_a1path_20261014_093859` · attempt `...-20261014-094020-150232` · 기동 직전 확인 15/15 (`codexw/prelaunch_v2b_final.json` 09:40:08 · GPU 1 여유 10581 MiB) · 실행기 · slot · guard rc 0 (`stopped_by_guard` false · min_free 7698 · max_used 8604 MiB · 76 표본 · 15.2 초) · `usd=[]` (변환 0 = 예상 0) · 충돌 `{}` · 자식 rc 0 · 필수 세 파일 있음 · Traceback 0 · 기록기 자체 검사: obs 와 명령 차 0 · 명령과 일정 차 0 · 비유한 값 0 · ray miss 0 · reset 2 · 관측 · 행동 순서 일치 (N 12 · T 60).
- **단계별 (중간 단계를 건너뛰지 않음):** `validate_dump --stamp` COLLECTED (22 PASS) → CPU `compare_native --recompute_action` ALL PASS (16 PASS · 행동 재계산 max_abs `2.86e-06` · 보고서 `compare_report_20261014-094103.json`) → `--approve --compare_report ... --code_bundle ce12_a1path/v2_bundle_17p.sha256`: **A1 ~ A9 모두 PASS · `APPROVED`** (이번 서명 경로가 슬래시로 기록돼 A1 의 정확 비교 통과 · 서명 해시 `dfc1410feaa6…` = 승인기가 다시 만든 값) → `--check_approval` **`APPROVAL STILL VALID`**. coverage: reset 2 · reset 뒤 action 60 · 명령 전환 1 · 전환 뒤 action 20 · **ray miss 0 (height miss +1 경로 미확인)**.
- **재현 관찰:** 08:52 기록과 09:40 기록의 `native.npz` 는 **SHA256 이 같다** (`c9a87ea527d4…`). 같은 컴퓨터 · 같은 GPU 에서 한 줄 수정 전후로 데이터가 바이트까지 같았다는 사실이고 다른 장비 · 다른 GPU 의 재현은 말하지 않는다 (미확인). `meta.json` · `signature.json` 은 경로 표기 한 곳 (env_yaml) 이 달라 다름.
- **보호 대조 (09:42 · `codexw/protect_now_0942.txt`):** 기동 전 (08:54) 과 달라진 것은 `out_ce12` (새 실행 산출물 11 개) 와 `ce12` (보관 폴더 `v_17n/dump_native_v2.py` 1 개) 뿐. 사본 `night-tools-20261013/ce12_a1path/v2_run_17p/`.
- **17p 가 허용한 말 · 금지한 말 (그대로):** 「새 v2 단회 기록은 COLLECTED, CPU 관측 · 행동 대조, A1 ~ A9 및 승인 도장 재검을 통과했다. 승인 범위는 고정된 평지 세 명령과 reset · 전환 fixture다.」 + ray miss 0 이므로 그 경로 미확인. 쓰면 안 되는 말: 「CE12 전체 완료」 · 「CTS 와 공통 성능 비교 승인」 · 「미경험 험지 성능 검증」 (기존 CTS r2 는 INVALID 상태).
- **남은 것:** 기존 CTS r2 승인 복구는 이번 허용에 포함되지 않음 (별도 판정 필요) · 새 시험 `test_v2_signature_path.py` 는 fixture 의존이라 저장소 사본만으로 재현 가능한 정본이 아님 (fixture 목록 · 해시 · 보관 위치 · 실행 방법을 남길 일) · 이 시험을 배포 관문으로 쓰려면 정규화 대입이 최상위 · parse_args 뒤 · 최초 소비 앞에 있는지도 검사해야 함 (ASTRA 17p 가 `if False:` 변이로 재현).
- **GPU:** GPU 1 은 09:40:37 부터 다시 빔 · GPU 0 은 05:46 부터 빔. 허용된 다음 기동 없음 (RAND smoke · 1043 평가 · CTS r2 재승인은 모두 별도 판정 · 팀장 결정 대기).

## 아침 보고 게시 (09:53)

- **페이지 7판 게시:** https://claude.ai/artifact/BYuAVDuVJuRWVkAs5mGJSN (버전 21 · version id `1791939069-24de` · 공개 범위는 그대로 「링크가 있는 누구나」 · 내가 바꾸지 않음). 이번 판은 텍스트 절만 바뀌어 영상 · 포스터 참조 54 개가 6판과 같음 (파일은 그대로 유지). 게시된 `index.html` 은 플랫폼이 머리를 감싸 로컬 빌드보다 370 바이트 큼 (sha256 `971037ba…` · 로컬 `8bbdd17e…`) · **게시본을 내려받아** 1920 / 1366 / 390 x 라이트 / 다크로 렌더 확인: 가로 넘침 0 · 본문 배경 라이트 `rgb(246,245,241)` · 다크 `rgb(18,22,29)` · 절 높이가 로컬 빌드와 같음. 표는 좁은 폭에서 `.tbl` 안 가로 스크롤 (설계). 새 영상이 없어 영상 전 프레임 검수는 이번 판에 해당 없음 (참조 영상 목록 · 파일은 6판과 같고 이전 검수 기록 그대로).
- **이슈 보고:** #546 에 아침 보고 댓글 (6158413103) · #550 에는 v2 승인 (6158284475) · 17o 정정 (6157984764) · v2 거절 (6157743670). 채팅 보고는 이 줄 뒤 마지막 턴에 한국어로.
- **정정 반영 확인:** 페이지 · 이슈 · NIGHT-PLAN 에서 「12.9 GB + 5.7 GB」 · 「6643 / 9659」 · 「환경 변수 덮어쓰기 없음」 이 남아 있지 않음 (페이지 본문 grep 0).
- **작업자 D (1043 평가 설계 메모 · `term_a29c03e2`):** 09:45 접수 · 읽기와 메모만 · `_eval` 에 파일을 만들지 않음 · 보고는 `codexD/MEMO.md` 와 #550 요약 댓글.

## 작업자 D 의 1043 평가 설계 메모와 ASTRA 17q 의뢰 (09:56)

- **작업자 D (`term_a29c03e2` · 09:45 접수 · 09:51 끝 · 컨텍스트 36 % 남음):** `codexD/MEMO.md` (사본 `night-tools-20261013/cmdr1043_eval_design/MEMO-codexD.md`) · `_eval` 에 만든 파일 0 개 · #550 댓글 6158385893. **권고 (가):** v37 동결 + 새 1043 전용 드라이버 + post v10 새 판이 같은 등록 manifest 를 읽음 (구성: 새 드라이버 → slot v3 → gpu_guard → isolate v3 → `q_eval_cmdr.py`). 1042 결박 전수 표 (v37 1~156 · 175~184 · 213 · 197~223 · 269~279 · 295~321 · 442~469 · 501~505 · 557~643 · 690~795 · 842~925 · 989~1043 · 1046~1390, post 123~131 · 189~207 · 225~339 · 700 · 713~755): 한 곳만 바꾸면 조용히 1042 자료를 읽거나 덮음 (`q()` 가 `--outdir` 를 안 넘김 · v37 의 자체 변환 lock · `PARTICIPANT` / `SELF_PATH` · `training_done()` 이 on 군만 봄 · post 표 제목이 아직 v8). 실제 1043 입력 읽기: 부모 `c8951b79…` 두 군 같음 · seed 1043 · 8192 환경 · 4000 update · `where=end` · `label_next=24000` · 22000 · 24000 해시는 메모 표 · 1043 용 번들 비교 보고서는 아직 없음.
- **견적 (작업자 · 읽은 1042 로그 기준):** v37 base = 5 모델 x 111 칸 = **555 run** (1042 평가는 445 재사용 · 새 실행 110 · guard try 평균 75.3 초). 외삽: **목표 전용 3 모델 x 3 칸 x 5 seed = 45 run ≈ 56 분** · 전체 555 run ≈ 11 시간 36 분 (GPU 1 관측의 환산 · GPU 0 은 미측정 · 시작 시험 · 대기 · 재시도 별도). 준비 8.5~16 시간 (작성 4~7 + 합성 시험 2~3 + 변이 1~2 + ASTRA 1~3 + 기동 전 0.5~1 · 코드 쓰기 전 계획 수치). 판정 규약: 목표 세 칸 각 500 쌍 · 구간 하한 > 0 · 세 칸 동일 가중 평균 ≥ +10 %p 가 모두 참이어야 `개선` (post v10 431~479 · 501~565).
- **lead 판단:** 메모의 범위 (45 run 먼저 · 555 run 은 뒤) 와 두 길 (가 · 나) · 작업자 D 에게 2 단계 (코드 · 합성 시험 · 변이 시험 · CPU 전용) 를 지금 맡겨도 되는지는 내가 혼자 정하지 않고 **ASTRA 17q (09:55 보냄 · `TASK-astra-17q-1043-eval-design.md`)** 에 물었다. 대기 동안 새 코드는 쓰지 않는다 (판정이 범위를 바꿀 수 있음). GPU 는 둘 다 비어 있음.

## ASTRA 17q 판정과 작업자 E 의 새 판 제작 (10:15)

- **17q (10:13 · 전문 읽음): (가) 의 새 판 CPU 제작을 권고하되 비교기의 seed 고정 · A/B 자료 소유권 · reset 명세 · Isaac 직렬 실행 계약을 먼저 고쳐야 함 · GPU 기동 승인이 아님.** 메모의 코드 해시 12 개 재계산 일치 · 1042 결박 목록의 주요 지적 (`q()` 가 `--outdir` 안 넘김 · v37 자체 변환 lock · 파일명 / 경로 자기 식별 · on 군만 보는 완료 검사 · post 제목은 713 이 아니라 **711 행**) 은 맞지만 전수 목록은 아님. **가장 큰 누락 = 비교기 자체:** `cmdr_bundle_compare.py:18~20,36~44,93` 가 기대 seed 1042 를 고정해서 실제 1043 입력은 양 군 seed 오류 두 개만으로 `DIFFERENT, rc 1` (자료 불일치가 아니라 도구 계약 불일치 · seed 검사 삭제나 1042/1043 동시 허용으로 풀면 안 됨 · 새 비교기가 등록 manifest 를 읽어야 함). 또 post 가 같은 태그를 두 로그에서 거절하고 태그를 `접두_모델_나머지` 로 파싱하므로 접두에 밑줄을 넣으면 모델 해석이 바뀜 · 새 pin 목록 · v3.2 재사용을 새 승인으로 계승하면 안 됨. **(가) 를 택하되** 「manifest 검증 함수만 새 코드」 라는 예상은 틀림 (slot 이관 · 단계별 자료 소유권 · 비교기 seed · 승인 / 출처 연결은 실질적 동작 변경). 변경을 ① manifest / 경로 ② 기동 관문 ③ 출처 / 단계 전환 ④ 판정 / 표시 로 나눈 diff · 함수 목록 · 가져오지 않는 기능과 이유를 제출할 것.
- **범위 (17q 3 절):** 원본 `jobs()` · `screen_universe()` 를 CPU 에서 분리 실행해 base 555 · **A 45 (부모 포함 45 회 모두 유효해야 A 완료)** · B 의 남은 base 510 · 추가 선별 대상 96 칸 · 최대 추가 768 run (24,000 off/on 에만 적용). **결과 전에 A 와 B 를 함께 등록하면 타당한 단계화** (A 만 끝낸 것은 17 의 전체 요구 완료가 아님 · 문구: 「학습 seed 1043 의 평지 목표 세 칸, 24,000 on−off 결합 판정. 부모 대비 별도 표시. 회귀 범위 3/99 칸 측정, 나머지 96 칸 및 22,000 미평가」 · 「퇴행 99 칸 미평가」 는 목표 3 칸도 99 칸에 포함되므로 틀림). A 를 좋게 보고 B 를 생략하거나 나쁘게 보고 다른 지형으로 바꾸는 선택은 불허. 목표 추가 seed 1001 ~ 1004 는 빼면 안 되고 뺄 수 있는 것은 B 의 퇴행 선별 확장뿐. A → B 재사용은 동일 입력 · 코드 · 장치 · 규약 · 짝 · 출처 재검 조건부 (최소안: 같은 base 로그의 다음 attempt 에서 A 를 재검해 555 로 확장 · A 시점 보고는 불변 사본). 첫 배포는 A 45 회만 기동 가능 · B / remeasure 는 명시적 비활성.
- **reset 정정:** q 평가기는 원점에 정확히 놓지 않음: 지형 원점 주변 **XY ±0.5 m · Z +0~0.2 m** · 관절 기본 자세 · 몸체 속도 0 · 명령별 고정 yaw (`q_eval_cmdr.py:142~154,242~247,332~386`). 「무작위화 없는 중앙 시작」 으로 구현하면 다른 시험 (ASTRA 17p 의 문구도 이 값까지 적어야 했음). env.yaml 은 현재 설정과 비교용이며 설정 전체를 복원하지 않음 (YAML 해시만으로 동일성 주장 금지).
- **GPU 0 · 직렬 실행 (17q 5 절):** GPU 0 에서 평지 평가가 가능했던 **제한된 과거 기록**은 있음 (`out/cq_test_*g0*` · 부모 flat/stop03 · 100 환경 · 50.9 초 · 최소 여유 12,917 MiB · 최대 사용 3,385 MiB · 110 환경 smoke 81.4 초). 그러나 현재 1043 기동 가능성과 전체 555 회 처리량의 근거는 아님 (`cmdr_eval_driver_g0.json` 의 16 개는 전부 재사용). 4,096 MiB 는 중단용 하한으로 유지하되 「16 GB 이고 15 MiB 만 쓰니 충분」 은 틀린 논증 (장치 전체 값 · 새 실행 peak 없음 · guard 는 자식을 먼저 띄운 뒤 샘플링). **slot v3 는 변환 직렬화일 뿐** (`isaac_slot_v3.py:483~505` 는 장면 생성 뒤 잠금을 풀고 자식은 계속 실행) → 양 GPU 에 Isaac 하나를 보장하려면 기동부터 자식 트리 종료까지 보유하는 별도 **실행 lease** (변환 잠금과 역할 · 획득 순서 분리) 가 필요.
- **견적 (17q 7 절):** 8.5 ~ 16 시간은 산술상 맞지만 검증된 납기 범위가 아님. 평균 75.3 초는 guard 호출을 감싼 기록이라 GPU 계산 시간만의 값이 아님 · A 56 분 · base 11 시간 36 분 · 최대 768 추가까지 고유 1,323 회면 같은 환산 약 27 시간 40 분 (시작 시험 · 대기 · 재시도 별도). **GPU 알려진 답 / 물리 버퍼 대조는 CPU 시험 2 ~ 3 시간에 끝나는 항목이 아님.**
- **결정 권한 (17q 6 절):** CMD-R reset 의미 · 채택 / 부모 승격 · 범위 축소 · 위험 허용선 변경 · GPU 배정 · 마감 · UNCR 이분 판정은 팀장 결정. 기존 규약을 보존하는 **별도 CPU 구현 · 시험 준비는 진행 가능** (운영 코드 교체 · GPU · 유료 · 한도 확대 권한은 생기지 않음).
- **작업자 E 접수 (`term_40bccb75` · 10:15 · 신규 sol 세션):** `TASK-codex-worker-1043-eval-build.md` · 작업 폴더 `codexE/` · `_eval` 은 읽기만 · CPU 전용 · 1 단계 (manifest + 새 비교기) 가 끝나면 `STAGE1-DONE.md` · 끝나면 `REPORT.md` 와 #550 요약 · 모자라면 `HANDOFF.md`. 작업자 D 는 컨텍스트 약 36 % 라 이 일에 쓰지 않음 (새 세션이 더 안전). **GPU 는 둘 다 비어 있음 · 이 작업 끝 → lead 재실행 → ASTRA 새 판 검증 → 새 승인 → 팀장 GPU 배정 확인 전에는 기동 없음.**

## 작업자 E 의 1043 평가 새 판 후보와 ASTRA 17r 의뢰 (11:50)

- **작업자 E (`term_40bccb75` · 10:15 접수):** 1 단계 (manifest + 새 비교기) 에서 10:26 에 스스로 멈춰 (HANDOFF · 컨텍스트 43 % 남음 · 「모자라면 중단」 을 너무 일찍 적용) lead 가 10:28 에 계속하라고 다시 지시 → **10:55 에 CPU 후보 완성 (약 40 분 · 17q 견적 8.5 ~ 16 시간 중 작성 · 시험 부분)**: `manifest_s1043.json` (계약 해시 `1cbfb526b745…`) · `s1043_manifest.py` · `cmdr_bundle_compare_s1043.py` · `cmdr_eval_driver_s1043.py` (v37 `c351fde3…` 기준) · `frozen_exec_s1043.py` · `cmdr_post_s1043.py` (post v10 `dea9ca7b…` 기준) · 시험 · 변이 · `CHANGES-driver.md` · `CHANGES-post.md` · `GPU-PLAN.md`. A 45 회만 허용 · B / remeasure 는 rc 8 · 미정 값은 `UNDECIDED` 로 기동 거절 (rc 4). 작업자 시험: 통합 33/33 · 복사본 전체 입력 9/9 · 비교기 5/5 · 드라이버 5/5. **`_eval` 에 만든 · 고친 파일 0 개** (작업자 보고). #550 댓글 6158817384 · 6159198847.
- **lead 재실행 (11:02 · run-id `lead1` · CPU · isaac311-moects):** `test_manifest` PASS (555/45/510/96/768 · 기동 거절 이유 15 개) · `test_stage1` 5/5 · `test_driver_cpu` 5/5 · `test_full_inputs_copy` 9/9 · `test_integration_s1043` 33/33 (변이 6 개 각각 got CAUGHT want CAUGHT) · 모두 종료 0. **하지 않은 것:** 후보 코드 줄 단위 검토 · 변이가 의도한 검사만 끈 것인지 코드 대조 · 실제 slot v3 · guard · isolate 연쇄 (GPU). 사본 `night-tools-20261013/cmdr1043_eval_cand/` (SHA256SUMS · lead_rerun).
- **ASTRA 17r 보냄 (11:49 · `TASK-astra-17r-1043-eval-candidate.md`):** 17q 필수 수정 4 건 (비교기 seed · A/B 소유권 · reset 명세 · Isaac 직렬) 이 코드에서 닫혔는지 · 숨은 1042 결박 · 평가기 인자 의미 · 시험 신뢰 범위 (실제 CLI 경로 · v10 대조 · 변이 6 개 vs 요구 반례) · `UNDECIDED` 중 lead 가 측정해 채울 것 / 팀장 결정 / ASTRA 승인 · 운영 반영 순서와 GPU 0 알려진 답 첫 걸음 허용 여부 · 남은 시간 견적. **GPU 는 둘 다 비어 있음 (GPU 1 09:40:37 부터 · GPU 0 05:46 부터).**

## ASTRA 17r 판정과 작업자 E 의 고침 라운드 (12:12)

- **17r (12:11 · 전문 읽음): 고칠 것 · 현 판의 운영 기동 보류.** 의뢰의 6 개 해시 일치 · 등록 입력 38 개 해시 일치 · 감사 전후 변경 없음 · 시험 통과 수는 재현됨. 그러나 **「모든 반례가 실제 기동 CLI 를 탔다」 는 해석은 틀림**: 드라이버 5 중 넷은 CLI · 다섯째 q 인자 검사는 import 후 함수 호출 · 전체 입력 9/9 는 `check_inputs/launch_errors` 직접 호출 · `on_only_complete` 는 실제로 부모만 지운 자료 · v2 registry / 별도 lock 시험은 문자열 필드를 바꿔 `--cpu_plan` 만 거절시킨 것 · slot 이후 변경 시험은 slot 을 안 띄움. 변이 6 곳은 유효하나 12 개 mutant 파일은 두 차례 생성물이지 12 종이 아님.
- **17q 필수 수정 4 건:** 비교기 seed 결박은 **해결** (실제 1043 번들 `SAME`, 1042 주입 `DIFFERENT`) · A 한정 소유권 · B / remeasure rc 8 은 구현 (단 B 는 구현 완료가 아님: B 확장 때 A 원출처 보존 재검 · 이주 절차 필요) · **reset 은 명세가 q 소스와 맞지만 D 가 대조 · 전달하지 않음** (명세 XY 를 ±9 m 로 바꿔도 통과) · **직렬 실행은 안 닫힘** (lease 는 직접 자식만 기다림: wrapper 만 먼저 끝나고 손자가 살아 있어도 해제됨).
- **P1 (CPU 에서 먼저 고칠 결함):** (1) M `135~145` `0 == False` 로 숫자 GPU 0 이 `gpu_index undecided` 로 거절 (GPU 1 은 오류 0) (2) D `1046` smoke 뒤 `HERE/q_eval.py` 해시에서 `FileNotFoundError` (3) F `95~98` 모든 태그에 `_s` 를 요구해서 시작 시험 태그 네 개 (`ka_orig` · `ka_copy` · `ka_copy_default_buffers` · `branch_on24000`) 가 `92/tag grammar` (4) M `138~178` 타입 검사 누락 (`candidate_hashes="yes"` 도 통과) · 기존 승인 파일을 둔 채 마감 · 위험 한도를 바꿔도 통과 (승인이 과학 계약만 묶고 코드 해시 · 실행 결정을 안 묶음 · v6 의 외부 digest 방식을 계승하지 않음) (5) lock 분리가 문자열 비교뿐 (대소문자만 다른 같은 파일 통과) (6) F `74~110` 첫 옵션값으로 검사하지만 argparse 는 마지막 값 적용 (`--outdir …/_eval/out` 을 뒤에 붙여도 통과). 추가: P `361~364` 가 논리 / 물리 장치 혼동 (`CUDA_VISIBLE_DEVICES=1` 이어도 자식 논리 장치는 0) · D `340~357` 이 다른 root 로그를 자기 OUT 에서 해석 · D `678~729` 가 USD 경로를 끝의 날짜 · 시각 · 난수로만 비교 · manifest 의 `missing_nonfinite` 와 P 의 지표별 유효성 불일치 (MAE 를 NaN 으로 만든 자료가 `45 valid / a_complete=true`).
- **정상 확인:** 부모 / off / on x noise on / off 의 q 인자 6 건을 원본 v37 builder 와 실제 q argparse 기본값으로 대조해 의도한 outdir 변경 외 의미가 같음 · `training_done()` 이 양 군을 봄 · P 의 옛 출력 · hold 환경 변수 우회 거절 · 현 A 경로가 1042 결과를 읽는 분기는 못 찾음.
- **UNDECIDED 구분:** lead 가 측정 (물리 UUID · index · 여유 · 해석기 / NumPy / torch / Isaac 판 · 코드 · 원자료 해시 · canonical lock / registry 경로) · 팀장 결정 (GPU 배정 · 독점 실행 범위 · 마감 · 위험 한도 · 중단 / 재시도 예산 · 「CMD-R 규약 교정」 의 연구 질문과 허용 해석) · ASTRA 판정 (수정된 정확한 코드 · 계약 · 시험 증거에 대한 제한된 기술 허용 · 현재 코드는 `stage=A` 승인만 받음 → **진단 승인과 A 본 수집 승인을 분리**). **순서:** 연구 질문 · 중단 규칙 확정 → 경로 · 공통 lease · 런타임 측정 → 후보 수정 · CPU 반례 재검 → **진단 범위 승인** · 기동 직전 측정 → GPU 알려진 답 → **A 별도 승인.** 과학 계약 · 선별 / 결합 기준은 결과를 보기 전에 고정.
- **운영 반영 (5 절):** 새 파일 추가 · 구판 보존은 맞지만 지금 파일을 `_eval` 에 그대로 복사하면 `ROOT=parents[1]` 와 자기 경로 검사가 `ROOT/cand/파일명` 배치를 요구해 실패 → 배치 구조 · 격리 출력 · 공통 lock 허용 경로를 manifest 로 확정. **첫 GPU 0 은 「진단만」 (별도 승인):** 부모 flat stop03 · seed 1000 · 100 episodes 로 q 원본 · q_cmdr 작은 버퍼 · q_cmdr 기본 버퍼를 같은 조건에서 각각 (Isaac 한 번이 아니라 세 번). 현재 D 는 시작 시험 뒤 자동으로 A 로 진행하므로 「진단만」 모드를 새로 만들어야 함.
- **견적 (17r 6 절):** 40 분은 작성의 자기 보고일 뿐. 남은 준비 약 **3 ~ 6.25 시간** (결함 수정 · 연결 / 반례 시험 2 ~ 4 + 변경 독립 재검 0.5 ~ 1 + 배치 · 계약 동결 0.25 ~ 0.5 + 별도 GPU 진단 0.25 ~ 0.75). A 는 과거 평균 75.3 초 단순 대입 때 56 분 28.5 초 (시작 시험 · 대기 · 실패 · 재시도 별도) → 「지금부터 한 시간 안에 A 결과」 는 근거 없음. 공통 lease 를 기존 모든 도구에 적용해야 하면 추가 범위.
- **조치:** `TASK-codex-worker-1043-eval-fix.md` (17r 줄 번호 · 반례 그대로 · 진단 모드 · 연결 시험 · 새 변이 · 고치기 전 `cand_17r_base/` 보존 · 중간에 멈추지 말 것) 로 작업자 E 에게 12:12 에 고침 라운드를 맡김 (컨텍스트 40 % · Codex 주간 한도 34 % 남음). GPU 는 둘 다 비어 있음 (GPU 1 09:40:37 · GPU 0 05:46 부터) · 새 판 승인 전 기동 없음.

## 작업자 E 17r 고침 결과와 ASTRA 17s 의뢰 (21:50 · 팀장 답 없이 준비 단계만 진행)

- **배경:** 팀장 질문 5 건 (13:36 #546 6160996409) 에 8 시간 넘게 답이 없고 GPU 0 은 05:46 부터 (약 16 시간) · GPU 1 은 09:40:37 부터 (약 12 시간) 비어 있다. 상시 지시 「GPU 쉬지 않게 · ASTRA 허용 범위만」 에 따라, GPU 를 띄우지 않고 팀장 결정이 필요 없는 준비 단계 (고침 후보 사본 · ASTRA 검증 의뢰) 만 진행한다. 사다리 우선순위 (S2 우선 · 1043 곁가지) 와 Worker 통합 · 아티팩트 8 판 · 세션 종료는 팀장 답 전까지 손대지 않는다.
- **작업자 E 보고 (12:54 · `REPORT-17r.md`):** 17r 항목 1 ~ 15 를 CPU 로 고쳤다고 보고. 한계 (작업자 자신): GPU · Isaac · 실제 slot v3 · guard · isolate · Kit 연쇄 미실행 / 공통 lease 를 다른 모든 실행기가 쓰는지 미확인 / 가짜 slot 은 CPU 경계.
- **lead 재실행 (12:55:00 ~ 12:55:35):** `run_all_17r.py` 새 run-id `run_20261014_125500_26228` · 여섯 시험 모두 종료 0 · `CAUGHT` 12 줄 모두 `want` 가 `got` 에 들어 있음 (로그 대조). 줄 단위 코드 검토 · 변이가 의도한 검사만 끈 것인지 · 17r 반례 직접 재현은 **하지 않음** (ASTRA 몫).
- **사본:** `night-tools-20261013/cmdr1043_eval_cand_17r/` (cand 와 `cmp` 불일치 0 · `SHA256SUMS.txt` 25 줄). 핵심 해시: `manifest_s1043.json` `79929490f5f2` · `frozen_exec_s1043.py` `eaee9668015d` · `cmdr_eval_driver_s1043.py` `69008ba41b52` · `cmdr_post_s1043.py` `9b2565c48946` · `cmdr_bundle_compare_s1043.py` `77c5e5dd0798` · `s1043_manifest.py` `ce1ad4930c5f`.
- **의뢰:** `TASK-astra-17s-1043-eval-fixed.md` 로 ASTRA 17s (고침 검증 · 진단 단계 승인 조건 · UNDECIDED 구분 · 견적). **GPU 기동 없음.** 판정 뒤에도 manifest 의 팀장 결정값 (GPU 배정 · 독점 실행 범위 · 마감 · 위험 한도 · 진단 반복 예산) 이 비어 있으면 승인 json 을 발급하지 않는다.
- **놀고 있는 GPU (21:50 기준):** GPU 0 05:46 부터 (이유: 1043 학습이 끝났고 허용된 다음 기동 없음 · 1043 평가는 17s 대기 · S2 학습 루프 미연결) · GPU 1 09:40:37 부터 (이유: v2 기록 뒤 허용된 다음 기동 없음 · 무작위화 smoke 는 GPU 전체 여유 부족으로 팀장 결정 대기). 둘 다 python / Kit 계산 프로세스 0.

## ASTRA 17s 판정과 작업자 E 의 17s 고침 라운드 (22:49)

- **17s (22:11 작성 · 전문 읽음): 고칠 것 · 현 후보의 GPU 진단 기동 보류 · 승인 json 발급 안 함.** 고정 파일 25개와 등록 입력 38개 해시 일치. 17r 의 주요 반례(GPU 0 정수 · bool/float/문자열 거절 · 9개 시작 시험 argv · 중복 옵션 · 대소문자 별칭 lock · 손자 자식 대기 · 물리 GPU 1 논리 CUDA 0 45 valid · MAE 한 건 NaN 거절 · 평평한 배치 · 진단 뒤 A 미호출)는 닫힘. ASTRA 격리 재실행 여섯 시험 모두 종료 0 (3.94 · 1.27 · 0.45 · 26.06 · 3.47 · 0.30 초).
- **새 결함 (고칠 것):** (P1) `D:995, 1478` 진단이 원본 q 결과에도 `need_iter=True` 를 적용하는데 고정 `q_eval.py` 는 `loaded_iter` 를 기록하지 않아 첫 진단이 held_incomplete 로 끝날 것으로 예상 (실제 원본 meta 에도 필드 없음) · (P1) `D:620, 664, 845` `max_wall_s` 는 실행 중 상한이 아님 (한도 2 초 / 4 초 자식이 5.8 초 뒤 rc=0) · (P1) 승인 예산 결박 미완성: 같은 승인 · digest 에서 `execution.attempt` 만 바꿔도 오류 0, launch 수는 프로세스마다 0 으로 시작 → 승인 ID · attempt · 누적 예산을 묶어야 하고 승인 B 스키마 변경 후 새 스키마 그대로 재검 · (P2) `M:239` 재시도 0 회 표현 불가.
- **시험 신뢰 범위:** 가짜 slot 연결 시험(`test_17r_e`)은 ready · GPU 탐지 · validate · fingerprint 를 성공 함수로 교체했고 `--cpu_fixture` 로 실제 GPU probe · 전체 launch 재검을 생략한다 (guard · isolate · q · Isaac 미실행). 변이 12 개는 「이름이 다른 입력 변조 12 종」이지 코드 검사를 하나씩 끈 변이가 아니다 (17r 의 코드 변이 6 종과 합쳐 18 종이라 세지 말 것). 진단의 byte-only 차이(JSON 공백 · 키 순서)도 held_mismatch/3 이 되므로 물리 비결정성으로 쓰면 안 됨.
- **UNDECIDED 구분 (17s 4 절):** lead 측정 = 물리 UUID/index · 여유 · 판/경로 · 고정 코드 · 38개 입력 해시 · 양 군 종료 · SAME · canonical lock/lease/registry와 참가 실행기의 사용 증거. 팀장 결정 = GPU 배정 · 독점 시간창과 참여 범위 · 시작/종료 마감의 의미 · 최대 launch · retry · 벽시계와 중단 방식 · 원본 반복 예산 · 한 승인으로 허용할 재기동 범위. ASTRA = 수정된 정확한 바이트에 대한 제한된 진단 기술 승인(지금 보류). 현 M 이 검사하는 승인 B 키: experiment · train_seed(1043) · contract_sha256 · stage · candidate_hashes(M · 비교기 · D · P · F 5개 파이썬) · comparison_report_sha256 · gpu_index · gpu_uuid · CUDA_VISIBLE_DEVICES · diagnostic_repeat_original · deadline_epoch · risk_limit(max_child_launches · max_retries_per_run · max_wall_s) · convert_lock · run_lease · registry · python. 승인 JSON 바이트 SHA256 을 `execution.approval_sha256` 과 `--approved_digest` 양쪽에 대조. 승인 스키마는 위 결함 3 때문에 바뀔 예정이므로 현 양식으로 발급하지 않음.
- **배치안(결정 아님):** `candidate_dir=_eval/cmdr1043_eval_17s_fixed/` (M · 비교기 · D · P · F · manifest 한 층) · `source_eval=_eval` · `write_root=_audit_cmdr1043/` 아래에 data/reports/work/attempts/logs/STOP. 현 M 은 모든 `WRITE_KEYS` 가 source_eval 밖이어야 해서 `_eval/slot` 같은 기존 공통 경로는 그대로 넣으면 거절됨. 비교기는 번들을 write_root 아래로 바이트 그대로 복사한 뒤 실행해야 함(ASTRA: SAME/0 → seed1042 변조 DIFFERENT/1 → 복구 SAME/0 확인).
- **A 예산(17s 5절 5):** A 기동 시 기본 시작 시험 8회 + 조건부 원본 반복 1회 + A 45회가 launch 예산에 들어가야 한다. A 45 만 세면 부족.
- **견적(추정, 보장 아님):** 수정 1 ~ 3 h + 독립 재검 0.5 ~ 1 h + 배치 · 측정 0.25 ~ 0.5 h = GPU 진단 시작까지 약 1.75 ~ 4.5 h + 팀장 결정 대기. 진단 한 묶음(Isaac 세 번)은 승인 뒤 10 ~ 20 분 작업창으로 잡되 실패 · 반복은 별도 예산.
- **조치 (22:49):** `TASK-codex-worker-1043-eval-fix2.md` 로 작업자 E (`term_40bccb75`, Codex 컨텍스트 18 % · 주간 29 %) 에게 17s 고침 라운드를 맡김. CPU 전용 · `_eval` 읽기만 · 팀장 결정값은 UNDECIDED 로 유지. 이 일은 1043 평가 곁가지이며 S2 우선 여부는 팀장 답 전까지 바뀌지 않음. GPU 기동 0.

## 작업자 E 17s 고침 결과와 ASTRA 17t 의뢰 (23:52)

- **작업자 E 보고 (23:15 · `REPORT-17s.md` · 전문 읽음):** 17s 7 항목을 CPU 로 고쳤다고 보고. 원본 q 의 누락된 `loaded_iter` 만 허용(원본 진단 · 반복 원본에만 `need_iter=False`) · `deadline_epoch` 시작 금지와 `max_wall_s` 소유 자식 트리 상한 분리(rc 124/125, `held`, 종료 확인 전 lease 유지) · 승인 B 22 키(`approval_id` · `attempt` · `log_name` · `restart_scope` · `termination_policy` · `comparison_pass_rule` 추가) 와 `write_root/approval_ledger/<id>/claim.json` 디렉터리 원자 생성 **단회 예약** · retry 0 허용 · byte-only 원인 코드와 비교 3 값 분리 · 보고 항목 동등 · `common_write_allowlist`. 작업자 한계: GPU · slot v3 · guard · isolate · Kit 연쇄 · 공통 lease 를 다른 모든 실행기가 쓰는지 · 운영 경로 적용 미확인, 관찰 전에 사라진 자식과 PID 재사용 보증 아님.
- **lead 재실행 (23:48:48 ~ 23:50:07):** `run_all_17s.py` 새 run-id `run_20261014_234848_102912` 열 시험 모두 종료 0. 코드 검사 끈 변이 6 종 모두 정상 종료 0 · 변이 종료 1 · `failed` = `want`, 변이 로그 3 건 끝의 `AssertionError` 라벨이 시험 소스 `check(...)` 줄과 일치. 입력 변조 12 종과 합치지 않고 따로 셈. 후보 159/159 해시 실행 전후 일치. 변이가 의도한 검사만 껐는지 · 줄 단위 코드 검토 · 17s 반례 직접 재현은 하지 않음(ASTRA 몫).
- **관찰할 점 (lead 메모):** 단회 claim 은 충돌 · 중단 뒤에도 같은 승인을 재사용 못 하므로 진단이 중간에 실패하면 승인 재발급이 필요하다. 「진단 한 묶음(세 번 + 조건부 원본 반복)」 이 한 claim 안에서 처리되는지가 17t 물음 1(c).
- **사본 · 의뢰:** `night-tools-20261013/cmdr1043_eval_cand_17s/` (cand 와 `cmp` 불일치 0 · `SHA256SUMS.txt` 31 줄 · 커밋 d1b2a0c1) · `TASK-astra-17t-1043-eval-fix2.md` 로 ASTRA 17t 의뢰(23:51). **GPU 기동 없음.** 팀장 결정값은 전부 UNDECIDED.
- **놀고 있는 GPU (23:52 기준):** GPU 0 05:46 부터 약 18 시간 · GPU 1 09:40:37 부터 약 14 시간. 이유는 앞 절과 같고 허용된 다음 기동이 없다. 둘 다 python / Kit 계산 프로세스 0.

## ASTRA 17t 판정과 작업자 E 의 17t 고침 라운드 (10/15 00:50)

- **17t (00:12 작성 · 전문 읽음): 고칠 것 · 진단 기동 보류 · 승인 json 발급 없음.** 고정 31개 파일 · 입력 38개 해시 일치, ASTRA 격리 재실행 열 시험 모두 종료 0 (79.70 초). 17s 의 네 결함은 지정 범위에서 닫힘: 원본 q 필드(검사를 통째로 끈 해결 아님) · 2 초 / 4 초 벽시계(rc 124) · 승인 장부 별도 프로세스 동시 시작 경쟁(1 건 claimed, 1 건 already used) · retry 0. 단회 claim 은 한 프로세스의 세 q 실행 · 승인된 재시도 · 조건부 반복이 누적 예산을 함께 쓰는 설계로 「진단 한 묶음」에 맞음(실패해도 이미 쓴 승인, 재개는 새 승인 ID).
- **기동 차단 결함 셋:** (1) `D:711~720, 753~766` PID 재사용: 관찰했던 중간 자식 110 이 종료된 뒤 다른 프로세스가 PID 110 을 재사용해 새 자식 300 을 낳으면 후보가 **무관한 300 을 known 에 넣고 kill 을 호출**(결정적 반례, 실제 프로세스를 죽인 실험은 아님). 부모의 PID + 생성 시각을 확인하지 못하면 소유했다고 판단하면 안 됨 (2) `M:232~340, D:1590~1591` `comparison_pass_rule` 값 검사 없음: 엄격 규칙 · `UNDECIDED` · `ignore_all_differences` · `false` · `null` 모두 관문 통과, `approval_id` · `log_name` 의 `UNDECIDED` 도 통과(현 미결정 manifest 전체가 기동 가능한 것은 아님, 다른 UNDECIDED 가 막음) (3) `D:1522~1557` 지문 계산 예외를 삼켜 `status=valid, fingerprint=null` 유지(실제 원본 사본에서 `env_origins.npy` 만 옮겨 재현), 최종 완료 조건도 못 봄.
- **정정 (ASTRA):** 코드 변이 6 종은 모두 「안전검사 비활성화」가 아니다(원본 필드 회귀 · 벽시계 비활성화 · claim 무력화 · retry 0 회귀 · byte-only 표기 오류 · allowlist 조건 제거). `test_17s_original` 은 slot 경계만이 아니라 `log_done` · `usd_check` · `py_traceback` 도 성공 함수로 바꿨다(50~52 줄). 이전 보고의 「slot 경계만 대체」는 틀린 설명이었음(작업자 보고를 그대로 전한 문장).
- **ASTRA 의 팀장 결정 권고 (추정, 승인값 아님):** 첫 묶음 launch 3 · retry 0 · 원본 반복 false (불일치 원인용 반복을 원하면 launch 4 · repeat true 를 사전에 선택) · `max_wall_s` 1200~1800 초(준비 · 안정성 관찰 · 대기 포함) · `deadline_epoch` 는 20~30 분 작업창의 새 자식 시작 마감 · `restart_scope=single_start_no_reuse` · `terminate_grace_s` 5~10 초 · 부분 결과 `held` · 통과선 `semantic_and_json_bytes_and_traj_bytes` 하나뿐 · GPU 0 또는 1 중 팀장이 비어 있는 것을 배정. 공통 잠금은 기존 검증 경로를 정확한 allowlist 로 재사용 권고(새 경로에 우리 lease 만 두면 서로 못 막음). A 는 시작 시험 8 + 45 = 53 launch(조건부 원본 재시험 포함 54) 별도 승인.
- **견적(추정):** GPU 진단 시작까지 1.5 ~ 3.5 h + 팀장 결정 대기(수정 중 병행 가능).
- **조치 (00:49):** `TASK-codex-worker-1043-eval-fix3.md` 로 작업자 E(컨텍스트 46 % · 주간 26 %) 에게 17t 고침 라운드를 맡김. CPU 전용 · GPU 기동 0.
- **놀고 있는 GPU (00:49 기준):** GPU 0 05:46 부터 약 19 시간 · GPU 1 09:40:37 부터 약 15 시간. 둘 다 python / Kit 계산 프로세스 0.

## 작업자 E 17t 고침 결과와 ASTRA 17u 의뢰 (10/15 01:52)

- **작업자 E 보고 (01:14 · `REPORT-17t.md` · 전문 읽음):** 17t 의 기동 차단 결함 셋과 보강 셋을 CPU 로 고쳤다고 보고. 부모 `(pid, create_time)` 확인 뒤에만 새 자식 등록 · 불명 자식은 신호 없이 `unowned_unknown` 으로 lease 유지 · `comparison_pass_rule` 등 승인 필드 값 검사(허용 집합 하나) · 필수 지문 누락은 `held` + why · 공통 지문 대조 · 비용 필드 · allowlist 정확 경로. 작업자 한계: 관찰 전 재부모화는 못 찾을 수 있음 · Job Object 는 구현하지 않음(검토 의견만) · `test_17s_original` / `test_17t_fingerprint` 가 `log_done` · `usd_check` · `py_traceback` · slot 을 가상화 · `test_17r_e` 의 validate / fingerprint 성공 함수 교체.
- **lead 재실행 (01:48:30 ~ 01:50:19):** `run_all_17t.py` 새 run-id `run_20261015_014830_16564` 열다섯 시험 모두 종료 0. 17s 코드 변이 6 종 + 17t 신규 3 종 모두 정상 종료 0 · 변이 종료 1 · `failed` = `want`, 신규 3 건은 변이 로그 끝의 `AssertionError` 라벨이 시험 소스 `check(...)` 줄과 일치. 후보 165 파일 해시 실행 전후 일치. 줄 단위 코드 검토 · PID 반례 직접 재현 · 변이가 의도한 검사만 바꿨는지는 하지 않음(ASTRA 몫).
- **사본 · 의뢰:** `night-tools-20261013/cmdr1043_eval_cand_17t/` (cand 와 `cmp` 불일치 0 · `SHA256SUMS.txt` 37 줄) · 커밋 30d625b5 · `TASK-astra-17u-1043-eval-fix3.md` 로 ASTRA 17u 의뢰(01:51). 핵심 물음: 17t 결함 셋 닫힘 여부 · 이 바이트가 「제한된 진단 기술 승인」 대상으로 충분한가 · 팀장이 17t 권고값을 그대로 쓸 수 있는가 · lead 측정 순서 · 공통 경로 canonical 후보 · 병행 가능한 단계. **GPU 기동 없음.**
- **한도:** Codex 주간 25 % (작업자 E · ASTRA 둘 다) · Claude 주간은 미확인. 이 곁가지가 한 라운드 돌 때마다 한도를 쓴다.
- **놀고 있는 GPU (01:52 기준):** GPU 0 05:46 부터 약 20 시간 · GPU 1 09:40:37 부터 약 16 시간. 둘 다 python / Kit 계산 프로세스 0. 팀장 질문 5 건 (#546 6160996409) · 00:49 채팅 질문에 대한 답은 아직 없음.

## 팀장 결정과 새 지시 (10/15 02:2x ~ 02:3x · 팀장 「권고대로」)

- **결정(#546 6173893451 의 다섯 가지 모두 「권고대로」):** (1) 틈 · 징검다리 연습을 지도 실험 안에 같이 넣고 「지도를 준 모델」 과 「안 준 모델」 을 비교하는 안 A (2) 1043 채점기 마무리 승인: GPU 0 · launch 3 · retry 0 · 원본 반복 없음 · `max_wall_s` 1200~1800 초 · 종료 유예 5~10 초 · 작업창 20~30 분 · 단회 승인 · 통과선 하나 (ASTRA 17u 판정이 나온 뒤 이 범위 안에서 정확한 값을 lead 가 정해 기록하고 ASTRA 가 승인 json 에 결박. 순위는 지도 실험 아래) (3) Codex 작업자는 E 하나만 남기고 이름은 `sol` (창 다섯 개 닫음: A `term_602208c0` · B `term_223a8374` · C `term_766933da` · D `term_a29c03e2` · luna `term_2d3193e9` 모두 입력 대기 상태였고 결과물은 파일로 보존. 옛 시험 프로세스 PID 175820 은 이미 없음) (4) 무작위화 영상용 화면 앱 정리 보류 (5) 보고 페이지 「한 장 흐름」 재작성은 1번 뒤.
- **팀장 새 지시:** (가) 핵심 원칙: GPU 는 절대 놀면 안 된다. (나) 실험은 곁다리가 아니라 실제 gap · stepping_stones 를 넘는 것을 해야 한다. (다) 11/7 은 마지막 날짜일 뿐이고 그 전에 방향을 빠르게 내야 한다. 효과 있는 방향이면 학습량을 올려 오래 학습한다(이 단계가 Linux 이전과 이어짐). (라) 팀장은 MoE-CTS 구조로는 원하는 결과를 얻기 어렵다고 본다. 먼저 MoE-CTS 방식으로 「지도를 준 student」(P 단계) 까지 실험하고, 그 결과를 보고 어떤 논문을 바탕으로 신경망을 다시 설계할지 정한다. 이 접근이 진도가 안 나가 실망했다. (마) 한도 대비: 주간 한도 85 % 이므로 omniroute 를 먼저 셋업해 작업에 문제가 없게 하고, 그 뒤 lead 를 Opus 5.5 로 올려 한도를 충분히 쓰고, 100 % 가 되어도 GLM 계열로 같은 작업을 이어 가게 한다(`/model` 은 팀장만 바꿀 수 있음).
- **lead 의 정정:** 02:2x 에 「지금 이어서 정리하고 있습니다」 라고 썼으나 그 턴이 끝나 아무것도 돌지 않았다. 말한 것을 하지 않은 것은 제 잘못이다. 또 작업자 창 이름을 바꾸려 `/rename sol` 을 Git Bash 에서 보내 `C:/Program Files/Git/rename sol` 이 입력으로 들어갔다(폴더는 생기지 않음, 메모리에 기록). Orca 탭 제목은 터미널이 보고하는 제목과 별개라 `orca terminal rename` 으로 따로 `sol` 을 지정했다.
- **조치(02:35):** (1) 작업자 sol 에게 `TASK-codex-worker-s2-step2.md` (S2 학습 루프 연결: 알고리즘 · 러너 · 지도 어댑터 · 희소 지형 겹침 · smoke 사전 등록 초안 · 기동 스크립트 초안 · CPU 가짜 환경 시험) 를 보냄. GPU 기동 아님. 1043 은 ASTRA 17u 판정 뒤 순위를 낮춰 잇는다 (2) super2 에게 omniroute 셋업을 최우선으로 해 팀장 손이 필요한 단계만 번호로 주고 나머지는 준비하라고 두 번 전달(대기열에 있음) (3) 이후 순서: sol 보고 → lead 재실행 → ASTRA 의뢰 → smoke 기동 허용이 나면 GPU. S2 학습 연결이 끝나기 전까지 GPU 에 올릴 수 있는 허용된 일은 1043 진단 하나뿐이다.
- **놀고 있는 GPU (02:35 기준):** GPU 0 05:46 부터 약 21 시간 · GPU 1 09:40:37 부터 약 17 시간. 둘 다 python / Kit 계산 프로세스 0.

## RAND smoke 기동 기록 (04:56 · ASTRA 17j 조건부 허용)

- **근거:** `VERIFY-astra-17j.md` 6 절. 허용은 **고정 판 v4 의 smoke invocation 하나** 뿐 (`--stop_after_smoke`). 네 장면 본 실행 · 다른 모델 · unseen · CE12 로 확장 안 함. `--skip_smoke` 금지.
- **기동 전 확인 (6 절 1 ~ 4 · 기록 job tmp `codexw/rand_smoke_preflight.json`):** (1) v4 8 개 · slot · isolate · guard 해시가 ASTRA 표와 같음 · python 3.11.15 · numpy 1.26.0 · 체크포인트와 env.yaml 해시 기록 (2) 상대 참가자: GPU 0 의 CMD-R 1043 on (PID 154852) 로그가 scan 범위 (`out_branch`) 에 있고 USD `usd_20261014_001833_9514` 가 읽힘 · GPU 1 의 다른 python 계산 프로세스 0 · dry-run 으로 v3 registry · 같은 변환 잠금 · attempt 별 USD 루트 · 변환 예상 1 · 검색 경로 확인 (3) GPU 1 NVML 새 조회: UUID `GPU-315d098f-...` 총 16303 MiB 사용 5783 MiB (여유 약 10.5 GB ≥ 하한 4096) (4) 명령: `--stop_after_smoke --probe auto --smoke_s 5 --min_free_mib 4096 --deadline <지금 + 20 분 epoch>`.
- **중단 · 보류:** 보호 종료 89 ~ 99 · USD 루트 밖 · 공유 · 미할당 · 추가 변환 · registry 오류 · 상대 로그 미해결 · 장치 UUID 불일치 · 코드 변경이면 다음으로 안 넘어감. S3 는 일부러 실패시키는 음성 대조 (`FRAME_GATE frame 20` 이어야 함).
- **끝난 뒤 읽을 것 (17j 6 절):** 각 시도의 명령 · slot · guard · 로그 · 스틸 · manifest · UUID 를 NVML · 논리 CUDA 0 · Kit 렌더 장치의 물리 장치로 연결 · USD 한 개 · 자기 루트 · 충돌 없음 · S1 검정 프레임 회복 · S2 상태 일치 · S3 의도한 실패 · 최고 사용량 · 최소 여유 · 시간. rc 만으로 probe 성공이라 하지 않음.
- **결과 (04:59): smoke S1 이 두 번 (a1 · a2) 종료 코드 3 으로 실패하고 설계대로 멈춤 (본 장면 · 다음 단계는 돌지 않음).** run `rand4-smoke-20261014-045701` (04:57:01 ~ 04:58 · 약 1 분). 보호 오류가 아님: 시도마다 USD 한 개 (`usd_20261014_045723_7028` · `usd_20261014_045750_7028`) · 충돌 `{}` · guard rc 3 은 자식 종료 코드 · min_free 4417 · 4442 MiB · max_used 11885 · 11860 MiB. **원인 (로그 464 ~ 481 행):** `q_rand.py:323` 이 환경 1 개 (`num_envs = 1`) 로 `OnPolicyRunnerCTS` 를 만드는데 `moe_cts.py:120~129` 의 teacher 환경 목록이 환경 1 개이면 항상 비어 `AssertionError: len(teacher_env_idxs)=0 != teacher_num_envs=1`. 다른 평가 스크립트는 환경이 여러 개라 문제없었음. CPU 가짜 시험으로는 안 보이는 결함 (ASTRA 도 17j 에서 「smoke 가 확인할 미확인」 으로 남겼음). 증거: `out_rand/rand4-smoke-20261014-045701/smoke_base/a*/fail.json` · 로그 `out_rand/rand4-smoke-20261014-045701__smoke_base__a*.log` · job tmp `codexw/rand_smoke_console.txt`.
- **조치:** 작업자 B 에게 최소 수정 (환경 2 개 이상 · 기록과 판정은 env 0 기준) 을 맡김 (04:59 · 보관 `rand_scenes/v4_smokefail/` · 보고 `codexB2/REPORT.md`). 고치면 `q_rand.py` 바이트가 바뀌므로 17j 허용은 적용되지 않음 → lead 재실행 → ASTRA 재확인 (17m) → smoke 다시. GPU 1 은 그동안 빔 (04:58 부터).
- **정정 (17j 2 절 P1):** 내가 「변이 9/9 CAUGHT (lead 재실행)」 이라 적은 것 중 **5 건 (M22 · M42 · M75 · M76 · M78) 은 시험 대상과 무관한 `ModuleNotFoundError: frame_audit` 실패를 CAUGHT 로 센 오집계**였다 (변이 실행기가 FAIL 줄이 하나라도 있으면 CAUGHT 로 셈 · 정상 소스를 같은 방식으로 돌려도 실패). ASTRA 가 경로를 보정해 정상 대조군 4/4 통과 뒤 같은 9 개를 다시 돌려 **실제 9/9 검출**을 확인함. 내 보고의 「변이 9/9」 는 ASTRA 의 재검 결과로만 인용한다. 나머지 변이 68 개는 아무도 안 돌림.

## 모델 · 한도 (팀장 10/14 02:2x)

- **lead 는 02:2x 부터 Sonnet 5.5.** 팀장이 `/model` 로 내림. 주간 한도 82 % (해제 10/17 20:00 · 이 계정을 여러 세션이 나눠 씀) · 5 시간 한도 해제 04:20. 한도를 재는 것은 super2 (Mods 기록) 이고 lead 는 직접 못 잼.
- **ASTRA 에는 02:2x 에 「lead 가 Sonnet 이니 더 신중 · 꼼꼼히 독립 대조」 를 요청.** 이후 모든 의뢰문 머리에 같은 줄을 넣는다 (17i 에 이미 넣음).
- **Sonnet lead 규칙:** 판정 파일은 끝까지 읽는다 · 기동은 승인 json 관문 (또는 ASTRA 판정이 명시 허용한 것) 을 통과할 때만 · 판정을 「허용」 으로 읽기 어려우면 보류 · 하위 작업은 Sonnet 으로 · 큰 결정은 팀장 · Opus 로 올릴 때까지 미룸.
- **점검 예약:** `b367e132` (옛 eaa6843f 지움 · 1043 끝 · ASTRA 17k 17l 와 작업자 B 점검 문구) 한 시간에 한 번 (`27 * * * *` · 옛 2b1bfe25 지움 · CronList 에 하나만) (02:2x · 한도 절약). 04:27 이 5 시간 한도 해제 뒤 첫 점검.
- **omniroute + GLM-5.3 (팀장 제안 · 02:2x):** 설치하지 않음. 조사 결과는 #550 02:3x 댓글. 요지: 별도 프로세스를 새로 띄우는 방식이라 이 세션을 못 바꿈 · NVIDIA 쪽은 평가용 trial 약관 · 속도 제한 · 데이터 취급 미확인 · 도구 호출 번역 한계 문서 없음. 조건을 갖춘 별도 보조 세션 (기계적인 일만) 으로만 검토.
- **이 세션은 끝내지 않는다.** 점검 예약 · 하위 작업 · 1043 학습 (상위 프로세스 21100 은 이미 없는데 학습은 계속 돔 · Claude 종료 때 셸을 트리째 죽이는지는 미확인) 이 여기에 걸려 있음.

## Codex Worker 점검 (02:38 · 팀장 「YOLO 모드로 해 문제 없어」)

- **세션:** Orca 창 「Codex Worker · sol 17g-A」 `term_602208c0-0d32-4891-9337-5506b6564c46` · 「Codex Worker · sol 17g-B」 `term_223a8374-3136-4d07-9564-29af942d4079` (둘 다 gpt-6-sol · 추론 high · YOLO · Codex 주간 67 % 남음). 「Codex Worker · luna (정해진 명령)」 `term_2d3193e9-4acc-42e6-bd5a-9905e0f2ab94` 는 시험 끝 (CE12 시험 재실행 답이 정확히 맞음 · 놀고 있음).
- **검증 세션 (ASTRA `term_fe1daede`) 과 섞지 않는다.** 작업자는 고치는 쪽, ASTRA 는 검증하는 쪽.
- **보호 기준선:** job tmp `codexw/protect_baseline.txt` (02:35 · `bash codexw/protect.sh` 로 다시 만들어 diff). 작업자가 끝나면 1043 학습 로그 (out_branch/cmdr_s1043_on_u4000*) 말고 아래가 **모두 같아야** 한다: out_uncr · out_uncr_reval · out_uncr_v5 · slot · branch · out_ce12 · handover · ce12 · s2 · out_smoke · 나머지 out_branch · frozen_py · isaac311-moects conda-meta. `out_rand` 는 판 4 시험이 읽기만 해야 하므로 같아야 한다. 다르면 **작업자 결과를 채택하지 않고** 무엇이 바뀌었는지 먼저 본다 (작업자는 YOLO 이므로 가장 큰 위험).
- **heartbeat 마다:** (1) 두 창의 마지막 상태를 읽는다 (`orca terminal read --terminal <h>`): 일하는 중 · 기다리는 중 · 오류 · 끝. 승인 창에서 멈춰 있으면 (YOLO 라 드묾) 어떤 승인인지 본다 (2) 새 보고서가 있으면 전문을 읽는다 (3) 같은 일을 다시 보내기 전에 창의 상태와 산출물을 확인한다. 끝났다고 한 말은 lead 가 재실행하기 전에는 사실이 아니다.
- **끝난 뒤 순서:** 보호 기준선 대조 → 보고서 전문 → 시험 · 변이 lead 재실행 (isaac311-moects · `CUDA_VISIBLE_DEVICES=-1` · 숫자 분모 구분) → 새 파일 저장소 사본 + SHA256SUMS → 17i (CE12) 가 먼저 가고 17j (v6 · 판 4) 가 그 다음. GPU 1 기동은 ASTRA 판정과 승인 json 이 있을 때만.
- **Codex 한도:** 주간 67 % 남음 (ASTRA 와 작업자가 같이 씀). 작업자는 한 번에 둘까지만. 같은 일을 다시 맡기지 않는다.

## 팀장 결정 대기

- 첫 S2 A/B 를 encoder 전 구간 고정으로 확정할지 (ASTRA 17f-2 권고 · lead 동의 · W50 · r0.1 은 뒤의 별도 물음).
- 1043 쌍 성능 평가 등록 (목표 칸 3 개 + 회귀 칸 · 「CMD-R 규약 교정」 결정과 묶임). GPU 0 이 05:46 부터 비어 있는 이유.
- 무작위화 smoke 의 GPU 메모리 (GPU 전체 사용량이 중단 시점까지 최고 12,928 MiB · 여유 3,374 MiB): 하한 4096 MiB 를 낮추지 않았고 GPU 0 으로 옮기지도 않았음. ASTRA 17o 순서 권고 (아래 「ASTRA 17o 판정」 절): 1 GPU 1 여유 확보 (불필요한 앱 정리는 팀장 결정) 2 렌더 비용 축소 (코드 변경 · 새 검증) 3 GPU 0 렌더 진단 (팀장 자원 배정) 4 하한 재검토 (팀장이 위험 수용). 어느 쪽도 lead 가 임의로 하지 않음.
- 사용 한도 대비: Codex Worker 먼저, omniroute + GLM 은 팀장이 키를 넣고 시험한 뒤 (설치하지 않았음).
- **정정 (09:04 super2 알림):** 위 표와 08:09 줄의 「ASTRA 재시작은 팀장 승인 대기」 는 낡은 정보다. super2 에 따르면 팀장이 01:39 에 직접 `codex resume` 으로 재시작을 끝냈다 (세션 01a0e3c2 그대로 · Codex 0.162.1 · #550 댓글 6150489719 는 super2 가 쓴 글). 나는 독립으로 재지 않았고 ASTRA 컨텍스트 자동 압축은 계속 일어난다 (09:03 에 10 % 에서 압축 중). 재시작 승인 항목은 목록에서 뺀다. 남은 것은 새 판에서 Mods hook 이 붙는지 (pipeline 몫).
- super2 가 09:03 에 RL 백업 마무리 회차를 시작함 (go2-eval 에 out_uncr_v6 · out_uncr_reval · out_ce12 · out_rand · slot 포함 · 원본은 읽기만). **이 회차가 끝나기 전에 위 원본 폴더를 지우거나 옮기지 않는다** (끝나면 vfxpedia/mai-os#34 에 결과가 적힘).

## Windows 업데이트 (00:32 확인)

팀장이 00:27 에 일시 중지 (레지스트리 기준 10/21 00:27 까지 · 품질 · 기능 둘 다). 00:25 에 Windows 가 대기 중이던 NVIDIA 표시 드라이버 32.0.16.1088 (지금 쓰는 것은 591.86) · Logitech 드라이버를 되돌렸고 KB5129195 되돌리기를 시작함 (완료 기록 아직 없음). 재부팅 대기 표시 둘 (RebootRequired · RebootPending) 은 아직 켜짐. 일시 중지 중에 스스로 재부팅할 수 있는지는 미확인. heartbeat 때 부팅 시각을 본다 (기준은 위).

## 읽기 · 재개 규칙 (팀장 10/14 00:05 · 00:20 · ASTRA 17h 고쳐서 채택 · 정본은 이 절)

1. **새 판단 문서 · 하위 작업 보고 · 현재 설계는 전문을 읽는다.** 읽은 뒤 대상별 허용 범위 · 필수 조건 · 미확인을 증거와 함께 위 「판정 조건」 에 적는다. 첫 줄 판정만 적으면 압축 뒤 「끝」 하나로 줄어든다.
2. **다시 읽기:** 이미 읽은 파일이라도 압축 뒤 조건이 불명확하거나 버전이 바뀌었으면 다시 읽는다 (00:56 17f 를 그렇게 다시 읽음). 근거가 남아 있고 버전이 같을 때만 생략한다. 참조된 옛 문서를 모두 따라 읽지는 않는다.
3. **시험 결과:** 통과 · 실패 수만이 아니라 예정 대비 실행 수 · skip · hold · pending · 종료 코드 · 출력 잘림 · 해석기 절대 경로와 버전 · 코드와 입력 해시 · 원로그 위치를 본다. 같은 숫자의 재실행은 시험 설계 오류 (예: 17f 의 공용 registry 기대값) 를 못 찾는다.
4. **진행 확인:** GPU 사용률과 콘솔 끝 세 줄은 표시용이다. attempt · PID · 로그 진행 (iteration · 시각 · 크기) · Traceback 으로 판정한다. 「새 결과 없음」 과 「진행 없음」 을 나눈다.
5. **그림:** 판단에 필요한 시각 근거 (지형 · 접촉 · 보행 영상 · 센서 정렬 · 학습 곡선) 는 본다. 같은 그림의 반복만 줄인다.
6. **재개:** 하위 작업을 잇거나 다시 맡기기 전에 현재 상태 · 산출물을 확인해 중복을 막는다. 실행을 띄우기 전에 무엇을 띄우는지 이 파일에 적고, 띄운 뒤 PID · attempt · 로그를 잇는다.
7. **줄이는 것:** 끝난 일의 전문 재주입 · 같은 보고의 여러 곳 복사 · 긴 git status · 디렉터리 나열 · 통과 시험 줄의 반복 · 의미 없는 진행 알림.
