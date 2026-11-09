> 분류: A/정책학습 · 앱 작업 지시서 (agent 에 그대로 붙여 넣는 한 장 · start 모드)
> 작성: 오흥재 · lead 세션 · 2026-11-09 11:1x v0.1
> 근거: 측정과 원인 [`APP-TUNING-1109.md`](APP-TUNING-1109.md) · 묶음 `start-m13000-app/` (lab `feature/verify-v2-mvp-jay` · 원격 커밋 `c9470ba0`) · foothold-app `dev` `2f1ef45` 줄 번호(읽기만 함) · 팀장 11/09 11:0x 「문서 하나만 보고 자기 agent 가 따라 할 수 있게」
> 요지: 여섯 단계를 순서대로 한다. ① start 정책을 m6000 에서 m13000 으로 바꾸기 ② start 화면 그리기 미루기 고치기 ③ 모든 사람 명령에 가감속 제한 ④ 목표 모드 직진 1.2 m/s ⑤ 고치기 전 · 뒤 숫자 재기 ⑥ 보고. 단계마다 「할 일 · 바꿀 파일:줄 · 확인 · 안 되면」 이 있다
> 상태: v0.1 · 지시서 · 앱에 적용 전 · 브라우저 · 폰 숫자는 ⑤ 에서 처음 잰다

# 앱 작업 지시서 · start 모드 (11/09)

**쓰는 법: 이 문서를 통째로 agent 에 붙여 넣으면 됩니다.** 대상 저장소는 `foothold-project/foothold-app`, 가지는 `dev` 입니다(줄 번호는 `dev` `2f1ef45` 기준. 그 뒤 커밋으로 줄이 밀렸으면 같은 코드를 찾아서 고칩니다). 새 작업 가지를 `dev` 에서 따서 하고, 단계마다 커밋을 하나씩 나눕니다.

왜 고치는지(측정 숫자 · 원인)는 [`APP-TUNING-1109.md`](APP-TUNING-1109.md) 에 있습니다. 이 지시서는 「무엇을 어떻게」 만 적습니다.

**다음 판(E0 · E1 …) 이 나오면 ① 만 폴더 이름(`start-m13000-app` → 새 폴더)과 파일 이름 · sha 를 바꿔 그대로 반복합니다.** ②~④ 는 한 번만 하면 됩니다.

시작 전에 ⑤ 의 콘솔 조각으로 「고치기 전」 숫자를 먼저 재 두십시오. 그래야 뒤와 견줄 수 있습니다.

---

## ① start 정책 교체: m6000 → m13000

**할 일.** start 모드가 읽는 ONNX 두 파일을 m13000 것으로 바꾸고, 후진 상한을 1.0 → 1.3 으로 올립니다. ONNX 입출력(이름 9 · 4, 순서, 모양, bool 플래그 셋)은 m6000 과 **같아서** 실행기 · 상태 되먹임 코드는 고치지 않습니다(두 묶음의 `contract.json` `app_onnx.inputs` 가 같음을 확인함).

**받을 파일.** lab 저장소 `feature/verify-v2-mvp-jay` 가지, 폴더 `inbox/jay/20261103-policy-handoff/start-m13000-app/` (원격 커밋 `c9470ba0` 에 있음. 아래 링크는 `gh api` 로 200 확인)

- 폴더: https://github.com/foothold-project/foothold-lab/tree/feature/verify-v2-mvp-jay/inbox/jay/20261103-policy-handoff/start-m13000-app
- 조건표: https://github.com/foothold-project/foothold-lab/blob/feature/verify-v2-mvp-jay/inbox/jay/20261103-policy-handoff/start-m13000-app/CONTRACT.md

받는 명령(LFS 아님, 일반 파일):

```sh
mkdir -p start-m13000-app && cd start-m13000-app
P=inbox/jay/20261103-policy-handoff/start-m13000-app
for f in start-m13000_map_on.onnx start-m13000_map_off.onnx contract.json SHA256SUMS \
         test_vectors_flat20_reconstruction.json test_vectors_flat20_gt.json test_vectors_flat20_off.json; do
  gh api -H "Accept: application/vnd.github.raw" "repos/foothold-project/foothold-lab/contents/$P/$f?ref=c9470ba0" > "$f"
done
sha256sum start-m13000_map_on.onnx start-m13000_map_off.onnx
```

맞는 sha:

| 파일 | sha256 |
|---|---|
| `start-m13000_map_on.onnx` | `4799677acdc9fbc22da28fd56fefa3181f24b38b198e3bea02270c1c1cd11d93` |
| `start-m13000_map_off.onnx` | `8317548f51a046afb537c212eec47a12b2888b6ea049fa84361d83aa8c30849f` |

**바꿀 파일:줄.**

| 파일:줄 | 지금 | 바꾼 뒤 |
|---|---|---|
| `mobile/sim/start-demo-adapter.js:11-16` `START_DEMO_ONNX` | `file` · `files` · `sha256` 가 `start-demo_map_on/off.onnx` · `81c7e079…` · `5d1b7bf3…` | `start-m13000_map_on.onnx` (gt · reconstruction) · `start-m13000_map_off.onnx` (off) · 위 sha 둘 |
| `mobile/sim/start-demo-adapter.js:58` `inRange` | `c[0] >= -1` | `c[0] >= -1.3` |
| `mobile/sim/manual-settings.js:9` `MODE_COMMAND_CAPS.start` | `reverse: 1` | `reverse: 1.3` |
| `mobile/scripts/policy-vector-selftest.mjs:26-27` `approved` | m6000 파일 이름 · sha | m13000 파일 이름 · sha |
| `mobile/scripts/policy-command-caps-selftest.mjs:32` · `:49` | 후진 끝 값 `-1` · 글자 `뒤1` | `-1.3` · `뒤1.3` |
| `deploy/prepare_sim.py:21-22` `ONNX_SHA` · `deploy/tests/test_prepare_sim.py:114` | m6000 이름 · sha | m13000 이름 · sha |
| `docs/POLICY-PROVENANCE.md:9-10` | m6000 줄 | m13000 줄 (크기 5813202 · 5823033 바이트, 근거 = 위 폴더 `CONTRACT.md`) |

모드 id `start-demo` 와 메뉴 이름은 그대로 둡니다(URL `?policy=start-demo` 가 깨지지 않게). 바꾼 뒤 `grep -rn "start-demo_map\|81c7e079\|5d1b7bf3" .` 이 0 줄이어야 합니다.

**확인.** 앱의 시험 벡터 시험을 새 폴더로 돌립니다(외부 경로는 각자 환경 값).

```sh
FH_START_SRC=<받은 start-m13000-app 폴더> FH_AME2_SRC=<ame2-demo-app 폴더> FH_AME2_F32_SRC=<ame2 f32 폴더> \
POLICY_ORT_NODE=<onnxruntime-node> FH_ORT_WEB=<onnxruntime-web> FH_PLAYWRIGHT=<playwright> \
node mobile/scripts/policy-vector-selftest.mjs
node mobile/scripts/policy-command-caps-selftest.mjs
FH_START_SRC=<받은 start-m13000-app 폴더> FH_SIM_SRC=<RS-6 폴더> node mobile/scripts/sync-web.mjs
```

- `policy-vector-selftest` 가 start 세 경우(reconstruction · gt · off)를 허용 오차 1e-4 안에서 통과해야 합니다. lab 이 CPU 에서 잰 최대 차이는 3.46e-6 입니다(`start-m13000-app/CONTRACT.md` §2).
- 시뮬을 열면 상태 글에 `start · ONNX WASM · Worker` 가 보이고, 막대를 뒤로 끝까지 당기면 `__sim.cmd()[0]` 가 `-1.3` 이어야 합니다.

**안 되면.**
- `unapproved model SHA` · `SHA-256 불일치`: 받은 파일 sha 를 다시 봅니다. 브라우저 캐시에 옛 파일이 남았으면 강력 새로고침.
- 입력 이름 · 모양 오류: `contract.json` 의 `app_onnx.inputs` 와 `START_DEMO_ONNX.inputs` 를 나란히 놓고 봅니다(같아야 정상). 다르면 고치지 말고 lab 에 알립니다.
- 숫자 차이가 1e-4 를 넘음: 시험 벡터 파일이 m13000 것인지(`test_vectors_flat20_*.json` 의 `onnx` 칸이 `start-m13000_*`) 봅니다. 그래도 넘으면 멈추고 보고합니다.

---

## ② start 화면 그리기 미루기 고치기

**할 일.** start 모드는 「이번 화면 틀에서 정책 계산을 보냈으면 그리기를 건너뛴다」 는 규칙 때문에 60 Hz 화면에서 초당 약 10 번만 그립니다(코드와 계산 모형으로 본 추정, AME-2 는 60 번). 시뮬이 실제로 밀릴 때만 미루도록 바꿉니다.

**바꿀 파일:줄.** `mobile/sim/main.js:980`

```js
// 바꾸기 전
if (clock.stats.pending && performance.now() - lastDrawAt < START_DRAW_MAX_GAP_MS) { timingUI(); requestAnimationFrame(frame); return; }
// 바꾼 뒤: 밀리지 않으면 매 틀 그린다. 밀릴 때(stats.slow, frame-clock.js:51)만 지금처럼 최대 100 ms 미룬다
const stats = clock.stats;
if (stats.pending && stats.slow && performance.now() - lastDrawAt < START_DRAW_MAX_GAP_MS) { timingUI(); requestAnimationFrame(frame); return; }
```

**확인.** ⑤ 조각에서 start 의 `fps` 가 화면 주사율 근처(60 Hz 화면이면 55 이상)로 오르고, `stepsPerSec` 50 · `simSpeed` 1.00 이 그대로인지. 헤드리스 시험(`policy-onnx-headless.mjs` 등)이 그대로 통과하는지.

**안 되면.**
- `fps` 가 그대로 10 안팎: 이 줄이 실제로 바뀌어 배포됐는지(`www/sim/main.js`), `sync-web` 을 다시 돌렸는지 봅니다.
- `fps` 는 올랐는데 `simSpeed` 가 1 아래로 떨어짐(느린 기계): 조건을 `stats.debt >= POLICY_DT` 로 바꿔 조금 일찍 미루게 하고 다시 잽니다. 그래도 떨어지면 그 숫자를 보고합니다.
- 고친 뒤에도 「무겁다」 면 원인이 그리기가 아니라 걸음새일 수 있습니다. 그대로 보고합니다(lab 이 따로 봅니다).

---

## ③ 모든 사람 명령에 가감속 제한

**할 일.** 지금 키보드에만 램프가 있고 막대 · 찍은 점 가기는 명령이 0 → 1.5 m/s 로 한 번에 바뀝니다. 그래서 「튀어 나감」 이 납니다(측정: 최대 가속 4.7~5.0 m/s², 1 초 램프면 2.0~3.0 m/s², AME-2 는 3.5). 사람 명령이 모이는 마지막 자리(`sim.cmd`)에 한 번 겁니다. 값은 지금 키보드 램프(`keyboard-ramp.js:2` `START_KEYBOARD_RAMP`)를 m/s 단위로 바꾼 것입니다. STOP 은 거치지 않고 바로 0 입니다.

**바꿀 파일:줄.**

1. `mobile/sim/keyboard-ramp.js` 끝에 더하기:

```js
// 사람 명령(막대 · 키 · 찍은 점 가기) → 정책 명령의 마지막 가감속 제한. 단위 m/s², rad/s². STOP 은 이것을 거치지 않는다.
// up = 늘릴 때 [앞뒤, 옆, 회전], down = 줄이거나 방향을 바꿀 때. START_KEYBOARD_RAMP(1 초 · 0.5 초 · 놓을 때 0.4 초)와 같은 느낌.
export const START_COMMAND_SLEW = Object.freeze({ up: [1.5, 0.5, 2.4], down: [3.75, 1.25, 3.0] });
export function slewCommand(previous, target, dt, slew) {
  return target.map((goal, i) => {
    const from = previous[i] ?? 0;
    const slowing = Math.abs(goal) < Math.abs(from) || from * goal < 0;
    const limit = (slowing ? slew.down[i] : slew.up[i]) * dt;
    return from + Math.max(-limit, Math.min(limit, goal - from));
  });
}
```

2. `mobile/sim/start-demo-adapter.js:58` 의 `command` 에 `slew: START_COMMAND_SLEW` 를 더하고, `:3` import 에 `START_COMMAND_SLEW` 를 더합니다(`import { START_KEYBOARD_RAMP, START_COMMAND_SLEW } from './keyboard-ramp.js';`).

3. `mobile/sim/main.js`:
   - `:21` import 에 `slewCommand` 를 더합니다(`import { createKeyboardRamp, slewCommand } from './keyboard-ramp.js';`).
   - `:58` `let joy = neutral(), …` 다음 줄에 `let lastCmd = neutral();`
   - `:62-69` `lock()` 안 `joy = neutral();` 옆에 `lastCmd = neutral();`
   - `prepare` 안 `:958` `skipLockedDecision = epoch !== startEpoch;` **바로 앞**에:

```js
// body_velocity 모드: 막대 · 키 · runner 가 정한 sim.cmd 를 마지막에 한 번 부드럽게. STOP(잠금)은 바로 0.
if (adapter.command.slew && adapter.command.kind === 'body_velocity' && !patrol.active) {
  sim.cmd = stopped ? neutral() : slewCommand(lastCmd, sim.cmd, POLICY_DT, adapter.command.slew);
  lastCmd = sim.cmd.slice();
}
```

4. 시험 하나 더하기(새 파일 `mobile/scripts/command-slew-selftest.mjs` 또는 기존 `policy-command-caps-selftest.mjs` 끝):

```js
import assert from 'node:assert/strict';
import { slewCommand, START_COMMAND_SLEW as S } from '../sim/keyboard-ramp.js';
let c = [0, 0, 0];
c = slewCommand(c, [1.5, 0, 1], .02, S); assert.deepEqual(c.map((v) => +v.toFixed(3)), [0.03, 0, 0.048]);
for (let i = 1; i < 50; i++) c = slewCommand(c, [1.5, 0, 1], .02, S);
assert.deepEqual(c.map((v) => +v.toFixed(3)), [1.5, 0, 1]);            // 1 초에 끝 값
let n = 0; while (c[0] > 0) { c = slewCommand(c, [0, 0, 0], .02, S); n++; }
assert.ok(n <= 21, `놓으면 약 0.4 초에 0 (${n} 스텝)`);
```

lab 에서 같은 함수를 돌려 본 값: 첫 스텝 `[0.03, 0, 0.048]`, 50 스텝 뒤 `[1.5, 0, 1]`, 놓으면 21 스텝(0.42 초)에 0, 1.5 → −1 은 52 스텝(약 1 초).

**확인.**
- 콘솔: `const t = setInterval(() => console.log(__sim.cmd()[0].toFixed(2)), 100)` 를 켜고 막대를 앞으로 끝까지 밀면 0.15 씩 올라 약 1 초 뒤 1.5. 놓으면 약 0.4 초에 0. STOP 은 바로 0. 끝나면 `clearInterval(t)`.
- 눈: 앞으로 밀 때 튀어 나가지 않는지, 놓을 때 멈추는 느낌이 지금 키보드와 같은지.
- 찍은 점 가기 출발도 같은 속도로 올라가는지(③ 은 runner 명령에도 걸림).

**안 되면.**
- 값이 그대로 한 번에 1.5: `prepare` 의 넣은 자리가 `else sim.cmd = …` (`:957`) **뒤**인지, `adapter.command.slew` 가 있는지(위 2 번, `start-demo-adapter.js:3` import 와 `:58`) 봅니다.
- 멈춘 뒤 다시 누르면 옛 속도에서 출발: `lock()` · `#reset` (`:882`) 에서 `lastCmd` 를 비웠는지 봅니다.
- 키보드가 전보다 굼뜸: 키보드 램프와 이 제한이 겹친 것이 아닌지 봅니다(값이 같으므로 겹쳐도 느려지지 않아야 정상). 느리면 그 숫자를 보고합니다.

---

## ④ 목표(찍은 점) 모드 직진 1.2 m/s

**할 일.** start 목표 모드의 직진 속도가 앱 기본 `sim_runner_vx` **0.4** 라서 느립니다(측정 0.39~0.41 m/s, AME-2 목표 모드는 1.05 m/s). start 만 기본을 **1.2 m/s** 로 올립니다(측정: 명령 1.2 → 실제 1.05~1.09 m/s, 학습 전진 0.1~1.5 안). 걸으며 돌 때 0.3~0.8 (`scenario.js:105`) 은 그대로 둡니다.

**바꿀 파일:줄.**

| 파일:줄 | 바꾼 뒤 |
|---|---|
| `mobile/sim/settings.js:19` | `vx: boundedNumber(o.sim_runner_vx, 0.1, 1.5, caps.runnerVx ?? DEFAULT_VX),` |
| `mobile/sim/main.js:265` | `simSettings(org, { vx: caps.forward, wz: caps.turnInPlace, runnerVx: adapter.command.runnerVx }, adapter.id)` |
| `mobile/sim/start-demo-adapter.js:58` `command` | `runnerVx: 1.2` 한 칸 더하기 |

`commandCaps` (`manual-settings.js:11-15`) 가 `command.caps` 만 돌려주므로 `runnerVx` 는 위처럼 `adapter.command` 에서 직접 읽습니다.

**조직 설정 0.4 확인 (웹에서 연 시뮬 `?from=web`).** 서버가 `sim_runner_vx: 0.4` 를 값으로 돌려주면 그것이 이깁니다(`apps/contracts/models.py:520` 기본 0.4). 웹 시뮬 콘솔에서:

```js
const o = await (await fetch('/api/v1/org/settings', { credentials: 'same-origin' })).json();
console.log(o.sim_runner_vx, o.model_overrides);
```

값이 0.4 로 오면 설정 화면(`apps/web/src/screens/settings.tsx:121` 「시뮬 임무 실행기 최대 전진」)에서 start 모델 덮어쓰기(`model_overrides['start-demo'].sim_runner_vx = 1.2`)를 넣습니다. 서버 기본값 0.4 자체를 바꿀지는 nvidia 모드도 같이 쓰므로 따로 판단합니다(이 지시서에서는 바꾸지 않음).

**확인.**
- 평지에서 5 m 앞을 찍고 도착까지 걸린 시간(지금 약 13 초. 바꾼 뒤는 미측정이라 숫자를 적어 보고).
- 곧게 갈 때 `__sim.cmd()[0]` 가 1.2(③ 때문에 약 0.8 초에 걸쳐 오름), 꺾을 때 0.3~0.8.
- 도착 반경 0.3 m 에서 지나쳤다 되돌아오지 않는지. `?from=web` 에서도 같은지.

**안 되면.**
- 여전히 0.4: `?from=web` 이면 위 조직 설정. 아니면 `settings.js:19` 와 `main.js:265` 둘 다 바뀌었는지.
- 목표를 지나침: `scenario.js:105` 다음 줄에 `speed = Math.min(speed, Math.max(0.3, dist));` 를 더해 1 m 안에서 줄입니다(lab 이 재지 않은 제안이라 결과를 보고).
- 길이 꺾일 때마다 멈춰 서서 여전히 느림: `scenario.js:83` 의 「0.4 rad 이상이면 제자리 회전」 때문입니다. 이번에는 바꾸지 말고 걸린 시간만 보고합니다.

---

## ⑤ 브라우저 · 폰에서 재기 (고치기 전 · 뒤 둘 다)

시뮬을 열고 「시작」 → 막대나 ↑ 키로 앞으로 걷게 한 채, 개발자 도구 콘솔에 붙여 넣습니다. 5 초 동안 잽니다. `?policy=start-demo` 와 `?policy=ame2-demo` 를 각각 잽니다.

```js
(async () => {
  const s = window.__sim, n0 = s.steps, t0 = performance.now(), pol = [], dep = [], map = [];
  const iv = setInterval(() => {
    pol.push(s.sim.policyMs);
    if (s.sim.depthScanner?.roundtripMs) dep.push(s.sim.depthScanner.roundtripMs);
    if (s.sim.heightScanner?.ms) map.push(s.sim.heightScanner.ms);
  }, 50);
  await new Promise((r) => setTimeout(r, 5000)); clearInterval(iv);
  const sec = (performance.now() - t0) / 1000, med = (a) => a.length ? [...a].sort((x, y) => x - y)[a.length >> 1].toFixed(2) : '-';
  console.table({ fps: s.fps(), stepsPerSec: ((s.steps - n0) / sec).toFixed(1), simSpeed: ((s.steps - n0) * 0.02 / sec).toFixed(2),
    policyMs: med(pol), depthRoundtripMs: med(dep), mapMs: med(map), cmd: s.cmd().join(', '), engine: s.policyEngine, ...s.timing() });
})();
```

폰(Android 앱)은 `chrome://inspect` 로 WebView 콘솔을 열어 같은 조각을 넣습니다.

채울 표(보고에 그대로 붙입니다):

| 기기 · 모드 | 시점 | fps | stepsPerSec | simSpeed | policyMs | depthRoundtripMs | engine |
|---|---|---|---|---|---|---|---|
| PC · start | 고치기 전 | | | | | | |
| PC · start | ①~④ 뒤 | | | | | | |
| PC · ame2 | 고치기 전 | | | | | | |
| 폰 · start | 고치기 전 | | | | | | |
| 폰 · start | ①~④ 뒤 | | | | | | |
| 폰 · ame2 | 고치기 전 | | | | | | |

읽는 법: `fps` 는 초당 그리기(② 뒤 start 가 60 근처면 성공). `stepsPerSec` 50 · `simSpeed` 1.00 이면 계산이 20 ms 기한 안. 1 보다 작으면 `policyMs` 가 20 에 가까운지 봅니다. lab PC 에서 잰 값은 우리 한 스텝 약 5 ms · AME-2 약 2.4 ms 입니다(`APP-TUNING-1109.md` §1-3).

눈 확인 표(예 · 아니오):

| 확인 | 고치기 전 | 뒤 |
|---|---|---|
| start 화면이 AME-2 만큼 매끄럽게 움직인다 | | |
| 막대를 앞으로 끝까지 밀어도 튀어 나가지 않는다 | | |
| 막대를 놓으면 0.5 초 안에 선다 · STOP 은 바로 선다 | | |
| 목표 모드 5 m 도착 시간(초) | | |
| 뒤로 끝까지 당기면 `cmd` 가 −1.3 | | |

---

## ⑥ 끝나면 보고할 것

아래를 한 번에 보고합니다(lab 의 오흥재에게, 또는 이 PR #590 댓글로).

1. 앱 작업 가지 이름과 단계별 커밋 해시 넷(① ② ③ ④).
2. ① 의 `policy-vector-selftest` 결과 줄(start 세 경우 최대 차이), `grep` 0 줄 확인.
3. ③ 의 새 시험 통과 줄.
4. ⑤ 의 두 표(숫자 그대로, 못 잰 칸은 「못 잼 · 까닭」).
5. 「안 되면」 에 해당한 것과 그때 한 일.
6. 아직 무겁거나 튀는 느낌이 남았으면 그 장면(지형 · 명령 · 몇 초쯤)을 한 줄로.

하지 않는 것: lab 저장소 파일 고치기(받기만), 서버 기본값 0.4 바꾸기, 목표 모드 「꺾을 때 멈춤」 바꾸기, ONNX 나 학습 값 바꾸기.
