> 분류: A/정책학습 · Codex Worker 작업서 (sol) · 1 단계 코드
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-18 13:20
> 근거: `DESIGN-step1-moects-plus-marg.md` (이 폴더, ASTRA 검증 중) · E1 코드 `C:/isaac/ext/go2_rl_robotlab` @28b4516 · `C:/isaac/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/gap_training/gap_observations.py` · S2 교훈(`RESEARCH-heightscan-architectures.md` 1 절)
> 요지: 1 단계(E1 MoE-CTS 이어 학습 · 구멍 +1 · 바닥 없는 gap · MARG 발 보상 · 지형 갈래)에 필요한 코드를 CPU 로 만든다. ASTRA 답에 따라 갈릴 부분은 설정값으로 둔다
> 상태: 작업 지시 (CPU 만 · GPU 실행은 lead)

# sol 작업서: 1 단계 코드 (목표 16:30)

원본 저장소를 직접 고치지 말고 사본(`C:/Users/AI-WS01/s2_lab/step1_moects_marg/`)에서 작업한다. 표준 runner(`on_policy_runner_cts.py`) 와 `ActorCriticMoECTS` 를 기반으로 한다(S2 자체 학습기 아님).

## 만들 것

1. **구멍 = +1 을 세 곳에 같은 함수로.** teacher(privileged) · critic 의 높이 지도와 (M1 의) actor 지도가 모두 `height_scan_with_gap` (offset 0.5, miss +1, clip [-1, 1]) 를 쓰게 한다. critic 쪽 기존 scale(× 2.5)이 있으면 그대로 두되 miss 가 +1 로 들어가는지 확인. 시험: 같은 ray 입력에서 세 곳 값이 같음, 바닥 없는 칸이 +1 (기존 함수는 -1 → 반례로 CAUGHT).
2. **바닥 없는 gap 지형.** Isaac Lab `mesh_terrains.gap_terrain` 을 E1 지형 생성기에 넣고 폭 0.10 → 0.60 m (MARG Single-Gap 수준 1 · 4 · 8 = 10 · 40 · 60 cm), 비율은 설정값(기본 0.3). curriculum 은 E1 과 같은 승급 규칙.
3. **MARG 발 보상 3 항** (가중치 설정값, 기본 MARG Table I): feet air time Σ(t_air - 0.5) 1.0 (robot_lab 함수 재사용) · feet stumble ‖f_xy‖ > 4 |f_z| 일 때 -1.0 (robot_lab 재사용) · feet center (발 주변 9 점, 점 높이 < -0.2 면 가장자리, c(n² + 2n³) -0.01). feet center 는 Kit 안 레이 캐스트로 발 주변 높이를 읽어야 한다(우리 `feet_center_any9_v1` 은 CPU 시험만 있음, ASTRA 17ag). 바닥 없는 칸(miss)은 가장자리로 센다.
4. **E1 에서 이어 학습할 때 상태 이어받기.** E1 `model_20000.pt` (SHA c8951b79…) 의 가중치 · 정규화 통계 · 행동 std, 그리고 **명령 범위 · 보상 curriculum · 지형 curriculum 이 끝값에서 시작**하도록 `common_step_counter` 등을 맞춘다(S2 는 0 부터 다시 돌았다). 학습률은 E1 마지막 값(약 0.00017)에서 시작, warm-up iteration 수와 갱신 1 의 KL 상한은 설정값. 시작 영수증에 실제 값(명령 범위 · 보상 가중치 · lr · 지형 레벨 분포)을 적는다.
5. **판 둘을 설정 하나로.** `--arm M0` (actor 는 지금처럼 [latent 32, 몸 상태 45]) 와 `--arm M1` (+ 지형 갈래: 높이 187 → MLP [128, 64, 16] → e^h, actor 입력에 더함, 새 열은 0 으로 시작해 첫 행동이 E1 과 같게. + 추정 머리: student latent → MLP → v̂ 3 · ĉ 4, 시뮬 정답과 MSE). 붙이는 자리는 `--map-attach actor|student|both` 로 바꿀 수 있게(ASTRA 답 대기). 두 판은 다른 모든 설정이 같아야 한다(시험).
6. **걸음 모양 측정 도구.** 평가 중 다리별 접촉 시계열에서 (a) 두 발 지지 중 대각 비율 (b) 앞쌍 · 뒷쌍 비율 (c) 네 발 비행 비율 (d) duty factor. 이동 중(수평 속도 0.3 m/s 초과, 첫 1 초 제외)만. 석헌 님 `diag_gait.py` 정의와 맞춘다(`C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/sh_ame2/` 에 받은 사본이 있으면 참고, 없으면 `REPORT-seokheon-ame2.md` 1.3 절 정의).
7. **창 띄우지 않기 · 멈추지 않기.** 자식 프로세스는 `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`. 학습 중 중간 체크포인트 500 iteration 마다.

## 시험 (CPU, CUDA 숨김)

- 위 1 · 5 의 같은 값 · 같은 설정 시험, 기존 함수 반례 CAUGHT.
- M1 의 첫 행동이 E1 과 같음(지형 갈래 0 시작) · M0 와 M1 의 E1 부분 가중치가 같음.
- 이어받기: 시작 영수증의 명령 범위 · curriculum 값이 E1 끝값과 같음(E1 기록 `logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192` 에서 끝값을 읽어 대조).
- 실제 Kit 짧은 실행은 lead 가 한다. lead 명령 두 줄(M0 · M1, 10 iteration 예행)을 보고서에 적어라.

## 끝나면

`REPORT-step1-code.md` (바뀐 파일 · 시험 · 미확인 · lead 명령), `STEP1-SHA256SUMS.txt`. ASTRA 검증(`VERIFY-astra-18a.md`)이 오면 lead 가 설정값을 정해 알린다.
