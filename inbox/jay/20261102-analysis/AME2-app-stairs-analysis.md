> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: analyst · 2026-11-02
> 근거: foothold-app dev 135a8469 · 원본 학습 코드/params SHA 재대조 · 소스와 CPU 산술
> 요지: 계단 실패를 JS 수치 오류로 확정할 수 없으며, 종료 판정 · 목표 계약 · 지도 광선 · 관절 순서부터 분리해야 한다
> 상태: 분석 완료 · 동등성/보행 시험 미실행 · 코드와 GPU 변경 없음

# AME-2 앱 계단 실패 원인 후보와 같은 입력 대조안

**우선 확인은 앱의 `fell` 표시와 목표 입력이다. 신경망 수치 시험만 반복하거나 곧바로 재학습할 근거는 부족하다.** 아래 우선순위는 원인 확률 순위가 아니라, 현재 근거가 있고 적은 비용으로 구분할 수 있는 확인 순서다. 실제 실패 영상, 앱 빌드, 계단 치수, 당시 입력/출력 기록은 이번 의뢰에 없으므로 실패 원인 확정은 불가다.

## 1. 비교 대상부터 고정

앱은 dev를 읽은 시점의 `135a8469896fd4b5ae222a8a89663ac5fb114efd`다. 실제 단말의 APK가 이 커밋인지 미확인. 분석 중 dev가 바뀌어도 이 보고서의 대상은 바뀌지 않는다.

앱 [PROVENANCE](https://github.com/foothold-project/foothold-app/blob/135a8469896fd4b5ae222a8a89663ac5fb114efd/docs/AME2-PROVENANCE.md#L15)는 원본 `model_14999.pt` SHA `8c3be365eeddd136edda31988df7fed96ad6f9f92713490b2d993037bf978d4d`, 앱 f32 SHA `28edbc05169b817044c600d90cc081bb797ae56c5b8400b8ffebf648410d26a0`를 기록한다. 두 모델 파일 자체는 이번에 재해시하지 않았고 문서의 주장으로 구분한다.

반면 학습 코드 5개와 env.yaml은 로컬 원자료를 직접 해시하여 위 문서와 일치했다. env.yaml이 일치한 실행 폴더는 다음이다. 이전의 다른 AME-2 실험 폴더로 대체하면 안 된다.

`D:/mai-data/ame2/raw/ame2_spd/logs/rsl_rl/go2_gaze_teacher/2026-10-27_15-57-27_nogapst5_vmax12_to15000/params/env.yaml`

| 원자료 | 이번 재계산 SHA-256 |
|---|---|
| 위 env.yaml | `08b815230d30f6d86e45913f39f8a818ab40cacbf40303cbc597623054ad4e65` |
| `ame2_spd/rsl_rl/rsl_rl/models/AME2_models.py` | `d88276b1a9cac8c676828af7991f50c7515726245210f5f6c09ae34c4466d14d` |
| `ame2_spd/rsl_rl/rsl_rl/modules/ame2_modules.py` | `b3fc6b38073b085299c9e622e1c1a6e86126d94ae488d5485e7853e7841a8a2c` |
| `ame2_spd/go2/ame2_go2/tasks/mdp/observations.py` | `02aca54ea3e5716fd0faacec5b6d54e592b89fd0841c73de1732e98fc140fee6` |
| `ame2_spd/go2/ame2_go2/tasks/mdp/actions.py` | `792b74d38c4cb1abe2350d63c18a20d96fb3414d8c8f1a525c63bb1b488bf756` |
| `ame2_spd/go2/ame2_go2/tasks/go2_env_cfg.py` | `58342b6abedc758e42ec0878a2ffedde2f74440c8277139a1ab93bb75e9f7ded` |

아래 `E`는 이 env.yaml, `O`는 이 observations.py, `M`은 이 AME2_models.py다. **앱 대상은 정답 지도와 실제 몸 속도를 받는 gaze teacher다.** AME-2 논문 전체 또는 LSIO/depth student의 배포가 아니다. M:390~405의 TAGA식 gaze 변형도 포함한다. 석헌 님의 계단 성공 영상이 정확히 이 체크포인트·목표·계단인지 먼저 대조해야 한다.

## 2. 원인 후보와 가르는 측정

| 후보 | 확인된 차이 또는 빈칸 | 이 원인을 가르는 최소 기록/시험 | 현재 판단 |
|---|---|---|---|
| 앱이 먼저 넘어짐으로 판정해 추론을 끊음 | `sim.js:54~58,91~98`은 몸통 투영 범위 5점의 최고 지면을 기준으로 높이 `<0.18 m` 또는 중력 z `>−0.5`면 `fell`을 래치한다. `main.js:579~584`는 그 뒤 정책 스텝을 하지 않는다. 학습 E:2272~2306의 자세 종료는 다른 조건이다 | 계단 접점 전후 `qpos.z`, 5개 지면값, `supportZ`, `s.z`, gravity, `fell` 최초 시각, 마지막 정책 호출 시각, 실제 접촉을 함께 기록. 멈춘 화면과 정책의 자발적 정지를 분리 | **실제 경로 차이 확인됨. 계단 실패에서 발동했는지는 미확인** |
| 목표 위치 정책을 짧은 목표 추적으로 바꿈 | 학습 O:296~340은 고정된 목표까지 몸 좌표 잔여 거리와 heading이다. 2 m보다 먼 목표는 길이 2로 자르고 yaw를 매 스텝 무작위화한다. E:2454~2466의 재추출은16.01 s. 앱 `ame2Joystick`은 매 스텝 몸 앞/옆 최대1 m의 새 목표와 누적 heading을 만든다 | 같은 계단에서 같은 세계 좌표 목표를 유지하며, 원본과 앱의 cmd4를 한 스텝씩 비교. 이후 앱 조이스틱 방식만 바꿔 대조 | **계약 차이 확인됨. 계단에서 추진/목표 도달 행동을 바꿀 가능성, 원인 확정 아님** |
| 높은 계단이 지도에서 빠짐 | 학습 E:592~614는 광선 시작 z+20 m. 앱 `ame2-adapter.js:40,58~70`은 몸 z+0.501 m 아래로만 쏜다 | 동일 root pose·동일 계단의 377개 hit/miss·xyz를 대조. 높이·상승 방향별로 누락 위치 표시 | **정의 차이 확인됨. 계단 높이·접근 위치에 따라 발생하므로 모든 계단 실패 설명은 아님** |
| 관절 순서·부호·기준 자세 불일치 | 앱 관절 순서는 명시적 가정이다. `joint_names=null` 또는 regex `.*`는 실제 Isaac articulation 순서를 증명하지 않는다 | 학습 런타임에서 저장한 `robot.joint_names`와 action/obs joint_ids, default q, 축 부호를 확보. 이름별 one-hot target와 q/dq를 대조 | **중요 미확인**. 심하게 틀리면 평지도 망가질 수 있으나 평지 성공만으로 모든 순서/부호를 증명하지 못함 |
| JS 신경망 수치 이식 | 기존274건은 독립 재구성 PyTorch Actor→NumPy→JS 대조다. 원본 클래스를 실행한 대조가 아님. 읽은 구조·가중치 이름·crop/MHA 경로는 대응 | §4의 실제 `AME2GazeModel` 결정적 출력과 JS를 같은 입력/같은 가중치로 비교 | **소스에서 구체 수치 결함은 찾지 못함**. 시험 범위를 넘어 원본 동등이라 부르지 않음 |
| 관측 축·단위·지도 순서 | 신체49열과 지도xyz 배치는 대체로 대응. 실시간 root 기준점, quaternion, 각속도·속도 변환, named joint 배열은 실측 전 | 회전/기울기/한 관절만 이동한 답 아는 상태로49열을 개별 비교. 지도는 한쪽에만 계단을 둬 x/y 반전 검출 | 소스 대응 확인, 실제 같은 상태의 입력 동등성은 미확인 |
| 자산·모터·접촉 모델 | 앱은 MuJoCo 자산, 학습은 E:134의 Isaac5.1 Go2 USD. 질량/관성/발 형상/자가 충돌의 실제 동일성 미확인. 주요 PD와 토크 곡선은 수치가 맞음 | 이름별 질량·COM·관성·관절 한계·축·충돌체·발 마찰 표와 동일 q/dq/target의 토크 비교. 관측/목표 동등 뒤 평지→단일 단→동일 계단 | **물리 이전 위험은 남음. 단순히 엔진 이름이 달라 실패했다고 단정 불가** |

경로 링크: [sim.js](https://github.com/foothold-project/foothold-app/blob/135a8469896fd4b5ae222a8a89663ac5fb114efd/mobile/sim/sim.js#L52), [main.js](https://github.com/foothold-project/foothold-app/blob/135a8469896fd4b5ae222a8a89663ac5fb114efd/mobile/sim/main.js#L572), [adapter](https://github.com/foothold-project/foothold-app/blob/135a8469896fd4b5ae222a8a89663ac5fb114efd/mobile/sim/ame2-adapter.js#L3), [미확정 관절 계약](https://github.com/foothold-project/foothold-app/blob/135a8469896fd4b5ae222a8a89663ac5fb114efd/docs/spec/11-POLICY-ADAPTER.md#L258).

**답 아는 산술 반례, 시뮬 측정 아님:** 몸 높이가 세계 z=0.35 m이고 몸통 투영 앞쪽 점에 높이0.20 m의 단이 들어오면 앱 기준 높이는0.15 m라 `<0.18`을 만족한다. 수평 자세여도 이 조건만으로 추론이 중단될 수 있다. 이것은 실제 접촉/넘어짐의 증거와 다르다. 따라서 실패 기록에서 가장 먼저 `fell`의 최초 원인을 찾는다. 이 반례를 이유로 안전 판정을 통째로 끄라는 권고는 아니다.

광선 반례도 조건부다. 몸 z=0.35일 때 앱의 광선 시작은0.851 m다. 그보다 높은0.90 m 상면은 위에서 내려쏘아 볼 수 없다. 여러 단의 누적 높이나 상부 구조물이 영향을 줄 수 있다. 반면 가까운 낮은 단이 광선 아래에 있으면 이 차이만으로 지도 오류라 할 수 없다.

## 3. 이미 맞는 것과 아직 다른 것

### 지도 29×13×3은 세 종류의 지도가 아니다

각 점의 채널은 **x · y · z**다. RGB, 높이/기울기/불확실도 세 채널이 아니다. x는 전후, y는 좌우, z는 `hit_world_z − sensor_world_z +0.27`이고 clip은±1.5 m다(O:160~224, E:1309~1313). 앱도 몸 기준으로 같은 식을 쓴다. 학습 RayCaster의 `+20 m`는 광선 출발 높이이고 정규화에 빼는 몸/sensor 위치에 더하는 값이 아니다.

범위는 x=−0.42~1.26 m, y=−0.36~0.36 m, 간격0.06 m. 저장은 x가 바깥 축이고 y가 빨리 변한다. CPU 산술로 index0=(−.42,−.36),12=(−.42,+.36),13=(−.36,−.36),376=(1.26,.36)을 확인했다. O:195~222와 앱:13,69가 대응한다. 로컬 Isaac `patterns.py:41~53`에서 `ordering=yx`는 meshgrid `ij`로 해석된다. 학습 당시 Isaac 패키지 바이트까지 같다는 증거는 별도다.

학습 지도에는 xy±.001 m, z±.05 m 잡음과 scanner drift±.04 m가 있다(E:616~618,1309~1312). 앱은 잡음0이다. 이것은 평가에서 의도적으로 없앨 수 있는 차이이며, 잡음을 안 넣었다는 이유만으로 실패 원인이라고 하지 않는다. 구멍 fallback도 학습 가상 바닥 이벤트와 앱 고정0.7 m를 따로 비교해야 한다.

### 모터 세기를 안 옮겼다는 주장은 현재 코드와 다르다

E:166~203과 앱:15~21,42~43은 kp25, kd0.5, action scale0.25, armature0.01, hip/thigh 구동20.2·제동23.4 Nm와 calf 구동38.7274·제동44.8624 Nm의 속도별 포화 곡선이 대응한다. 앱은 XML의 중복 토크 제한도 푼다(`sim.js:42~49`). 실제 원본 함수는 `go2_curve.py:6~16`이다.

다만 학습의 지연은 reset마다0~4 **물리 스텝**(0~20 ms), 앱은0이다(E:21,1598~1600, actions.py:44~72). 지연 버퍼는 `process_actions`가 아니라 `apply_actions`에서 이동하며, 로컬 Isaac `manager_based_rl_env.py:182~189`는 이를 매 물리 스텝 호출한다. 따라서 정책 주기20 ms를 곱해80 ms라고 읽으면 안 된다. 학습 서버의 Isaac 패키지 자체 해시는 이번에 확인하지 않았다. 앱 `ISAAC_LIKE`는 관절 추가 damping/frictionloss0, 발 마찰0.8이다(`sim.js:12~13,34~38`, main.js:173). 0.8은 학습 DR0.3~1.0 범위 안이다(E:1628~1633). 이 사실은 질량·COM·충돌체·접촉 솔버까지 같다는 뜻이 아니다.

## 4. 실제 PyTorch 원본 대 JS 시험 계획

다음은 **실행 전 설계**다. 이번에는 모델 로드·추론·물리 시험을 하지 않았다. 새 학습이 아니라 변환과 소비 경로를 나눠 확인하는 시험이다.

| 순서 | 입력과 비교 | 통과/실패 해석 |
|---|---|---|
| 대상 고정 | 원본 체크포인트·f32·배치표·실제 앱 빌드·자산·장면·계단 치수·명령 로그의 SHA를 한 manifest에 기록. 성공 영상의 원본 모델과도 대조 | 다른 모델/과제이면 먼저 그 차이를 남김. 영상만 보고 동일 모델이라 가정하지 않음 |
| 원본 순전파 | 받은 `AME2GazeModel` 실제 클래스와 같은 state_dict를 CPU fp32, eval, deterministic mean으로 호출. 배포용 `_TorchAME2GazeModel`도 비교. 앱 exporter의 독립 Actor는 세 번째 대조용으로 둠 | 원본→독립 Actor→JS 어느 구간에서 달라지는지 분리. `stochastic` sample과 mean을 비교하지 않음 |
| 같은 관측 묶음 | 실제 계단 접근·첫 발 접촉·상승·실패 직전의 `teacher_prop[49]`, `teacher_mapping[29,13,3]`, 직전 action을 원본/JS 양쪽에 동일한 float32 바이트로 공급. 평지·좌우 계단·yaw90°·기울기·void와 crop 반정수 경계도 추가 | 기존274개 합성 입력을 보존하되 실제 실패 입력으로 빈틈을 메움. GPU 필요 없는 신경망 대조부터 |
| 중간 출력 | prop embedding, global feature, gaze logits/좌표, crop의 정수 index와 xyz, local token, query, attention, raw action12를 저장 | crop index는 완전 일치. 기존 시험의 `atol=1e-4, rtol=0`를 진단 출발값으로 유지하고 층별 최대/평균 오차·비유한값을 보고. 문턱을 나중에 넓혀 통과시키지 않음 |
| 행동 소비 | raw action 이후 이름별 target=`default+.25*a`, clip, 지연, q/dq, PD torque, torque-speed clip을 비교 | 신경망 출력이 같아도 target/torque가 다르면 adapter/actuator 문제. 1e-4 action 차이는 포화 전 target2.5e-5 rad·kp항0.000625 Nm에 해당하며 실제 보행 보증은 아님 |
| 관측 소비 | 같은 세계 상태에서 source runtime이 산출한49열·377xyz와 앱 산출을 비교. 몸 좌표 회전·joint ordering·광선 miss·지면 기준을 항목별 출력 | 같은 배열 시험 통과와 실제로 같은 배열을 만드는 것을 분리. 기존 지도 selftest의 분석식 일치는 Isaac 실제 관측 일치가 아님 |
| 폐루프 | 위 차이를 닫은 뒤 동일 치수 계단·초기상태·정지→출발·고정 세계 목표로 원본과 앱을 비교. `fell` 시각/정책 호출, 명령, 발 접촉·높이·미끄럼, 몸 기울기, 토크 포화, 영상 동시 보존 | 수치가 같지만 물리 궤적이 갈리면 자산/접촉/모터 이전을 조사. 앱 조이스틱 방식의 시험은 그다음 별도로 |

원본 파일을 새로 작성한 복제 클래스와 혼동하지 않는다. 실제 원본을 CPU에서 불러오기 위한 의존성은 확인하되, Isaac/Kit을 켤 필요 없는 네트워크 경로부터 분리한다. 입력 수집을 위해 원본 환경 실행이 필요하면 이번 읽기 전용 범위 밖이므로 실행 담당자가 별도 결정한다.

## 5. 기존 PASS가 보장하는 범위

[exporter:1~2,48~49,287~305,328~337](https://github.com/foothold-project/foothold-app/blob/135a8469896fd4b5ae222a8a89663ac5fb114efd/mobile/scripts/ame2_export.py#L48)는 학습 소스를 **읽어서 재구성**한 `Actor`를 사용한다. 기존 문서의274건·최대오차는 이번 재실행 수치가 아니다. `ame2-network.js:1~2`도 NumPy reference에서 번역했다고 명시한다. 이 대조는 유용하지만 원본 실행을 생략한 공통 오역까지 배제하지 않는다.

[sim selftest:1,76~88](https://github.com/foothold-project/foothold-app/blob/135a8469896fd4b5ae222a8a89663ac5fb114efd/mobile/scripts/ame2-sim-selftest.mjs#L76)는 3초/150스텝 유한값과 reset을 확인하며 **보행 성공은 판정하지 않는다**고 직접 적었다. `ame2-perf-parity.mjs`는 최적화 전후 JS 동등성 검사다. 따라서 기존 시험을 허위라고 부를 이유는 없지만, 계단 성공을 이미 검증했다는 근거로도 쓸 수 없다.

## 6. lead에게 넘길 결론

먼저 실패 화면의 실제 모델·계단·명령과 `fell` 최초 시각을 확보하고, 원본과 동일한 고정 세계 목표 및 지도 입력으로 좁힌다. 관절 순서는 제공자의 실제 이름 배열로 닫는다. 그와 병렬로 같은 관측에 대한 원본 PyTorch→JS 출력을 CPU에서 대조한다. 이 순서면 **정책이 계단을 못 배웠는지**, **앱이 다른 입력/물리 과제를 주는지**, **앱이 먼저 멈췄는지**를 분리할 수 있다.

원자료 사본은 `C:/mai/wt/foothold-lab/analyst-1102/_out/1102/app/`, 해시·산술 기록은 같은 `_out/1102/AME2-static-evidence.json`이다. 사본을 실행하거나 수정하지 않았고, EX-40·그림자 루프·학습 코드·원장은 건드리지 않았다. 문서 분석의 막음0, **원인 확정과 이식 동등성은 미확인**이다.
