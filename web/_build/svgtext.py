# -*- coding: utf-8 -*-
"""그림 안에서 «글자가 겹치는가 · 틀 밖으로 나가는가» (빌드 [3.48] 단계).

분류: 운영 · 작성: 오흥재 · 2026-09-14 · 상태: 확정
근거: 실측 (브라우저 getBBox 로 잰 값과 대조 · 알려진 결함 2종 재현 검출)

## 왜 있나

2026-09-13 에 팀장이 프로토콜 페이지를 보고 「글씨 겹침 · border 다름 ·
layout 선 넘어옴」을 지적했다. 브라우저에서 `getBBox` 로 15개 그림을 재니
실제로 둘이 겹치고 있었다.

  eval-v2-scan-meaning.svg   「?」 가 「광선이 아무것도 못 맞힘」 위에 앉음
  eval-v2-gap-geometry.svg   「틈 0.125 m」 와 「착지면 3.94 m」 가 10 px 겹침
  eval-v2-fig04.svg          위와 같은 그림의 옛 사본 (폭 780 이라 34 px 잘림)

**셋째 줄이 이 관문이 필요한 이유다.** 같은 그림이 두 이름으로 있었고 한쪽만
고쳐져 있었다. 사람 눈으로는 잡을 수 없다. 그림이 15개고 글자가 400개다.

## 어떻게 재나

브라우저 없이 잰다. `<text>` 의 x·y·font-size·text-anchor 를 읽고 글자 폭을
추정한다. 한글은 1.0em, ASCII 는 0.5em 으로 센다.

**추정이라 일부러 좁게 잡는다** (`SHRINK`). 실측 대조에서 추정이 실제보다
6~14 % 작았다. 좁게 잡으면 **아슬아슬한 것은 놓치고 확실한 것만 잡는다.**
관문이 틀린 이유로 배포를 막는 것보다 낫다. 정확한 값이 필요하면
`tools/svg_measure.html` 를 브라우저로 열어 `getBBox` 로 잰다.
"""
import html
import io
import math
import os
import re
import sys
import unicodedata

sys.stdout.reconfigure(encoding='utf-8')

TEXT = re.compile(r'<text([^>]*)>(.*?)</text>', re.S)
ATTR = re.compile(r'(\S+?)="([^"]*)"')
TAG = re.compile(r'<[^>]+>')

# 추정 폭을 실제보다 좁게 본다. 실측 대조에서 추정/실제가 0.88~0.94 였다.
SHRINK = 0.86
# 이만큼 겹쳐야 «겹쳤다» 고 센다. 글자 상자는 여백을 조금 물고 있다.
PAD = 3.0

# 선 굵기 한 벌 (tools/svg_strokes.py 와 같아야 한다)
SCALE = {'1', '1.6', '2', '2.8', '6'}


def _em(s):
    """글자열의 가로 폭을 em 단위로 어림한다."""
    w = 0.0
    for ch in s:
        if ch in ' \t':
            w += 0.30
        elif unicodedata.east_asian_width(ch) in ('W', 'F'):
            w += 1.00
        elif ch in '.,:·-−()':
            w += 0.32
        else:
            w += 0.52
    return w


def boxes(svg_text, skipped=None):
    """[(x1, x2, y1, y2, 글자)] · 못 읽는 것은 건너뛴다.

    `skipped` 에 리스트를 주면 «못 잰 글자» 를 거기 담는다. 조용히 빼면
    관문이 무엇을 안 보고 있는지 아무도 모른다.
    """
    out = []
    for m in TEXT.finditer(svg_text):
        a = dict(ATTR.findall(m.group(1)))
        # ★ 엔티티를 «먼저» 푼다. 안 풀면 `&#xC885;` 여덟 글자를 ASCII 여덟
        #   자로 세서 한 글자짜리가 여덟 배로 부풀고, 그 그림이 전부 「틀 밖」
        #   으로 잡힌다. 처음 돌렸을 때 거짓 경보 4건이 그래서 났다.
        s = html.unescape(TAG.sub('', m.group(2))).strip()
        if not s:
            continue
        # ★ 회전·기울임이 걸린 글자는 여기서 못 잰다. x·y 는 회전 «전» 좌표라
        #   가로 폭을 더해도 실제 자리가 아니다. `architecture.svg` 의
        #   rotate(-90) 세로 글자가 「44 px 넘침」으로 잡혔는데 화면에서는
        #   멀쩡했다. 못 재는 것은 «안 재고 센다». 조용히 빼지 않는다.
        if 'transform' in a:
            if skipped is not None:
                skipped.append(s)
            continue
        try:
            x = float(a.get('x', 'nan'))
            y = float(a.get('y', 'nan'))
            fs = float(a.get('font-size', '12'))
        except ValueError:
            continue
        if math.isnan(x) or math.isnan(y):
            continue
        w = _em(s) * fs * SHRINK
        anc = a.get('text-anchor', 'start')
        if anc == 'middle':
            x1 = x - w / 2
        elif anc == 'end':
            x1 = x - w
        else:
            x1 = x
        # 기준선(y)에서 위로 0.78em, 아래로 0.22em 이 글자 상자다
        out.append((x1, x1 + w, y - fs * 0.78, y + fs * 0.22, s))
    return out


def overlaps(bs):
    hits = []
    for i in range(len(bs)):
        for j in range(i + 1, len(bs)):
            a, b = bs[i], bs[j]
            if (a[0] + PAD < b[1] and b[0] + PAD < a[1]
                    and a[2] + PAD < b[3] and b[2] + PAD < a[3]):
                hits.append((a[4], b[4]))
    return hits


def outside(svg_text, bs):
    """viewBox 밖으로 나간 «글자». 그림 요소는 안 본다 (표식·잘라내기 틀이
    일부러 밖에 있는 경우가 있어 거짓 경보가 난다)."""
    m = re.search(r'viewBox="([^"]+)"', svg_text)
    if not m:
        return []
    try:
        vx, vy, vw, vh = [float(v) for v in m.group(1).split()]
    except ValueError:
        return []
    bad = []
    for x1, x2, y1, y2, s in bs:
        over = max(vx - x1, x2 - (vx + vw), vy - y1, y2 - (vy + vh))
        if over > 2:
            bad.append((s, round(over)))
    return bad


def _skipcount():
    sk = []
    boxes('<svg viewBox="0 0 400 200"><text x="1" y="1" transform="rotate(-90)">가</text></svg>', sk)
    return len(sk)


def _selftest():
    """알려진 답. 겹치게 만든 두 줄은 잡고, 떨어뜨린 두 줄은 안 잡는다."""
    def svg(body):
        return '<svg viewBox="0 0 400 200">%s</svg>' % body

    T = ('<text x="%s" y="%s" font-size="10" text-anchor="%s">%s</text>')
    bad = svg(T % (100, 50, 'start', '틈 0.125 m') + T % (130, 50, 'start', '착지면 3.94 m'))
    good = svg(T % (100, 50, 'start', '틈 0.125 m') + T % (200, 50, 'start', '착지면 3.94 m'))
    stack = svg(T % (100, 50, 'start', '틈 0.125 m') + T % (100, 90, 'start', '착지면 3.94 m'))
    out = svg(T % (370, 50, 'start', '바깥으로 나간 글자'))
    cases = [('겹친 것을 잡는다', len(overlaps(boxes(bad))), 1),
             ('떨어진 것은 안 잡는다', len(overlaps(boxes(good))), 0),
             ('줄이 다르면 안 잡는다', len(overlaps(boxes(stack))), 0),
             ('틀 밖을 잡는다', len(outside(out, boxes(out))), 1),
             ('틀 안은 안 잡는다', len(outside(good, boxes(good))), 0),
             ('엔티티를 한 글자로 센다',
              len(outside(svg(T % (300, 50, 'start', '&#xC885;&#xB8CC;')),
                          boxes(svg(T % (300, 50, 'start', '&#xC885;&#xB8CC;'))))), 0),
             ('회전 글자는 안 잡는다',
              len(outside(svg('<text x="34" y="370" font-size="10"'
                              ' transform="rotate(-90 34 370)">실패 원인 분석 · 학습 조건 개선</text>'),
                          boxes(svg('<text x="34" y="370" font-size="10"'
                                    ' transform="rotate(-90 34 370)">실패 원인 분석 · 학습 조건 개선</text>')))), 0),
             ('회전 글자를 «건너뛴 것» 으로 센다', _skipcount(), 1),
             ('엔티티 폭이 한글과 같다',
              round(boxes(svg(T % (0, 50, 'start', '&#xC885;&#xB8CC;')))[0][1], 3),
              round(boxes(svg(T % (0, 50, 'start', '종료')))[0][1], 3))]
    for name, got, want in cases:
        if got != want:
            return False, '%s -> %d (기대 %d)' % (name, got, want)
    return True, '%d칸' % len(cases)


def main(vault):
    ok, why = _selftest()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    print('  자기시험 통과 (%s)' % why)

    roots = [os.path.join(vault, 'assets')]
    seen, bad, skip, texts = 0, [], [], []
    for root in roots:
        for dirpath, _dirs, files in os.walk(root):
            for f in sorted(files):
                if not f.endswith('.svg'):
                    continue
                p = os.path.join(dirpath, f)
                try:
                    t = io.open(p, encoding='utf-8', errors='replace').read()
                except OSError:
                    continue
                seen += 1
                texts.append(t)
                bs = boxes(t, skip)
                if not bs:
                    continue
                for a, b in overlaps(bs):
                    bad.append('%s  글자 겹침: «%s» / «%s»' % (f, a[:22], b[:22]))
                for s, over in outside(t, bs):
                    bad.append('%s  틀 밖으로 %d: «%s»' % (f, over, s[:22]))

    if not seen:
        print('  [!] 검사한 그림이 0개입니다. 통과로 안 읽습니다')
        return False

    # ★ 2026-09-14 신설. 선 굵기가 «한 벌» 밖으로 새지 않았나.
    #   팀장이 「border 다름」이라 한 것이 이것이다. 그림 19장에 굵기가
    #   16가지였다. 한 벌로 모은 뒤에도 새 그림이 들어오면 또 벌어지므로 센다.
    #   고치는 도구는 tools/svg_strokes.py 다.
    stroke = set(re.findall(r'stroke-width="([\d.]+)"', ''.join(texts)))
    stray = sorted(stroke - SCALE, key=float)
    if stray:
        bad.append('한 벌에 없는 선 굵기: %s (한 벌 = %s)'
                   % (' · '.join(stray), ' · '.join(sorted(SCALE, key=float))))
        bad.append('  고치려면: python tools/svg_strokes.py --write')
    print('  그림 %d개 검사 · 글자 결함 %d곳 · 못 잰 글자 %d개(회전·변형)'
          % (seen, len(bad), len(skip)))
    if bad:
        for b in bad[:12]:
            print('     ' + b)
        print('      정확한 값은 tools/svg_measure.html 로 잽니다 (getBBox)')
        return False
    return True


if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    sys.exit(0 if main(os.path.dirname(here)) else 1)
