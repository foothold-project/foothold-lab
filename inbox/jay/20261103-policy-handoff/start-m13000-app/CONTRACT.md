> 분류: A/정책학습 · 앱 전달 조건표 (start-m13000 · m6000 조건표와 다른 것만)
> 작성: 오흥재 · lead 세션 · 2026-11-09 10:2x v0.1
> 근거: 저장본 `C:/Users/AI-WS01/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914/model_1000.pt` (sha256 `20365a2c…`, 직접 잼) · 같은 폴더 `params/env.yaml` · `params/agent.yaml` · `manifest.json`(학습 코드 `eae0bed7`, 바뀐 소스 0 바이트) · `ex42_application.jsonl`(0 단계 명령 범위) · m6000 조건표 `../start-demo-app/CONTRACT.md` · 만든 명령 `../make_start_app_bundle.py` · 결정 팀장 11/09 10:0x 「m13000 ONNX 를 git 으로 팀원 · 앱에 전달하고 앞으로 같은 절차로 반복」
> 요지: m13000 은 m6000 과 ONNX 입출력(이름 9 · 4, 모양, 자료형)이 같아서 앱 실행기는 그대로 쓴다. 바뀐 것은 저장본 · actor 안의 자세 명령 2 칸(ONNX 안에서 0 고정) · 학습 때 지도 섞기(정답 고정 → 정답 · 복원 섞음) · 후진 학습 범위(−1.0 → −1.3) 넷이다
> 상태: v0.1 · 묶음 만듦 · CPU 같은 출력 확인 끝(parity.json) · 앱 적용 · 브라우저 ORT · 실기는 미확인

# start-m13000 조건표 (m6000 과 다른 것만)

이 묶음의 조건은 `../start-demo-app/CONTRACT.md` (m6000) 와 같다. 아래 표에 적은 것만 다르다. 앱 쪽 할 일은 `../HANDOFF-APP-DEVELOPER.md` 하나만 본다.

## 1. 무엇이 바뀌었나 (m6000 → m13000)

| 칸 | m6000 (`start-demo`) | m13000 (`start-m13000`) | 앱이 할 일 |
|---|---|---|---|
| 저장본 | EX-40 `model_6000.pt` · sha `d5e9ec40…` | EX-42 0 단계(`EX42_0_T0_prime`) `model_1000.pt` · 누적 13000 update(부모 EX-41 `model_6000.pt` = 누적 12000, sha `1c6af631…`) · sha `20365a2c6d70f94f65f1114471f7df198e56d86db6d02d89cea43c666b95e768` | 파일 · sha 를 바꾼다 |
| ONNX 파일 | `start-demo_map_on.onnx` · `_map_off.onnx` | `start-m13000_map_on.onnx` · `start-m13000_map_off.onnx` (sha 는 `contract.json` · `SHA256SUMS`) | 파일 이름 · sha 만 바꾼다 |
| ONNX 입출력 | 입력 9 · 출력 4 | **같다** (이름 · 순서 · 모양 · 자료형, 플래그 셋 bool). 만드는 명령이 m6000 의 `app_onnx` 칸과 한 칸씩 대조해 같을 때만 묶음을 낸다 | 없음 |
| actor 입력 | 96 = 몸감각 45 + 추정 51 | 98 = 몸감각 45 + 추정 51 + **자세 명령 2** [몸 높이 변화 m, 몸 roll rad]. 학습 내내 0 이었으므로(D93 첫 단계) **ONNX 안에서 0 으로 고정**했다. ONNX 입력이 아니다 | 없음. 앱이 자세 명령을 넣을 자리는 없다 |
| 학습 때 지도 | 늘 정답 지도(`force_gt=true`) · 지도 끔 10 % | 정답 · 복원을 섞음(`force_gt=false`, 마지막 update 의 정답 쓴 env 비율 0.286 · 0 단계 `map_reset_counts` 정답 1571 만 · 복원 4733 만 · 끔 696 만) · 지도 끔 10 % 같음 | 없음. 복원 모드가 이제 학습한 모드다 |
| 명령 학습 범위(0 단계 표집) | 전진 0.1~1.5 · **후진 −1.0~−0.2** · 옆 0.2~0.6 · 제자리 회전 0.3~1.5 · 걸으며 회전 wz 0.2~1.0 와 vx 0.3~0.8 · 대각 vx 0.3~0.6 와 vy 0.2~0.5 | 같고 **후진만 −1.3~−0.2** (`ex42_application.jsonl` `stage_config.ranges.reverse_vx`) | 모드 상한 후진 1.0 → **1.3** (D108 후진 상한 1.3 과 학습 범위 중 작은 쪽). 나머지 상한(전진 1.5 · 옆 0.5 · 제자리 회전 1.2 · 걸으며 회전 1.0)은 같다 |
| 보상 · 지형 순서 | EX-40 | EX-41 W86 보상 항 · 가중치 둘(`lin_vel_z` −2.0 → 0 · `stumble` −1.0 → −2.0) · EX-41 지형 순서 | 없음(학습 쪽만) |

`params/env.yaml` 두 판의 차이 92 줄을 모두 읽었다. 관측 · 행동 · 센서 · 로봇(PD · 토크 · 기본 관절각 · 행동 배율 0.25) 칸에는 차이가 없고, 차이는 자세 명령 관측 묶음 · 보상 · 지형 순서 · 리셋 이벤트 · 무효 판 종료 · 경로뿐이다. `agent.yaml` 의 행동 자르기 ±17 · 관측 정규화 끔도 같다.

## 2. 같은 출력 확인 (CPU · `parity.json`)

| 확인 | 결과 |
|---|---|
| ONNX checker | 두 그래프 통과(map_on 289 · map_off 354 node) |
| 합성 입력 12 경우(첫 스텝 · 이어진 스텝 · 깊이 틱 없음 · 정답 지도 · 3 스텝 되먹임, 지도 켬 · 끔) | PyTorch 대 onnxruntime CPU 최대 차이 7.63e-6 (기준 3e-5) |
| 실제 Kit 입력 9 경우 × 20 스텝(평지 · rough L0 · 계단 L2 × 복원 · 끔 · 정답), ORT 의 GRU 출력을 다음 스텝에 되먹임 | 최대 차이 3.46e-6 (기준 1e-4) · action · h · 복원 지도 넷 모두 |

**실제 입력의 뜻.** Kit 이 기록한 관측 · 깊이 · 지도(m6000 묶음 때 기록 `D:/mai-tmp/scripter/start_demo_real20_20261103_try03/`)를 그대로 넣고, GRU 상태만 m13000 자기 것으로 이었다. 로봇을 몬 것은 m6000 이므로 **m13000 이 스스로 걸은 궤적(폐루프)은 아니다.** 입력 정렬(이력 순서 · 깊이 지연 · 플래그)과 ONNX 가 PyTorch 와 같은 답을 내는지를 보는 시험이고, 걸음 성적을 보는 시험이 아니다. 이번에는 GPU · Kit 을 쓰지 않았다.

같은 방법이 맞는지 답을 아는 입력으로 먼저 쟀다. 같은 명령에 m6000 저장본을 넣으면 ONNX 두 파일이 lab 의 `start-demo` 파일과 **바이트까지 같고**(sha `81c7e079…` · `5d1b7bf3…`), CPU 재생 출력이 Kit 기록 출력과 최대 2.6e-6 차이였다.

## 3. 시험 벡터

`test_vectors_flat20_{reconstruction,gt,off}.json` · `.npz` (평지 20 스텝, format `start-m13000-test-vectors/1`, `state_feedback=true`) · 기본 `test_vectors_flat20.json` 은 reconstruction 과 같은 파일 · 합본 `test_vectors_flat20.npz`. 꼴은 m6000 과 같다(앱 문서 §2-4). expected 는 m13000 PyTorch CPU 출력이다(위 2 의 실제 입력).

## 4. 미확인

- 미확인: m13000 이 Kit 에서 스스로 걸을 때의 입력으로 한 같은 출력 확인 · 정해질 때까지 위 2 의 재생 확인만 근거로 쓴다.
- 미확인: 앱 Node · 브라우저 ORT 에서의 최대 차이와 추론 시간(20 ms 기한) · 정해질 때까지 앱 시험(`HANDOFF-APP-DEVELOPER.md` §2-4)을 통과해야 그 모드를 켠다.
- 미확인: 0 단계 이전 EX-41 단계들의 명령 범위가 m13000 걸음에 남긴 영향 · 앱 상한은 위 1 의 0 단계 범위로 둔다.
- 미확인: 실기 카메라 · IMU · 관절 스트림 정렬, Jetson, 실기 안전 제어 · 정해질 때까지 웹 시뮬 전용(m6000 과 같음).
