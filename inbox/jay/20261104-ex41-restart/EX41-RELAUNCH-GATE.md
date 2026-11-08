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
| 길이 | 6000 회 고정 끝(누적 m12000) |
| 단계 | S2a 750 · S2b 1000 · S2c 1000 · S2d 1250 · S2e 500 · T0′ 500 + 나머지(D181: 전체 6000 회에서 끝 · 연장 · 멈춤으로 늘어난 만큼 T0′ 가 줄고, 늘어남이 없으면 T0′ 가 1000 회 더 · 최대 끝 6000) |
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
| M1 | 측정 실패(rc≠0 · 표식 충돌 · 결과 없음) → 같은 회차 자동 재측정 · 영수증 RETRY · W72 증거에 안 들어감 · DR 멈춤 한도 안 씀 | runner |  23:5x lead 확인: `D:/mai-tmp/runner/s2_lab/ex41_rehearsal_20261104_232543` model_1 공백 처리 · 결과 미사용 · 다음 회차 진행 · 재측정 상한 3(ac181550) |
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
| R1 | 운영 출력 자리 · 실제 승인 파일 · 실제 argparse · 단계 길이만 줄인 실제 Kit 실행으로 모든 단계 경계를 지남 | runner |  일부(22:0x lead 직접 확인): ex41-measure-fix e44e8830(source_dirty.diff 0 바이트) 실제 Kit 단계 축소 예행 `D:/mai-tmp/runner/s2_lab/ex41_rehearsal_20261104_214336` · model_1~12 저장 · `ex41_application.jsonl` 에서 0 S2a(DR 0.5) → 3 S2b(0.5) → 5 S2c(0.65) → 7 S2d(0.8) → 9 S2e(1.0) → 11 T0′(1.0) → 13 T0′ 모두 applied. 남음: 같은 판의 P1 평가가 model_2 에서 map_steps=1 로 재측정 세 번 실패(R2 · M1 미통과 · bf3687c4 에서 고침), D181 두 경우 Kit 완주 미확인 |
| R2 | 250 경계 P1 자동 평가 · 측정 실패를 일부러 넣어 자동 재측정이 증거로 들어가는 것 확인 | runner |  23:5x lead 직접 확인 · 실제 Kit 단계 축소 예행 `D:/mai-tmp/runner/s2_lab/ex41_rehearsal_20261104_232543`(HEAD 9b3f4cce · 되돌림 2b01df9a): P1 평가 m2 · m3 · m4 · m5 · m6 다섯 모두 첫 시도 완료(`watch_state.json` done 5 · attempts 에 model_1 만), 실패 주입 model_1 은 4 회 시도 = 재측정 3 회 뒤 `measurement_gaps/model_1_d5cc56735107.json`(224727 판 m2 · m4 도 같음 · 학습 계속) |
| R3 | 단계 끝 자동 등록 → P2 숫자 → P3 영상 넷 → 재생 목록 | runner · scripter |  23:5x lead 확인: `D:/mai-tmp/runner/s2_lab/ex41_rehearsal_20261104_232543` 단계 끝마다 실제 대기열 `D:/mai-tmp/gpu/queue.json` 에 REHEARSAL 표시 P2 axis_v2 · P3 a_push_video 등록(item 379~388) · 중복 8 건 취소 · 387 · 388 은 실행 확인용으로 남김. 운영 전체 목록(P2 셋 · P3 W57 39 + W80 12)은 CPU 시험만(실제 gpu_jobs 로 55 건 등록) ; **운영 확인 11/05 06:45**: score_750 직후 실제 대기열 55 건(P2 axis_v2 · w78_v2 · push_ladder · P3 a_push_video + W57 39 + W80 12 · item 411~465) |
| R4 | C층(P4) 가 P1 이 오자 비켜 줌 | lead |  운영 확인 11/05 02:11 · 04:0x · 06:03: 250 · 500 · 750 P1 평가 중 dispatcher `yield_p1 marker:PRIORITY_BUSY_GPU1` 로 C층(P4) 새 단위를 띄우지 않음(dispatch.stdout.new.log) |
| R5 | 학습 중 설정 바꾸기(critic_mirror · 보상 한 칸 · 명령 몫 한 칸)를 W72 로 적용하고 되읽음 | runner |  23:5x lead 확인: `D:/mai-tmp/runner/s2_lab/ex41_rehearsal_20261104_232543` 실행 중 W72 커밋(9b3f4cce) 뒤 회차 4 경계에서 `ex41_application.jsonl` side 몫 0.07/0.07 → 0.08/0.06 applied · 학습 · 점수 감시 계속(model_2~6 평가 완료) · 운영 승인 · 경계 파일은 revert 로 원복(2b01df9a) · c499593e 대비 차이는 0.0 인 command_share_bias 손잡이 다섯뿐 |
| R6 | 이어 가기: 실제 저장본에서 이어 가 저장 한 번 통과 · 코드 비교 기준 다시 잡힘 · 감시기 재기동 · **끊기 직전과 이어 간 직후가 같음을 출력으로(팀장 17:3x): 정책 · critic 가중치 · optimizer 상태 · 학습률(KL 적응 현재 값) · 관측 · 보상 정규화 통계 · 난수 · 커리큘럼 시계(elapsed · pause_used · 단계 · DR · 밀기) · W72 적용 상태 · 명령 몫 · W86 가중치 · 지도 전환 난수열 · use_gt_frac** | runner |  일부(19:1x lead 직접 확인): ex41-measure-fix a3092af4(origin 일치) 실제 Kit · fresh 3072 env 10/10 rc 0(`D:/mai-tmp/runner/s2_lab/ex41_rehearsal_20261104_185400`, model_10 sha 06c18638) → 새 프로세스 재개 11~12 rc 0. 재개 로그 `ex41-r6-kit-resume-20261104_190300.log` 의 EX41_RESUME_STATE_READBACK 에서 정책 · critic · Adam · 학습률(1.71e-4, 바닥 위) · 정규화 · 난수 · 커리큘럼 시계 · W72 경계와 명령 몫 · W86 · 지도 난수와 use_gt_frac 아홉 묶음 matched, segment 0→1 · Traceback 0. 앞서 Kit 이 copy · math 미임포트와 같은 회차 저장 자기 참조 셋을 잡았고 a3092af4 에서 고침(pyflakes 미정의 이름 0). 남음: 정규화 running_buffer_count 0 이 설정상 맞는지 · 감시기 재기동 · 코드 비교 기준 재설정은 미확인 |
| R7 | 결정 D 마다 런타임 호출 증거(자동 규칙 · 손잡이 · 판정 칸) | runner · lead | |

## 6. 문서 · 승인

| # | 행 | 담당 | 증거 |
|---|---|---|---|
| D1 | 이전 EX-41 요구 등록부 · 출발 점검표 · 최종 감사의 열린 행을 이 관문의 행으로 옮기거나 닫음(남는 행은 팀장 「받아들임」 서명) | lead | |
| D2 | FAILURE-LOG 의 「다음 실험에서 커진다」 항목이 이 관문의 행으로 있음 | lead | |
| D3 | 결과 시나리오표 · 다음 실험 1 ~ 2 개 시작 스크립트 DRY | planner · lead | planner fable-25a 526c19a2 `inbox/jay/20261101-ex41/EX41-RESULT-SCENARIOS.md` v1.0(lead 15:5x 읽음): S1 졸업 · S2 복원 미달 · S3 처방 미달 · S4 퇴행 · 밖 · 단계 표(6000 회 · 250 경계 24 · 단계 끝 6) · 비교군 규칙(n ≤ 1250 직접 · 1500 ~ 2000 은 DR 0.575 꼬리표로 참고 열만) · 다음 실험 A EX-42 v0.15 시작 조건 A1 ~ A9 · B T0′ +500. lead 몫 결정 7-2 · 7-5 · 7-6 은 planner 안 그대로(P7 번호 n5750 · n6000 · 밀기 연속 미달은 졸업 판정이 아니라 다음 실험 선택에만 · 옛 1500 ~ 2000 은 참고 열만). 팀장 몫 7-1 · 7-3 · 7-4 는 실행 끝 판정에 쓰는 것이라 기동을 막지 않음(기동 보고에 묶어 여쭘) |
| D4 | 출발: 이 표의 증거 칸 전체를 팀장에게 보고한 뒤 바로 기동(D179 · 팀장 11/04 14:0x 「문제 없으면 보고한 뒤 실험 바로 EX41 진행」) · 「지금 띄웁니다」 한 줄 | lead | |

## 7. 이전 등록부 · 감사 · FAILURE-LOG 에서 옮긴 행 (D1 · D2 · 15:4x)

이전 요구 등록부 · LAUNCH-GAPS · FINAL-AUDIT · FAILURE-LOG 의 닫히지 않은 행 218 개(출처가 겹친 수)를 하나씩 대조했다: 이 관문의 행으로 덮임 85 · 새 행이 필요 64(아래 N1 ~ N24 로 모임) · 이번 실행에 해당 없음 33(EX-42 몫 · 대체된 결정 · 운영 · 문서) · 이전 실행에서 끝났고 그대로 참 36(YAML 값 · 조상 커밋). FAILURE-LOG 의 「다음 실험에서 커진다」 는 M85(→ M1 · M6 · M7) 와 M88(→ 이 관문) 이다.

이전 고침 커밋 가운데 통합 HEAD 에 변경 내용(patch-id)이 없는 것: e5a908a2(DR 켠 평가 모드 · planner 가지에만) · 03d5078d(W78 v2 측정 준비) · 69e119dd(critic 거울 기록 관절 순서 시험) · 7256a118(W57 · axis250 지도 셋 관문) · 48846e53(CANON 계보 등록). 다섯 다 이전 실행 HEAD 975166d9 의 조상도 아니었다(이전 실행에도 없었음). 기능이 다른 커밋으로 들어갔는지는 아래 N3 · N21 에서 실제 출력으로 확인한다.

**출발 막음(학습 프로세스 · 기동 자체에 걸림 · 다 차야 띄운다)**

| # | 행 | 담당 | 증거 |
|---|---|---|---|
| N3 | critic 거울: 예행 경계에서 critic_mirror 관측이 빈 값이 아님(이전 실행 9 회 모두 무효) · 좌우 대칭 관측 쌍 시험 skip 0(69e119dd 내용이 HEAD 에 있는지 포함) | runner · scripter | |
| N5 | 관문 가정값: D96 「S2a 첫 측정 뒤 확정」 과 RH77 「결과 전 고정」 을 하나로 · 확정 회차와 바꿀 칸을 문서 커밋으로 | lead | lead 결정(15:5x · D179 위임): 새 실행의 유지 판정 문턱은 결과 전에 지금 YAML 값으로 고정한다(`ex41-fixed5000.yaml:455` maintenance_drop_count 3 · 기준 m6000 점수 sha a1457a3d). D96 의 「S2a 첫 측정 뒤 확정」 은 이전 실행의 S2a 측정(750 경계 · 단계 끝)으로 이미 했다고 보고 새 실행에서는 바꾸지 않는다. 근거: 같은 저장본 시드 셋 평가 잡음 칸별 최대 0.0084(m6000) · 0.0088(m7500) 로 오차 문턱 0.03 의 1/3 아래 |
| N6 | 기동 1 분 안 되읽기: 실행 폴더 params/env.yaml(유지 항 · foot_slip 0 · lin_vel_z 0) · 첫 reset DR 0.5 · 부모 sha d5e9ec40 · 단계 · 승인 SHA 를 계획과 대조한 출력 | runner · lead | |
| N7 | 졸업 · 끝: S2c 미달 때 T0′ 진입 · 졸업 판정 · 학습 끝 뒤 최종 T0′ 점수 배출이 예행 끝점에서 실제로 나옴 | runner | |
| N8 | S2d 부터 지형 레벨 성과 승급이 예행에서 실제 레벨 변화로 · 경계마다 지형 종류별 env 수 · 레벨 분포 기록 | runner | |
| N10 | force_gt 끈 T0′ 구간에서 use_gt_frac · GT/PRED/OFF 실제 소비가 경계 기록에(예행 줄) | runner | |
| N11 | 저장 용량: 저장 간격 50 × (6000 + 연장) 저장본 크기 · C: 남은 공간 · 디스크 관문 값 | lead | 15:5x 실측: 저장본 1 개 35.6 MB × (6000 + 연장 500) / 50 = 130 개 ≈ 4.6 GB · 이전 실행 폴더 2100 회까지 3.9 GB(평가 포함) → 6500 회 약 12 GB(추정) · C: 남은 공간 483.2 GB |
| N12 | 승인 문장은 회차가 주 조건 · END_BY ≥ 예상 끝 + 24 h · 첫 50 회 실측 속도로 끝 시각 재계산을 첫 보고에 | lead | |
| N13 | 학습 GPU0 · 평가 · 촬영 GPU1 · 자식 env 에 CUDA_VISIBLE_DEVICES 없음 · 화면 GPU 렌더를 실제 자식 env 덤프로 | runner · lead | |
| N14 | 전역 NaN · reset 실패를 env 복구로 가장하지 않음: 비유한 입력을 넣어 저장 경계에서 멈춤 + 경보가 lead 에 닿는 시험 | runner | |
| N16 | 경계 거절 · 오래된 점수: 거절 때 pause_used · delta 회귀 없음 · 점수 나이 off-by-one(`ex41.py:427`) 판정 | runner | |
| N22 | 최종 구조 감사 세 갈래(독립 · planner · verifier) 결과 표를 새 HEAD 로 채움 · 막음 0(M88: 11/02 표가 빈 채로 띄움) | lead | |
| N23 | 실행 창(약 2 일) 안에 Windows 재부팅 · 업데이트 예정 없음 | 팀장 · lead | 15:5x 읽음: 재부팅 대기 표시(WindowsUpdate RebootRequired · CBS RebootPending) 둘 다 없음 · 업데이트 일시 중지 만료 2026-11-07 08:04Z(11/07 17:04 KST). 6000 회 × 27.5 초 ≈ 46 시간 + 최대 연장 · 멈춤 약 8 시간 → 오늘 16 ~ 18 시 기동이면 11/06 밤 ~ 11/07 새벽 끝(추정) · 만료 전. 늦어지면 팀장께 일시 중지 연장 부탁 · 17:5x 팀장이 업데이트 일시 중지를 12/9 까지로 늘림(실행 창 안 재부팅 걱정 없음) |
| N24 | 기동과 함께 20 분 점검 예약 · 점검 문구가 HOLD · rc · 경계 적용 영수증 · 1 시간 산출 · 실패 수를 읽음 | lead | |

**기동 뒤 붙여도 학습에 영향 없음(평가 · 보고 · 영상 쪽 · 팀장 받아들임 D180 · 11/04 16:0x · 해당 단계 전까지)**

| # | 행 | 담당 | 증거 |
|---|---|---|---|
| N1 | D79 단계 끝 정식 분석 보고기(곡선 · lr · std · 위상 · W57 · CMP · 경로) · 첫 단계 끝(750) 전까지 | lead · runner | |
| N2 | B층 ①~⑦ · 평지 서 있기 촬영 · 첫 250 경계 B층은 이번 실행 제외 여부 팀장 판단 | scripter | |
| N4 | 무릎 토크 한계 붙음 비율을 점수 · 경계 기록 칸으로 | runner | |
| N9 | 영상 이름 D48 · R23 검사가 단계 끝 · 밀기 영상에 걸림(V5 이름 고침은 cf247103) | scripter | |
| N15 | 단계마다 켜지는 판정 가지 표와 가지마다 실제 평가 출력 채점 | analyst | |
| N17 | PROVENANCE 칸에 스윙 · 걸림 · 자세 명령 · critic 거울 · W86 · 명령 몫 칸 기재 | runner | |
| N18 | 기록 전용 진단(링크 접촉 · foot_slip 어댑터)이 오류 · 가짜 기록이 아님 | runner | |
| N19 | 제외된 8 FAIL · PPO 연결 시험 skip 처분 | runner | |
| N20 | 평가 자식이 커리큘럼 끔 · 지형 해시를 영수증에 | runner | |
| N21 | D125 DR 켠 평가 칸(배율 1.0)이 P1 점수 파일에(e5a908a2 는 planner 가지에만) | runner · planner | |
