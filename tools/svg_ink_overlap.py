# -*- coding: utf-8 -*-
"""도해에서 «글자가 무엇에 파묻혔는가» 를 찾는다.

분류: 운영 · 작성: 오흥재 · 2026-09-14 · 상태: 확정
근거: 실측 (브라우저 getBBox · 고의 결함 주입 시험)
요지: 글자가 상자·띠 안에 들어가면 화면에서 덮인다. 글자끼리만 보면 못 잡는다

## 왜 있나

팀장이 **네 번째로** 짚었다. 「`gap 지형 광선 187개가 어디를 비추나` 에서
도식화 밑에 라인 긋고 텍스트로 `같은 광선 22개가 …` 라는 것도 라인에 지금
글씨가 겹쳐있잖아」.

재 보니 맞았다.

    글자  «같은 광선 22개가 …»        y 335~351
    상자  격자 바탕 405x315          y  43~358
    상자  빗나간 광선 영역 (점선)      y  46~354

**글자가 상자 «안» 에 있었다.** 상자가 y 358 까지 내려오는데 글자를 y 348 에
두어 분홍 띠가 글자 위를 지나갔다.

## 왜 기존 관문이 못 잡았나

`[3.48]` 은 **글자끼리** 의 겹침만 본다. 그리고 내가 급히 만든 「선-글자」
검사는 «가늘고 긴 것» 만 선으로 셌다. 이건 405x315 짜리 큰 상자라 선이 아니다.

**「무엇과 겹치나」를 미리 정하면 그 목록 밖에서 새어 나간다.**
그래서 여기서는 종류를 안 가리고 **글자를 덮는 모든 것**을 본다.

## 무엇을 겹침으로 보나

글자 상자가 다른 도형과 겹치는데, 그 도형이

- 글자보다 **뒤에 그려지고** (SVG 는 뒤가 위에 온다)
- 투명하지 않은 채움이나 선을 가지면

글자가 덮인다. 앞에 그려진 바탕은 정상이라 안 센다.

## 쓰는 법

내용 상자와 그리기 순서는 브라우저만 안다. `tools/svg_measure.html` 을 열어
찍힌 값을 `--json` 으로 넘긴다. 파이썬 혼자서는 글자 폭을 못 잰다.

    python tools/svg_ink_overlap.py --json <잰값.json>
    python tools/svg_ink_overlap.py --selftest
"""
import io
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

MEASURE_JS = r"""
// 브라우저 콘솔에 붙여 넣는다. 결과 JSON 을 파일로 저장해 --json 으로 넘긴다.
(async () => {
  const files = [...document.querySelectorAll('img[src*=".svg"]')]
    .map(i => i.src.split('/').pop().split('?')[0]);
  const host = document.createElement('div');
  host.setAttribute('style', 'position:absolute;left:-99999px;top:0;width:1400px');
  document.body.appendChild(host);
  const out = {};
  for (const f of [...new Set(files)]) {
    host.innerHTML = await (await fetch('/assets/visual/' + f)).text();
    const svg = host.querySelector('svg');
    if (!svg) continue;
    svg.setAttribute('width', '1000');
    const all = [...svg.querySelectorAll('text,rect,circle,ellipse,path,polygon,line,image')];
    out[f] = all.map((e, i) => {
      let b; try { b = e.getBBox(); } catch (x) { return null; }
      if (!b.width && !b.height) return null;
      const cs = getComputedStyle(e);
      return {i, tag: e.tagName, s: (e.textContent || '').trim().slice(0, 40),
              x: +b.x.toFixed(1), y: +b.y.toFixed(1),
              w: +b.width.toFixed(1), h: +b.height.toFixed(1),
              fill: cs.fill, stroke: cs.stroke, op: cs.opacity};
    }).filter(Boolean);
  }
  host.remove();
  console.log(JSON.stringify(out));
})();
"""

CLEAR = ('none', 'rgba(0, 0, 0, 0)', 'transparent')


def buried(items):
    """글자를 덮는 것 목록. `items` 는 그리기 순서대로."""
    out = []
    for t in items:
        if t['tag'] != 'text':
            continue
        for o in items:
            if o is t or o['i'] <= t['i']:
                continue                      # 앞에 그려진 것은 글자 뒤에 온다
            if o['tag'] == 'text':
                continue                      # 글자끼리는 [3.48] 이 본다
            if o['fill'] in CLEAR and o['stroke'] in CLEAR:
                continue
            if float(o.get('op', 1) or 1) < 0.05:
                continue
            ox = min(t['x'] + t['w'], o['x'] + o['w']) - max(t['x'], o['x'])
            oy = min(t['y'] + t['h'], o['y'] + o['h']) - max(t['y'], o['y'])
            if ox > 1 and oy > 0.5:
                out.append((t['s'], o['tag'], round(ox), round(oy)))
                break
    return out


def _selftest():
    """알려진 답."""
    def it(i, tag, x, y, w, h, s='', fill='rgb(0,0,0)'):
        return {'i': i, 'tag': tag, 's': s, 'x': x, 'y': y, 'w': w, 'h': h,
                'fill': fill, 'stroke': 'none', 'op': '1'}
    cases = [
        ('글자가 뒤 상자에 덮임',
         [it(0, 'text', 0, 100, 200, 16, '같은 광선 22개'), it(1, 'rect', 0, 40, 400, 300)], 1),
        ('바탕이 앞에 그려짐 (정상)',
         [it(0, 'rect', 0, 40, 400, 300), it(1, 'text', 0, 100, 200, 16, '제목')], 0),
        ('안 겹침',
         [it(0, 'text', 0, 400, 200, 16, '아래 글'), it(1, 'rect', 0, 40, 400, 300)], 0),
        ('투명한 것은 안 셈',
         [it(0, 'text', 0, 100, 200, 16, '글'),
          it(1, 'rect', 0, 40, 400, 300, fill='none')], 0),
        ('글자끼리는 안 셈',
         [it(0, 'text', 0, 100, 200, 16, '가'), it(1, 'text', 10, 102, 100, 16, '나')], 0),
    ]
    ok = 0
    for name, items, want in cases:
        got = len(buried(items))
        good = got == want
        ok += good
        print('  %s %-22s 기대 %d · 결과 %d' % ('OK ' if good else '[X]', name, want, got))
    print('  %d/%d' % (ok, len(cases)))
    return ok == len(cases)


def main():
    if '--selftest' in sys.argv:
        return 0 if _selftest() else 1
    if '--measure' in sys.argv:
        print(MEASURE_JS)
        return 0
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--json' not in sys.argv or not args:
        print(__doc__.split('## 쓰는 법')[1].strip())
        return 2
    data = json.load(io.open(args[0], encoding='utf-8'))
    bad = 0
    for f, items in sorted(data.items()):
        hits = buried(items)
        if hits:
            bad += len(hits)
            for s, tag, ox, oy in hits[:3]:
                print('  [!] %-26s «%s» 가 <%s> 에 덮임 %dx%dpx'
                      % (f, s[:26], tag, ox, oy))
    print('  도해 %d장 · 글자가 덮인 자리 %d곳' % (len(data), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
