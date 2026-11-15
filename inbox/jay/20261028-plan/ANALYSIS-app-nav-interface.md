> 분류: B/항법 · 앱과 보행 정책 인터페이스 조사
> 작성: verifier · 2026-10-28
> 근거: foothold-app 고정 커밋 3개 · 민우 RunPod 저장 YAML/코드 · 설계 21/23/43/44/54 · CPU 계약 입력
> 요지: 모바일 MuJoCo 번들·서버 Gazebo·민우 Isaac/Nav2는 서로 다른 경로다. 공통 속도 계약은 가능하나 START/AME-2 파일 교체만으로 붙지 않는다.
> 상태: 조사 완료 · 실행·통합 승인 아님 · 정책 원 가중치와 실기 동작 미확인

# 카드 B · 앱·Nav2·보행층 연결 규격

핵심은 세 가지다. 모바일 MuJoCo는 평면 지형 관측을 넣는 고정 MLP 실행기다. 민우 Nav2는 MPPI 속도 출력 경로이며 우리 문서의 Nav2 경로→깃발 추종기와 다르다. Nav2 전체 경로→HiPAN 근거리→START라는 이번 의뢰 방향도 기존 문서의 HiPAN 우선/ Nav2 대체와 다르므로, 이미 통합됐다고 설명하면 안 된다.

## 1. 읽은 판과 근거 자리

| 자료 | 고정 기준 | 범위와 한계 |
|---|---|---|
| foothold-app main | `6f16be74b2373f4ff0897f9c4b44255ea7354fa1` | 앱·서버·agent. MuJoCo 모바일 경로는 이 판에 없음 |
| foothold-app dev | `cf6445ac34b048966748bf52a5ad56ce7c0cf18c` | 이번 MuJoCo·Three.js 항목의 직접 대상. 이하 `APP/`는 이 판 |
| server 작업 브랜치 | `feature/server-sim-gl` @ `2178418ddf93d734f32c1aaf974ab7bb6c309508` | simmgr 외부 runtime 호출 경로 확인. 배포 완료와 동일시하지 않음 |
| 설계 | lead_tmp-20261023 @ `9e650a28702e4dd11833a8a5c7f47020556bf03c` | `inbox/jay/20261019-design/`의 원문. 현재 의뢰와 다른 내용도 보존 |
| START 코드 | impl-integ @ `496e0cfed7fffe704b91c22f52f89572a5bab20e` | `foothold_s2/models/` 및 `deploy/` 읽기 |
| 민우 최신 저장 설정 | `s3://rzklpc35sl/leeminwoo/ros2_ws/src/go2_tutorial/` | nav2_params.yaml 수정 시각 2026-10-13, 설치본 같은 경로의 config와 내용 일치. 원격 실행 중 파라미터 dump는 아님 |
| 민우 교재 | `s3://rzklpc35sl/leeminwoo/go2-slam-nav2/` | ch08 설정, ch10 어댑터. 교재 기본값과 최근 실행 override를 구별 |

읽기 사본·CPU 증거: `C:/mai/wt/foothold-lab/verifier-27c-window/_out/app_nav_1028/`. `app/`, `app_dev/`, `app_feature/`, `nav/`에 출처별로 보존했다. 키·토큰·.env 내용은 출력하지 않았다. `hashes.json`은 내려받은 파일의 SHA256 목록이다. 이번 산출만 요청된 lead worktree에 새로 썼고 기존 변경에는 손대지 않았다.

앱 고정 원문 링크: [dev sim.js](https://github.com/foothold-project/foothold-app/blob/cf6445ac34b048966748bf52a5ad56ce7c0cf18c/mobile/sim/sim.js), [dev main.js](https://github.com/foothold-project/foothold-app/blob/cf6445ac34b048966748bf52a5ad56ce7c0cf18c/mobile/sim/main.js), [dev 모바일 설명](https://github.com/foothold-project/foothold-app/blob/cf6445ac34b048966748bf52a5ad56ce7c0cf18c/mobile/README.md).

## 2. 앱의 정책 실행 경로

### 모바일 로컬 MuJoCo 번들

`.pt` 직접 로더가 아니다. `APP/mobile/sim/main.js:80`이 `policy_v2.f32`를 fetch하고, `:89`에서 MuJoCo 실행기에 넣는다. `APP/mobile/README.md:49`는 이 가중치·WASM·Three·Go2 메시를 커밋하지 않고 외부 `FH_SIM_SRC`에서 빌드 시 복사한다고 명시한다. 원 `foothold-v2.pt`와 f32의 변환 오차·SHA 연결은 이번 저장소만으로 확인하지 못했다.

| 계약 | 현재 구현 값 | 근거 |
|---|---|---|
| 추론 | 235→512→256→128→12, hidden ELU, 마지막 선형. Float32 LE weight·bias 286604개 = 1146416 bytes | `mobile/sim/sim.js:17`~37. CPU 길이 재계산 및 마지막 bias만 넣은 네트워크 출력 확인 |
| 관측 순서, 0 기반 | 0:3 몸 선속도, 3:6 몸 각속도, 6:9 projected gravity, 9:12 명령 vx/vy/wz, 12:24 q−default, 24:36 dq, 36:48 이전 action, 48:235 height 187 | `sim.js:64`, `:77`~99 |
| 관측 scale | 위 값을 직접 넣음. 별도 관측 정규화 wrapper 없음 | `sim.js:96`~100 |
| **지형 관측** | 187칸 모두 `clip(base 높이−floorZ−0.5, −1,1)`. 실제 발앞 지형이나 라이다 높이 지도가 아님 | `sim.js:88`, `:99` |
| 행동 | Isaac 관절 순서 12개. `q_target = default + 0.25*a`; 이 함수에 action clip 없음 | `sim.js:101`~111 |
| 기본 자세 | hip [+.1,−.1,+.1,−.1], thigh [.8,.8,1,1], calf [−1.5]×4 rad | `sim.js:4`~10 |
| 관절 순서 | Isaac은 부위별 FL/FR/RL/RR, MuJoCo는 다리별 hip/thigh/calf. MuJoCo index→Isaac index는 [0,4,8,1,5,9,2,6,10,3,7,11] | `sim.js:5`, `:6`, `:54`~55. SDK 순서와는 별도 |
| 제어 | 물리 .005 s ×4 = 정책 .02 s(50 Hz), PD 25/.5, DCMotor effort23.5 N·m·velocity30 rad/s를 전 관절에 사용 | `sim.js:10`~11, `:41`~45, `:109`~112 |
| 물리 보정 | 기본 페이지 ISAAC_LIKE는 damping0·frictionloss0·footSpin false, armature .01·footFriction .8 | `sim.js:13`~15, `main.js:89`. 물리 엔진 동등성 증거는 아님 |
| 조이스틱 | 원형 입력 정규화 후 vx=−y, vy=−.5x, wz=−오른막대x. 각각 최대 ±1 m/s, ±.5 m/s, ±1 rad/s | `main.js:45`~65. 화면 좌측이 vy+·wz+ |
| 제한 | 학습 범위 밖을 색으로 알림. 그 이유로 명령을 자르지 않음 | `main.js:45`, `:289`, `:323` |
| STOP | 초기 잠금, STOP/창 비활성 등에서 명령0과 잠금, 다시 시작만 해제 | `main.js:21`~39. 명령0은 몸의 물리 정지를 보장하지 않음 |
| 주기 한계 | 화면 시간 누적에 맞춰 정책 step을 실행하되 프레임당 최대5회, 밀리면 누적시간 폐기 | `main.js:283`~295. 50Hz 시뮬 시간 계약이지 실시간 50Hz 보장 아님 |
| 정책 선택 | 단일 f32 경로와 고정 network shape. 지도/시나리오 선택은 있으나 이 경로에 START/AME-2 선택·교체 상태기계 없음 | `main.js:80`, `sim.js:17`; `scenario.js:4`~61 |

**CPU 확인:** `probe.mjs`에서 원본 모듈을 import하고 물리를 움직이지 않는 fake MuJoCo 객체를 넣었다. 알려진 선속도 [1,2,3], 각속도 [4,5,6], 명령 [−1,.5,1]이 예상 0:12 칸에 들어갔고 height187은 전부 약 −.1, physics 호출은 4번이었다. action별 다른 bias를 넣었을 때 재배열된 토크가 `25×.25×a`와 1e-6 이내로 맞았다. 원 가중치 성능, 실제 MuJoCo 보행, 브라우저 실행은 재측정하지 않았다.

### 서버 Gazebo 경로는 별개

`APP/apps/simmgr/native_entrypoint.py:54`~79는 검증된 외부 `sensor_isolation.py`와 `live_map.py`를 불러 실행한다. `launcher.py:341`은 phone에 정책 표시 이름/판을 전달하고 `:370`은 Nav2Unit을 붙인다. 이 서버가 모바일 WASM의 `sim.js`를 정책 실행기로 쓰는 것은 아니다.

`APP/apps/agent/foothold_agent/safety/core.py:61` 부근 quantize는 0, (.6,0,0), (.6,0,±.5)만 통과시킨다. 후진·횡이동·제자리 회전은 거부한다. CPU에서 입력 (−1,0,0), (0,1,0), (0,0,1)이 모두 0, (1,0,1)이 (.6,0,.5)인 것을 재확인했다. 따라서 **모바일 로컬은 뒤·옆을 내보내지만 서버 agent는 막는다.** 한 화면의 성공을 다른 경로의 계약 이행으로 볼 수 없다.

policy name/version은 `phone/hub.py:50`, `:350`에 표시 정보로 있다. 실행 가중치를 바꾸는 selector와 동일하지 않다. 외부 Gazebo 정책 런타임의 실제 관측·토크 설정은 제공된 앱 저장소만으로 확정할 수 없다.

## 3. START·AME-2를 붙일 때 맞출 것

| 항목 | START 경로 | AME-2 경로 | 현재 앱 대비 필요한 연결 |
|---|---|---|---|
| 관측·메모리 | 현재 actor96=o45+추정51. 지각에 hist10·depth2×60×60·GRU 상태, 지도32×16. `models/start_policy.py:1`, `start_perception.py:32`, `:272`, `:295` | 석헌 Go2 export의 실제 입력 계약 필요. 공개 로컬 ame2_minimal `ame2_env_cfg.py:242`~260은 상태·관절·이전 action 뒤 pose command/time을 쓰며 velocity3 직접 입력과 같다고 단정 못 함 | 235 MLP에 weight만 바꾸면 안 됨. 관측 assembler, 지각망/메모리 lifecycle, reset, normalization을 정책별로 명시 |
| 지도 | 실제 depth와 TR-Net 복원. 실기 PRED 경로이며 GT/추정 선택을 명시 | 고도 지도·학습된 attention 입력과 정규화가 export에 결속되어야 함 | 평면187 대입 제거가 선행. 표시용 라이다가 정책 입력으로 저절로 연결되지 않음 |
| 행동·모델 | 저장된 학습 cfg의 scale/default/limit/PD를 따라야 함 | Go2 이식 자산·관절수·순서·gains를 원본 G1과 분리해 확인 | 앱 상수0.25·23.5·30·25/.5를 모든 정책의 확정값으로 재사용하지 않음 |
| 실행물 | 현재 `deploy/export.py:1`은 S1-blind495 MLP exporter. START 전체 지각+actor export가 아님 | teacher/student·mapping 소비 방식·정책 hash를 지정해야 함 | 파일 확장자 .pt 하나로 호환 여부 판정 금지 |
| 상위 명령 | body vx/vy/wz를 수신하고 해당 정책·지형에서 허용된 범위만 사용 | 속도 계약을 지키는 adapter가 있으면 앱 공통 계약 사용 가능 | AME-2 원 정책이 pose/time 입력이면 변환기가 필요. `44 §5`의 “차이는 내부뿐”은 adapter 완성 조건하의 설계 주장 |
| 정지·전환 | 정책0 유지와 recurrent reset 시점, 재개 시 이전 입력 폐기 구분 | 같은 의미의 STOP·상태 응답 필요 | 이름 표시와 안전하게 정책 교체하는 기능을 구별. SDK SportClient와 LowCmd를 동시에 구동하지 않음 |

단순한 공통 GUI는 유지할 수 있다. 그러나 **실제 policy loader·관측·상태·actuator adapter를 공통 속도 계약 아래 따로 만드는 일**이 남는다. 이번 조사에서 특정 AME-2 Go2 checkpoint를 받거나 실행하지 않았으므로 그 입출력 차원·성능·실기 준비 완료는 미확인이다.

## 4. 민우 Nav2 자료와 턱 차단 위치

lab 원격 main의 `inbox/lee/`에는 README·브레인스토밍 2파일·20260908-pit진단이 있다. 이번 lead branch는 inbox/jay만 있어 “저장소에 민우 자료 없음”이라고 일반화하면 틀린다. Nav2 설정의 직접 근거는 RunPod `ros2_ws`와 `go2-slam-nav2`다. runs/ch11에는 nav01~nav09, nav_v2_L* 및 L13/L14 등이 보존돼 있다. 이번은 성공률 재집계 요청이 아니므로 run 목록을 성공 증거로 세지 않았다.

이하 `NAV/`는 로컬 `.../_out/app_nav_1028/nav/`다.

| 구성 | 민우 최신 저장 YAML | 근거 |
|---|---|---|
| 전역 planner | `nav2_navfn_planner::NavfnPlanner`, use_astar false | `config/nav2_params.yaml:310`~321 |
| local controller | `nav2_mppi_controller::MPPIController`, model_dt .05, horizon56, batch2000, vx_max1.0/vx_min0/vy_max0/wz_max.6 | 같은 파일 `:85`~110. 주석의 vx .5보다 실제 YAML 1.0이 우선 |
| local costmap | odom/base_link, 6×6 m, .05 m, robot_radius .35; VoxelLayer + InflationLayer | `:185`~230 |
| global costmap | map의 24×24 m rolling window, ObstacleLayer + InflationLayer; static_layer는 설정 블록이 있어도 plugins 배열에서 제외 | `:253`~293 |
| 장애물 입력 | 둘 다 `/scan_map` LaserScan, marking/clearing true, obstacle range2.5 m, raytrace3 m, inflation .4 m | `:202`~230, `:270`~293 |
| 별도 충돌 감시 | `/scan`을 사용. cmd_vel_smoothed→cmd_vel, FootprintApproach, time_before_collision1.2, min_points6, source_timeout3 | `:412`~445 |
| PPO 교재 adapter | Twist body vx/vy/wz, 마지막 명령 유지, 기본 stale .5 s와 clip [1.5,0,.6], 정책50Hz | `cmdvel_ppo_adapter.py:12`~15, `:32`~33, `:71`~77, `:106`~107 |

**교재와 실제 override 구분:** `stack_nav_scanfix_D3.log:79`은 MPPI/smoother/adapter 상한1.0을 기록한다. 위 adapter 기본1.5가 그 run에 들어갔다고 쓰지 않는다. 최신 source와 S3 install nav2_params 내용은 일치했지만, 모든 과거 run이 같은 YAML을 소비했는지는 별도 미확인이다.

턱을 벽으로 보는 경로는 다음과 같다.

1. `config/pointcloud_to_laserscan_map.yaml:8`~17에서 `base_stabilized` 기준 z −.22~+.13 m 띠, 거리 .3~4 m를 남겨 2D scan으로 만든다. 이 단계에서 높이별 형상과 발판 의미가 줄어든다. 원점 높이가 .32 m라는 주석 전제라면 바닥 위 .10~.45 m의 턱/벽이 모두 띠에 들어갈 수 있다. 실제 자세에 따라 달라지므로 보편적인 통과 높이가 아니다. [공식 변환기](https://github.com/ros-perception/pointcloud_to_laserscan#parameters)는 target_frame 변환 후 min/max height로 표본을 고른다.
2. scan을 local **VoxelLayer**, global **ObstacleLayer**가 marking한다. 따라서 “ObstacleLayer 하나”로 부르면 local 경로를 놓친다. InflationLayer는 이미 표시된 장애물 주변 비용을 확장한다. [Nav2 ObstacleLayer](https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/costmap_2d/costmap_plugins/obstacle/)의 marking·range 정의와 일치한다.
3. collision monitor는 costmap과 별도로 `/scan` 원물에서 정지/감속을 걸 수 있다. [Nav2 공식 설명](https://api.nav2.org/nav2-rolling/html/md_nav2_collision_monitor_README.html)은 이를 Nav2 아래의 독립 안전 노드로 설명한다. **이 노드만 끄면 costmap의 턱 marking이 없어지는 것은 아니다.**

이번 자료에서 특정 턱 정지 사건의 원인 층을 확정할 timestamp별 costmap/scan/command 동시 대조는 하지 않았다. YAML로 확인한 차단 가능 경로와 개별 실패 원인 확정은 다르다. 기존 주석의 기울어진 먼 바닥·가짜 장애물 실측 주장 역시 이번 조사에서 수치 재현한 것은 아니다.

앱 자체의 Nav2도 민우 설정과 다르다. `APP/apps/agent/tools/nav2/nav2_params.yaml:29`은 RegulatedPurePursuitController, `:48` Navfn A*, `:63`부터 base_footprint·반경 .782·GT scan/map. `executor/nav2/intent.py:29`~61은 시험한 이산 속도만 받으며 미지원 속도를0으로 만든다. 민우의 연속 MPPI 명령을 그대로 연결하면 저속·회전 명령이 거부될 수 있다.

## 5. 우리 설계와의 대조

| 설계 요구 | 확인한 구현과의 관계 | 판정 |
|---|---|---|
| 44 §2 body vx/vy/wz 공통 계약 | 세 경로 모두 이 축 정의를 사용할 수 있음. 그러나 모바일 연속 입력, agent 이산 입력, 민우 vy0/연속vx는 범위가 다름 | 축은 맞음, 허용 범위 계약 미통합 |
| 44 §2~3 정책·지형별 허용 범위와 표시/전환 | 모바일은 경고만, 서버는 고정 alphabet. 정책 이름은 표시되지만 실행물 전환기는 확인 못 함 | 부분 구현 |
| 44 §2 .3s 끊김 STOP 같은 동작, 43 C3는 가정 | agent Core `:302`~305는 deadman 입력 폐기/0이며 그 분기 자체는 latch를 세우지 않음. 민우 교재는 .5s→0 뒤 새 메시지로 복귀 | 의미 다름. 가정을 확정된 공동 계약으로 읽지 말 것 |
| 23 §1/§8 HiPAN 우선, Nav2 경로→깃발 추종 대체 | 민우는 MPPI→Twist→PPO, 앱은 RPP→이산 adapter. 현재 impl-integ에 문서의 ros/goal_provider·flag_follower 경로 없음 | 별도 연결 필요 |
| 이번 의뢰의 Nav2 전체 경로 + HiPAN 짧은 거리 + START 하위 | 21/23/54는 HiPAN과 Nav2를 우선/대체로 서술. 현재 코드에서 Nav2 부목표→HiPAN 입력의 결속은 확인 못 함 | **방향과 옛 문서 사이 차이**. 새 요구를 폐기하지 않고 interface 항목으로 명시해야 함 |
| APPROVED O / 44 §3 계단에서 Nav2 collision monitor 해제 | 그 조치만으로 local/global costmap의 계단 장애물 표현은 해결되지 않음 | 충분조건 아님 |
| 23 §3 듬성 지형 자율통과는 HiPAN, Nav2 대체는 제외 | 2D occupied/free만으로 발판 지지·구덩이 여부를 보장하지 못함. 모바일 평면187은 더 제한적 | 제한을 유지해야 함 |
| 44 §5 AME-2도 같은 계약 | 공통 외부 계약이라는 설계는 가능. 공개 AME-2의 pose/time과 실제 Go2 이식 입력을 adapter로 잇는 증거 필요 | 조건부, drop-in 확정 불가 |

## 6. 전달해야 할 최소 결속 정보

다음 학습 설계 전에 정리할 연결 정보는 정책 artifact SHA와 export 종류, 관측 항목/순서/좌표/정규화, history·GRU 초기화, 실제 센서 지도 생성법, 관절순서·default·PD·토크/속도·action clip, 정책/물리 주기, body 명령 허용 범위와 source 우선권, STOP/timeout/재개 의미다. Nav2+HiPAN을 직렬로 쓸 경우에는 map 부목표의 좌표틀·유효시간·도달/실패·취소 계약과 속도 명령의 단일 생산자도 필요하다.

이 목록은 새 숫자 관문이나 실행 지시가 아니다. **현재 확인된 연결 실패 가능성을 막기 위한 계약 공백 목록**이다. GPU/Kit/서버/실기 실행, 앱 코드 수정, 정책 교체, 커밋·push는 하지 않았다.
