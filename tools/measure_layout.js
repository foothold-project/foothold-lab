// 화면이 «쓸 만한가» 를 잰다. 브라우저 콘솔에 붙여 넣는다.
//
// 왜 있나 (2026-09-13).
//   `tools/verify_live.py` 가 41항목을 «전부 통과» 시킨 화면이 실제로는
//   못 쓰는 상태였다. 입구 여섯을 `<nav>` 로 만들었더니 전역 규칙
//   `nav:not(.gnav){height:calc(100vh - …)!important}` 에 걸려 입구 하나가
//   1,273px 이 됐고 첫 문서 카드가 561 -> 3,404 로 밀렸다.
//
//   개수를 세는 검사는 「있는가」를 묻는다. 이 파일은 「몇 px 인가」를 묻는다.
//   둘 다 있어야 한다. 하나만으로는 오늘 같은 사고를 못 막는다.
//
// 쓰는 법: 대상과 «같은 출처» 페이지에서 돌린다. 창 크기를 바꾸지 않는다.
//   창 크기 조절은 성공을 찍어도 실제로 안 바뀐 적이 있어서, 폭은
//   iframe 으로 만든다 (memory: chrome-resize-iframe-viewport).
//
//   await measureHub(1440)   // PC
//   await measureHub(390)    // 휴대폰

async function measureHub(w, path) {
  path = path || '/hub-research.html';
  const f = document.createElement('iframe');
  f.style.cssText =
    'position:fixed;left:-9999px;top:0;border:0;width:' + w + 'px;height:2600px';
  f.src = path;
  document.body.appendChild(f);
  await new Promise(function (r) { f.onload = r; });
  await new Promise(function (r) { setTimeout(r, 500); });

  const d = f.contentDocument, W = f.contentWindow;
  const q = function (s) { return d.querySelector(s); };
  const h = function (el) {
    return el ? Math.round(el.getBoundingClientRect().height) : null;
  };
  const top = function (el) {
    return el ? Math.round(el.getBoundingClientRect().top + W.scrollY) : null;
  };

  const card = d.querySelector('.evs3 .ev3') || d.querySelector('.ev3');
  const body = card ? card.querySelector('.eb3') : null;

  // 가로로 삐져나온 «범인» 도 찾는다. 넘침만 알면 어디를 고칠지 모른다.
  let worst = null, worstBy = 0;
  d.querySelectorAll('*').forEach(function (el) {
    const r = el.getBoundingClientRect();
    if (r.right > w + 1 && r.right - w > worstBy) {
      worstBy = r.right - w; worst = el;
    }
  });

  // 예산. 넘으면 화면이 못 쓰게 된 것이다.
  const budget = w >= 1000
    ? { firstCardTop: 700, doorH: 60, relH: 260, bodyW: 0 }
    : { firstCardTop: 1000, doorH: 120, relH: 480, bodyW: 200 };

  const m = {
    width: w,
    relH: h(q('.rel3')),
    heroH: h(q('.hero3')),
    pinsH: h(q('.tkcs3')),
    boardH: h(q('#terrain-board')),
    doorsH: h(q('.dr3')),
    doorH: h(q('.dr3 a')),
    firstCardTop: top(card),
    cardBodyW: body ? Math.round(body.getBoundingClientRect().width) : null,
    overflowX: Math.max(0, d.documentElement.scrollWidth - w),
    overflowBy: worst
      ? worst.tagName.toLowerCase() + '.' +
        String(worst.className).split(' ')[0] + ' +' + Math.round(worstBy)
      : null
  };

  const fail = [];
  if (m.firstCardTop > budget.firstCardTop) {
    fail.push('첫 문서 카드가 ' + m.firstCardTop + 'px (예산 ' +
              budget.firstCardTop + ')');
  }
  if (m.doorH > budget.doorH) {
    fail.push('입구 하나가 ' + m.doorH + 'px (예산 ' + budget.doorH + ')');
  }
  if (m.relH > budget.relH) {
    fail.push('배포 블록이 ' + m.relH + 'px (예산 ' + budget.relH + ')');
  }
  if (m.overflowX > 0) {
    fail.push('가로로 ' + m.overflowX + 'px 넘침 · ' + m.overflowBy);
  }
  if (budget.bodyW && m.cardBodyW && m.cardBodyW < budget.bodyW) {
    fail.push('카드 본문 폭이 ' + m.cardBodyW + 'px (최소 ' + budget.bodyW + ')');
  }

  f.remove();
  m.verdict = fail.length ? fail : '예산 안에 듭니다';
  return m;
}

// 두 폭을 한 번에.
async function measureBoth(path) {
  return {
    pc: await measureHub(1440, path),
    mo: await measureHub(390, path)
  };
}
