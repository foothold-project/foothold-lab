const GP = {};
GP.el = function (tag, attrs, children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'text') node.textContent = v;
    else if (k === 'html') node.innerHTML = v;
    else if (k === 'class') node.className = v;
    else node.setAttribute(k, v === true ? '' : String(v));
  }
  for (const child of (children || [])) { if (child) node.appendChild(child); }
  return node;
};
GP.video = function (attrs) {
  const v = GP.el('video', Object.assign({ preload: 'metadata', playsinline: true, muted: true }, attrs || {}));
  v.muted = true; v.defaultMuted = true;
  return v;
};
GP.attach = function (video, src) {
  if (video.getAttribute('src') === src) return video;
  const rate = video.playbackRate;
  video.setAttribute('src', src);
  video.load();
  if (rate && rate !== 1) {
    video.playbackRate = rate;
    video.addEventListener('loadedmetadata', () => { video.playbackRate = rate; }, { once: true });
  }
  return video;
};
GP.play = function (video) {
  const p = video.play();
  return p && p.catch ? p.catch(err => ({ error: err })) : Promise.resolve();
};
GP.fmt = function (s) {
  if (!Number.isFinite(s)) return '--:--';
  const m = Math.floor(s / 60);
  return m + ':' + String(Math.floor(s % 60)).padStart(2, '0') + '.' + String(Math.floor((s % 1) * 10));
};
GP.syncGroup = function (o) {
  const players = {}; let order = []; let running = false, raf = 0, base = 0;
  const live = () => order.map(k => players[k]).filter(p => p && p.video.getAttribute('src'));
  const longest = () => Math.max(0, ...live().map(p => p.duration || 0));
  const clock = () => { if (o.onClock) o.onClock(GP.fmt(base) + ' / ' + GP.fmt(longest())); };
  function tick() {
    if (!running) return;
    base = Math.max(0, ...live().map(p => p.video.currentTime));
    clock();
    if (base >= longest() - 0.04) { stop(); return; }
    raf = requestAnimationFrame(tick);
  }
  async function play() {
    running = true;
    const res = await Promise.all(live().map(async p => {
      if (p.duration && p.video.currentTime >= p.duration - 0.04) return null;
      const r = await GP.play(p.video);
      return r && r.error ? p.key : null;
    }));
    const failed = res.filter(Boolean);
    if (o.onNote) o.onNote(failed.length ? failed.join(' · ') + ' 이 재생을 시작하지 못했습니다' : '');
    if (o.onButton) o.onButton('멈춤');
    raf = requestAnimationFrame(tick);
  }
  function stop() {
    running = false; cancelAnimationFrame(raf);
    live().forEach(p => p.video.pause());
    if (o.onButton) o.onButton('함께 재생');
  }
  return {
    clear() { stop(); order = []; Object.keys(players).forEach(k => delete players[k]); base = 0; clock(); },
    add(key, video, duration) {
      players[key] = { key, video, duration: duration || 0 };
      if (order.indexOf(key) < 0) order.push(key);
      video.addEventListener('loadedmetadata', () => { if (players[key]) { players[key].duration = video.duration || duration || 0; clock(); } });
      video.addEventListener('pause', () => { if (running && live().every(p => p.video.paused)) stop(); });
    },
    toggle() { if (running) stop(); else play(); },
    stop,
    seek(t) { base = t; live().forEach(p => { p.video.currentTime = Math.min(t, Math.max(0, (p.duration || t) - 0.01)); }); clock(); },
    rate(x) { live().forEach(p => { p.video.playbackRate = x; }); },
    clock
  };
};
GP.transport = function (group, rates) {
  const btn = GP.el('button', { class: 'chip', type: 'button', text: '함께 재생' });
  const rew = GP.el('button', { class: 'chip', type: 'button', text: '처음으로' });
  const clock = GP.el('span', { class: 'clock', text: '0:00.0 / 0:00.0' });
  const note = GP.el('span', { class: 'tnote' });
  const row = GP.el('div', { class: 'trow' }, [btn, rew, clock, GP.el('span', { class: 'flabel', text: '배속' })]);
  let cur = 1;
  (rates || [0.25, 0.5, 1, 2]).forEach(x => {
    const b = GP.el('button', { class: 'chip', type: 'button', 'aria-pressed': x === 1 ? 'true' : 'false', text: x + '×' });
    b.addEventListener('click', () => {
      row.querySelectorAll('.chip[aria-pressed]').forEach(o => o.setAttribute('aria-pressed', 'false'));
      b.setAttribute('aria-pressed', 'true'); cur = x; group.rate(x);
    });
    row.appendChild(b);
  });
  row.appendChild(note);
  btn.addEventListener('click', () => group.toggle());
  rew.addEventListener('click', () => { group.stop(); group.seek(0); });
  return { row, button: btn, clock, note, rate: () => cur };
};

