// onnxruntime-web (WASM backend, the app's runtime) on the recorded env inputs vs the original PyTorch action.
import fs from "node:fs";
import * as ort from "onnxruntime-web";

const pkg = JSON.parse(fs.readFileSync(new URL("./node_modules/onnxruntime-web/package.json", import.meta.url)));
ort.env.wasm.numThreads = 1;
const model = fs.readFileSync(process.argv[2]);
const s = await ort.InferenceSession.create(model, { executionProviders: ["wasm"] });
const steps = JSON.parse(fs.readFileSync("steps.json"));
const f32 = (p) => { const b = fs.readFileSync(p); return new Float32Array(b.buffer, b.byteOffset, b.byteLength / 4); };
const res = { onnxruntime_web: pkg.version, backend: "wasm (numThreads 1)", node: process.version, tags: {} };
let worst = 0;
for (const t of ["flat", "stairs"]) {
  const P = f32(`${t}_prop.bin`), M = f32(`${t}_map.bin`), A = f32(`${t}_act.bin`), O = f32(`${t}_off.bin`);
  let offDiff = 0;
  let m = 0, at = -1;
  for (let i = 0; i < steps[t]; i++) {
    const out = await s.run({
      prop: new ort.Tensor("float32", P.slice(i * 49, (i + 1) * 49), [1, 49]),
      mapping: new ort.Tensor("float32", M.slice(i * 1131, (i + 1) * 1131), [1, 29, 13, 3]),
    });
    const a = out.action.data;
    for (let k = 0; k < 12; k++) { const d = Math.abs(a[k] - A[i * 12 + k]); if (d > m) { m = d; at = i; } }
    const o = out.gaze_offset.data; if (o[0] !== O[i * 2] || o[1] !== O[i * 2 + 1]) offDiff++;
  }
  res.tags[t] = { steps: steps[t], max_abs_action_web_vs_torch: m, step_of_max: at, gaze_offset_steps_differing: offDiff };
  worst = Math.max(worst, m);
}
res.max_abs_action_web_vs_torch = worst;
res.pass = worst <= 1e-4;
fs.writeFileSync("parity_web.json", JSON.stringify(res, null, 1) + "\n");
console.log("WEB", JSON.stringify(res));
