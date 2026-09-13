// 고정 뷰포트 계산 스타일 채취기 (mai-os#24)
//
//   ★ 창 크기는 못 믿는다. window.resizeTo 는 막혀 있다 (실측 2026-09-02).
//     같은 출처 iframe 을 정확한 크기로 만들어 그 안에서 잰다.
//
//   ★ 2026-09-02 독립 검수가 잡은 결함 · 전수가 아니라 «표본» 이었다
//     전에는 같은 tag/id/class 묶음에서 `if (i >= 3) return` 으로 앞 3개만 모았다.
//     그래서 145/141 같은 숫자는 전수가 아니었고, 네 번째 이후의 변경·소실은
//     비교기에 아예 도달하지 못했다. 무시각변경 검증에서 그것은 눈먼 지점이다.
//     이제 «보이는 요소를 전부» 모으고, 열쇠는 DOM 경로로 만든다.
//
//   열쇠 = `body>div:nth-child(2)>p:nth-child(4) | p.lede`
//     앞부분(경로)이 유일성과 안정성을 준다. 뒷부분은 사람이 읽으라고 붙인다.
//
//   쓰는 법
//     대상 산출물을 띄운 정적 서버의 아무 페이지에서 이 파일을 붙여 넣고
//       await window.__H.run('이름', '/index.html', 1280, 900)
//     자기시험
//       await window.__H.selftest()
window.__H = (function () {
  const PROPS = ['width','height','marginTop','marginRight','marginBottom','marginLeft',
    'paddingTop','paddingRight','paddingBottom','paddingLeft','color','backgroundColor',
    'display','position','top','left','fontSize','fontWeight','lineHeight','letterSpacing',
    'borderTopWidth','borderBottomWidth','borderTopColor','maxWidth','zIndex','textAlign'];
  let fr = null;

  function frame(w, h) {
    if (!fr) { fr = document.createElement('iframe'); document.body.appendChild(fr); }
    fr.style.cssText = 'position:fixed;left:0;top:0;border:0;z-index:2147483647;background:#fff';
    fr.width = w; fr.height = h;
    return fr;
  }

  // 안정 식별자. body 부터의 nth-child 경로 + 읽기용 이름
  function pathOf(n) {
    const parts = [];
    for (let e = n; e && e.nodeType === 1 && e.tagName !== 'BODY'; e = e.parentElement) {
      let i = 1;
      for (let s = e.previousElementSibling; s; s = s.previousElementSibling) i++;
      parts.unshift(e.tagName.toLowerCase() + ':nth-child(' + i + ')');
    }
    return 'body>' + parts.join('>');
  }

  function label(n) {
    const cls = (n.className && typeof n.className === 'string')
      ? '.' + n.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
    return n.tagName.toLowerCase() + (n.id ? '#' + n.id : '') + cls;
  }

  function collect(doc, win) {
    const out = { meta: { w: win.innerWidth, h: win.innerHeight,
                          theme: doc.documentElement.dataset.theme || '(none)' }, el: {} };
    // ★ 임의 제한 없음. 보이는 요소를 전부 모은다
    doc.querySelectorAll('body *').forEach(n => {
      if (!n.getClientRects().length) return;
      const cs = win.getComputedStyle(n), r = n.getBoundingClientRect();
      const v = { _box: [Math.round(r.x), Math.round(r.y),
                         Math.round(r.width), Math.round(r.height)] };
      PROPS.forEach(p => v[p] = cs[p]);
      out.el[pathOf(n) + ' | ' + label(n)] = v;
    });
    out.meta.count = Object.keys(out.el).length;      // 실제 센 수. 비교기가 대조한다
    out.meta.emptyStyle = [...doc.querySelectorAll('style')]
      .filter(s => !s.textContent.replace(/@[a-zA-Z-]+[^{};]*\{\s*\}/g, '').trim()).length;
    out.meta.styleBlocks = doc.querySelectorAll('style').length;
    return out;
  }

  function timed(ms) { return new Promise(r => setTimeout(r, ms)); }

  async function settle(doc, win) {
    // 폰트가 다 오기 전에 재면 폭이 흔들린다. 조건을 명시적으로 기다린다.
    //
    //   ★ 2026-09-02 실측 · 배경 탭에서는 requestAnimationFrame 이 «아예 안 돈다».
    //     그래서 여기서 채취가 통째로 멈췄다 (45초 넘게 응답 없음). 조용한 멈춤이다.
    //     두 기다림 모두 시간 제한과 경주시킨다. 최악이라도 늦어질 뿐 멈추지 않는다.
    //     배치 확정은 rAF 가 아니라 강제 reflow 로 보장한다.
    try { await Promise.race([doc.fonts.ready, timed(3000)]); } catch (e) {}
    await Promise.race([new Promise(r => win.requestAnimationFrame(() => r())), timed(300)]);
    doc.body.getBoundingClientRect();      // 배치를 지금 확정시킨다 (rAF 에 기대지 않는다)
    await timed(600);
  }

  async function load(url, w, h, theme) {
    const f = frame(w, h);
    await new Promise(res => { f.onload = res; f.src = url + '?t=' + Date.now(); });
    const doc = f.contentDocument;
    // 테마를 명시적으로 고정한다. 저장값이나 OS 설정에 따라 흔들리면 비교가 무의미하다
    doc.documentElement.setAttribute('data-theme', theme || 'light');
    await settle(doc, f.contentWindow);
    return doc;
  }

  return {
    async run(name, url, w, h, theme) {
      const doc = await load(url, w, h, theme);
      const s = collect(doc, fr.contentWindow);
      const res = await fetch('http://127.0.0.1:8824/' + name, {
        method: 'POST',
        headers: { 'X-Snap-Token': window.__SNAP_TOKEN || '' },
        body: JSON.stringify(s)
      });
      return { name, saved: res.ok, ...s.meta };
    },

    // ★ 답을 아는 입력. 네 번째 형제의 변경·소실을 잡는지 본다
    //   전에는 앞 3개만 모아서 이 둘을 통째로 놓쳤다.
    async selftest() {
      const f = frame(600, 400);
      const doc = f.contentDocument;
      doc.open();
      doc.write('<!doctype html><html><head><style>i{display:block;height:10px}</style>'
              + '</head><body><div id="w">'
              + '<i class="row">1</i><i class="row">2</i><i class="row">3</i>'
              + '<i class="row">4</i><i class="row">5</i></div></body></html>');
      doc.close();
      await settle(doc, f.contentWindow);
      const a = collect(doc, f.contentWindow);
      const rows = doc.querySelectorAll('i.row');
      if (rows.length !== 5) return { ok: false, why: '준비 실패' };
      if (a.meta.count !== Object.keys(a.el).length)
        return { ok: false, why: 'meta.count 가 실제와 다름' };
      if (Object.keys(a.el).length < 6)
        return { ok: false, why: '전수를 안 모음: ' + Object.keys(a.el).length };
      // 4번째만 바꾼다
      rows[3].style.height = '40px';
      await settle(doc, f.contentWindow);
      const b = collect(doc, f.contentWindow);
      const changed = Object.keys(a.el).filter(k => k in b.el
        && JSON.stringify(a.el[k]) !== JSON.stringify(b.el[k]));
      if (!changed.length) return { ok: false, why: '네 번째 요소 변경을 못 잡음' };
      // 4번째를 지운다
      rows[3].remove();
      await settle(doc, f.contentWindow);
      const c = collect(doc, f.contentWindow);
      if (Object.keys(c.el).length >= Object.keys(a.el).length)
        return { ok: false, why: '네 번째 요소 소실을 못 잡음' };
      // 열쇠가 유일한가
      if (new Set(Object.keys(a.el)).size !== Object.keys(a.el).length)
        return { ok: false, why: '열쇠가 겹침' };
      return { ok: true, 전수: Object.keys(a.el).length,
               변경검출: changed.length, 소실후: Object.keys(c.el).length };
    }
  };
})();
