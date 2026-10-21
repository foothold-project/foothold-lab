> 분류: A/정책학습 · 설계 (10 보행층 · Go2 로봇 모델과 무작위화)
> 작성: 오흥재 (lead 세션 초안 · fable 20f 가 v1 으로 고쳐 씀)
> 근거: Go2 URDF `C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf` 6 · 63 · 84 · 89 · 101 · 122 · 139 · 160 · 205 · 251 · 289 · 327 · 418 · 456 · 494 행 · Isaac Lab 2.3.2 `isaaclab_assets/robots/unitree.py` 140~180 · `actuators/actuator_pd.py` 295~307 · `config/go2/rough_env_cfg.py` 30~35 · `sensors/contact_sensor/contact_sensor_cfg.py` 45 · PIE 2408.13740v3 Table II (ASTRA 19g 4 절, root.tex 182~203) · START 2512.13153v1 221 · 580 행 · JEPLO `go2_loco_env.py` 835~847 (evidence/maicode-jeplo-deep) · MARG 2509.20036v2 647 행 · DECISIONS-step2-lead.md A3 · A4 · APPROVED F-D1 · F-D2 · H(팀장 승인 10/19) · fable 20e 2 절 · VERIFY-fable-20f P9 · P22 · VERIFY-astra-r1 §3~§6(20t · fable 재측: 공식 USD sha256 · usd-core 질량 합 · FK · 카메라 기하)
> 요지: 시뮬 Go2 가 실기보다 「빠르거나 세지」 않게 종아리 관절만 URDF 값(속도 15.70 rad/s · 토크 45.43 N·m)으로 떼어 DCMotor 로 두고, 나머지는 Isaac Lab Go2 설정을 그대로 쓴다(팀장 승인). 무작위화는 START 가 위임한 PIE 표를 쓴다(짐 무게 −1~2 kg, 팀장 승인). 실측이 오면 실측이 이긴다
> 상태: v1 · 팀장 검토 전 · 수치는 출처 등급(논문 · 선행 · 코드 · URDF · 실측 · 가정) · 20k ASTRA 마지막 검증(VERIFY-astra-final) 계약 반영 · **20m 승인 차이 넷 반영(fable 10/20)** · **20s lead 답 8 항 반영(fable 10/20)** · **20t ASTRA-R1 셋 반영(fable 10/20)** · 10/21 S1a-Rx1 종료·클립 이력 추가 · 평가 연결 미확인

# 17 · Go2 로봇 모델

## 0. 쉬운 요약

시뮬레이션 속 로봇이 진짜 로봇보다 힘이 세거나 빠르면, 시뮬에서만 되는 걸음을 배운다. Go2 의 설계도(URDF)를 보니 무릎(종아리) 관절은 다른 관절보다 **두 배 느리고 두 배 센** 모터다(감속비가 다르다). 그런데 Isaac Lab 의 기본 Go2 모델은 12 관절을 전부 같은 모터로 둔다. 그래서 종아리만 따로 떼어 설계도 값으로 고정한다. 짐 무게 · 마찰 · 모터 세기 같은 것은 학습 때 일부러 흔들어서(무작위화) 로봇이 어떤 상황에도 적응하게 하는데, 그 범위는 START 가 따른 PIE 논문의 표를 쓴다. 진짜 Go2 가 오면 첫 주에 이 값들을 재서 덮어쓴다.

## 1. 관절 한계 (URDF 와 Isaac Lab 의 차이)

| 관절 | URDF 범위 (rad) | URDF 토크 (N·m) | URDF 속도 (rad/s) | Isaac Lab Go2 (DCMotor, 12 관절 공통) | 출처 |
|---|---|---|---|---|---|
| hip (×4) | −1.0472 ~ 1.0472 | 23.7 | 30.1 | 토크 23.5 · 포화 23.5 · 속도 30.0 · Kp 25 · Kd 0.5 | **URDF** 84 · 251 · 418 행 · **코드** `unitree.py` 170~177 |
| thigh 앞 | −1.5708 ~ 3.4907 | 23.7 | 30.1 | 같음 | **URDF** 122 · 289 |
| thigh 뒤 | −0.5236 ~ 4.5379 | 23.7 | 30.1 | 같음 | **URDF** 456 |
| calf (×4) | −2.7227 ~ −0.83776 | **45.43** | **15.70** | **같음 (23.5 · 30.0)** | **URDF** 160 · 327 · 494 |

**무엇이 문제인가.** 종아리는 같은 모터에 감속이 약 1.92 배 더 걸려 있다(45.43 / 23.7 = 1.92, 30.1 / 15.70 = 1.92, URDF 값으로 계산). Isaac Lab 모델은 종아리를 허벅지와 같은 모터로 다뤄서, 시뮬 종아리는 실기보다 **토크는 절반 · 속도는 두 배**다. 정책이 시뮬에서 「빠른 종아리 스윙」 을 배우면 실기 모터는 그 속도를 못 낸다(fable 20e 2 절).

**동결값 (팀장 승인 10/19 · APPROVED F-D2).** 종아리 actuator 를 따로 묶고 값은 **URDF 그대로** 쓴다. 초안의 환산값 15.6 · 45.1 은 쓰지 않는다(VERIFY 20f P9).

| 묶음 | 토크 (effort · saturation) | 속도 한계 | Kp · Kd | 등급 |
|---|---|---|---|---|
| hip · thigh | 23.5 · 23.5 | 30.0 | 25 · 0.5 | **코드** Isaac Lab 그대로 |
| calf | **45.43 · 45.43** | **15.70**(모터 곡선 인자 `velocity_limit`. PhysX 상한 `velocity_limit_sim` 은 **적용하지 않음**, 아래 동결값) | 25 · 0.5 (관절 공간 PD 는 그대로) | **URDF** 160 행 · 팀장 승인 · 동결값은 **가정**(20k) |

DCMotor 의 뜻(**코드** `actuator_pd.py` `_clip_effort` 295~308 행, ASTRA 가 CPU 에서 그대로 실행해 확인 · VERIFY-astra-final 3): 토크는 절댓값 대칭이 아니라 **추진 · 제동 비대칭**이다. 상한 = min(effort_limit, saturation × (1 − q̇ / velocity_limit)), 하한 = max(−effort_limit, saturation × (−1 − q̇ / velocity_limit)). 종아리(45.43 · 45.43 · 15.70)에서 +100 N·m 를 요청하면 q̇ = 0 → +45.43, 7.85 → +22.72, 15.70 → 0, 20.00 → **−12.44**(강제 제동) 이고, −100 N·m 를 요청하면 같은 속도들에서 전부 **−45.43**(제동은 속도와 무관하게 끝까지 가능). 즉 「15.70 에서 토크 0」 은 추진 방향만의 이야기다. 이것이 실제 모터의 토크 · 속도 선에 가장 가깝다. `velocity_limit` 은 이 곡선의 인자이고 PhysX 관절 최대 속도 `velocity_limit_sim` 과는 별개다(`actuator_base.py` 182~210 행: `velocity_limit_sim` 은 USD 값과 대조해 PhysX 에 쓰고, `velocity_limit` 은 따로 파싱). **동결값(가정)**: 종아리 `velocity_limit = 15.70`, `velocity_limit_sim` 은 USD 값 그대로(적용 안 함). 이유: 곡선이 15.70 을 넘는 속도에서 추진 토크를 음수로 만들어 물리적으로 제동하므로 solver 상한을 따로 두지 않고, 넘는 비율은 H17-2(≤ 1 %)로 본다. 실측(6 절 T2)이 오면 재검토. 실측(6 절 T2)이 오면 실측이 이긴다(APPROVED C). 지속 토크를 23.5 로 따로 자르는 변형(effort_limit 23.5)은 실측 뒤 재검토 항목이다(10 절).

## 2. 질량과 크기

**학습 자산은 하나다(ASTRA R1-1 · 20t).** S1-a 가 로드하는 로봇은 sonnet-code `tasks/s1_env_cfg.py` 56 행 → `robots/go2_cfg.py` 11 행 `UNITREE_GO2_CFG.replace(actuators=…)`(spawn 은 그대로) → 설치 Isaac Lab 2.3.2 `unitree.py` 142 행이 가리키는 **공식 Go2 USD** 이고, 10/20 16:59(scan · GPU 0) · 17:00(blind · GPU 1) 두 본 학습 판의 `params/env.yaml` 286 행에 같은 경로가 기록돼 있다(**코드 · 실행 기록**, fable 20t). 아래 표의 질량 · 기하는 이 자산에서 읽은 값이고 URDF 값은 비교 열이다. **16.087 · 16.142(URDF) 와 15.019(USD) 를 섞어 쓰지 않는다.**

| 항목 | 학습 자산(공식 Go2 USD) | 비교: Go2 URDF | 출처 |
|---|---|---|---|
| 경로 | `https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/IsaacLab/Robots/Unitree/Go2/go2.usd`(+ 상대 참조 `Props/instanceable_meshes.usd`) | robotlab `C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf`(JEPLO `training/resources/go2/urdf/go2.urdf` 와 **바이트 동일**) · MGDP `all_dog/go2/urdf/go2.urdf` | **코드** `unitree.py` 142 · `apps/isaaclab.python.kit` 306(asset_root cloud = Assets/Isaac/5.1) · **실행 기록** env.yaml 286 행 |
| sha256 | go2.usd 8,142 B `ba171c97…11c6d` · instanceable_meshes.usd 18,802,187 B `2902646d…93fb5` | robotlab = JEPLO `f130b1d2…a5810` · MGDP `2b64012c…7559` | ASTRA R1 §8 · **fable 재측 10/20**(내려받아 sha256 · 전부 일치) |
| 총질량 | **15.019 kg**(`physics:mass` 19 prim 합 15.018999692: base 6.921 · 다리마다 hip 0.678 + thigh 1.152 + calf 0.154 + foot 0.040 = 2.024 · Head_upper · Head_lower 0.001 씩) | robotlab = JEPLO **16.087**(33 링크 · 회전자 12 × 0.089 = 1.068 포함 · 카메라 없음) · MGDP **16.142**(+ D435 0.055) | USD 는 usd-core 26.8 로 fable 재측(ASTRA R1 §4 와 같음) · URDF 는 XML 합산 fable 재측. **차이 1.068 kg 은 URDF 의 회전자 링크가 USD 에 없기 때문**이고 USD 에 더하지 않는다(ASTRA R1-1). 공식 사양 약 15 kg(fable 20e [5]) |
| 로드 뒤 질량 | **미확인**(Kit 로그에 질량 출력 없음 · 평가 시작 · S2 첫 실행 로그에 `root_physx_view` 질량 합 출력 예정 · D55). cfg 의 `mass_props` 는 null(env.yaml 252 행)이라 USD 값이 그대로 PhysX 에 들어간다고 본다(**가정**). 학습 중 base 에 짐 −1~2 kg 이 더해진다(5 절) | | 실행 기록 · 가정 |
| 실기 질량 | **미확인** → 저울(6 절). START 자산(MGDP Lite3)과의 동일성도 미확인(ASTRA R1 §1) | | |
| 허벅지 · 종아리 길이 | 0.213 · 0.213 m(`FL_thigh/FL_calf_joint` · `FL_calf/FL_foot_joint` localPos0 z) | 같음 | USD · URDF 일치(ASTRA R1 §4 · fable 재측) |
| 앞뒤 hip 축 간격 | 0.3868 m(`base/FL_hip_joint` localPos0 x 0.1934 × 2) | 같음. Lite3 0.349 | USD · URDF · Lite3 는 MGDP `lite3.urdf` 95 · 203 행 |
| hip = 0 의 좌우 thigh 축 간격(옛 이름 「좌우 발 간격」 은 틀린 이름 · 20t) | 0.284 m = 2 × (0.0465 + 0.0955) | 같음. **Lite3 0.321** = 2 × (0.062 + 0.0985)(`lite3.urdf` 95 · 135 행. 옛 0.319 는 이 파일에서 안 나옴) | ASTRA R1 §3 · fable 재측 |
| 기본 자세(3 절)의 발 구 중심 좌우 간격 · 바닥 접촉 base 높이 | 간격 앞 0.345 · 뒤 0.344 m, 높이 앞 0.3235 · 뒤 0.3139 m(hip ±0.1 · thigh 0.8 / 1.0 · calf −1.5 · roll · pitch 0 · 발 구 반지름 0.022 · 중심 x −0.002). **정적 평형 높이가 아니고, 스폰 z 0.4 도 서 있는 높이가 아니다.** 11 §7 기하 시험은 base z 0.33 을 따로 고정한다 | hip 0 이면 간격 0.284 · 높이 앞 0.3346 · 뒤 0.3250 | FK 계산(ASTRA R1 §4 · fable 재측 `fk20t.py`) |
| 발 충돌 구 | 반지름 0.022 m(지름 0.044). Lite3 0.040(지름 0.080) | 같음 | USD `FL_foot/collisions/mesh_0` · URDF |
| 몸통 충돌 상자 | 0.3762 × 0.0935 × 0.114 m | 같음 | USD `base/collisions/mesh_0` scale |
| 센서 추가 질량 | D435i · 장착대 | | **미확인** → 실측 |

## 3. 행동과 제어

| 항목 | 값 | 출처 |
|---|---|---|
| 행동 | 관절 목표 = 기본 자세 + 0.25 × a | **코드** `rough_env_cfg.py` 30 |
| 정책 주기 | 50 Hz (물리 200 Hz × decimation 4) | **코드** `velocity_env_cfg.py` 308 · 311 (training-benchmarks.md 45~52 행) · START 실기 50 Hz (**논문** 528 행) |
| PD | Kp 25 · Kd 0.5 | **코드** `unitree.py` 175~176 |
| 기본 자세 | hip ±0.1 · 앞 thigh 0.8 · 뒤 thigh 1.0 · calf −1.5, 높이 0.4 m 스폰(**스폰 z 0.4 는 서 있는 높이가 아니다**. 이 자세의 바닥 접촉 base 높이 0.3139~0.3235 m 는 2 절 · 11 §7 기하 시험은 base z 0.33 고정 · 20t) | **코드** `unitree.py` 157~167 |

## 4. 발 접촉 정의

- 시뮬: 발 링크(`*_foot`) 접촉 센서 힘 > 1 N 을 접촉으로 본다 → **가정** (START 미기재. Isaac Lab `ContactSensorCfg.force_threshold` 기본 1.0, `contact_sensor_cfg.py` 45 행).
- 실기: Go2 EDU 발 힘 센서 값(SDK `foot_force`). 시뮬 1 N 과 같은 문턱이 맞는지 실측해야 한다(fable 20e 2 절 「지연 · 잡음 미확인」).
- 걸려 넘어짐 항(16 문서 13 항)도 같은 센서를 쓴다.

## 5. 도메인 무작위화 (START → PIE 위임)

START 는 「DR 은 [31] 을 따른다」 고만 쓴다(**논문** 221 행). [31] 은 PIE(Luo 외, 같은 연구실, **논문** 580 행). PIE Table II 값(ASTRA 19g 4 절, root.tex 182~203):

| 항목 | PIE 값 | Go2 적용 | 등급 |
|---|---|---|---|
| 짐 무게 | −1 ~ 2 kg | 그대로. **기준 질량(20t · ASTRA R1 §4)**: 절대 추가 질량이고 base 에 add 한다(**코드** sonnet `tasks/s1_env_cfg.py` 128~131 · **실행 기록** env.yaml `add_base_mass` base · add · (−1, 2) · startup). 기준은 **학습 자산 공식 USD 총질량 15.019 kg**(2 절) → 학습 중 총질량 14.019~17.019 kg(−6.66~+13.32 %). URDF 16.087 기준이면 −6.22~+12.43 %, MGDP Lite3 9.038 kg 기준의 −11.06~+22.13 % 와 같은 상대 교란이 아니다(기록 · 승인값 유지). (**팀장 승인 10/19**, APPROVED F-D1. 이전 ±1.6 kg 은 AME-2 본선일 때의 환산이라 버림. Lite3 질량 대비 비율 재환산은 Lite3 질량을 원문으로 확인한 뒤에만) | **논문(위임)** |
| Kp · Kd · 모터 세기 배율 | 0.9 ~ 1.1 | 그대로. Kp · Kd 는 `randomize_actuator_gains`(scale · uniform, startup). 모터 세기 배율은 이득 무작위화와 같은 startup event 로 **구현 예정**(lead 승인 10/20 · 20m, 코드 71d6eac2 에는 없음) | **논문(위임)** |
| 무게중심 이동 | ±50 mm | 그대로 | **논문(위임)** |
| 마찰 | 0.2 ~ 1.2 | 그대로 | **논문(위임)** |
| 초기 관절 | 0.5 ~ 1.5 (표 단위 rad) | 단위 해석 열린 항목 (ASTRA 19g 「factor 로 임의 정정 금지」). 1 차는 Isaac Lab Go2 기본 `reset_robot_joints` position_range (1.0, 1.0) 유지 → **가정** | **논문(위임)** |
| 시스템 지연 | 0 ~ 15 ms | 그대로. 구현은 **행동 지연 버퍼**(제어 스텝 20 ms 안의 물리 하위 스텝 0~3 개 = 0~15 ms 동안 직전 관절 목표를 유지, env 마다 reset 때 뽑음 · lead 승인 10/20 · 20m, 코드 71d6eac2 에는 없음) | **논문(위임)** |
| 카메라 위치 x · y · z | 각 ±10 mm | 그대로 | **논문(위임)** |
| 카메라 pitch | ±1° | 그대로 (공칭 pitch 는 11 문서) | **논문(위임)** |
| 수평 FOV | 86 ~ 88° | 그대로 | **논문(위임)** |

참고: Isaac Lab Go2 기본은 짐 (−1, 3) kg · base_com 없음 · push 없음(`rough_env_cfg.py` 33~35 · 49). 우리는 PIE 표를 우선한다.

## 6. 실측으로 덮을 것 (Go2 도착 첫 주 · 42 문서)

| 항목 | 방법 | 쓰는 곳 |
|---|---|---|
| 관절별 최고 속도 · 토크 | 다리를 들어 올린 상태에서 계단 명령 · 정현파 위치 명령, SDK 로 q̇ · τ 기록 | 1 절 actuator |
| PD 응답 · 지연 | 같은 기록에서 명령 대 실제 위상차 | DR 지연 범위 |
| 발 힘 센서 문턱 · 잡음 | 서 있기 · 한 발 들기 | 4 절 |
| 전체 질량 · 센서 장착 질량 | 저울 | 2 절 · DR |
| D435i 장착 위치 · pitch | 줄자 · 경사계, 체커보드 | 11 문서 · 5 절 |
| Orin NX 추론 시간 | 지각망 + 정책 ONNX/TensorRT 50 Hz 루프 | 13 문서 수출 · 42 T7 (APPROVED H) |

## 7. 종료 조건 (논문 미기재 · 가정)

START 는 「미리 정한 각도 한계를 넘는 뒤집힘 · 발 높이가 지면 아래 문턱 밑」 만 적는다(**논문** 221 행, 숫자 없음 · deep-research). 1 차 **가정**: 투영 중력과 z 축 사이 각 > 1.5 rad(Isaac Lab `bad_orientation(limit_angle=1.5)`, **코드** sonnet `tasks/s1_env_cfg.py` 152~153 · 설치 `terminations.py` 51~57 행 · 20m #5 · lead 20s 「코드대로」. JEPLO `go2_loco_env.py` 835~847 의 roll · pitch 각각 1.5 와는 기하가 다름: roll 1.2 · pitch 1.2 는 JEPLO 식으로 생존, 우리 식으로 종료) 또는 발 높이 < 지면 −0.2 m(**논문** MARG 2509.20036v2 647 행의 −0.2 m 를 참고). 몸통 접촉 종료는 두지 않는다(fable 20a S-10, Rudin 기본과 다름 · 기록).

### S1a-Rx1의 종료 여유와 행동 클립 · 10/21 이력

**코드 · 진단 실측, S2 자동 상속 아님**: 위 −0.2 m는 최초 설계의 참고값이다. 회복 판 S1a-Rx1(과거 실행 이름 `S1a-v1.1`)의 S1 cfg에서 `foot_below_ground`는 `go2_params.TERMINATION["foot_below_ground_m"]`을 받아 0.25 m를 썼다(`tasks/s1_env_cfg.py` 160~165 · `robots/go2_params.py` 32). `tasks/mdp_extra.py` 14~29는 발 중심이 가장 가까운 유효 높이 스캔 점의 지면 z보다 여유치만큼 아래일 때 종료하며, 유효점이 0.15 m 밖이면 그 발을 제외한다. 물리 바닥을 낮춘 변경이 아니다. 별개 1024 env · 20 s 진단에서 이전 0.2 m 조건은 레벨 9의 계단과 역계단에서 26 + 30 = 56건, 0.25 m 조건은 0건이었다. 서로 다른 실행이라 짝 대조와 전체 지형의 종료 성적은 미확인이다. 16 §2의 발 가장자리 보상 마스크 낙하 높이 0.2 m는 독립된 기준이다.

**코드 · 진단 실측**: S1 PPO cfg의 `clip_actions=17.0`은 학습과 현재 S1 평가의 `RslRlVecEnvWrapper`가 `env.step` 직전에 행동 원소를 [−17, 17]로 자르는 값이다. 잘린 값이 `action`·`prev_action`, `last_action` 관측과 `action_rate_l2`에 이어진다. 각도 17 rad나 토크 17 N·m의 한계가 아니다. 정상 보행 진단의 원소별 `|action|` p99.9는 기준 10.79766과 D2 6.52201이고, `ceil(max × 1.5)=17`로 정했다. 단기 클립 진단으로 장시간 안정성은 증명되지 않았다. Rx1은 14:38에 중단됐다. 평가기가 Rx1 체크포인트에 같은 cfg를 적용했는지, 전체 관문을 통과했는지는 미확인이다. 현재 S2-G0에는 Rx1 종료 여유와 클립을 처방이라는 이유만으로 상속하지 않는다. 근거: [밤 기록 §진단](NIGHT-REPORT-1021.md) · [#555 처방](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304758796) · [Rx1 카드](../20261021-experiments/EXP-S1a-Rx1.md) · `0259d4d0`의 17 §7.

## 8. 장면 예

| 장면 | 모델이 하는 일 |
|---|---|
| 계단을 오르며 종아리를 12 rad/s 로 휘두르려 한다 | 시뮬 종아리 토크가 45.43 × (1 − 12/15.70) ≈ 10.7 N·m 로 줄어 그 걸음이 안 나온다. 실기에서도 안 나올 걸음을 시뮬이 미리 막는다 |
| 2 kg 짐을 얹었다 | DR 범위 안이라 정책이 이미 겪었다. 3 kg 은 범위 밖(기록) |
| 몸이 1.5 rad 넘게 기울었다 | 종료 · 리셋. 벌점은 없다(가정) |

## 9. 구현 방법 · 검증 사다리

- 자리: `foothold_s2/robots/go2_cfg.py`. `UNITREE_GO2_CFG` 를 복제해(spawn `usd_path` 는 바꾸지 않는다 · 2 절 자산) `actuators` 를 `hip_thigh`(`.*_hip_joint`, `.*_thigh_joint`) · `calf`(`.*_calf_joint`) 두 `DCMotorCfg` 로 나눈다. DR 은 `EventCfg` 의 `randomize_rigid_body_material`(마찰) · `randomize_rigid_body_mass`(짐) · `randomize_actuator_gains`(Kp · Kd) · 무게중심 이동 · 카메라 자세(센서 오프셋) term. 시스템 지연은 행동 지연 버퍼 term(`tasks/delayed_action.py`), 모터 세기 배율은 이득 무작위화와 같은 startup event(둘 다 구현 예정 · 20m).
- L0 CPU: 설치 `DCMotor._clip_effort` 를 CPU 더미 상태로 그대로 실행해 ASTRA 표와 대조: +100 요청 → q̇ 0 · 7.85 · 15.70 · 20.00 에서 +45.430 · +22.715 · 0 · −12.443, −100 요청 → 네 속도 모두 −45.430. negative control: `velocity_limit` 을 30 으로 두면 15.70 에서 +21.66(= 45.43 × (1 − 15.70 / 30) = 21.655 · 20m #6 정정)이 나와야 함. AST 로 cfg 의 joint 정규식이 URDF 관절 이름 12 개를 정확히 둘로 나누는지(가짜 cfg 금지, 실제 USD 관절 이름으로).
- L1 Kit: 첫 10 update 에서 종아리 q̇ 히스토그램 로그. DCMotor 는 토크를 줄일 뿐 속도를 막지 않으므로(`actuator_pd.py` 299~302 행) 15.70 을 넘는 스텝이 정상 판에서도 나올 수 있다. 기준은 「15.70 초과 비율 ≤ 1 %」(**가정**, VERIFY-lead-final 23).

## 10. 검증할 가설 · 열린 항목

| # | 가설 | 어떻게 보나 |
|---|---|---|
| H17-1 | 종아리 속도 15.70 rad/s 제한이 계단 · 틈 학습을 막지 않는다 | 제한 판과 기본 판의 짧은 학습 대조(2,000 회) |
| H17-2 | 시뮬 종아리 속도가 15.70 rad/s 를 넘는 스텝 비율이 1 % 이하다(DCMotor 는 속도를 자르지 않으므로 0 이 아니라 비율로) | 학습된 정책의 q̇ 히스토그램 · 42 T2 |

열린 항목: PIE 「초기 관절 0.5 ~ 1.5」 의 단위 · 종료 조건 숫자(가정 유지) · 지속 토크 23.5 변형의 실측 뒤 재검토 · 센서 질량 · Kit 로드 뒤 질량 값(lead 20t 답 · D55: sonnet 사슬의 평가 시작 · S2 첫 실행 로그에 env robot `root_physx_view` 질량 합 한 줄 출력, lead 가 sonnet 에 지시) · 실기 질량과 START 자산 동일성(미확인).
