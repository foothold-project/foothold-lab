> 분류: A/정책학습 · EX-41 결과 시나리오표 (U9)
> 작성: planner (Claude Fable 5.1) · 2026-11-02 20:1x
> 근거: FLOW-experiment-cycle-1029 1 단계 · WORKLIST D49(10/29 15:3x) · D56(10/29 21:1x) · EX41-REQUIREMENT-REGISTER 0e85c3d7 U9 행 · CARD-EX38-1029 §8(선례) · DESIGN-EX41-STAGE2-draft 660891be §1 · §2 · §4 · §5.8 · §5.12 · §11 · P7-GRADUATION-SPEC 53fda76c · analyst CONTRACT-EX41-SCORE-WATCH · IMPLEMENT-EX41-REQUIREMENT-FOLLOWUP(c6fff190 읽기) · `ex41_fixed.py` c6fff190 · `ex41_scoring.py`
> 요지: EX-41 이 끝났을 때 나올 수 있는 결과를 넷(S1 졸업 · S2 복원 미달 · S3 처방 미달 · S4 퇴행)과 「밖」 으로 결과 전에 고정하고, 처치마다 「어느 칸에서 보이고 어느 칸에서 안 보이나」 와 「다음 단계(EX-42 · W59)에서 터질 것」 을 적는다. 유력 다음 실험은 둘(A EX-42 T1 지형 · B T0′ 이어 학습 +500)이고 둘 다 **시작 스크립트가 아직 없다**(실측). DRY 는 계획만 적고 planner 는 만들지 않는다.
> 상태: v0.2(D143 · D146 · D148 · D150 반영) · 팀장 결정 U9-1~U9-4 대기 · 등록부 U9 칸은 lead 가지라 lead 가 이 경로를 적는다

# EX-41 결과 시나리오표 (U9 · 한 표 보기 전 등록)

## 0. 범위 · 가정

- 카드(lead 11/02 18:2x · 등록부 U9 행): 「결과 시나리오표 등록 · 『어느 칸에서 보이나 · 다음 단계에서 터질 것』 · 유력 1~2 개 다음 실험 DRY」. 규칙 D49: 실험 시작 때 등록하고, 가능성 높은 1~2 개는 시작 스크립트까지 미리 만들어 실제 경로를 점검한다. 결과가 표 밖이면 억지로 끼우지 않고 해석부터 다시. 규칙 D56: 처치가 어느 칸에서 보이고 어느 칸에서 안 보이나 · 다음 단계에서 터질 것을 반드시 적는다.
- 가정 1: lead 18:2x 카드의 문구는 「다음 실험 DRY **계획**」 이다. RULES-HUB 1 절에서 planner 는 구현 · GPU 를 하지 않으므로 시작 스크립트 · DRY 실행은 여기 적힌 계획을 lead 가 scripter · runner 에 배정한다. planner 가 만든 코드는 없다.
- 가정 2: 「등록」 자리. CARD-EX41 파일은 없고(실측 `git ls-tree`: CARD-EX36 · CARD-EX38 만) 등록부 `EX41-REQUIREMENT-REGISTER.md` 는 lead 가지(`feature/verify-v2-mvp-jay`)에 있어 planner 가 고치지 않는다. 이 파일이 EX-38 카드 §8 에 해당하는 「시나리오표」 이고, 등록부 U9 칸에는 이 경로를 lead 가 적는다.
- 가정 3: 판정 대상은 P7 정본(`P7-GRADUATION-SPEC.md` 53fda76c)의 측정 셋 M1(n4751 경계 · 저장본 n4750) · M2(n5001 경계 · 저장본 n5000) · M3(학습 뒤 끝 저장본 최종 평가) 과 문턱 G1~G8 이다. 여기서 문턱을 새로 만들거나 넓히지 않는다. 연장 · 유지로 번호가 밀리면(연장 때 경계 n5251 · n5501) 같은 규칙으로 읽는다.
- 등급 표기: 결정 · 설계 · 코드 · 실측 · 계산 · 가정 · 읽기(다른 세션 결과, 미재측).

## 1. 판정 폭과 기준선 (결과 전 고정)

| 항목 | 값 | 등급 · 근거 |
|---|---|---|
| 생존 반복 폭 | 3/64 | 실측(D60 · 설계 §2 (나) 「반복 폭 3/64 실측」) |
| 추종 오차 폭 | 단계 관문 +0.02 · T0′ 상대선 +0.05 | 설계 §4 S2a 끝 관문(+0.02) · T0′ 관문(D60 꼴 · 가정 +0.05) |
| 절대선 | 세 모드 생존 ≥ 60/64 · 오차 ≤ 0.15 | 결정 D57 |
| yaw | abs(yaw, 전진 1.0 · heading 끔 · 6 s) ≤ 5° · 저장본 3 연속(n4500 · n4750 · n5000) | 결정 D86 · P7 G5 |
| 서 있기 | ≥ 61/64 | 결정 D130 · YAML `stand_min_passed 61` |
| 복원 실제 소비 | T0′ 평균 use_gt_frac ≤ 0.3 | **결정 D143 P7-4**(11/02 20:2x · v0.1 가정값)(P7 G7 · 팀장 결정 P7-4 대기 · EX-40 T0 0.151 의 두 배, D136) |
| 기준선 저장본 | 부모 EX-40 m6000 `scores-b/score_6000_d5e9ec400f33.json` | 결정(팀장 11/02 14:0x) · 실측(planner 재읽음): 정답 back1.0 64/64 · 0.1487 / 끔 back1.0 **60/64 · 0.1507(미달 칸)** / diag-back+side+ 정답 63 · 끔 62 / eval_pred 최소 생존 62 · **오차 칸 없음** |
| 기준선 대칭비 S(정답) | 옆 0.930 · 앞 대각 0.948 · 뒤 대각 0.883 · 회전 0.993 | 읽기(analyst IMPLEMENT §P3 후속 · `score-watch-b/model_6000_d5e9ec400f33/map64/map_modes.json` 재계산 · planner 미재측) |

m6000 의 끔 back1.0 60/64 · 0.1507 은 D57 미달 칸이고 S2a 끝 관문(n751)의 필수 통과 칸이다(설계 §2 · §9 Q18). 그래서 S3(처방 미달) 는 「부모보다 나빠짐」 이 아니라 「부모의 미달 칸을 끝까지 못 넘김」 으로 읽는다.

## 2. 어디서 보이나 (파일 · 키 지도)

학습 run 폴더(`run_dir`, 기동 때 정해짐) 와 평가 폴더(`out_root` · `score_dir`, analyst 계약) 기준. 이름은 코드 · 계약 읽기이고 실제 EX-41 산출은 아직 없다.

| 무엇 | 파일 | 키 · 내용 | 언제 | 등급 |
|---|---|---|---|---|
| 250 경계 점수(정본) | `<score_dir>/score_<N>_<sha12>.json` (`foothold-ex41-score/1`) | `metrics.maintenance_counts`(39 칸 기록) · `maintenance_pass`(26 칸 판정 · D133) · `metrics.stand_counts` · `stand_min_passed` · `stage_pass`(항상 false 유지) · `metrics.training_knee_effort`(U10) · `metrics.critic_mirror_symmetry`(P3 S 값 · 모드마다 20 짝) | 저장본 n250k 마다 · 비동기(경계 뒤 도착 가능, `maximum_score_age 500`) | 코드 `ex41_scoring.py:118~130` · 계약 CONTRACT-EX41-SCORE-WATCH(읽기) |
| 칸별 원자료 | `<out_root>/.../map64/map_modes.json` · stand · W57 NPZ · W78 v2 출력 | eval_gt · probe(끔) · eval_pred(복원) 13 명령 × 생존 · 오차 / 서 있기 세 모드 / yaw 누적(30 칸) / 계단 240 조합 · `min_lr_ratio`(방향별 실제 대 명령 이동비 중 작은 값) | 같음 | 코드 · 계약(읽기) · EX-40 선례 실측 |
| 단계 · DR 적용 | `<run_dir>/ex41_application.jsonl` | 적용된 단계 id · DR 배율 · 유지(pause) · 연장 | 경계마다 | 코드 `ex41.py:276` |
| 학습 쪽 기록 | `<run_dir>/stage_log.jsonl` | `terrain_distribution`(50 회 · 종류별 env 수 · 레벨 분포) · `promotion_readback`(P8 실제 승급 · 강등 · 불일치) · `config_consumption`(U12 구 · 신 설정 걸음 비율) · `final_evaluation_pending` | 50 회 · 경계 · 끝 | 코드 · analyst IMPLEMENT(읽기) |
| 계측 | `<run_dir>/ex41_w86.jsonl` | `knee_effort.joints`(무릎 0.9 비율) · `all_link_contact`(U15) · foot_slip(U16, 가중 0) | 회차 끝 | 읽기(analyst) · Kit 미확인 |
| 치명 오류 | `<run_dir>/ex41_fatal.jsonl` (`ex41-fatal/1`) | 전역 NaN · reset 실패 · stop_requested | 발생 때 | 읽기 · 실행기 연결 미완(U6) |
| 끝 저장본 평가 요청(P7 M3) | `<run_dir>/final_eval_requests/final_<N>_<sha12>.json` (`foothold-ex41-final-eval-request/1`) | `status pending` · 끝 저장본 sha · `graduated false` · `dr_scale` · `full_dr_reached` | 학습 종료 뒤 마지막 저장 직후 | 코드 `ex41_fixed.py:222~245`(c6fff190 1eeb03b2) · **요청만 있고 판정 소비자는 없음** |
| 졸업 판정(정본) | `graduation.json` (`foothold-ex41-graduation/1`) | G1~G8 PASS/FAIL · 미달 줄 · spec_sha256 | M3 뒤 | P7 §6 계약 · **구현 없음** |
| 복원 실제 소비 | 학습 기록 use_gt_frac | T0′ 구간 평균 | T0′ | D136 · **키 위치 미확인**(EX-40 T0 0.151 은 lead 보고 읽기) |
| 영상 | 단계 끝 A층(D85 지형 기술 세트 · W80 네 방향) · B층 7 규칙 | 뒷발 끌림 · 정지 뒤 몸 돌기 · 후진 왼쪽 치우침의 눈 확인 | 단계 끝 | 결정 · 판정에는 안 씀(지표 §5.8 셋이 잰다) |

## 3. 처치마다 「보일 칸 · 안 보일 칸」 (D56)

| 처치(설계 §4 · §5) | 보일 칸(여기서 안 보이면 처치가 안 먹은 것) | 안 보일 칸(여기서 달라지면 다른 원인) | 처음 보이는 경계 | 등급 |
|---|---|---|---|---|
| 자세 명령 2 칸 0 초기화(끝에 붙임, §2.1) | n0 점수표 = 부모 m6000 점수표(차이 0 ± 반복 폭, 수술 시험) | 그 뒤 전부(값 0 고정이라 영향 없어야 함) | n0 | 설계 |
| 회전 명령 0 때 회전 L1 −0.5(§5.1) | yaw250 abs(전진 1.0) · 정지 진입 뒤 각속도(기록) · W57 누적 heading 부호 | 13 명령 생존 · 추종 오차(회전 오차는 작아 묻힘) | n251 | 설계 · 결정 D89 |
| 발 들어 올림 비용 w_swing −10 · 걸림 −2(§5.6 · D123) | W78 v2 계단 생존 · 이동 비율 · 걸림 횟수 · A층 뒷발 끌림 | 평지 W15 생존(이미 64 근처) | n251 · 단계 끝 영상 | 설계 · 결정 |
| 같은 처치의 부작용 자리 | **서 있기**: 61/64 미만이면 D130 이 스윙 가중을 한 번 반감(코드 `ex41_fixed.py:187~192`) → `ex41_application.jsonl` 에 남음 | | 경계마다 | 코드 |
| heading 전진 비율 0.5 → 0.3(§5.2) | yaw250(치우침이 커질 위험 쪽) | 생존 | n251 | 설계 |
| 후진 1.0 처방: 몫 14 · 범위 −1.3 · 대각 후진 2.5(§5.3) | back1.0 세 모드 오차 ≤ 0.15 · 끔 back1.0 생존(부모 60) · diag-back 좌 · 우 ≥ 60 | 전진 · 옆 칸. **잠재 손실 칸**은 몫을 줄인 전진 0.5 · 1.0 · 제자리 좌 · 우(≥ 기준 −3 · ≤ +0.02) | n751(S2a 끝 관문) | 설계 §4 |
| DR 램프 0.5 → 1.0(§5.9) | 유지 26 칸 하락 → `maintenance_pass false` → 유지(pause) · DR 켠 평가 칸(D94 · 가정 56/64 · 기록) | 지도 모드 차(정답 대 복원 · 끔)는 DR 과 무관해야 함 | n1001 부터 | 설계 · 코드 |
| L0~2 → L5 성과 승급(S2d · §5.5) | `terrain_distribution` 레벨 중앙값 · L5 비율 · `promotion_readback` · W78 v2 고정 L5 | W15 기준축(L0~2 고정) | n2751~ | 설계 · 코드(P8 CPU) |
| T0′ 복원 지도 전환 | probe · eval_pred 생존 대 eval_gt(≥ GT−3) · 오차(≤ GT+0.05, **eval_pred 오차 칸 없음 → 끔만 가능**, P7-5) · use_gt_frac | 정답 모드 자체 · DR(1.0 고정) | n4751 · n5001 | 설계 · 코드 · 실측(칸 없음) |

## 4. 결과 시나리오표 (S1~S4 · 밖)

판정은 P7 M3(끝 저장본 최종 평가) 로 하고 M1 · M2 는 추세 · 반복 폭 확인에 쓴다. 둘 이상 맞으면 **나쁜 쪽이 이긴다**(S4 > S3 > S2 > S1). 표 밖이면 해석부터 다시(D49).

| 시나리오 | 조건(M3 · 결과 전 고정) | 어디서 보이나 | 다음 실험 | 미리 만들기(§5) |
|---|---|---|---|---|
| **S1 졸업** | P7 G1~G8 전부 PASS: 39 칸 D57(60/64 · 0.15) · 복원 · 끔 ≥ 정답 −3/64 · 오차 ≤ 정답 +0.05(끔) · yaw ≤ 5° 3 연속 · 서 있기 ≥ 61 · use_gt_frac ≤ 0.3(가정) · DR 1.0 · 유지 실패 0. 그리고 M2 와 M3 의 같은 칸 차이가 반복 폭 안 | `graduation.json` PASS · `score_<끝>_*.json` · `final_eval_requests/` 의 sha 일치 | **A. EX-42 T1 지형 판**(W59 · D81 · EX-42 초안 v0.2 §12) | 시작 스크립트 **없음** → 만들 것(§5 A) |
| **S2 복원 미달** | G1 · G2 · G5 · G6 PASS(평지 · 정답 모드는 유지) 인데 G3 또는 G4(복원 · 끔 상대선) 또는 G7(use_gt_frac) FAIL | 같은 점수 파일의 probe · eval_pred 줄 · use_gt_frac | **B. T0′ 이어 학습 +500**(복원 지도 유지 · 처치 없음 · 한 번) 을 팀장 결정 안으로. EX-42 자동 기동 없음(Q11) | 이어 학습 경로는 있음(runner U5 abf3d733 · CPU, 읽기) 이나 **T0′ 연장 설정은 없음**(§5 B) |
| **S3 처방 미달** | back1.0 또는 diag-back 좌 · 우(S2a 처방 칸) 가 M3 에서 G1 · G2 FAIL, 전진 0.5 · 1.0 · 서 있기는 기준 −3 안 | `maintenance_counts` 의 back1.0 · diag-back 칸 · 조기 신호는 n751 S2a 끝 관문(`ex41_application.jsonl`) | 처방 재설계(몫 · 범위 · 보상 항) 카드만 · 다른 시드 아님(D21) | 카드만 |
| **S4 퇴행 · 안전** | 전진 0.5 · 1.0 · 제자리 · 서 있기 가운데 하나라도 기준 −3 넘게 하락 또는 서 있기 < 61 또는 yaw > 5° 3 연속, 또는 안전 멈춤(D29 내림세 · GATE-v3 규칙 5 · `ex41_fatal.jsonl`) 으로 끝 저장본이 T0′ 가 아님 | `maintenance_pass false` 연속 · `stand_counts` · yaw250 · `ex41_fatal.jsonl` · `final_eval_requests` 없음 | 되돌림 · 처치 분리(DR 램프 대 처방 가운데 하나만) 카드만 | 카드만 |
| **밖** | 위 넷에 안 들어옴. 예: M2 와 M3 의 같은 칸 차이가 반복 폭을 넘음(측정 불안정) · 점수가 HOLD 영수증만 남음(W78 v2 미완주 · 자식 실패) · `final_eval_requests` 는 있는데 M3 평가가 안 돎 | HOLD 영수증 · `children/<phase>/` 로그 | 해석부터 다시 · 측정 장치 먼저 | - |

S2 의 「다음 실험」 B 는 팀장 결정 사항이다(P7 Q11 「미달이면 EX-42 자동 기동 없음」 과 EX-42 초안 §12 는 「시작 안 함」 까지만 정했고 그 다음은 안 정했다). planner 안은 B 이고 까닭은 §5 B.

## 5. 유력 다음 실험 둘과 DRY 계획 (D49 「시작 스크립트까지 미리」)

실측(11/02 20:0x `git ls-files` · `git ls-tree`): analyst 사본 c6fff190 과 lead 가지 0e85c3d7 어디에도 `ex42` 로 시작하는 설정 · 스크립트가 없다. 둘 다 새로 만들어야 하고 planner 는 만들지 않는다(가정 1).

### A. EX-42 T1 지형 판 (S1 때)

결정 **D146**(11/02 20:2x 팀장): EX-42 자동 기동은 없다. EX-41 졸업 판정(P7 · D143) 이 나오면 그때 묻고, 결과가 매우 유의미하면 텔레그램으로 알린다. **D148**: 진입 목표 11/5 06:00 이전 · END_BY 는 M77 그대로. 아래 DRY 는 그 물음에 바로 답하려고 미리 준비하는 것이지 자동 사슬이 아니다.

| 항목 | 내용 | 등급 |
|---|---|---|
| 입력 | `graduation.json` PASS(spec_sha256 핀) · 끝 저장본 sha · 레벨 분포 히스토그램 · 마지막 점수표(설계 §11 「원장에」) | P7 §6 · 설계 §11 |
| 바뀌는 것 | 레벨 상한 5 → 9(`level_cap`) · W78 v2 고정 L3 평가 칸 · D44 계단참 회전 · 계단 위 정지 재출발 칸 · 명령 몫 그대로 · 깃발 슬롯 14 는 몫 0 으로 등록 | 설계 §11 · EX-42 초안 v0.2 |
| 만들 것(lead 배정) | ① `ex42.yaml`(고정 일정 · 경계마다 DR 램프, 설계 §5.9 「다음 판부터 램프」) ② 시작 스크립트(EX-41 시작 스크립트에서 부모만 바꿈) ③ W59 카드 ④ `graduation.json` 을 읽는 preflight(EX-42 초안 §12) | 계획 |
| CPU DRY 목록 | (1) `python _out/tools/worklist_gate.py W59` 통과(지금은 **W55 MISSING_PATH 로 막힘**, 등록부 WL233) (2) 부모 sha = `graduation.json` 의 끝 저장본 sha 대조(불일치 거절 시험) (3) 실제 argparse + 학습 env import(prelaunch 교훈 R1: 가짜 경로 시험은 못 잡는다) (4) EX39_SLOTS 밖 슬롯 14 등록이 W55 파서에서 거부되는 것을 답 아는 입력으로 확인(W60 코드 없음) (5) `level_cap` 9 가 `terrain_levels_mixed` 에 실제로 읽히는지 (6) 실제 끝 저장본 바이트로 loader 한 번 | 계획 · 실행은 runner · scripter |
| GPU DRY | Kit 1 회차(GPU1 · 촬영 없음) 는 lead 승인 뒤 · RH66 무인 사슬 꺼짐 · 판마다 기동 승인(RH109 · RH208) | 결정 |

### B. T0′ 이어 학습 +500 (S2 때 · **팀장 결정 D150**, 11/02 20:2x)

| 항목 | 내용 | 등급 |
|---|---|---|
| 무엇 | 끝 저장본에서 그대로 이어 복원 지도 500 회 더(처치 · DR · 몫 바꾸지 않음). 판정은 같은 P7 표를 밀린 번호(M1′ n5251 · M2′ n5501 · M3′ 끝) 로 한 번 더 | 설계 §5.12 와 같은 꼴 · 계획 |
| 까닭 | S2 는 「평지는 되는데 복원 지도 노출이 모자람」 이라 변수 하나(노출 길이)만 늘리는 것이 가장 작은 다음 실험. EX-40 T0 가 500 회에 use_gt_frac 0.151 까지 내려간 선례(D136 · 읽기) | 계획 · 읽기 |
| 상한 | 한 번(+500). 같은 조건 누적 1,000 회는 D06 상한 1,500 안 | 결정 D06 · 계산 |
| 있는 것 | same-run resume 경로(runner U5 abf3d733 · CPU 18+29 PASS · Kit 미확인, 읽기) | 읽기 |
| **없는 것** | 고정 일정의 연장은 S2e 에만 붙는다(`extension_updates 500 · maximum_extensions 1`, D126). **T0′ 를 늘리는 설정 항목이 없다** → 새 YAML(또는 `fixed_update` 를 5500 으로 둔 두 번째 일정) 이 필요하고 그것이 「막는 칸」 인지(W72 어댑터로 되는지) lead 판단 | 코드 · 설정 실측(P7 §1) |
| CPU DRY 목록 | (1) 끝 저장본 sha · 회차 · 설정 sha 가 `final_eval_requests` 의 값과 같은지 (2) 이어 학습이 `graduated False` 를 유지하고 `requires_review` 를 새로 적는지 (3) 번호가 밀린 경계(5251 · 5501) 를 `p7_spec_check.py` 가 받는지(지금은 5001 까지만 핀) | 계획 |

### C. S3 · S4 는 카드만

처방 재설계 · 되돌림은 결과를 봐야 값이 정해지므로 미리 만들지 않는다(EX-38 선례 S3 · S4 와 같음).

## 6. 다음 단계(EX-42 · W59)에서 터질 것 (D56)

| # | 터질 것 | 어디서 | 지금 상태 | 누가 |
|---|---|---|---|---|
| 1 | W59 카드의 앞 일 관문 `worklist_gate W59` 가 W55 MISSING_PATH 로 막힘 | 등록부 WL233 · #555 L1605 | 막힘 | lead(W55 증거 경로) |
| 2 | `graduation.json` 을 만드는 판정기가 없다. runtime 은 `final_eval_requests` 요청(pending) 까지만 | P7 §6 · `ex41_fixed.py:222~245` | 요청 생산만(CPU 2 PASS, 읽기) | runner · analyst(연결) · planner(정본) |
| 3 | 복원 모드(eval_pred) 추종 오차 칸이 점수 파일에 없어 G4 를 끔으로만 잰다 | P7-5 · `score_6000` 실측 | 미결 | lead |
| 4 | 깃발 슬롯 14 를 W55 파서가 거부(W60 코드 없음) | 설계 §11 · `continuous.py` | 코드 없음 | scripter |
| 5 | T2 평균대 · T3 틈은 메시 교체 = 판 시작 경계에서만(Q17) | 설계 §11 · 15-TERRAIN | 미결 | 팀장 |
| 6 | DR 을 EX-42 부터 경계마다 램프로 · DR 켠 평가 칸 문턱 56/64 는 가정값 | 설계 §5.9 · §5.8 | 가정 | 팀장(값) |
| 7 | 레벨 분포 근거(W86 「경계마다 종류별 env 수 · 레벨 분포」) 는 P8 CPU 기록까지. Kit 에서 실제 승급 미확인 | 등록부 WL264 · analyst P8 | Kit 미확인 | runner |
| 8 | 무인 사슬 꺼짐(RH66) + 판마다 기동 승인 → Q5 「EX-42 로 이어짐」 은 자동이 아니라 승인 둘 | 등록부 RH66 · 감사 Q5 | 결정 필요 | 팀장 · lead(U22) |
| 9 | P3 거울: EX-41 의 `critic_mirror_candidate`(S < 0.8 두 경계) 결과로 지형 판 시작 경계에서 켤지 정함. 자동 켬 없음 | analyst P3 후속(lead 19:3x 해석) | 해석 단계 | lead · 팀장 |
| 10 | 「다른 시드」 는 모든 과정 끝에 한 번(D21) → EX-42 가 아니라 그 뒤 | D21 · R11 | 규칙 | - |
| 11 | 끝 저장본 평가(M3) 가 학습 GPU 가 비워진 뒤 GPU1 에서 돌지, 그 사이 다음 판 기동과 겹치지 않을지(GPU 줄) | P7 M3 · D61 · D62 | 미정 | lead |

## 7. 결정 물음

| 번호 | 물음 | planner 안 | 누가 |
|---|---|---|---|
| U9-1 | S2(복원 미달) 의 다음 실험을 「T0′ 이어 학습 +500 한 번」 으로 미리 둘지, 결과 뒤 결정으로 남길지 | 미리 둔다(변수 하나 · D06 안). 다만 T0′ 연장 설정이 없어 새 일정 파일이 필요(§5 B) | 팀장 → **닫힘 D150**(11/02 20:2x): 미리 둔다. T0′ 연장 설정이 없다는 막음은 그대로(§5 B 「없는 것」) |
| U9-2 | 둘 이상 맞을 때 S4 > S3 > S2 > S1 순서 | 그대로(나쁜 쪽 우선 · EX-38 선례와 같음) | lead |
| U9-3 | A · B 의 시작 스크립트 · CPU DRY 담당과 시점 | scripter(스크립트) · runner(DRY) · W55 경로 보충 뒤 · EX-41 S2b 안(n1750 전) | lead |
| U9-4 | 「밖」 가운데 「M2 · M3 차이 > 반복 폭」 을 측정 불안정으로 다루는 규칙 | 같은 저장본 두 번 측정이라 반복 폭 밖이면 평가 장치 점검이 먼저 | lead |

## 8. 안 한 것 · 미재측

- 코드 · 스크립트 · 설정 파일을 만들지 않았다(가정 1). 등록부 U9 칸 · CARD 파일을 고치지 않았다(가정 2).
- analyst 숫자(대칭비 S · CPU PASS 수 · 평가 순서 · 파일 이름 대부분) 는 c6fff190 문서 · 코드 읽기이고 planner 가 다시 돌리지 않았다. `use_gt_frac` 의 기록 위치(파일 · 키) 는 미확인.
- EX-41 `run_dir` · `score_dir` 실제 경로는 기동 전이라 없다. 표의 경로는 계약의 자리 표시다.
- P7 정본의 열린 물음(P7-1~P7-7) 은 그대로다. 이 표는 그 답에 따라 G7 값 · G4 모드만 바뀐다.

## 9. 근거 경로

- 규칙: `inbox/jay/20261028-plan/FLOW-experiment-cycle-1029.md` §1 1 · 6 · §5 P4 / `WORKLIST.md` D49(75 행) · D56(82 행) / `CARD-EX38-1029.md` §8
- 등록부: `inbox/jay/20261101-ex41/EX41-REQUIREMENT-REGISTER.md` 0e85c3d7 U9(196 행) · WL233(86 행) · WL264(100 행) · RH66(141 행) · P7(221 행) / `EX41-LAUNCH-FINAL-AUDIT.md` Q5(29 행) · 52 행
- 설계: `inbox/jay/20261101-ex41/DESIGN-EX41-STAGE2-draft.md` 660891be §1 · §2 · §4 · §5.8 · §5.12 · §10 · §11 / `P7-GRADUATION-SPEC.md` 53fda76c §2 · §3 · §5 · §6 · §9 / `inbox/jay/20261102-ex42/DESIGN-EX42-TERRAIN-draft.md` 68c737a9 §12 · §13b
- 코드(analyst 사본 c6fff190, 읽기 전용): `foothold_s2/curriculum/ex41_fixed.py` 20~27 · 187~192 · 222~245 · 308~312 / `ex41_scoring.py` 118~130 / `ex41.py` 276 / `ex41_score_watch.py` 211 · 238 · 413 / `inbox/jay/20261102-analysis/CONTRACT-EX41-SCORE-WATCH.md` · `IMPLEMENT-EX41-REQUIREMENT-FOLLOWUP.md`
- 실측: `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/scores-b/score_6000_d5e9ec400f33.json`(planner 재읽음, P7 §1) · `git ls-files | grep -i ex42` 0 건(11/02 20:0x)
