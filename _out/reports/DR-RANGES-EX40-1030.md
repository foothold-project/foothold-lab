> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: analyst · 2026-10-30
> 근거: WORKLIST D73·D74(e18ae14c) · EX-39B 실행 YAML · 설치 Isaac Lab · PIE/START/HIM/DreamWaQ 원문 · W51 원자료
> 요지: 마찰·질량·관측 잡음은 유지하고 다섯 DR의 소비 의미·범위·일정을 고정하며, 같은 조건의 GPU1 비교로 영향과 한계를 확인한다
> 상태: v0.1 진행 중 · 범위 원문 대조 확인됨 · GPU1 비교 12건 진행 중 · 결과와 문서 정합 대조는 아래에 추가

# EX-40 DR 전체 범위와 W51 추가 비교

**권고: 관측 잡음의 최종 크기는 현재 값으로 유지한다. 밀기는 수평 속도 변화량 각 축 ±0.5 m/s, 에피소드 안 10~15초 간격을 D 단계 제안값으로 둔다.** 이는 실기 성공이 보장된 값이 아니라 선행 코드에서 가져온 우리 가정이다. 아래 측정은 기존 정책의 단기 내성 시험이며 EX-40의 학습 성공 증거가 아니다.

## 1. 범위와 실제로 바뀌는 것

짧은 경로의 뿌리: `E = C:/mai/wt/foothold-lab/analyst-dr-w51`(평가 전용 907fe1ed), `I = C:/isaac/IsaacLab/source/isaaclab/isaaclab`, `Y = C:/Users/AI-WS01/s2_lab/basic_gait_runs/main/EX-39B-basic-heading_20261030_005644_48924/params/env.yaml`. 등급 `논문`과 `코드`는 실기에서 잰 값이라는 뜻이 아니다.

| 항목 | m0 / B3c 끝 / D 전체 범위 | 실제 소비와 단위 | 근거·판단 |
|---|---|---|---|
| 마찰 | 처음부터 정적·동적 각각 U(0.2,1.2), 그대로 | 몸 링크 재질에 적용, 두 값의 combine 방식도 보존 | 코드·채택: Y physics_material, E/foothold_s2/eval/actuator_variants.py:233. 이미 켠 항목을 새 여섯 항목의 효과로 세지 않음 |
| 몸 추가 질량 | 처음부터 U(−1,+3) kg, 그대로 | base 링크 질량에 더함. 총질량 1~3 kg라는 뜻 아님 | 코드·채택: Y add_base_mass, D63·74. PIE의 −1~2 kg와 다름 |
| COM | 0 / 각 축 ±0.025 m / 각 축 ±0.05 m | base COM의 x,y,z 이동. ±5 cm 구면 반경이 아닌 정육면체 표본 | 논문: [PIE Table II](https://arxiv.org/html/2408.13740v3#S3.T2), 코드: E/foothold_s2/tasks/s1_env_cfg.py:132. 3축 끝점 길이 8.66 cm는 계산. Go2 실제 오차 실측 없음. 특히 수직 ±5 cm는 넓은 강건성 시험 |
| PD 이득 | 1 / 0.95~1.05 / 0.9~1.1 배 | 명목 Kp=25, Kd=0.5를 각각 곱함. D에서 Kp22.5~27.5, Kd0.45~0.55 | PIE Table II, E/foothold_s2/tasks/s1_env_cfg.py:136 및 robots/go2_params.py. 제조 오차의 측정치는 아님 |
| 모터 세기 | 1 / 0.95~1.05 / 0.9~1.1 배 | 현재 구현은 PD 명령 토크 전체를 곱하는 방식이 아니라 DCMotor effort_limit와 saturation_effort를 함께 조절 | PIE 계수 차용, 구현: E/foothold_s2/tasks/mdp_extra.py:32~51. 명목 한계 아래에서 작동하면 변화가 작을 수 있음 |
| 행동 지연 | 0 / 설정 상한7.5 ms / 설정 상한15 ms | 이전 action target을 physics substep 동안 유지. 제어20 ms·물리5 ms에서 D 표본0/5/10/15 ms | 논문 PIE Table II, 코드 E/foothold_s2/tasks/delayed_action.py. 센서 지연·통신 누락·상위 명령 지연 전체를 뜻하지 않음 |
| 밀기 | 0 / Δvx,Δvy 각 ±0.25 m/s / 각 ±0.5 m/s | world XY 속도에 순간 변화량을 더함. z·각속도 유지. 간격10~15 s는 강도와 별도 | 제안·가정: Isaac Lab 공통 velocity_env_cfg.py:222~226. Go2 rough는 push=None(:33)이므로 ‘Go2 기본 활성값’이라고 부르면 틀림. 원문 근거 비교는 §3 |
| 관측 잡음 | **m0부터 끝까지 현재1.0배 고정** | 각 관측 계산 때 U(−a,+a) 가산. 명령·이전 action에는 잡음 없음 | Y:951~1029, §2. 최종2배를 기본값으로 올릴 근거 없음. W51 noise2는 스트레스 진단만 |

D74 및 lead22:0x 정정: 관측 잡음은 처음부터1배 고정한다. B0는 COM·gain·strength·delay·push 다섯 항목 배율0, B1~B3c에 0→0.5, D=m6001~7500, T0=m7501~8000, 총8001갱신. D의 0.5→1.0 확대 형태와 끝값 도달 시점은 실행카드에 수식으로 고정해야 한다. D 시작에 갑자기1로 바꾸는지 선형으로 올리는지는 D74의 ‘D에서 전체’만으로 확정되지 않는다. 제안은 D 앞1000갱신 동안0.5→1, 끝500갱신1 유지이며 **가정·확인 필요**다.

### 1.1 범위표만 바꾸면 생기는 구현 결함

1. `randomize_motor_strength`는 현재 모든 env를 곱하고 `env_ids`를 쓰지 않는다(E/foothold_s2/tasks/mdp_extra.py:38~50). reset 이벤트로 이름만 바꾸면 다른 env까지 바뀌고 곱셈이 누적된다. `명목 한계 × 이번 배율`을 reset 대상에만 대입해야 한다.
2. 설치 `randomize_rigid_body_com`도 현재 COM에 `+= rand_samples`를 한다(I/envs/mdp/events.py:400~435). reset마다 그대로 쓰면 COM이 랜덤워크한다. 최초 명목 COM을 보존해 `명목+이번 offset`으로 대상 env에만 대입해야 한다.
3. 지연7.5 ms는 물리5 ms의 정수 buffer로 정확히 표현되지 않는다. 현재 `round(max_delay_s/dt)`는 반올림 결과10 ms를 허용할 수 있다. 상한을 넘기지 않는 `floor`를 쓰면 B 끝 실제 표본은0/5 ms다. 설정 상한과 실현 표본을 함께 적고, 정확한7.5 ms 연속 지연이라고 주장하지 않는다. 물리 dt 변경이나 action 보간은 별도 처치다.
4. 관측 잡음은 현재 manager가 매 관측 계산 때1배 잡음을 뽑는 경로를 유지한다. reset별 배율 일정에 넣지 않는다. 밀기도 reset 순간에 로봇을 치는 것이 아니라 reset에서 다음 에피소드의 강도·간격을 정하고 interval에 발생시킨다.
5. 중간 cfg를 수정해도 초기화 때 복사된 observation manager·actuator·PhysX 값이 따라 바뀐다고 볼 수 없다. 적용 직후 실제 배열, env_ids, 배율, 최초 명목값 해시와 지연 hist를 기록한다. 재개도 이 상태와 다음 push 시각을 보존한다.

## 2. 관측 잡음과 실제 Go2 공개값

EX-39B 저장 YAML에서 직접 읽었다. 현재 actor에 선속도 정답 관측은 없으며 속도 추정 오차를 따로 넣는 항목도 없다. critic의 특권 선속도와 actor의 estimator 출력을 혼동하지 않는다.

| policy 항목 | 현재 U 범위 | 표준편차 a/√3(계산) | B 끝 반폭(1배 유지) | 근거 |
|---|---|---|---|---|
| 몸 각속도 | ±0.2 rad/s | 0.11547 rad/s | ±0.2 | Y:957~965 |
| 몸 좌표 중력 방향 | 성분마다 ±0.05, 무차원 | 0.02887 | ±0.05 | Y:970~978. 각도3°를 직접 더하는 것과 다름 |
| 관절 위치 | ±0.01 rad | 0.005774 rad | ±0.01 | Y:993~1001 |
| 관절 속도 | ±1.5 rad/s | 0.86603 rad/s | ±1.5 | Y:1006~1014 |
| 속도 명령·이전 action | 없음 | 없음 | 없음 | Y:988·1023. 명령 무작위화와 센서 잡음은 별개 |

[AME-2 Appendix B](https://arxiv.org/html/2601.08485v3#A2)는 각속도0.2·중력0.05·q0.01·dq1.5를 사용한다. 이는 **선행 학습 노이즈**이지 Go2 센서 오차 측정치가 아니다. payload±5kg·delay20ms(ANYmal D/TRON1), TRON1의 PD/armature±15%도 Go2에 그대로 옮길 근거가 아니다.

Go2 제조사의 공개 자료·SDK에서 IMU noise density, encoder 절대 정확도, 동적 속도 추정 RMSE를 숫자로 대조할 수 있는 출처는 이번 검색에서 찾지 못했다. 검색 범위: Unitree Go2 제품/개발 문서, unitree_sdk2_python, `Go2 IMU noise density`, `Go2 encoder accuracy`, `Go2 state estimation noise`. 값 없음은 센서가 조용하다는 증거가 아니다.

독립 작성자의 [Go2 Pro 유선 DDS 실측 저장소](https://github.com/AstroKido/go2pro_benchmarks/tree/fd42769b2df1fceef14bd4c0703782f77470316c)는 비교 가능한 일부 원자료를 제공한다. 등급은 **외부 실측 보고·우리 기기 미확인**, 제조사 사양 아님. `results/jitter_60s/encoder_jitter_results.json` 30004표본의 관절 q 표준편차는3.89046e−5~3.65527e−4 rad다(JSON의12관절 열 직접 계산). 현재 U±0.01의표준편차0.005774 rad는 그중최대의15.80배다. 외부정지자료의작은 q흔들림보다현학습잡음이이미크므로q잡음을더키울근거가아니다. 연속 표본 차이 Δq의 표준편차를 q 센서 표준편차나 관절 속도 rad/s로 읽지 않는다. 정지 자료는 하중·온도·진동·충격·bias를 모두 대표하지 않는다.

결론: 현재 잡음을 올려야 한다는 실기 근거는 없다. **최종 크기 유지가 합리적이나, 모든 Go2 센서 오차를 충분히 덮는다는 주장은 미확인**이다. 실제 장비의 정지·보행 센서 로그로 bias와 분산을 따로 재야 한다. 깊이 카메라 잡음은 본 의뢰 밖이지만 실기 전 결측·거리별 오차·노출 및 지연 검증이 필요하다.

### 2.1 제어 주기와 지연

공식 [SDK 예제](https://github.com/unitreerobotics/unitree_sdk2_python/blob/814556d15970dd2ecf1c9984e845ca02ab07e206/example/go2/low_level/go2_stand_example.py#L21)는 lowcmd 송신2ms(:76)다. 이는50Hz 정책주기나 명령 도착 지연의 보증이 아니다.

위 외부 실측의 [latency_v4_results.json](https://github.com/AstroKido/go2pro_benchmarks/blob/fd42769b2df1fceef14bd4c0703782f77470316c/results/latency_v4_results.json)은 유선 저수준 토크 입력부터 `tau_est`가 입력 변화의20%를 넘는 시점까지 선형 보간한199회: 평균5.513ms·p95 7.022·p99 8.612·최대10.178. 우리의 action→관절 운동이나 웹앱→서버→ROS 경로와 같은 측정이 아니다. 0~15ms는 이 자료의 해당 응답 범위를 덮지만 우리 end-to-end 지연을 덮는지는 미확인이다. 장기 packet gap은 별도이며 고정 action delay만으로 재현되지 않는다.

## 3. 계단 위 외란 선행과 밀기 제안

| 출처·실기 관련성 | 학습 때의 외란 | 간격·방향·지속 | 해석 |
|---|---|---|---|
| [HIM ICLR2024 Appendix A.2 Table6](https://arxiv.org/html/2312.11460v3#A1.SS2), A1 계단/외란 실험 | 힘 xyz 각 −30~30 N | 논문은 간격·힘 지속시간 미기재 | [공식 페이지](https://junfenglong.com/HIMLoco/)에 계단에서 발차기·다리/등 끌기 시연이 명시됨. 이번에 해당 동영상 전체를 직접 판독한 것은 아님 |
| [HIM 공식 코드 ef289aca](https://github.com/InternRobotics/HIMLoco/blob/ef289acaa62795009363b7b819c9186690630441/legged_gym/legged_gym/envs/base/legged_robot_config.py#L152) | 힘±30N 및 XY 속도±1m/s 두 장치 | disturbance_interval=8은robot.py:452의policy step 나머지연산, push는16s. robot.py:543은 XY속도 **대입**, :550은 로컬 힘 | 논문 표와 현재 공개코드의 다른 범위를 섞지 않음. `8`을8초라고읽지않음. force함수1회가물리엔진에서유지되는시간은이자료만으로확정하지않음 |
| [DreamWaQ III-B/III-F](https://arxiv.org/html/2301.10602v2), Unitree A1 | TableII에는 push 행 없음 | III-F의 xyz 무작위 속도·1초 간격은 **시험 조건** | 최대push1.121±0.164m/s 결과를 학습 설정으로 옮기면 틀림 |
| [Rudin 공식 legged_gym 8fa29acc](https://github.com/leggedrobotics/legged_gym/blob/8fa29acc6fd1910c3d9659eef6310bdd301cde0a/legged_gym/envs/base/legged_robot_config.py#L112) | XY 속도±1m/s | 15s, 순간 속도 대입 | ANYmal 기반 선행 코드. Go2 실측 아님 |
| 설치 Isaac Lab 공통 velocity task | XY 속도변화량±0.5m/s | 10~15s, world XY 가산, 순간 | events.py:1046~1073의 **본문은 가산**. docstring의 ‘set’만 보고 속도 대입이라고 읽으면 틀림. Go2 rough는 끔 |
| START III-D/PIE III-C3 | PIE TableII DR 따름, push 미기재 | 간격·힘·지속 없음 | START가 특정 밀기 값을 검증했다고 쓰지 않음 |

권고 D: **수평 Δv 각 축 U(−0.5,+0.5)m/s**, B 끝각축±0.25, z/각속도0, 에피소드 안독립 timer10~15s, instant1회. 네모 분포라 평면 최대 크기는0.707m/s(D),0.354m/s(B 끝), 방향각 균일 분포가 아니다. 배율은 크기에만 적용하고 간격을0.5배로 줄이지 않는다. 명목12kg라면 각축 최대 운동량 변화6N·s라는 계산일 뿐, 6N 힘이나 30N의 특정 지속시간과 동등하다고 단정하지 않는다. 계단 발에 걸리는 외력·장시간 끌기·수직 타격은 이 설계가 검증하지 않는다.

## 4. W51 비교 조건과 실제 소비 확인

기존 W51의 `dr_s1`에는 이미 지연+COM+gain+strength가 함께 들어갔다. `eval_actuator/ex38_m3001/dr_s1/map_modes.json` action지연 hist는0:663·1:546·2:507·3:780, 합2496(64×39). 반면 `ex38_m3001_v2/dc`와 `dc_delay`는 마찰·질량을 껐고 dr_s1은 켰다. 따라서 기존 차이를 ‘세 DR만의 영향’이라고 해석하지 않는다.

추가 측정은 두 정책에 동일한 마찰0.2~1.2·질량−1~3을 켠다. frozen 평가 코드 E 907fe1ed, 학습 코드는 수정하지 않았다. CUDA_VISIBLE_DEVICES를 바꾸지 않고 `cuda:1`에서 Kit 한 개씩 실행한다.

| 비교군 | COM/gain/strength/delay | 잡음 | 밀기 | 반복 |
|---|---|---|---|---|
| w51_base | 끔 | 현재1배 | 없음 | 같은 seed42 두 번 |
| w51_push | 끔 | 현재1배 | t2·4s에±0.5m/s | 한 번 |
| w51_noise2 | 끔 | policy4항만2배 | 없음 | 한 번 |
| w51_combo4 | ±5cm·±10%·±10%·0~15ms | 현재1배 | 없음 | 한 번 |
| w51_all6 | combo4와같음 | 현재1배 | t2·4s에±0.5m/s | 한 번 |

각각64env·6초·13명령×지도3모드=39칸. 연속 지형7종 L1, fixed terrain seed42, 초기 생존episode만 계산. 정지·전후진·횡·대각·좌우회전 포함. 빠른 비교의 밀기는6초 안에서2회로 강제해 **제안 학습 간격10~15초보다 빈번**하다. 이는 기존정책 스트레스 시험이며 D학습성공/실기안전 판정이 아니다. 명령 전환 sequence는 이번 좁은 비교에서 제외했다.

예정12실행=468칸, 29,952 env-case. baseline 두 반복의 최대차를 정책·명령·지도별 계산한다. 이는 seed일반화나 오차의 확정 상한이 아니다. 추가DR군의차이가 같은조건 반복폭보다 큰지와 칸별 방향을 같이 보고, 통계적으로 원인이 증명됐다고 부르지 않는다. 생존/추종/기울기는 측정하지만 발위상·관절하중·영상은 이번 평가 코드의 기록에 없어 미확인이다.

첫 CPU17시험 통과. 첫8env Kit는 PhysX read API 오기로실패했고 원자료 보존. `get_root_velocities`로 설치source 대조후 두번째실행 통과:8/8생존, push각8env×2회 readback차0, GT2400/2400, 지연hist0:3·1:1·2:3·3:1. 짧은통과를 전체통과로쓰지 않는다.

원자료: `C:/Users/AI-WS01/s2_lab/basic_gait_runs/eval_actuator/w51_followup_20261030/`. 각 `map_modes.json`에실제재질·질량·COM배열과해시, policy noise범위, actuator수치, 지연hist, push전후속도·PhysX읽기, sourceSHA, checkpointSHA가있다. baseline와변형의재질·질량해시가같은지도결과표작성전에확인한다.

## 5. 전체 측정 결과

진행 중. 결과가 없는 칸을 통과나 영향 없음으로 쓰지 않는다.

## 6. D68~D74 문서 정합 두 차례 대조

측정 후 정본·WORKLIST·FLOW·내 단계 문서·실행카드의 현재 바이트를 다시 읽고, 변경소유자와 행 번호를 표로 남긴다. 정본 세 파일은 직접 고치지 않는다.

## 변경 기록

| 판 | 변경 |
|---|---|
| v0.1a | lead22:0x 정정 반영. 관측 잡음은m0부터1배고정, 다섯DR만확대. GPU비교설정에는변경없음 |
