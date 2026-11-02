> 분류: 실험 준비 작업 목록 (정본)
> 작성: lead · 2026-11-02 14:4x
> 근거: 독립 검토 2건(ced6c43a 일정 검토 · 결정 대비 전수 감사) · verifier VERIFY-EX41-fixed5000.md · 팀장 11/02 14:2x 지시 · WORKLIST D80~D132
> 요지: EX-41 은 아직 학습 진입 경로가 없다. 막음 12건을 닫고 두 겹 검토 · GPU 예행 · 팀장 승인 뒤 기동한다
> 상태: 진행 중. 항목을 닫을 때마다 커밋 · 시험 · 검토자를 이 표에 적는다

# EX-41 기동 전 빠진 것 목록

팀장 지시(11/02 14:2x): 이전 실험에서 놓친 코드, 결정한 것, WORKLIST, 연결해야 하는 부분을 빠짐없이. 실험 중간 설정 변경 가능 · 영상 규칙 · 대칭 검증 · 정답 복제 시험 위험까지.

감사 기준: runner 통합본 ea51caab + 미커밋 3 파일, analyst ced6c43a, scripter 68cffa0f · 8cab09f2 · 606c9daf. CPU 118 통과 · 7 skip. Kit 거동은 전부 미확인.

## 막음 (기동 전에 반드시)

| 번호 | 내용 | 근거 | 담당 | 닫는 조건 |
|---|---|---|---|---|
| G1 | EX-41 학습 진입: load_plan · make_runtime · prepare_env_cfg · attach_runtime · apply_runtime_fields · 부모 이식 · 첫 리셋 전 DR 0.5 를 시작 경로에 연결. 지금 EX-41 함수를 부르는 곳은 시험뿐 | continuous.py:38,53 · w86_runtime.py:30,240 · ex41.py:750 · start_runner.py:1241 | runner | 실제 parser · env import 로 DRY 통과 + GPU 예행 첫 10 update |
| G2 | env 쪽 자세 명령(pose_cmd) 관측 생성. 없으면 첫 관측에서 멈춤 | start_runner.py:227-238, 233 | scripter | Kit 예행에서 관측 차원 · 0 열 출력 동일 |
| G3 | 끝 회차에서 학습 멈춤(runtime.finished · 최대 6501) | start_runner.py:326 · ex41_fixed.py:155 | runner | 5001 에서 끝나는 끝점 시험 |
| G4 | 상한 경계 회복이 소진보다 먼저 | ex41_fixed.py:96 | analyst | 751 멈춤 · 1501 · 1751 회복 → 재개 시험 |
| G5 | 최신 점수가 NaN · SHA 오류면 과거 PASS 로 덮지 않고 유지 | verifier H1 · ex41_fixed.py:157,177-181 · ex41.py:393,416,424 | analyst | 실제 JSON reader 로 정상 → 오류 순서 회귀 시험 |
| G6 | EX-41 채점기: foothold-ex41-score/1 로 39칸 maintenance_counts · stand_min_passed 를 칸별 숫자로. 없으면 750 회부터 DR 이 0.5 로 굳음(D130) | ex41_startup.py:139-212 · ex41_score.py(미커밋) | analyst + runner(루프) | m6000 실제 점수 폴더로 만든 파일이 기준표 39칸과 같은 숫자 |
| G7 | stand_min_passed 가 없으면 통과(64)가 아니라 실패 | ex41_fixed.py:187 · ex41.py:545 | analyst | 칸 지운 점수로 오류 시험 |
| G8 | preflight 부모 7500 → 6000(D124), 시험도 | ex41_start_preflight.py:18,76,166 · test_..._preflight_cpu.py:71-118 | runner | m7500 을 주면 거절되는 시험 |
| G9 | D132 지도 셋 강제: W57 · 그림자 기록 · W78 v2 · axis250 요약에서 한 모드라도 빠지면 실패 기록 | axis_v2_run.py:158 · axis250_loop.sh:51(EX-40 은 eval_gt 만) | scripter | --modes eval_gt 하나로 돌리면 실패하는 시험 |
| G10 | W78 v2 구현: 계단 시작 방향 0/30/60/90° · L2/L5 · 지도 셋 · D128 정지 yaw 와 정지 뒤 후진 횡 이탈 · w78_min_lr_ratio 출력(D101 발동 입력) | WORKLIST W83 · 계약 5f326ece 만 있음 · axis_v2_cells.py:15 는 평지 회전 | scripter | 답을 아는 자세로 방향 각 확인 + Kit 예행 |
| G11 | EX-41 루프 일체: 단계 끝(세 모드 + W57 + 촬영 + 전 프레임 검사) · axis250 · 그림자 · 재생 목록(고정 폴더 s2_lab/_playlists, 이름 EX41-m0XXXX) | EX-40 stage_loop2.sh · shadow_loop.sh:23 은 EX-40 채점기 | runner | 가짜 저장본 하나로 루프 한 바퀴 DRY |
| G12 | critic 거울 시험을 답을 아는 입력으로: 좌우 대칭 자세를 Kit 에서 놓고 잰 관측 쌍으로 M(x)=x′. 지금 시험은 환경 변수 없으면 skip, 돌연변이 셋 모두 생존 | test_ex41_b345.py:214-233 · ex41_critic_mirror.py:173-200 | scripter | 돌연변이 셋이 모두 실패하는 시험 · skip 0 |

## 낮음 (기동 전 가능하면, 아니면 첫 경계 전)

- D121 종료 조건 · 에피소드 길이 변경 때 「과제 변경」 기록 + 전후 같은 평가 (analyst)
- W72 승인 파일이 허락하는 칸은 swing · stumble · zero_yaw 셋. entropy · KL · 명령 몫 · 범위 · 지형 상한을 중간에 바꾸려면 승인 파일 커밋이 먼저. 명령 몫 · 범위 칸은 아직 없음 (analyst, W72 카드와 대조)
- 경계 거절 시 시계 되돌림으로 delta 500 · pause_used 1250 가능 · 오래된 점수 재사용 · load_state_dict 형식 검사 (analyst)
- W76 B층 규칙 · W80 네 방향 영상 · EX-41 단계 끝 영상 (scripter · runner)
- D93 계단 상대 각 히스토그램 (analyst)
- m6000 점수 폴더 map64 대 map64_b3 중 기준 정하기 (analyst)
- PPO 연결 시험 4 개 skip(EX41_PPO_CONSUMER_ROOT) → 통합본에서 skip 0 으로 (runner)

## 팀장 결정 대기

- 복원 지도 기록 전용 13칸을 DR 유지 판단에 넣을지. lead 권고: 넣지 않음(기록만), 판정은 정답 · 끔 26칸. 코드는 설정값으로 둘 다 가능하게.

## C층 (D131, m6000 정본)

- scripter 606c9daf: C층 대기열 · 가변 시드 녹화기 · CPU 12 통과. 다음: 독립 검토 → 한 편 먼저 Kit 촬영(GPU0, cuda:0) 후 직접 확인 → 전량 → 전 프레임 검사 → 재생 목록 → RESULT 형식 보고.

## 14:5x 추가 (C층 독립 검토 · planner 교차 검증 CROSSCHECK-EX41-1433)

C층 606c9daf 막음 6 (scripter): C1 기술 실패가 시드 4회 한도를 소모해 칸이 닫히고 대기열이 완료를 냄(c_layer_queue.py:222-223,312-320) · C2 연속 지형 모양이 시드 따라 바뀜(record_c_layer.py:1244) · C3 HUD heading · 옆 이탈 · 아래 띠 · 회색 「정책에는 0」 없음 · C4 전 프레임 검사 없음 · C5 재생 목록 없음 · C6 정본 m6000 고정값 · plan.json · 한 칸 시험 모드.

설계 v0.7 대 코드 어긋남: ① +500 연장 대상은 S2e(1.0 유지), 코드가 D126 과 맞음 → 설계 고침(planner) · ② 연장 레벨 Δ 0.5 대 0.2 → analyst 가 실측 근거로 제안 · ③ 명령 몫 2차가 n751 DR 램프 시작과 겹침 → n1751 로(analyst) · ④ 서 있기 복원 서술 → 설계 고침(planner) · lin_vel_z 가중이 경계마다 0 (ex41.py:376-377) 대 EX-40 −2.0 → m6000 실제 값 재기(analyst).

진행: runner G3 · G8 코드 · CPU 연결 보고(14:4x), analyst a0581766(G4~G7) 두 겹 검토 중.

G13 (14:5x, planner 확인): D125 DR 켠 평가 칸 배율 1.0 이 코드 · 인자 · 시험 모두 없음(eval_map_modes.py:91-104 가 DR 이벤트 삭제). 담당 planner(worktree planner-d125-1102), 기본 끔 출력 바이트 동일 + 배율 0/1.0 답 아는 시험. Q26 ② 는 코드(유지 때 단계 경계도 밈)를 정본으로, 설계 v0.7.2.

## 15:1x 추가 (세 번째 감사: EX-40 교훈 · 계보 · 흐름)

EX-40 그림자 채점 31개 중 마지막 PASS 는 m1250. m1500~m8000 은 전부 HOLD, retry 로 살린 저장본 0. 원인 둘 다 EX-41 에서 그대로 재발한다(재발하면 증거 없음 → DR 0.5 고정).

| 번호 | 내용 | 근거 | 담당 | 닫는 조건 |
|---|---|---|---|---|
| G14 | W57 rc=1 의 정체: 창 없는 하위 프로세스(CREATE_NO_WINDOW)에서 Git Bash sha256sum 이 stdin 없이 「Bad file descriptor」 로 죽음. 본 평가 · retry 모두 영수증 0 바이트. axis_v2.json 자료는 남아 있음 | run_axis_v2.sh:28,42 · ex40_eval_once.py:30-34(stdin 없음) · lead 확인 | runner | stdin=DEVNULL(또는 </dev/null) · 같은 방식 .sh 전수 · 창 없는 실제 하위 프로세스로 rc 0 재현 시험 |
| G15 | W15 연속 칸 incomplete 수정 38ee51df 가 EX-41 가지에 없음(fix/ex40-score-w15-seq-1101 · lead/w78-terrain-skill-1101 에만). ex41_scoring.py:11 이 옛 ex40_score 를 import | ex40_score.py:221-228 · M79 | analyst | 병합 + 실제 EX-40 평가 출력으로 PASS 재현 |
| G16 | 정본 계보: CANON-REGISTRY 에 EX-39 · EX-40 0건, m6000 미등록. 빠진 것: agent.yaml SHA · 평가기 HEAD 둘(38ee51df · 5c160641) · W57 retry 결과 경로 · 기준 점수 판정 HOLD(W57 칸 없음) · 단계 B3c · force_gt=true(복원 지도로 학습한 적 없음) · AdaSmpl p · 부모 없음(처음부터) | CANON-REGISTRY.json | lead (+ analyst 숫자) | 등록 커밋 + 값마다 실측 |
| G17 | W71(D78 「EX-40 끝나면 고칠 것」) 미착수: supervisor HOLD 뒤 미호출 · W57 사슬 rc1(=G14) · retry 영수증 · 복원 지도 요약 · 로그 이름 · CMP | WORKLIST W71 | analyst | 항목별 닫힘 |

낮음: 촬영 검정 프레임은 「첫 프레임」 이 아니라 env_step 0~186 에서 발생, 모두 cuda:1 · 2차에서 살아남(원인 미확인, 촬영 장치 분리 기록 · runner) · stage_loop done 조건에 W57 영수증 없음(runner, G11) · shoot_d51 · compose_d51 이 git 에 없음(??) → W75 이름으로 저장소에(scripter).

사실 확인: EX-40 T0 는 복원 지도를 실제로 썼다(use_gt_frac 7501 1.0 → 7600 0.115 → 8000 0.102, 7501~8000 평균 0.151, 약 85~89 % 복원).

G16 닫힘(15:2x): CANON-REGISTRY 에 EX-40_m6000 등록 48846e53. SHA(저장본 · env · agent · 기준 점수) lead 실측, force_gt true · AdaSmpl p 1.0(checkpoint 상태), 기준 점수 HOLD 와 W57 칸 없음 명시, current.ex41_parent · c_layer_canon 지정. (JSON 다시 쓰며 들여쓰기만 바뀜, 기존 3 항목 내용 동일)

15:2x 닫힘: analyst 08a8c99c 두 겹 검토(verifier VERIFY-EX41-08a8c99c 막음 0 · 독립 막음 0, CPU 55 · 101) → G4 · G5 · G7 · D133 닫힘, G6 소비 쪽 닫힘(생산 루프 G11 runner 남음). C1~C6 scripter 519a430f, verifier 재검토 중. C층 첫 한 편 1차는 대기열이 Isaac EULA 환경 변수를 안 넣어 7초 만에 실패(기술 실패로 정상 기록) → scripter 수정 중, lead 가 표준 env 로 2차 촬영 중.
