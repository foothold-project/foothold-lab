// APP-TUNING-1109: 앱 main.js 의 start 화면 루프(그리기 미루기 START_DRAW_MAX_GAP_MS 100)와
// 앱의 frame-clock.js 를 가상 시계로 돌려, 추론 왕복 시간 L 에 따라 화면이 몇 번 그려지고 시뮬 시간이 벽시계를 따라가는지 센다.
// 실제 브라우저 측정이 아니다(계산 모형). 그리기 · 물리 자체 비용은 0 으로 둔다.
// 쓰는 법: APP_SIM=<foothold-app>/mobile/sim node app_tuning_frameloop_sim.mjs
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
const { createFrameClock } = await import(pathToFileURL(join(process.env.APP_SIM, 'frame-clock.js')).href);
const flush = () => new Promise((r) => setImmediate(r));

async function run({ L, depthMode, seconds = 10, rafMs = 1000 / 60 }) {
  let vnow = 0, accepted = 0, draws = 0, lastDrawAt = -Infinity;
  const events = [];
  const at = (t, fn) => { events.push({ t, fn }); events.sort((a, b) => a.t - b.t); };
  const clock = createFrameClock({ dt: 0.02, yieldOnRejected: depthMode,
    step: () => new Promise((res) => at(vnow + Math.min(L, 20), () => res(L < 20))), onStep: () => { accepted++; } });
  clock.reset();
  const frame = () => {
    clock.frame(vnow, false);
    if (depthMode && clock.stats.pending && vnow - lastDrawAt < 100) { at(vnow + rafMs, frame); return; }
    draws++; lastDrawAt = vnow;
    at(vnow + rafMs, frame);
  };
  at(0, frame);
  while (events.length && events[0].t <= seconds * 1000) {
    const e = events.shift(); vnow = e.t; e.fn(); await flush(); await flush();
  }
  return { L, depthMode, fps: +(draws / seconds).toFixed(1), simSpeed: +((accepted * 0.02) / seconds).toFixed(3) };
}
const out = [];
for (const depthMode of [true, false]) for (const L of [1, 3, 5, 8, 12, 16, 19, 25]) out.push(await run({ L, depthMode }));
console.table(out);
