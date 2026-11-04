> 분류: A/정책학습 · 출발 관문
> 작성: 오흥재 · lead 세션 · 2026-11-04 13:4x
> 근거: WORKLIST D178 · 실험 흐름 정본 v2(`inbox/jay/20261028-plan/FLOW-experiment-cycle-1029.md` 2 ~ 5 절) · 사후 점검 `EX41-POSTMORTEM.md` 1 ~ 7 절 · EX41-REQUIREMENT-REGISTER
> 요지: 새 EX-41(m6000 에서 6000 회 · 누적 m12000) 을 띄우기 전에 모두 「증거」 칸이 채워져야 하는 행. 증거는 실제 실행 산출 경로 · 커밋 · 장면 캡처이고, 가짜 입력 · 가짜 자식 시험은 증거가 아니다. 한 행이라도 비면 띄우지 않는다
> 상태: v1 · 전 행 열림

# 새 EX-41 출발 관문

## 0. 실행 설정 (D178)

| 칸 | 값 |
|---|---|
| 이름 | EX-41(같은 이름 · 새 실행 폴더) · 이전 실행 `ex41_main_20261103_195435` 는 비교군 |
| 시작 저장본 | EX-40 m6000(`ex40_main_20261031_041313/.../model_6000.pt`, sha d5e9ec40) |
| 길이 | 6000 회(누적 m12000) |
| 단계 | S2a 750 · S2b 1000 · S2c 1000 · S2d 1250 · S2e 500 · **T0′ 1500**(500 → 1500, D178 가) |
| DR · 밀기 · 보상 · 명령 몫 | 이전 실행과 같음(EX-41 fixed5000 설정) · DR 멈춤 한도 1000 회 그대로(측정 실패는 한도를 쓰지 않음) |
| 학습 중 손잡이 | swing · stumble · zero_yaw · critic_mirror · **명령 몫 칸(D96 ±1 %p · 누적 ±2 %p, D177 a)** 을 approvals 에 넣는다 |

## 1. 코드 한 곳

| # | 행 | 담당 | 증거 |
|---|---|---|---|
| C1 | 학습 · 점수 감시기 · 단계 끝 평가 · 밀기 감시기 · 영상 촬영기 · 합성기 · 디스패처가 원격에 push 된 한 커밋(가지 `ex41-measure-fix`) | runner · scripter · lead | |
| C2 | runner 커밋 d4f8193d · 4c1b14e2 · 7a907a90 · scripter 커밋 c4b84391 · cd41b19d · 4bde9787 · 12b8cdf7 · SB 촬영기가 그 커밋의 조상(`git merge-base --is-ancestor` 출력) | lead | 15:0x ex41-measure-fix e5c30137 에서 patch-id 대조(cherry-pick 이라 해시는 다름): c4b84391 → d2f31e82 · cd41b19d · 12b8cdf7 · 230cc44e 그대로 · 4bde9787 → 6527ffb2 · 54e393a5 → 8cad4806 · runner 3 커밋 dd653dc0 · d6598e06 · e702e65b · lead 93fd9441 · b26c556c · 889266c8 조상 확인. 남음: 새 실행 기동 HEAD 가 이 커밋(또는 그 뒤)인지 기동 때 대조 |
| C3 | 프로세스마다 시작 때 HEAD 대조 · 다르면 거절(시험: 다른 HEAD 로 띄워 거절되는 로그) | runner | |
| C4 | 실행 사본 쓰기 잠금(커밋 거절 hook · 시험 커밋이 거절된 출력) | lead | `_out/tools/ex41/lock_checkout.py`(f7c4d3d3) · 15:4x 시험 사본(ex41-measure-fix HEAD)에서 lock → 추적 파일 649 개 모두 읽기 전용 · 소스 편집 Permission denied · 새 파일(outputs) 쓰기 됨 · 잠근 채 `import foothold_s2.ex41_score_watch` 정상 · unlock 으로 되돌림. 남음: 기동 직후 실행 사본에 lock · check 0 writable 기록 |
| C5 | 저장소 밖 실행 파일 0(mirror guard · boundary report · 디스패처 · 관리판을 저장소 `tools/` 로) | lead | 일부: 디스패처 · 관리판 `_out/tools/gpu_jobs/dispatch.py`(93fd9441) · 경계 보고 `_out/tools/ex41/boundary_report.py`(b26c556c, 실행 루트 인자 · 측정 없음이면 rc 2 · 경계 적용 DR 줄 출력, 1250 · 1500 · 2000 으로 확인). 남음: mirror guard 는 runner 가 정본 코드로(M8) |

## 2. 측정 체계

| # | 행 | 담당 | 증거 |
|---|---|---|---|
| M1 | 측정 실패(rc≠0 · 표식 충돌 · 결과 없음) → 같은 회차 자동 재측정 · 영수증 RETRY · W72 증거에 안 들어감 · DR 멈춤 한도 안 씀 | runner | |
| M2 | GPU1 표식이 잡혀 있으면 기다렸다 띄움(실패 금지) | runner | |
| M3 | 250 경계 평가 트리거가 N 저장 직후(N+50 아님) | runner | |
| M4 | 단계 끝 일이 P1 을 막지 않음: 단위로 쪼개 P1 이 들어오면 비켜 줌 · 단계 끝 총 시간 실측 ≤ 250 경계 간격 | runner · lead | |
| M5 | 단계 끝 항목별 영수증 · 한 항목 실패가 다른 숫자를 막지 않음 · 숫자는 바로 다음 경계 판단 기록으로 | runner | |
| M6 | 밀기 감시기: HOLD 회차는 기록만 하고 다음 경계로 · 감시기 위치가 학습보다 250 넘게 뒤처지면 경보 | runner | |
| M7 | 판정 칸 미달 때 할 일이 코드에 있음(D179: 밀기 미달이면 상한 유지 · 다음 단계 끝 재측정 · 두 번 연속이면 보고 · 대책 제안 · 학습은 계속) | runner | |
| M8 | 대칭 규칙 하나(D179: 팀장 D174 그대로 · 정본 코드로 옮김 · D142 쌍 이벤트는 기록 · lead 의 0.85/5 쌍 폐기) · critic_mirror 관측 사유 문구가 실제 원인을 적음 | runner | |
| M9 | 경보가 lead 세션에 실제로 닿음(orchestration pending 0 · lead 창 수신 캡처) | lead | 원인: 기동 환경에 `EX41_ORCHESTRATION_TO` 가 없어 `ex41_ops._send_orchestration` 이 받는 곳 없이 실패(15 건 pending). 14:4x 같은 함수에 lead 창 handle 을 주고 보내 True · lead 받은편지함 도착 확인. lead 받은편지함 대기가 lead 창 발신을 거르던 필터를 제목 「[lead」 기준으로 고치고 시험 경보 2 로 깨어남 확인. 남음: 새 시작 스크립트가 이 환경 변수를 넣는지(runner · 기동 때 lead 확인) |
| M10 | 경계 적용 영수증(DR · 단계) 계획 대비 0.01 어긋나면 경보 | runner | |
| M11 | 평가 잡음 기준선(m6000 시드 42 · 43 · 44 · 39 칸 · 이미 잼: 칸별 차 중앙값 0.0022 · 최대 0.0084) | lead | `M6000-ANALYSIS.md` |
| M12 | S2a 첫 500 회 lr 바닥 · KL 넘침(이전 실행 233 / 500 회)을 경계 보고에 넣음 | lead | 경계 보고 12 줄(f7c4d3d3): 지난 250 회 lr 바닥 횟수 · KL probe > 0.05 횟수 · lr 중앙. 이전 실행으로 확인: 500 경계 바닥 117 회 · KL 24 회 · 2000 경계 바닥 4 회 · KL 0 회 |

## 3. 단계 끝 자동화 · 영상

| # | 행 | 담당 | 증거 |
|---|---|---|---|
| V1 | 단계 끝에 학습 쪽이 P2(밀기 사다리 6 단 · 걷기 1.5 포함 · 계단 옆걸음 전체 · 축 · 회전 진단) · P3(W57 명령 13 × 지도 셋 · W80 네 방향 · W78 계단 12 · 밀기 지도 셋 · 재생 목록)를 대기열에 스스로 등록 | runner · scripter | |
| V2 | 녹화기가 SB 정책을 받음 · 화살표 · C76 가시성 · 시드 2 개 고침이 같은 커밋 | scripter | SB 촬영기 · 화살표 · C76 가시성 · 두 시드가 scripter/ex41-video-on-measure 2bc0ccd8(origin) · CPU 94 passed(`D:/mai-tmp/scripter/pytest-ex41-video-gate.txt`). **남음: ex41-measure-fix HEAD e5c30137 에 2bc0ccd8 이 아직 안 들어감 → runner 합침 뒤 같은 HEAD 로 다시 확인** |
| V3 | 영상 넷이 예행에서 실제로 한 편씩 나옴 · lead 가 장면을 직접 열어 확인(밀기: 순간에만 · 몸통 위 · 힘 방향 · 짧게 · 범례 같은 방향) | scripter · lead | 15:2x lead 장면 직접 판독. 밀기(m750 정답 · `ex41_video_sb_1625006c/a_push_m750/.../eval_gt/styled.mp4`): 1.80 s 화살표 없음 · 2.12 s 몸통 위 원에서 시작 · 범례(노란 ↗)와 같은 방향 · 2.32 s 아직 보임(밀기 0.3 s 안) · 2.56 · 3.02 s 없음 · 4.14 s 두 번째 밀기(2.0 m/s)에 다시 · 기준 통과(12:4x 불합격 판 3.02 s 잔류 고쳐짐). 계단 W78 L5 30° 정답 · 명령 W57 전진 0.5 · 네 방향 W80 계단 옆걸음 왼: 로봇 한 대 · HUD · 지형 정상. 복원 · 끔 밀기는 scripter 화소 검사만 |
| V4 | 영상 done = 영상 수 = 목록 수 · 전 프레임 문제 0 · 판 영수증 v3.4-D168 | scripter | scripter 영수증: 네 종류 raw · styled 전 프레임 문제 0 · v3.4-D168 · 같은 m750 SHA(`D:/mai-tmp/scripter/REPORT-EX41-video-gate-1104.md`) · lead 는 영수증 경로 확인 · 전 프레임 재검 안 함 |
| V5 | 재생 목록 `s2_lab/_playlists/EX41-m단계-all|fail.m3u8` 가 예행 단계 끝에서 생김 | scripter | `C:/Users/AI-WS01/s2_lab/_playlists/EX41-m00750-all.m3u8` 6 편(lead 열어 봄) · fail 0 편. 밀기 세 편 파일 이름이 `styled.mp4` 로 D48 규칙과 다름 → scripter 에 전달 |

## 4. GPU 관리

| # | 행 | 담당 | 증거 |
|---|---|---|---|
| G1 | 디스패처 순위 P1 250 경계 > P2 단계 끝 평가 > P3 단계 끝 영상 > P4 C층 · P4 상시 깔림 · 위 순위가 오면 다음 단위부터 비켜 줌 · 학습 여부는 TRAINING_BUSY_GPU0 표식 + 실제 PID(없음 = GPU1 자유 · 죽은 PID = 재기동용 보류) | lead | 일부: lead/ex41-dispatch-on-measure 93fd9441(ex41-measure-fix a48ac12b 위) · `test_dispatch.py` 102 passed · 14:2x 실제 dispatcher 를 이 판으로 다시 띄움(PID 96960) · 첫 단계 busy_own 151 확인 · 시험 test_no_training_marker_frees_gpu1_dead_marker_holds_it. 남음: runner 등록이 이 대기열 하나로(W28 금지) · 예행 R4 에서 P1 이 오자 P4 가 비켜 주는 실제 기록 |
| G2 | 「대기 · 승인」 글자 판별 제거(`gpu_jobs.py:637-639`) · 「취소」 상태 추가 | lead | lead/ex41-dispatch-on-measure 93fd9441(ex41-measure-fix a48ac12b 위) · `test_dispatch.py` 102 passed · 14:2x 실제 dispatcher 를 이 판으로 다시 띄움(PID 96960) · 첫 단계 busy_own 151 확인 · 시험 test_condition_words_alone_never_gate · test_cancel_marks_never_run_items_and_refuses_running |
| G3 | 띄우기 전 출력 폴더 · EULA · 대상 사본 도구 · 인자 검사(dry-parse) | lead | 일부 a11d8d43 · 97faa5cb |
| G4 | 같은 종류 기술 실패 3 회 연속이면 그 종류를 막고 경보 | lead | lead/ex41-dispatch-on-measure 93fd9441(ex41-measure-fix a48ac12b 위) · `test_dispatch.py` 102 passed · 14:2x 실제 dispatcher 를 이 판으로 다시 띄움(PID 96960) · 첫 단계 busy_own 151 확인 · 시험 test_three_consecutive_failures_block_that_family_only |
| G5 | 학습 상태 파일을 읽는 도구 전부 Windows 잠금 시험 통과 | lead | 15:4x 실제 Windows 시험(`D:/mai-tmp/lead/g5_lock_test/`): 학습 상태 쓰기(`runners/status.py write_status`, 0e38d9d7 재시도) 와 디스패처 share-all 읽기 셋을 20 초 동시에. 실제 읽기 속도(0.2 s) 13,364 쓰기 · 건너뜀 0 · 깨진 읽기 0 · 쓰기 예외 0. 극단(초당 수천 읽기) 25 쓰기 중 11 건 재시도 끝 건너뜀 · 쓰기 예외 0(학습은 죽지 않음) |
| G6 | 점검 문구에 「지난 1 시간 산출 수 · 실패 수」 | lead | |
| G7 | C층 216 칸(시드 [42, 43] · MAX_ATTEMPTS 2) 이 P4 로 깔림 | scripter | 계획 c9600daa · 대기열 181 ~ 378 P4 · 15:0x 6 칸 끝 · 실패 0 · L3 분할 빈 마스크 원인 미확인(디스패처 3 회 막음으로 헛돌지 않음) |

## 5. 실제 예행 한 바퀴 (가짜 입력 금지)

| # | 행 | 담당 | 증거 |
|---|---|---|---|
| R1 | 운영 출력 자리 · 실제 승인 파일 · 실제 argparse · 단계 길이만 줄인 실제 Kit 실행으로 모든 단계 경계를 지남 | runner | |
| R2 | 250 경계 P1 자동 평가 · 측정 실패를 일부러 넣어 자동 재측정이 증거로 들어가는 것 확인 | runner | |
| R3 | 단계 끝 자동 등록 → P2 숫자 → P3 영상 넷 → 재생 목록 | runner · scripter | |
| R4 | C층(P4) 가 P1 이 오자 비켜 줌 | lead | |
| R5 | 학습 중 설정 바꾸기(critic_mirror · 보상 한 칸 · 명령 몫 한 칸)를 W72 로 적용하고 되읽음 | runner | |
| R6 | 이어 가기: 실제 저장본에서 이어 가 저장 한 번 통과 · 코드 비교 기준 다시 잡힘 · 감시기 재기동 | runner | |
| R7 | 결정 D 마다 런타임 호출 증거(자동 규칙 · 손잡이 · 판정 칸) | runner · lead | |

## 6. 문서 · 승인

| # | 행 | 담당 | 증거 |
|---|---|---|---|
| D1 | 이전 EX-41 요구 등록부 · 출발 점검표 · 최종 감사의 열린 행을 이 관문의 행으로 옮기거나 닫음(남는 행은 팀장 「받아들임」 서명) | lead | |
| D2 | FAILURE-LOG 의 「다음 실험에서 커진다」 항목이 이 관문의 행으로 있음 | lead | |
| D3 | 결과 시나리오표 · 다음 실험 1 ~ 2 개 시작 스크립트 DRY | planner · lead | |
| D4 | 출발: 이 표의 증거 칸 전체를 팀장에게 보고한 뒤 바로 기동(D179 · 팀장 11/04 14:0x 「문제 없으면 보고한 뒤 실험 바로 EX41 진행」) · 「지금 띄웁니다」 한 줄 | lead | |
