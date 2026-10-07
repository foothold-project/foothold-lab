# -*- coding: utf-8 -*-
"""가우시안 스플래팅을 «처음 보는 사람» 에게 설명하는 그림 셋을 만든다.

> 분류: 운영
> 작성: 오흥재 (Claude 세션) · 2026-09-18 13:10
> 근거: 3DGS 원논문(arXiv 2308.04079) 파라미터 수 · COLMAP 소스의 삼각측량각
>       기본값 · 우리 1차 PoC 촬영 실측(카메라 이동 0.80 m)
> 요지: 표와 arXiv 번호만으로는 「이 기술이 무엇인지」가 안 전해진다. 세 장으로
>       가른다. 무엇을 담는가 · 왜 시차가 필요한가 · 왜 움직이는 것은 안 되는가
> 상태: 확정

## 왜 만드나

팀장 지적: 「기술에 대한 설명이라던가 이런게 자세하게 있어야, 이런 기술을
이렇게 활용하는구나 하고 우리 프로젝트에서 반영하고자 하는 것에 대해서도
프로젝트 기준으로는 이런 기술을 염두하고 있다」.

앞서 낸 문서는 표와 arXiv 번호만 늘어놓아 **읽고 배울 수가 없었다.** 기술의
«동작» 은 글보다 그림이 빠르다. 세 가지가 이해의 길목이다.

  1. 가우시안 하나가 무엇을 들고 있고 그것이 어떻게 화면에 찍히나
  2. 왜 카메라가 «움직여야» 깊이가 생기나  (우리 1차 실패의 원인)
  3. 왜 정지한 것은 되고 움직이는 사람은 안 되나  (동기 리그가 필요한 이유)

## 색과 규약

브랜드 토큰만 쓴다. `svg_selfcontained` 가 팔레트를 파일 안에 넣어 `<img>` 로
불러도 색이 살고, `tools/svg_theme.py` 가 다크 짝을 굽는다. 선 굵기는 이미
쓰이는 집합(1 · 1.6 · 2 · 2.8 · 6) 밖으로 나가지 않는다.
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import svg_selfcontained as SC  # noqa: E402

FONT = 'Pretendard, Malgun Gothic, sans-serif'


def esc(t):
    return (t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def head(w, h, title, sub):
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
         'viewBox="-20 -20 %d %d" font-family="%s">'
         % (w + 40, h + 40, w + 40, h + 40, FONT)]
    o.append(SC.style_block())
    o.append('<text x="0" y="16" font-size="17" font-weight="700" '
             'fill="var(--ink)">%s</text>' % esc(title))
    o.append('<text x="0" y="38" font-size="12" fill="var(--ink-2)">%s</text>'
             % esc(sub))
    return o


def lab(x, y, t, size=12, fill='var(--ink-2)', weight='400', anchor='start'):
    return ('<text x="%.1f" y="%.1f" font-size="%d" font-weight="%s" '
            'text-anchor="%s" fill="%s">%s</text>'
            % (x, y, size, weight, anchor, fill, esc(t)))


def box(x, y, w, h, fill='var(--card)', stroke='var(--rule)', rx=8):
    return ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%d" '
            'fill="%s" stroke="%s" stroke-width="1"/>'
            % (x, y, w, h, rx, fill, stroke))


def arrow(x1, y1, x2, y2, color='var(--ink-3)', wdt='1.6'):
    return ('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
            'stroke-width="%s" marker-end="url(#ah)"/>'
            % (x1, y1, x2, y2, color, wdt))


def defs_arrow():
    return ('<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            '<path d="M0 0 L10 5 L0 10 z" fill="var(--ink-3)"/></marker>'
            '<marker id="ahb" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            '<path d="M0 0 L10 5 L0 10 z" fill="var(--bad)"/></marker></defs>')


# ── 그림 1 · 가우시안 하나와 화면에 찍히는 네 단계 ──────────────────
def fig_what():
    W, H = 880, 372
    o = head(W, H, '가우시안 스플래팅이 담는 것',
             '장면을 삼각형 메시가 아니라 «흐릿한 타원» 수십만 개로 적는다')
    o.append(defs_arrow())

    # 왼쪽 · 가우시안 하나
    o.append(box(0, 58, 330, 292, 'var(--paper-2)'))
    o.append(lab(16, 82, '가우시안 하나가 들고 있는 숫자', 13,
                 'var(--ink)', '700'))
    cx, cy = 152, 152
    o.append('<ellipse cx="%d" cy="%d" rx="62" ry="30" '
             'transform="rotate(-24 %d %d)" fill="var(--accent-soft)" '
             'stroke="var(--accent)" stroke-width="2"/>' % (cx, cy, cx, cy))
    o.append('<circle cx="%d" cy="%d" r="3.2" fill="var(--accent)"/>'
             % (cx, cy))
    rows = [('위치', '3개', '어디에 있나'),
            ('크기', '3개', '세 축으로 얼마나 퍼지나'),
            ('회전', '4개', '어느 쪽으로 누웠나'),
            ('불투명도', '1개', '얼마나 진한가'),
            ('색 (SH)', '48개', '보는 각도마다 다른 색')]
    yy = 218
    for name, n, why in rows:
        o.append(lab(16, yy, name, 11, 'var(--ink)', '700'))
        o.append(lab(84, yy, n, 11, 'var(--accent)', '700'))
        o.append(lab(124, yy, why, 11, 'var(--ink-3)'))
        yy += 20
    o.append(lab(16, yy + 6, '모두 59개. 이 숫자만 사진에 맞춰 바꾼다', 11,
                 'var(--ink-2)', '700'))

    # 오른쪽 · 네 단계
    o.append(lab(366, 82, '이것이 화면에 찍히는 네 단계', 13,
                 'var(--ink)', '700'))
    steps = [('1', '납작하게 누른다',
              '3D 타원을 카메라에서 본 2D 타원으로'),
             ('2', '앞뒤로 줄 세운다',
              '카메라에 가까운 것부터'),
             ('3', '겹쳐 칠한다',
              '진한 것이 뒤를 가린다'),
             ('4', '사진과 견준다',
              '틀린 만큼 59개 숫자를 고친다')]
    sy = 102
    for i, (num, t, d) in enumerate(steps):
        o.append(box(366, sy, 494, 52))
        o.append('<circle cx="392" cy="%d" r="13" fill="var(--accent)"/>'
                 % (sy + 26))
        o.append(lab(392, sy + 31, num, 13, 'var(--card)', '700', 'middle'))
        o.append(lab(416, sy + 22, t, 12, 'var(--ink)', '700'))
        o.append(lab(416, sy + 40, d, 11, 'var(--ink-3)'))
        # 마지막 단계 뒤에는 화살표를 달지 않는다. 가리킬 곳이 없다
        if i < len(steps) - 1:
            o.append(arrow(613, sy + 54, 613, sy + 60))
        sy += 62

    o.append(lab(0, H - 4,
                 'NeRF 는 픽셀마다 광선 위 수십 점을 신경망에 묻는다. '
                 '스플래팅은 타원을 화면에 바로 뿌린다. 그래서 빠르다', 11,
                 'var(--ink-2)'))
    o.append('</svg>')
    return '\n'.join(o), W, H


# ── 그림 2 · 시차 ────────────────────────────────────────────────
def fig_parallax():
    W, H = 880, 416
    o = head(W, H, '카메라가 움직여야 깊이가 생긴다',
             '두 시점에서 같은 점을 보는 «각» 이 깊이의 정확도를 정한다')
    o.append(defs_arrow())

    CAM_Y, PT_Y, GND_Y = 136, 230, 276

    def panel(x0, title, note, ax, spread, color, tone, angword):
        p = [box(x0, 58, 416, 236, 'var(--paper-2)')]
        p.append(lab(x0 + 16, 82, title, 13, 'var(--ink)', '700'))
        p.append(lab(x0 + 16, 100, note, 11, 'var(--ink-3)'))
        p.append(lab(x0 + 208, 124, '각 %s' % angword, 11, color,
                     '700', 'middle'))
        gx = x0 + 208
        for sgn in (-1, 1):
            cxx = gx + sgn * ax
            p.append('<rect x="%.1f" y="%d" width="26" height="17" rx="3" '
                     'fill="var(--card)" stroke="%s" stroke-width="1.6"/>'
                     % (cxx - 13, CAM_Y, color))
            p.append('<line x1="%.1f" y1="%d" x2="%d" y2="%.1f" '
                     'stroke="%s" stroke-width="1"/>'
                     % (cxx, CAM_Y + 17, gx, PT_Y - spread, color))
        # 광선이 만나는 자리의 «깊이 불확실 구간»
        p.append('<ellipse cx="%d" cy="%d" rx="7" ry="%.1f" fill="%s" '
                 'stroke="%s" stroke-width="1.6"/>'
                 % (gx, PT_Y, spread, tone, color))
        p.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" '
                 'stroke="var(--ink-3)" stroke-width="2"/>'
                 % (x0 + 40, GND_Y, x0 + 376, GND_Y))
        p.append(lab(x0 + 208, GND_Y + 16, '땅', 11, 'var(--ink-3)',
                     '400', 'middle'))
        return p

    o += panel(0, '걸어다니며 찍는다', '두 시점이 멀다. 광선이 또렷하게 만난다',
               84, 9, 'var(--accent)', 'var(--accent-soft)', '넓다')
    o += panel(444, '한자리에서 둘러본다', '두 시점이 붙어 있다. 광선이 나란하다',
               24, 34, 'var(--bad)', 'var(--bad-soft)', '거의 없다')

    o.append(lab(0, 330, '깊이 오차는 각에 반비례한다', 13, 'var(--ink)', '700'))
    cells = [('16도', '0.18 %', 'COLMAP 이 첫 쌍에 요구하는 각'),
             ('1.5도', '1.9 %', '이보다 좁으면 점을 버린다'),
             ('0.1도', '29 %', '10 m 앞을 몇 cm 움직여 찍은 경우')]
    bx = 0
    for ang, err, why in cells:
        o.append(box(bx, 342, 286, 46))
        o.append(lab(bx + 14, 364, ang, 13, 'var(--ink)', '700'))
        o.append(lab(bx + 62, 364, err, 13,
                     'var(--bad)' if '29' in err else 'var(--accent)', '700'))
        o.append(lab(bx + 14, 381, why, 10, 'var(--ink-3)'))
        bx += 297

    o.append(lab(0, H - 2,
                 '우리 1차 촬영은 36초 동안 0.80 m 움직였다. '
                 '그 각으로 첫 쌍이 성립하는 거리는 2.85 m 까지다', 11,
                 'var(--bad)', '700'))
    o.append('</svg>')
    return '\n'.join(o), W, H


# ── 그림 3 · 정지한 것과 움직이는 것 ──────────────────────────────
def fig_moving():
    W, H = 880, 356
    o = head(W, H, '정지한 것은 되고 움직이는 사람은 안 되는 이유',
             '삼각측량에는 «같은 순간에» 같은 점을 보는 광선이 둘 이상 필요하다')
    o.append(defs_arrow())

    # 왼쪽 · 정지
    o.append(box(0, 58, 416, 230, 'var(--paper-2)'))
    o.append(lab(16, 82, '정지한 것 · 카메라 한 대로 된다', 13,
                 'var(--ink)', '700'))
    o.append(lab(16, 100, '내가 걸어다니는 동안 대상은 그대로다', 11,
                 'var(--ink-3)'))
    tx, ty = 208, 226
    for i, dx in enumerate((-120, 0, 120)):
        cx = 208 + dx
        o.append('<rect x="%d" y="126" width="26" height="17" rx="3" '
                 'fill="var(--card)" stroke="var(--accent)" '
                 'stroke-width="1.6"/>' % (cx - 13))
        o.append(lab(cx, 121, 't%d' % (i + 1), 10, 'var(--accent)',
                     '700', 'middle'))
        o.append('<line x1="%d" y1="144" x2="%d" y2="%d" '
                 'stroke="var(--accent)" stroke-width="1"/>' % (cx, tx, ty - 6))
    o.append('<circle cx="%d" cy="%d" r="7" fill="var(--accent-soft)" '
             'stroke="var(--accent)" stroke-width="2"/>' % (tx, ty))
    o.append(lab(208, 258, '광선 셋이 한 점에서 만난다', 11,
                 'var(--accent)', '700', 'middle'))
    o.append(lab(208, 276, '깊이가 정해진다', 11, 'var(--ink-2)',
                 '400', 'middle'))

    # 오른쪽 · 움직임
    o.append(box(444, 58, 416, 230, 'var(--paper-2)'))
    o.append(lab(460, 82, '움직이는 것 · 한 대로는 안 된다', 13,
                 'var(--ink)', '700'))
    o.append(lab(460, 100, '내가 도는 동안 대상도 자리를 옮긴다', 11,
                 'var(--ink-3)'))
    for i, (dx, tdx) in enumerate(((-120, -66), (0, 0), (120, 66))):
        cx = 652 + dx
        px = 652 + tdx
        o.append('<rect x="%d" y="126" width="26" height="17" rx="3" '
                 'fill="var(--card)" stroke="var(--bad)" '
                 'stroke-width="1.6"/>' % (cx - 13))
        o.append(lab(cx, 121, 't%d' % (i + 1), 10, 'var(--bad)',
                     '700', 'middle'))
        o.append('<line x1="%d" y1="144" x2="%d" y2="220" '
                 'stroke="var(--bad)" stroke-width="1" '
                 'stroke-dasharray="4 3"/>' % (cx, px))
        o.append('<circle cx="%d" cy="226" r="6" fill="var(--bad-soft)" '
                 'stroke="var(--bad)" stroke-width="1.6"/>' % px)
    o.append(lab(652, 258, '만날 두 광선이 «같은 순간» 에 없다', 11,
                 'var(--bad)', '700', 'middle'))
    o.append(lab(652, 276, '깊이가 안 정해진다', 11, 'var(--ink-2)',
                 '400', 'middle'))

    o.append(lab(0, 316, '그래서 동기화된 카메라 여러 대가 필요하다', 13,
                 'var(--ink)', '700'))
    o.append(lab(0, 336,
                 '한 순간을 수십 대가 동시에 찍으면 그 «정지된 순간» 을 '
                 '복원할 수 있다. 상용 쇼케이스의 인물 장면이 카메라 50 대에서 '
                 '240 대를 쓰는 이유다', 11, 'var(--ink-2)'))
    o.append(lab(0, H - 2,
                 '동기 오차 x 사지 속도가 그대로 공간 오차다. '
                 '30 fps 한 프레임(33 ms) 어긋나면 3 m/s 로 움직이는 손이 '
                 '10 cm 어긋난다', 11, 'var(--ink-3)'))
    o.append('</svg>')
    return '\n'.join(o), W, H


FIGS = [('gs-what-is.svg', fig_what),
        ('gs-parallax.svg', fig_parallax),
        ('gs-moving.svg', fig_moving)]


def _selftest(name, svg, W, H):
    bad = []
    if 'var(--' not in svg or ':root{' not in svg:
        bad.append('토큰이나 팔레트가 없다')
    if chr(8212) in svg:
        bad.append('em dash 가 있다')
    for w in ('stroke-width="1.2"', 'stroke-width="1.4"',
              'stroke-width="3"', 'stroke-width="4"'):
        if w in svg:
            bad.append('쓰지 않는 선 굵기: %s' % w)
    need = {
        'gs-what-is.svg': ['59개', '48개', '색 (SH)', '납작하게 누른다'],
        'gs-parallax.svg': ['16도', '0.18 %', '29 %', '0.80 m', '2.85 m'],
        'gs-moving.svg': ['깊이가 정해진다', '깊이가 안 정해진다',
                          '10 cm', '240 대'],
    }[name]
    for t in need:
        if t not in svg:
            bad.append('«%s» 가 없다' % t)
    # 그린 것이 틀 밖으로 나가지 않았나 (x 좌표만 거칠게 본다)
    import re
    for m in re.finditer(r'\sx="(-?\d+(?:\.\d+)?)"', svg):
        if float(m.group(1)) > W + 12:
            bad.append('x=%s 가 틀(%d) 밖이다' % (m.group(1), W))
            break
    if bad:
        for b in bad:
            print('  [X] %s · %s' % (name, b))
        return False
    return True


def main():
    ok, n = True, 0
    outs = [d for d in (os.path.join(LAB, 'docs', 'assets', 'visual'),
                        os.path.join(LAB, 'web', 'assets', 'visual'))
            if os.path.isdir(d)]
    for name, fn in FIGS:
        svg, W, H = fn()
        if not _selftest(name, svg, W, H):
            ok = False
            continue
        for d in outs:
            io.open(os.path.join(d, name), 'w', encoding='utf-8',
                    newline='\n').write(svg)
            n += 1
        print('  %-18s %5d 글자 · %d곳' % (name, len(svg), len(outs)))
    print('  %d개 파일을 썼습니다' % n)
    # ★ 이 도구는 «밝은 판» 만 만든다. 사이트에는 테마 토글이 있어서 짝이
    #   없으면 빌드가 배포를 막는다. 그리고 `svg_theme.py` 는 원본 파일도
    #   함께 고치므로, 이 도구를 다시 돌리면 그 고침이 지워진다.
    #   그래서 순서가 «항상» 이렇다. 잊으면 빌드가 잡아 주지만 한 번 더 돈다.
    print('  [다음] python tools/svg_theme.py --write  (다크 짝을 굽는다)')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
