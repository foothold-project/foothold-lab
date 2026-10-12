> 분류: A/정책학습 · 평가
> 작성: 오흥재 (lead 세션 하위 작업 · Claude 실행) · 2026-10-11
> 근거: `inbox/jay/20261008-546-design/DESIGN-astra-rl-topdown.md` 3절 공통 평가 계약 Q · 4절 E0·E1 · 코드 `go2_rl_robotlab` 28b4516d · 체크포인트 SHA-256 (1절) · 원자료 `C:/isaac/ext/go2_rl_robotlab/_eval/out/`
> 요지: E1 배포 student 는 평지에서 Q 기본 명령 cell 을 정지 하나 빼고 모두 넘는다. 가장 약한 능력은 험지 위 정지이고, 명령 확대 500 iter 뒤(20499)에는 정지 · 계단 위 후진·횡이동 · obstacles 이동이 유의하게 나빠졌다 (좋아진 cell 은 500 확대에서 2 개뿐). 정지 통과율은 관측 noise 에 크게 좌우된다 (학습과 같은 noise 를 켜면 평지 97 → 15 %. 몸은 멈춰 있고 순간 yaw rate 가 문턱을 넘음). 0.1 m/s 명령에는 대부분 서 있는데 Q 의 MAE 문턱은 이것을 통과로 센다. Q3 corridor 는 명령을 그대로 주면 평지에서도 heading drift 로 대부분 실패한다
> 상태: 1차 선별(cell 당 100 episodes) 끝 · 임계값 부근 cell 500 확대 {{EXPAND_STATE}} · export · 실기 · 발 착지 계측은 미측정

# Q-E1 · E1 배포 student 기본 명령 평가 (model_20000 · model_20499)

## 0. 한눈에

| 물음 | 20000 (명령 상한 0.5) | 20499 (상한 1.0 뒤 500 iter) | 상태 |
|---|---|---|---|
| 평지 기본 명령 (Q1, 정지 제외 10 cell) | 10 cell 모두 통과 | 10 cell 모두 통과 | 확인됨 |
| 평지 정지 (Q2) | 97 % 통과 (500 확대 96.2 %) | 87 % 미달 (500 확대 89.2 % 미달 · 짝 차 p 1.6e-5) | 확인됨 |
| 험지 7종 정지 (tile 중앙 출발 · 경사·계단 띠 출발) | 14 cell 중 2 통과 | 14 cell 중 1 통과 (100 episodes 에서는 2. obstacles 중앙이 500 확대에서 83.0 % 로 미달) · 띠 출발에서 6 cell 유의하게 하락 | 확인됨 (500 확대 반영) |
| 계단 위 후진·횡이동 | 모두 통과 | stairs_up 후진 67 % · 오른쪽 79 % · stairs_down 후진 84 % 미달 | 확인됨 |
| 0.1 m/s 저속 | Q1 은 100 % 통과로 셈. 실제로 움직인 episode 38 % (평지) | 12 % (평지) | 확인됨. Q 문턱의 맹점 |
| 4 m gate · corridor 0.30 m (Q3) | 평지 0.3 m/s 13 % | 13 % | 확인됨. 주원인은 heading drift (heading hold 변형에서 평지 0.3 m/s 13 → 54 %) |
| 관측 noise 를 켠 정지 (학습 조건) | 평지 15 % · stairs_up 8 % | 평지 6 % · stairs_up 6 % | 확인됨. 몸은 멈춰 있음 (5 s 이동 중앙값 3 cm). 순간 yaw rate 가 표본의 약 10 % 에서 0.10 rad/s 초과 |
| 낙상 | 주 실행 · 띠 출발 · heading hold 34,400 episodes 중 41 건 (두 체크포인트 합) | | 확인됨 |

20000 은 「명령 확대 직전」이라고 불렀지만 정확히는 확대가 시작된 iteration 20000 의 rollout 으로 PPO 갱신을 한 번 거친 판이다(`on_policy_runner_cts.py:110`~157: rollout · update · 저장 순서, 학습 로그 839958 행 `Command range updated at iter 20000` 가 iteration 20000 블록 앞에 찍힘). 그 rollout 에서 새 범위로 다시 뽑힌 env 의 비율은 미확인이다.

학습 로그 숫자(lead 요약)를 `train.log` 에서 다시 읽어 맞는 것을 확인했다. 19999: teacher 57.97 · student 56.34 · noise std 0.28 · 지형 레벨 5.67 · illegal_contact 2.4 % · max_command_x 0.5. 20499: 43.33 · 37.51 · 0.40 · 5.98 · 8.0 % · 1.0. 평가는 `act_inference`(평균 행동)라 학습 탐색 noise std 는 행동에 직접 들어가지 않는다.

## 1. 무엇을 어떻게 쟀나

**대상.** 코드 `C:/isaac/ext/go2_rl_robotlab` HEAD 28b4516d22617b11aeaf8ead63cc00b0c0bcd1bd. `git status` 는 추적 파일 변경 없음(추적 밖 `_eval/` · `_smoke/` 만). env `isaac311-moects` (isaacsim 5.1.0.0 · isaaclab 0.54.2 · isaaclab_rl 0.4.7 · rsl-rl-lib 3.3.0 · robot_lab 2.3.0 · torch 2.7.0+cu128, robot_lab 과 rsl_rl 은 이 저장소의 editable 설치).

| 체크포인트 | SHA-256 |
|---|---|
| `logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192/model_20000.pt` | `c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8` |
| `.../model_20499.pt` | `7e52a5026086660308fbc270f30ebf983064b1cb8695aca73652136ebf02f904` |

**정책 경로는 배포 student 하나다. 확인됨 (코드와 실행 둘 다).**

- 코드: `scripts/rsl_rl/play.py:202`~208 과 같은 경로로 `OnPolicyRunnerCTS(...).load()` 뒤 `get_inference_policy()` 를 쓴다. 이것은 `ActorCriticMoECTS.act_inference` 를 돌려주고(`on_policy_runner_cts.py:281`~285), `act_inference` 는 `obs['single_obs']` 와 `obs_groups['policy']` 만 읽어 `student_moe_encoder` 와 `actor` 를 지난다(`actor_critic_moe_cts.py:225`~234). `teacher_encoder` 와 `critic` 그룹(정답 height scan 포함)은 이 함수에 없다.
- 실행: 실제 `obs_groups` 는 `{"policy": ["policy"], "critic": ["critic"]}`, 관측 shape 은 policy 450 · single_obs 45 · critic 275 (그중 height scan 187). 첫 관측에서 `critic` 전체를 크기 10 의 난수로 바꿔도 행동 변화 최대값 **0.0** (모든 실행). 양성 대조로 policy history 에 0.1 noise 를 넣으면 행동이 {{PERT_POL}}, single_obs 에 넣으면 {{PERT_SGL}} 바뀐다 (실행별 최대값의 범위). 모듈을 손으로 이어 계산한 student 경로와 `act_inference` 의 차이 0.0.
- 학습 설정 대조: 평가 스크립트가 만든 기본 `Go2EnvCfg` 를 E1 실행의 `params/env.yaml` 과 비교했다. observations · actions · decimation · sim · events · terminations 차이 0 건, scene/robot 은 prim_path 문자열 표기 1 건뿐이다. 행동 관절 순서는 FL·FR·RL·RR × hip·thigh·calf 로 학습 설정과 같다.

**장치. 확인됨.** 모든 실행은 `CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES` · headless. 프로세스 안에서 env device · sim device · runner device · policy parameter device 가 모두 `cuda:0` 이고, torch `cuda:0` 의 UUID 는 `315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f` = `nvidia-smi` 의 GPU 1 이다. Kit 의 렌더 장치 표에서도 Active 는 UUID 315d098f 하나다 (실행 로그 {{N_LOGS}} 개 모두). **env 와 policy 는 같은 물리 GPU 1 에 있다.** GPU 0 사용량은 모든 실행 동안 14,611 MiB 로 변하지 않았다(E2 학습). GPU 1 의 9/29 렌더 프로세스(pid 25916)는 건드리지 않았다. 평가 프로세스 하나가 GPU 1 에 더한 양은 {{MEM_ADD}} (`nvidia-smi` 전체 사용량의 실행 전 대비 최대 증가로 잰 값). GPU 1 여유는 늘 {{MEM_FREE}} 이상이었다.

**cell (명령).** 모두 정지 상태에서 출발하고 한 episode 에 명령 하나다. body frame 기준.

| cell | 명령 vx, vy, wz | 길이 | 출처 |
|---|---|---|---|
| stand | 0, 0, 0 | 10 s | lead 가 정한 임시값 |
| stop03 | 0.3, 0, 0 을 5 s 뒤 0 을 5 s | 10 s | Q 2행 |
| fwd01 · fwd02 | 0.1 · 0.2, 0, 0 | 20 s | lead 가 정한 임시값 (저속) |
| fwd03 | 0.3, 0, 0 | 20 s | Q 1행 (명령값) · 길이는 임시값 |
| fwd05 | 0.5, 0, 0 | 20 s | lead 가 정한 임시값 (일반 전진 = 20k 전 학습 상한) |
| back03 · left03 · right03 | -0.3, 0, 0 · 0, ±0.3, 0 | 20 s | Q 1행 · 길이는 임시값 |
| yawL05 · yawR05 | 0, 0, ±0.5 | 20 s | Q 1행 · 길이는 임시값 |

**지형.** 학습 지형 `mdp/terrains.py` 의 비중이 0 이 아닌 8 종을 원래 이름 그대로 쓴다: flat · wave · slope_up · slope_down · rough_slope · stairs_up · stairs_down · obstacles. 한 실행 안에서 지형 한 종이 한 열(column)이고 10 행이 모두 **난이도 0.5 고정** (lead 가 정한 임시값. 학습 끝 평균 지형 레벨 5.67 에 가까운 중간값). 이 난이도에서 계단 단차 0.154 m, 경사 0.334 (약 18.5도), 장애물 높이 0.163 m, wave 진폭 0.19 m (설정식으로 계산한 값). gap · stepping_stones 는 학습 비중 0 이라 넣지 않았다. 지형 생성 시드 1000, 실제 USD 충돌 메시의 SHA-256 을 실행마다 기록했고 두 체크포인트 실행 사이에 모든 지형에서 같다.

**출발.** episode i 는 행 i mod 8 의 tile 중앙에서 xy ±0.5 m (시드로 동결), z +0~0.2 m (학습과 같음), 관절 기본 자세, 속도 0 으로 시작한다. 이동 명령은 명령 방향이 world +x 를 향하도록 처음 yaw 를 정해서, 20 s 동안 같은 지형 열 안에서만 움직인다. 피라미드형 지형(slope · stairs · obstacles · rough_slope)은 중앙에 3 m 평평한 platform 이 있어서, 중앙 출발이면 stand · yaw 는 사실상 평지 시험이고 stop03 도 platform 끝 근처에서 멈춘다. 그래서 **제자리 cell 을 경사·계단 띠 위에서 다시 쟀다** (stand · yaw 는 +2.5 m, stop03 은 +1.75 m 에서 출발. lead 가 정한 임시값). 띠 출발은 ray scanner 로 발 밑 최고 지면을 읽어 높이를 맞췄고, 모든 로봇이 그 지면에서 0.40~0.60 m 위에서 시작함을 확인했다.

**표본과 짝.** cell 당 100 episodes. Q 는 「evaluation seed 1000~1099 로 짝지어」라고 적었지만, 병렬 시뮬에서는 episode 마다 시드를 줄 수 없어 **전역 시드 1000 한 번 + env 100 개**로 대신했다 (Q 와 다른 구현). 두 체크포인트 실행은 같은 시드 · 같은 배치를 써서 초기 root 자세 · 관절각 · 몸 질량(DR) · 관절 강성(DR) 의 SHA-256 이 모든 지형에서 같다. 즉 episode i 끼리 짝이 맞는다. 학습 DR(질량 · COM · 마찰 · 게인 · 모터 영점 · 모터 지연)은 그대로 두고 시드로 동결했다.

**지표와 판정 (Q 그대로).**
- Q1: 이동 구간 첫 1 s 제외, body frame vx · vy MAE 각 ≤ 0.15 m/s, wz MAE ≤ 0.20 rad/s, 그 창 안에서 낙상 없음. 명령하지 않은 축도 0 을 목표로 잰다. cell 판정은 생존 ≥ 95 % 이고 episode 통과 ≥ 90 %.
- Q2: 명령 0 이 된 뒤 평면 속도 < 0.05 m/s 와 |yaw rate| < 0.10 rad/s 가 **1 s 내내** 유지되는 창의 시작이 1 s 안이고, 그 시점까지 이동 거리 ≤ 0.20 m, 10 s 동안 낙상 없음. 창은 끝까지 온전해야 한다 (끝자락의 짧은 창은 정지로 세지 않음). 여기에 「전진 5 s 구간이 Q1 을 넘었을 것」을 lead 가 정한 임시 조건으로 더했다 (0 행동이 「이미 멈춰 있음」으로 통과하는 것을 막으려고. 2절).
- Q3: 출발점에서 명령 방향 4 m gate 도달, 경로 corridor 최대 이탈 ≤ 0.30 m, 20 s 낙상 없음, Q1 통과. gate 판정 창은 출발부터 gate 통과까지 (임시값).
- 낙상: base 접촉 1 N 초과(학습 종료 조건), 몸 기울기 60도 초과 0.2 s 지속, base 가 발 밑 지면 아래. 가장 이른 것을 쓴다.
- 이동 보조 판정 (Q 아님 · lead 가 정한 임시값): 추종 창 안에서 명령 방향 body 속도 평균 ≥ 명령의 50 % (yaw 는 heading 변화 ≥ 명령의 50 %). 2절에서 0 행동이 0.1 m/s cell 의 Q1 을 통과해서 더했다.
- 통계: 비율은 Wilson 95 % 구간, 두 체크포인트 짝 차는 Newcombe 방식 10 구간과 정확한 McNemar p.

**학습 때와 다르게 둔 것 (모두 meta.json 에 기록).** 관측 noise 끔 (policy · single_obs 둘 다. lead 가 정한 임시값. 10절에서 noise 를 켠 결과와 대조) · push 끔 (play.py 와 같음) · 관절 초기 자세 scale 0.5~1.5 대신 1.0 · 초기 속도 0 · yaw 는 cell 별 고정 · curriculum 전부 끔 · episode 길이 25 s → 30 s (20 s cell 안에서 time_out 이 나지 않게). 명령 생성기는 `Go2RLGymCommand._resample` 를 평가 스크립트 안에서 고정 명령으로 바꿔 끼웠다 (저장소 파일은 그대로).

## 2. 측정기 시험 (답을 아는 입력)

| 시험 | 기대 | 결과 |
|---|---|---|
| 합성 궤적 51 건 (`test_q_metrics.py`): 완전 추종 · 0.2 오프셋 · 첫 1 s 제외 · 후진·횡 좌표 · corridor · yaw 감김 · 기울기 0.18 s 대 0.20 s · 지수 감쇠 정지 시각과 거리 해석해 · 끝자락 짧은 창 · Wilson 95/100 = 0.8883~0.9785 · McNemar · Newcombe 구간의 모의 포함률 | 정해진 값 | 51 건 모두 통과. Newcombe 포함률 0.93~0.975 안 |
| 위 시험이 틀린 코드를 잡는가: 사본에 결함 5 가지(첫 1 s 제외 끔 · 기울기 지속 0.18 s · 정지에서 yaw 조건 뺌 · 정지의 이동 조건 뺌 · 경로 좌표를 명령 방향 대신 몸 방향) | 각각 실패해야 함 | 5 가지 모두 실패로 잡힘 |
| 정책 대신 0 행동 (평지 · stairs_up · cell 당 10) | 움직이지 않음. 이동 cell 의 MAE = 명령 크기 | 22 cell 모두 생존. MAE vx 0.1 · 0.2 · 0.3 · 0.5, vy 0.3, wz 0.50 으로 명령 크기와 같음. 이동 cell 은 Q1 실패. **단 fwd01 은 Q1 통과** (MAE 0.10 ≤ 0.15). 그래서 이동 보조 판정을 더했고 0 행동은 이것을 0 % 통과 |
| 명령 전달: 관측의 명령 칸(single_obs 6:9 와 history 최신 칸 87:90) 대 평가가 넣은 명령 | 0 | 모든 실행 모든 step 최대 차 0.0 |
| 유한값 | 비유한 행동·관측 0 | 모든 실행 0 |
| 결정성: 같은 시드로 같은 실행 두 번 (20000 평지) | 같아야 함 | 궤적 · 종료 · cells.json 비트 단위로 같음. 평가 스크립트를 고친 뒤에도 같은 비교를 다시 해 같음 |
| 기울기 규칙이 잡은 평지 낙상 1 건 (20499 · fwd02) | 진짜 넘어짐인가 | 13.0 s 부터 기울기 82도까지 오르고 base 높이 0.16 m 까지 내려갔다가 일어남. base 접촉 1 N 은 넘지 않아 학습 종료 조건으로는 안 잡히는 실제 넘어짐 |
| 띠 출발 높이 | 지면에 박히지 않음 | 발 밑 최고 지면 위 0.40~0.60 m (기본 0.4 + z 0~0.2) |

## 3. 결과 · 평지

{{T1}}

`*` 는 cell 판정 미달. 평지에서 두 체크포인트 모두 stop03 을 뺀 Q1 cell 을 전부 넘는다. stop03 은 20000 97 % 에서 20499 87 % 로 떨어져 미달이 됐고, 짝 차 +0.10 [+0.02, +0.18] · p 0.021 이다. 새 표본 500 episodes 에서도 96.2 % 대 89.2 % 로 같은 결과다 (표 8). 실패는 모두 「멈추는 데 1 s 넘게 걸림」 또는 「창 안에 못 멈춤」이다 (표 4). **fwd01 은 Q1 이 100 % 통과로 세지만 이동 보조는 38 % / 12 %** 다. 0.1 m/s 명령에 두 정책 모두 대부분 서 있거나 조금만 움직이고, 20499 는 더 그렇다 (추종 창의 「정지 상태」 비율 0.50 / 0.85). cell 별 MAE 평균은 모두 0.11 이하라 Q 문턱 0.15 · 0.20 에서 멀다. 이 문턱은 0.3 m/s 명령에서 절반 속도도 통과시키므로, 통과율만으로 추종 품질을 말하지 않는다.

회전에서 방향 비대칭이 뒤집힌다. 20000 은 오른쪽 회전이 느리고 (MAE wz 0.064 왼쪽 · 0.087 오른쪽), 20499 는 왼쪽이 느리다 (0.103 · 0.063). 원인은 미확인이다.

## 4. 결과 · 험지 7종 (tile 중앙 출발)

{{T2}}

20000 의 미달은 8 cell 이다: 정지 5 (wave · rough_slope · stairs_up · stairs_down · obstacles) 와 obstacles 의 전진 0.3 · 왼쪽 · 오른쪽. 20499 는 12 cell 이다: 정지 5 (wave · slope_up · rough_slope · stairs_up · stairs_down), 계단 위 후진 2 (stairs_up 67 % · stairs_down 84 %), stairs_up 오른쪽 (79 %), obstacles 의 전진 0.3 · 후진 · 왼쪽 · 오른쪽. obstacles 정지는 20499 가 100 episodes 에서 92 % 로 통과했지만 500 확대에서는 83.0 % 로 미달이다 (9절). 생존은 모든 cell 에서 97 % 이상이다. 계단 위 실패는 넘어짐이 아니라 추종 실패다: stairs_up back03 20499 의 MAE vx 0.141 (20000 0.074), 이동 보조 평균 0.54. 피라미드 지형의 stand · yaw 는 중앙 platform 위라 평지와 거의 같은 값이 나온다 (그래서 6절에서 띠 위에서 다시 쟀다).

## 5. 두 체크포인트 차이

{{T3}}

100 episodes 선별 단계에서 McNemar p < 0.05 인 cell 은 위가 전부다. **모두 20499 가 나쁜 방향이고, 이 단계에서 20499 가 유의하게 좋은 cell 은 없다.** 500 확대(표 8)에서는 나쁜 방향 13 cell, 좋은 방향 2 cell (stairs_up 중앙 left03 · stairs_down 띠 yawR05) 이다. 검정은 cell 마다 따로 했고 다중 비교 보정은 하지 않았다. 선별 단계 검정이 116 개라 차이가 전혀 없어도 p < 0.05 가 6 개쯤 나올 수 있다. 그래서 개별 p 보다 한쪽으로 몰린 방향(선별 12 대 0)과 p 가 아주 작은 cell (1e-4 이하 6 개, 그중 1e-5 이하 5 개)을 근거로 본다. 같은 지형·같은 초기 상태라 차이는 정책에서 온다 (확인됨: 결정성 시험과 짝 hash). 단 이것은 훈련 시드 하나(42)의 두 시점 비교다. E2(시드 43)에서 같은 방향인지는 미확인이다.

## 6. 정지와 제자리 동작

{{T4}}

정지 실패의 거의 전부가 「1 s 넘게 걸림」 또는 「창 안에 못 멈춤」이다. **정지 거리는 주된 문제가 아니다.** 중앙값은 2~10 cm 이고, 1 s 안에 멈춘 episode 가운데 거리 0.20 m 를 넘은 것은 정지 episode 3,000 건 중 4 건이다. 거리 0.20 m 를 넘은 110 건은 거의 모두 늦게 멈추거나 못 멈춘 episode 라, 그 거리는 멈춘 시점 또는 끝까지 움직인 양이다. 즉 몸은 거의 그 자리에 서지만 평면 속도 0.05 m/s 또는 yaw rate 0.10 rad/s 아래로 1 s 를 버티지 못한다 (발을 계속 디디는 것으로 추정. 발 접촉은 재지 않았다). 띠 위에서 20499 가 크게 나빠진다: stairs_up 61 → 19 %, rough_slope 80 → 48 %, slope_down 82 → 51 %.

{{T5}}

경사·계단 띠 위에서 stand 는 모두 통과하고 회전도 대부분 통과한다. 100 episodes 에서 미달은 20000 stairs_down 의 오른쪽 회전 88 % 하나였는데, 500 확대(9절)에서는 그 cell 이 91.2 % 로 통과했고 대신 20499 obstacles 왼쪽 회전이 86.4 % 로 미달이다. 띠 위 회전의 MAE wz 는 평지보다 크다 (stairs 에서 0.09~0.15). obstacles 띠 출발에서 20499 yawL05 1 건이 0.90 s 에 base 접촉으로 넘어졌는데, 출발 1 s 안이라 출발 위치(상자 모서리)의 영향일 수 있다 (추정).

## 7. 4 m gate · corridor (Q3) 와 heading drift

{{T6}}

명령을 Q 대로 그대로 주면 평지에서도 Q3 통과가 8~32 % 다. 원인은 heading drift 다: 평지 직진 cell 에서 19 s 동안 처음 방향에서 평균 0.6~0.9 rad 돌아가고, 부호는 episode 마다 다르다 (`out/Q-E1-diag.json` heading). 몸 기준 속도는 잘 따라가도 (Q1 통과) world 경로가 휜다. **Q1 이 허용하는 wz MAE 0.20 rad/s 는 Q3 의 0.30 m corridor 와 open-loop 속도 명령에서는 함께 지킬 수 없다** (확인됨: 이 구현과 이 시험에서). 대조로 lead 가 정한 임시 변형 「heading hold」(wz 명령 = 0.5 × 처음 방향과의 차, ±0.5 rad/s 로 자름. Isaac Lab 기본 heading 이득과 같은 값)를 돌렸다. Q 가 아니다. 평지 gate 도달은 오른쪽 횡이동(84 / 78)을 빼고 95 % 이상이 되고, corridor 통과는 34~56 % 로 오른다. 남은 이탈은 몸 기준 횡속도 오차가 쌓인 것으로 추정한다 (heading hold 는 횡 위치를 고치지 않음). 험지에서 heading hold 를 해도 20499 의 후진·오른쪽 gate 도달이 20000 보다 낮다 (472 대 642, 516 대 642 / 700). Q3 를 판정에 쓰려면 경로 추종(상위 계층)을 두고 잴지, open-loop 명령 그대로 잴지 Q 쪽에서 정해야 한다.

## 8. 낙상

{{T7}}

주 실행 · 띠 출발 · heading hold 실행 34,400 episodes 중 41 건이고 절반(21 건)은 기울기 규칙으로만 잡혔다 (500 확대와 noise 실행은 표 8 · 9 에 따로). 학습 종료 조건(base 접촉 1 N)만으로 낙상을 세면 이만큼 빠진다. 지지면 아래 추락은 0 건이다 (구멍 지형이 없어 예상대로). obstacles 가 가장 많다.

## 9. 임계값 부근 500 episodes 확대

{{EXPAND_TEXT}}

{{T8}}

## 10. 관측 noise 민감도

{{NOISE_TEXT}}

{{T9}}

## 11. 해석

**확인됨.**
- 배포 student 경로는 teacher 입력을 쓰지 않는다 (코드와 실행 시험).
- E1 student 는 평지와 경사에서 Q1 기본 명령을 넘고, 험지 7종에서도 생존 97 % 이상이다.
- 가장 약한 능력은 험지 위 정지다. 실패 형태는 「거리」가 아니라 「1 s 정지 유지」다.
- 정지 판정은 관측 noise 에 크게 좌우된다. 학습과 같은 noise 를 켜면 몸은 그대로 멈춰 있는데 순간 yaw rate 가 문턱을 넘어 평지 정지 통과가 97 → 15 % (20000) 로 떨어진다. 표 4 의 정지 통과율은 noise 를 끈 낙관적 조건의 값이다. Q2 를 순간값으로 둘지 짧은 평균으로 둘지는 Q 쪽 결정이다 (이번에는 원문대로 순간값).
- 명령 확대 뒤 500 iter (20499) 는 선별 단계에서 유의하게 나빠진 cell 이 {{N_WORSE}} 개, 좋아진 cell 이 0 개다. 500 확대에서는 나빠진 cell 13 개, 좋아진 cell 2 개다. 나빠진 곳은 정지 · 계단 위 후진·횡이동 · obstacles 위 이동과 회전이다. 학습 로그의 student 보상 하락(56 → 37.5)과 같은 방향이지만 보상 숫자가 이 cell 들을 가리키지는 않는다.
- Q1 의 MAE 문턱은 0.1 m/s 에서 「서 있음」을 통과로 센다. 이동 보조 판정으로 보면 0.1 m/s 에 실제로 움직인 episode 는 지형별로 20000 29~42 %, 20499 8~24 % 다.

**추정.**
- 20499 의 하락은 명령 상한이 0.5 → 1.0 으로 바뀐 뒤 아직 적응 중인 과도기일 수 있다 (학습 로그: noise std 0.28 → 0.40, illegal_contact 2.4 → 8.0 %). 더 학습하면 회복하는지는 미확인.
- 0.1 m/s 에서 서 있는 것은 학습 명령이 작은 전진 명령을 드물게 만들기 때문일 수 있다. 기본 경로(`commands.py:141`~165, `dynamic_resample_commands=True`)는 vx · vy 각각에 하한 `vel_low_bound` = 남은 거리 / 남은 시간을 두는데, episode 시작에서 그 값은 (0.625 × 8 m) / 25.02 s ≈ 0.20 m/s 다. 0.2 m/s 아래 명령은 거리가 쌓여 하한이 줄어든 뒤에만 나온다. 또 `limit_vel` 은 vx · vy 를 상한 양 끝에만 둔다(:367). 코드에서 계산한 값이고 실제 학습 명령 분포는 재지 않았다.
- 정지 실패는 제자리 디딤이 계속되는 것으로 보인다. 발 접촉을 재지 않아 미확인.

**미확인.** 훈련 시드 변동 (E2 대기) · 다른 지형 난이도 · export 정책과의 일치 · 실기와 sim2sim · 발 착지 질.

## 12. 못 잰 것

- **export (JIT · ONNX) 정책.** native student 만 쟀다. E0 의 export 일치 시험(1e-5)은 이번 범위 밖.
- **Q 4행 (발 놓기 · touchdown · 위험 착지).** 착지 계측기가 없다. gap · rails · stepping stones 는 학습 비중 0 이라 넣지 않았다.
- **Q 5행 (새 능력의 손실).** 비교할 새 능력 실험이 아직 없다. 이번 표가 그 기준선이다.
- **지형 난이도.** 0.5 하나. 학습 끝 레벨 5.67 근처지만 다른 난이도는 미확인.
- **시드.** 평가 시드 1000 하나(검증용 성격). holdout 시드 · 메시는 따로 두지 않았다. 훈련 시드는 42 하나.
- **episode 별 시드 1000~1099.** 전역 시드 + env 100 개로 대신했다 (1절).
- **Q3 의 상위 경로 추종.** heading hold 변형은 Q 가 아니고 횡 위치 보정도 없다.
- **관측 noise 를 켠 조건.** 평지와 stairs_up 만 (10절). 실기 IMU · 관절 센서 noise 와 같은지는 미확인.
- **실제 학습 명령 분포 · 정지 실패 중 발 디딤.** 재지 않았다.

## 13. 파일과 재현

평가 코드는 `C:/isaac/ext/go2_rl_robotlab/_eval/` 에 있고 저장소 원본은 고치지 않았다.

| 파일 | 내용 |
|---|---|
| `q_eval.py` | Isaac 실행 (cell · 지형 배치 · 명령 고정 · 출발 · heading hold 변형 · 사전 점검 · 궤적 저장) |
| `q_eval_batch1.py` · `q_eval_batch2.py` | 주 실행 · 띠 출발 실행 때 쓴 판 (지금 판은 옵션만 더함. 같은 결과를 다시 낸 것 2절) |
| `q_metrics.py` · `test_q_metrics.py` | Q 지표 함수와 답을 아는 시험 51 건 |
| `q_post.py` | traj.npz → episodes.csv · cells.json (시뮬 없이 다시 계산 가능) |
| `q_table.py` · `q_diag.py` · `q_pairs.py` · `q_expand_plan.py` · `q_md.py` · `q_doc.py` | 비교 CSV · 진단 · 짝 검사 · 확대 선정 · 표 생성 · 이 문서 조립 (`Q-E1.src.md` + `Q-E1.fill.json` + `out/Q-E1-tables.md` → `Q-E1.md`) |
| `run_batch.sh` · `run_offplat.sh` · `run_hh.sh` · `run_expand.sh` · `run_noise.sh` | 실행 묶음 (머리에 실행 전 선언) |
| `out/<tag>/` | 실행마다 `meta.json` (설정 · 장치 · hash · 점검) · `traj.npz` (궤적) · `episodes.csv` (episode 별 지표) · `cells.json` (cell 요약) |
| `out/Q-E1-cells.csv` · `out/Q-E1-pooled.csv` · `out/Q-E1-diag.json` · `out/Q-E1-pairing.json` · `out/Q-E1-pairs.json` · `out/expand_plan.json` | 두 체크포인트를 한 행에 둔 비교 (주 실행) · 험지 합계 · 진단 · 주 실행 짝 검사 · 모든 실행 쌍의 짝 검사 (26 쌍 모두 초기 상태 · DR · 메시 · 설정 같음) · 확대 선정 |
| `out/Q-E1-tables.md` | 이 문서의 표 원본 |

재현: `run_batch.sh` 를 다시 돌리면 같은 시드라 같은 궤적이 나온다 (2절 결정성). 지표만 바꿀 때는 `python q_post.py out/<tag>` 로 궤적에서 다시 계산한다.
