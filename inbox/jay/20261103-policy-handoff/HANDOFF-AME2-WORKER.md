> 분류: A/정책학습 · AME-2 작업자 전달 지시문 (AME-2 teacher → 앱 묶음)
> 작성: 오흥재 (lead 세션) · 2026-11-03 15:2x v0.1 · 16:1x v0.2 · 16:3x v0.3 (문서 셋으로 나눔 · 저장소 배치 · 가리키는 파일)
> 근거: m6000 앱 조건표 `APP-POLICY-CONTRACT-m6000.md` v0.2 양식 · m6000 ONNX 묶음 `D:/mai-tmp/scripter/w89_export/contract.json` · 석헌 실험 읽기 `inbox/jay/20261018-next-arch/REPORT-seokheon-ame2.md` · 로컬 원자료 `D:/mai-data/ame2/raw/ame2_spd/` (env.yaml · agent.yaml · observations.py · AME2_models.py) · 앱 사본 `analyst-1102/_out/1102/app/mobile/sim/ame2-adapter.js` (135a8469) · 앱 dev d9b6f382 (gh 읽기)
> 요지: 석헌 님(또는 석헌 님의 에이전트)이 아래 「지시문」 하나만 보고 AME-2 저장본에서 ONNX · contract.json · 조건표 · 같은 출력 확인 기록을 뽑아 lab 저장소 `inbox/lim/` 에 PR 로 올리면, 현민 님이 그대로 앱에 붙일 수 있게 한다. AME-2 는 우리 START_oh2l2 와 명령 · 관측 · 지도 · 신경망 · 상태가 모두 달라서 m6000 문서를 그대로 베끼면 안 된다(§3)
> 상태: v0.1 · 사실 대부분은 원자료 · 코드 읽기, 저장본(.pt) 은 로컬에 없어 열어 보지 못함 · §4 미확인 7 건 · 무게 파일 공개 저장소 업로드는 팀장 결정 대기(§5)

# AME-2 정책을 앱에 넘기는 지시문

## 0. 흐름 한 줄

석헌 님이 §1 지시문을 에이전트에 붙여 넣는다 → 에이전트가 RunPod 저장소의 저장본으로 §2 묶음을 만든다 → lab 저장소 `inbox/lim/20261103-policy-handoff/ame2-demo/` 에 브랜치 · PR → 팀장 머지 → 현민 님이 묶음의 `contract.json` 을 읽어 앱에 붙인다.

이 문서의 기준 저장본(앱이 지금 쓰는 것, 미확인 4 참조):
`s3://rzklpc35sl/limseokheon/ame2_spd/logs/rsl_rl/go2_gaze_teacher/2026-10-27_15-57-27_nogapst5_vmax12_to15000/model_14999.pt` (100,274,078 B · 앱 `docs/AME2-PROVENANCE.md:17` 의 sha `8c3be365…`)

앱 개발자(현민 님)는 이 묶음을 기다리지 않고 `HANDOFF-APP-DEVELOPER.md` §1.2 `ame2` 열의 값(학습 env.yaml 에서 이미 뽑음)으로 먼저 만든다. 이 묶음은 그 값을 **원본으로 확인하고 ONNX 를 원본 기준으로 바꿔 끼우는** 용도다.

## 0a. 이름 규칙 (팀장 11/03 16:0x)

| 무엇 | 지금(중간 확인) | 최종 |
|---|---|---|
| START 계열 묶음 format | `start-demo-onnx/1` (scripter 묶음의 옛 값 `foothold-ex40-w89-onnx/1` 을 바꿈) | `start-oh2l2-onnx/1` |
| AME-2 계열 묶음 format | `ame2-demo-onnx/1` | `ame2-oh2l2-onnx/1` |
| ONNX 파일 | `start-demo_map_on/off.onnx` · `ame2-demo.onnx` | `start-oh2l2*.onnx` · `ame2-oh2l2.onnx` |
| 앱 adapter id | `start-demo` · `ame2-demo` | `start-oh2l2` · `ame2-oh2l2` |

같은 계열 안에서 저장본이 바뀌면 이름의 `m<ITER>` 만 바꾸고, 계약(입출력 이름 · 모양)이 바뀌면 format 끝의 `/1` 을 올린다.

---

## 1. 지시문 (이 칸을 통째로 에이전트에 붙여 넣는다)

```text
너는 FOOTHOLD 팀의 AME-2 정책을 앱(foothold-app)에 넘기는 묶음을 만든다. 아래를 순서대로 하고, 하나라도 실패하면 멈추고 그 단계 번호와 원문 오류를 보고한다. 추측으로 채우지 않는다. 값마다 근거(파일:줄)를 적는다.

[입력]
- 저장본: <RUN>/model_<ITER>.pt  (기본: ame2_spd/logs/rsl_rl/go2_gaze_teacher/2026-10-27_15-57-27_nogapst5_vmax12_to15000/model_14999.pt)
- 그 run 의 params/env.yaml · params/agent.yaml (학습이 실제로 읽은 설정 = 정본)
- 그 run 을 학습한 코드 사본 (rsl_rl/rsl_rl/models/AME2_models.py · go2/ame2_go2/tasks/mdp/observations.py · go2 env cfg)

[0단계 · 신원]
1. sha256(model_<ITER>.pt), sha256(env.yaml), sha256(agent.yaml) 을 잰다.
2. 학습 코드의 git 커밋(또는 사본 폴더 이름과 날짜), Isaac Lab · rsl_rl 판을 적는다.
3. 저장본 안의 robot.joint_names(go2_env_state 또는 critic_contract 쪽)를 그대로 꺼내 적는다. 이것이 관절 순서의 정본이다.

[1단계 · 조건표 값 뽑기 · env.yaml/agent.yaml 줄 번호와 함께]
- 제어: sim dt · decimation(→ 제어 Hz) · 행동 지연(물리 스텝 단위인지 초 단위인지 그대로)
- 관절: 순서(0단계 3) · 기본 관절각 · Kp · Kd · 모터 모델(토크 · 속도 한계와 곡선 식)
- 행동: scale · use_default_offset · clip(env 쪽과 runner 쪽 둘 다) · 직전 행동 관측에 넣는 값이 자르기 전/후 어느 것인지
- actor 관측: 항 이름 · 차원 · 순서 · 배율 · 자르기 · 잡음(학습만) · 이력 길이. lin_vel 처럼 실기에서 직접 못 재는 항은 「특권」 표시
- 명령: 종류(목표 위치 [x, y, sin, cos] 인지) · 좌표틀 · 2 m 넘을 때 처리 규칙 · 재표집 주기 · heading 범위
- 지도: 모양(예 29×13×3) · 간격 · 범위(x, y) · 정렬(yaw) · 바깥 축 순서 · 값 정의(z 기준점 · 더하는 상수 · 자르기) · 광선 시작 높이 · 미검출 값 · 학습 잡음
- 신경망: actor 클래스 · 층 크기 · attention head 수 · gaze crop · 순환 상태 유무 · 관측 정규화 유무
- critic · 정답 전용 입력은 「제외」 로 표시

[2단계 · ONNX 내보내기]
- AME2GazeModel 원본에는 as_onnx 가 없다(AME2_models.py:225~227 NotImplementedError, as_jit 만 :636~638). 원본 forward 를 그대로 감싼 내보내기 모듈을 만든다. 층을 새로 짜서 가중치를 옮기는 「재구성」 은 하지 않는다(재구성하면 3단계에서 원본과 맞춰야 한다).
- opset 17 · batch 1 · float32. 입력은 원본과 같은 두 텐서(prop [1,49] · mapping [1,29,13,3]) 를 그대로 둔다. 출력 action [1,12] 와, 있으면 진단 출력(gaze offsets · logits)을 이름과 함께.
- 파일 이름: ame2-demo.onnx (지금은 ame2-demo.onnx · 최종 모델이 정해지면 ame2-oh2l2.onnx), sha256 기록.

[3단계 · 같은 출력 확인 (답을 아는 입력으로)]
- 학습 env 에서 실제 관측 200 스텝(prop · mapping · 원본 action)을 기록해 npz 로 저장한다(평지 1 · 계단 1).
- 같은 입력을 원본 PyTorch(또는 as_jit) · ONNX(onnxruntime CPU) 에 넣어 action 최대 차이를 잰다. 기준 1e-4 이하(float32). 넘으면 멈춘다.
- 기본 자세 시험: 기본 자세에서 joint_pos_rel 12 가 전부 |값|<0.05, action 0 일 때 목표각 = 기본 관절각 벡터.

[4단계 · 묶음 만들기 (§2 목록 그대로)]
- contract.json: m6000 묶음(format "start-demo-onnx/1")과 같은 꼴로 format "ame2-demo-onnx/1", checkpoint · sha256 · source · inputs/outputs(이름 · 모양 · dtype · 뜻) · actor_input_order · command_type "goal_pose_xy_sincos" · state "stateless" · action 식(바깥에서 할 일) · joint_names · default_joint_pos · kp/kd · control_hz · action_delay · map spec · artifacts(path · sha256 · bytes) 를 넣는다.
- CONTRACT.md: m6000 조건표와 같은 절 순서(0a 맨 위 값 표 · 0b 관절 순서 경고 · 1 저장본 · 2 ONNX 에 든 것 · 3 조건표 · 5a 받아 쓰는 법 · 9 기계 블록)로, 값마다 파일:줄과 등급(설정/코드/실측/가정).
- parity.json: 3단계 결과(스텝 수 · 최대 차이 · 통과 여부).
- 3단계 기록 중 평지 20 스텝을 test_vectors_flat20.json 과 .npz 두 꼴로(꼴은 HANDOFF-APP-DEVELOPER.md §2-5a, format "ame2-demo-test-vectors/1", state_feedback false) · 앱이 자기 구현을 맞춰 보는 데 쓴다.

[5단계 · 올리기]
- foothold-project/foothold-lab 을 받아 main 에서 브랜치 inbox-lim-ame2-export 를 만든다.
- inbox/lim/20261103-policy-handoff/ame2-demo/ 아래에 CONTRACT.md · contract.json · parity.json · test_vectors_flat20.json · test_vectors_flat20.npz · SHA256SUMS 을 커밋한다(꼴은 같은 폴더 README.md 「저장소 배치」). 다른 폴더(docs/ 등)는 건드리지 않는다.
- ONNX 파일도 같은 폴더에 커밋한다(팀장 11/03 17:0x · 한 파일 100 MB 아래인지 확인). .pt 저장본은 올리지 않고 RunPod 경로와 sha256 을 contract.json 의 checkpoint 칸에 적는다.
- PR 제목 「AME-2 teacher m<ITER> 앱 전달 묶음」, 본문에 체크포인트 sha · parity 최대 차이 · 미확인 목록.
- 문장에 em dash(가로로 긴 줄표)를 쓰지 않는다.

[보고]
끝나면: PR 주소 · contract.json sha256 · parity 최대 차이 · 못 채운 칸(미확인) 목록.
```

---

## 2. 묶음 목록 (m6000 묶음과 같은 꼴)

| 파일 | 무엇 | m6000 에서의 같은 것 |
|---|---|---|
| `ame2-demo.onnx` | actor 한 그래프 · 상태 없음 | `start-demo_map_on.onnx` · `_map_off.onnx` (두 개, 지금 파일 이름은 ex40_m6000_* · 이름 바꿈 예정) |
| `contract.json` | 입출력 이름 · 모양 · 식 · sha | `w89_export/contract.json` |
| `CONTRACT.md` | 사람이 읽는 조건표(같은 절 순서) | `APP-POLICY-CONTRACT-m6000.md` |
| `parity.json` | PyTorch 대 ONNX 최대 차이 | `w89_export/comparison.json` |
| `test_vectors_flat20.json` · `.npz` | 앱이 맞춰 볼 입력 · 정답 출력(꼴은 앱 문서 §2-5a) | start-demo 도 같은 꼴 |

## 2a. 앱 쪽

앱이 이 묶음을 어떻게 받는지는 같은 폴더 `HANDOFF-APP-DEVELOPER.md` 에 있다. 이 문서는 묶음을 **만드는 쪽** 일만 적는다.

## 3. AME-2 와 우리 START_oh2l2 의 차이 · 섞으면 안 되는 것

석헌 님 AME-2 앱 대상은 **목표 위치 gaze teacher** 다. 속도 명령 정책이 아니고, 실기용 student 도 아니다. 정답 지도와 실제 몸 속도를 받는다.

| 항목 | m6000 (START_oh2l2) | AME-2 teacher (model_14999) | 근거 등급 |
|---|---|---|---|
| 명령 | 속도 (vx, vy, wz) 3 | **목표 위치** [x, y, sin, cos] 4 · 2 m 넘으면 2 m 로 자르고 yaw 다시 뽑음 · 재표집 16.01 s · heading ±π/3 | 설정 (env.yaml:2454~2466) · 코드 (observations.py:276~340) |
| 몸감각 | 45 · lin_vel 없음 | **49** = lin_vel 3 · ang_vel 3 · 중력 3 · q−q0 12 · dq 12 · 직전 raw 행동 12(±50 자름) · 목표 4. **lin_vel 은 특권**(실기 직접 측정 불가) | 설정 (env.yaml:1320~1409) |
| 이력 · 순환 상태 | 이력 10×45 · GRU h_prop · h_terr 각 128 | **없음**(매 스텝 독립) | 코드 |
| 지도 | 32×16 · 5 cm · 높이 1 채널 · 복원 또는 정답 + 깊이 60×60 | **29×13×3(xyz)** · 6 cm · x −0.42~1.26 · y ±0.36 · x 가 바깥 축 · z = hit − sensor + 0.27, ±1.5 자름 · 광선 +20 m · **정답 지도만** | 설정 (env.yaml:586~618 · 1277~1316) |
| 신경망 | 지각(TR-Net · I-E, GRU 둘) + actor MLP 512/256/128 | AME2GazeModel: prop MLP 49→512→512→128 · 전역 CNN→64 · gaze crop 12×10 · 토큰 96 · MHA 32 heads · 288→512→512→12 · RNN 없음 | 설정 (agent.yaml:1~45) · 코드 |
| ONNX 입력 | 9 개(obs45 · hist · depth2 · h 둘 · 플래그 · gt_map) | 2 개(prop · mapping) | 코드 |
| 관절 순서 | hip4 → thigh4 → calf4 (FL FR RL RR) | **같음**(앱 ame2-adapter.js:3~9 · 저장본 joint_names) | 코드 |
| 기본 자세 · Kp/Kd · 배율 · 50 Hz | 0.1/0.8/1.0/−1.5 · 25/0.5 · 0.25 · 50 Hz | 같음 | 설정 |
| 행동 지연 | 0~15 ms(DR 배율 연동) | **0~4 물리 스텝**(0~20 ms) | 설정 (env.yaml:1583~1600) |
| 모터 모델 | DCMotor · hip/thigh 23.5 · calf 45.43 N·m | Go2HV · hip/thigh 20.2/23.4 · calf 38.73/44.86 곡선 | 설정 (env.yaml:166~203) |
| 행동 자르기 | ±17 | ±100(env) | 설정 |
| 관측 정규화 | 없음 | 없음(empirical_normalization null) | 설정 |
| 학습 틀 | Isaac Lab · rsl_rl PPO | Isaac Lab 5.1 · 수정 rsl_rl · PPO muon · bf16 · critic MoE 16 | 설정 |

**받는 쪽 주의 셋 (v0.2 · 팀장 답 반영)**
1. 명령 칸은 목표 위치다. 앱이 조이스틱 속도를 「매 tick 1 m 안쪽 목표」 로 바꿔 넣는 것(ame2-adapter.js:54~62)은 목표 기반 정책을 조이스틱으로 모는 **변환으로서 문제없다**(팀장 판단). 다만 학습은 최대 2 m 목표였고(AME-2 기저 설정), 이 판은 이동 보상 속도 상한을 **1.2 m/s** 로 낮춰 학습했다(`raw/ame2_spd/README.txt:2`, `--move2goal_vmax 1.2`). 그래서 조이스틱 1.5 를 줘도 1.2 근처에서 멈춘다. 1 m 목표에서 실제 속도가 얼마나 나오는지 앱 시뮬에서 한 번 재서 앱의 AME-2 범위 표에 적는다.
2. 이 teacher 는 실제 몸 속도와 정답 지도를 쓴다. 지금은 중간 확인이라 시뮬 트윈 전용으로 쓴다. **최종 발표 때는 student 를 실기에, teacher 를 시뮬에** 둔다(팀장 11/03 16:0x). student 는 석헌 님이 학습할 예정이다.
3. 지도 배열의 「뜻」 이 두 정책이 다르다. 우리 START 는 한 칸에 숫자 하나(그 칸 바닥 높이 − 몸 높이)를 32 × 16 칸에 담는다. AME-2 는 한 칸에 숫자 셋(그 칸의 x · y · z 좌표)을 29 × 13 칸에 담고, z 는 「바닥 높이 − 센서 높이 + 0.27」 이다(0.27 은 서 있을 때 평지가 0 근처가 되게 학습 코드가 더하는 고정값). 칸 간격도 5 cm 대 6 cm 로 다르다. 그래서 앱은 **정책마다 지도 만드는 함수를 따로** 둔다. 한 함수를 같이 쓰면 숫자가 학습 때와 달라져 로봇이 땅 높이를 잘못 본다.

## 4. 미확인 · 석헌 님께 물을 것

1. 계단 영상이 정확히 model_14999 와 같은 목표 · 같은 계단 치수에서 찍혔는지.
2. ~~student 계획~~ **답: 학습할 예정**(팀장 11/03 16:0x). 남은 물음: 일정 · student 입력(깊이 · 이력 20) · 같은 이름 규칙으로 묶음.
3. ~~2 m 대 1 m~~ **답: AME-2 기저 설정이 2 m 라 그렇다**(팀장). 남은 물음: 1 m 목표에서 실제 속도 · 앱 상한(1.2)을 석헌 님이 확인해 줄 수 있는지.
4. model_14999.pt sha256 을 석헌 님이 직접 다시 잴 수 있는지(이번에 재지 못함, .pt 로컬 사본 없음).
5. 학습 당시 Isaac Lab · rsl_rl 커밋.
6. 원본(as_jit) 출력과 앱 ONNX 를 맞춰 본 적이 있는지. 앱 ONNX(`ame2_actor.onnx` sha 398acb0c…)는 **재구성 actor** 로 내보낸 것이라(앱 `mobile/scripts/ame2-training-contract.md:35` · `ame2_export.py`) 이 지시문 3단계로 원본과 맞춰야 한다.
7. 가상 바닥 · 무반사 처리(앱의 0.7 m 고정 대체값)를 학습과 맞춰도 되는지.

## 5. 팀장 결정 필요

- ~~ONNX 를 공개 lab 에 올릴지~~ **답: 올린다**(팀장 11/03 17:0x). AME-2 공개 코드는 GPL-3 라 그것을 고친 내보내기 스크립트를 함께 올리면 그 스크립트는 GPL-3 로 둔다.
