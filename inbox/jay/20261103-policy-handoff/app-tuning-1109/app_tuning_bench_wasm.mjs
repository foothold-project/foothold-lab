// APP-TUNING-1109: onnxruntime-web (wasm, 앱과 같은 1 스레드 · proxy 끔) 추론 시간을 Node 에서 잰다.
// 앱 policy-onnx.js 의 설정(numThreads 1 · graphOptimizationLevel 'all' · executionProviders ['wasm'])을 그대로 쓴다.
// 쓰는 법: ORT_WEB=<onnxruntime-web 1.31.1 의 dist/ort.wasm.min.mjs 경로> VEC=<입력 .bin 폴더> node app_tuning_bench_wasm.mjs [호출 수]
// 입력 .bin 은 app_tuning_bench.py 와 같은 시험 벡터(평지 20 스텝)를 float32 · uint8 로 풀어 둔 것이다.
import { readFileSync } from 'node:fs';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = join(dirname(fileURLToPath(import.meta.url)), '..'); // 묶음 폴더(20261103-policy-handoff)
const ort = await import(pathToFileURL(process.env.ORT_WEB).href);
ort.env.wasm.numThreads = 1;
ort.env.wasm.proxy = false;
const VEC = process.env.VEC, CALLS = Number(process.argv[2] ?? 500);
const f32 = (p) => { const b = readFileSync(p); return new Float32Array(b.buffer, b.byteOffset, b.byteLength / 4); };
const u8 = (p) => new Uint8Array(readFileSync(p));
const START = [['obs45', [1, 45]], ['hist', [1, 10, 45]], ['depth2', [1, 2, 60, 60]], ['h_prop', [1, 128]], ['h_terr', [1, 128]],
  ['depth_tick', [1], 'bool'], ['first_after_reset', [1], 'bool'], ['use_gt', [1], 'bool'], ['gt_map', [1, 32, 16]]];
const size = (d) => d.reduce((a, b) => a * b, 1);
const runs = [
  ['m6000_map_on', 'start-demo-app/start-demo_map_on.onnx', 'm6000_on'],
  ['m6000_map_off', 'start-demo-app/start-demo_map_off.onnx', 'm6000_off'],
  ['m13000_map_on', 'start-m13000-app/start-m13000_map_on.onnx', 'm13000_on'],
  ['m13000_map_off', 'start-m13000-app/start-m13000_map_off.onnx', 'm13000_off'],
  ['ame2', 'ame2-demo-app/ame2-demo.onnx', 'ame2'],
];
const stats = (t) => { t.sort((a, b) => a - b); return { median: t[t.length >> 1], p95: t[Math.floor(.95 * t.length) - 1], max: t.at(-1) }; };
const result = { ort: ort.env.versions?.web ?? 'unknown', node: process.version, calls: CALLS, models: {} };
for (const [name, file, tag] of runs) {
  const session = await ort.InferenceSession.create(readFileSync(join(here, file)), { executionProviders: ['wasm'], graphOptimizationLevel: 'all' });
  const times = [];
  if (tag === 'ame2') {
    const prop = f32(`${VEC}/ame2_prop.bin`), mapping = f32(`${VEC}/ame2_mapping.bin`);
    for (let i = 0; i < CALLS + 20; i++) {
      const s = i % 20;
      const feeds = { prop: new ort.Tensor('float32', prop.slice(s * 49, s * 49 + 49), [1, 49]),
        mapping: new ort.Tensor('float32', mapping.slice(s * 1131, s * 1131 + 1131), [1, 29, 13, 3]) };
      const t = performance.now(); const out = await session.run(feeds); const dt = performance.now() - t;
      for (const v of Object.values(out)) v.dispose?.();
      if (i >= 20) times.push(dt);
    }
  } else {
    const data = Object.fromEntries(START.map(([k, d, ty]) => [k, ty === 'bool' ? u8(`${VEC}/${tag}_${k}.bin`) : f32(`${VEC}/${tag}_${k}.bin`)]));
    let state = null;
    for (let i = 0; i < CALLS + 20; i++) {
      const s = i % 20, feeds = {};
      for (const [k, d, ty] of START) {
        const n = size(d);
        let v = data[k].slice(s * n, s * n + n);
        if (s > 0 && state && k === 'h_prop') v = state[0];
        if (s > 0 && state && k === 'h_terr') v = state[1];
        feeds[k] = new ort.Tensor(ty ?? 'float32', ty === 'bool' ? Uint8Array.from(v) : v, d);
      }
      const t = performance.now(); const out = await session.run(feeds); const dt = performance.now() - t;
      state = [out.h_prop_next.data.slice(), out.h_terr_next.data.slice()];
      for (const v of Object.values(out)) v.dispose?.();
      if (i >= 20) times.push(dt);
    }
  }
  await session.release();
  result.models[name] = stats(times);
  console.log(name.padEnd(15), Object.entries(result.models[name]).map(([k, v]) => `${k} ${v.toFixed(3)}`).join(' · '), 'ms');
}
if (process.env.OUT) (await import('node:fs')).writeFileSync(process.env.OUT, JSON.stringify(result, null, 1));
