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
| GPU 0 · CMD-R 1043 on 갈래 | attempt `g0-cmdr_s1043_on_u4000-1014001820-895773` · PID 154852 (시작 00:18:20) · 셸 btwz5bu9g | `_eval/out_branch/cmdr_s1043_on_u4000.log` 의 마지막 `Learning iteration N/24001` · `Traceback` 수 · 로그 크기 · 콘솔 `_eval/out_smoke/night_1043_v3.console.txt` | 01:08 iteration 20618/24001 (00:54 뒤 +169 · 약 5.1 s/it) · PID 살아 있음 · Traceback 0 · 로그 12.45 MB (시작 때 USD Head_lo/up 경고는 이미 알던 것) | 05:40 무렵 · 다음 heartbeat 에서 iteration 이 늘었는지 |
| GPU 1 | 01:16 CTS r2 기록 끝 (01:16:26 · slot 0 · guard 0) · 그 뒤 빔 | job tmp `ce12fix/r2_*.txt` | r2 COLLECTED · 대조 ALL PASS (action 2.15e-6) · APPROVED (`--code_bundle CODE_BUNDLE_r2.txt`) · 재확인 유효. **채택은 17i 뒤** | 17g |
| 감시 스크립트 (사용 한도 대비) | 셸 bd8y4zrp0 · job tmp `arm_v5_full.sh` · 로그 `arm_v5.log` | ASTRA 가 `uncr_v5/approval-astra-17g.json` 을 쓰고 값 (decision approve · by 17g · reval 98322ffb · manifest ac09c264 · 75 · no · 묶음 e5597517) 이 맞을 때만, GPU 1 에 python 이 없을 때 v5 full,post 를 띄움 (deadline 09:00 · 콘솔 job tmp `v5_full_console.txt`). 승인 파일 없이 17g 가 10 분 지나거나 04:40 이 되면 띄우지 않고 끝. 멈추려면 `_eval/out_uncr_v5/STOP` | 01:18 걸어 둠 (판정 확인 함수는 답을 아는 json 둘로 시험: OK · BAD decision) | lead 가 깨면 17g 전문을 읽고, 조건이 v5 full 과 어긋나면 STOP |
| 하위 작업 · CE12 대조기 고침 + 17f 4.2 ~ 4.4 | 00:29 맡김 · 01:02 보고 | lead 재실행 job tmp `ce12fix/` (시험 둘 · 변이 둘 · 해시 sha_before.txt) | 보고: 실제 기록 대조 ALL PASS (관측 · target · last action 차 0 · CPU action 2.15e-6) · 새 출처 검사 A9 로 이 기록은 REJECTED (guard 해시 미기록 · 기록 뒤 세 파일 수정) · 시험 132/132 · 23/23 · 변이 65/65 · 24/24 (보고값) | lead 재실행 결과 → r2 재기록 |
| 하위 작업 · S2 판 3 | 00:40 맡김 | 같음 | 진행 중 | 알림 |
| heartbeat 예약 | `2b1bfe25` (7 · 27 · 47 분 · 세션 안에서만 · 7 일 만료) · 00:57 등록 · 옛 `b698612f` 지움 · CronList 에 하나만 있음 확인 | 이 문구로 깨어난 기록 | 01:08 첫 도착 확인 (이 문구로 깨어남) | 매 도착 |
| ASTRA 17g | 00:54 보냄 · 터미널 term_fe1daede | `VERIFY-astra-17g.md` · (승인 시) `night-tools-20261013/uncr_v5/approval-astra-17g.json` | 검사 중 · 00:59 터미널 제목에 「Context 11% left」 (17g 도중 자동 압축 또는 중단 위험 · super2 상태판에 「팀장: ASTRA 재시작 승인」 대기가 있음 · 17g 끝나기 전 재시작은 17g 를 잃음) | 파일 생김 · 다음 의뢰 전에 ASTRA 컨텍스트 처리 (새 세션 또는 압축) 를 팀장 · super2 와 맞춤 |

부팅 기준: **09/17 21:16 KST** (`Win32_OperatingSystem.LastBootUpTime`). 다르면 위 PID · 실행을 그대로 믿지 않고 새 기동을 보류한 채 다시 확인하고 #550 · 채팅에 보고한다. 적법한 재부팅이 확인되면 이 기준값을 고친다.

## 판정 조건 (대상별 · 조건마다 지금 상태와 증거)

**17f (00:17 · 고쳐서 기동)**

| 절 | 조건 | 지금 |
|---|---|---|
| §1 | 야간 셸 시험 호출은 Git Bash 실제 경로와 PATH 를 고정 (기본 PATH 는 `system32/bash.exe` 를 집어 rc 127) | 미반영. 운영 1043 은 Git Bash 안에서 돌고 있어 해당 없음 (추정). 시험 `test_night_1043_v3b.py` 를 다시 돌릴 때 PATH 고정 |
| §3 | CE12 는 v3 전용 registry · v2 registry 무수정 · 같은 변환 잠금 · attempt 마다 USD 루트 · dry-run 확인 | 충족: `run_dump.py:63` v3 registry (시험 117/117 기대값 고침) · 실행 USD `out_ce12/native/_attempts/<attempt>/usd/` |
| §4.2 | 승인 재확인이 which · checkpoint · tag · attempt 를 대조 (다른 모델이면 실패) | 하위 작업 고침 (01:02 · stamp 에 대상 · VA-ck-target) · lead 재실행 중 · ASTRA 17i 검증 전에는 채택 안 함 |
| §4.3 | 실행 당시 코드 해시를 승인 묶음과 연결 | 하위 작업 고침 (provenance 시작 · 끝 · 실행 중 변경 87 · 승인 A9). 00:25 기록은 실행 중 변경은 없었으나 guard 해시 미기록 · 기록 뒤 수정으로 A9 REJECTED → 새 tag r2 재기록 필요 · ASTRA 17i 전에는 채택 안 함 |
| §4.4 | `switch_step <= T-1` · 전환 뒤 action 비교 횟수 · miss 미측정과 0 구분 | 하위 작업 고침 (1..T-1 · reset 뒤 60 · 전환 뒤 20 action step 셈 · miss None 은 미측정) · ASTRA 17i 전에는 채택 안 함 |
| §4.5 | 1 고정 · 2 짧은 기록 · 3 COLLECTED 와 출처 확인 · 4 `compare_native --recompute_action` (1e-6 · 1e-4 사후 완화 금지) · 5 CTS 승인 뒤 v2 expect 0 | 1 · 2 끝 · 3 COLLECTED 22 PASS · 4 고친 대조기로 ALL PASS (보고서 `out_ce12/native/cts_e1_m20000/compare_report_20261014-005010.json`) · 5 대기 (CTS 승인 뒤) |
| §5 | S2 학습 기동 보류 (센서 · rollout 저장소 · 학습기 연결 · 사전 등록 전) | 보류 유지 |

**17f-2 (00:33 · 다른 안)**: 첫 S2 A/B 는 encoder 전 구간 실제 고정 (팀장 확정 대기) · r=0 은 실제 고정이 아님 (판 3 이 고침) · smoke 기준 (cosine 0.9 · 평지 −10%p) 자동 전환 금지 · 사전 등록 5.3 의 1 ~ 6 미충족 · S2 자체 갱신 번호 · adaptive LR 이 group LR 덮어쓰기 검사. S2 학습 기동 없음.

**17h (00:49 · 고쳐서 채택)**: 아래 「읽기 · 재개 규칙」 과 하트비트 문구로 반영 (00:57). 수용 기준 (17h 7 절) 은 실제로 지키는지 아침까지 관측한다.

**17g (대기)**: 무작위화 smoke · 미경험 v5 full 의 기동 조건. 판정 전 GPU 1 기동 없음.

## 일 표 (우선순위 순 · 의존과 자원을 보고 고른다)

| 순서 | 일 | 의존 · 자원 | 상태 | 다음 행동 |
|---|---|---|---|---|
| 1 | GPU 0: 1043 off → 검증 → on | 스크립트 | 단계 끝 (off VALID · on 00:18:20 START) · 실행은 「진행 중 실행」 | iteration 관측 |
| 2 | ASTRA 17f | | 끝 00:17 (b77106d2) | 조건은 위 표 |
| 2b | ASTRA 17f-2 → 팀장 채팅 · #550 | | 끝 00:33 · 채팅 · #550 6149317273 (df9e89f9) | 팀장 확정 대기 |
| 2c | ASTRA 17h | | 끝 00:49 (7d24517a) · 반영 00:57 | 관측 |
| 3 | GPU 1: 같은 시험지 CTS E1 20000 짧은 기록 | 17f §3 충족 | 기록 끝 00:25 · COLLECTED · 대조 ALL PASS · A9 REJECTED (출처) | 3b |
| 3b | GPU 1: CTS 재기록 tag `cts_e1_m20000_r2` (README 「lead 가 돌릴 명령」 · reset 1,6@30 · 전환 0@40 fwd03) · 코드 해시 고정 뒤 · dry-run 먼저 | 기동 안전 조건 (17f §3: v3 registry · 같은 변환 잠금 · slot v3 · isolate v3 는 17f 가 본 판 그대로) · lead 재실행 통과 · GPU 1 에 다른 Isaac 없음 · 고친 기록기는 ASTRA 미검토라 결과의 승인 채택은 17i 뒤 | lead 재실행 끝 01:15 (시험 23/23 · 132/132 · 변이 24/24 · 65/65 · PASS 아닌 줄 없음 · 해시 그대로 · 변이 사본 없음) · 코드 묶음 `night-tools-20261013/ce12/CODE_BUNDLE_r2.txt` (slot · isolate · guard 포함) · 01:16 dry-run → 기록 띄움 | 수집 · 대조 · 승인 판정 (채택은 17i 뒤) |
| 3c | ASTRA 17i: CE12 고침 (4.2 ~ 4.4 · A9 · dims) 검증 | 17g 끝 · ASTRA 컨텍스트 처리 | 의뢰문 쓸 것 | |
| 4 | GPU 1: 같은 시험지 v2 기록 (expect 0) | 3 승인 · GPU 1 이 비어 있을 때 | 대기 | |
| 5 | 미경험 v5 · 무작위화 lead 재실행 | | 끝 00:43 · v5 isaac311-moects 51/51 · 변이 38/38 · 옛 루트 재검사 23 valid · 묶음 e5597517 · manifest 75 · base python 3.13 은 X01 hold (원인은 BLAS FMA 여부 · 7c) · 무작위화 27/27 | |
| 6 | ASTRA 17g | 5 끝 · ASTRA 한 번에 하나 | 00:54 보냄 | 판정 전문 읽고 조건 표에 적기 |
| 7 | GPU 1: 무작위화 smoke → 스틸 · 영상 전 프레임 확인 → 네 판 한 실행 → 미경험 v5 full 75 | 17g 허용 · GPU 1 에 Isaac 하나 · 여유 6,144 MiB 이상 | 대기 | |
| 7b | S2 판 3 (CPU) | 17f-2 | 01:27 보고 (시험 14/14 · 292 칸 · 변이 69/69 · 첫 실행 T13 기대 상수 1 ulp FAIL · 변이 1 차 68/69 (q28) 를 고쳐 다시 돎 · 학습 루프 연결 · smoke 등록 5.3 의 2 ~ 6 · 난수 상태 · 센서 관문은 안 됨) · lead 재실행 백그라운드 bjwaki7me (job tmp `s2v3/lead/`) | 재실행 결과 → 저장소 사본 → ASTRA (17i 뒤) |
| 7c | 미경험 X01 환경 차이 분석 (CPU) | 독립 · 임시 폴더에서만 | 끝 01:06 (하위 작업 · 산출물 job tmp `x01env/`): 원인은 python · numpy 가 아니라 **BLAS gemv · ddot 의 FMA 여부** (q_metrics.py:224 `xy @ e` · :249 norm). MKL · OpenBLAS Nehalem 은 두 번 반올림, OpenBLAS 기본 (Cooperlake) 은 FMA · 원본 23 실행 바이트는 FMA 쪽. 차이는 progress_m 150 · disp_m 12 값 · 1 ULP · 서식 차 0 · 판정 열은 이 자료에서 같음 (일반 보장은 미확인 · 4.0 m 경계에서 뒤집힐 수 있음). lead 확인 01:10: 같은 isaac311-moects 에 `OPENBLAS_CORETYPE=Nehalem` 만 주니 X01 valid 8 · hold 15 (job tmp uncr_v5_lead_test_nehalem.txt). 「통과 환경」 도 CPU 커널에 기댐 · Linux 이전 때 다시 잼 | 17g 판정에 보탬 · 관문 고침 (환경 지문 · `[post-env]`) 은 ASTRA 검토 뒤 |
| 8 | 아침 7판 (조각 job tmp `e12page/`) → 렌더 1920 · 1366 · 390 · 라이트 · 다크 → 게시 → #550 · #546 · 채팅 | 아침 · 밤 결과 | 대기 | |
| 9 | super2 에 「GPU 1 out_* 실행 끝」 | 7 끝 | 대기 (Windows 업데이트 알림은 00:45 보냄) | |

## 사용 한도 (super2 01:13 전달)

5 시간 한도 88 % (01:30 무렵 100 % · 해제 04:20) · 주간 81 %. 한도에 걸리면 lead 는 04:20 까지 멈춘다. 그동안: GPU 0 1043 on 은 스크립트가 끝까지 (05:40 무렵) · GPU 1 은 위 감시 스크립트만. 새 하위 작업은 띄우지 않는다 (super2 요청). 돌고 있는 하위 작업: S2 판 3. 깨면 (04:20 뒤 첫 heartbeat) 17g 전문 → 감시 스크립트 로그 → 17i 보내기 (ASTRA 컨텍스트 처리 먼저) → 무작위화 smoke → 아침 7판.

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
