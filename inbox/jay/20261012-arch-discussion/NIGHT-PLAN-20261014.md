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

- **v6 full:** 47 번째 실행까지 전부 종료 코드 0 · 한 실행 약 72 ~ 77 초 · guard 최소 여유 6643 MiB · HALT · STOP 없음. 남은 약 28 개 · 실측 간격으로 추정하면 08:27 무렵 끝 (보장 아님 · 마감 09:00 은 새 시도 기동 마감).
- **ASTRA 17m (무작위화 v4.1) 07:52 보냄.** lead 재실행: 시험 31/31 · 변이 11/11 (각 항목이 의도한 시험의 AssertionError · import 오류 없음 · 새 변이 5 개가 정적 소스 검사 한 시험에 몰린다는 점을 의뢰문에 알림). 사본 `rand_scenes_v41/` (17ee58ed).
- **작업자 B 의 v2 기록기 수정 (`dump_native_v2.py:242` `runner.load(ckpt, map_location=dev)`):** 07:27 보고. lead 확인: 새 시험 `test_v2_load_device.py` 는 **v2 기록기의 해석기 `isaac311` python 에서는 통과** (CONTROL 로 수정 전 CUDA:1 실패 재현 · PASS) 하고 `isaac311-moects` 에서는 다른 `rsl_rl` (저장소 source) 이 불려 `AttributeError: alg_cfg` 로 실패. 작업자 보고서는 해석기를 `isaac311-moects` 라고 적어 어긋남 (시험은 실제 기록기의 해석기로 돌려야 함). CE12 회귀 (23 · 139 · 24 · 65 · 11) lead 재실행 진행 중. 끝나면 17n.
- **v2 다시 시도:** 17n 허용 + v6 가 끝나 GPU 1 이 비고 + 기동 직전 확인 (17k 5 절) 이 있어야. 그 전에는 안 함.

## v6 full 결과와 RAND smoke 2 기동 기록 (08:31)

- **v6 full 끝 (06:51:59 ~ 08:29:45):** 75 개 실행 모두 종료 코드 0 · 한 실행 약 70 ~ 77 초 · guard 최소 여유 6643 MiB · 최고 사용 9659 MiB · HALT · STOP 없음 · 새 시도 마감 09:00 안. 드라이버 종료 코드 1 은 마지막 후처리의 「새 재검 보고서 파일을 쓰지 못함」 때문: v6 기본 보고서 위치 (`out_uncr_v6/reval`) 가 입력 루트 안이라 재검기가 쓰기를 거절 (작업자 시험은 경로를 작업 폴더로 덮어써 못 봄 · **승인된 v6 코드의 기본 경로 결함**). 후처리가 메모리에서 낸 결과: 32 칸 · 완전 32 · 요청 칸 누락 · 불완전 · invalid · hold · 짝 불일치 0 · 동결 확인 · 옛 묶음 일치 · 표 `UNCR-cells-v6.csv` · `post_v6.json` 은 써짐.
- **lead 가 재검기 v3 명령줄로 새 루트를 읽기 전용으로 다시 검사 (08:30 · 보고서를 루트 밖 `out_uncr_reval/20261014-083045/revalidate.json` 에 씀 · 코드 수정 · 환경 변수 덮어쓰기 없음):** 실행 75 valid · hold 0 · invalid 0 · 새 칸 25 valid · 불완전 0 · 새 묶음 `9e2f6dba…` (후처리의 값과 같음) · 동결 확인 · 입력 825. 명령줄 종료 코드 1 은 「진단 칸 7 개 없음」 (진단 칸은 옛 묶음에 있고 새 루트에는 없음) 때문으로 **추정** (확인은 ASTRA).
- **RAND smoke 2 (ASTRA 17m 조건부 허용 · v4.1):** 기동 직전 확인 (job tmp `codexw/rand_smoke2_preflight.json` · `prelaunch_check_0833.json` · dry-run `rand_smoke2_dry.txt`): v6 끝 · GPU 1 에 python · Kit 계산 프로세스 없음 · GPU 1 UUID `GPU-315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f` 총 16303 · 사용 5754 · 여유 10549 MiB (하한 4096 · 과거 값 재사용 안 함) · v4.1 8 개 코드 해시 17m 사본과 8/8 같음 · slot · isolate · guard · frame_audit · q_metrics 해시 17m 때와 같음 · E1 체크포인트 `c8951b79…` · train yaml `2ee0009f…` · python 3.11.15 · numpy 1.26.0 (isaac311-moects) · 구형 registry 27/27 · v3 registry 79/79 로그 읽힘 · 상대 실행 프로세스 없음 · 환경 변수 덮어쓰기 0 · STOP · HALT 없음 · v3 registry · 변환 lock · attempt 별 USD 루트 · 변환 예상 1. 명령은 17m 그대로 (`--stop_after_smoke --probe auto --smoke_s 5 --min_free_mib 4096 --deadline <지금 + 20 분>`).

## ASTRA 17m 판정과 다음 GPU 1 순서 (08:10)

- **17m (08:07 · RAND v4.1): smoke 한 번만 조건부 허용 · 본 실행 미승인.** 수정이 S1 실패 원인 (환경 1 개에서 teacher 목록이 빔) 을 고쳤다고 확인 (실제 `MoECTS` 클래스로 n=1 실패 · n=2 통과 · 단 n=3, 4, 5 는 teacher 목록이 달라 「2 개 이상이면 항상 [1]」 은 틀림 · 이번 설정은 정확히 2 개). **조건:** (1) v6 의 GPU 1 사용이 끝나고 자식 Isaac 도 종료된 것을 실제 프로세스와 GPU 로 확인 (2) 새 8 개 코드 · slot · isolate · guard · frame_audit · q_metrics · 체크포인트 · train YAML · 실제 자식 python 환경의 해시와 절대 경로 (3) GPU 1 NVML UUID · 총량 · 여유를 새로 읽음 (최소 4096 MiB · 과거 4417 · 4442 MiB 재사용 금지) (4) 상대 실행의 실제 로그가 scan 에 포함되고 읽히고 USD 경로가 풀림 (수동 읽기 필수) · v3 registry · 변환 lock · 새 run_id. 명령: `rand_driver.py --run_id <astra17m-smoke-...> --stop_after_smoke --probe auto --smoke_s 5 --min_free_mib 4096 --deadline <지금 + 20 분>` (`--skip_smoke` · `--probe on` · 무기한 deadline 금지 · S1 은 `tries=2` 로 최대 두 시도 · invocation 하나가 최대 네 native 시도). S1 이 같은 오류로 두 번 실패하면 종료 5 로 멈추고 재시작하지 않음.
- **설명 정정 (17m 2 절):** env 1 은 「teacher 정책을 돌린다」 가 아니라 runner 초기화에 필요한 **보조 환경**이고 두 로봇 모두 student 추론을 쓰며 **평가는 env 0 하나**. 결과 문구는 17m 6 절 문장 그대로. 새 변이 5 개 (M79 ~ M84) 가 한 시험에 몰린다는 lead 설명은 정정됨: M84 는 실제 `eval_env_problems` 를 부르고 나머지 4 개 (M79 · M81 · M82 · M83) 만 문자열 정적 검사. 내가 17m 의뢰문에서 보조 환경을 「teacher」 로 쓴 것이 그 점을 흐렸다.
- **smoke 후 볼 것:** S1 (2 환경 · judged 0 · 보조 1 · state 30 black 주입 뒤 재렌더 회복 · env 0 연속 궤적 · 영상 전체에서 보조 로봇 · 그림자 · 반사 · 카메라 대상 변경 없음 · 1 환경 영상과 이어 붙이지 않음) · S2 (probe 지원 여부와 S1 과 같은 251 상태를 나눠서) · S3 (`FRAME_GATE frame 20` 의도한 재렌더 실패 · 다른 예외를 성공으로 안 셈) · 보조 환경 실제 좌표 · 메모리 최고와 최저 · 시도 시간. smoke 의 세 장면은 교란 없는 base 라 실제 밀기와 마찰 반응은 검증하지 않음.
- **순서:** v6 full 이 끝남 (59/75 · 08:09 · 약 08:30 추정) → v6 자식 종료 확인 → RAND smoke (위 조건) → ASTRA 17n 이 v2 재시도를 허용하면 v2 단회 (17k 5 절 조건 · 새 tag) → 한 번에 하나의 Isaac 으로. 둘은 서로 겹치지 않게.
- **ASTRA 컨텍스트 9 % 남음 (08:09):** 17n 을 보냄 (08:10 · 범위를 좁힘). 재시작은 팀장 승인 (super2) 대기.

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
