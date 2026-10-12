> 분류: A/평가 · 공통 평가 계약 설계
> 작성: ASTRA (Codex) · 2026-10-13
> 근거: 의뢰 12 · VERIFY-astra-11 §3.3 · v2 모델·설정 기록 · 양 계열 평가기와 직접 의존 코드 정적 대조
> 요지: 관측 adapter만으로는 같은 시험이 되지 않는다. 공통 물리·명령·궤적 계약과 별도 판정기를 두고, 이식 검증·명령 시험·장애물 통과·앱 운용을 구분한다.
> 상태: 설계 제안 · 파일 읽기와 해시 확인만 수행 · 구현·학습·평가 미실행 · 처리량·실기 성능 미확인

# ASTRA 12 · v2·CMD-R·지도 A/B의 공통 평가 계약

**추정:** 권고 계약 이름은 `CE12-v1`이다. 기존 v2 규격 2나 Q-E1의 이름으로 새 점수를 발표하지 않는다. 동일 세계에서 각 정책이 원래의 입력 표현을 받도록 하고, 같은 기록 형식으로 남긴 궤적을 하나의 판정기로 다시 읽는다. 과거 점수 재현, 동결 정책의 새 요구 적합성, 새 구조의 인과 효과는 서로 다른 질문이다.

**확인됨:** 이 문서는 저장소 HEAD `730d50f825e8b862ea3689a9b975723675d85c50`에서 지정 자료와 직접 의존 코드를 읽어 작성했다. 공유 체크아웃에 다른 작업의 변경이 있으므로 기존 파일은 수정하지 않았다. 이번 산출물은 이 파일 하나다. 코드의 동작 설명은 정적 확인이고 실제 실행 결과가 아니다.

**미확인:** 현재 CMD-R on/off 24,000 checkpoint의 실제 완성·선정 여부, 그 checkpoint의 실행 시 resolved 설정, Linux 이전 뒤 동등성, 5080 처리량은 이번에 확인하지 않았다. 아래에서 CMD-R은 파일명만으로 확정된 모델이 아니라 해시·bundle로 등록해야 할 후보를 뜻한다.

## 1. 직접 확인한 차이와 먼저 막아야 할 오류

**확인됨:** 경로 약어는 `LAB` = 이 저장소 루트, `Q` = `C:/isaac/ext/go2_rl_robotlab/_eval`, `RL` = `C:/isaac/ext/go2_rl_robotlab/source/robot_lab/robot_lab`, `IL` = `C:/isaac/IsaacLab/source/isaaclab/isaaclab`이다. 아래 `파일:행`은 이번에 읽은 파일의 위치다.

| 항목 | 정적 확인과 설계에 미치는 영향 | 근거 |
|---|---|---|
| 물리 모델 | **확인됨:** v2는 Isaac Go2 USD·DCMotor, RobotLab 기본은 URDF 변환·UnitreeActuator Go2HV다. 둘 다 Kp=25·Kd=0.5라도 동일 구동기가 아니다. 후자는 지연 0~4 설정과 다른 토크 제한 곡선을 가진다. 단순 관측 변환만으로 같은 물리라는 주장은 틀린다. | `LAB/models/foothold-v2.env.yaml:134,166` · `RL/tasks/go2/env_cfg.py:63` · `RL/assets/unitree.py:127,142` · `RL/assets/unitree_actuator.py:59,78,125` |
| 제어 주기 | **확인됨:** 읽은 양 설정은 physics 0.005초·decimation 4다. 실행값이 동일한지는 별도 assert가 필요하다. | `LAB/models/foothold-v2.env.yaml:21,84` · `RL/tasks/go2/env_cfg.py:483,486` |
| v2 명령 | **확인됨:** 학습에는 heading·standing이 있지만, 기존 평가기는 heading·standing을 끄고 `(vx,0,0)`을 준다. v2만 heading 제어를 살리는 것은 공통 평가가 아니다. | `LAB/models/foothold-v2.json:72` · `LAB/sim/eval/eval_generalization.py:255` |
| 초기 상태·DR | **확인됨:** v2 평가기는 base mass·COM·push 등을 끄지만, CMD-R 평가기는 push만 끄고 다른 기본 DR이 남는다. CMD-R은 xy ±0.5m, z +0~0.2m, 기본 관절 자세를 사용한다. 현재 평가 둘의 같은 seed는 같은 초기 상태·물성을 뜻하지 않는다. | `LAB/sim/eval/eval_generalization.py:276` · `Q/q_eval_cmdr.py:234` · `RL/tasks/go2/env_cfg.py:249,269,285,296` |
| 지형 복제 | **확인됨:** CMD-R은 v2 지형 설정을 가져와도 10행으로 바꾸고 8개 시작 행을 사용한다. v2는 1행이다. 생성기 seed와 전역 난수 소비도 구분해야 한다. 설정 이름이 같다는 이유로 동일 mesh라고 판단할 수 없다. | `Q/q_eval_cmdr.py:254,285,332` · `LAB/sim/eval/generalization_env_cfg.py:30` · `LAB/sim/eval/eval_generalization.py:220` |
| v2 성공 | **확인됨:** 시간 만료 생존·3m 진행·평면 속도 오차·3m gate에서의 방향 판정이다. 방향 축은 전체 궤적의 최대 이탈과 다르다. | `LAB/models/foothold-v2.json:173` · `LAB/sim/eval/metrics.py:493,641` |
| Q의 저속 | **확인됨:** 기본 Q1은 축별 MAE 0.15m/s여서 0.1 명령에서 가만히 있어도 추종 오차는 통과할 수 있다. q1a는 명령 축에 `min(0.15,0.5×명령 크기)`를 적용하지만 주 성공 판정과 별도다. | `Q/q_metrics.py:28,42,198,206` · `Q/q_post.py:66,78` |
| Q의 시간 | **확인됨:** 기본 `n50`은 50표본, `span`은 51표본으로 1초 유지를 판정한다. `q_post`는 둘을 계산하지만 원 지표 전부를 span으로 바꾸지는 않는다. 새 결과의 시간 정의를 이름과 함께 고정해야 한다. | `Q/q_metrics.py:47,113` · `Q/q_post.py:17,44,81` |
| Q의 STOP | **확인됨:** 정지 거리는 정지 구간 시작까지의 순변위다. 최대 이탈·잔류 이동은 별도 기록이며 Q2의 주 조건이 아니다. 갔다 돌아온 경우나 잠시 정지 후 다시 움직인 경우를 새 운용 판정에서 따로 막아야 한다. | `Q/q_metrics.py:276,290,300,317` |
| 건넘 | **확인됨:** `unseen_post`의 crossed는 낙상 전 base x가 장애물 끝을 넘었는지다. 발 전체의 이탈·도착 유지·회피 여부를 검증하지 않는다. q1/span과도 독립적이다. | `Q/unseen_post.py:45,51,62` |
| 종료 시점 | **확인됨:** q 기록의 종료 표본은 이미 reset된 상태일 수 있어 invalid로 취급한다. 기존 v2도 마지막 접촉·이동 표본 손실을 주석으로 인정한다. 이것을 그대로 결합하면 종료 직전의 발 위치·위험선 침범을 놓친다. | `Q/q_metrics.py:10` · `Q/q_eval_cmdr.py:621` · `LAB/sim/eval/eval_generalization.py:1418,1534` |

**추정:** 따라서 기존 CSV 열 이름을 서로 바꾸는 방식으로는 해결되지 않는다. 기존 평가기는 비교 근거로 보존하고, 공통 환경·입력 adapter·시간 정렬·판정기를 별도로 구현한다. 현행 실행 파일은 수정하지 않는다.

## 2. 실행 계약

### 2.1 무엇을 동일하게 하고 무엇을 보존하는가

| 계층 | CE12-v1 계약 | 상태 |
|---|---|---|
| 물리 세계 P0 | **v2 기록을 출발점으로 한 하나의 Go2 USD·DCMotor 설정**을 모든 후보에 적용. Kp 25, Kd 0.5, effort·saturation 23.5, velocity 30, 관절 마찰 0, 인위적 구동 지연 0. 질량·관성·충돌 mesh·solver·접촉 재질은 resolved manifest로 동결 | 추정. 수치 출처는 `models/foothold-v2.env.yaml:166`. 모든 기체 자산의 실제 동일성은 미확인 |
| 이 선택의 의미 | P0는 v2와 연속성이 있는 **명시적 기준 물리**이지 중립적 실물 정답이 아니다. CMD-R에는 물리 분포 변화가 될 수 있다. 아래 이식 진단 없이 P0 결과를 구조 순위로 해석하지 않음 | 추정 |
| DR·잡음 | 1차 R0는 mass·COM·gain·motor offset·delay·push·외력·관측 잡음·curriculum을 모두 끔. 모든 충돌 shape와 바닥의 마찰 1.0/1.0, restitution 0, combine multiply를 명시. 이후 DR 시험은 모델별 난수 호출 대신 episode별 실제 물리 값 파일을 재사용 | 추정. 마찰 출처 `models/foothold-v2.env.yaml:54,343`. R0는 기존 v2의 재질 DR까지 동일한 역사 재현이 아님 |
| 시간 | physics dt=0.005, policy dt=0.020초. 제어 step 수는 정수. 가변 dt·렌더 속도로 명령 시간을 정하지 않음 | 추정. 기존 주기는 위 표에서 확인됨 |
| reset | 같은 canonical root pose·관절 위치·속도·이전 action 상태. root z는 공통 시작 패치 기준 0.4m에서 준비하고 충돌·지지 검사. 정책 없이 공통 PD 준비 동작을 거친다면 그 길이·도달 상태를 고정하고 시험 시계 밖에 둠 | 추정. 준비 동작 뒤 완전히 같은 상태를 확보하는 구현은 미확인 |
| 관측 | 각각의 학습 입력 순서·scale·clip·이력·정규화를 보존. v2에는 본래의 선속도·지도, CMD-R student에는 본래의 proprio 이력. 동일 정보량으로 억지로 바꾸지 않음 | 추정. 이는 동결 정책 전체의 비교이며 구조 하나의 인과 비교가 아님 |
| 출력 | 모델별 raw action 의미와 순서를 복원한 뒤 이름 기반으로 공통 joint target에 연결. 공통 물리에 각 모델의 native actuator를 따로 쓰지 않음 | 추정 |
| 상태 판정 | 정책 내부 critic·보상·종료 함수를 성적표로 쓰지 않음. 공통 물리 상태와 사건에서 판정. 모든 후보에 같은 관측 외 평가용 GT 허용 | 추정 |

**추정:** 먼저 작은 **이식 진단**을 두 단계로 한다. ① 원래 세계의 같은 원시 상태·명령 이력을 입력했을 때 native 코드와 새 adapter의 obs·action·joint target이 일치하는지 검사한다. ② flat의 stand·fwd03·yawL05에서 각 정책을 P0와 CMD-R의 동결 native 물리 P1에 모두 놓는다. P1은 비교 진단용 세 칸뿐이며 본 성적표와 합치지 않는다. P1은 현재 기본 cfg가 아니라 선정 checkpoint의 실제 설정·bundle로 정한다. 코드의 default-vs-train diff가 기록만 되고 자동 중단되지 않는 점도 고친다. 근거: `Q/q_eval_cmdr.py:188,216,222`.

**추정:** 동일 물리에서 점수가 낮으면 그 시험에서 낮다는 결과는 유효하다. 다만 native에서는 정상이고 다른 물리에서만 크게 나빠지면 먼저 이식 민감도로 분류한다. P0/P1에서 우열이 뒤집히면 ‘어느 구조가 우수하다’는 단일 결론을 내리지 않는다. 두 물리 전체 지형 재평가를 자동 추가하기보다 물리 설정과 새 A/B 학습 세계를 먼저 결정한다.

**미확인:** 추가 장착 모듈·payload·실기 토크 지연의 사실값이 확보되지 않았으므로 P0를 Go2 실물의 검증된 digital twin이라고 부르지 않는다. 앱 기획에도 D435i·XT-16 장착과 robot watchdog이 미확인이다. 근거: `../20261013-go2-app-study/APP-PLAN-facts.md:18,30`.

### 2.2 관측 adapter · 차원보다 의미가 먼저다

| adapter | 구성·변환 | 근거·상태 |
|---|---|---|
| `V2Adapter` | 235 = base lin vel 3, base ang vel 3, gravity 3, command 3, relative q 12, relative dq 12, previous action 12, height 187. 읽은 env.yaml의 body 항 scale은 null이다. CMD-R의 0.25·0.05를 여기 복사하지 않음 | 확인됨: `models/foothold-v2.env.yaml:539` |
| v2 높이 | yaw 정렬, 1.6×1.0m·0.1m·ordering xy. `height_scan_with_gap`의 **sensor.data.pos_w 기준 식**과 offset 0.5·miss +1·clip [-1,1]을 그대로 사용. ray 발사 offset 20m를 몸 높이에 잘못 더하지 않음 | 확인됨: `models/foothold-v2.env.yaml:354,630` · `sim/eval/gap_observations.py:56,69` |
| v2 관절 | `.*`와 preserve_order=false여서 12개 이름의 실제 articulation 순서를 확인해야 한다. CMD-R 순서라고 추정하지 않음. 원래 USD에서 얻은 이름 목록을 adapter의 입력·출력 서명으로 고정 | 확인됨: `models/foothold-v2.env.yaml:595,670` · 미확인: 이번에 런타임으로 해석한 v2 12개 순서 |
| `CTSStudentAdapter` 단일 관측 | 45 = scaled body ang vel 3(×0.25), gravity 3, command 3, relative q 12, relative dq 12(×0.05), previous raw action 12. 각 term clip [-100,100] 후 scale. FL→FR→RL→RR의 hip·thigh·calf 순서 | 확인됨: `RL/tasks/go2/env_cfg.py:23,122` · `IL/managers/observation_manager.py:392` |
| CTS 이력 | **각 term의 10개 시간 이력을 flatten한 뒤 term들을 concatenate.** `[45차원 시점0, 시점1, …]`를 붙이는 time-major 배열이 아님. 오래된 항목부터 최신까지. 최신 command가 이력의 87:90에 위치하는 현 검사와 일치해야 함 | 확인됨: `IL/managers/observation_manager.py:408,423,430` · `IL/utils/buffers/circular_buffer.py:80` · `Q/q_eval_cmdr.py:600` |
| 이력 초기화 | 첫 표본을 10칸에 반복하는 native buffer 동작을 보존. 10칸을 0으로 채운 뒤 천천히 채우는 구현으로 바꾸지 않음. 정책 step당 정확히 한 번 갱신하고 디버그 관측 읽기는 history를 전진시키지 않음 | 확인됨: `IL/utils/buffers/circular_buffer.py:129,136` · `IL/managers/observation_manager.py:317` |
| CTS 추론 | `act_inference`의 student encoder + single_obs 경로만 사용. teacher/critic 입력을 바꿔도 action이 변하지 않는 known-input 검사. 구현 생성자 때문에 critic key가 필요하더라도 추론에 정보가 새지 않게 검증 | 확인됨: `C:/isaac/ext/go2_rl_robotlab/source/rsl_rl/rsl_rl/modules/actor_critic_moe_cts.py:70,225` · `Q/q_eval_cmdr.py:469` |
| 정규화 | checkpoint와 함께 저장된 agent 설정과 normalizer 상태를 복원하고 eval 상태로 고정. 현재 템플릿은 normalization=false지만 그것으로 모든 후보를 단정하지 않음 | 확인됨: `models/foothold-v2.agent.yaml:23` · `RL/tasks/go2/rsl_rl_cfg.py:47` · 추정: 로딩 계약 |
| `MapABAdapter` | 미래 구현의 서명을 읽어 등록. A/B는 같은 몸 상태 경로와 지도 표현. A의 높이·validity mask 모두 상수, B는 동일 GT 지형 원천. 값·shape를 확정하기 전 109 등 잠정 차원을 하네스에 하드코딩하지 않음 | 추정. 미래 구현 미확인 |

**추정:** `PolicyAdapter.reset(ids)`, `observe(state, command, sensor_packet)`, `infer()`, `decode_action(raw)`를 경계로 둔다. adapter가 질량·구동 지연·명령 시간·낙상 기준을 바꾸지 못하게 한다. joint target은 `q_default_native + scale_native × clipped_raw_native`를 원래 규칙으로 복원한 뒤 이름으로 공통 관절에 대응한다. previous action은 **각 정책에서 실제로 관측하던 표현**을 저장하며 target이나 applied torque로 대체하지 않는다. 근거: v2 actions `env.yaml:670`, CTS actions `env_cfg.py:110`, 두 관측의 last_action 항.

### 2.3 명령과 heading · 두 모드를 섞지 않는다

**추정:** 주 시험은 `BODY_FIXED`다. 미리 저장한 `(vx_body, vy_body, wz_body)`를 두 계열에 **수치까지 같은 시간열**로 준다. native resampling·heading·standing 확률·0.2 이하 명령 절삭을 모두 우회한다. ‘v2의 heading을 없애면 학습과 다르다’는 이유로 v2에만 복원하지 않는다. 기존 v2 평가도 이미 heading을 껐다. CMD-R의 `_resample` 우회와 실제 관측 command 검사를 일반화한다. 근거: `Q/q_eval_cmdr.py:355,599`, `RL/tasks/go2/mdp/commands.py:186`, `sim/eval/eval_generalization.py:255,375`.

**추정:** 통과 방향은 세계 +X로 고정한다. 전진 yaw0=0, 후진 yaw0=π, 좌횡 yaw0=-π/2, 우횡 yaw0=+π/2로 배치한다. 모델 간에는 같은 yaw·공간 위치를 쓴다. 몸을 돌려 전진해 통과하면 순수 횡이동 명령의 성공으로 세지 않는다. 몸체 추종과 세계 방향 진행을 모두 기록한다. 이 배치 자체는 기존 CMD-R 방식과 같다. 근거: `Q/q_eval_cmdr.py:350`.

**추정:** 앱 연결용 보조 모드는 `WORLD_PATH`다. 같은 세계 목표 속도를 각 정책의 현재 yaw로 몸체 좌표에 변환하고, 공통 heading controller가 있으면 두 정책 모두에 적용한다. `vx_b=cosψ·vx_w+sinψ·vy_w`, `vy_b=-sinψ·vx_w+cosψ·vy_w`. 이 경우 **같은 제어 법칙이지만 실제 policy command 숫자는 상태에 따라 다르다.** BODY_FIXED와 같은 ‘동일 명령 시간열’ 비교라고 부르지 않고 별도 controller_id와 표를 사용한다. 최초 평가에는 BODY_FIXED만 필수다.

### 2.4 시간·종료·원시 기록

**추정:** 기본 기록은 `state[k] at t=k×0.02`, `command[k]가 obs[k]에 들어감`, `action[k]`, `state[k+1]`이다. 상태를 만든 명령은 command[k]이며 command[k+1]가 아니다. 기존 Q의 `cmd[j]`는 state[j]를 만든 action[j-1]의 명령이므로 legacy adapter에서 한 번만 변환한다. 신규 형식은 `state_time`과 `action_time`을 명시해 추측을 없앤다. 근거: `Q/q_metrics.py:10`, `Q/q_post.py:37`, `Q/q_eval_cmdr.py:599`.

**추정:** STOP이 5.00초면 state[250]에서 command[250]=0을 처음 정책에 보여주고 그때의 위치를 정지 원점으로 삼는다. 직전 구간의 이동 평가는 command[249]까지의 반응을 포함한다. 새 명령 전환 때문에 현재 history의 command slot을 다음 관측과 맞바꾸거나 이력을 두 번 갱신하지 않는다.

**추정:** 자동 reset 이전의 마지막 상태·접촉·관절·발 위치를 저장한다. Isaac의 `record_post_step`/`record_pre_reset` 지점을 이용할 수 있으나, recorder가 없으면 현 코드처럼 실행되지 않을 수 있다. 실제 callback이 reset 전에 유효 데이터를 잡는지 먼저 검증한다. contact history는 decimation 4개 물리 표본을 모두 덮도록 최소 4개를 확보하고 타임스탬프를 보존한다. 외부 라이브러리나 실행 중 하네스를 직접 수정하지 않고 평가 전용 recorder 또는 subclass에 둔다. 근거: `IL/envs/manager_based_rl_env.py:181,203,210,215`.

**추정:** 첫 종료는 흡수 상태로 취급한다. 이후 reset된 로봇이 다시 걸은 결과를 같은 episode에 잇지 않는다. 물리적 실패·시간 만료·하네스 오류를 별도로 분류한다. timeout은 낙상이 아니다. NaN은 성공도 누락 표본도 아니며, 정책 출력의 NaN이면 정책 실패, 파일 손상·환경 생성 실패면 실행 무효로 분리한다. 무효 판은 분모에서 조용히 빼지 말고 수와 사유를 공개하며 재실행은 같은 episode_id로 한정한다.

| 기록 | 필수 필드 | 상태 |
|---|---|---|
| manifest | contract·code·checkpoint·bundle·asset·mesh·원자료 SHA, policy signature, physical_profile, command_mode, physics/policy dt, versions, resolved physics·DR, sensor truth/occlusion 의미 | 추정 |
| episode identity | cell_id, terrain_family, geometry_id/hash, terrain_draw_seed, start_id, initial_state_hash, DR_draw_id, command_schedule_hash, checkpoint_id, training_seed, parent_id, pair_key | 추정 |
| 시계열 | root position·quaternion·world/body 선속도·각속도, command·raw action·joint target, q/dq, 발 위치·접촉, base 접촉, support query와 valid mask, 위험선 거리, 센서 시각, 종료 사건 | 추정 |
| 판정 출력 | 원시 오차·거리·시간, track/route/survive/cross/arrival/stop flags, 실패 사유와 최초 시각, 예측이 아니라 실제 조우, invalid reason, legacy 점수 namespace | 추정 |

## 3. 시험 칸과 판정

### 3.1 시험지를 네 묶음으로 고정한다

| 묶음 | 칸 | 시간·거리 | 상태 |
|---|---|---|---|
| H · 역사 비교 | gap·rails·rough6 여섯 종류 × 전진 0.5/1.0/1.5 = 24칸. rough를 하나의 평균 칸으로 뭉개지 않음 | 기존 12/6/4초, 3m 진행·3m direction gate·0.75m·MAE 0.25. 원래 환경 재현 H-native와 P0 위에서의 H-score를 구분 | 확인됨: `models/foothold-v2.json:173`, `sim/eval/terrains.py:79` · 추정: namespace 분리 |
| C · 명령 능력 | flat와 random_rough 각각 전진 0.1/0.2/0.3/0.5, 후진·좌·우 0.3, yaw ±0.5rad/s, stand, stop03, stop05 = 각 12칸 | 아래 C 정의. 주 결과는 CE12. 기존 Q1/q1a/span은 보조 출력 | 추정 |
| S · 희소 지형 통과 | gap·stepping_stones 각각 전진 0.3/0.5 = 4칸. 그다음 gap의 후진·좌·우 0.3. rails 저속은 추가 칸 | 실제 장애물 끝과 안전 도착 구간으로 완료 거리 결정. C에서 실패해도 S를 성공으로 숨기지 않음 | 추정 |
| O · 앱 운용 | 감속·STOP·위험선 접근. 속도 0.3/0.5, 위험선까지 초기 제동 여유 0.3/0.5/0.8m | 첫 단계는 정책에 직접 0 명령. 지연 0.3/1.0초는 별도 fault injection. 보행 S와 합산하지 않음 | 추정. 앱 요구 근거 `APP-PLAN-facts.md:17,18,20` |

**추정:** 초기 pilot는 **C-flat 12칸 + S-gap03 + S-stones03의 14칸**으로 제한한다. 설계된 나머지 칸은 삭제된 것이 아니라 확인 평가 목록이다. 비용을 측정한 뒤 H 24칸·C-rough·나머지 S·O 순으로 확대한다. 일부만 돌았으면 전체 요구 완료라고 적지 않는다. 모델은 동결 v2, 사전 등록한 CMD-R 후보, 미래 A/B다. on/off를 둘 다 비교하면 모델이 다섯이며, 평가 결과를 보고 한쪽을 숨기지 않는다.

### 3.2 C · 저속·횡·후진·회전

**추정:** 양의 이동 명령 크기를 `v=||(vx,vy)||`라 두고, 정상 추종 구간 `W=max(5초,1m/v)`, 총 시간 `T=ceil((1+W)/0.02)×0.02`로 정한다. 처음 1초는 과도 응답으로 별도 기록하고 정상 추종 오차에서는 제외한다. 생존·위험 침범은 처음부터 센다. 0.1은 T=11초, 0.2/0.3/0.5는 T=6초다. 정상 구간의 명령 거리 `D_cmd=∫v dt`도 저장한다. 이 시험은 1~2.5m 구간의 명령 능력이며 큰 지형 하나를 완주했다는 시험이 아니다.

| 지표·판정 | CE12-v1 제안 | 상태 |
|---|---|---|
| 이동 축 추종 | 명령 축 MAE ≤ `min(0.15m/s,0.5×|c_axis|)`. 상대 오차도 원값으로 공개. 0.1→0.05, 0.2→0.10, 0.3/0.5→0.15. 이는 기존 q1a 계열의 연구용 문턱이며 제품 정밀도 인증이 아님 | 추정. q1a 근거 `Q/q_metrics.py:206` |
| 0 명령 선형 축 | 각 MAE ≤0.05m/s. 0.1 전진에 횡 0.14m/s를 허용하는 기존 Q의 약점을 막음 | 추정. 새로운 문턱이므로 Q1 점수라고 부르지 않음 |
| yaw 추종 | 이동 칸에서 body wz MAE ≤0.20rad/s. yaw 칸은 `min(0.20,0.5×|wz_cmd|)` 적용, 선형 speed 평균 ≤0.05m/s·평면 최대 이탈 ≤0.20m | 추정 |
| 실제 진행 | 정상 구간의 세계 고정 진행축에 대한 **signed net progress / D_cmd ≥0.5**. body 속도 평균만으로 대체하지 않음. 돌거나 갔다 돌아와 마일리지가 쌓인 판을 배제 | 추정. 기존 body move_ratio 근거 `Q/q_metrics.py:235` |
| 방향 | 직선 칸의 최대 횡이탈 ≤0.30m를 전체 구간에서 검사. heading 오차 시계열·끝점·최대값도 보고. yaw 칸은 진행 거리 기준을 적용하지 않음 | 추정. 0.30의 기존 근거 `Q/q_metrics.py:38` |
| 회전 실제량 | yaw ±0.5 칸은 T=6초, 정상 5초. unwrap한 signed yaw 변화/명령 적분 ≥0.5. angular MAE와 함께 판정. ±π wrap을 실패나 역회전으로 읽지 않음 | 추정 |
| stand | T=10초. 평면 speed<0.05, |wz|<0.10을 유지하는 비율·최장 이탈 시간·최대 위치 이탈 기록. CE stand pass는 1초 이후 전 구간 임계 이내·최대 이탈 ≤0.10m·전 구간 생존 | 추정 |
| 종합 | `C_pass = survived ∧ tracking_pass ∧ progress_or_rotation_pass ∧ route_pass`. stand는 별도 식. 축별 flag를 모두 보존. 생존자만의 MAE와 전체 pass를 같은 것으로 제시하지 않음 | 추정 |

**추정:** 50% 상대 오차는 ‘움직이지 않는데 통과’ 오류를 막는 초기 연구 문턱일 뿐, 충분히 정확한 앱 제어라는 뜻이 아니다. 결과에는 실제 gain, 상대 MAE, 최대 overshoot, 정체 시간도 같이 낸다. 이 문턱을 나중에 통과율에 맞춰 바꾸면 contract 판을 올리고 모든 저장 궤적을 재판정한다.

**추정:** C의 `정체`는 명령이 0이 아닌 동안 2초 이동 창의 signed progress가 기대 거리의 10% 미만인 사건으로 정의한다. 발생 횟수·시간을 기록하며, 이를 발견했다고 즉시 조기 종료하지 않는다. 희소 지형에서 잠시 발판을 고르는 동작은 완료 여부와 구분한다. 0 명령 구간에는 정체를 붙이지 않는다.

### 3.3 S · 장애물을 실제로 만났고 건넜는가

**확인됨:** 기존 `obstacle_zone_m`는 타일 중심 기준 +X의 구간이다. gap 끝은 플랫폼/2+틈폭, rails는 바깥 레일 끝, 나머지는 넓은 타일 반폭일 수 있다. 이것을 실제 출발점 상대 거리로 쓰거나 임의 방향의 위험 polygon으로 간주하면 틀린다. 근거: `sim/eval/terrains.py:169,216,231`.

**추정:** 각 지형 instance에 `approach_gate`, 실제 위험 영역 또는 obstacle segment, `exit_gate`, `landing_region`, 허용 corridor를 **세계 좌표로** 저장한다. gap은 빈 지면 영역·착지면, rails는 첫/마지막 레일, stones는 해당 구간의 발판 mesh를 연결한다. 기하 근거를 못 만들면 ‘base가 구간 끝을 지남’이라는 legacy 보조 지표만 낼 수 있으며 `cross_success`는 미확인이다.

| 사건 | 정의 | 상태 |
|---|---|---|
| 조우 | 정해진 접근 방향으로 approach gate를 통과하고 로봇의 전방 지지 발 footprint가 장애물 접근 띠에 진입. 발판 위에 실제로 발을 놓거나 gap 안에 발을 넣어야만 조우라고 세지 않음 | 추정 |
| 우회 | 장애물 출구 쪽에 도달했으나 필수 통과 영역·corridor를 벗어남. `avoidance=true`. S에서는 성공 아님, O에서는 경로 정책에 따라 정상일 수 있음 | 추정 |
| 건넘 | base뿐 아니라 **네 발 모두** 지정 exit gate를 지나 안전 영역에 있고, 네 발 각각이 출구 후 유효 지면 접촉을 한 번 이상 얻음. 네 발의 동시 접촉은 요구하지 않음 | 추정 |
| 도착 | 건넘 뒤 같은 이동 명령 아래 안전 착지 구간을 0.5초 이상 유지. 끝을 순간적으로 넘고 바로 추락하면 건넘 사건은 남기되 최종 성공은 아님 | 추정 |
| 추락·물리 실패 | base 접촉 >1N, 기울기 >60°의 0.2초 지속, 또는 사전 정의된 지지면 이탈·낙하 한계. 최초 onset와 확인 시점을 둘 다 기록 | 추정. 기존 base·tilt 근거 `Q/q_metrics.py:118` |
| 정체·미조우 | 위 C의 정체 사건, 시간 내 approach gate 미도달을 각각 기록. 이 판도 전 episode 분모에 포함 | 추정 |
| 최종 성공 | `S_pass = survived ∧ encountered ∧ crossed ∧ arrived ∧ corridor_ok`. 명령 준수까지 필요한 `S_command_pass=S_pass∧tracking_pass`를 별도 주 열로 병기 | 추정 |

**추정:** 통과 시간은 속도와 코스 길이에 맞춘다. `D`를 실제 시작 위치에서 안전 도착 구간까지의 세계 진행축 거리로 두고 `T=ceil((1초+1.5×D/v+0.5초)/0.02)×0.02`. 같은 pair_key는 같은 T다. 저속 0.1에서 긴 코스가 수십 초라면 시간을 잘라 실패시키지 말고 그 칸의 추가 비용을 명시한다. 1차 S는 0.3/0.5만 한다. 성공 뒤 시험을 일찍 끝내고 생존 시간을 늘린 것처럼 세지 않으며 전체 정해진 구간을 기록한다.

**추정:** 착지 구간과 이후 안전 여유가 위 T의 이동을 담아야 한다. 지형 바깥으로 떨어지는 것을 정책 낙상으로 채점하지 않도록 미리 경계 검사한다. 원 지형을 늘리거나 출구에 별도 landing 패치를 붙였으면 mesh hash와 시험 이름을 바꾸고 H 재현으로 부르지 않는다.

**추정:** 낙하 판정에 `base_z - 주변 hit의 평균 높이 <0`만 쓰지 않는다. 기존 Q의 평균은 단차 양쪽이나 빈 공간에서 기준이 달라지고 모두 miss면 NaN이다. gap은 출발·착지 지지면과 실제 바닥, stones는 구역별 발판 기준면, pit는 낮은 바닥 자체가 합법적인 지지면인지를 manifest에 지정한다. 지형별 fallback kill plane은 해당 기하에서 정하고 레퍼런스 값이 없으면 오류로 중단한다. 근거: `Q/q_eval_cmdr.py:560`, `Q/q_metrics.py:138`. 필요한 기하값은 미확인이다.

### 3.4 STOP · 순변위 한 개로 안전을 판단하지 않는다

**추정:** 기본 stop03·stop05는 5초 이동 +5초 0 명령, 총 10초다. 첫 1초를 제외한 이동 구간에서 C의 추종·실제 진행이 성립해야 한다. 처음부터 안 움직인 정책이 정지 성공을 얻지 못하게 `moving_ok`를 분리한다.

**추정:** 정지 속도는 평면 speed<0.05m/s 및 |body wz|<0.10rad/s다. `t_settle`은 이 조건을 **1.00초 이상 연속 유지하는 첫 구간의 시작**이다. 50Hz에서 양 끝 포함 51표본으로 span 1초를 확인한다. `t_confirm=t_settle+1초`도 저장한다. ‘1초 안에 정지’는 시작 시각 `t_settle≤1초`라는 뜻이며 확인 완료 시각이 1초 이내라는 뜻이 아니다. 물리 표본 간격이 달라지면 표본 수 상수가 아니라 타임스탬프로 판단한다.

| STOP 출력 | 정의·성공 조건 | 상태 |
|---|---|---|
| 정지 시간 | t_settle·t_confirm. 실패는 0이 아니라 null와 실패 이유 | 추정 |
| 순변위 | 정지 원점에서 t_settle 위치까지의 거리. legacy 대응용이며 단독 성공 기준이 아님 | 추정 |
| 최대 이동 | 0 명령 수신 뒤 종료까지 원점으로부터 평면 최대 이탈 `D_max`. 갔다 돌아와도 최대값 유지 | 추정 |
| 경로 길이 | 0 명령 뒤 실제 이동 거리 합. 진동·우회 진단. 표본 주기와 함께 기록 | 추정 |
| 잔류 이동 | t_confirm 뒤 종료까지 최대 speed·최대 yaw rate·위치 이탈·조건 위반 시간. 잠깐 멈춘 뒤 다시 움직인 판을 적발 | 추정 |
| CE STOP 성공 | 전 구간 생존, moving_ok, t_settle≤1초, D_max≤0.20m, 정지 유지 구간 시작부터 종료까지 위 속도 조건 유지. 조건별 flag 공개 | 추정. 기존 Q2보다 엄격한 새 지표임 |
| 분모 | 이동 실패 / 이동 성공·정지 실패 / 모두 성공으로 전체 N을 분해. 정지 부분만 성공한 수와 이동 성공에 조건부인 수를 구별 | 추정. 기존 분해 근거 `Q/q_metrics.py:297` |

**추정:** 낙상 전에 정지했더라도 이후 낙상하면 최종 실패다. 기존 Q는 tilt 지속을 확인한 뒤 onset로 되돌려 invalid 처리한다. CE12는 `failure_onset`·`failure_confirmed`를 별도로 저장하고 성공 분모에서는 실패로 처리하되, 원시 궤적을 onset 이전으로 잘라 지우지 않는다. 원인과 유효 표본을 구분한다.

### 3.5 O · 위험 구간 진입 전에 멈출 수 있는가

**추정:** 위험선 거리는 base 중심이 아니라 위험 방향의 **가장 앞선 발·몸체 footprint의 여유**로 잰다. 위험선과 footprint를 기하적으로 정의하고, 센서 미관측을 안전 지면으로 채우지 않는다. `D_max≤0.20m`만으로 발이 위험선을 넘지 않았다고 판정할 수 없다.

**추정:** 우선 고정 시각 STOP으로 동일 명령 시간열을 비교한다. 다음에는 같은 초기 episode에서 `signed_clearance≤d_trigger`가 되는 첫 시각에 STOP하는 상태 기반 시험을 별도로 한다. 후자는 같은 규칙이지 같은 시각 명령은 아니다. d_trigger=0.3/0.5/0.8m, 진입 명령 0.3/0.5m/s를 시험한다. 접근 전 낙상·미도달도 전체 분모에 포함한다. 더 가까운 trigger부터 무조건 단조롭게 성능이 나빠질 것으로 가정하지 않는다. 보행 위상도 영향을 준다.

**추정:** `safe_stop`은 위 CE STOP 조건에 더해 요청 시각 이후 위험선 침범 0, 요청 전에 이미 위험 구간에 진입하지 않음, 도착 후 재가속 없음이다. 공중 단계 STOP은 별도 범주로 남긴다. 위험선 이후에 내려진 요청으로 ‘진입 전 정지’ 성능을 평가하지 않는다.

**추정:** `d_required = 관측된 제동 전진량 + 지연 중 전진량 + 위치·footprint 불확실성 여유`를 상태·속도별로 추정하되, 표본 최대값이나 95분위수를 보편 안전 거리로 단정하지 않는다. 외삽하지 않고 시험한 거리·속도·보행 위상과 통과 구간만 보고한다. 실제 네트워크·추정 오차 여유는 미확인이다.

**확인됨:** 앱 기획의 0.3초 deadman과 1초 화면 신호 단절은 정책 자체의 제동 시간이 아니다. 근거: `APP-PLAN-facts.md:18`. **추정:** `t_request`, `t_controller_receive`, `t_first_action_with_zero_command`, `t_settle`을 나누고 주 STOP은 수신 이후, end-to-end는 요청 이후로 잰다. 여기서 0은 속도 명령이며 관절 action·토크를 0으로 강제한다는 뜻이 아니다. 0.3/1.0초 지연 주입은 실제 앱 지연 실측과 구분한다.

**추정:** 앱 속도 상한도 `command_cap_ok`와 실제 speed의 초과량·초과 지속시간을 따로 기록한다. 기획의 상한이 명령 제한인지 순간 실제 속도 한계인지 아직 명확하지 않아 후자의 제품 합격 문턱은 **미확인**이다. 이 불명확성을 ‘0.02 정도는 괜찮다’고 임의로 덮지 않는다. 연구용 C/S 점수로 앱 운용 승인을 대신하지 않는다.

## 4. 지형·초기 조건·표본과 통계

### 4.1 재현 단위는 seed 문자열이 아니라 실제 세계다

**추정:** `geometry_id`는 생성기 코드·설정·실제 mesh vertex/index·transform의 해시를 포함한다. 별도 생성 단계에서 세계를 동결한 뒤 모든 정책이 같은 파일을 읽는다. 전역 NumPy 난수를 쓰는 지형은 생성 중 상태를 격리하고 복원하거나 별도 생성 프로세스로 만든다. 정책별 env 생성 순서가 지형 모양을 바꾸지 못하게 한다. `TerrainGeneratorCfg.seed`만 바꾸면 충분하다는 설계는 채택하지 않는다. 근거: `sim/eval/eval_generalization.py:220`.

**추정:** native H 재현은 원래 설정·전체 지형 생성 순서·seed·초기 배치를 보존한다. 다른 가족을 빼고 재생성하면 이후 지형의 난수 소비가 달라질 수 있다. CE는 한 번 확보한 collision asset을 재사용해 family 선택이나 batch 크기 변화가 기하를 바꾸지 못하게 한다.

**추정:** 결정론적 gap·rails·slope는 동일 난이도에서 seed만 바꿔도 같은 기하일 수 있다. 같은 hash를 서로 다른 지형 군집으로 세지 않는다. H의 고정 d=0.5는 그 조건에 대한 평가로 남긴다. 일반화 G는 각 family의 d∈[0.1,0.9]를 20개 층으로 나누어 층당 하나를 사전 추출하고, 확률적 생성기는 독립 generation seed도 준다. random_rough처럼 difficulty가 형상을 조절하지 않는 종류는 실제 다른 mesh seed만 사용한다. 새 치수·배치를 시험한 것이지 훈련 계열 자체가 미경험이라는 뜻은 아니다. 근거: `sim/eval/rough6_env_cfg.py:29,103`.

**추정:** 첫 구현의 시작 조건은 공통 안전 패치 내 xy ±0.05m, yaw ±0.05rad, 관절 q_default±0.02rad, 초기 속도 0의 사전 추출 목록을 제안한다. 모델별로 유리한 시작을 골라내지 않는다. 환경 준비 단계에서 정책과 무관하게 유효 지지·비관통을 검사해 start manifest를 확정한다. 무효 위치를 제외한 수와 이유도 남긴다. 낙하시키는 z+0~0.2m를 기본 안정 보행 비교에 넣지 않고 별도 충격 내성 시험으로 분리한다. 아직 이 시작 분포가 모든 지형에서 유효한지는 **미확인**이다.

### 4.2 표본 계획

| 단계 | 표본·목적 | 통계적 한계·상태 |
|---|---|---|
| 구현 확인 | 알려진 입력·소수 실제 episode. 점수 경쟁용 아님 | 추정. 아래 §5.2 |
| pilot | 14칸 × 기하/준비 조건 5개 × 시작 4개 = 280 episode/checkpoint. flat은 기하 5개로 위장하지 말고 시작 20개 | 추정. 탐색용이며 성능 주장·채택의 확증 표본 아님 |
| 일반 확인 | 가족별 G 20개 기하 × 시작 5개 = 100/cell/checkpoint. 중요 명령·STOP·stones 비교는 20×10=200. H는 고정 기하에 시작 100개로 별도 | 추정. 모든 칸을 처음부터 200으로 예약하지 않음 |
| 학습 변동 | 예비 A/B 한 seed. 결과가 유효하면 같은 부모에서 후속 seed 총 3개를 우선 목표. 확증 셀은 세 seed 모두 같은 세계·시작 목록 사용 | 추정. 세 개는 정밀한 학습 분포 추정에 부족. 부모 사전학습의 독립 재현은 아님 |
| 유보 자료 | pilot/dev geometry와 confirm geometry·시작 목록을 분리. 문턱·checkpoint 선택·시드 추가 결정 후 confirm을 연다 | 추정. 적응적으로 좋아 보이는 칸만 늘린 결과는 탐색으로 표시 |

**추정:** pair_key는 `(contract_hash, physical_profile, cell_id, geometry_hash, start_hash, DR_draw_id, schedule_or_controller_id)`다. 모델 이름·학습 seed는 포함하지 않고 별도 축으로 둔다. 모델별 행 순서나 env index로 zip하지 않는다. 중복·누락·초기 상태 불일치가 있으면 짝 비교를 중단한다. mesh와 초기 상태의 실제 값도 보존하고 반올림 해시만으로 같다고 단정하지 않는다.

### 4.3 집계와 구간

**추정:** 우선 각 동결 checkpoint에 대해 `p = 평균_g(평균_r y[g,r])`를 보고한다. 같은 기하 안의 시작을 독립 지형처럼 세지 않는다. pair의 효과는 `Δ = 평균_g,r(y_new−y_ref)`다. 기하마다 같은 수의 시작이 원칙이며 실패가 많다는 이유로 그 기하의 표본을 줄이지 않는다. 누락이 생기면 사전 고정한 가중치를 유지하고 무효 원인을 해결한다.

**추정:** 동결 checkpoint의 불확실성은 paired cluster bootstrap 10,000회를 제안한다. 기하 g를 복원 추출하고 그 안의 시작 pair를 함께 추출한다. 같은 추출 인덱스를 두 정책에 적용하고 Δ의 2.5·97.5분위수를 낸다. flat·H의 단일 고정 기하는 ‘이 기하에서 시작 분포에 대한 구간’만 낸다. 기하가 5개뿐인 pilot는 개별 기하 성적을 중심으로 보고 구간으로 확증하지 않는다.

**추정:** 세 학습 seed가 같은 G·시작을 공유하면 training seed와 geometry는 교차 요인이다. 각 학습 seed의 Δ·지형별 값·최소/최대값을 먼저 공개하고, 전체 요약은 seed 축과 geometry 축을 **독립적으로 재표집하되 정책 간 짝을 유지**한다. 같은 geometry를 seed별로 완전히 다른 지형처럼 독립 재추출하지 않는다. 동결 v2는 한 모델이며 A/B seed 수만큼 새로운 v2가 생기는 것이 아니다. 전체 CI는 세 seed의 한계가 큰 근사치로 표시한다.

**확인됨:** 교차 요인의 재표집은 각 요인의 수준에 별도 가중치를 주는 접근이며, 이 문제에 일반적인 정확 bootstrap이 존재한다고 가정할 수 없다. [Owen·Eckles, 원문 초록](https://arxiv.org/abs/1106.2125v3). **추정:** 이 근거는 위 구조를 선택하는 이유이지 우리 3 seed CI의 정확한 95% coverage를 보증하지 않는다. 전부 성공·전부 실패여서 bootstrap 폭이 0이 되는 경우도 확실성 100%로 해석하지 말고 표본 부족을 표시한다.

**추정:** 현재 `q_metrics.wilson`, `newcombe_paired`, `mcnemar_exact`는 legacy·독립 pair 조건의 참고 출력으로 보존한다. 지형 내 상관이 있는 200 episode를 그대로 넣은 구간을 공통 비교의 주 CI로 쓰지 않는다. 근거: `Q/q_metrics.py:56,69,90`. 여러 confirm 칸을 훑어 가장 좋은 p-value 하나를 고르지 않는다. 주 비교는 S-gap03·S-stones03, 필수 비퇴행은 C-flat의 저속·횡·후진·STOP으로 사전 등록하고 결과를 각각 보인다. 통합 우월성을 주장할 때는 동시 구간 등 다중 비교 조정을 별도 구현해야 하며 미구현이면 탐색 결론으로 제한한다.

**추정:** 정지 실패의 t_settle을 0으로 채우거나 실패를 제외한 평균만 보고하지 않는다. 전체 N 중 정지 확인 비율과 제한 시간 내 누적 정지 비율, 성공 판의 조건부 거리·시간 분포를 함께 낸다. C/S 실패·추락의 시각도 같은 원칙이다. 기준선 대비 비퇴행을 ‘유의한 하락을 못 찾음’으로 판정하지 않는다. 미리 정한 허용 손실에 대해 효과 구간 하한을 보고, 부족하면 미확인으로 둔다.

**추정:** 의뢰 11에서 재검토한 +10%p·-5%p는 여전히 연구상 제안이다. 실제 앱 STOP·위험선 침범에 5%p 손실을 허용한다는 뜻이 아니다. 확증 표본으로도 제품 안전을 인증하지 않는다. 예상 효과·군집 분산을 재지 않았으므로 100/200 episode가 충분한 검정력을 준다는 주장은 **미확인**이다.

## 5. 최소 구현 순서와 알려진 입력 시험

### 5.1 기존 파일을 어디까지 재사용하는가

| 순서 | 구현 제안 · 아직 만들지 않음 | 재사용·변경 원칙과 산출 관문 |
|---|---|---|
| 1 | `sim/eval/common_contract.py` | 추정: 셀·시계·manifest·pair schema·문턱을 한 곳에 둔다. metric 코드에 상수 중복 금지. checkpoint와 eval 계획을 실행 전에 동결 |
| 2 | `sim/eval/common_metrics.py`와 대응 tests | 추정: Isaac 없는 순수 궤적 함수. Q의 시간 정렬·span·분해, v2의 기존 네 축은 별도 namespace로 보존. 모호한 crossed·support를 그대로 새 성공으로 승격하지 않음 |
| 3 | `sim/eval/common_policy.py` | 추정: V2·CTSStudent·미래 AB adapter. 표의 obs 의미·순서·history·raw action을 native 경로와 대조. 학습 runner를 공통 세계 생성기로 사용하지 않음 |
| 4 | `sim/eval/common_env_cfg.py`와 terrain/start manifest 생성 기능 | 추정: P0, R0, 공통 reset·고정 명령. `generalization_env_cfg`·`rough6_env_cfg`는 기하 원천으로 재사용하고 native 구동기·DR까지 따라오지 않게 분리 |
| 5 | `sim/eval/eval_common.py` + 평가 전용 recorder | 추정: step 시각·명령 일치 검사, terminal pre-reset 저장, episode 단위 파일과 checkpoint 해시. 첫 종료 뒤 상태 차단. 성적 계산 전에 원시 기록 확정 |
| 6 | `sim/eval/post_common.py` | 추정: 공통 schema 검증·짝 매칭·군집 집계·원인 표. q_post처럼 시뮬과 분리하되 원본 episodes.csv를 덮지 않음. contract별 출력 경로 사용 |
| 7 | Linux에서 이식 확인 → pilot → 확증 | 추정: 원래 환경과 새 adapter의 known-input 일치, P0/P1 세 칸 진단 후 확장. 성공 로그만으로 완료 처리하지 않고 실제 궤적·대표 성공/실패 영상과 사건 시각을 대조 |

**추정:** 기존 `eval_generalization.py`, `metrics.py`, `q_eval_cmdr.py`, `q_metrics.py`, `q_post.py`, `unseen_post.py`의 기존 판정을 소급 변경하지 않는다. 공통 기능을 추출할 때도 실행 중 원본 대신 저장소에 고정한 사본·새 모듈에서 작업한다. 절대 경로 `_lab_eval`은 새 runner에서 repository root로 해석하고 source hash를 남긴다. 기존 Q 스크립트를 import하면 top-level 시뮬·파일 쓰기가 실행될 수 있으므로 함수만 필요하다고 그대로 import하지 않는다. 근거: `Q/q_eval_cmdr.py:113,185,301`, `Q/unseen_post.py:37,71`.

### 5.2 알려진 답 시험 목록

| 입력 | 기대 결과 | 상태 |
|---|---|---|
| 12개 관절마다 다른 작은 target·dq. 각 native offset·scale의 역변환으로 raw action fixture 구성 | 두 adapter가 이름 기준으로 지정한 target을 복원하고 다른 관절에 값을 보내지 않음. 동일 raw 벡터가 모델마다 동일 target을 뜻한다고 가정하지 않음 | 추정 |
| 시각·term마다 다른 sentinel 10개 | CTS 이력은 term-major·oldest→newest. 최신 command 87:90, single command 6:9 일치. reset 후 첫 표본 10회 반복 | 추정 |
| 같은 observation을 디버그용으로 두 번 읽기 | history가 두 번 전진하지 않음. policy step 한 번당 한 갱신 | 추정 |
| sensor z=0.4, hit z=0, offset=0.5; hit=inf/NaN | v2 height=-0.1, miss=+1. sensor offset 20이 결과에 더해지지 않음. AB는 hit-validity를 별도 유지 | 추정 |
| heading 90°, world +X 0.3 | WORLD_PATH body command=(0,-0.3). BODY_FIXED는 변환하지 않음. 명령 sampler의 0.2 절삭이 0.1을 지우면 오류 | 추정 |
| 5초에 command 0 전환, 가짜 plant가 한 step 뒤 반응 | 0 명령을 처음 받은 action index=250, 반응 state=251. 시간·속도 오차에 한 프레임 선행/지연이 없음 | 추정 |
| 0.1 명령에 계속 정지 | legacy Q1은 통과할 수 있으나 CE C는 상대 MAE·진행으로 실패 | 추정 |
| 0.3 명령을 정확히 따르며 직선 이동 | C 추종·진행·방향 통과. 0 명령 횡축에 0.14 이동을 추가하면 CE 실패 | 추정 |
| 몸을 돌며 local vx만 맞추고 원점으로 복귀 | body MAE만 양호해도 signed world progress·corridor에서 실패 | 추정 |
| yaw가 +π에서 -π로 넘어가는 정상 회전 | unwrap 후 회전량 정상. 반대 방향 회전은 signed ratio 실패 | 추정 |
| 50Hz 50개 정지 표본과 51개 정지 표본 | 50개는 0.98초 span이라 CE 1초 유지 실패, 51개는 1초로 통과. 경계 값의 <·≤ 규칙 일관 | 추정 |
| STOP 후 0.35m 이동했다 원점으로 돌아옴 | net≈0이어도 D_max에서 실패 | 추정 |
| STOP 0.4초 후 멈추고 1.2초 유지한 뒤 다시 이동 | 첫 t_settle은 남기되 sustained stop 실패 | 추정 |
| 종료 직전 gate 통과 후 같은 step에서 base 충돌·reset | terminal pre-reset 상태와 실패 보존. reset된 upright 상태로 생존·도착 성공이 되지 않음 | 추정 |
| physics 네 substep 중 첫 번째에만 접촉 >1N | 접촉 사건을 놓치지 않음. 마지막 세 표본만 읽는 구현이면 실패해야 함 | 추정 |
| base만 출구 통과, 뒷발은 틈 전 | legacy crossed는 가능하나 CE crossed=false | 추정 |
| 장애물 옆으로 나가 출구 도달 | S avoidance=true, S pass=false. O는 등록된 우회 정책에 따라 별도 판정 | 추정 |
| pit 바닥의 정상 보행·gap의 모든 ray miss | pit를 상부 지면보다 낮다는 이유로 추락 처리하지 않음. 모두 miss를 평균 NaN으로 만든 뒤 생존으로 통과시키지 않음 | 추정 |
| 같은 seed·다른 생성 순서, 또는 같은 기하·다른 seed | mesh 불일치면 짝 거부. 동일 hash면 독립 지형 수를 늘리지 않음 | 추정 |
| pair 행 순서 뒤섞기·중복·누락 | 명시적 key로 결과 불변. 중복·누락은 오류와 수를 남김 | 추정 |
| 한 기하의 시작 수만 복제 | 기하 동일 가중 평균이 바뀌지 않음. 중복 episode_id는 거부. 표본 복제로 CI가 부당하게 좁아지지 않음 | 추정 |
| A/B가 모든 pair에서 동일 | Δ=0. 지형별·seed별 표도 동일. ‘차이 없음’과 검정력 충분을 동일시하지 않음 | 추정 |

**미확인:** 위 시험들은 설계한 관문이지 이번에 실행한 시험 결과가 아니다. 유효 입력·정확한 오차 허용값·GPU 비결정성 허용 범위는 구현 단계에서 원래 추론 경로를 기준으로 정해야 한다. 정책 입력/출력의 같은 FP32 CPU 계산은 우선 최대 절대차 1e-6을 목표로 삼되, GPU·Linux 차이에 그 값을 무근거하게 강제하지 않는다. 관측 순서·명령 시각·joint 이름은 수치 오차로 넘어갈 수 없는 계약이다.

## 6. 의뢰 11의 내 제안을 이번에 수정하는 부분

| 이전 제안의 빈틈 | 이번 정정 | 상태 |
|---|---|---|
| ‘같은 물리’와 고유 action 변환 보존의 경계를 구체화하지 않음 | action decode는 보존하되 actuator·PD·지연은 공통 물리로 동결한다. native 물리는 별도 이식 진단으로 격리 | 추정. 위 §1의 실제 차이로 보완 |
| 5 지형 seed×20 시작을 제시 | seed가 다른데 같은 기하일 수 있고 군집 5개도 부족하다. pilot 5×4, 확인 20×5, 핵심 20×10. 결정론적 기하는 명시적 치수 변화 또는 고정 기하 조건부 결과로 처리 | 추정 |
| STOP 시간·거리만 나열 | command 수신 시계·span·최대 이탈·잔류 재이동·footprint 위험선까지 명세 | 추정 |
| v2·CMD-R을 같은 조건으로 재자고만 제안 | native 관측 packing과 구동기 차이 때문에 별도 adapter 검증이 선행돼야 함. 이식 실패를 새 구조의 열등함으로 판정하지 않음 | 추정 |

**추정:** lead가 먼저 구현할 것은 새 학습 cfg가 아니라 **입력·출력 adapter의 native 일치 시험, CE 시간·판정 fixture, 공통 P0 manifest와 terminal recorder**다. 이 네 가지가 통과한 뒤에야 모델별 점수 비교가 의미를 갖는다. 실행 전까지 ‘평가 계약이 같아졌다’가 아니라 ‘같게 만들 설계를 작성했다’가 정확한 상태다.

## 부록 · 저장소 밖 파일의 읽은 판

**확인됨:** 아래 SHA-256은 2026-10-13 로컬 파일에서 읽었다. 실행·평가 결과의 해시가 아니다. 다른 세션이 파일을 바꾸면 같은 행 번호라도 다시 확인해야 한다.

| 파일 | SHA-256 |
|---|---|
| `Q/q_eval_cmdr.py` | `24AEAF6358EF79096911E3DCB220212AC715775012DA96BF14E438C331DBA4BC` |
| `Q/q_metrics.py` | `C9930F8D327EFD04DF51440DA519FEFAB2585490AE45B4A6FFBD39466138A794` |
| `Q/q_post.py` | `F90AAA97A50C5347111298B913D7BB948E58F0D1CE3AF09808739CFCAE1E26DD` |
| `Q/unseen_post.py` | `880CA17C469C3FF79A66AFC631F49DB420FD7C3CC71FF240EC096E960A41975E` |
