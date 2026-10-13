> 분류: 실험 결과 (MuJoCo sim-to-sim 평가)
> 작성: 오흥재 (lead 세션 하위 작업 · Claude 실행) · 2026-10-13
> 근거: RoboGauge v1.1.9 (add2c7e) StressPipeline 원출력 `_eval/out/robogauge/stress/go2_lab_stress_*/*/stress_benchmark_results.yaml` · 집계 `_eval/out/robogauge/summary.json` · 논문 arXiv 2602.00678 v4 Table IV·XIII·XIV · go2_rl_robotlab README 표 (commit 28b4516)
> 요지: 기지 답 둘이 맞았다 (0.6953 → 0.6954 · 0.6984 → 0.6970). 같은 틀로 잰 E1·E2 는 Score 0.5258~0.6141 로 두 기준 정책보다 0.08~0.17 낮고, 네 checkpoint 모두 model_20499 가 model_20000 보다 높다.
> 상태: 측정 완료 (같은 기기 재실행 동일 확인) · 해석은 시드 2개 · checkpoint 4개 범위

# MoE-CTS E1·E2 RoboGauge 평가

## 결론 다섯 줄

1. **틀이 맞는지 먼저 확인했다.** 저자 정책 두 개를 같은 명령으로 돌려 0.6953 → **0.6954**, 0.6984 → **0.6970** 이 나왔다. Tracking·Safety·Quality·Level 도 README 값과 0.002 이내다 (§3).
2. **E1·E2 점수** (Score): E1 model_20000 **0.5258** · model_20499 **0.5867** · E2 model_20000 **0.5400** · model_20499 **0.6141** (§4).
3. **두 기준 정책 (0.6954 · 0.6970) 보다 낮다.** 가장 가까운 E2 model_20499 도 0.08 낮다. E2 model_20499 를 지형별로 보면 평지만 거의 같고 (-0.005 · -0.019), 계단 내리기에서 가장 크게 벌어진다 (-0.145 · -0.184).
4. **20499 가 20000 보다 높다** (E1 +0.061 · E2 +0.074). 평지 점수가 가장 많이 오른다 (+0.144 · +0.154). 학습 로그에서 명령 범위가 iteration 20000 에 ±0.5 → ±1.0 m/s 로 넓어졌고 RoboGauge 는 ±1.0 m/s 로 시험한다. 이 둘을 원인으로 잇는 것은 **추정** 이다.
5. 영상 19편 (기준 정책 7 · E1 model_20000 12) 을 찍었고 전 프레임 검사에서 검은 프레임 · 단색 프레임 0 이다 (§6).

## 1. RoboGauge 가 재는 것 (쉬운 설명)

학습은 Isaac Lab 에서 했다. RoboGauge 는 그 정책을 **다른 물리 엔진 (MuJoCo)** 으로 옮겨 시험한다. 학습한 시뮬레이터에서만 잘 걷는 정책을 걸러 내려는 것이다. 논문 (RSS 2026) 은 이 점수가 실물 로봇 결과와 잘 맞는다고 주장한다.

**시험장은 지형 7개다.** 평지 · 물결 (wave) · 경사 오르기 (slope_fd) · 경사 내리기 (slope_bd) · 계단 오르기 (stairs_fd) · 계단 내리기 (stairs_bd) · 장애물 (obstacle). 평지를 빼고 각각 1~10 단계 난이도가 있다. 지형 파일 머리 주석에서 읽은 값:

| 지형 | 1 단계 | 5 단계 | 10 단계 |
|---|---|---|---|
| 계단 한 칸 높이 | 8 cm | 18 cm | 23 cm |
| 경사 각도 | 8.4° | 18.5° | 29.7° |
| 물결 진폭 | 2 cm | 10 cm | 20 cm |
| 장애물 높이 | 7.3 cm | 16.5 cm | 28 cm |

**바닥 미끄러움을 9가지로 바꾼다.** 마찰 계수 0.2, 0.3, ... 1.0. 0.2 는 얼음에 가깝다. 지형 7 × 마찰 9 = **63 칸** 을 하나씩 시험한다. 몸무게 추가 (base mass) 는 이 표준 시험에서 0 kg 하나만 쓴다 (서버 기본 인자).

**일부러 방해도 넣는다.** 명령이 모터에 닿는 시점을 매번 0~18 ms 무작위로 늦추고, 센서 값에 잡음을 더한다 (각속도 ±0.8 rad/s · 관절 각 ±0.01 rad · 관절 속도 ±3.0 rad/s, 균등 분포). 우리 학습 설정의 잡음은 각속도 ±0.2 · 관절 각 ±0.03 · 관절 속도 ±2.0 이다 (E1 `params/env.yaml`). 둘 다 스케일 곱하기 전의 원래 값에 더한다 (RoboGauge `base_pipeline.add_noise` · Isaac Lab `observation_manager.py` 400행 코드 확인).

**한 칸마다 시험이 두 번 있다.**

- **시험 1. 몇 단계까지 건너가나 (Level).** 로봇을 지형 앞에 세우고 목표 지점까지 걸어가라고 한다. 시드 5개로 5번 돌려 4번 (80 %) 이상 도착하면 그 단계는 통과다. 1~10 을 이진 탐색해서 통과하는 가장 높은 단계 L* 를 찾는다. 1 단계도 못 넘으면 L* = 0 이고 그 칸은 0점이다.
- **시험 2. L* 단계에서 얼마나 잘 걷나.** 앞·뒤·옆·회전을 한 방향씩 최대 속도로 5초 명령하고 2초 멈추게 한다. 그다음 대각선 명령을 바꿔 가며 준다. 시드 3개. 0.1초마다 아래 8가지를 0~1 로 잰다. 1 이 좋다.

| 지표 | 무엇을 보나 | 묶음 |
|---|---|---|
| lin_vel_err | 시킨 직선 속도를 얼마나 따라가나 | Tracking |
| ang_vel_err | 시킨 회전 속도를 얼마나 따라가나 | Tracking |
| dof_limits | 관절이 한계 근처까지 꺾이나 | Safety |
| dof_power | 모터 전력을 얼마나 쓰나 (과열 위험) | Safety |
| orientation_stability | 몸이 옆으로 기우나 (roll) | Quality |
| torque_smoothness | 모터 힘이 덜컥거리나 | Quality |
| zmp_margin | 무게 중심이 발 사이에 잘 있나 | Quality |
| friction_margin | 발이 미끄러지기 직전까지 가나 | Quality |

**점수는 이렇게 모은다.**

1. 순간 품질 Q: 8 지표의 가중 기하평균 (속도 추종 둘은 가중 2, 나머지 1). 기하평균이라 하나라도 0 에 가까우면 전체가 낮아진다.
2. 쉬운 구간 빼기: 시험 목표 (최대 속도 · 대각선) 하나 안의 0.1초 값들을 줄 세워 **나쁜 쪽 절반의 평균** (mean@50) 을 쓴다. 가만히 서 있는 구간으로 점수를 버는 것을 막는다.
3. 지형 점수 S = 0.09 × (L* - 1) + 0.19 × Q. 10 단계를 Q = 1 로 통과하면 1.0 이다. 한 단계가 0.09 점이라 **점수의 대부분은 몇 단계까지 가느냐** 에서 나온다. 평지는 S = Q.
4. 마찰 9칸 평균 (L* = 0 칸은 0) → 지형 7개 평균 = **Score**.
5. Tracking · Safety · Quality 는 위 8 지표를 묶음별로 평균한 값이다 (mean@50, 지형 지표도 3번처럼 단계 가중된 값). 이 묶는 법은 논문에 식으로 없어서, 논문 Table XIII 의 지표값으로 Table IV 의 세 열을 다시 계산해 네 행 (Ours · CTS · HIM · DreamWaQ) 12칸이 모두 0.00005 이내 (반올림 차이) 로 맞는 것을 확인하고 썼다 (예: Ours Tracking (0.6908 + 0.6431) / 2 = 0.66695 → 표 0.6669).
6. Level 은 지형 6개 × 마찰 9칸 = 54칸의 L* 평균이다 (L* = 0 포함). **이 정의는 재구성** 이다. 저자 집계 코드를 찾지 못했다. 0.6984 정책에서 8.28 (README 8.30) 이 나와 맞는 쪽으로 보이지만 확정은 아니다.

## 2. 어떻게 돌렸나

| 항목 | 값 |
|---|---|
| RoboGauge | v1.1.9 · commit add2c7e · `C:/isaac/ext/RoboGauge` (임시 폴더에서 복사) |
| 환경 | conda `robogauge` (Python 3.11 새로 만듦) · mujoco 3.2.3 · torch 2.4.1+cpu · numpy 1.26.4 · dm-control 1.0.23 (pyproject runtime 그룹 그대로, torch 만 CPU 판) |
| 기기 | Windows 11 · Threadripper 7970X · GPU 사용 0 (CUDA_VISIBLE_DEVICES=-1, CPU 전용 torch) |
| 시험 명령 | 서버 `server.py` 의 기본 인자 그대로: `--stress-benchmark --stress-terrain-names flat wave slope_fd slope_bd stairs_fd stairs_bd obstacle --seeds 0 1 2 --search-seeds 0 1 2 3 4 --frictions 0.2 ... 1.0 --compress-logs --headless` |
| task | `go2_lab` (학습 runner `on_policy_runner_cts.py` 가 서버에 보내는 이름과 같다. Kp 25 · Kd 0.5 · 명령 스케일 1.0 · 각속도 0.25 · 관절 속도 0.05) |
| 관절 순서 | 학습 관측·행동 모두 다리별 묶음 (FL hip·thigh·calf, FR, RL, RR, `preserve_order: true`) = MuJoCo 순서. go2_lab 의 재배열 없음과 맞다 |
| 병렬 | 프로세스 8개, 한 번에 정책 하나 (lead 요청. 처음 28개로 시작한 1회는 74초에 중단하고 버렸다) |
| checkpoint 내보내기 | 저장소 자체 함수 `rsl_rl.utils.exporter_cts.export_cts_policy_as_jit` (학습 중 RoboGauge 제출과 같은 함수) 를 CPU 에서 호출. Isaac Sim 은 띄우지 않았다. 내보낸 JIT 와 eager 정책 (Isaac Lab 의 항목별 10프레임 이력 배치로 따로 조립) 을 15스텝 비교해 최대 오차 0.0 |

벽시계 (8 프로세스, 정책 하나당): 기준 0.6953 1406 s · 기준 0.6984 1355 s · E1 20000 1260 s · E2 20000 1367 s · E1 20499 1381 s · E2 20499 1552 s · E1 20000 재실행 1289 s. 영상 19편은 편당 9~26 s. RoboGauge README 는 64 프로세스 · AMD EPYC 7763 에서 63칸 2분 46초라고 적는다.

## 3. 기지 답 확인 (먼저 했다)

| 정책 | 기대값 (출처) | 이번 실측 | 차이 |
|---|---|---|---|
| go2_moe_cts_symmetry v5.1 52k | Score 0.6953 (폴더 이름) | **0.6954** | +0.0001 |
| go2_moe_cts 176k (`deploy/pre_train/go2/go2_moe_cts_176k_0.6984.pt`) | Score 0.6984 (파일 이름 · README 표) | **0.6970** | -0.0014 |
| 같은 176k | Tracking 0.7055 · Safety 0.8159 · Quality 0.7693 · Level 8.30 (README 표) | 0.7039 · 0.8146 · 0.7680 · 8.28 | -0.0016 · -0.0013 · -0.0013 · -0.02 |

- 0.6984 쪽 차이 0.0014 의 원인은 **미확인** 이다. 후보: 저자는 Linux, 이쪽은 Windows (부동소수 차이가 넘어짐 여부를 바꿀 수 있다) · 저자 평가 때 RoboGauge 판 (v1.1.7 이후로 보이나 미확인) · README 값은 학습 중 여러 checkpoint 가운데 최고값이라는 점.
- Level 8.28 은 54칸 합 447, README 8.30 은 448 에 해당한다 (448/54 = 8.296). 한 칸에서 한 단계 차이다.

## 4. 점수표

| 정책 | 학습 iteration | Score | Tracking | Safety | Quality | Level |
|---|---|---|---|---|---|---|
| 기준 symmetry v5.1 | 52k (이름) | 0.6954 | 0.7030 | 0.8193 | 0.7741 | 8.33 |
| 기준 176k (README 최고) | 176k (이름) | 0.6970 | 0.7039 | 0.8146 | 0.7680 | 8.28 |
| E1 (시드 42) model_20000 | 20000 | 0.5258 | 0.5329 | 0.6722 | 0.6272 | 6.52 |
| E1 (시드 42) model_20499 | 20499 | 0.5867 | 0.5966 | 0.7151 | 0.6676 | 7.00 |
| E2 (시드 43) model_20000 | 20000 | 0.5400 | 0.5423 | 0.6865 | 0.6404 | 6.67 |
| E2 (시드 43) model_20499 | 20499 | **0.6141** | 0.6189 | 0.7356 | 0.6921 | 7.28 |

참고로 논문 Table IV (go2_rl_gym 쪽 모델, 학습 프레임워크가 다르다): MoE-CTS 0.6713 · CTS 0.5786 · HIM 0.5379 · DreamWaQ 0.5054. 같은 RoboGauge 틀의 숫자지만 학습 시뮬레이터 · 학습량 · checkpoint 고르는 법이 달라 **서열 비교로 쓰면 안 된다.**

README 그림 `resources/results/robogauge_compare.png` 의 robotlab 곡선에서 20k 부근 값은 그림이라 읽어 내지 않았다 (**미확인**).

## 5. 지형별 점수와 단계

**지형 점수** (마찰 9칸 평균, mean@50):

| 정책 | flat | wave | slope_fd | slope_bd | stairs_fd | stairs_bd | obstacle |
|---|---|---|---|---|---|---|---|
| 기준 symmetry v5.1 | 0.6561 | 0.6542 | 0.5567 | 0.6189 | 0.7855 | 0.7591 | 0.8368 |
| 기준 176k | 0.6697 | 0.6466 | 0.5530 | 0.6034 | 0.7862 | 0.7982 | 0.8217 |
| E1 20000 | 0.4985 | 0.4411 | 0.3870 | 0.5045 | 0.5973 | 0.5140 | 0.7385 |
| E1 20499 | 0.6426 | 0.5800 | 0.4943 | 0.5132 | 0.6841 | 0.5631 | 0.6298 |
| E2 20000 | 0.4968 | 0.5352 | 0.4285 | 0.4730 | 0.6406 | 0.5179 | 0.6877 |
| E2 20499 | 0.6510 | 0.5732 | 0.4778 | 0.5422 | 0.7088 | 0.6142 | 0.7310 |

**평균 통과 단계 L*** (마찰 9칸 평균):

| 정책 | wave | slope_fd | slope_bd | stairs_fd | stairs_bd | obstacle |
|---|---|---|---|---|---|---|
| 기준 symmetry v5.1 | 7.67 | 6.56 | 7.22 | 9.56 | 9.00 | 10.00 |
| 기준 176k | 7.56 | 6.44 | 7.00 | 9.44 | 9.44 | 9.78 |
| E1 20000 | 5.33 | 4.78 | 6.11 | 7.44 | 6.44 | 9.00 |
| E1 20499 | 6.89 | 5.89 | 6.11 | 8.44 | 7.00 | 7.67 |
| E2 20000 | 6.44 | 5.22 | 5.67 | 7.89 | 6.44 | 8.33 |
| E2 20499 | 6.78 | 5.67 | 6.33 | 8.67 | 7.44 | 8.78 |

**마찰별 L*** (마찰 0.2 → 1.0 순서, 원출력 키 `<지형>_<단계>_baseMass0_friction<f>` 에서 읽음):

| 정책 | wave | slope_fd | slope_bd | stairs_fd | stairs_bd | obstacle |
|---|---|---|---|---|---|---|
| 기준 symmetry v5.1 | 4 5 6 7 8 9 10 10 10 | 0 2 4 6 8 9 10 10 10 | 1 3 5 7 9 10 10 10 10 | 6 10 10 10 10 10 10 10 10 | 3 8 10 10 10 10 10 10 10 | 10 ×9 |
| 기준 176k | 4 5 6 7 7 9 10 10 10 | 0 2 4 6 7 9 10 10 10 | 0 2 5 7 9 10 10 10 10 | 5 10 10 10 10 10 10 10 10 | 5 10 10 10 10 10 10 10 10 | 8 10 10 10 10 10 10 10 10 |
| E1 20000 | 2 3 4 5 6 6 7 7 8 | 0 1 3 4 5 6 7 8 9 | 0 2 4 5 7 8 9 10 10 | 3 7 7 8 9 9 8 9 7 | 2 3 8 7 7 7 8 7 9 | 7 8 9 10 10 9 10 9 9 |
| E1 20499 | 4 4 6 6 7 8 8 9 10 | 0 2 3 5 6 8 9 10 10 | 0 2 3 5 7 8 10 10 10 | 2 7 8 10 10 10 9 10 10 | 2 6 8 7 9 7 8 8 8 | 6 7 8 8 8 8 8 8 8 |
| E2 20000 | 2 4 5 6 7 8 8 9 9 | 0 1 3 4 6 7 8 9 9 | 0 1 3 5 6 8 9 9 10 | 1 8 8 9 9 10 9 10 7 | 2 4 6 8 8 7 8 7 8 | 6 9 9 9 9 10 8 8 7 |
| E2 20499 | 3 4 5 6 7 8 9 9 10 | 0 1 3 5 6 7 9 10 10 | 0 2 4 5 7 9 10 10 10 | 3 7 9 10 10 10 10 9 10 | 3 7 8 8 8 9 8 8 8 | 8 9 10 10 9 9 9 8 7 |

**8 지표** (mean@50, 단계 가중 포함):

| 정책 | lin_vel | ang_vel | dof_limits | dof_power | orientation | torque_smooth | zmp | friction |
|---|---|---|---|---|---|---|---|---|
| 기준 symmetry v5.1 | 0.7429 | 0.6632 | 0.8463 | 0.7922 | 0.8360 | 0.7850 | 0.8097 | 0.6656 |
| 기준 176k | 0.7398 | 0.6680 | 0.8414 | 0.7878 | 0.8339 | 0.7785 | 0.7997 | 0.6599 |
| E1 20000 | 0.5682 | 0.4976 | 0.7016 | 0.6428 | 0.6819 | 0.6410 | 0.6626 | 0.5233 |
| E1 20499 | 0.6400 | 0.5532 | 0.7446 | 0.6857 | 0.7309 | 0.6784 | 0.7003 | 0.5610 |
| E2 20000 | 0.5789 | 0.5057 | 0.7121 | 0.6608 | 0.6971 | 0.6521 | 0.6788 | 0.5337 |
| E2 20499 | 0.6563 | 0.5814 | 0.7638 | 0.7074 | 0.7589 | 0.7006 | 0.7260 | 0.5830 |

표에서 읽히는 것 (잰 범위 안에서만):

- 마찰 0.2 의 경사 오르기는 여섯 정책 모두 L* = 0 이다. 경사 내리기 0.2 도 symmetry v5.1 (1) 을 빼고 0 이다. 이 칸은 모두에게 같은 감점이다.
- 기준 정책은 마찰이 커질수록 L* 가 오르거나 유지된다. E1·E2 는 계단·장애물에서 마찰 1.0 의 L* 가 중간 마찰보다 낮은 칸이 있다 (예: E2 20499 장애물 0.4~0.5 에서 10, 1.0 에서 7). 원인은 **미확인**.
- 20000 → 20499 에서 지형 점수가 내려간 칸은 E1 장애물 하나다 (0.7385 → 0.6298, 평균 L* 9.00 → 7.67). E2 장애물은 올랐다 (0.6877 → 0.7310). 두 시드의 방향이 갈려 판단을 보류한다.
- E2 가 E1 보다 두 checkpoint 모두 높다. 시드가 둘뿐이라 시드 차이인지 다른 이유인지 가를 수 없다.

## 6. 영상

`_eval/out/robogauge/videos/` 에 mp4 19편 (1280×720 · 30 fps). 화면 크기만 바꿨다 (`RG_RENDER_W/H`, 물리·점수와 무관). 모두 마찰 0.6 · 시드 0 의 단일 실행이다. 평지는 최대 속도 명령 시험, 나머지는 시험 1 (목표 지점 걷기) 그 자체다. 단계는 기준 정책 symmetry v5.1 의 마찰 0.6 L* 를 두 정책에 똑같이 주고, E1 은 자기 L* 단계도 따로 찍었다. 성공 여부는 각 실행의 `results.yaml` `target_pos_velocity.success` 에서 읽었다.

| 지형 | 단계 | 기준 symmetry v5.1 | E1 model_20000 |
|---|---|---|---|
| flat (최대 속도 명령) | - | 1395 프레임 | 1385 프레임 |
| wave | 8 | 도착 | 못 감 |
| wave | 6 (E1 L*) | | 도착 |
| slope_fd | 8 | 도착 | 못 감 |
| slope_fd | 5 (E1 L*) | | 도착 |
| slope_bd | 9 | 도착 | 못 감 |
| slope_bd | 7 (E1 L*) | | 도착 |
| stairs_fd | 10 | 도착 | 못 감 (174 프레임에서 끝남) |
| stairs_fd | 9 (E1 L*) | | 도착 |
| stairs_bd | 10 | 도착 | 못 감 |
| stairs_bd | 7 (E1 L*) | | 도착 |
| obstacle | 10 | 도착 | 도착 |

시드 0 한 번의 결과다. 시험 1 판정은 시드 5개 중 4개라서 영상 한 편이 통과·실패를 정하지 않는다. 다만 단계 영상 17편 모두 스트레스 결과의 마찰 0.6 L* 와 어긋나지 않는다 (L* 이하에서 도착, L* 보다 높은 단계에서 못 감).

**전 프레임 검사** (`_eval/robogauge/video_audit_full.py`, 기존 `video_frame_audit.py` 의 판정을 화면 전체 영역으로 바꾼 것): 19편 11,333 프레임 전부 디코드 (ffprobe 프레임 수와 일치), 검은 프레임 (평균 밝기 < 20) 0 · 단색 프레임 (밝기 표준편차 < 6) 0. 파랑 우세 판정은 MuJoCo 바닥·하늘이 원래 파랗기 때문에 평지 영상에서 전 프레임이 걸리므로 결함 판정에서 뺐다. 검사기 자체는 검은 프레임 2장을 넣은 시험 영상에서 2장을 잡고 깨끗한 영상에서 0 을 내는 것을 먼저 확인했다. 결과 `_eval/out/robogauge/videos_audit.json`. 각 영상 60 % 지점 프레임을 모은 그림 `_eval/out/robogauge/frames_check/contact_mid60.png` 를 눈으로 보았다.

렌더링은 OpenGL (glfw) 이 GPU 1 에서 했다 (nvidia-smi 프로세스 목록에서 robogauge python 이 GPU 1 의 C+G 로만 보이고 GPU 0 메모리는 13954 MiB 그대로). 렌더 중 GPU 1 사용량 9804 / 16303 MiB (여유 6499 MiB).

## 7. 논문·README 설정과 다른 점

| 항목 | 저자 | 이번 | 영향 |
|---|---|---|---|
| OS·CPU | AMD EPYC 7763 (RoboGauge README) · OS 는 Linux 로 보임 (CMD.md 경로 `/home/...`, 미확인) | Windows 11 · Threadripper 7970X | 0.6984 에서 -0.0014. 원인 미확인 |
| torch | 2.4.1+cu124 (pyproject) | 2.4.1+cpu | 정책은 둘 다 device cpu 로 돈다 (go2_config). 영향 없을 것으로 봄 · 미시험 |
| 병렬 수 | 63~64 | 8 | 칸마다 시드가 고정이라 결과는 같아야 하나 **미시험** |
| 결과 파일 인코딩 | UTF-8 (Linux 기본) | cp949 (Windows 기본, RoboGauge 가 인코딩 없이 씀) | 점수 무관. 집계 스크립트가 cp949 로 읽음 |
| 비교 대상 | 논문 Table IV 는 go2_rl_gym (IsaacGym) 모델 | 우리는 Isaac Lab (robotlab) 모델 | README robotlab 행과 비교해야 한다 |
| 학습량 | 52k · 176k iteration | 20000 · 20499 | 같은 시점 비교가 아니다 |
| symmetry | v5.1 은 symmetry 학습 (이름) | E1·E2 `symmetry_cfg: null` | 다름 |
| checkpoint 고르기 | 0.6984 는 학습 중 최고값 | 고정 checkpoint 4개 | 저자 값에 선택 효과가 들어 있다 |
| 명령 범위 | 시험은 ±1.0 m/s (지형 회전 ±1.5, 평지 ±2.0 rad/s) | model_20000 은 ±0.5 m/s · 회전 ±1.0 으로 학습 (로그 `Command range updated at iter 20000`) | model_20000 은 학습 범위 밖 명령으로 시험된다 |
| 단계 탐색 시드 | 논문 IV-C 는 시드 5개 · 80 %, 부록 A-C 는 "세 시드" 로 서로 다르게 적혀 있다 | 코드 (v1.1.9) 대로 탐색 시드 5개 · 80 % | 코드를 따랐다 |

## 8. 미확인 · 한계

- **Level 열의 정의** (54칸 평균, L* = 0 포함) 는 재구성이다. README 와 한 칸 차이로 맞았다는 것까지만 확인했다.
- **같은 기기 재실행 재현성은 확인했다.** E1 model_20000 을 같은 명령으로 한 번 더 돌린 결과 (`e1_model_20000_rerun`, 1289 s) 가 Score · 8 지표 · 지형 점수 · 54칸 L* 모두 첫 실행과 같았다. 시드가 고정이라 같은 기기에서는 같은 답이 나온다는 뜻이다. 거꾸로 말하면 이 재실행은 **시드를 바꿨을 때의 퍼짐을 재지 않는다.**
- 병렬 수 8 이 64 와 같은 결과를 내는지 미시험.
- 시드 2개 (E1·E2) 로는 시드 간 퍼짐을 잴 수 없다. checkpoint 사이 흔들림 (README 곡선의 들쭉날쭉) 도 이번에 재지 않았다. 따라서 0.01~0.03 수준의 차이는 의미를 두지 않는다.
- 20000 → 20499 상승을 명령 범위 확대 탓으로 보는 것은 추정이다. 같은 기간의 다른 변화 (학습 진행 자체) 를 배제하지 않았다.
- 기준 정책 두 개의 학습 설정이 commit 28b4516 기본값과 같은지는 확인하지 않았다 (symmetry v5.1 은 다른 설정임이 이름으로만 보인다).
- 영상은 시드 0 한 번씩이다.

## 9. 다시 돌리는 법

```bash
# 1) 내보내기 (GPU 숨김, isaac311-moects 는 읽기만)
CUDA_VISIBLE_DEVICES=-1 C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe \
  C:/isaac/ext/go2_rl_robotlab/_eval/robogauge/export_jit.py <logs/.../model_N.pt> <out.pt>
# 2) 스트레스 시험 (서버 기본 인자 · go2_lab · 8 프로세스)
bash C:/isaac/ext/go2_rl_robotlab/_eval/robogauge/run_stress.sh <label> <jit.pt> 8
# 3) 표 만들기
C:/Users/AI-WS01/anaconda3/envs/robogauge/python.exe C:/isaac/ext/go2_rl_robotlab/_eval/robogauge/summarize.py
# 4) 영상 한 편 / 전 프레임 검사
bash C:/isaac/ext/go2_rl_robotlab/_eval/robogauge/run_video.sh <label> <jit.pt> <terrain> <level|-> 0.6 0
C:/Users/AI-WS01/anaconda3/envs/robogauge/python.exe C:/isaac/ext/go2_rl_robotlab/_eval/robogauge/video_audit_full.py <dir> <out.json>
```

## 10. 파일

| 무엇 | 경로 |
|---|---|
| 스크립트 | `C:/isaac/ext/go2_rl_robotlab/_eval/robogauge/` (export_jit.py · rg_run.py · run_stress.sh · run_queue.sh · summarize.py · run_video.sh · run_video_queue.sh · video_audit_full.py) |
| 내보낸 JIT 4개 | `C:/isaac/ext/go2_rl_robotlab/_eval/out/robogauge/jit/` |
| 스트레스 원출력 | `C:/isaac/ext/go2_rl_robotlab/_eval/out/robogauge/stress/go2_lab_stress_<label>/<시각>_run/stress_benchmark_results.yaml` (하위 로그는 subtasks.tar.xz) |
| 콘솔 로그 · 벽시계 | `.../stress/<label>.console.log` · `.../stress/walltimes.csv` |
| 집계 | `C:/isaac/ext/go2_rl_robotlab/_eval/out/robogauge/summary.json` |
| 영상 · 실행 결과 | `C:/isaac/ext/go2_rl_robotlab/_eval/out/robogauge/videos/*.mp4` · `*.results.yaml` · `*.log` |
| 프레임 검사 | `.../videos_audit.json` · `.../frames_check/contact_mid60.png` · 검사기 자가 시험 `.../audit_selftest/` |
| 버린 실행 (28 프로세스, 74초 중단) | `.../aborted_28proc/` |
| 논문 HTML 사본 | `.../paper_dl/paper.html` |
