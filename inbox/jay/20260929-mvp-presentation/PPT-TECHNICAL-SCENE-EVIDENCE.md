# Go2 기술 소개 연속 장면의 실제 근거

> 분류: 리서치
> 작성: 오흥재 · 2026-10-02 00:55
> 근거: v2g2 학습 저장 설정·체크포인트 직접 열람 · Isaac Lab/RSL-RL 로컬 코드 · 평가 시계열 · 사용자 장비 확인 기록
> 요지: 같은 Go2에서 관측 235개, 별도 Actor/Critic, 관절 목표 12개, 병렬 학습으로 이어지는 화면의 정확한 데이터와 경로.
> 상태: 확인 범위 명시 · 새 렌더 없음
> 판: v1.0

이슈: [#490](https://github.com/foothold-project/foothold-lab/issues/490). 요청받은 이 파일만 작성했다. 시뮬레이션이나 학습은 실행하지 않았다.

## 1. 이번에 직접 확인한 정책과 설정

현재 발표의 v2는 `v2g2-feetair01`, 학습 시드 42, iter3000이다. 아래 경로를 기준으로 한다.

- 학습 폴더 `C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/`
- `params/env.yaml`: 이 문서에서 `env.yaml`이라고 쓸 때 위 폴더의 파일이다.
- `params/agent.yaml`: 이 문서에서 `agent.yaml`이라고 쓸 때 위 폴더의 파일이다.
- `model_3000.pt`: 위 폴더의 체크포인트를 Isaac용 Python으로 CPU에 읽어 가중치 크기를 확인했다. 새 추론이나 실제 뉴런 활성값 추출은 하지 않았다.

## 2. 화면에서 로봇 주위로 모을 입력 235개

`확인됨`: `env.yaml:539`의 관측 그룹은 `policy` 하나이며 `concatenate_terms: true`이다. 다음 순서로 연결된다. 인덱스는 0부터 시작하는 반열림 구간이다.

| 화면 그룹 | 실제 입력 | 차원·구간 | 직접 근거 |
|---|---|---|---|
| 몸의 움직임 | 몸체 좌표계 선속도 | 3 · [0,3) | env.yaml:546 · Isaac Lab observations.py:54,58 |
| 몸의 움직임 | 몸체 좌표계 각속도 | 3 · [3,6) | env.yaml:559 · observations.py:64,68 |
| 몸의 기울기 | 몸체 좌표계로 투영한 중력 벡터 | 3 · [6,9) | env.yaml:572 · observations.py:74,78 |
| 수행할 명령 | base_velocity 명령 | 3 · [9,12) | env.yaml:585,588 |
| 관절 상태 | 기준 자세 대비 관절 위치 | 12 · [12,24) | env.yaml:595 · observations.py:212,219 |
| 관절 상태 | 기준 속도 대비 관절 속도 | 12 · [24,36) | env.yaml:608 · observations.py:257,264 |
| 직전 행동 | action manager가 보관한 직전 raw action | 12 · [36,48) | env.yaml:621 · observations.py:657,664 |
| 주변 지면 | 높이 스캔 | 187 · [48,235) | env.yaml:630 · 체크포인트 actor 첫 층 235 |

로컬 함수 원문: `C:/isaac/IsaacLab/source/isaaclab/isaaclab/envs/mdp/observations.py`.

화면에는 `몸 상태·명령·이전 행동 48 + 지면 높이 187 = 235`를 쓴다. 48개 전부를 고유수용감각이라고 부르지 않는다. 투영 중력은 roll/pitch/yaw 세 각도의 나열이 아니다. 선속도도 IMU 한 센서가 직접 측정해 현재 정책으로 들어오는 것처럼 그리지 않는다. 현 설정은 시뮬레이터의 로봇 상태를 읽는다.

`확인됨`: 관측 시간 이력 적층은 없고 각 항 `history_length: 0`이다. 이전 행동 12개가 포함되는 것과 관측 이력 네트워크가 있는 것은 다르다. 발 접촉력·원본 RGB·Depth·LiDAR 점군은 이 235개에 직접 들어가지 않는다. 접촉력은 보상 및 평가 기록에서 쓰일 수 있으나 그것을 Actor 입력으로 연결하면 틀린다.

## 3. height scan 화면의 실제 기하와 하드웨어와의 구분

`확인됨`: `env.yaml:354`부터 실제 센서 설정은 다음과 같다.

| 설정 | 값 | 화면에 반영할 내용 |
|---|---|---|
| 센서 종류 | RayCaster | 시뮬레이터의 지형 mesh에 대한 광선 검사 |
| 기준 prim | `/World/envs/env_.*/Robot/base` | 로봇 몸체를 중심으로 이동 |
| 갱신 주기 | 0.02초 | 50Hz 표본 |
| 검사 mesh | `/World/ground` | 물리 지형 표면으로 광선 연결 |
| 방향 정렬 | `ray_alignment: yaw` | 몸체의 yaw를 따라 회전하는 지면 격자 |
| 격자 범위 | x 1.6m × y 1.0m | 몸체 중심 x ±0.8m, y ±0.5m |
| 간격 | 0.1m | 17 × 11 = 187점 |
| 광선 방향 | (0,0,-1) | 아래를 향하는 병렬 광선 |
| 원점 offset | (0,0,20)m | 지면 hit를 얻기 위한 가상 광선 시작점. 실제 장착 센서 높이가 아님 |
| 광선 배열 | `ordering: xy` | grid_pattern의 순서를 보존할 때 사용 |

격자 생성 코드: `C:/isaac/IsaacLab/source/isaaclab/isaaclab/sensors/ray_caster/patterns/patterns.py:45`와 `:46`의 양끝 포함 arange, `:47` meshgrid, `:57` 하향 광선.

높이 관측은 `sim/policy/gap_observations.py:28`의 `sensor.data.pos_w[:,2] - ray_hit_z - offset`이다. `:29`에서 유한값을 확인하고 `:32`에서 미검출을 `miss_value`로 치환한다. 저장 설정은 offset 0.5, miss_value +1(`env.yaml:656`), clip [-1,+1](`:664`), 학습 잡음 U(-0.1,+0.1)(`:659`)이다.

연출: 로봇 발 주변을 포함한 직사각 격자가 지형 높낮이에 맞춰 꺾이는 모습이 적절하다. 머리에서 먼 전방으로만 부채꼴 점군을 쏘는 LiDAR 장면은 현재 정책의 이 센서 구성과 다르다. 영화 속 콘셉트 HUD와 연구 구조 설명을 혼동하지 않는다.

바로 사용 가능한 실제 배경 설명 그림: `docs/assets/visual/v2-height-scan.png`(파일 존재 확인). 추가 도식은 `docs/assets/visual/eval-v2-scan-grid.svg`, `eval-v2-scan-meaning.svg`. 이 그림은 실시간 187채널 로그가 아니다. 이번 조사에서 187채널 높이와 전체 관측을 프레임마다 저장한 시계열은 확인하지 못했다. 실제 수치가 반응하는 연출이라면 새 계측이 필요하며, 기존 93열 데이터에 높이 배열이 있다고 가정하면 안 된다.

## 4. Actor와 Critic은 같은 입력을 받는 별도 네트워크

`확인됨`: `agent.yaml:25` Actor, `:29` Critic hidden dims는 각각 [512,256,128], `:33` 활성화는 ELU이다. `:23`과 `:24`의 관측 정규화는 모두 false다.

직접 연 체크포인트의 weight shape:

| 층 | Actor | Critic |
|---|---|---|
| 0 | (512,235) | (512,235) |
| 2 | (256,512) | (256,512) |
| 4 | (128,256) | (128,256) |
| 6 | (12,128) | (1,128) |

공유하는 것은 입력 그룹이다. 가중치를 공유하는 한 신경망이라고 표현하지 않는다. `env.yaml`에는 별도 critic 관측 그룹이 없고 `agent.yaml:6`은 `obs_groups: {}`이다. RSL-RL은 기본 policy 그룹을 찾고 critic 그룹이 없으면 policy 그룹을 복사해 쓴다.

- `C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/rsl_rl/runners/on_policy_runner.py:42`, `:45`: critic 기본 그룹 해석 호출.
- 같은 패키지 `utils/utils.py:244`, `:279`, `:290`: policy fallback 및 critic에 policy 그룹 복사.
- 같은 패키지 `modules/actor_critic.py:44`, `:48`, `:58`, `:69`: 두 입력 크기 산출, Actor 별도 생성, Critic 출력 1.
- 같은 패키지 `runners/on_policy_runner.py:328`, `:332`: 실행 정책은 `act_inference` 반환.

화면 동선: 235 입력에서 위쪽 Actor와 아래쪽 Critic으로 분기한다. Actor의 12개 행동이 로봇으로 돌아가고, Critic의 값 1개는 PPO 학습 경로로 간다. Critic을 Actor 뒤에 직렬로 붙이거나 Critic에서 관절 제어선을 내보내지 않는다. 추론 장면에서는 Critic을 흐리게 두거나 학습 모드 클릭에서만 켠다. 점들이 층을 지나는 애니메이션은 정보 흐름 도식이며 실제 활성값으로 표시하지 않는다.

## 5. 12개 출력에서 관절 제어로

`확인됨`: `env.yaml:670`은 JointPositionAction, action scale 0.25(`:678`), use_default_offset true(`:681`)이다.

화면 식: `q_target = q_default + 0.25 × action`.

원문: `C:/isaac/IsaacLab/source/isaaclab/isaaclab/envs/mdp/actions/joint_actions.py:173`은 raw action에 scale과 offset 적용, `:195`는 기준 관절 위치를 offset으로 사용, `:199`는 위치 목표 전달이다. 정책이 12개 토크를 직접 내는 그림은 틀린다.

Actuator는 DCMotor(`env.yaml:168`), stiffness 25.0, damping 0.5(`:177`), effort limit 23.5, velocity limit 30.0(`:173`)이다. PD 계산과 토크 제한은 `C:/isaac/IsaacLab/source/isaaclab/isaaclab/actuators/actuator_pd.py:190`~`:195`에 있다. 시뮬레이션 제어 설정이며 제품 하드웨어 토크 제원으로 제시하지 않는다.

기준 자세(`env.yaml:154`): 좌 hip +0.1, 우 hip -0.1, 앞 thigh 0.8, 뒤 thigh 1.0, calf -1.5rad. 명령 벡터의 순서를 맞출 때 실제 관절 순서는 `FL_hip, FR_hip, RL_hip, RR_hip, FL_thigh, FR_thigh, RL_thigh, RR_thigh, FL_calf, FR_calf, RL_calf, RR_calf`이다. 다리마다 세 출력으로 묶어 보여줘도 실제 배열이 다리별 연속 세 개라고 구현하면 안 된다. 근거: 아래 평가 manifest `:18` 이후 joint_names, parquet 메타데이터.

오독 방지: `sim/eval/eval_generalization.py:154`의 `joint_pos_scale=0.05`는 action scale이 아니다. 도움말은 초기 관절 위치 흔들기 비율이며 `:301`에서 reset position_range=(0.95,1.05)에 사용한다. 두 값을 혼동하지 않는다.

## 6. 기존 영상과 실제 데이터가 동기화되는 자료

### 한 Go2의 명령·관절 반응

- 정지 원본 영상: `sim/eval/results/20260929-axis2-fall/v2/stop/v2_stop.mp4`.
- 정확히 대응하는 데이터: `sim/eval/results/20260929-axis2-fall/v2/stop/timeseries/ep0009.parquet`.
- 설정·평가 근거: `sim/eval/results/20260929-axis2-fall/v2/probe_manifest.json:18`(관절 순서), `:33` 이후(시계열 규격).
- 이미 HUD를 얹은 영상: `sim/eval/results/20260929-axis2-hud/axis2-stop-v2.mp4`, 웹 사본 `docs/assets/video/v2/axis2-stop-v2.mp4`.
- 동일 구조의 hold와 turn: 위 stop 폴더를 hold/turn으로 바꾸고 영상명도 `v2_hold.mp4`/`v2_turn.mp4`, 대응 데이터는 각 폴더의 `timeseries/ep0009.parquet`.
- 기존 제작 연결 근거 `_out/loop/axis2_hud.py:35`~`:39`: 영상 env 8이므로 ep0009, `:62`~`:68` 경로와 번호, `:83` 기존 parquet를 변조 없이 HUD trace로 연결.

`확인됨`: ep0009를 직접 열었을 때 env_id=8, dt_s=0.02, 500행, 93열이다. 화면에서 실제로 쓸 수 있는 열은 `t_s`, `frame`, `cmd_vx_mps`, `cmd_vy_mps`, `cmd_wz_rps`, `vx_mps`, `vy_mps`, `pitch_deg`, `roll_deg`, `yaw_deg`, `joint_pos_<관절명>`, `joint_vel_<관절명>`, `joint_target_<관절명>`, `joint_torque_<관절명>`, `foot_contact_<발>_n` 등이다. foot_contact는 평가 표시용으로 쓸 수 있지만 위 235 Actor 입력에는 없다.

실제 표본 t=4.0초(frame200): 전진 명령 0.0, 실제 vx 1.0131402m/s, FL hip 실제각 -0.4157831rad, 목표각 -0.3261245rad. 명령을 멈춰도 곧바로 속도가 0이 되지 않는 장면을 이 표본으로 설명할 수 있다. t=0의 joint_target은 0으로 기록되어 있으므로 영상 전체 초기 버퍼 값을 정상 정책 출력이라고 해석하지 않는다.

이 데이터에는 187개 높이 값·235개 전체 관측·12개 raw action·뉴런 활성값이 없다. 관절 위치/속도와 목표는 실측 애니메이션으로, 네트워크 내부와 높이 격자는 구조 도식으로 구분한다. 전체 관측 벡터를 정확히 복원했다는 주장은 불가하다.

### 한 로봇에서 병렬 환경으로 뒤로 빠지는 장면

- 사용 중인 가독성 좋은 영상: `sim/eval/results/20260929-train-army-ramp/train-army.mp4`.
- 웹 사본: `docs/assets/video/v2/train-army.mp4`, 포스터 `docs/assets/video/v2/posters/train-army.jpg`.
- 실제 4096마리 렌더 후보(파일 존재): `sim/eval/results/20260929-train-army-4096/slow-0/flat_army_A_4096_topdown.mp4`, `slow-3000/flat_army_A_4096_topdown.mp4`.

`확인됨`: 실제 학습 설정 env.yaml:86,189는 4096환경이고 :200,201은 지형 격자 10×20이다. agent.yaml:3은 환경당 24스텝, 따라서 한 rollout의 표본 수는 4096×24=98,304이다. 이것은 초당 처리량이나 비용 절감 배수가 아니다.

기존 `train-army`는 600마리, 5×6 지형 칸에 약20마리씩 보여주는 학습 체크포인트 변화 렌더다. 학습 전체는 200칸, 약20마리/칸이다. 근거: `inbox/jay/20260929-mvp-submission/source/report-text.txt:2401`~`:2450`. 원래 4096마리를 30칸에 넣은 후보는 흰 덩이처럼 겹쳐 가독성이 낮아 보류된 기록이다. 화면에 `4,096 환경 학습 / 렌더는 600개 환경`을 구분하거나, 확대·축소 도식으로 '일부 환경을 확대해서 보았다'고 표현한다. train-army 화면의 모든 개체를 세면4096이라는 설명은 금지한다.

## 7. 실물 센서 표기의 확인 수준

근거 기록 `GO2-HARDWARE-REFERENCE.md:17`은 기본 LiDAR L2가 사용자 제공 이미지의 표기로 확인됐으며, 사용자가 실제 장비와 같은 이미지라고 답했다는 기록이다. **실물 개체 직접 검사 결과는 아니다.** 이번 조사에서는 원래 제품 이미지 원본을 다시 열어 L2 글자를 독립적으로 확인하지 않았다. 모델 세대 라벨이 필요하면 `사용자 제공 구성 기준`을 메모에 남기고 실물 검증으로 격상하지 않는다.

같은 문서 :18~:21에서 전면 카메라, 추가 Orin NX16GB, D435i, HESAI-360의 근거를 구분한다. HESAI-360의 제조사 세부 제품 식별자는 미확인이다. 보유와 현재 장착·연동 완료는 다르다.

실제 모듈 소개 영상 `inbox/jay/20260929-mvp-presentation/go2_module.mp4` 존재 확인. 기존 프레임 확인 기록은 `GO2-HARDWARE-REFERENCE.md:27`~`:36`: 0.5~1초 Orin,1.5~2초 D435i,약4초 HESAI-360. 이 시점은 기존 기록이며 이번에 전 프레임을 새 검사하지 않았다. 2.5~3초 MID-360은 선택 사양이며 팀 보유로 추가하면 안 된다.

실물 소개에서 시뮬레이션 소개로 전환하는 클릭 때 `지금부터 시뮬레이션 정책의 입력`이라는 전환을 둔다. 실제 LiDAR/Depth 카메라선이 그대로187격자로 들어가는 그림은 현재 연결이 입증되지 않았으므로 사용하지 않는다.

## 판 이력

| 판 | 날짜 | 변경 |
|---|---|---|
| v1.0 | 2026-10-02 | 저장 설정·체크포인트·로컬 코드·동기화 parquet 직접 대조, 장비 확인 범위와 렌더 환경 수 분리 |
