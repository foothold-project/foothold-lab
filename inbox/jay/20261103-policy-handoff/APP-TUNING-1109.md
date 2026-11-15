> 분류: A/정책학습 · 앱 조종감 맞추기 안내 (start 모드 · 팀장 11/09 10:5x 관찰 셋)
> 작성: 오흥재 · lead 세션 · 2026-11-09 11:1x v0.1
> 근거: foothold-app `dev` `2f1ef45` (2026-11-09 09:47, 읽기만 함) `mobile/sim/` · 이 폴더의 ONNX 다섯(m6000 · m13000 지도 켬/끔 · ame2) · EX-42 `params/env.yaml` 명령 칸 · 학습 코드 `eae0bed7` `foothold_s2/commands/mixed_command.py` · 측정 스크립트와 결과 `app-tuning-1109/` (CPU 만, GPU 안 씀)
> 요지: 세 증상 중 둘은 원인을 쟀다. ① 「튀어 나감」 은 막대가 0 에서 1.5 m/s 를 한 번에 보내서다(학습도 계단 명령이라 정책이 0.1 초 만에 0.5 m/s 를 넘긴다). ② 「목표 모드가 느림」 은 앱 기본 속도 0.4 m/s 때문이다(측정 0.39~0.41 m/s). ③ 「무거움」 은 계산이 원인이 아니다(우리 한 스텝 약 5 ms 로 20 ms 기한의 1/4). 코드로 보면 start 모드만 화면을 초당 약 10 번 그리게 되어 있고 이것이 가장 유력하지만 브라우저에서 아직 재지 않았다
> 상태: v0.1 · 측정은 이 PC(Node · Python CPU) 만 · 브라우저 · 폰 실측과 고친 뒤 확인은 미확인 · 앱 저장소는 손대지 않음

# 앱 조종감 맞추기 · start 모드 (11/09)

현민 님께. 팀장님이 앱에서 우리 정책(start)과 AME-2 를 나란히 몰아 보고 세 가지를 말했습니다. 이 문서는 각 증상의 원인을 숫자로 재고, 앱에서 무엇을 어떻게 고치면 되는지 순서대로 적은 것입니다. 앱 코드 줄 번호는 모두 `dev` `2f1ef45` 기준입니다.

| 번호 | 팀장 관찰 (11/09 10:5x) | 원인 | 확실한 정도 |
|---|---|---|---|
| 1 | 조이스틱으로 몰면 AME-2 는 안 느린데 우리 것은 「느리더라도 무거워」 | 계산 시간은 아님(측정). start 모드만 화면 그리기를 미루는 코드가 있어 60 Hz 화면에서 초당 약 10 번만 그린다 | 계산 시간: **측정** · 10 번 그리기: **코드 + 계산 모형으로 추정**, 브라우저 미확인 |
| 2 | 앞으로 누르면 우리 것만 「튀어 나간다」 | 막대를 밀면 명령이 0 → 1.5 m/s 로 한 번에 바뀌고(막대에는 가감속이 없음), 정책은 학습 때 계단 명령만 받아서 아주 빨리 따라간다 | **측정** (앱의 MuJoCo 코드를 그대로 돌림) |
| 3 | 목표(찍은 점) 모드에서 너무 느림. 0.3~0.8 m/s 로 정했던 기억 | 직진 속도가 앱 기본값 `sim_runner_vx` 0.4 m/s. 0.3~0.8 은 「걸으며 돌 때」 만 쓰는 범위 | 앱 값: **코드 확인** · 실제 속도 0.39~0.41 m/s: **측정** |

이 문서에서 쓰는 말:
- **측정**: 이 PC 에서 실제로 돌려서 잰 값. 어디서 어떻게 쟀는지 §1 에 적었습니다.
- **추정**: 코드를 읽고 계산으로 따진 것. 브라우저에서 다시 재야 확정입니다.
- **미확인**: 재지 않은 것.

---

## 1. 잰 숫자

### 1-1. 어떻게 쟀나

- 기계: AMD Ryzen Threadripper 7970X (이 PC). 폰이나 노트북은 이보다 느립니다. 그래서 **절대 시간보다 우리 대 AME-2 의 비율**을 보십시오.
- (가) ONNX 만: Python onnxruntime 1.31.0 CPU (`app_tuning_bench.py`), 그리고 앱과 같은 **onnxruntime-web 1.31.1 wasm 1 스레드**를 Node 에서 (`app_tuning_bench_wasm.mjs`). 입력은 각 묶음의 시험 벡터(평지 20 스텝)를 돌려 쓰고 GRU 상태를 되먹였습니다. 먼저 답을 아는 입력으로 확인했습니다: wasm 출력과 기대 출력의 차이 최대 1.9e-6.
- (나)(다) 앱 코드 그대로: 앱 `mobile/sim/` 의 `createSim` · `start-demo-sensors.js` · `policy-onnx.js` 를 **고치지 않고** Node 에서 불렀습니다(`app_tuning_sim_bench.mjs`). MuJoCo 는 `@mujoco/mujoco` 3.17.0(앱 배포와 같은 판), Go2 모델은 mujoco_menagerie `unitree_go2`(앱 빌드가 복사하는 RS-6 폴더 것과 같은지는 미확인), 장면은 앱의 `assets/warehouse`. 깊이 Worker 는 Node 에서 끄고 같은 광선 계산을 화면 쪽에서 돌려 시간만 쟀습니다.
- 못 잰 것: 브라우저의 화면 그리기(three.js), Worker 왕복 시간, 폰. 이것은 §3 의 브라우저 측정 조각으로 현민 님이 재 주십시오.

### 1-2. ONNX 자체 (가)

| 모델 | 파일 | 가중치 수 | 곱셈-덧셈(MAC) / 호출 | 입력 float 수 | CPU 1 스레드 중앙값 · p95 | **wasm 1 스레드 (앱과 같음)** 중앙값 · p95 |
|---|---|---|---|---|---|---|
| m6000 지도 켬 | 5.81 MB | 1.44 M | 35.6 M | 8,463 | 0.98 · 1.09 ms | **3.09 · 3.35 ms** |
| m6000 지도 끔 | 5.82 MB | 1.44 M | 35.6 M | 8,463 | 1.03 · 1.19 ms | **3.02 · 3.28 ms** |
| m13000 지도 켬 | 5.81 MB | 1.44 M | 35.6 M | 8,463 | 0.99 · 1.18 ms | **3.01 · 3.22 ms** |
| m13000 지도 끔 | 5.82 MB | 1.44 M | 35.6 M | 8,463 | 1.09 · 1.24 ms | **2.94 · 3.11 ms** |
| AME-2 | 5.04 MB | 1.25 M | 5.8 M | 1,180 | 0.32 · 0.34 ms | **0.53 · 0.57 ms** |

- 우리 모델은 AME-2 보다 연산이 약 **6 배**, wasm 시간이 약 **5.7 배**입니다. 입력도 7 배 큽니다. 차이의 대부분은 **깊이 60 × 60 두 장을 읽는 합성곱(Conv) 17.0 M MAC** 와 이력 · GRU 쪽 행렬곱(MatMul 15.9 M) 입니다.
- 「지도 켬 · 끔」 은 시간이 거의 같습니다(차이 0.1 ms 안). 지도 입력(32 × 16 = 512 칸)은 작습니다.
- 그래프 안에 조건 분기(If)가 없어서, 새 깊이가 없는 스텝(5 번 중 4 번)에도 깊이 합성곱을 매번 다 계산합니다(그래프 구조 확인. 따로 시간을 나눠 재지는 않음).
- 그래도 **20 ms 기한(50 Hz) 의 약 1/6** 입니다. 이 PC 에서는 여유가 큽니다.

### 1-3. 앱의 한 스텝을 셋으로 나누면 (가)(나)(다)

창고 장면, 0.6 m/s 로 6 초(300 스텝) 걷기. 앱 코드 그대로 (`result_app_sim.json`).

| 모드 | (가) 추론(앱 호출 경로: 입력 검사 + 실행 + 출력 검사) | (나) 높이 지도 512 광선 / 스텝 | (나) 깊이 3,600 광선 / 0.1 초에 한 번 | (다) 물리 4 번 / 스텝 | 한 스텝 합(깊이는 5 스텝 평균) |
|---|---|---|---|---|---|
| m6000 정답 지도 | 4.03 ms | 0.09 ms | 4.98 ms (스텝당 약 1.0) | 0.25 ms | **약 5.4 ms** |
| m6000 지도 끔 | 4.07 ms | 없음 | 4.75 ms | 0.23 ms | 약 5.3 ms |
| m13000 정답 지도 | 3.92 ms | 0.09 ms | 4.69 ms | 0.23 ms | 약 5.2 ms |
| m13000 지도 끔 | 3.85 ms | 없음 | 4.57 ms | 0.21 ms | 약 5.0 ms |
| AME-2 | 0.75 ms | 1.40 ms (377 광선) | 없음 | 0.21 ms | **약 2.4 ms** |

읽는 법:
- **높이 지도는 무겁지 않습니다.** 우리 지도 0.09 ms 는 AME-2 지도 1.40 ms 보다 오히려 빠릅니다(앱의 빠른 수직 광선 경로 `fastVertical` 덕).
- **깊이는 한 번에 약 5 ms** 지만 0.1 초에 한 번이고, 브라우저에서는 따로 Worker 에서 돕니다(`start-depth-worker.js`). 스텝당으로 나누면 약 1 ms.
- 앱 호출 경로의 추론(4.0 ms)이 순수 wasm 실행(3.0 ms)보다 약 1 ms 깁니다. `policy-onnx.js` 의 `inputData` 가 입력 8,463 개를 `Array.from(...).every(Number.isFinite)` 로 두 번 훑고 새 배열을 만들고, 출력도 같은 식으로 검사해서입니다(작은 비용).
- 한 스텝 합이 우리 약 5 ms, AME-2 약 2.4 ms. **둘 다 20 ms 기한 안이고, 이 PC 에서는 시뮬 시간이 벽시계를 따라갑니다.** 그래서 「깊이 · 높이 지도 구현 때문에 무겁다」 는 이 PC 숫자로는 **아닙니다.** 폰처럼 4~5 배 느린 기계라면 우리 쪽이 20 ms 에 닿을 수 있고, 그때는 Worker 가 늦은 결과를 버려 시뮬이 느려집니다(`policy-worker-client.js:22-31 · :41-44` · `frame-clock.js`). 폰은 **미확인** 이라 §3 의 조각으로 재야 합니다.

### 1-4. 출발 반응 (증상 2)

평지에서 2 초 서 있다가 앞으로. 앱 코드 그대로 (`result_app_sim.json` `launch`). 가속도는 0.1 초 평균 속도의 변화로 셌습니다.

| 정책 · 명령 | 최대 가속도 | 0.5 m/s 까지 | 첫 1 초 최고 속도 | 첫 1 초 몸 앞뒤 기울기 폭 | 1 초에 간 거리 |
|---|---|---|---|---|---|
| m6000 · **0 → 1.5 한 번에** (지금 막대) | **5.0 m/s²** | **0.10 초** | 1.56 m/s | 5.9° | 1.20 m |
| m13000 · 0 → 1.5 한 번에 | 4.7 m/s² | 0.10 초 | **1.73 m/s** (넘침) | **10.7°** | 1.21 m |
| m6000 · 0 → 0.8 한 번에 | 4.6 m/s² | 0.10 초 | 0.83 m/s | 4.7° | 0.67 m |
| m6000 · 1.5 까지 **1 초 램프** (지금 키보드와 같은 값) | 2.0 m/s² | 0.44 초 | 1.23 m/s | 6.7° | 0.53 m |
| m13000 · 1.5 까지 1 초 램프 | 3.0 m/s² | 0.52 초 | 1.30 m/s | 5.9° | 0.51 m |
| m6000 · 1.5 까지 2 초 램프 | 1.7 m/s² | 0.80 초 | 0.65 m/s | 4.2° | 0.27 m |
| m13000 · 1.5 까지 2 초 램프 | 2.6 m/s² | 0.94 초 | 0.72 m/s | 5.1° | 0.21 m |
| **AME-2 · 1 m 앞 목표** (지금 막대 끝까지) | **3.5 m/s²** | 0.14 초 | 1.10 m/s | 9.7° | 0.79 m |

읽는 법:
- 지금 막대를 끝까지 밀면 우리 정책은 **0.1 초 만에 0.5 m/s, 최대 가속 4.7~5.0 m/s²** 로 나갑니다. AME-2 는 3.5 m/s² 에 최고 속도도 1.1 m/s 라 덜 튀어 보입니다. m13000 은 첫 1 초에 1.73 m/s 까지 넘쳤다가 내려옵니다.
- **1 초 램프를 넣으면 최대 가속이 2.0~3.0 m/s² 로 AME-2 아래가 되고**, 1.0 초쯤에 목표 속도의 90 % 에 닿습니다. 2 초 램프는 더 부드럽지만 0.5 m/s 까지 0.8~0.9 초가 걸려 굼떠 보일 수 있습니다.
- 시드 하나 · 평지 한 판씩입니다. 경향은 분명하지만 소수점 끝자리는 판마다 흔들립니다.

**왜 이렇게 배웠나 (학습 쪽 확인).** 학습 명령은 4 초마다 새로 뽑아 **그 자리에서 바로 바꿉니다**(`mixed_command.py:221` `self.vel_command_b[group] = out["cmd"]`, `env.yaml` `resampling_time_range (4.0, 4.0)`). 램프나 가속 제한이 없습니다. 0 단계 표집은 서기 10 % · 전진 23 % (0.1~1.5 m/s 고르게) 등이라 「서 있다가 1.5 로」 같은 계단도 학습 중에 나옵니다(`ex42_application.jsonl` `stage_config.shares` · `ranges`). 그래서 정책은 계단 명령을 아주 빨리 따라가도록 배웠고, 앱이 계단을 그대로 주면 그대로 튀어 나갑니다. AME-2 는 속도가 아니라 「1 m 앞 목표」 를 받고 속도를 스스로 정하는 방식이라(`ame2-adapter.js:57-64` `ame2Joystick`) 이 문제가 덜합니다. **D108 이 정한 「앱 가속 제한」 이 아직 막대에 없는 것이 원인**입니다(`start-demo-app/CONTRACT.md` 맨 위 ⑥ 「미확인: 명령 가속 제한 값 · 정해질 때까지 가속 제한 없음」 을 이 문서 값으로 닫자는 제안).

### 1-5. 실제 속도 (증상 3)

평지, 명령을 8 초 유지, 마지막 4 초 평균 (`result_app_sim.json` `speed`).

| 명령 vx | 0.3 | **0.4 (지금 목표 모드)** | 0.8 | 1.2 | 1.5 |
|---|---|---|---|---|---|
| m6000 실제 | 0.32 | **0.41** | 0.69 | 1.05 | 1.36 m/s |
| m13000 실제 | 0.28 | **0.39** | 0.73 | 1.09 | 1.36 m/s |
| AME-2 · 1 m 앞 목표 | | | | | 1.05 m/s |

목표 모드에서 우리 것은 **0.4 m/s 로 가고**, AME-2 는 **1.05 m/s** 로 갑니다. 2.6 배 차이입니다. 팀장님이 기억한 0.3~0.8 은 앱 `scenario.js:105` 의 「걸으며 돌 때(|wz| ≥ 0.2) 속도 범위」 이고, 곧게 갈 때의 속도는 아래처럼 0.4 로 정해집니다.

---

## 2. 증상별 원인 (코드 자리)

### 2-1. 「무거움」 (증상 1)

**측정으로 배제한 것.** 추론 · 높이 지도 · 깊이 · 물리를 합쳐 한 스텝 약 5 ms(§1-3). 이 PC 에서 시뮬은 실제 시간과 같은 속도로 돕니다. 깊이 · 지도 구현이 계산을 무겁게 만든다는 가설은 이 PC 숫자로는 맞지 않습니다. 조종 반응도 느리지 않습니다(명령을 주면 0.1 초에 0.5 m/s, §1-4). 즉 「느리지는 않은데 무겁다」 는 계산 지연이나 둔한 반응이 아닙니다.

**가장 유력한 원인 (추정).** `main.js:972-981` 의 화면 루프:

```js
// main.js:978-980 (dev 2f1ef45)
if (adapter.depth) {
  clock.frame(now, ...);
  if (clock.stats.pending && performance.now() - lastDrawAt < START_DRAW_MAX_GAP_MS) { timingUI(); requestAnimationFrame(frame); return; }
}
```

start 모드(`adapter.depth` 있음)만, **이번 화면 틀에서 정책 계산을 하나라도 보냈으면 그리기를 건너뜁니다**(최대 100 ms 까지). 정책 계산은 늘 비동기(Promise)라 보낸 바로 다음 줄에서 `pending` 은 반드시 true 입니다. 60 Hz 화면에서 50 Hz 정책을 돌리면 6 틀 중 5 틀에 계산을 보내므로, **그리는 틀은 6 번에 1 번, 초당 약 10 번**이 됩니다. AME-2 는 `adapter.depth` 가 없어서 이 분기를 타지 않고 매 틀 그립니다(초당 60 번).

앱의 `frame-clock.js` 를 그대로 가상 시계에 넣어 계산해 보면(`app_tuning_frameloop_sim.mjs`, 계산 모형):

| 추론 왕복 시간 | 1 · 3 · 5 · 8 · 12 · 16 ms | 19 ms | 25 ms (기한 넘음) |
|---|---|---|---|
| start 경로(그리기 미룸) 초당 그리기 | **10.1** | 9.5 | 9.5 |
| AME-2 경로 초당 그리기 | 60.1 | 60.1 | 60.1 |
| 시뮬 속도(1 = 실제 시간) | 1.00 | 1.00 | **0** (모든 결과가 늦어 버려짐) |

추론이 아무리 빨라도 start 는 초당 약 10 번만 그립니다. 몸은 제 속도로 움직이는데 화면이 뚝뚝 끊겨 보이면 「느리지는 않은데 무겁다」 로 느껴질 수 있습니다. 이 코드는 `4d1316c` (11/04 「bound start redraw deferral」) 에서 헤드리스 SwiftShader 시험의 20 ms 기한을 지키려고 넣은 것입니다. 120 Hz 화면에서는 초당 약 70 번이 되므로 기기마다 느낌이 다를 수 있습니다.

**확인할 것 (미확인).** 이것이 팀장님이 본 「무거움」 의 원인인지는 브라우저에서 §3 의 조각으로 `fps` 를 재야 확정입니다. 화면 그리기 비용과 Worker 왕복 시간도 브라우저에서만 잴 수 있습니다. 걸음새 자체(발 디딤 · 몸 높이)가 무겁게 보이는 것일 가능성도 남아 있고, 이것은 재지 않았습니다.

### 2-2. 「튀어 나감」 (증상 2)

- 막대: `main.js:148-152` `updateStickAxes` 가 막대 값을 `manualCommand` 로 바로 `joy` 에 쓰고, `main.js:957` 이 다음 스텝에 그대로 `sim.cmd` 로 보냅니다. 막대를 끝까지 밀면 다음 20 ms 스텝에 명령이 0 에서 **1.5 m/s** 가 됩니다(`manual-settings.js:9` start 전진 상한 1.5).
- 키보드에는 이미 램프가 있습니다(`keyboard-ramp.js:2` `START_KEYBOARD_RAMP = { translation: 1, turn: 0.5, release: 0.4 }`, `cc75cf3` 11/04). 그런데 막대는 이 램프를 **끕니다**(`main.js:149` `keyboardRamp.reset()`, 이후 `prepare` 의 램프 갱신은 `keyboardActive` 일 때만, `main.js:944`).
- 찍은 점 가기도 같습니다. `scenario.js:84,107` 이 첫 스텝부터 `[maxVx, 0, wz]` 를 냅니다(지금은 0.4 라 덜 보일 뿐, 속도를 올리면 똑같이 튑니다).
- 학습은 계단 명령만 받았습니다(§1-4). 정책이 이상한 것이 아니라 **배운 대로** 움직입니다.

### 2-3. 「목표 모드가 느림」 (증상 3)

- `scenario.js:56` `maxVx = min(sim_runner_vx, 상한)`. `sim_runner_vx` 의 기본값은 **0.4** 입니다(`settings.js:2` `DEFAULT_VX = 0.4` · `settings.js:19`, 서버 쪽 기본도 `apps/contracts/models.py:520` `default=0.4`). 웹에서 연 시뮬(`?from=web`)은 조직 설정 값을 쓰고, 모델별 덮어쓰기(`model_overrides`)가 있으면 그 값을 씁니다(`settings.js:9-12`).
- `scenario.js:83-84`: 방향 오차가 0.4 rad(23°) 이상이면 **멈춰서 제자리 회전**(vx 0) 한 뒤 다시 갑니다. 길이 꺾일 때마다 서므로 평균 속도는 0.4 보다 더 낮아집니다(평균 속도는 재지 않음).
- `scenario.js:102-105`: start 는 걸으며 돌 때(|wz| ≥ 0.2) 속도를 0.3~0.8 로 맞춥니다(학습 `walk_vx` 0.3~0.8 그대로, 앞 문서 §1.5 ④ 대로 잘 들어가 있음). 다만 `min(maxVx, ...)` 라서 maxVx 가 0.4 면 결국 0.4 입니다.
- AME-2 는 목표만 주고 속도는 정책이 정해서 1.05 m/s 로 갑니다.

---

## 3. 브라우저에서 먼저 재 주십시오 (고치기 전 · 고친 뒤 둘 다)

앱에 이미 있는 `window.__sim` (`main.js:920-921`) 만 씁니다. 시뮬을 열고(`?policy=start-demo` 와 `?policy=ame2-demo` 각각), 「시작」 을 누르고, 막대나 ↑ 키로 앞으로 걷게 한 상태에서 개발자 도구 콘솔에 붙여 넣습니다. 5 초 동안 잽니다.

```js
(async () => {
  const s = window.__sim, n0 = s.steps, t0 = performance.now(), pol = [], dep = [], map = [];
  const iv = setInterval(() => {
    pol.push(s.sim.policyMs);                                   // 관측 만들기 + Worker 왕복 + 추론
    if (s.sim.depthScanner?.roundtripMs) dep.push(s.sim.depthScanner.roundtripMs);  // start 깊이 Worker 왕복
    if (s.sim.heightScanner?.ms) map.push(s.sim.heightScanner.ms);                  // start 높이 지도
  }, 50);
  await new Promise((r) => setTimeout(r, 5000)); clearInterval(iv);
  const sec = (performance.now() - t0) / 1000, med = (a) => a.length ? [...a].sort((x, y) => x - y)[a.length >> 1].toFixed(2) : '-';
  console.table({ fps: s.fps(), stepsPerSec: ((s.steps - n0) / sec).toFixed(1), simSpeed: ((s.steps - n0) * 0.02 / sec).toFixed(2),
    policyMs: med(pol), depthRoundtripMs: med(dep), mapMs: med(map), cmd: s.cmd().join(', '), engine: s.policyEngine, ...s.timing() });
})();
```

읽는 법:
- `fps`: 화면을 초당 몇 번 그렸나. **start 가 10 안팎이고 AME-2 가 60 안팎이면 §2-1 의 추정이 맞습니다.**
- `stepsPerSec` 50 · `simSpeed` 1.00 이면 계산이 기한 안입니다. 이보다 낮으면 계산이 밀리는 것이고, 그때 `policyMs` 가 20 에 가까운지 봅니다.
- `engine` 이 「Worker」 인지 「Worker 늦음 → 화면 계산」 인지도 적어 주십시오.
- 폰(Android 앱)에서도 같은 값을 재 주시면 §1-3 의 「폰에서는?」 이 닫힙니다.

---

## 4. 고칠 것 · 순서대로

모두 앱 `mobile/sim/` 안입니다. 하나 고칠 때마다 §3 조각과 각 항목의 「확인」 을 돌려 주십시오.

### ① 화면 그리기 미루기를 「밀렸을 때만」 으로 (증상 1 · 효과 가장 클 것으로 추정)

`main.js:978-980` 의 조건에 「시뮬이 실제로 밀리고 있을 때」 를 더합니다. `frame-clock.js:51` 의 `stats.slow` (밀린 시간 0.1 초 이상이거나 버린 시간이 있음)를 그대로 씁니다.

```js
// main.js:980 바꾸기 전
if (clock.stats.pending && performance.now() - lastDrawAt < START_DRAW_MAX_GAP_MS) { timingUI(); requestAnimationFrame(frame); return; }
// 바꾼 뒤: 밀리지 않으면 매 틀 그린다. 밀릴 때만 지금처럼 최대 100 ms 미룬다
const stats = clock.stats;
if (stats.pending && stats.slow && performance.now() - lastDrawAt < START_DRAW_MAX_GAP_MS) { timingUI(); requestAnimationFrame(frame); return; }
```

- 왜 이것인가: 미루기는 「느린 기계에서 그리기가 추론 Worker 와 다툴 때」 를 위해 넣은 것(`4d1316c`)이라, 밀리지 않을 때까지 미룰 까닭이 없습니다.
- 확인: §3 조각에서 start `fps` 가 60 안팎(화면 주사율 근처)으로 오르고, `stepsPerSec` 이 50 · `simSpeed` 1.00 그대로인지. 헤드리스 시험(`policy-onnx-headless.mjs` 등 SwiftShader)에서 「시뮬 느림」 이 새로 뜨지 않는지. 뜨면 이 조건을 `stats.debt >= POLICY_DT` 정도로 조금 넓힙니다.

### ② 막대 · 찍은 점 가기 명령에 가감속 제한 (증상 2)

키보드에만 있는 램프를 **모든 사람 명령의 마지막 자리**에 한 번 겁니다. 값은 지금 키보드 램프(`START_KEYBOARD_RAMP`)를 m/s 단위로 바꾼 것입니다. 앞뒤 1.5 m/s² (0 → 1.5 에 1 초), 옆 0.5 m/s² (0 → 0.5 에 1 초), 회전 2.4 rad/s² (0 → 1.2 에 0.5 초), 줄일 때는 0.4 초에 끝(앞뒤 3.75 · 옆 1.25 m/s² · 회전 3.0 rad/s²).

`keyboard-ramp.js` 에 더하기:

```js
// 사람 명령(막대 · 키 · 찍은 점 가기) → 정책 명령의 마지막 가감속 제한. 단위 m/s², rad/s². STOP 은 이것을 거치지 않는다.
export const START_COMMAND_SLEW = Object.freeze({ up: [1.5, 0.5, 2.4], down: [3.75, 1.25, 3.0] });
export function slewCommand(previous, target, dt, slew) {
  return target.map((goal, i) => {
    const from = previous[i] ?? 0;
    const slowing = Math.abs(goal) < Math.abs(from) || from * goal < 0;   // 줄이거나 방향을 바꿈
    const limit = (slowing ? slew.down[i] : slew.up[i]) * dt;
    return from + Math.max(-limit, Math.min(limit, goal - from));
  });
}
```

`start-demo-adapter.js:58` 의 `command` 에 한 칸 더하기:

```js
command: { kind: 'body_velocity', caps: MODE_COMMAND_CAPS.start, keyboardRamp: START_KEYBOARD_RAMP, slew: START_COMMAND_SLEW, inRange: ... },
```

`main.js` 의 `prepare` (`main.js:941-959`) 끝, `skipLockedDecision = ...` 바로 앞에 넣기:

```js
// body_velocity 모드에서 사람 명령(막대 · 키 · runner)이 정한 sim.cmd 를 마지막에 한 번 부드럽게. STOP(잠금)은 바로 0.
if (adapter.command.slew && adapter.command.kind === 'body_velocity' && !patrol.active) {
  sim.cmd = stopped ? neutral() : slewCommand(lastCmd, sim.cmd, POLICY_DT, adapter.command.slew);
  lastCmd = sim.cmd.slice();
}
```

그리고 `let lastCmd = neutral();` 을 `joy` 선언 근처(`main.js:58`)에 두고, `lock()` (`main.js:62-69`) 과 `#reset` (`main.js:882`) 에서 `lastCmd = neutral();` 로 비웁니다.

- 왜 마지막 자리인가: 막대 · 키 · 찍은 점 가기가 모두 `sim.cmd` 로 모이므로 한 곳에 걸면 셋 다 같은 느낌이 됩니다. 키보드 램프와 값이 같아서 키보드는 지금과 느낌이 같습니다.
- 왜 STOP 은 빼나: 정지는 안전 동작이라 늦추지 않습니다(학습에도 계단 정지가 있음).
- 측정 근거: 1 초 램프에서 최대 가속 2.0 (m6000) · 3.0 (m13000) m/s², AME-2 3.5 m/s² 보다 낮음(§1-4).
- 확인: ① 콘솔에서 `setInterval(() => console.log(__sim.cmd()[0].toFixed(2)), 100)` 를 켜고 막대를 끝까지 밀면 0.15 씩 올라 1 초 뒤 1.5 에 닿는지. ② 놓으면 약 0.4 초(21 스텝)에 0. 반대로 밀면 0 을 지나 방향을 바꾼다(1.5 → −1 에 약 1 초). ③ STOP 은 바로 0. ④ 눈으로: 앞으로 밀 때 튀어 나가지 않는지. ⑤ 앱 시험(`start-demo-selftest.mjs` 등)에 「막대 끝까지 → 첫 스텝 vx 0.03, 50 스텝 뒤 1.5」 단언 하나를 더합니다.

### ③ 찍은 점 가기의 start 기본 속도 (증상 3)

- 직진 속도를 **1.2 m/s** 로 올립니다. 측정상 1.2 명령이면 실제 1.05~1.09 m/s 로 AME-2 목표 모드(1.05 m/s)와 비슷합니다(§1-5). 학습 전진 범위 0.1~1.5 안입니다.
- 걸으며 돌 때는 지금처럼 0.3~0.8 그대로 둡니다(`scenario.js:105`, 학습 `walk_vx` 0.3~0.8).
- 앱 쪽 기본값을 모드별로 둡니다. `settings.js:19` 의 기본값을 모드가 줄 수 있게:

```js
// settings.js:19 바꾸기 전
vx: boundedNumber(o.sim_runner_vx, 0.1, 1.5, DEFAULT_VX),
// 바꾼 뒤: 모드가 기본 직진 속도를 주면 그것을 기본으로(조직 설정 · 모델별 덮어쓰기가 있으면 그것이 이긴다)
vx: boundedNumber(o.sim_runner_vx, 0.1, 1.5, caps.runnerVx ?? DEFAULT_VX),
```

`main.js:265` 에서 `simSettings(org, { vx: caps.forward, wz: caps.turnInPlace, runnerVx: adapter.command.runnerVx }, adapter.id)` 로 넘기고, `start-demo-adapter.js:58` `command` 에 `runnerVx: 1.2` 를 더합니다.

- **웹에서 연 시뮬(`?from=web`) 주의**: 서버 조직 설정이 `sim_runner_vx: 0.4` 를 값으로 돌려주면 그것이 이깁니다(`models.py:520` 기본 0.4). 콘솔에서 `await (await fetch('/api/v1/org/settings')).json()` 으로 `sim_runner_vx` 와 `model_overrides` 를 보고, 값이 있으면 설정 화면에서 start 모델 덮어쓰기(`model_overrides['start-demo'].sim_runner_vx = 1.2`)를 넣어 주십시오. 서버 기본값을 바꿀지는 현민 님 판단입니다(nvidia 모드도 이 값을 같이 씁니다).
- 목표 근처에서 너무 빠르면(지나쳐서 되돌아오는 일) 남은 거리로 줄이는 한 줄을 더합니다. 이 값은 재지 않은 제안입니다:

```js
// scenario.js:105 다음 줄 (start 만)
speed = Math.min(speed, Math.max(0.3, dist));   // 1 m 안에서는 남은 거리만큼(m/s), 최소 0.3
```

- ②의 가감속 제한이 runner 명령에도 걸리므로, 1.2 로 올려도 출발은 튀지 않습니다.
- 확인: ① 평지에서 5 m 앞을 찍고 걸린 시간을 잽니다(지금 약 13 초 → 바꾼 뒤 6 초 안팎 예상, 미확인). ② `__sim.cmd()` 가 곧게 갈 때 1.2, 꺾을 때 0.3~0.8 인지. ③ 도착 판정(0.3 m)에서 지나치지 않는지. ④ `?from=web` 에서도 같은지.

### ④ (선택) 꺾을 때 멈추지 않게

`scenario.js:83` 의 「0.4 rad 이상이면 멈춰서 돌기」 때문에 길이 꺾일 때마다 섭니다. 1.0 rad 까지는 걸으며 돌게(vx 0.3~0.8, wz 는 지금처럼 `turnWalking` 1.0 안) 넓히면 더 빨라질 수 있습니다. 학습 「걸으며 회전」 범위(wz 0.2~1.0 · vx 0.3~0.8) 안이지만, 좁은 통로에서 벽에 붙을 수 있어 재지 않고는 권하지 않습니다. ③ 뒤에도 느리면 그때 해 봅니다.

### ⑤ (작은 것) 입력 검사 비용

`policy-onnx.js:5-17` `inputData` 가 매 호출 입력 8,463 개를 `Array.from` 으로 두 번 복사해 검사합니다(앱 호출 경로 4.0 ms 대 순수 실행 3.0 ms, §1-3). 지금은 기한 안이라 급하지 않습니다. 폰에서 `policyMs` 가 20 ms 근처로 나오면 그때 `Float32Array` 는 `for` 반복 한 번으로 검사하도록 줄입니다.

---

## 5. 우리(모델 · 학습) 쪽에서 바꿀 것

- **지금 바꿀 것 없음.** 세 증상 모두 앱 쪽 값으로 풀립니다. 정책은 학습한 대로 움직이고 있습니다.
- 가감속 제한은 앱 몫으로 둡니다(D108 「앱 가속 제한」). 위 ② 값(앞뒤 1.5 m/s² · 회전 2.4 rad/s²)을 우리 쪽 결정 기록에 「앱 가속 제한 값」 으로 올려 `start-demo-app/CONTRACT.md` 맨 위 ⑥ 「미확인」 을 닫자고 lead 에 제안합니다(이 PR 은 문서만 더함, 계약 문서는 고치지 않음).
- 지켜볼 것 (추정 · 미확인): m13000 은 계단 명령에서 m6000 보다 몸이 더 흔들립니다(첫 1 초 앞뒤 기울기 폭 10.7° 대 5.9°, 최고 속도 1.73 대 1.56, §1-4 · 한 판). m13000 은 W86 에서 `lin_vel_z` 벌점을 −2.0 → 0 으로 껐는데 이것과 관련 있는지는 재지 않았습니다. 램프를 넣으면 5.9° 로 m6000 과 비슷해집니다.
- 폰에서 계산이 20 ms 에 닿는다고 나오면(§3), 그때는 우리 쪽에서 줄일 수 있습니다: 깊이 합성곱(17 M MAC, 전체의 절반)이 새 깊이가 없는 스텝에도 매번 돕니다. 깊이 특징을 0.1 초에 한 번만 계산해 두는 형태로 ONNX 를 다시 내보내면 호출당 연산이 크게 줍니다. 지금 이 PC 숫자로는 필요 없어서 하지 않습니다.
- 지금 앱(`dev` `2f1ef45`)은 m6000(`start-demo`) 을 씁니다(`start-demo-adapter.js:10-22`). 팀장님 관찰도 m6000 이었을 가능성이 큽니다(현민 님 로컬에서 m13000 으로 바꿨는지는 미확인). 위 숫자는 둘 다 쟀고 결론은 같습니다.

---

## 6. 미확인

- 미확인: 브라우저 · 폰의 `fps` · `policyMs` · Worker 왕복 · 화면 그리기 시간. 정해질 때까지 §2-1 의 「초당 10 번 그리기」 는 추정이고, §3 조각으로 재면 닫힙니다.
- 미확인: 「무거움」 이 그리기 횟수 때문인지, 걸음새(발 디딤 · 몸 높이 · 흔들림) 때문인지. ① 을 고친 뒤에도 무거우면 걸음새 쪽을 따로 봅니다.
- 미확인: 앱 빌드가 쓰는 Go2 모델 파일(RS-6 폴더)과 이 측정에 쓴 mujoco_menagerie `unitree_go2` 가 같은지. 물리 시간 · 출발 반응 숫자가 조금 달라질 수 있습니다.
- 미확인: 출발 반응은 평지 · 시드 하나 · 한 판씩입니다. 거친 지형 · 계단에서의 반응은 재지 않았습니다.
- 미확인: ③ 의 목표 근처 감속 줄과 ④ 는 재지 않은 제안입니다.
- 미확인: 꺾을 때 멈추는 것(④)이 목표 모드 평균 속도를 얼마나 깎는지.

## 7. 다시 재는 법

`app-tuning-1109/` 의 스크립트 넷과 결과 셋. 모두 CPU 만 씁니다.

| 파일 | 무엇 |
|---|---|
| `app_tuning_bench.py` | ONNX 크기 · 가중치 수 · MAC · Python onnxruntime CPU 시간(1 스레드 · 기본 스레드, 500 번) → `result_cpu_ort.json` |
| `app_tuning_bench_wasm.mjs` | 앱과 같은 onnxruntime-web 1.31.1 wasm 1 스레드 시간(500 번) → `result_wasm_ort_web.json` |
| `app_tuning_sim_bench.mjs` | 앱 `mobile/sim` 코드를 그대로 불러 시간 나누기 · 출발 반응 · 실제 속도 → `result_app_sim.json` |
| `app_tuning_frameloop_sim.mjs` | 앱 `frame-clock.js` + `main.js` 그리기 미루기 규칙의 가상 시계 계산(초당 그리기 · 시뮬 속도) |

각 스크립트 맨 위에 쓰는 법(환경 변수)이 있습니다. 앱 저장소는 `dev` 를 읽기 전용으로 받아 썼고, 앱 저장소에는 아무것도 올리지 않았습니다.
