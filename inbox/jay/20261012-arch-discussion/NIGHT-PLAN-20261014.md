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

## ASTRA 17u 판정과 1043 채점기 보류 (10/15 02:40)

- **17u (02:3x · 전문 읽음): 고칠 것 · 진단 기동과 승인 json 발급 보류.** 닫힘: 17t 의 PID 재사용 반례 · 승인 필드 값 검사(30 개 거절 + 별도 검사) · 필수 지문 누락 held. 열다섯 시험 모두 종료 0(109.13 초), 코드 변이 9 건(기존 6 + 신규 3)과 입력 변조 12 건은 따로 센다.
- **남은 기동 차단 결함 둘:** (P1-1) 스냅샷과 생성 시각 조회가 다른 시각이라, 살아 있는 부모 아래 자식 PID 가 사라진 뒤 **무관한 프로세스가 같은 PID 로 재사용**되면 등록되어 STOP 에서 kill 이 호출됨 (P1-2) 부모 생성 시각을 못 읽어 unknown 으로 둔 상태에서 그 아래 자식이 known 에 못 올라, 루트와 부모가 자연 종료하면 **자식이 살아 있는데 rc 0 으로 반환**(후손 놓침). ASTRA 결론: 공유 워크스테이션의 자동 종료를 허용하는 진단에서는 이 위험을 수용하지 않음. **Windows Job Object 같은 OS 소유 경계(시작 전 편입 · 후손 이탈 방지 · 전체 종료 확인 · 편입 실패 시 기동 거절)가 필요.** 현재 조회를 한 번 더 넣는 것만으로는 원자적 소유권이 생기지 않음.
- **운영 참여 확인(소스 기준):** 실제 슬롯은 `_eval/isaac_slot_v3.py` (`_eval/slot/` 아래가 아님). 변환 lock 후보 `_eval/slot/isaac_convert.lock`, registry 후보 `_eval/slot/isaac_usd_registry_v3.json`(슬롯의 registry 기본값은 아직 구형이라 `--registry` 를 생략하면 안 됨). **전체 실행 lease 는 조사한 어느 실행기(미경험 v6 · CE12 · RAND · 구형 v3.7 평가 · 슬롯)에도 구현돼 있지 않음.** 구형 v3.7 평가의 변환 lock 은 `_eval/out/isaac_convert.lock` 으로 다름. 17t 의 「기존 공통 lease 를 재사용하면 된다」 는 현 운영 사실이 아님.
- **보고 정정 요구:** `eval_changes` 전체를 「의도한 차이」 로 제외하는 것은 너무 넓음(reset · push · curriculum 까지 포함 · 임의 변경도 equal 로 나옴) → 버퍼 항목만 정규화. `non_try` 에 준비 시간이 이미 포함돼 `startup` 을 더하면 중복, 전체 비용은 `attempt_total_wall_s`. 기본 run 이 미완료인데 `repeat_not_needed` 로 표기하는 것은 「판정 전 미실행」 으로.
- **견적:** 진단 시작까지 2 ~ 5 시간 + 팀장 결정 대기(소유 경계 수정 1 ~ 3 h + 영향 재검 0.5 ~ 1 h + 참가 실행 관문 · 배치 · 동결 0.5 ~ 1 h). 팀장 결정(GPU · 창 · 마감 · 위험)과 lead 의 참가자 · runtime · 입력 조사는 수정과 병행 가능. 수정 중인 판으로 먼저 기동하고 나중에 승인받는 병행은 하지 않음.
- **lead 판단(제안):** 1043 진단은 20 분짜리 GPU 일인데 위 기동 조건을 채우려면 소유 경계 수정 + 운영 실행기 전체 연결 + ASTRA 재검이 더 필요하고, Codex 주간 한도가 22 % 남았다. 지도 실험(핵심)이 같은 한도를 쓰므로 **1043 채점기 고침은 보류하고 sol 을 지도 실험 학습 연결(`TASK-codex-worker-s2-step2.md`)에 쓴다.** 되돌리려면 팀장 말씀. 1043 사본 · 판정 · 작업서는 모두 보존.
- **놀고 있는 GPU (02:40 기준):** GPU 0 05:46 부터 약 21 시간 · GPU 1 09:40:37 부터 약 17 시간. 둘 다 계산 프로세스 0. 허용된 기동 없음.

## 지도 실험 학습 연결 2 단계 · 3 단계 · ASTRA 17v · Linux 멈출 선 (10/15 04:0x)

- **팀장 답(03:5x):** (1) Omniroute 는 pipeline 과 시험 중이라 팀장이 끝나면 직접 말함 (2) Codex 주간 한도가 99 % 가까이 차면 reset 권이 있으니 ASTRA 세션에 말해 반영하게 하면 됨(한도 때문에 검증을 줄이지 않는다) (3) Linux 날짜는 super2 에게 확인 (4) 주된 실험을 어느 선에서 멈추고 Linux 로 갈지 제안 (5) GPU 는 로컬 자원이라 세션 한도와 무관, 계획만 잘 세우면 단계별로 계속 돌릴 수 있음.
- **sol 2 단계 후보(03:02 보고 · 전문 읽음):** `s2_ppo.py` · `s2_runner.py` · `s2_env_adapter.py` · `s2_terrain_overlay.py` · 사전 등록 초안 · 기동 스크립트 초안(무조건 `exit 99`) · 시험. 가짜 환경 시험 26 PASS · 코드 변이 6/6 CAUGHT. **한계: 실제 Isaac 학습 진입점 없음, 실제 RayCaster 미접속.** lead 재실행(03:48:44 ~ 03:56:41) 네 실행 모두 종료 0: 1 단계 14/14(292 칸) · 1 단계 변이 69/69(소스 변이 68 + 입력 해시 관문 변조 1) · 2 단계 26 PASS · 2 단계 코드 변이 6/6, 후보 16 파일과 부모 두 파일 해시 전후 일치. 사본 `night-tools-20261013/s2_step2/`(커밋 9d13c726).
- **ASTRA 17v 의뢰(03:59):** 후보 정상성 · 첫 GPU 일(Isaac 접속 확인, 학습 없음)의 범위 · 17u 소유 경계 결함이 S2 의 기존 사슬에도 적용되는지 · **단계별 사슬 승인**(접속 확인 → smoke → 짧은 A/B 를 합격 판정 스크립트로 잇고 사슬 전체를 한 번에 승인) 가능 조건 · 사전 등록 값 권고 · 「지도 효과」 기준 제안(목표 칸마다 95 % 구간 하한 > 0 이고 평균 차 ≥ 10 %p).
- **sol 3 단계 작업(04:00 맡김):** `TASK-codex-worker-s2-isaac-entry.md` : Isaac 접속 확인 스크립트와 CPU 검증기 · 실제 학습 진입점 후보 · 단계별 사슬 정의와 합격 판정 스크립트 · 기동 스크립트 초안 갱신. 모두 CPU 전용, 실행 금지.
- **Linux 날짜(super2 04:05 답 · #550):** 설치 마감 목 10/15 · 마지노선 토 10/17 에 Linux 에서 이어 작업(런북 0-1, 팀장 10/12 23:50 채팅과 10/13 super 재확인). 팀장이 super2 에게만 따로 말한 날짜는 기록에 없음. 순서: NAS 백업 → 설치 → lead 가 코드 이전 → 같은 숫자 시험 → 통과 뒤 학습 재개. 아직 못 정한 것은 설치 시각, 부트로더(C: 물리 제거 여부), 비밀값 길, 세션 정지 승인. Windows GPU 정지 구간 약 3~5 시간(추정), 같은 숫자 시험까지 하루. super2 제안 멈출 선: **새 GPU 학습을 시작하기 직전**. 진행 중 학습은 가져가지 않고 S2 A/B 학습은 Linux 같은 숫자 시험 통과 뒤. 멈출 조건 (a) GPU 계산 0 (b) 마지막 결과 manifest 닫힘과 ASTRA 판정 끝 (c) NAS 증분 백업 대조 (d) 코드 커밋 · push, `_eval` python 68 개 대조, census 0 (e) Windows 기준선 `traj.npz` sha256 기록 (f) 모든 세션의 이어 갈 자리 기록.
- **lead 제안(팀장 결정 대기):** 팀장 원칙(GPU 는 놀면 안 됨, 방향 먼저)과 super2 선(S2 학습을 Linux 에서)이 충돌한다. 조정안: Windows 에서는 **짧은 방향 확인 사슬(접속 확인 → smoke → 짧은 A/B)까지만** 돌려 그 묶음이 끝나 (a)~(f) 가 참이 되는 순간 멈추고, 긴 학습은 Linux. 방향 확인 결과는 «방향 근거»일 뿐 Linux 의 부모로 잇지 않는다(기존 ASTRA 17 규칙). 마지노선 10/17 에 Linux 에서 일하려면 설치가 늦어도 10/16 에는 시작해야 하는데(설치 + 같은 숫자 시험 하루) 짧은 A/B 는 10/16 ~ 17 에 끝날 수 있어 **날짜를 10/18 안팎으로 미룰지 팀장 결정이 필요**. 권고: 미루되 Windows 사슬 종료 상한을 먼저 못 박기.
- **Windows 기준선 후보(미확인):** 10/13 14:12 의 `_eval/out/cq_test_8d384fcb_g0t141025p134176_ka_orig/` 는 체크포인트 SHA256 `c8951b79…f47e8`(E1 20000) · 칸 stop03 이고 `traj.npz` SHA256 `d53786e0501f2d8f69addca89ee1751e9574452f23053eb19d924cf8581cc6dc`. 100 판 · noise 켬 · 시드 1000 조건이 같은지는 ASTRA 확인 전이라 후보일 뿐이다. 같다면 설치 전 별도 GPU 일이 필요 없다.
- **한도 대비:** Codex 주간 20 % 남음. 99 % 가까이 차면 ASTRA 세션에 reset 권 반영을 말한다(팀장 지시). 1043 채점기 고침은 한도 때문이 아니라 우선순위 때문에 S2 사슬 뒤 대기열.
- **놀고 있는 GPU (04:05 기준):** GPU 0 05:46 부터 약 22 시간 · GPU 1 09:40:37 부터 약 18 시간. 둘 다 계산 프로세스 0. 허용된 기동 없음. 가장 빠른 실제 GPU 일 = Isaac 접속 확인(ASTRA 17v 판정 + sol 3 단계 + 사슬 검증 뒤, 빨라도 오전 중으로 추정, 미확인).

## Linux 이전 날짜 변경 전달 (10/15 04:1x · super2 경유 · 팀장이 super2 창에 직접 입력했다고 전함)

- **전달된 팀장 말(원문 요지):** 학습이 필요한 실험이 있다면 방향을 빨리 잡고 토요일까지 돌리는 게 의미가 있을 때, 거기서 학습이 다 된 것으로 방향성을 확정하고 토요일(10/17) 오후에 Linux 로 넘어가도 좋다. 의미 없으면 일찍 넘어가도 된다. 조건은 lead 판단에 맡김.
- **확인 수준:** 팀장이 직접 lead 채팅에 쓴 것이 아니라 다른 세션이 전한 말이다. lead 는 이것을 승인이 아니라 정보로 기록하고, 아래 판단은 lead 의견으로 팀장 채팅에서 한 줄로 확인받는다. 팀장 답이 아직 없는 두 가지(1043 채점기 대기열 · 「지도 효과」 기준)는 받지 못한 것으로 적는다.
- **lead 판단:** 지도 실험의 짧은 방향 확인 묶음(접속 확인, smoke, 짧은 A/B)은 토요일까지 Windows 에서 돌리는 것이 방향 확정에 의미가 있다. 따라서 **Windows 묶음 종료 상한 = 토 10/17 정오, Linux 설치는 토요일 오후**로 계획한다. 그 시각 전이라도 묶음이 끝나 super2 멈춤 조건 (a)~(f) 가 참이면 일찍 멈춘다. 토요일 정오에 못 끝난 학습은 가져가지 않고 중간 상태로 남기며 방향 근거에서 제외한다.
- **super2 가 준비한 것:** 설치 USB 는 팀장이 Ubuntu 24.04.4 부팅 디스크를 이미 만듦. `C:\Users\AI-WS01\mai-tools\ubuntu-usb-data-20261015\` 에 설치 스크립트 · 공개키 · 런북 사본 · 해시 목록. Windows 쪽 증분 백업과 마지막 쓰기 시점은 토요일 정오 이후.

## 팀장 직접 확인과 새 지시 (10/15 04:1x · lead 채팅)

- **팀장 답:** 「응 너가 제안한 방향대로 진행해」. lead 가 04:0x 에 제안한 세 가지: (1) Linux 설치는 토요일 오후, Windows 묶음 종료 상한은 토 10/17 정오(super2 경유 전달과 같은 방향이었고 이제 팀장이 lead 채팅에서 직접 확인) (2) 1043 채점기는 지도 실험 사슬 뒤 대기열 (3) 「지도 효과」 기준(목표 칸마다 95 % 구간 하한 > 0 이고 평균 차 ≥ 10 %p). 문구가 세 제안을 따로 짚지 않았으므로 틀리면 팀장이 고친다.
- **새 지시(원문 요지):** GPU 는 절대 멈추지 않고 계속 가동한다. 세션은 멈출지언정 GPU 는 실험을 계속 진행할 수 있게 해 둔다. 지형 지도를 줬을 때 의미가 있는지 파악하고, 그 결과로 앞으로의 실험 방향을 정한다. 다른 논문의 구조를 우리에게 적용해 돌려볼 수 있으면 돌려서 의미가 있다고 판단되는 것을 보고, 그 뒤 Linux 로 넘어간다.
- **lead 조치(04:1x):** (1) ASTRA 17v 에 추가 전달: 세션과 분리된 무인 사슬 실행기, 마감까지 GPU 두 장을 채우는 시간 상자 확장, 학습 중 지형 조우 기록의 A 대 B 비교로 방향 판정, 기준 사전 동결, 교체 가능한 지도 encoder 로 다른 논문 구조를 추가 arm 으로 (2) sol 3 단계(접속 확인 · 학습 진입 · 단계별 사슬)가 진행 중이고, 그 보고 뒤 이어서 4 단계 작업서 `TASK-codex-worker-s2-unattended.md`(무인 사슬 실행기 · 교체 가능한 encoder(mlp 와 AME-2 식 attention) · A/B 비교기)를 하도록 대기열에 보냄.
- **정직한 한계:** 무인 실행기가 있어도 (a) ASTRA 의 사슬 승인과 첫 접속 확인 전에는 GPU 가 빈다 (b) 단계 합격 판정이 보류면 사슬이 그 자리에서 멈추고 사람 · ASTRA 가 올 때까지 GPU 가 논다. 보류 때 GPU 를 채울 안전한 예비 일감(예: 이미 끝난 체크포인트의 읽기 전용 평가)이 있는지는 아직 정하지 않았다. 다음 ASTRA 의뢰에 넣는다. (c) 세션이 끊기면 lead 의 점검 예약(cron)도 세션 안 장치라 같이 멈추므로 상태 파일 감시는 세션 밖 도구(super2 · Orca)에 걸어야 한다.
- **한도:** Codex 주간 18 % 남음. 한 시간에 약 3 %p 씩 줄고 있다. 99 % 가까이 차면 ASTRA 세션에 reset 권 반영을 말한다.
- **놀고 있는 GPU (04:16 기준):** GPU 0 05:46 부터 약 22.5 시간 · GPU 1 09:40:37 부터 약 18.5 시간. 계산 프로세스 0. 허용된 기동 없음.

## ASTRA 17v 판정과 sol 합쳐진 작업 (10/15 04:3x)

- **17v(04:2x · 전문 읽음): 고칠 것 · 현재 GPU 기동 보류. 그러나 세션 독립 무인 사슬이 토요일 정오(epoch 1792206000)까지 고정 증분을 자동 진행하는 방식은 채택 가능.** 조건: 수정된 실행 · 판정 코드와 유한한 예산을 동결. 승인 단위를 「프로세스 한 번」에서 「한 번 claim 하는 유한한 사슬」로 넓힘.
- **CPU 후보 결함(P1):** (1) 시간제한 종료(timeout)를 진짜 terminal 과 섞음(부모는 reward 에 gamma × value 를 더하는데 후보는 bootstrap 을 끊음: 알려진 답 부모 2.98 대 후보 1.00) (2) 오래된 센서 packet 이 번호만 정상 증가해도 valid (3) yaw NaN 이 기하 검사를 우회. 보완: 조우 기록기가 중복 사건을 그대로 셈 · PPO 부모 차이(두 군 surrogate 평균의 합 대 전체 평균, advantage `std()` 정의, 순열 재사용) 등록 · `collect()` invalid 의 지속 보류. 재실행은 독립 확인: 14/14 · 소스 변이 68 + 입력 해시 변조 1 · 26 PASS · 코드 변이 6/6, 합계 493 초.
- **첫 GPU 일(학습 없는 접속 확인) 고정 시험안:** 8 환경(평지 · 0.20 m 단차 · 틈 · 비대칭 징검다리 × yaw 0/90°), 환경당 256 step, 정답표(x-fast 17×11 · index 0 = (-.8,-.5) 등 · 20 m offset 이중 가산 금지 · miss 와 깊은 유한 바닥 구분 · 허용 오차 후보 2 mm). 이 시험은 전체 장기학습 구현의 완성을 기다리지 않는다.
- **기존 사슬 재사용:** 17u 소유 경계 결함의 직접 대상은 1043 의 새 감시기. 그러나 변경하지 않은 `_eval/isaac_slot_v3.py:145~152` 도 저장 PID 로 새 프로세스를 만들어 PID 재사용 시 무관한 프로세스에 kill 을 호출(가짜 OS 로 재현), slot / guard 는 직계 자식 기준. 최소 조건: **세션과 분리된 감독 프로세스가 실행 가족을 OS 수준으로 묶고(Windows Job Object 등) 그 가족만 중단.** GPU UUID 별 전체 실행 lease 와 호스트 공통 USD 변환 lock 구분.
- **사슬 계약(채택 조건):** 단회 claim 은 사슬 전체에 한 번, A/B 는 stage/arm 별 한 번씩 파생 · 영수증 해시 연결 · 30 초 heartbeat · 마지막 증분 크기 표(500/250/100/50/10/1) + 최소 15 분 reserve · 절대마감은 모든 Windows GPU 작업의 종료 상한 · A/B 는 별도 1-GPU 프로세스(DDP 아님) 같은 경계에서만 짝 판정, 한쪽 고장이면 둘 다 중단. 단계 출발 예산: 0 단계 15 분, smoke 각 30 분(timeout 후보). **고장 때 GPU 를 채우려면 이미 승인된 별도 후보/시드의 대기열을 함께 동결해야 하고, 없으면 보류가 맞다.**
- **수치 출발값(ASTRA 권고, 승인값 아님):** E1 20000 · full_freeze · LR 0.000170859375 · N=1,024/arm · smoke seed 101, 짧은 학습 seed 42 · smoke 200 · 짧은 비교 2,000 · 연장 +500 update · gap 15 % · stones 15 % · 나머지 70 % · 체크포인트 0/200/2,000/+500 경계 · 최종 비교는 마감 전 양쪽이 끝낸 마지막 공통 경계(좋은 중간 checkpoint 선택 금지).
- **지도 효과 기준(수정):** 두 Wilson 하한의 차를 B−A 구간으로 쓰면 틀림. 배정 대비 통과율을 주 모니터, 접근 대비를 보조. 같은 update 창 · 지형 · 난이도 비교, 비중첩 500 update 창 + 누적 곡선. 지형 seed · 환경 · 시간 묶음 block/cluster 재표집은 탐색용. 매 증분은 「탐색 방향」, 정식 판정은 마지막 공통 경계에서 한 번. 한 학습 seed 의 on-policy 자료에서 기준을 넘어도 일반적 · 인과적 효과가 입증된 것은 아님(「해당 창의 관찰 기준 충족」). 독립 평가 첫 pilot 은 지형당 200 case(탐색 예산, +10 %p 검출에 충분하다는 수치는 아님), 확증은 학습 seed 최소 3개 검토. 「이 조건에서 못 배웠다」를 MoE-CTS 불가능으로 확대하지 말 것.
- **encoder 추가 arm:** 세 군(A · B-mlp · B-attn)은 탐색 패키지 비교로만 가능. 「arm 사이에 다른 것은 encoder 구조뿐」 은 틀림(A 와 B 는 지도 정보가 다르고 두 B 는 구조가 다름). 구조 효과까지 분리하려면 A-mlp/B-mlp/A-attn/B-attn 2×2. attn 은 미작성 · 미검증이라 첫 사슬 묶음에 못 넣고 새 manifest / 승인 묶음으로 추가.
- **견적:** 후보 수정 · 실제 진입 코드 · 감독기 · validator 의 작성 시간이 병목이고 GPU startup · 초당 step 은 미측정이라 시각은 약속할 수 없다(ASTRA). 개발 병행은 가능.
- **sol 조치(04:31):** 합쳐진 작업서 `TASK-codex-worker-s2-17v-fix.md`(1 먼저 고칠 것 → 2 접속 확인 정답표와 Isaac 미확인 호출 여섯을 Isaac Lab 소스 정적 확인으로 해결 → 3 무인 사슬: 소유 경계 · 영수증 · 상태 파일 · 마감 · 교체 가능 encoder · 비교기)를 보냄. 3 단계 보고(04:20)의 미확인 호출 여섯: `env_origin_w`/terrain accessor, 센서 timestamp, 드라이버 판 읽기, 환경 상태 저장 · 복원 API(`NotImplementedError` 로 닫음), 조우 이벤트 · 충돌 메시 대조, 한 AppLauncher 안 순차 `gym.make`.
- **팀장 의견(04:3x):** 「지도를 보면 당연히 더 좋겠지」, 하나씩 검증하며 방향을 빨리 확정, 하루 반나절이면 파악 가능하지 않냐, GPU 가 24 시간 쉰 것이 아깝다, 정확한 설계가 있으면 새 encoder · AME-2 앞단 · 다른 논문 적용까지 갔을 것. lead 답: 10/17 정오는 상한이고 목표가 아니다(채팅). 한 사이클(실험 → 평가 → 다음 설계 → 실험)에서 다음 설계를 GPU 가 도는 동안 미리 한다.
- **한도(04:30):** Codex 주간 16 %. 약 3 %p/시간으로 줄어 오전 9~10시에 바닥. 그 전에 ASTRA 세션에 reset 권 반영을 말한다.
- **놀고 있는 GPU(04:31 기준):** GPU 0 약 22.8 시간, GPU 1 약 18.8 시간. 계산 프로세스 0. 허용된 기동 없음.

## 운영 사이클 (팀장 10/15 04:3x 확인 · 이 절이 정본)

팀장이 정한 흐름: 설계, ASTRA 검증, 그것을 바탕으로 lead 가 sol 에 작업 지시, GPU 실제 작업, 결과 보고, lead 가 결과를 파악 · 분석, ASTRA 가 검증하고 설계 방향 검토, lead 가 받아 설계 방향을 확인하고 GPU 가 놀지 않게 sol 에 전달.

**보완(lead 제안, 팀장 확인 대기):** 이 흐름을 한 줄로만 돌리면 결과가 나온 뒤 분석, ASTRA 검증, sol 지시를 기다리는 동안 GPU 가 논다(사이클마다 약 1~2 시간 추정). 그래서 두 줄로 나눈다.
- **GPU 줄(기계, 기다리지 않음):** 승인된 사슬이 마감까지 단계 · 고정 증분을 자동 진행한다. 합격 판정은 스크립트가 한다. 세션과 무관하게 돈다. 다음 일감(이미 검증 · 승인된 대기열)이 결과 보고 전에 걸려 있다.
- **판단 줄(사람 · AI 세션):** 설계, ASTRA 검증, 결과 분석, 다음 설계를 **GPU 가 도는 동안 병행**한다. 결과가 나오기 전에 다음 실험의 설계와 코드와 검증을 끝내 둔다(사전 등록한 갈래: 지도 효과 큼 / 일부 / 없음). 판단이 오면 대기열에 한 칸 넣고 필요하면 증분 경계에서 방향을 바꾼다.
- 규칙: 결과 분석은 lead 의 요약이 아니라 ASTRA 의 원자료 재계산을 사실로 쓴다 · 기준(성공 · 보류 · 중단)은 결과를 보기 전에 파일로 동결 · 사슬 안의 변경은 새 승인 없이, 구조 · 소스 · 보상 · 지형 · PPO 변경은 새 판정(17v 4 절).
- 이 흐름의 어느 칸에서도 GPU 가 비면 보고에 비운 시작 시각과 이유를 적는다.

## 팀장 위임과 첫 GPU 일 앞당기기 (10/15 04:5x)

- **팀장 말(04:5x):** Omniroute 는 pipeline 에게 이야기했고 **잠시 홀드**. **실험 계획과 GPU 사용은 lead 가 권한대로 해도 된다.** sol 은 GPU 를 돌리는 정도의 역할일 텐데 왜 60 분이나 걸리는지, ASTRA 검증 25 분도 왜 이리 긴지 질문.
- **lead 해석:** 위임은 실험 계획(값 선택, 순서, 갈래)과 GPU 사용 우선순위에 대한 것이다. 「GPU 는 ASTRA 허용 범위만」 이라는 기존 원칙은 그대로이며 허용 없이 띄우지 않는다. 계획 값은 ASTRA 권고 범위 안에서 정하고 기록한다.
- **sol 이 오래 걸리는 까닭:** sol 은 GPU 를 돌리는 역할이 아니라 후보 코드를 쓰는 역할이다(GPU 는 사슬 실행기가 돌린다). 한 작업이 크고(수정 + 센서 확인 + 소유 경계 + 사슬 + 비교기 + 시험 + 변이 + 보고), 변이 시험만 한 번에 7~8 분 걸린다. 이를 쪼개지 않은 것이 lead 의 지시 방식 문제였다.
- **조정(04:56):** sol 에 0 단계 묶음(A: 센서 packet · yaw 수정, 접속 확인 스크립트와 검증기, 0 단계만 돌릴 최소 감독기 · 합격 판정)을 먼저 끝내 중간 보고(`REPORT-s2-step4a.md`)를 내게 하고 이어서 B(학습 연결 나머지)로 가게 함. 17v 가 접속 확인은 전체 학습 구현의 완성을 기다릴 필요가 없다고 했다. A 는 lead 재실행 후 ASTRA 에 좁혀서 보낸다.
- **ASTRA 검증 시간을 줄이는 방법:** 의뢰문에 바뀐 파일 · 해시 대응표 · diff 만 주고, 안 바뀐 파일의 회귀는 lead 재실행 결과의 해시 일치로 갈음하게 요청하고(독립 재실행은 바뀐 부분과 반례에 집중), 물음 수를 줄인다. 깊이를 희생하지는 않는다(17v 의 P1 셋은 독립 반례에서 나왔다).

## 0 단계 묶음 A 도착과 ASTRA 17w 의뢰 (10/15 05:1x · 팀장 「작업 문제 없이 진행 · GPU 두 장 알아서」)

- **sol A 중간 보고(05:0x · 전문 읽음):** 오래된 센서 packet 과 yaw 비유한값 두 P1 수정, 8 환경 × 256 step 접속 진단과 17v 정답표 검증기, Windows Job Object 최소 감독기(`s2_job_owner.py` · `s2_resource_lease.py` · `s2_zero_supervisor.py`)와 0 단계 판정. **한계: 이 스크립트로 첫 실제 캡처를 하면 설계대로 HOLD**(mesh · 충돌체 · 고정 자세 증거 필드가 비어 있음). 즉 첫 GPU 일은 정보 수집 단계이고 이 HOLD 를 PASS 로 위장하지 않는다. 기존 slot / guard 를 호출하지 않고 감독기의 Job Object 안에서 직접 기동하는 방식을 제안(PID 재사용 kill 경로 회피).
- **lead 재실행(05:12:27 ~ 05:12:44):** `lead_0516` 정상 7 개 종료 0 (PASS 라벨 44) · A 코드 변이 5/5 CAUGHT(한 줄 치환, 첫 FAIL = want). sol 목록 24 개 중 23 개 해시 일치, 시험 파일 `test_s2_step4_mutants.py` 하나는 sol 이 B 변이를 얹으려고 고쳐 다름(A 실행기는 `--only` 로 A 변이 5 개만 지정). 사본 `night-tools-20261013/s2_step4a/`.
- **lead 측정(05:11):** GPU UUID 둘 · 해석기 판 · IsaacLab / go2_rl_robotlab 커밋 · E1 20000 해시 · slot 도구 해시. 예약 작업은 NAS 백업 하나뿐, Isaac / Kit 프로세스 없음. `night-tools-20261013/s2_lead_measure/`.
- **ASTRA 17w(05:14, 좁은 의뢰):** P1 둘 닫힘 여부, 접속 확인 정답표 대로인지와 「정보 수집 단계 허용」 여부, Job Object 소유 경계 충분성(15 분 단회 한 번), slot / guard 를 쓰지 않는 직접 기동의 대가, 첫 GPU 일 한 번의 허용 조건(GPU 0 에 한 번, GPU 1 은 데스크톱 앱 사용 중이라 이번에는 쓰지 않는 안), 견적과 GPU 1 에 안전하게 올릴 일 유무.
- **두 GPU 운영안(lead 계획, 권한 위임에 따름):** 0 단계는 GPU 0 에 단독 한 번. 이후 사슬(묶음 B)은 A / B 를 별도 1-GPU 프로세스로 GPU 0 · GPU 1 에 한 arm 씩, 같은 비교 경계에서만 짝 판정(ASTRA 17v 4 절). 위험: GPU 1 은 데스크톱 앱이 약 5.9 GB 를 써서 VRAM 여유가 작다. smoke 에서 양쪽 N=1,024 가 들어가는지 재고, 안 들어가면 양쪽 N 을 함께 줄인 새 계획(결과 뒤 한 군만 줄이지 않음).
- **놀고 있는 GPU(05:15 기준):** GPU 0 05:46 부터 약 23.5 시간 · GPU 1 09:40:37 부터 약 19.5 시간. 계산 프로세스 0.

## ASTRA 17w 판정과 sol A2 작업 (10/15 05:3x · 팀장 취침 직전)

- **17w(05:2x · 전문 읽음): 고칠 것. 현재 묶음 그대로의 GPU 기동은 보류하되, 누락 의존 파일 · 잘못된 환경 연결 · 장치 / 자원 보호 · 실패 자료 보존을 고친 뒤 lead 권한으로 GPU 0 단회 정보 수집(최대 900 초)을 진행할 수 있다. 그 HOLD 를 0 단계 합격이나 학습 허용으로 읽지 않는다.** 지난 위임(팀장 「GPU 사용은 lead 권한」)을 인정해 팀장 재승인은 요구하지 않음.
- **결함:** (1) lead 가 해시 목록대로만 복사해 고정 A 사본에 `s2_terrain_overlay_17v.py` · `s2_runner_17v.py` · `s2_ppo_17v.py` 가 빠졌다(`import` 가 `ModuleNotFoundError`). lead 의 복사 실수이며 작업자가 보고한 코드의 결함이 아니다. (2) 환경 연결 오류: `Isaac-Velocity-Rough-Unitree-Go2-v0` 의 지형 여섯 키에 `gap` · `stepping_stones` · `flat` · `obstacles` 가 없어 `TerrainOverlayError`. (3) 검사기 거짓 PASS 반례 다섯(height NaN · 고정 구간 1 개 · root X +100 m · 장애물 제거 · 평지 world Z 정답 계산). 로봇 이동에 맞춰 바닥을 올리는 합성 fixture 도 문제. (4) 센서 tracker 가 갱신 순간의 raw digest 를 고정하지 않아 버퍼를 직전 자료로 돌려놓아도 재봉인됨. (5) 첫 수집 자료 보존 부족: 256 행을 메모리에 모은 뒤에만 저장, 시작 시각 오기록, 자식 stdout / stderr 미연결. (6) 직접 기동의 대가: 호스트 USD 변환 lock 정의만 있고 호출 안 됨, UUID → index → PCI → 실제 장치 결박 없음(UUID 를 바꿔도 PASS), 디스크 상한은 양수 여부만, 승인이 묶는 파일이 네 개뿐.
- **정정:** lead 가 「각 한 줄」 이라고 쓴 변이 설명 중 `yaw_finite` 는 유한성 검사 **두 곳**을 제거하고 `claim_exclusive` 는 0 단계 감독기가 아니라 학습 사슬의 `s2_chain_runner.py` 를 바꾼다(0 단계 claim 은 정상 반복 호출 거절 시험만 있음).
- **단회 수용 범위(17w 3 절):** 감독기 세션 분리 · hang · 다른 실행기 lease 불참은 15 분 단회에 한해 「참석자가 터미널을 유지하는 단회 관찰」 + 예약 구간 배제로 수용 가능. 무인 사슬 전에는 세션 종료 뒤 생존 · 독립 watchdog · 공통 lease 시험이 필수. LLM 이 잠깐 깨어 있는 것은 참석자가 아니므로 무인 단회로 돌릴 계획이면 독립 마감 장치를 먼저 넣어야 함.
- **첫 GPU 일 권고값(출발점, 승인값 아님):** `stage0_information_only`, GPU 0 (UUID `GPU-c08e23b0-…`), 8 환경 · 256 step · 16 warmup · 개입 64 / 128 / 192, optimizer 0, 1 회 · retry 0 · 하류 없음, `max_wall_s=900`, 기동 전 여유 ≥ 8 GiB · 실행 중 여유 < 2 GiB 이면 보류, 출력 ≤ 1 GiB · 기동 전 디스크 여유 ≥ 2 GiB, criteria .002 / .002 / .005. 이 실행의 claim `stage0-capture-<attempt>` 은 이후 사슬과 분리. 결과 보고 문구: 「정보 수집 N/256 step, optimizer 0, 결과 HOLD, 사유, GPU / 소요 / 최소 여유, 다음 학습 미실행」.
- **GPU 1:** 지금 안전하게 올릴 승인 · 완결된 별도 작업이 확인되지 않음. 실패한 바이트로 예약 재시도를 돌려 GPU 가동률을 채우는 것은 진척이 아님.
- **견적(추정):** 수정 30~90 분 + 기동 직전 확인 5~10 분 + 수집 최대 15 분. 측정된 ETA 아님.
- **조치(05:31):** sol 에 `TASK-codex-worker-s2-17w-fix.md` (A2) 를 B 보다 앞세워 보냄. 완결된 묶음을 `s2_step4a2_frozen` 에 복사하고 clean-import 시험을 넣게 함. 끝나면 lead 재실행 → ASTRA 에 수정분만 좁혀 확인(17x) → lead 가 승인값을 동결하고 기동 직전 확인 스크립트를 돌린 뒤 GPU 0 한 번. 사람이 자는 동안 15 분 단회를 무인으로 돌릴지는 독립 마감 장치 유무로 정한다.
- **GPU 감시 도구 제안:** 팀장 질문에 대한 의견을 `PROPOSAL-gpu-monitor.md` 에 정리(커밋 55274624).

## sol A2 도착 · ASTRA 17x 의뢰 · 독립 watchdog · reset 권 (10/15 06:4x ~ 07:0x)

- **하트비트(06:48) 발견:** sol 과 ASTRA 두 Codex 창이 「Approaching rate limits · Switch to gpt-6-luna?」 선택창에서 입력 대기로 멈춰 있었다(sol 은 A2 를 06:05 에 끝낸 뒤, ASTRA 는 05:56 에 답한 뒤). lead 가 두 창에 `2`(Keep current model, 모델 변경 없음)를 보내 닫았다. 「never show again」 은 고르지 않았다(지속 설정 변경이라 팀장 확인 대상). 이 선택창은 한도가 줄 때마다 다시 뜰 수 있어 자는 동안 작업이 멈출 위험이 있다.
- **reset 권(ASTRA 답 05:56):** 주간 잔여 9 % (현재 8 %), 저장된 reset 권 1 회, 만료까지 23 일, 한도 소진 후에도 사용 가능, 사용하면 주간 초기화 날짜가 바뀐다. **ASTRA 는 「다른 세션이 전한 팀장 승인은 승인이 아니다」(공통 규칙 AGENTS.md 77 행) 때문에 팀장이 직접 승인해야 잔여 5 % 이하에서 쓸 수 있다고 했고 아직 쓰지 않았다.** 팀장이 일어나면 직접 확인받는다. 그 전에 한도가 바닥나면 Codex 작업(sol · ASTRA)이 멈춘다.
- **sol A2 보고(06:05 · 전문 읽음):** 39 파일 고정 묶음(`s2_step4a2_frozen`) 완성. 17w 지적 반영: 등록 Go2 환경 cfg 를 불러온 뒤 명시적 네 지형(flat · obstacles · gap · stepping_stones)으로 교체한 알려진 답 장면, 검사기의 거짓 PASS 반례 다섯 HOLD, 센서 tracker 가 갱신 직후 digest 를 동결, 256 raw 행 원자 기록, 장치 결박 · VRAM / 디스크 감시 · host USD lock, 기동 직전 확인 스크립트. 한계: 실제 Isaac 에서 cfg override 와 mesh 대응은 미확인, 진단 메타의 세 검증 bool 은 의도적으로 false, 독립 watchdog 은 sol 묶음에 없음(참석 단회 관찰 한정). 고정 폴더 clean-import 22 모듈 통과.
- **lead 재실행(06:49:43 ~ 06:50:17):** 복사본에서 `run_all_s2_step4a2.py` 종료 0 · 정상 12 개 PASS 라벨 84 · A 변이 5/5 · A2 변이 7/7 · `frozen_clean_import` 22. 고정 폴더 해시 39/39 일치. 사본 `night-tools-20261013/s2_step4a2/`(커밋 f5b78b15).
- **lead 가 만든 독립 watchdog(07:00):** 감독기와 별개의 분리 프로세스가 감독기를 (pid, 생성 시각) 으로만 식별하고, 하트비트 정지 또는 절대 마감 초과 때 그 감독기 하나만 종료한다(감독기가 죽으면 Job 핸들이 닫혀 OS 가 소유 가족을 종료). CPU 시험 13 PASS · 코드 변이 4/4 CAUGHT(첫 실행 3/4 였고 want 라벨을 lead 가 잘못 지정한 것을 정정해 재실행했음). 실제 Job 자식으로 확인한 시험은 아님. `night-tools-20261013/s2_step4a3_watchdog/`(커밋 d62e9e81).
- **ASTRA 17x(06:51 의뢰, 좁은 범위):** A2 의 17w 지적 항목 닫힘 여부 · 새 위험 · 무인 단회 가능성(watchdog 포함) · 기동 직전 값 · 견적. watchdog 은 07:01 에 추가분으로 전달. 판정이 오면: 값을 동결하고 `s2_stage0_prelaunch.py` 로 GO 확인 후 `s2_launch_stage0.py` 로 GPU 0 에 한 번(정보 수집 전용 · 최대 900 초). 판정이 「참석 단회만」 이면 팀장이 일어난 뒤로 미룬다.
- **놀고 있는 GPU(07:01 기준):** GPU 0 05:46 부터 약 25.2 시간 · GPU 1 09:40:37 부터 약 21.3 시간. 계산 프로세스 0. 이유: 첫 GPU 일(학습 없는 센서 접속 확인)의 검증이 끝나지 않았다.

## ASTRA 17x 판정과 lead 의 A3 수정 (10/15 07:48 확인 · 07:5x ~ 08:03 작업)

- **17x(07:07 작성, lead 는 07:48 하트비트에서 읽음 · 전문 읽음): 고칠 것.** 현행 A2 는 실제 PyTorch 장치 조회에서 수집 전에 막혀 기동 보류. 최소 수정 뒤 **참석 단회**는 가능, 독립 watchdog 을 붙인 현행 조합도 **무인** 요건은 미충족. 닫힘: 17w 의 거짓 PASS 반례 다섯, 센서 digest 동결, W 정상 시험 13 PASS, 실제 Job 연결(CPU 감독기를 W 가 종료하면 자식 · 손자 소멸).
- **17x 가 찾은 것:** (P1) `torch.cuda.cudart().cudaDeviceGetPCIBusId` 가 설치 torch 2.7.0+cu128 에 없어 `DeviceHold: cudart_bus_unavailable` 로 `IsaacProvider` 생성 전에 멈춤(가짜 객체 시험은 존재하지 않는 API 를 구현해 통과) / `step_zero` 등 개입 · step 단계 예외에서 raw 와 emergency raw 를 못 남김, `final_cfg.json` 은 gym 생성 성공 뒤에야 기록 / `capture` 의 `ray_index` (256,187) 대 검사기 (187,) 불일치로 정상 provider 도 `shape_or_steps` HOLD / 장면 값 `step_height_m=.3` 이 prelaunch GO / `usd_root` 가 자식에 연결 안 됨 / `competing_isaac_processes()` 가 `kit.exe` · `isaac-sim` 이름만 봄 / 출력 용량 중복 합산. (무인) watchdog 에 READY 핸드셰이크 없음 · 승인 결박 없음 · 단조 마감 없음 · NaN 마감 · heartbeat 거절 안 함 · 로그 실패가 kill 을 막음 · AccessDenied 를 정상 종료로 보고 · watcher 생존 확인 없음.
- **정정:** 전달 목록 `S2-STEP4A2-DELIVERY-SHA256.txt` 는 39 행이 아니라 6 개 기록물 목록(코드 39 개 일치와 구분). README 의 「모든 import 전에 launch 저장」 은 범위 과함(Python 초기 import 실패는 감독기 `attempt_start.json` 과 자식 로그가 근거). W 변이 4/4 는 제공 summary 와 라벨 일치까지만 확인(독립 4/4 실측 아님).
- **Codex 한도 5 % (sol · ASTRA 모두):** sol 에게 새 수정 라운드를 맡기면 한도가 바닥나 멈추므로 lead 가 최소 수정을 직접 했다. reset 권은 팀장 직접 승인이 필요(ASTRA 규칙).
- **lead A3 수정(`night-tools-20261013/s2_step4a3/` · 47 파일 · 커밋 45b0ea7f):** 장치 UUID(`get_device_properties(0).uuid` 정규화 비교, 원 값 선저장) · `capture` 전 단계 실패 보존(`stage_failure.json` + emergency raw) · `final_cfg.json` 선언을 `gym.make` 앞으로 · `ray_index` (187,) 로 접음 · 계약이 장면 값(step 높이 · 폭 · 비율 .25)을 답과 대조 · 감독기가 승인된 `usd_isolate_run_v3.py` 래퍼로 진단을 띄우고 `FOOTHOLD_USD_ROOT` · `FOOTHOLD_EXPECT_CONVERSIONS` 전달, 영수증에 isolate 상태 해시 · 중첩 출력 루트를 한 번만 계산하고 로그 폴더를 실행 전용으로 요구 · python 로 돌아가는 Isaac 도구 서명 탐지. **무인 요건 일곱 항목(watcher READY 핸드셰이크 · 승인 결박 · 단조 마감 · NaN 입력 거절 · 로그 실패가 kill 을 막지 않기 · AccessDenied 구분 · watcher 생존 확인)은 구현하지 않음.**
- **lead 재실행(07:56:34 ~ 08:01:25, 고정 폴더 복사본):** `run_all_s2_step4a3.py` 종료 0 · 정상 15 개 PASS 라벨 128 · A 변이 5/5 · A2 변이 6/6(옛 `torch_bus` 변이는 지워진 cudart 검사를 가리켜 폐기, A3 `device_uuid_compare_removed` 로 대체) · A3 변이 7/7 · 감시기 변이 4/4 · 깨끗한 폴더 import 22 모듈 · 해시 47/47. 정직한 기록: A3 변이 첫 실행 6/7 (`stage_failure_not_recorded` 가 `FAIL` 라벨 없이 예외로 끝나 시험에 존재 확인 라벨을 더함), 감시기 변이 첫 실행 3/4 (want 라벨을 lead 가 잘못 지정해 정정), A3 첫 전체 실행 1회는 오래된 변이 앵커와 해시 목록 파싱 차이로 실패해 고친 뒤 재실행.
- **ASTRA 17y(08:02 의뢰, 매우 좁은 범위):** 참석 단회 GO 조건과 기동 순서, 무인에 필요한 남은 목록과 우선순위, 첫 수집 뒤 CPU 로 미리 준비할 accessor. 한도 때문에 판정이 막히면 팀장 일어난 뒤 reset 권 승인이 먼저다.
- **놀고 있는 GPU(08:03 기준):** GPU 0 05:46 부터 약 26.3 시간, GPU 1 09:40:37 부터 약 22.4 시간. 계산 프로세스 0. 이유: 첫 GPU 일의 검증이 끝나지 않았다(ASTRA 17y 대기).

## ASTRA 17y 판정과 참석 단회 준비 (10/15 08:48 확인 · 전문 읽음 · 판정 파일 작성 08:10)

- **17y 첫 줄:** 조건부 허용. A3 고정 바이트로, 아래 입력을 동결하고 **실제 사람이 계속 참석하는** GPU 0 정보 수집 **한 번**은 진행할 수 있다. **무인 기동과 후속 학습은 허용하지 않는다.** 승인 JSON 은 아직 발급 안 됨(lead 가 동결해 만든다).
- **확인됨(ASTRA):** 47/47 해시, 수정 관련 정상 시험 5 개 스크립트 50 PASS 라벨, A3 변이 7/7 독립 재현(정상 소스 종료 0 · 변이 종료 1 · 첫 FAIL = want), 설치 USD 래퍼를 CPU 표적으로 실제 실행해 argv · cwd · sys.path[0] · 환경 전달 확인(sibling import 가 깨진다는 반례 없음), `on_cfg → gym.make` 순서(시험 대역 주입으로 확인). 17x 의 장치 · 실패 보존 · ray_index · 장면 값 · 래퍼 연결 지적은 닫힘.
- **남은 결함과 이번 허용 입력으로 배제하는 방법(필수):**
  1. `expect_conversions` 는 **`"0"` 으로 고정**(`"any"` 는 상한이 아님). 변환기가 불리면 첫 호출부터 HOLD 로 멈추고 조사. 실패했다고 `any` 로 풀지 않는다.
  2. `validate_a2:117` 이 **같은 경로값**을 못 잡는다(`usd_root=out_root` 반례가 계약 통과 · 가짜 GO). out · USD · log 부모를 **서로 다른 세 형제 폴더**로 동결. status · claim · prelaunch 보고서는 그 폴더를 미리 만들지 않는 별도 위치.
  3. `code_hashes` 는 `REQUIRED_BUNDLE` **정확히 23 개**(47 개로 늘리면 계약이 거절). 전체 47 목록은 별도 보존. Python · diag · criteria · parent · hook · 래퍼 경로와 해시를 승인 입력과 대조.
  4. 장치 UUID 형식은 **미확인**. 형식 때문에 멈추면 「장치 결박 실패 · 수집 0행」 으로 보고하고 claim 을 보존(같은 claim 지우기 · 이름만 바꾼 자동 재시도 금지).
  5. 감독기 `control_steps` 는 `partial_rows`(실패 행 포함)에서 오므로 보고에 **정상 완료 step · raw 행 수 · emergency 여부를 따로** 쓴다. HOLD 자료의 수집량이지 학습 · 평가 완료 수가 아니다.
  6. `competing_isaac_processes()` 는 알려진 서명 목록이라 완전 탐지기가 아니고 GPU 1 의 Isaac 도 보류시킬 수 있다. 빈 목록을 「GPU 와 예약이 모두 비었다」 로 번역하지 않고 예약 현황을 따로 본다.
- **입력 동결(출발값 · 충분성은 실측 아님):** GPU 0 실제 UUID · bus, 8 환경 · 256 step · 16 warmup · 개입 64/128/192 · optimizer 0 · retry 0 · `max_wall_s=900`, 초기 free VRAM ≥ 8 GiB, 실행 중 2 GiB 미만 중단, 초기 free disk ≥ 2 GiB, 출력 ≤ 1 GiB, 구체 마감 · 승인 만료, 실제 참석자, chain/attempt · 승인 ID/by · manifest digest.
- **기동 순서(참석자가 보는 터미널에서만):** `s2_stage0_prelaunch.py --manifest M --approval A` → 종료 0 이 아니면 NO_GO → GO 본문 · 동일 digest · **60 초 이내**를 확인 → `s2_zero_supervisor.py --manifest M --approval A`. **분리 launcher/watchdog 을 덧붙이지 않는다.** 기존 prelaunch 파일은 재사용 거절이라 새 보고서 경로를 동결.
- **중단 · 보고:** STOP · 마감 · 자원 하한/상한 · 장치/자산 불일치 · 예상 밖 변환기 · 예외는 HOLD. 멈춤이나 상태 갱신 중단 시 참석자가 **확인된 해당 감독기와 소유 가족만** 정리(광범위한 프로세스 종료 · 자동 retry 없음). 보고는 「시작 실패 / 부분 수집 / 256 행 수집 후 검증 보류」 로 나누고 **「참석 단회 정보 수집, HOLD_INFORMATION_ONLY, optimizer 0, 후속 학습 없음」** 이라고 쓴다. 256 행이나 종료 코드만으로 S2 통과 · 0 단계 PASS 라고 쓰지 않는다. **참석자가 자리를 비우면 이 허용도 끝난다. LLM 세션이 응답 중인 것은 참석이 아니다.**
- **무인 최단 목록(ASTRA):** 시작 전(watcher READY · 실행 identity · manifest/마감 결박 · 준비 실패 시 소유 감독기 정리 · 참석/무인 계약 분리) · 실행 중(absolute 와 monotonic 마감 동시 · NaN/Inf/미래 heartbeat 거절 · 로그 쓰기 실패와 AccessDenied 가 종료를 막거나 정상 종료로 오인되지 않게 · 감독기의 watcher 생존 확인) · 종료 후(가족 종료 receipt · 빈 가족 확인 전 후속 기동/lease 재취득 금지). 추정 30~60 분 이상(실측 ETA 아님). **ASTRA 의견: 참석자가 준비되는 시점에 이 단회를 먼저 한다.**
- **HOLD 이후:** 첫 수집 전부터 CPU 에서 accessor 계약 · 기대값 · 실패 자료 규약(Warp mesh 정점 · 면 · 월드 변환, USD 충돌체와 숨은 plane, ray 시작 · 방향 · hit 결박, root-sensor pose · sensor timestamp · reset 경계, 고정 자세 유지, Kit/driver 판)을 정한다. CPU 대역은 실제 메시가 그 값을 준다는 증거가 아니다. 두 번째 0 단계는 별도 동결 실행.
- **ASTRA 의 한도:** 17y 라운드(10 분 24 초)로 주간 5 % → 4 %. 이후 라운드는 몇 개 안 남음. **팀장이 일어나면 reset 권 직접 승인이 첫 일.**
- **lead 가 확인한 것(08:48~08:52):** 부팅 09/17 21:16:07 그대로. GPU 0 15 MiB · GPU 1 5,926 MiB(데스크톱 앱) · 어느 쪽에도 python · Kit 계산 프로세스 없음 · 기동 0 건. 이슈 #550 마지막 댓글은 ASTRA 17y(23:11Z), 팀장 새 댓글 없음. Isaac 해석기 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe`. 이 진단의 로봇 자산은 기본 Isaac Lab 작업의 `UNITREE_GO2_CFG` 의 `ISAACLAB_NUCLEUS_DIR/Robots/Unitree/Go2/go2.usd`(원격 USD 직접 읽기 · 변환기 안 불림 · 실제 문자열은 Kit 가 만든 값이라 첫 수집에서 확인).
- **놀고 있는 GPU(08:52 기준):** GPU 0 05:46 부터 약 27 시간, GPU 1 09:40:37 부터 약 23.2 시간. 이유: 첫 GPU 일이 **참석 단회**로만 허용됐고 팀장이 취침 중. 무인 요건(위 목록)을 채워 ASTRA 확인을 받기 전에는 띄울 수 없다.

## 무인 사슬 A4 구현과 ASTRA 17z 의뢰 (10/15 09:00 ~ 10:11 · 팀장 취침 중)

- **참석 단회 준비(09:0x):** `night-tools-20261013/s2_step4a3_launch/s2_attended_launch_a3.py` + `RUN-CARD-s2-stage0-a3-attended.md`(커밋 018e6b8a). 해시 47/47 · GPU 0 UUID/위치/여유 · 다른 Isaac 없음 확인 → 서류 생성 → prelaunch → (live 에서만) 감독기. 예행 2 회(감독기 안 띄움)에서 prelaunch GO 0.9 초 · 여유 15.59 GiB. 실행 위치는 한글 없는 `C:/Users/AI-WS01/s2_lab/`(고정 묶음 바이트 복사, 47/47 재확인). **참석자(팀장)가 없어 아직 안 띄움.**
- **무인 요건 7 개를 lead 가 새 파일로 구현(A3 한 바이트도 안 바꿈):** `night-tools-20261013/s2_step4a4_unattended/` 의 `s2_watchdog_v2.py`(READY 핸드셰이크 · chain_id 와 유한 heartbeat 만 진행으로 인정 · 절대 + monotonic 마감 · 로그 실패가 kill 을 안 막음 · AccessDenied 는 BLIND · kill 영수증과 후손 정리) · `s2_unattended_gate.py`(무인 계약 `a4u` 검증 → READY 확인 → 감시자 생존 스레드 → 안쪽 pair 유도 → A3 prelaunch/run_zero) · `s2_unattended_launch.py`(gate 먼저, 감시자에 신원 전달, READY 보고 종료, 실패 시 자기가 만든 두 프로세스만 정리).
- **측정(lead):** 정상 시험 **79 PASS**(감시자 24 · gate 39 · 프로세스 16, 실제 프로세스와 실제 Job Object) + 세션 독립 5 PASS · 변이 **40/41 CAUGHT**(NOT_CAUGHT 1 건 `gate_monitor_not_started` 는 정직하게 남김: 스레드 미시작 `join` 예외로 첫 FAIL 이 G4 라 의도한 G6 가 아님, 깨끗한 대체 변이 `gate_monitor_check_disabled` 는 CAUGHT) · 실제 기계 예행(Isaac 안 띄움: 운영 launcher → gate → 실제 watchdog READY → 실제 A3 prelaunch GO → 종료, 4 초, 남은 프로세스 0).
- **정직한 기록:** 시험 첫 실행 시험 쪽 오류로 중단, 둘째 실행에서 시험 기대값 1 + 코드 분류 1 수정, 후손 정리 경쟁 1 수정, 변이 첫 실행 38/40 에서 두 건이 FAIL 라벨 없이 끝나 시험을 고치고 **변이 전체를 처음부터 재실행**(39/40 → 위 40/41).
- **직접 잰 사실:** 이 세션 Bash 아래 프로세스는 Job 밖. 떼어낸 자식은 부모가 살아 있는 동안 `taskkill /T` 에 같이 죽고, launcher 가 먼저 끝난 뒤에는 산다(그래서 launcher 는 READY 뒤 곧바로 끝남). 메모리 `detached-child-survives-tree-kill-only-after-launcher-exits`.
- **ASTRA 17z 의뢰(10:10, 커밋 039b8c19, 작업서 `TASK-astra-17z-s2-unattended-a4.md`):** 일곱 요건이 닫혔는가 · `derive_inner` 안전성 · **무인 GPU 0 정보 수집 한 번** 허용 조건과 사후 절차 · 실제 기계 위험. ASTRA 는 10:11 에 작업 시작 확인(한도 4 %). 허용 판정이 오기 전에는 무인 기동 없음. 팀장이 먼저 일어나면 참석 단회가 우선.
- **gpuwatch:** super2 가 맡기로 함(mai-os `tools/gpuwatch/`, 댓글 6181717191, 제 답 6181783709). lead 몫은 RL 쪽 상태 칸과 무인 사슬 어댑터.
- **놀고 있는 GPU(10:12 기준):** GPU 0 은 10/14 05:46 부터 약 28.4 시간, GPU 1 은 10/14 09:40:37 부터 약 24.5 시간. 계산 프로세스 0. 이유: 첫 GPU 일이 참석 단회로만 허용됐고 팀장이 취침 중이며 무인 허용 판정(17z)이 아직 없다.

## ASTRA 17z 판정 (무인 보류) 와 A4 r2 수정 (10/15 10:2x 판정 확인 · 10:3x ~ 작업 · 전문 읽음)

- **17z 첫 줄:** A4 무인 GPU 0 단회는 **보류**. PID 신원 미확인 종료 · 거짓 가족 종료 영수증 · 감시 및 승인 결박의 결함을 고치기 전에는 17y 의 **실제 사람 참석 단회** 조건만 유지. 판정 대상은 커밋이 아니라 동결 바이트(목록 SHA256 `ecb9a716…`). 정상 시험 79 PASS 는 ASTRA 가 독립 재현.
- **ASTRA 가 찾은 결함(전부 사실로 받아들임):**
  1. **P1 신원 미확인 종료:** watchdog 이 후손의 생성 시각을 못 읽으면 `(pid, None)` 으로 남겨 `ct is None or ...` 로 통과시켜 **같은 pid 의 나중 프로세스를 kill** (대역 반례). launcher `kill_if_same` 도 생성 시각이 None 이면 비교 없이 종료. 후손 신원 접근 불능은 생존자 목록에서 빠져 **거짓 `family_empty=true`**.
  2. **감시 입력:** gate 모니터가 watchdog 하트비트의 `seq != last_seq` 만 봐서 `seq=NaN`, 다른 chain, 잘못된 pid 가 신선도를 갱신(`NaN != NaN`).
  3. **승인 결박:** CLI `--watch-dir` 이 승인된 `unattended.watch_dir` 과 같은지 안 봄(직접 gate 호출 시 prelaunch · run 모두 호출). watchdog 명령줄은 경로 문자열 포함 여부만 봄. **live 도구가 「존재하는 파일」이면 불허 문서도 승인 근거로 받음**(`UNATTENDED DENIED` 파일도 통과) · live 가 import 하는 `s2_attended_launch_a3.py` 는 목록 밖.
  4. **마감:** `deadline <= 토요일 정오` 만 검사해 `deadline + 60 s + 종료 대기` 가 정오를 넘을 수 있음. watchdog 1020 s 는 시작점이 감독기 900 s 와 다름.
  5. **launcher:** READY 파일만 보고 0 을 반환(READY 직후 gate 가 거절해도 성공처럼 보임).
  6. **동기 I/O:** 로그 쓰기 예외는 막지만 반환하지 않는 `fsync` · 파일 접근은 시한을 못 지킴(미측정).
  7. **한계 정정:** `startup_grace_s=180` 은 Kit 준비 제한이 아니라 「첫 유효 감독기 heartbeat」 대기 시간. 자식 Kit 가 멈춰도 부모가 heartbeat 를 쓰면 stale 30 초가 안 걸리고 남는 제한은 `max_wall_s=900` 과 외부 mono. child-progress 감시는 아직 없음.
  - `derive_inner` 자체는 해시 사슬을 끊지 않음(어댑터로는 가능) · 단 attended 로 바꾼 값은 사람 참석의 증거가 아님 · 최종 기록에 실제 모드(unattended)와 바깥/안쪽 해시를 함께 남길 것.
- **ASTRA 권고(그대로 따름):** 우선 17y 의 **실제 참석 단회**로 launcher → 자식 PID → Kit 준비 → 첫 수집 → 종료 · 가족 비움의 시간을 실측. 무인은 수정과 실제 기계 관측이 갖춰진 뒤 다시 판단. 지금 무인 승인을 내릴 근거는 없음.
- **lead 결정:** 무인 기동 안 함(보류). 참석 단회는 팀장이 일어나면. A4 는 **r2 로 고쳐 두고** ASTRA 재검은 참석 단회 실측 뒤(한도 4 % 이하라 낭비하지 않음). r2 수정: watchdog 신원 불명은 UNKNOWN(신호 금지 · 가족 `unverified` · 종료 코드 2) · 후손 강제 종료는 스냅샷 신원 일치 + 신호 직전 재확인만 · launcher 정리는 보유한 Popen 핸들로만 · 파일 I/O 는 별도 작업 스레드(결정 스레드는 디스크를 안 기다림 · 작업 스레드가 멈추면 `io_stalled` 로 kill) · kill 을 로그보다 먼저 · gate: watch 폴더 · watchdog 명령줄 전체 정확 일치 · 모니터는 chain · pid · 생성 시각 · 정수 단조 seq 만 진행으로 인정 · 승인에 scope + 결정 근거(verdict 파일 해시와 기계 줄) · 마감 여유를 앞에서 뺌 · launcher 는 감독기 status 를 본 뒤에만 성공 · live 도구는 verdict 파일에 `UNATTENDED_GO scope=… a4_list=… a3_list=…` 줄(현재 바이트 해시와 일치)이 있어야만 진행(불허 문서는 통과 못 함). mono 예산 1080 s.
- **r2 측정(11:56, lead):** 정상 시험 **115 PASS**(감시자 32 · gate 63 · 프로세스 20, 실제 프로세스와 실제 Job Object) + 승인 도구 9 PASS + 세션 독립 5 PASS · 변이 **58/58 CAUGHT**(감시자 23 · gate 30 · launcher 5, 정상 소스 먼저 통과 + 첫 FAIL 라벨 = want) · 실제 기계 예행(Isaac 안 띄움, 10:40) 정상: launcher → 실제 watchdog READY(정확한 명령줄 일치) → 실제 A3 prelaunch GO → gate DONE, 1.2 초, 남은 프로세스 0. 17z 때의 `gate_monitor_not_started`(첫 FAIL 이 G4)는 r2 에서 변이 목록에서 뺐고 대신 `gate_monitor_check_disabled` 로 같은 관문을 깨끗이 끈다. 정직한 기록: 패치 스크립트를 셸 heredoc 로 넘기다 셸 구문 오류가 두 번 나서 파일로 써서 실행했다(코드 결함 아님). r2 시험은 다시 쓴 뒤 그룹별 첫 실행에서 모두 통과(감시자 31 · gate 63 · 프로세스 19)했고, 그 뒤 후손 신원 경쟁(W25) · 하트비트 쓰기 스레드 · P11 시험과 monitor 입력 검증 시험을 더해 115 가 됐다. 증거 `rehearsal_evidence_r2/`, 고정 목록 `SHA256SUMS.txt`(13 파일).
- **ASTRA 재검(17z2)은 참석 단회 실측 뒤에 한 번만** 요청(주간 한도 4 % 아낌). 무인은 그 전까지 보류.
- **놀고 있는 GPU(11:57 기준):** GPU 0 약 30.2 시간(어제 05:46~) · GPU 1 약 26.3 시간(어제 09:40:37~). 계산 프로세스 0. 이유: 참석 단회는 참석자(팀장 취침 중) 필요, 무인은 17z 보류.


## S2 첫 GPU 수집 기동 기록 (참석 단회 · ASTRA 17y 조건부 허용) (10/15 14:02)

- **계기:** 팀장이 14:0x 채팅에 직접 들어와 「어제부터 GPU 가 하나도 안 돌았냐」 라고 물음. 팀장이 지금 화면 앞에 있으므로 17y 의 「실제 사람 참석」 조건을 채운 것으로 보고 띄운다. **팀장이 자리를 비우면 Ctrl+C 로 중단**한다고 알린다.
- **기동 전 확인(14:02:34):** 부팅 09/17 21:16:07 그대로 · GPU 0 15 MiB · 두 장 모두 python · Kit 계산 프로세스 0 · A3 고정 묶음 47/47(`C:/Users/AI-WS01/s2_lab/night-tools-20261013/s2_step4a3/`) · 기동 도구는 11:58 예행에서 prelaunch GO(여유 VRAM 15.59 GiB). 도구가 기동 순간에 다시 해시 47/47 · GPU 0 UUID `GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b` / bus 41:00.0 · 경쟁 프로세스 · 여유 VRAM 8 GiB 이상을 확인하고 하나라도 어긋나면 NO_GO 로 아무것도 안 띄운다.
- **띄우는 것:** GPU 0 · 8 환경 · 256 step · 개입 64/128/192 · optimizer 0 · retry 0 · `max_wall_s=900` · 변환 0 · 결과/USD/로그가 서로 다른 새 폴더(`s2_runs/live-<시각>/{out,usd,logs}`) · 분리 launcher/watchdog 없음. 명령(Orca 터미널 「S2 첫 수집 (참석)」):
  `& 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe' -B C:/Users/AI-WS01/s2_lab/night-tools-20261013/s2_step4a3_launch/s2_attended_launch_a3.py --live --attendee team-lead --confirm LAUNCH-ATTENDED`
- **중단:** Ctrl+C(STOP 파일 → 감독기가 자기 가족 정리, 90 초). 안 멈추면 도구가 알려주는 감독기 pid 한 개만 `taskkill /T`. 자동 재시도 없음. 같은 claim 을 지우고 다시 띄우지 않음.
- **보고(고정 문구):** 「참석 단회 정보 수집, HOLD_INFORMATION_ONLY, optimizer 0, 후속 학습 없음」. 시작 실패 / 부분 수집 / 256 행 수집 후 검증 보류로 나누고 정상 완료 걸음 · 원시 행 · 비상 행을 따로 적는다. 256 행이나 종료 코드 0 만으로 통과라 쓰지 않는다.
- **결과(첫 시도, 14:03:14 ~ 14:03:16 · 14:06 기록): 시작 실패 · 원시 행 0 · 정상 완료 걸음 0.** 기동 도구 → prelaunch GO(0.7 초) → 감독기 pid 169356 → 자식 종료 코드 42 → 영수증 `HOLD_INFORMATION_ONLY`(사유 artifact_missing · exit_code · step_count), `family_active_count=0`, 총 2 초, GPU 0 메모리는 15 MiB 에서 안 움직임. **원인:** Kit `check_eula()` 가 `input()` 으로 EULA 를 묻는데 자식에 stdin 이 없어 `input(): lost sys.stdin` → `Unable to bootstrap inner kit kernel`. 우리 감독기가 `OMNI_KIT_ACCEPT_EULA` 를 안 줬다. 이 저장소의 동작하던 Isaac 기동기(`unseen_driver_cmdr_v6.py:105`, `run_e2.sh:18`)는 모두 `OMNI_KIT_ACCEPT_EULA=YES` 와 `PYTHONUNBUFFERED=1` 을 준다. **lead 가 기존 기동기의 환경과 새 감독기의 환경을 한 줄씩 대조하지 않았고 ASTRA 도 못 봤다.** 이 변수는 CPU 시험으로는 안 잡히는 부류라 첫 실기동이 있어야 드러난다. 증거 `night-tools-20261013/s2_stage0_first_collection/attempt1_20261015_1403/`.
- **수정과 다음:** 기동 도구(`s2_attended_launch_a3.py`)와 A4 launcher 가 감독기/gate 를 띄울 때 두 변수를 준다(A3 47 파일 바이트는 그대로). 17y 는 retry 0 이었으므로 **ASTRA 17aa 에 두 번째 시도 허용 여부를 매우 좁게 의뢰**(14:05, ASTRA 주간 한도 2 %). 허용이 오면 같은 도구로 새 attempt 를 띄운다. 이 시도의 claim 은 지우지 않았다.

## S2 첫 GPU 수집 두 번째 시도 기동 기록 (ASTRA 17aa 조건부 허용) (10/15 14:27)

- **허용 근거:** `VERIFY-astra-17aa.md` (14:09). 환경 변수 `OMNI_KIT_ACCEPT_EULA=YES` · `PYTHONUNBUFFERED=1` 두 개만 더한 두 번째 참석 단회. 재시도 자동화 · 무인 불허. A4 는 안 씀.
- **EULA 동의 · 참석 · 한 번 실행 확인(팀장, 채팅 직접, 14:2x):** 「NVIDIA Omniverse EULA에 동의한다 / 이번 15분 동안 화면 앞에서 끝까지 본다 / GPU 0 수집을 이번 한 번 실행해라」. 원문은 `s2_stage0_first_collection/consent_attempt2.json` 에 인용해 두었고 기동 도구가 이 파일 없이는 시작하지 않는다.
- **기동 전 확인(14:26:46):** 부팅 09/17 21:16:07 그대로 · GPU 0 15 MiB · python/Kit 계산 프로세스 0 · A3 47/47 · 도구 해시는 manifest 에 기록(`launch_tool_sha256`). 도구가 기동 순간에 해시 47/47 · GPU 0 UUID/위치 · 경쟁 프로세스 · 여유 VRAM 8 GiB 이상을 다시 확인하고 prelaunch GO 가 60 초 안일 때만 감독기를 띄운다.
- **입력 그대로:** GPU 0 · 8 환경 · 256 step · 개입 64/128/192 · optimizer 0 · retry 0 · `max_wall_s=900` · 변환 0 · 새 out/USD/log 폴더. 새 chain 은 시각으로 만들어지고 첫 시도(chain `s2-stage0-a3-live-20261015-140314`)의 claim 은 보존. 보고에서 이것은 **전체 두 번째 시도**임을 명시한다.
- **중단:** Ctrl+C(STOP). **보고 문구:** 「두 번째 참석 단회 정보 수집, 시작 실패 / 부분 수집 / 256 행 후 검증 보류, HOLD_INFORMATION_ONLY, optimizer 0, 자동 재시도 및 후속 학습 없음」.

## S2 첫 GPU 수집 두 번째 시도 결과와 A3.1 (10/15 14:36)

- **결과(chain `s2-stage0-a3-live-20261015-142719`, 14:27:19 ~ 14:27:35 · 16 초): 시작 실패 · 원시 행 0 · 정상 완료 걸음 0.** 감독기 pid 131648, 자식 종료 코드 `3221225477`(0xC0000005 접근 위반), 영수증 `HOLD_INFORMATION_ONLY`(artifact_missing · exit_code · step_count), 가족 0.
- **첫 시도보다 멀리 감:** EULA 통과 → Kit 7.7 초 기동 → **GPU 0 장치 결박 통과**(`out/device_binding.json`: `str(props.uuid)` = 기대 UUID `c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b`, `repr` 은 `<torch._C._CUuuid object>` 객체, Kit `/physics/cudaDevice=0` · `/renderer/activeGpu=0` `verified`) → 그 뒤 `IsaacProvider` 가 `tensordict` 를 Kit 시작 **뒤에** 불러오다 `tensordict/utils.py:44 from tensordict._C import` 에서 접근 위반. 17y 4 번 「UUID 실제 형식 미확인」 이 이 실측으로 닫힘.
- **원인:** 이 저장소의 동작하는 드라이버(`_eval/q_eval.py:24-25`, `ce12/dump_native_v2.py:32-33`, `branch/branch_run.py:45-46`)는 `h5py` · `torch` · `tensordict` 를 Kit 보다 먼저 불러온다(Windows DLL 선적재). S2 진단만 빠졌다. 첫 시도와 같은 부류: **동작하던 기동기와 한 줄씩 대조하지 않음.**
- **수정(A3.1):** `s2_connect_diag_17v.py` 의 `_main_capture` 안 `from isaaclab.app import AppLauncher` 앞에 세 줄(diff `s2_stage0_first_collection/A31_diag_preload.diff`). A3 나머지 46 파일 바이트 그대로, 새 목록 SHA256 `089f6f16…`. **A3.1 CPU 전체 시험 정상 15 개 종료 0 (128 PASS) · 변이 5/5 · 6/6 · 7/7 · 감시자 4/4 · 깨끗한 폴더 import 22 모듈 · 해시 47 줄.** 증거 `attempt2_20261015_1427/`, `A31_suite_summary.json`.
- **다음:** ASTRA 17ab(14:32 의뢰)에 세 번째 시도 허용 + 다른 선적재 누락 확인. 팀장에게 시도마다 새 동의를 받는다(EULA · 화면 앞 · 한 번 실행). sol 에게 B 번들 실기동 경로 작업서(`TASK-codex-worker-s2-B-live.md`: 기동기 동등성 표를 시험으로 먼저)를 14:34 에 병렬 지시(sol 한도 100 % 복구).
- **놀고 있는 GPU(14:3x 기준):** GPU 0 10/14 05:46 부터 약 32.9 시간 · GPU 1 10/14 09:40:37 부터 약 29 시간 동안 계산 작업 0 이었고, 14:03 과 14:27 의 두 시도가 첫 기동이었다. E1 속도(8,192 환경, 20,000 update 에 23.3 시간)로 환산하면 GPU 0 하나만으로 약 28,000 update 분량이다.

## 세 번째 시도 대기와 heartbeat (10/15 14:48 ~ )

- **14:48 점검(date 14:48:12):** 부팅 2026-09-17 21:16:07 기준과 같음. GPU 0 15 MiB · GPU 1 10,652 MiB(데스크톱 앱 약 40 개, 계산 프로세스 아님). Isaac/Kit 프로세스 없음. 새 판정은 ASTRA 17ab(14:39 댓글 6185302444, 이미 전문 읽음) 하나. 이 heartbeat 문안의 1043 쌍 · 17k · 17l · RAND smoke 항목은 10/14 것이라 이번에는 해당 없음.
- **GPU 0 이 노는 이유(14:48 기준):** 세 번째 참석 단회는 ASTRA 17ab 가 조건부로 허용했으나, 조건에 팀장 본인의 새 동의(EULA · 화면 앞 끝까지 · 이번 한 번 실행)가 시도마다 있다. 팀장 채팅 응답이 아직 없다(마지막 동의는 14:26 · 두 번째 시도용). 동의가 올 때까지 lead 는 기동하지 않는다. GPU 0 은 10/14 05:46 부터 비어 있었고 첫 기동 시도는 10/15 14:03 이었다.
- **GPU 1:** 허용된 기동 없음. 지도 효과 B 번들 smoke 는 sol 이 실기동 경로(`codexE/s2_step5`)를 만드는 중이고 ASTRA 판정 전이라 띄울 수 없다. 앱 정리는 팀장 결정(10.6 GB 점유, 여유 약 5.7 GB).
- **병렬(GPU 줄 밖):** A4 무인 사슬 시험 재실행. 마지막 SUMS 생성(11:58) 뒤 `ISAAC_ENV`(EULA 변수) 와 P12 시험이 추가되어 이미 낡았다. 14:51 재실행 결과: 감시자 32 · 관문 63 · 프로세스 21(P12 포함) · 세션 독립 5 · 요약기 5 PASS · 모두 종료 0. 기동 보조 시험(`test_s2_unattended_live.py`)은 한글 출력을 cp949 로 읽다 죽던 시험 쪽 문제를 고쳤고(encoding=utf-8), L8 은 SUMS 가 낡아 거부하던 것이라 SUMS 재생성 뒤 확인한다. 변이 58 개는 14:52 에 재실행 중.

## S2 첫 GPU 수집 세 번째 시도 기동 기록 (ASTRA 17ab 조건부 허용) (10/15 15:06)

- **팀장 동의(채팅 원문, 15:0x 수신):** 「3차도 같은 조건(EULA 동의 / 화면 앞에서 끝까지 본다 / 이번 한 번 실행)으로 해라」. 동의 파일 `s2_lab/consent_attempt3.json`(15:06 기록, 저장소 사본 `s2_stage0_first_collection/consent_attempt3.json`). 앞의 두 번과 같은 EULA · 참석 · 한 번 실행 조건이며 시도마다 새로 받았다.
- **근거 판정:** `VERIFY-astra-17ab.md`(A3.1 선적재 · 시도 번호 3). 목록 SHA256 `089f6f16…` · 진단 `2f4352a6…`. 새 chain · manifest · approval(시도 번호 3 · 앞선 두 chain 기록)을 기동 도구가 시각으로 만든다.
- **조건 유지:** 무인 아님 · 자동 재시도 없음 · optimizer 0 · 변환 0 · 900 초 · GPU 0 UUID `GPU-c08e23b0-…` · 환경 변수 `OMNI_KIT_ACCEPT_EULA=YES` `PYTHONUNBUFFERED=1`. 실패하면 새 예외 · 예상 밖 변환 · 자원 초과 · 장치 불일치 · 상태 정지 모두 HOLD, 가족 종료 확인.
- **기동 직전 GPU:** GPU 0 15 MiB · Isaac/Kit 없음(15:05). 같은 시각 A4 변이 시험(CPU, 내 프로세스)이 돌고 있어 경쟁 프로세스 검사에 걸리면 도구가 NO_GO 를 낸다.

## S2 첫 GPU 수집 세 번째 시도 결과 (10/15 15:08)

- **결과(chain `s2-stage0-a3-live-20261015-150639`, 15:06:39 ~ 15:07:13 · 감독기 32 초): 256 행 수집 후 검증 보류.** 감독기 pid 114632 · 종료 코드 42(HOLD_INFORMATION_ONLY 정상 코드), 자식 pid 115856 은 29.3 초 뒤 종료 코드 0. **정상 완료 걸음 256 · 보존된 원시 행 256 · 비상 저장 행 없음 · Traceback 0 · 가족 활성 0 · 변환 0.** 영수증 문구는 `HOLD_INFORMATION_ONLY`, optimizer 0, 자동 재시도 없음, 후속 학습 없음.
- **고쳐졌다고 확인된 것:** A3.1 선적재(h5py · torch · tensordict)로 2차의 `tensordict._C` 접근 위반이 없어졌다(실행 기록으로 확인, 원인 가설이 맞았다는 통제 비교는 아님). 환경 변수 두 개로 EULA 입력 막힘도 없다. GPU 0 장치 결박: `torch_uuid` 일치 · Kit `/physics/cudaDevice=0` · `/renderer/activeGpu=0` verified(렌더러 · PhysX 의 물리 UUID 를 각각 잰 것은 아님).
- **VRAM:** 최소 여유 11.77 GiB(약 3.8 GiB 사용 최고) · 종료 뒤 GPU 0 15 MiB. 완료 기록 `cleanup`: `app_close` · `provider_close` 가 `pending` 으로 남음(가족 0 은 감독기 확인).
- **검사기 `check.json`: 판정 HOLD, 사유 13 개** `boundary_evidence_content` `boundary_evidence_hash` `boundary_mask` `boundary_unreported` `case_assignment` `fixed_pose_evidence` `mesh_evidence_hash` `provenance_missing` `root_sensor_transform` `scene_hit_mask` `sensor_timestamp` `stale_packet` `world_height_answer`. 계수: live_steps 240 · fixed_steps 16 · miss 19,308 · boundary 2,494 · deep_finite 3,596. `meta.json`: `fixed_pose_verified` · `mesh_collision_verified` · `terrain_assignment_verified` 모두 false. **0 단계 PASS 아님.** 이 13 개 중 진단이 아직 기록하지 않아서 생기는 것과 실제 불일치인 것을 나누는 일이 다음(2 단계).
- **증거:** `night-tools-20261013/s2_stage0_first_collection/attempt3_20261015_1506/`(6.0 MB · 파일 21 · 원시 행 256). 원 폴더 `s2_lab/.../s2_runs/live-20261015-150639`.
- **놀고 있는 GPU(15:08 기준):** GPU 0 은 수집 종료(15:07:13)부터 다시 비었다. 이유: 다음 GPU 일은 (1) 0 단계 HOLD 사유를 진단에 반영한 재수집 또는 (2) B 번들 smoke 인데, 둘 다 ASTRA 허용 전이다. GPU 1 은 허용된 기동이 없다.

## S2 0단계 A3.2와 4차 준비 (10/15 15:52 ~ 16:50 · ASTRA 17ac 전문 읽음)

- **ASTRA 17ac(15:52 의뢰, 판정 파일 `VERIFY-astra-17ac.md`) 조건:** 3차는 수집 완료 · 0단계 HOLD. **내 「10개는 기록 누락, 3개는 데이터 문제」 요약은 폐기**(실제는 기록 · 출처 관문 7 + 수치 · 실험 계약 관문 6, 섞여 있음). gap_90 추락은 173행부터(191행 아님). 무중력 · 종료 해제는 진단 전용으로 가능하나 「고정됨」의 증명이 아니라 첫 16행을 실측해야 함. PhysX 비교는 환경 x 표면 갈래별 충족 · 원시 응답 보존 · 구멍을 하나도 안 본 입력은 불합격(ASTRA 반례). 시계는 예정된 128행만 되감김. 이 조건을 갖춘 A3.2는 ASTRA 재왕복 없이 lead 검증 기록 + 팀장 새 동의로 4차 참석 단회 가능. **PhysX API 첫 확인 중 HOLD는 허용되나 PASS 선승인 아님. 17z 무인 보류 유지.** 0단계 전 배관 smoke는 기술적으로 가능하나 코드 없는 200 update · 두 arm은 보류(PPO 1~2회 `plumbing_only` 단회로 줄여 별도 계약 · 새 동의).
- **A3.2 구현(커밋 71aeaf8a 후 57932407):** 환경(무중력 · base_contact 끔) · 검사기(예정 리셋 시계 · 에피소드 +1 · 종료 별도 · 광선 틀 3종 · scope 요구) · 진단(버전 · 자산 다이제스트 · 센서 view 오프셋 · 원본 경계 마스크 보존 · PhysX 캡처 도중 질의 · 원시 응답 파일) · 프로브(Warp/USD · 16갈래 branch_report). 시험 203 PASS(16 파일, 종료 0), 변이 5/5 6/6 7/7 4/4 **28/28**, 깨끗한 폴더 import 22, 해시 49, 목록 SHA `98bd1936…`. lead 검증 기록 `RECORD-lead-a32-pre-attempt4.md`. 예행 `--rehearse` prelaunch GO.
- **B 번들(sol)**: `REPORT-s2-step5.md` 도착. lead 재실행(run `lead_rerun_1602`): 정상 PASS 53 · 변이 7/7 · 종료 0 · GPU 0회. 지도 계산 모듈 6개(`s2_env_adapter_17v` `s2_map_obs` `s2_sensor_tracker_17v` `s2_policy` `s2_ppo_17v` `s2_terrain_overlay_17v`)는 0단계 번들과 바이트가 같다(env_config · check · diag · packet은 다름: 학습은 RobotLab-Go2-v0 + 희소 지형 overlay). 저장소 사본 + ASTRA 의뢰는 아직.
- **Chrome 탭 메모:** 바탕화면 `Chrome-열린-탭-20261015.txt`(탭 236개, URL 227개 일치). GPU 1 VRAM 10.5 GB 중 Chrome GPU 프로세스 약 8.5 GB(WDDM 카운터, 합계가 장치 값보다 커서 근사). 정리는 팀장 결정.
- **놀고 있는 GPU(16:50 기준):** GPU 0은 15:07:13부터 다시 비었다. 이유: 4차 수집은 A3.2 + lead 검증 기록이 준비됐지만 **팀장의 새 동의(EULA · 화면 앞 끝까지 · 이번 한 번 실행)가 아직 없다.** 그 사이 약 1시간 40분을 A3.2 수정 · 시험 · 판정 읽기에 썼고 GPU 줄은 비어 있었다. GPU 1은 10/14 09:40:37부터 허용된 기동 없음.

- **17:50 heartbeat:** 부팅 기준 일치. GPU 0 0 MiB · GPU 1 10.6 GB(앱). Isaac/Kit 없음. 팀장 응답은 중간 보고 요청(17:48)뿐이고 4차 동의 한 줄은 아직 없다 → **GPU 0 이 15:07:13 부터 2시간 43분 비어 있다. 이유: 팀장 새 동의 대기.** 병렬로: sol 에게 `TASK-codex-worker-s2-B-plumbing.md`(배관 smoke 단계, CPU) 17:49 지시, ASTRA 에게 `TASK-astra-17ad-s2-B-plumbing.md` 17:50 의뢰. 4차 수집 도구는 49개 해시 · 예행 GO 로 준비 끝.

- **18:48 heartbeat:** 부팅 기준 일치. GPU 0 0 MiB · GPU 1 10.8 GB(앱) · Isaac/Kit 없음. **GPU 0 은 15:07:13 부터 3시간 41분 비어 있다. 이유: 4차 수집에 팀장의 새 동의가 없다.** 그 사이 한 일: ASTRA 17ad 판정 읽음(B 실제 기동 보류 · 장치 결박 API · USD 격리 · plumbing 보강 7곳 · 4차 후 같은 GPU 0 에서 작은 plumbing 한 arm 권고), sol step6(plumbing) lead 재실행 기존 53 + 새 42 PASS · 변이 7/7 + 11/11 → 저장소 사본 `s2_step6/`, sol step7(17ad 결함 수정) 18:14 지시 중, A4 r2 재검증 변이 58/58 · 해시 재생성(`eba07a4f`).

- **19:48 heartbeat:** 부팅 기준 일치. GPU 0 0 MiB · GPU 1 10.8 GB(앱) · Isaac/Kit 없음. **GPU 0 은 15:07:13 부터 4시간 41분 비어 있다. 이유: 4차 수집에 팀장의 새 동의가 없다.** 그 사이: ASTRA 17ad(B 실제 기동 보류) → sol step7 → lead 재실행(31/31 파일, 정상 273 라벨 = 271 + 변이 선행 2, 변이 54/54) → ASTRA 17ae(첫 GPU 0 plumbing 은 현 바이트로 보류, 결함 둘: CUDA 재적재의 optimizer 비교 장치 불일치, 합성 입력 정답 probe 불일치; 고치고 CPU 증거를 모으면 lead 기록 + 팀장 단회 동의로 진행) → sol step8 19:35 지시(진행 중, 컨텍스트 50 %) → 독립 가족 정리 관찰자 `s2_family_observer.py` 시험 10 PASS · 기동 도구에 연결(`55c7d150`). 정정: 「6개 모듈 바이트 동일」 은 5/6, 「271 틀림」 은 내가 틀렸다(271 과 273 은 의미가 다름).

- **20:48 heartbeat:** 부팅 기준 일치. GPU 0 0 MiB · GPU 1 10.8 GB(앱) · Isaac/Kit 없음. **GPU 0 은 15:07:13 부터 5시간 41분 비어 있다. 이유: 팀장의 새 동의가 없다(4차 0단계 수집과 B 첫 배관 단회 둘 다 동의 대기).** 20:04 이후 새 판정 · 댓글 없음. 준비 상태: 4차 도구(해시 49 · 예행 GO), B 배관 도구(`s2_step8` 해시 104 · 예행 GO, lead 기록 `RECORD-lead-b-plumbing-first.md`), 독립 관찰자. 마지막 팀장 메시지는 17:48(중간 보고 요청)이며 그 뒤 동의 응답 없음.

- **21:48 heartbeat:** 부팅 기준 일치. GPU 0 11 MiB · GPU 1 13.9 GB(앱, 20:48 의 10.8 GB 에서 3.1 GB 늘었다: 누가 무엇을 열었는지 미확인) · Isaac/Kit 없음. **GPU 0 은 15:07:13 부터 6시간 41분 비어 있다. 이유: 팀장의 새 동의가 없다.** 20:04 이후 새 판정 · 보고 · 댓글 없음.

- **22:48 heartbeat:** 부팅 기준 일치. GPU 0 11 MiB · GPU 1 13.7 GB(앱) · Isaac/Kit 없음. **GPU 0 은 15:07:13 부터 7시간 41분 비어 있다. 이유: 팀장의 새 동의가 없다.** 21:48 이후 새 판정 · 보고 · 댓글 없음.

- **23:48 heartbeat:** 부팅 기준 일치. GPU 0 11 MiB · GPU 1 13.8 GB(앱) · Isaac/Kit 없음. **GPU 0 은 15:07:13 부터 8시간 41분 비어 있다. 이유: 팀장의 새 동의가 없다.** 22:48 이후 새 판정 · 보고 · 댓글 없음.

- **10/16 00:48 heartbeat:** 부팅 기준 일치. GPU 0 11 MiB · GPU 1 13.5 GB(앱) · Isaac/Kit 없음. **GPU 0 은 10/15 15:07:13 부터 9시간 41분 비어 있다. 이유: 팀장의 새 동의가 없다.** 10/15 23:48 이후 새 판정 · 보고 · 댓글 없음.

- **10/16 01:48 heartbeat:** 부팅 기준 일치. GPU 0 11 MiB · GPU 1 13.5 GB(앱) · Isaac/Kit 없음. **GPU 0 은 10/15 15:07:13 부터 10시간 41분 비어 있다. 이유: 팀장의 새 동의가 없다.** 00:48 이후 새 판정 · 보고 · 댓글 없음.

- **10/16 02:48 heartbeat:** 부팅 기준 일치. GPU 0 11 MiB · GPU 1 13.6 GB(앱) · Isaac/Kit 없음. **GPU 0 은 10/15 15:07:13 부터 11시간 41분 비어 있다. 이유: 팀장의 새 동의가 없다.** 01:48 이후 새 판정 · 보고 · 댓글 없음.

- **10/16 03:48 heartbeat:** 부팅 기준 일치. GPU 0 11 MiB · GPU 1 13.5 GB(앱) · Isaac/Kit 없음. **GPU 0 은 10/15 15:07:13 부터 12시간 41분 비어 있다. 이유: 팀장의 새 동의가 없다.** 02:48 이후 새 판정 · 보고 · 댓글 없음.

- **10/16 04:48 heartbeat:** 부팅 기준 일치. GPU 0 11 MiB · GPU 1 13.5 GB(앱) · Isaac/Kit 없음. **GPU 0 은 10/15 15:07:13 부터 13시간 41분 비어 있다. 이유: 팀장의 새 동의가 없다.** 03:48 이후 새 판정 · 보고 · 댓글 없음.

- **10/16 05:48 heartbeat:** 부팅 기준 일치. GPU 0 11 MiB · GPU 1 13.5 GB(앱) · Isaac/Kit 없음. **GPU 0 은 10/15 15:07:13 부터 14시간 41분 비어 있다. 이유: 팀장의 새 동의가 없다.** 04:48 이후 새 판정 · 보고 · 댓글 없음.

- **10/16 06:48 heartbeat:** 부팅 기준 일치. GPU 0 11 MiB · GPU 1 13.4 GB(앱) · Isaac/Kit 없음. **GPU 0 은 10/15 15:07:13 부터 15시간 41분 비어 있다. 이유: 팀장의 새 동의가 없다.** 05:48 이후 새 판정 · 보고 · 댓글 없음.

- **10/16 07:48 heartbeat:** 부팅 기준 일치. GPU 0 11 MiB · GPU 1 13.5 GB(앱) · Isaac/Kit 없음. **GPU 0 은 10/15 15:07:13 부터 16시간 41분 비어 있다. 이유: 팀장의 새 동의가 없다.** 06:48 이후 새 판정 · 보고 · 댓글 없음.

- **10/16 08:48 heartbeat:** 부팅 기준 일치. GPU 0 11 MiB · GPU 1 13.4 GB(앱) · Isaac/Kit 없음. **GPU 0 은 10/15 15:07:13 부터 17시간 41분 비어 있다. 이유: 팀장의 새 동의가 없다.** 07:48 이후 새 판정 · 보고 · 댓글 없음.

- **10/16 09:48 heartbeat:** 부팅 기준 일치. GPU 0 11 MiB · GPU 1 13.4 GB(앱) · Isaac/Kit 없음. **GPU 0 은 10/15 15:07:13 부터 18시간 41분 비어 있다. 이유: 팀장의 새 동의가 없다.** 08:48 이후 새 판정 · 보고 · 댓글 없음.

- **10/16 10:48 heartbeat:** 부팅 기준 일치. GPU 0 11 MiB · GPU 1 13.4 GB(앱) · Isaac/Kit 없음. **GPU 0 은 10/15 15:07:13 부터 19시간 41분 비어 있다. 이유: 팀장의 새 동의가 없다.** 09:48 이후 새 판정 · 보고 · 댓글 없음. 팀장의 마지막 메시지는 10/16 09:5x 의 「실험에 유의미한 결과가 생겼는지?」 질문이며 동의는 아니었다(답: RL 실험 결과는 없고 진단 지식만 있다고 보고함).

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


## 네 번째 시도 기동 기록 (10/16 14:15 · lead)

- **동의:** 팀장이 채팅 선택지에서 직접 「둘 다 동의」 (질문과 선택지 설명 원문은 `consent_attempt4.json` · `consent_plumbing_A_first.json`). 범위: 4차 0단계 수집(A3.2) 한 번 + 독립 관찰자의 가족 정리 검사가 PASS 이면 GPU 0 배관 arm A(합성 N=32, 1 iteration) 한 번. ASTRA 17af 5절이 이 형식을 각 실행의 직접 동의로 인정했다. 재시도 · 무인 · GPU 1 · short 학습은 포함되지 않는다.
- **GPU 0 은 10/15 15:07:13 부터 비어 있었다** (이유: 직접 동의 없음. 이 날 질문은 11:07 에 보냈고 답은 14:14 직전에 왔다).
- **예행 14:15:08:** 번들 49개 일치 · GPU 0 여유 15.59 GiB · 경쟁 프로세스 없음 · prelaunch GO.
- 이 기동은 정보 수집 전용이며 결과는 HOLD_INFORMATION_ONLY 외에 PASS 로 쓰지 않는다.

## 4차 결과와 첫 배관 기동 기록 (10/16 14:17 · lead)

- **4차 수집 (A3.2, 14:15:29 기동, 36초):** 감독기 rc=42, HOLD_INFORMATION_ONLY. 정상 256 step · raw 256행 전부(FULL_ROWS_HOLD) · 장치 결박 verified (Kit 장치 0, torch UUID 일치). check.json HOLD 이유 3개: case_assignment · fixed_pose_evidence · mesh_evidence_content. 독립 관찰자 PASS (남은 프로세스 0 · 미분류 0 · GPU lease와 USD 잠금 획득 후 해제). 실행 폴더 `s2_runs/live-20261016-141535`.
- **동의 조건 충족:** 동의 범위 「관찰자의 가족 정리 검사가 PASS 이면 이어서 배관 arm A」 → 배관 기동. 관찰자 PASS는 정리 PASS이며 0단계 과학적 PASS가 아니다 (ASTRA 17af 5절).
- 배관 입력은 synthetic_known_answer, N=32, 1 iteration, 최대 600초. 성공 문구는 plumbing_checks=PASS · stage0_passed=false · performance_verified=false.
- **10/16 14:25 heartbeat:** 부팅 09/17 21:16:07 일치. GPU 0 비어 있음 (14:18:46 부터 · 이유: 직접 동의로 실행한 4차와 첫 배관이 끝났고, 다음 기동은 sol step10 후 새 직접 동의가 필요). GPU 1 앱 13.7 GB. 새 판정 없음, #550 새 댓글 없음. sol step10 접수 (14:23), 산출물 아직 없음.
- **10/16 14:48 heartbeat:** 부팅 일치. GPU 0 비어 있음 (14:18:46 부터 · 이유: 다음 기동은 sol step10 확정과 새 직접 동의 대기). sol step10 중간 보고 도착 (14:48, 시험 최종 결과 진행 중이라 재실행 보류). lead 가 바이트로 확인한 것: A3.3 사본은 A3.2 와 41개 파일 동일, 달라진 파일은 보고서가 적은 9개와 같음(지도 · 어댑터 · runner · tracker · 점검 코드 · 메시 프로브 동일). 보고서 주장: PhysX 질의 103,224개 전부 miss(RayCaster 유한 hit 101,844개), env 6 자세 편차는 x 성분 step 7 부터 허용 초과. GPU 판별 단회 제안 있음(8 env x 16 step, 학습 0).
- **10/16 15:51 heartbeat:** 부팅 일치. GPU 0 비어 있음 (14:18:46 부터 · 이유: sol step10 확정 후 ASTRA 17ah 판정과 팀장 새 직접 동의 대기). sol step10 최종 보고 15:05 도착 (B 39/39 파일 331 PASS 변이 70/70, A3.3 23/23 작업 208 PASS 변이 50/50, 해시 180/180과 50/50 lead 확인). lead 재실행 15:49 시작(B, A3.3, AST 순). ASTRA 17ah 의뢰 발송, sol step11(판별 도구 + 평가 경로) 접수.
- **10/16 16:50 heartbeat:** 부팅 일치. GPU 0 비어 있음 (14:18:46 부터 · 이유: A3.4 CPU 구현과 팀장 새 직접 동의 대기). ASTRA 17ah 판정(16:09) 확인: PhysX 전부 miss 의 직접 원인 = sim.enable_scene_query_support False. sol step11(16:26) 읽음. lead 는 두 보고를 39분, 22분 늦게 읽었다(heartbeat 간격이 1시간). sol step12(A3.4) 접수 16:49. 앞으로 일꾼 대기 중에는 20분 간격으로 산출물을 본다.
- **10/16 17:48 heartbeat:** 부팅 일치. GPU 0 비어 있음 (14:18:46 부터 · 이유: sol step12 A3.4 CPU 구현 중, 완성 후 lead 재실행과 팀장 새 직접 동의 대기). sol 은 16:49 지시 직후 모델 용량 오류로 멈췄다가 17:31 에 재개, 17:48 에 s2_step12 에 s2_step4a34 와 배관 시험이 생김. 새 판정 없음.
- **10/16 18:46:** sol step12 lead 재실행 통과 (A3.4 214 PASS 변이 50/50, B 355 PASS 변이 74 CAUGHT), 두 기동 도구 리허설 prelaunch GO. GPU 0 비어 있음 (14:18:46 부터, 이유: 팀장 새 직접 동의 대기). 동의 문구를 채팅 글로 요청함.
- **10/16 19:49 heartbeat:** 부팅 일치. GPU 0 비어 있음 (14:18:46 부터 · 이유: 팀장 두 단회 직접 동의 대기 · 동의 문구 18:46 채팅). sol step13(평가기 CPU 코어)과 step14(Kit 연결부 CPU) lead 재실행 통과: step13 16 PASS 변이 14/14, step14 14 PASS 변이 8/8, 해시 1243/1243과 1259/1259. 새 ASTRA 판정 없음.
- **10/16 20:48 heartbeat:** 부팅 일치. GPU 0 비어 있음 (14:18:46 부터 6시간 29분 · 이유: 팀장 두 단회 직접 동의 대기, 요청은 18:46 채팅). step15 lead 재실행 통과(B 51/51, 356 PASS, 변이 단계 CAUGHT 84)이고 첫 인도본의 B 회귀 둘을 lead 재실행이 잡았다. ASTRA 17ai 발송(20:40), 답 대기. sol 은 맡은 일 없음 (17ai 판정 뒤 배정).
