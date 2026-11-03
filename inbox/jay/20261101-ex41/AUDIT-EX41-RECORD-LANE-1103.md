> 분류: 점검 자료 · EX-41 기동 전 세 갈래 감사 중 기록 갈래 (목록만 · 고치지 않음)
> 작성: planner · 2026-11-03 12:2x · 브랜치 `feature/fable-25a-jay`
> 근거: lead 11/03 12:1x 의뢰 · WORKLIST 473fad35 (D141~D164 · W 표) · CURRICULUM-GATES 69d386ec 「결정 반영」 표 · docs/FLOW.md · FLOW-experiment-cycle-1029.md (lead 가지 v1 · runner 가지 v1.1) · RULES-HUB 473fad35 · EX41-REQUIREMENT-REGISTER · EX41-LAUNCH-GAPS · EX41-LAUNCH-FINAL-AUDIT · runner HEAD ec82f5cd5389b7beb9129bbc70f9efb218b0a469 (`origin/feature/ex41-b6-b7-runner`) · mai-os `os/foothold-folder-plan.md` 97bbb2a (`D:/mai-wt/mai-os/runner-ex41-paths`, 원격 가지 0) · 실측은 Test-Path · LastBootUpTime · 폴더 목록만
> 요지: 결정은 있는데 코드 · 문서에 없는 것 8 건을 막음으로, 문서끼리 다른 것 · 카드 갱신 13 건을 낮음으로 적었다. 기동 직후 할 일 셋 가운데 W89 ONNX 만 카드가 있고(상태 · 시점은 낡음), P3 경계 보고 → 승인 → 켬 절차와 첫 250 경계 B층 영상은 카드가 없다. 본 기동 경로에서 U21 되읽기 함수가 D: 를 강제해 D164 (가) C: 자리와 충돌한다(읽기 · 미실행).
> 상태: 읽기 전용 감사 · 코드 · GPU · Kit · 시험 실행 없음 · 고친 것 없음

# EX-41 기록 갈래 감사 (lead 11/03 12:1x)

## 0. 범위와 등급

- 대조 축: WORKLIST 「확정」 D141~D164 · W 표 · CURRICULUM-GATES 「11/01 결정 반영」 표 · FLOW 둘 · RULES-HUB ↔ runner HEAD ec82f5cd 코드 ↔ 폴더 계획 7 절(97bbb2a).
- 등급: **읽기** = 파일 · 코드 줄을 열어 읽음(실행 안 함) · **실측** = 이 기기에서 Test-Path · 부팅 시각 · 폴더 목록 · **계산** 없음. 다른 세션 보고는 「읽기」 로만 옮겼다.
- 막음 = 결정이 코드 · 문서 · 카드에 없어 기동 직후 흐름이 끊기거나 기록이 남지 않는 것. 낮음 = 문서끼리 다르지만 기동 직후 흐름을 끊지 않는 것.
- 폴더 계획 97bbb2a 는 runner 의 로컬 mai-os 사본에만 있고(`git branch -r --contains` 0 · mai-os origin/main 의 이 파일 마지막 커밋 cce5b1e) 정본 저장소에는 아직 없다(읽기).

## 1. 막음 (8)

| # | 결정 | 코드 · 문서에 없는 것 | 근거(줄) | 등급 |
|---|---|---|---|---|
| M1 | D164 결정 2(가): EX-41 학습 출력은 `C:/Users/AI-WS01/s2_lab/ex41_main_YYYYMMDD_HHMMSS/main/<run>` (폴더 계획 7 절 · 코드 `ex41_startup.py:39 · 204~226 · 249~257` 이 이 C: 꼴만 허용) | 본 기동 경로의 **U21 되읽기** `train_start.py:670 · 677` 이 부르는 `verify_ex41_start_readback` · `write_ex41_start_readback` 은 `_require_d_drive(log_dir)` (`ex41_startup.py:730 · 783 · 197~201`) 로 **D: 가 아니면 ValueError** 를 낸다. 같은 `log_dir` 를 `validate_ex41_output_directory` (`:260~265`) 는 C: 꼴로 통과시키므로, 본 기동에서 env 생성 뒤 첫 학습 전에 멈출 것으로 읽힌다. CPU 시험 `test_ex41_startup_integration_cpu.py:796~849` 는 임시 경로라 이 조합을 안 잰다 | 읽기 · 미실행 | 코드끼리 다름 |
| M2 | D102 재생 목록 고정 폴더 `C:/Users/AI-WS01/s2_lab/_playlists/` · `EX번호-m단계-all|fail.m3u8` (11/01 23:0x 팀장) | 코드 `ex41_startup.py:223` `playlist_dir = <ROOT>/eval` · 폴더 계획 7 절 「재생목록 파일은 `eval/`」 · GAPS G11 「`s2_lab/_playlists`」 가 서로 다르다. EX-41 코드에 `.m3u8` · `_playlists` 문자열 없음(`foothold_s2/scripts/ex41_startup.py` · `ex41_score_watch.py` · `ex41_eval_once.py` · `ex41_ops.py` · `eval/ex41_w78_video_request.py` grep 0) | 읽기 | 결정 ≠ 코드 ≠ 문서 |
| M3 | D164 「EX-41 이 쓸 자리(학습 출력 · 평가 · 재생 목록 · **영상**)는 계획 7 절을 채운 뒤 기동」 | 97bbb2a 의 7 절은 cce5b1e 에 있던 「영상(본편) · 미확인 · scripter 가 적는다」 행을 지우고 대체 행이 없다. 「W78 영상 출력」 과 「W78 영상 산출」 두 행이 같은 경로 `D:/mai-tmp/ex41/w78_video` 로 중복. 본편(A · B · C층) 영상 자리는 7 절에 없다. 97bbb2a 자체가 정본 저장소 밖 | 읽기 | 7 절 미완 |
| M4 | D155 · D142: 좌우 대칭 기록을 단계 경계 보고(lead · 텔레그램)로 보이고 팀장 승인 뒤 다음 경계에서 critic 거울을 켠다. 자동 켬 없음 · 1000 회 제한 없음 | **카드 없음**: WORKLIST W 표에 「P3 경계 보고 → 승인 → 켬」 W 가 없고, CURRICULUM-GATES 표는 D155 를 W72 로만 가리킨다. **절차 문서 없음**: 켜는 길은 boundary `critic_mirror: true` 와 approvals `fields.critic_mirror: {decision_id, choices: [true]}` 를 같은 커밋에 넣고(`w72.py:94~101` 은 `choices` 를 요구) W72 APPROVED 영수증(gate · status · approval_id = approvals SHA · config_sha256 · config_commit 40 자 · decision_ids · 두 파일 경로, `start_runner.py:334~362`)을 넘기는 것인데, 이 절차는 runner 가지 analyst 문서 `IMPLEMENT-EX41-REQUIREMENT-FOLLOWUP.md` §P3 에만 있고 거기도 `choices` 를 안 적었다. 요구 등록부 P3 행(「approvals 에 critic_mirror 칸 없음 · 첫 1000 회 안 켤 길 없음」) 은 D155 이전 내용. 본 실행 사본 `ex41-fixed5000-approvals.yaml` 의 `fields` 에 `critic_mirror` 없음(승인 전이니 맞음). 보고 쪽 코드는 있음: `ex41_fixed.py:267~398` 경계마다 `critic_mirror_observation` (S = min/max · 0.8 · 연속 2 · `automatic_activation: False` · `request_manual_W72_approval`) · `ex41_ops.py:74~84` 단계 끝 보고에 `p3_state` · `:114~119` 텔레그램 `C:/ssd-cleanup-logs/tg-send.ps1` (실측 Test-Path True) | 읽기 · 실측 | 카드 · 절차 없음 |
| M5 | 「첫 250 경계 B 행」 = W76 B층 규칙 ①~⑦ (저장본마다 정책당 최대 4 편) 을 EX-41 첫 250 경계부터 | **카드 없음**: W76 상태 칸은 EX-40 「m6250 부터 루프」 기준이고 EX-41 행이 없다. GAPS 낮음 절은 「W76 B층 규칙 · W80 네 방향 영상 · EX-41 단계 끝 영상 (scripter · runner)」 라고 담당만 적었다. **코드 없음**: runner HEAD `foothold_s2/` · `_out/tools/` 에 `W76` · `b_layer` · `B층` 문자열 파일 0(시험 제외 grep). 단계 끝 영상 요청은 `eval/ex41_w78_video_request.py` 뿐 | 읽기 | 카드 · 코드 없음 |
| M6 | WORKLIST 규칙 8: 결정은 같은 커밋에서 ① 확정 D ② W 카드 ③ CURRICULUM-GATES 「결정 반영」 표 ④ view-latest | CURRICULUM-GATES 표 머리 「정본은 WORKLIST 확정 D80~D162」 · 표에 **D144 · D145 · D146 · D147 · D149 · D152 · D161 · D163 · D164 아홉 행 없음** (D143 · D148 · D150 · D151 · D153~D160 · D162 는 있음) | 읽기 | ③ 어김 |
| M7 | D143 P7 졸업 판정 승인(53fda76c) + lead P7-5 「복원 모드 오차 칸 기동 전 추가」 · P7-6 반복 폭 3/64 초과 HOLD | 53fda76c 는 `origin/feature/fable-25a-jay` 에만 있고 lead 가지 · runner 가지에 없다(`git branch -r --contains`). runner 코드는 졸업을 판정하지 않는다: `ex41_score_watch.py:165 · 211` `graduation_not_judged_separate_approved_spec_required` · `ex41_fixed.py:237~238` 「separate approved spec and final evidence required」. 복원 모드 **오차 칸**은 `ex41_score.py` · `curriculum/ex41_scoring.py` 에 error 필드 0(grep). analyst 11/02 09:51 메시지도 「졸업 함수 정본 · 허용값 고정본 주면 연결」(읽기) | 읽기 | 결정 ≠ 코드 (P7-5 는 기동 전) |
| M8 | D150 S2 이면 다음 실험 「T0′ 이어 학습 +500」 · FLOW 1 단계 「가능성 높은 다음 실험은 시작 스크립트까지 실제 저장본으로 DRY」 · U9 담당 planner | 0e7be9a3 `EX41-RESULT-SCENARIOS.md` 는 A(EX-42 T1) · B(T0′ +500) **계획 문장**만 있고, runner HEAD 에 다음 실험 설정 · 시작 스크립트 · DRY 영수증이 없다(`git ls-tree` 에 ex41 next · extend · ex42 파일 0). 이것은 planner 몫으로 남아 있다 | 읽기 | 코드 · DRY 없음 (내 몫) |

## 2. 낮음 (13) · 문서끼리 다르거나 카드가 낡은 것

| # | 무엇 | 다른 곳 | 근거 | 등급 |
|---|---|---|---|---|
| L1 | W89 ONNX(D144 · D162 「EX-41 기동 직후 scripter」) | 카드는 있으나 WORKLIST 행 상태 「대기」 · 시점 없음(「기동 직후」 는 CURRICULUM-GATES 표 D162 행에만). 코드 `foothold_s2/deploy/export_ex40_w89.py` · 시험 · `REPORT-W89-m6000-ONNX-CPU-1102.md` 는 runner HEAD(34982e13)에 이미 있음. 조건표 `contract.json` 은 `D:/mai-tmp/scripter/w89_export/` (저장소 밖, 실측 존재) 에 있고 D144 의 **명령 범위 · PD · 토크 한계 · 제어 주기 · 기본 관절각 값**이 없다(입출력 이름 · 「clip ±17 · default_joint_pos + 0.25·action 은 그래프 밖」 문장만) | 읽기 · 실측 | 카드 낡음 · 정본 밖 |
| L2 | D145 재부팅(EX-40 v3.2 재합성 뒤 · GPU0 Kit 예행 전) | 이 기기 LastBootUpTime **2026-11-02 21:29:49** (실측) 인데 W74 행 상태 「대기」 · D145 언급 없음 | 실측 · 읽기 | 카드 낡음 |
| L3 | 규칙 8 ④ view-latest | `C:/mai/wt/foothold-lab/view-latest` HEAD 69d386ec, lead HEAD 473fad35(D163 · D164 두 커밋 뒤) | 읽기 | ④ 어김 |
| L4 | FLOW-experiment-cycle-1029.md | lead 가지 = v1(10/29) · runner 가지 = v1.1(10/31 analyst §1a EX-40 D72~D77 예외) → 정본이 옛 판 | 읽기 | 판 갈림 |
| L5 | CURRICULUM-GATES 사본 | runner 가지는 10/31 c1cefb1a 판(「11/01 결정 반영」 표 없음) · lead 가지는 11/02 69d386ec | 읽기 | 판 갈림 |
| L6 | D142 · D155 「자동 켬 없음 · 1000 회 제한 없음」 | 비실행 사본 `ex41-approvals.yaml:11` `automatic.critic_mirror: D101` 과 `ex41.py:608~612` (`iteration<=1000` 자동 켬) 가 남아 있다. 본 실행 `ex41-fixed5000-approvals.yaml` 의 automatic 에는 없고 `ex41_fixed.py` 는 `_automatic` 을 부르지 않는다(grep 0) | 읽기 | 혼동 위험만 |
| L7 | D151 · W91 16 env 회전 진단(단계 끝 저장본 7 개 · 기록 전용) | `eval/ex41_turn_receipt.py` 와 계약 문서는 있으나 시험 밖 호출 0(`ex41_eval_once.py` · `ex41_score_watch.py` · `ex41_ops.py` · `ex41_startup.py` grep). 저장본이 남으니 사후 실행 가능 | 읽기 | 사슬 미연결 |
| L8 | D147 wt_guard 공용 훅 설치 승인 | W 카드 없음. runner HEAD `tools/wt_guard/` 는 `disk_guard.py` · `wt_config.py` 2 파일, 861d65ae 는 7 파일(`install.sh` · `inventory.py` · `post-checkout` · 시험 포함). 설치 여부 미확인 | 읽기 | 카드 없음 |
| L9 | D146 · D149 · D163 · D164 | W 카드 없음(D164 는 W90 이 34 사본만). D149 GPU 배정은 등록부 U8 만. 코드: 예행 경로 `ex41_startup.py:479 · 492` 가 cuda:0 강제, 본 기동 장치는 이 감사에서 안 읽음 | 읽기 | 카드 없음 |
| L10 | WORKLIST D164 행 | `C:\mai\projectsoothold-lab` 오타(폴더 계획 3 절은 `C:\mai\projects\foothold-lab`) | 읽기 | 오타 |
| L11 | 「P3」 이름 | FLOW-experiment-cycle §5 W50 P3 = 자동 촬영 · 요구 등록부 P3 = 거울 발동 경로 · gpu_jobs P3 = 시드 반복 · 코드 `p3_state` = 대칭 기록. 네 뜻 | 읽기 | 용어 충돌 |
| L12 | RULES-HUB D138 (5) 「학습 실행 폴더는 D: 에 둔다」 · FINAL-AUDIT Q14 「실행 폴더 D:」 · 등록부 P13 | D164 결정 2(가) 와 7 절 · 코드는 C: s2_lab. 뒤 결정(D164)이 이기지만 세 문서는 정정 표시가 없다. M1 의 원인과 같은 뿌리 | 읽기 | 문서 ≠ 결정 |
| L13 | 기동 직후 항목 U21(1 분 되읽기) · U7(첫 50 회 속도로 END_BY 재계산) | 등록부에만 있고 W 카드 없음. U21 코드는 M1 의 그 함수 | 읽기 | 카드 없음 |

## 3. 결정 = 코드로 읽힌 것 (막음 아님 · 읽기)

D141 lin_vel_z 0 (`ex41.py:381~384`, `_sync_rewards` 는 `:318 · 343 · 719` 에서 호출) · D152 headless (`record_c_layer.py:1225` 강제 True) · D153 직전 경계 점수 (`ex41_ops.py:25` `completed − 250`) · D154 W78 없을 때 결측 기록 (`ex41_symmetry.py:90` `missing_pairs`) · D156 END_BY 경고만 + 최대 연장 + 24 h (`ex41_startup.py:567~640` · 519e496b) · D157 C층 양보 표식 (`c_layer_queue.py:110 · 367~398` · `ex41_gpu_priority.py:11` `D:/mai-tmp/gpu/PRIORITY_BUSY_GPU1`, 지금은 없음 실측) · 7 절 자리 ↔ 코드 (`ex41_startup.py:39 · 40 · 204~226 · 240~244` 와 같은 문자열) · DRY 폴더 `C:/Users/AI-WS01/s2_lab/ex41_main_20261103_042946/` 는 `eval/` 만 있고 `main/` 없음(실측 · 「신규 run 만들지 않음」 과 맞음).

## 4. 기동 직후 할 일 셋 · 카드 여부 (물음에 대한 답)

| 할 일 | 카드 | 코드 | 남은 것 |
|---|---|---|---|
| W89 ONNX (D144 · D162) | W89 있음(상태 · 시점 낡음, L1) | export · 시험 · CPU 보고 있음 | 조건표 값 다섯 · 저장소 안 정본 · 팀장 결정 |
| P3 경계 보고 → 승인 → 켬 (D155) | 없음(M4) | 보고 · 텔레그램 · W72 검증 있음 | 카드 · 절차 문서(`choices` 포함) · 승인 영수증 누가 만드나 |
| 첫 250 경계 B 행 (W76 B층) | 없음(M5) | 없음 | 카드 · 코드 · 담당 |

## 5. lead 가 정할 것

M1 의 처리(되읽기 함수의 D: 강제를 D164 (가) 꼴로 넓힐지, 아니면 본 기동도 D: 로 할지) · M2 재생 목록 자리 하나로 · M3 7 절 영상 행 · 97bbb2a push · M4 · M5 카드 신설과 담당 · M6 · L3 동기화 · M7 P7-5 기동 전 여부 재확인 · M8 은 planner 가 DRY 를 만들지(카드 요청).

## 6. 안 한 것

코드 · 시험 · GPU · Kit 실행 없음 · 고친 파일 없음 · 본 기동 장치(`production_launch_status` 뒤 실제 CLI) 의 GPU 인자 미확인 · 다른 세션 결과는 재지 않음 · docs/FLOW.md(8/11 전체 흐름) 는 EX-41 항목이 없어 대조 대상에서 뺌 · 폴더 계획 1~6 · 8~11 절 미대조 · WORKLIST D80~D140 미대조.
