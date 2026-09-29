/* 갤러리 공통 코드. 세 화면이 이것 하나를 쓴다.
 *
 * 분류: 운영 · 작성: 오흥재 · 2026-09-12 · 상태: 확정
 * 근거: gpt-6-astra high 설계 검토 (Claude/site-gallery-design-result.md)
 *
 * 여기 있는 규칙은 전부 그 검토가 지목한 실패를 막으려는 것이다.
 *  · 링크로 들어온 값은 색인에 있는 것만 받는다. 없는 값을 몰래 바꾸지 않는다
 *  · 경로는 색인이 적어 준 것만 쓴다. 판·모델 이름을 이어 붙여 만들지 않는다
 *  · 구간은 경계를 닫아 적는다. 1~49 는 49.5 를 빠뜨린다
 *  · 영상은 고른 것에만 src 를 건다. 84개를 한꺼번에 걸면 다 받아 온다
 */
'use strict';

const G = {};

/* 갤러리 뿌리 주소. **자기 스크립트가 어디서 왔는지로 잡는다.**
 *
 * 상대 경로(`../versions.json`)를 쓰면 안 된다. vercel.json 이
 * `trailingSlash: false` 라 `/gallery/view/` 가 `/gallery/view` 로 바뀌고,
 * 그러면 `../` 가 `/gallery/` 가 아니라 `/` 를 가리킨다. 로컬에서는 멀쩡하고
 * 배포에서만 404 가 난다.
 */
G.root = (function () {
  const self = document.currentScript && document.currentScript.src;
  if (!self) return '/gallery/';
  return self.replace(/gallery\.js(\?.*)?$/, '');
})();

G.at = function (path) { return G.root + String(path).replace(/^\/+/, ''); };

/* ── 색인 읽기 ──────────────────────────────────────────── */

G.loadJSON = async function (url) {
  const res = await fetch(url, { cache: 'no-cache' });
  if (!res.ok) throw new Error(url + ' 를 못 읽었다 (' + res.status + ')');
  return res.json();
};

/* 색인이 우리가 아는 모양인가. 모르는 모양이면 조용히 그리지 않는다. */
G.checkSchema = function (data, prefix) {
  const got = String(data && data.schema || '');
  if (!got.startsWith(prefix)) {
    throw new Error('모르는 색인 모양: ' + got + ' (기대: ' + prefix + '…)');
  }
  return data;
};

/* ── 구간 ───────────────────────────────────────────────── */

/* 경계를 닫아서 센다. `min_open`·`max_open` 이 열린 쪽을 말한다. */
G.inBand = function (value, band) {
  if (band.null) return value === null || value === undefined;
  if (value === null || value === undefined) return false;
  const lo = band.min_open ? value > band.min : value >= band.min;
  const hi = band.max_open ? value < band.max : value <= band.max;
  return lo && hi;
};

G.bandOf = function (value, bands) {
  return bands.find(b => G.inBand(value, b)) || null;
};

/* ── URL 상태 ───────────────────────────────────────────── */

/* 링크로 들어온 값을 **색인에 있는 것과 대조한다.** 없으면 버리고 알린다.
 * 몰래 첫 값으로 바꾸면 저장한 링크가 다른 화면을 연다. */
G.readParams = function (allowed) {
  const q = new URLSearchParams(location.search);
  const out = {};
  const rejected = [];

  for (const [key, values] of Object.entries(allowed)) {
    const raw = q.get(key);
    if (raw === null || raw === '') continue;
    const ok = values.find(v => String(v) === raw || G.sameNumber(v, raw));
    if (ok === undefined) { rejected.push(key + '=' + raw); continue; }
    out[key] = ok;
  }

  return { value: out, rejected };
};

/* `speed=1` 과 `speed=1.0` 을 같은 것으로 본다. 쓸 때는 하나로 통일한다. */
G.sameNumber = function (a, b) {
  const x = Number(a), y = Number(b);
  return Number.isFinite(x) && Number.isFinite(y) && x === y;
};

G.writeParams = function (state, replace) {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(state)) {
    if (value === null || value === undefined || value === '') continue;
    q.set(key, String(value));
  }
  const url = location.pathname + (q.toString() ? '?' + q : '');
  if (replace) history.replaceState(state, '', url);
  else history.pushState(state, '', url);
};

/* ── 영상 ───────────────────────────────────────────────── */

/* 고르기 전에는 src 를 걸지 않는다. 84개를 한꺼번에 걸면 미리 읽기가 돈다. */
G.attach = function (video, src) {
  if (video.getAttribute('src') === src) return video;
  /* **배속을 지킨다.** `load()` 가 `playbackRate` 를 1 로 되돌린다.
   * 개열하기 전에 0.25x 를 고르면 단추는 0.25x 로 남고 실제는
   * 1배로 돌았다 `확인됨` (2026-09-12 codex 7회차). */
  const rate = video.playbackRate;
  video.setAttribute('src', src);
  video.load();
  if (rate && rate !== 1) {
    video.playbackRate = rate;
    video.addEventListener('loadedmetadata', () => { video.playbackRate = rate; },
                           { once: true });
  }
  return video;
};

G.detach = function (video) {
  video.pause();
  video.removeAttribute('src');
  video.load();
};

/* `play()` 는 비동기로 거절될 수 있다. 결과를 보고 실패한 열을 표시한다. */
G.play = function (video) {
  const p = video.play();
  return p && p.catch ? p.catch(err => ({ error: err })) : Promise.resolve();
};

G.fmtSeconds = function (s) {
  if (!Number.isFinite(s)) return '--:--';
  const m = Math.floor(s / 60);
  return m + ':' + String(Math.floor(s % 60)).padStart(2, '0') +
         '.' + String(Math.floor((s % 1) * 10));
};

/* ── 그리기 조각 ────────────────────────────────────────── */

G.rateClass = function (rate) {
  if (rate === null || rate === undefined) return '';
  if (rate === 0) return 'zero';
  if (rate < 50) return 'low';
  if (rate >= 90) return 'high';
  return '';
};

/* 참여도를 글자로 바꾼다. **규칙은 여기 한 곳에만 둔다** (#435).
 *
 * 참여도는 「몸통 아래 중앙 광선이 지난 높이 폭 / 스캔 전체가 본 높이 폭」이다.
 * 그런데 `gap` 은 발판과 테두리 사이에 **바닥이 없다.** 광선이 맞힐 면이 없으니
 * 위아래 폭이 안 잡히고 코드가 빈 칸으로 둔다.
 *
 * 문제는 «아주 가끔» 값이 나온다는 것이다. gap 21,640 에피소드 중 값이 나온 것이
 * 5 개인데, 그 5 개는 전진 1.53 m 이하 · 곧 **출발 발판을 못 벗어난** 것들이다
 * (통과선은 3 m). 0.03 % 표본으로 만든 숫자를 100 % 표본의 숫자와 같은 모양으로
 * 보이면 읽는 사람이 속는다.
 *
 * 실제로 화면이 이렇게 서 있었다.
 *
 *     baseline      성공   1 %    참여도 1.00
 *     foothold-v1   성공 100 %    참여도 측정값 없음
 *
 * **정확히 거꾸로 읽힌다.** 기준선이 지형을 잘 탄 것처럼, foothold-v1 이 안 탄
 * 것처럼 보인다. 실제는 foothold-v1 이 틈을 건너가서 광선이 맞힐 바닥이 없어진
 * 것이고, 기준선의 1.00 은 틈에 닿지도 못한 에피소드 하나로 낸 값이다.
 *
 * 그래서 gap 에서는 숫자를 아예 내지 않고 «왜 없는지» 를 적는다. 「측정값 없음」
 * 으로만 두면 「자료가 빠졌나」로 읽히므로 그 말도 쓰지 않는다.
 *
 * **지형 이름을 박지 않고 표본 수로 가린다.** 2026-09-19 실측이다.
 *
 *     15개 지형   모든 칸이 n = 100 / 100
 *     gap         n = 0 ~ 3 / 100  (9칸 전부)
 *     표본이 모자란 칸 = 9개, 전부 gap
 *
 * 오늘은 둘이 같은 결과를 내지만, 이름으로 박으면 **나중에 다른 지형에서 같은
 * 일이 나도 안 잡힌다.** 값이 나온 표본이 에피소드 수에 못 미치면 그 숫자는
 * 전수가 아니므로 숫자로 내지 않는다.
 */
G.engText = function (ev) {
  if (!ev) return '참여도 측정값 없음';
  const n = (ev.engagement_n === null || ev.engagement_n === undefined)
    ? null : ev.engagement_n;
  const eps = ev.episodes || 0;
  if (n !== null && eps > 0 && n < eps) {
    if (ev.terrain === 'gap') {
      return '참여도 측정 불가 · 바닥이 없어 광선이 맞힐 면이 없음';
    }
    return '참여도 측정 불가 · ' + eps + ' 중 ' + n + ' 에피소드에서만 값이 나옴';
  }
  const v = ev.engagement;
  return '참여도 ' + (v === null || v === undefined ? '측정값 없음' : v.toFixed(2));
};

G.el = function (tag, attrs, children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'text') node.textContent = v;
    else if (k === 'class') node.className = v;
    else node.setAttribute(k, v === true ? '' : String(v));
  }
  for (const child of (children || [])) {
    if (child) node.appendChild(child);
  }
  return node;
};

/* 조건 하나의 단추 줄. **남는 건수를 같이 적는다.** 0건인 선택지를 눌러
 * 빈 화면을 보게 두지 않는다. */
G.chipRow = function (label, values, current, countOf, onPick) {
  const row = G.el('div', { class: 'frow' }, [
    G.el('span', { class: 'flabel', text: label })
  ]);

  const add = (value, text) => {
    const n = countOf(value);
    const on = String(current) === String(value);
    const chip = G.el('button', {
      class: 'chip', type: 'button', 'aria-pressed': on ? 'true' : 'false',
      disabled: (n === 0 && !on) || null
    }, [
      G.el('span', { text: text }),
      G.el('span', { class: 'n', text: String(n) })
    ]);
    chip.addEventListener('click', () => onPick(on ? null : value));
    row.appendChild(chip);
  };

  add('', '전부');
  values.forEach(v => add(v, typeof v === 'number' ? v.toFixed(1) : String(v)));
  return row;
};

/* 지형 무리 이름. 색인의 열쇠는 영어라 화면에 그대로 내지 않는다.
 * **모르는 열쇠가 와도 지우지 않고 그 열쇠를 그대로 보여준다.** 조용히
 * 빠지면 새 무리가 생겼을 때 아무도 모른다. */
/* ── 계보 차례 ─────────────────────────────────────────────
 *
 * ★ 2026-09-29. **규칙을 한 곳에만 둔다.**
 *
 * `compare/index.html` 이 자기 `MODEL_ORDER` 를 들고 있었고, 갤러리 카드는
 * 그 규칙을 아예 몰라서 판 비교 링크에 두 열만 넘겼다. 그래서 세 번째 열이
 * 어느 갤러리에서 와도 똑같이 «알아서» 골라졌다 (팀장 지적 2026-09-29:
 * 「gallery-v1 에서 판비교 할 때랑 gallery-v2 에서 할 때 기본 셋업값이
 * 다르면 좋을 것 같아서」).
 *
 * 두 파일에 나눠 적으면 갈라진다. 여기 한 번만 적는다.
 */
G.MODEL_ORDER = ['baseline', 'A', 'foothold-v1', 'foothold-v2'];

/** 모델 이름을 계보 차례로 줄 세운다. 모르는 이름은 뒤에 붙인다. */
G.lineage = function (names) {
  const rank = n => {
    const i = G.MODEL_ORDER.indexOf(n);
    return i < 0 ? G.MODEL_ORDER.length : i;
  };
  return [...names].sort((a, b) => rank(a) - rank(b) || (a < b ? -1 : a > b ? 1 : 0));
};

/** 그 판의 «기본 세 열». 기준선을 먼저 두고, 나머지는 계보의 «뒤» 에서 집는다.
 *
 * 모델이 셋이면 그대로 셋이다.
 *   v1   baseline · A · foothold-v1
 *   v2   baseline · foothold-v1 · foothold-v2
 *
 * 넷 이상이면 기준선 + 뒤 둘이다. 대표(main)가 빠지지 않는다.
 */
G.defaultColumns = function (names, want) {
  const n = want || 3;
  const all = G.lineage(names);
  const base = all.filter(x => x === 'baseline');
  const rest = all.filter(x => x !== 'baseline');
  const tail = rest.slice(Math.max(0, rest.length - (n - base.length)));
  return base.concat(tail).slice(0, n);
};

/** 그 판의 «기본 칸» (지형 · 속도).
 *
 * ★ 2026-09-29. 팀장: 「gallery-v1 에서 판비교 들어가면 gap 이 기본
 * 지형이어야할 꺼 아니야」. 맞다. 전에는 코드에 한 칸이 박혀 있어서 어느
 * 판에서 와도 같았다 (v1 때 `gap 0.5` -> v2 배포 때 `rails 1.0` 으로
 * 손으로 갈았다).
 *
 * 규칙: **그 판의 대표가 «계보에서 바로 앞» 대비 가장 크게 벌어지는 칸.**
 * 1.5 m/s 는 뺀다 (NVIDIA 학습 명령 범위 밖이라 0 % 가 흔하고, 그것을
 * 기본으로 두면 기준선이 억울하게 보인다).
 *
 * 손으로 두 번 고른 답을 이 규칙이 그대로 낸다 `확인됨`.
 *
 *   v1 -> gap 0.5     (A 0.0 -> foothold-v1 90.0 · +90.0 %p)
 *   v2 -> rails 1.0   (foothold-v1 48.0 -> foothold-v2 100.0 · +52.0 %p)
 */
G.defaultCell = function (man, opts) {
  const skipFast = !(opts && opts.allowFast);
  const models = G.lineage(Object.keys((man && man.models) || {}));
  const main = man && man.main_model;
  const i = models.indexOf(main);

  if (!man || i < 0) return null;

  const prev = i > 0 ? models[i - 1] : null;
  const rate = {};

  (man.evaluations || []).forEach(e => {
    rate[e.model + '|' + e.terrain + '|' + e.speed_mps] = e.success_rate;
  });

  let best = null;

  (man.evaluations || []).forEach(e => {
    if (e.model !== main) return;
    if (skipFast && e.speed_mps >= 1.5) return;

    const before = prev
      ? rate[prev + '|' + e.terrain + '|' + e.speed_mps]
      : undefined;

    /* 앞 모델이 없으면 «가장 낮은 칸» 을 고른다. 볼 것이 있는 자리다. */
    const gain = (before === undefined) ? -e.success_rate
                                        : (e.success_rate - before);

    if (!best || gain > best.gain
        || (gain === best.gain && e.speed_mps < best.speed)) {
      best = { terrain: e.terrain, speed: e.speed_mps, gain: gain };
    }
  });

  return best ? { terrain: best.terrain, speed: best.speed } : null;
};

G.SET_NAME = { rough6: '기존 험지', unseen10: '미경험 험지' };

/* 읽는 순서. 학습에 쓴 것을 먼저 놓고 안 본 것을 뒤에 놓는다. 여기 없는
 * 무리는 색인이 적은 순서대로 뒤에 붙는다. 새 무리를 여기 안 적어도 나온다. */
G.SET_ORDER = ['rough6', 'unseen10'];

/* 지형 거르개. **한 줄에 16개를 늘어놓지 않는다.**
 *
 * 왜 (2026-09-13 팀장 지시): 지형 16종이 한 줄에 평평하게 깔려 있었고,
 * 그 옆에 「지형 집합」 줄이 따로 있었다. 두 줄이 같은 것을 다르게 말한다.
 * 그리고 **이 과제의 요점인 「학습에 쓴 것 / 한 번도 안 본 것」의 구분이
 * 화면에 없다.** 목록만 보고는 gap 이 미경험인지 기존인지 알 수 없다.
 *
 * 그래서 두 줄을 하나로 합치고 무리로 접는다.
 *
 *   기존 험지 6종    [전부 54]  [boxes 9] [random_rough 9] ...
 *   미경험 험지 10종 [전부 90]  [gap 9] [pit 9] [rails 9] ...
 *
 * 앞으로 쌓일 것 (팀장 질문 5번):
 *   · 무리는 색인(`terrain_sets`)이 정한다. 새 무리가 생기면 저절로 줄이 는다
 *   · 이름을 모르는 무리는 **열쇠를 그대로 써서** 보인다. 안 지운다
 *   · **어느 무리에도 없는 지형은 「무리 미지정」 줄에 모은다.** 이것이 없으면
 *     색인에 지형만 추가하고 무리에 안 넣었을 때 화면에서 통째로 사라진다.
 *     그 부류로 이미 여러 번 당했다
 *   · 줄은 넘치면 접힌다. 한 무리가 30종이 돼도 깨지지 않는다
 */
G.terrainRows = function (opts) {
  const wrap = G.el('div', { class: 'tgrp' });
  const sets = opts.sets || {};
  const all = opts.terrains || [];
  const placed = new Set();
  Object.values(sets).forEach(list => (list || []).forEach(t => placed.add(t)));
  const orphan = all.filter(t => !placed.has(t));

  const keys = Object.keys(sets).slice().sort((a, b) => {
    const ia = G.SET_ORDER.indexOf(a), ib = G.SET_ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
  const groups = keys.map(key => ({
    key: key,
    list: (sets[key] || []).filter(t => all.indexOf(t) >= 0),
    name: G.SET_NAME[key] || key
  })).filter(g => g.list.length);
  if (orphan.length) {
    groups.push({ key: null, list: orphan, name: '무리 미지정' });
  }

  groups.forEach(g => {
    const row = G.el('div', { class: 'frow tset' }, [
      G.el('span', { class: 'flabel', text: g.name + ' ' + g.list.length + '종' })
    ]);

    if (g.key) {
      const n = opts.countSet(g.key);
      const on = opts.set === g.key && !opts.terrain;
      const chip = G.el('button', {
        class: 'chip whole', type: 'button',
        'aria-pressed': on ? 'true' : 'false',
        disabled: (n === 0 && !on) || null
        /* 「전부」라 쓰지 않는다. 아래 줄들의 「전부」는 «조건 없음» 이고
         * 이것은 «이 무리만» 이다. 같은 글자로 다른 뜻을 말하면 안 된다. */
      }, [G.el('span', { text: '무리 전체' }),
          G.el('span', { class: 'n', text: String(n) })]);
      chip.addEventListener('click', () => opts.pickSet(on ? null : g.key));
      row.appendChild(chip);
    }

    g.list.forEach(t => {
      const n = opts.countTerrain(t);
      const on = opts.terrain === t;
      const chip = G.el('button', {
        class: 'chip', type: 'button',
        'aria-pressed': on ? 'true' : 'false',
        disabled: (n === 0 && !on) || null
      }, [G.el('span', { text: t }), G.el('span', { class: 'n', text: String(n) })]);
      chip.addEventListener('click', () => opts.pickTerrain(on ? null : t));
      row.appendChild(chip);
    });

    wrap.appendChild(row);
  });
  return wrap;
};

G.emptyBox = function (title, detail, onClear) {
  const box = G.el('div', { class: 'empty' }, [
    G.el('strong', { text: title }),
    G.el('div', { text: detail })
  ]);
  if (onClear) {
    const btn = G.el('button', { class: 'chip', type: 'button', text: '조건 모두 풀기' });
    btn.style.marginTop = '12px';
    btn.addEventListener('click', onClear);
    box.appendChild(btn);
  }
  return box;
};

G.warn = function (text, bad) {
  return G.el('div', { class: bad ? 'note bad' : 'note' }, [
    G.el('span', { text: text })
  ]);
};

/* 영상 한 칸. **`muted` 는 속성만으로는 안 걸린다.**
 *
 * ★ 2026-09-29 실측. `createElement('video')` 로 만든 다음
 * `setAttribute('muted','')` 를 하면 **속성은 true 인데 성질은 false** 다
 * (`v.hasAttribute('muted')` true · `v.muted` false) `확인됨`.
 * 속성은 파서가 만든 태그의 «처음 값» 만 정한다.
 *
 * 크롬의 자동재생 규칙은 «성질» 을 본다. 그래서 사람이 단추를 누르지 않은
 * 재생은 전부 거절된다.
 *
 *     NotAllowedError: play() failed because the user didn't interact
 *
 * 사람이 누를 때는 그 누름이 허락이 되므로 화면은 멀쩡해 보인다. 그래서
 * 아무도 못 봤다. 그리고 소리가 든 컷이 들어오면 **실제로 소리가 난다.**
 * 여기 한 곳에서 성질로 건다.
 */
G.video = function (attrs) {
  const v = G.el('video', Object.assign({
    preload: 'auto', playsinline: true, muted: true
  }, attrs || {}));
  v.muted = true;                 /* 속성 말고 성질 */
  v.defaultMuted = true;          /* 다시 읽어도 꺼진 채로 */
  return v;
};

/* ── 여러 칸을 한 시계로 묶어 재생 ──────────────────────────
 *
 * ★ 2026-09-29. **규칙을 한 곳에만 둔다** (커널 철칙 4).
 *
 * 이 코드는 `compare/index.html` 안에만 있었다. 축 2 화면도 세 칸을 나란히
 * 재생해야 하는데, 거기에 똑같은 것을 한 벌 더 적으면 **갈라진다.** 이미
 * `MODEL_ORDER` 를 두 곳에 나눠 적어서 한 번 당했다.
 *
 * 쓰는 쪽은 칸을 `add` 로 넣고 단추를 `toggle`·`seek`·`rate` 에 건다.
 * 글자를 어디에 쓸지는 `on*` 로 받는다. 이 코드가 DOM 을 찾지 않는다.
 *
 *   const g = G.syncGroup({ onClock: t => ..., onButton: t => ..., ... });
 *   g.add('left', videoEl, 4.0);
 *   playbtn.onclick = () => g.toggle();
 *
 * **`duration` 은 색인이 적어 준 값으로 먼저 잡고**, `loadedmetadata` 가
 * 오면 실제 값으로 바꾼다. 안 그러면 시계가 0 에서 안 움직인다.
 */
G.syncGroup = function (opts) {
  const o = opts || {};
  const players = {};
  let order = [];
  let running = false, raf = 0, base = 0;

  const live = () => order.map(k => players[k])
    .filter(p => p && p.video.getAttribute('src'));

  const longest = () => Math.max(0, ...live().map(p => p.duration || 0));

  const clock = () => {
    if (o.onClock) o.onClock(G.fmtSeconds(base) + ' / ' + G.fmtSeconds(longest()));
  };

  function tick() {
    if (!running) return;
    base = Math.max(0, ...live().map(p => p.video.currentTime));
    clock();

    live().forEach(p => {
      const done = !!(p.duration && base >= p.duration - 0.04);
      if (o.onEnded) o.onEnded(p.key, done);
    });

    if (base >= longest() - 0.04) { stop(); return; }
    raf = requestAnimationFrame(tick);
  }

  async function play() {
    running = true;
    /* `play()` 는 비동기로 거절될 수 있다. **어느 칸이 못 떴는지 적는다.** */
    const results = await Promise.all(live().map(async p => {
      if (p.duration && p.video.currentTime >= p.duration - 0.04) return null;
      const r = await G.play(p.video);
      return r && r.error ? p.key : null;
    }));
    const failed = results.filter(Boolean);
    if (o.onNote) {
      o.onNote(failed.length
        ? failed.join(' · ') + ' 이 재생을 시작하지 못했습니다' : '');
    }
    if (o.onButton) o.onButton('멈춤');
    raf = requestAnimationFrame(tick);
  }

  function stop() {
    running = false;
    cancelAnimationFrame(raf);
    live().forEach(p => p.video.pause());
    if (o.onButton) o.onButton('함께 재생');
  }

  return {
    /* 다시 그리기 전에 부른다. 안 부르면 사라진 칸이 시계에 남는다. */
    clear() { stop(); order = []; Object.keys(players).forEach(k => delete players[k]); },

    add(key, video, duration) {
      players[key] = { key: key, video: video, duration: duration || 0 };
      if (order.indexOf(key) < 0) order.push(key);
      video.addEventListener('loadedmetadata', () => {
        players[key].duration = video.duration || duration || 0;
        clock();
      });
      return players[key];
    },

    playing() { return running; },
    toggle() { if (running) stop(); else play(); },
    play: play,
    stop: stop,

    seek(t) {
      base = t;
      live().forEach(p => {
        p.video.currentTime = Math.min(t, Math.max(0, (p.duration || t) - 0.01));
      });
      clock();
    },

    rate(x) { live().forEach(p => { p.video.playbackRate = x; }); },
    longest: longest,
    clock: clock
  };
};

/* 조종간 한 줄. 「함께 재생 · 처음으로 · 시계 · 배속」.
 * **`compare` 와 축 2 화면이 같은 것을 쓴다.** 따로 그리면 갈라진다. */
G.transport = function (group, extra) {
  const btn = G.el('button', { class: 'chip', type: 'button', text: '함께 재생' });
  const rew = G.el('button', { class: 'chip', type: 'button', text: '처음으로' });
  const clock = G.el('span', { class: 'clock', text: '0:00.0 / 0:00.0' });
  const note = G.el('span', { class: 'tag warn' });

  const row = G.el('div', { class: 'transport' }, [
    btn, rew, clock, G.el('span', { class: 'flabel', text: '배속' })
  ]);

  (extra && extra.rates || [0.25, 0.5, 1, 2]).forEach(x => {
    const b = G.el('button', {
      class: 'chip', type: 'button',
      'aria-pressed': x === 1 ? 'true' : 'false', text: x + '×'
    });
    b.addEventListener('click', () => {
      row.querySelectorAll('.chip[aria-pressed]')
         .forEach(other => other.setAttribute('aria-pressed', 'false'));
      b.setAttribute('aria-pressed', 'true');
      group.rate(x);
    });
    row.appendChild(b);
  });

  row.appendChild(note);
  btn.addEventListener('click', () => group.toggle());
  rew.addEventListener('click', () => { group.stop(); group.seek(0); });

  return { row: row, button: btn, clock: clock, note: note };
};

/* ── 축 탭 ──────────────────────────────────────────────────
 *
 * ★ 2026-09-29 팀장 지시: 「gallery-v2 부터는 저속 영상이랑, 턴, 등 …
 * 비교해서 볼 수 있게 … 이 후로는 축2에 대해서 더 확장이 될 예정이니,
 * 평가 대상으로는 안해도 기록으로 남긴다」.
 *
 * 축이 둘이 됐다. 어느 화면에서도 같은 자리에서 갈아탈 수 있어야 한다.
 * **주소는 절대경로로 적는다.** 이 화면들은 `/gallery/view` 처럼 슬래시
 * 없이 서빙되므로 `axis2/` 같은 상대경로는 한 칸 위로 풀려 404 가 된다
 * `확인됨` (갤러리 첫 화면에서 같은 실수를 한 적이 있다).
 *
 * `has2` 가 거짓이면 **탭을 아예 그리지 않는다.** 누르면 빈 화면이 나오는
 * 탭을 두느니 없는 편이 낫다 (v1 판에는 축 2 자료가 없다).
 */
G.AXES = [
  { id: 'terrain', label: '축 1 · 험지 통과', href: '/gallery/view' },
  { id: 'command', label: '축 2 · 명령 응답', href: '/gallery/axis2' },
];

G.axisTabs = function (opts) {
  const o = opts || {};
  if (!o.has2) return null;

  const wrap = G.el('div', { class: 'viewsw axistab' });

  G.AXES.forEach(ax => {
    const on = ax.id === o.current;
    const href = ax.href + (o.version ? '?v=' + encodeURIComponent(o.version) : '');
    const node = on
      ? G.el('span', { class: 'rb on', text: ax.label, 'aria-current': 'page' })
      : G.el('a', { class: 'rb', href: href, text: ax.label });
    wrap.appendChild(node);
  });

  return wrap;
};

/* 그 판이 축 2 자료를 가졌나. **`versions.json` 이 적어 준 것만 믿는다.**
 * 폴더 이름으로 추측하면 파일이 없는데 있다고 하게 된다. */
G.hasAxis2 = function (entry) {
  return !!(entry && entry.axis2 && entry.axis2.index);
};
