// APP-TUNING-1109: 앱 자신의 시뮬 코드(foothold-app mobile/sim, 읽기 전용)를 Node 에서 그대로 돌려
// (a) ONNX 추론 · (b) 지도 · 깊이 입력 만들기 · (c) 물리 시간을 따로 재고, 같은 루프로 출발 반응과 속도를 잰다.
// 화면 그리기(three.js) 와 Worker 왕복은 여기서 못 잰다(브라우저 몫, APP-TUNING-1109.md 의 측정 조각).
//
// 쓰는 법:
//   APP_SIM=<foothold-app>/mobile/sim  MUJOCO=<@mujoco/mujoco 3.17.0>/mujoco.js  ORT_WEB=<onnxruntime-web 1.31.1>/dist/ort.wasm.min.mjs
//   GO2=<mujoco_menagerie unitree_go2 폴더>  OUT=<결과.json>  node app_tuning_sim_bench.mjs
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = join(dirname(fileURLToPath(import.meta.url)), '..'); // 묶음 폴더(20261103-policy-handoff)
const url = (p) => pathToFileURL(p).href;
const APP = process.env.APP_SIM, GO2 = process.env.GO2;
const { default: load } = await import(url(process.env.MUJOCO));
const ort = await import(url(process.env.ORT_WEB));
ort.env.wasm.numThreads = 1; ort.env.wasm.proxy = false;
const { createSim, ISAAC_LIKE } = await import(url(join(APP, 'sim.js')));
const { loadOnnxPolicy, withPolicyState } = await import(url(join(APP, 'policy-onnx.js')));
const { getPolicyMode } = await import(url(join(APP, 'policy-modes.js')));

const mj = await load();
mj.FS.mkdir('/go2'); mj.FS.mkdir('/go2/assets');
mj.FS.writeFile('/go2/go2.xml', readFileSync(join(GO2, 'go2.xml')));
for (const f of readdirSync(join(GO2, 'assets'))) mj.FS.writeFile(`/go2/assets/${f}`, readFileSync(join(GO2, 'assets', f)));
const worlds = {
  flat: '<mujoco><worldbody><geom name="floor" type="plane" size="60 60 0.1"/></worldbody></mujoco>',
  warehouse: readFileSync(join(APP, 'assets/warehouse/warehouse.xml'), 'utf8'),
};
for (const [id, xml] of Object.entries(worlds)) {
  mj.FS.writeFile(`/go2/world_${id}.xml`, xml);
  mj.FS.writeFile(`/go2/scene_${id}.xml`, `<mujoco model="go2 ${id}"><include file="go2.xml"/><include file="world_${id}.xml"/></mujoco>`);
}
const FLOOR = { flat: 0, warehouse: JSON.parse(readFileSync(join(APP, 'assets/warehouse/map.json'), 'utf8')).floor_z };

const POLICIES = {
  m6000: { mode: 'start-demo', files: { gt: 'start-demo-app/start-demo_map_on.onnx', off: 'start-demo-app/start-demo_map_off.onnx' } },
  m13000: { mode: 'start-demo', files: { gt: 'start-m13000-app/start-m13000_map_on.onnx', off: 'start-m13000-app/start-m13000_map_off.onnx' } },
  ame2: { mode: 'ame2-demo', files: { gt: 'ame2-demo-app/ame2-demo.onnx' } },
};
const timed = (fn, bucket) => {
  const w = (...a) => { const t = performance.now(); const r = fn(...a); bucket.push(performance.now() - t); return r; };
  return Object.assign(w, fn);
};
async function makeSim(policyId, mapMode, world) {
  const p = POLICIES[policyId], mode = getPolicyMode(p.mode);
  const contract = mode.onnx;
  const infer = await loadOnnxPolicy(ort, readFileSync(join(here, p.files[mapMode] ?? p.files.gt)), contract, 'wasm');
  const t = { infer: [], map: [], depth: [], phys: [], step: [] };
  const run = async (...a) => { const s0 = performance.now(); const r = await infer(...a); t.infer.push(performance.now() - s0); return r; };
  run.async = true; run.dispose = infer.dispose;
  const policy = mode.depth ? withPolicyState(run, contract) : Object.assign(run, { async: true });
  const s = createSim(mj, `/go2/scene_${world}.xml`, ISAAC_LIKE, policy, { floorZ: FLOOR[world], spawn: [0, 0, 0] }, mode.id,
    { startMapMode: mode.depth ? (mapMode === 'off' ? 'off' : 'gt') : undefined, depthWorkerOptions: { createWorker: null } });
  s.heightScanner = timed(s.heightScanner, t.map);
  if (s.depthScanner) s.depthScanner = timed(s.depthScanner, t.depth);
  return { s, t, mode };
}
const pitchOf = (q) => Math.asin(Math.max(-1, Math.min(1, 2 * (q[3] * q[5] - q[6] * q[4]))));
async function step(sim) {
  const t0 = performance.now();
  const r = await sim.s.step();
  if (r === false) throw new Error('step rejected');
  sim.t.step.push(performance.now() - t0); sim.t.phys.push(sim.s.physMs);
}
const stats = (a) => { if (!a.length) return null; const b = [...a].sort((x, y) => x - y); return { n: b.length, median: +b[b.length >> 1].toFixed(3), p95: +b[Math.floor(.95 * b.length) - 1].toFixed(3), max: +b.at(-1).toFixed(3) }; };
const result = { node: process.version, ort: '1.31.1 wasm 1 thread', mujoco: '3.17.0', timing: {}, launch: {}, speed: {} };

// 1) 시간 나누기: 창고 장면, 0.6 m/s 로 6 초 걷기(300 스텝)
for (const [pid, mapMode] of [['m6000', 'gt'], ['m6000', 'off'], ['m13000', 'gt'], ['m13000', 'off'], ['ame2', 'gt']]) {
  const sim = await makeSim(pid, mapMode, 'warehouse');
  sim.s.reset(); sim.s.hold(0.5);
  for (const k of Object.keys(sim.t)) sim.t[k].length = 0;
  sim.s.cmd = sim.mode.command.kind === 'nearby_goal' ? [0.6, 0, 0, 1] : [0.6, 0, 0];
  for (let i = 0; i < 300; i++) await step(sim);
  const key = `${pid}_${mapMode}`;
  result.timing[key] = Object.fromEntries(Object.entries(sim.t).map(([k, v]) => [k, stats(v)]));
  result.timing[key].per_step_sum_ms = +(['infer', 'map', 'phys'].reduce((a, k) => a + (stats(sim.t[k])?.median ?? 0), 0)
    + (sim.t.depth.length ? sim.t.depth.reduce((a, b) => a + b, 0) / 300 : 0)).toFixed(3);
  console.log(key, JSON.stringify(result.timing[key]));
  sim.s.dispose();
}

// 2) 출발 반응: 평지, 서기 2 초 → 앞으로 (계단 명령 · 1 초 램프 · 2 초 램프). AME-2 는 1 m 앞 목표.
const ramps = { step: 0, ramp1s: 1.0, ramp2s: 2.0 };
for (const pid of ['m6000', 'm13000', 'ame2']) {
  for (const [rname, rampS] of Object.entries(pid === 'ame2' ? { step: 0 } : ramps)) {
    for (const vmax of pid === 'ame2' ? [1] : [1.5, 0.8]) {
      const sim = await makeSim(pid, 'gt', 'flat');
      const goal = sim.mode.command.kind === 'nearby_goal';
      sim.s.reset(); sim.s.hold(0.5);
      sim.s.cmd = goal ? [0, 0, 0, 1] : [0, 0, 0];
      for (let i = 0; i < 100; i++) await step(sim);
      const trace = [];
      for (let i = 0; i < 200; i++) {
        const tt = i * 0.02, frac = rampS ? Math.min(1, tt / rampS) : 1;
        sim.s.cmd = goal ? [vmax, 0, 0, 1] : [vmax * frac, 0, 0];
        await step(sim);
        const q = sim.s.d.qpos;
        trace.push({ t: +tt.toFixed(2), cmd: +(goal ? NaN : vmax * frac).toFixed(3), vx: +sim.s.linB[0].toFixed(3), pitch: +pitchOf(q).toFixed(4), z: +q[2].toFixed(4), x: +q[0].toFixed(3) });
      }
      // 0.1 s 이동 평균 속도로 가속도
      const v = trace.map((r) => r.vx), sm = v.map((_, i) => v.slice(Math.max(0, i - 4), i + 1).reduce((a, b) => a + b, 0) / Math.min(5, i + 1));
      const acc = sm.map((x, i) => i < 5 ? 0 : (x - sm[i - 5]) / 0.1);
      const first = (thr) => { const i = sm.findIndex((x) => x >= thr); return i < 0 ? null : +(i * 0.02).toFixed(2); };
      const vss = v.slice(-50).reduce((a, b) => a + b, 0) / 50;
      const key = `${pid}_${rname}_v${vmax}`;
      result.launch[key] = {
        peak_acc_mps2: +Math.max(...acc).toFixed(2), peak_vx_1s: +Math.max(...v.slice(0, 50)).toFixed(3),
        t_to_0p5: first(0.5), t_to_90pct_final: first(0.9 * vss), vx_last1s: +vss.toFixed(3),
        pitch_range_1s_deg: +((Math.max(...trace.slice(0, 50).map((r) => r.pitch)) - Math.min(...trace.slice(0, 50).map((r) => r.pitch))) * 180 / Math.PI).toFixed(2),
        x_at_1s: trace[49].x, x_at_4s: trace[199].x,
        vx_0p1s: trace.filter((_, i) => i % 5 === 4).slice(0, 15).map((r) => r.vx),
      };
      console.log(key, JSON.stringify(result.launch[key]));
      sim.s.dispose();
    }
  }
}

// 3) 정상 속도: 평지 8 초, 마지막 4 초 평균 (찍은 점 가기 기본 0.4 와 비교)
for (const pid of ['m6000', 'm13000']) {
  for (const vx of [0.3, 0.4, 0.8, 1.2, 1.5]) {
    const sim = await makeSim(pid, 'gt', 'flat');
    sim.s.reset(); sim.s.hold(0.5); sim.s.cmd = [vx, 0, 0];
    const v = [];
    for (let i = 0; i < 400; i++) { await step(sim); v.push(sim.s.linB[0]); }
    result.speed[`${pid}_cmd${vx}`] = +(v.slice(-200).reduce((a, b) => a + b, 0) / 200).toFixed(3);
    sim.s.dispose();
  }
}
{
  const sim = await makeSim('ame2', 'gt', 'flat');
  sim.s.reset(); sim.s.hold(0.5); sim.s.cmd = [1, 0, 0, 1];
  const v = [];
  for (let i = 0; i < 400; i++) { await step(sim); v.push(sim.s.linB[0]); }
  result.speed.ame2_goal1m = +(v.slice(-200).reduce((a, b) => a + b, 0) / 200).toFixed(3);
  sim.s.dispose();
}
console.log('speed', JSON.stringify(result.speed));
if (process.env.OUT) writeFileSync(process.env.OUT, JSON.stringify(result, null, 1));
