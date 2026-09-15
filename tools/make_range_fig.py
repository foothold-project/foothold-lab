# -*- coding: utf-8 -*-
"""「연습한 틈」과 「평가의 틈」을 한 자에 놓는 그림을 만든다.

> 분류: 운영
> 작성: 오흥재 (Claude 세션) · 2026-09-15 06:10
> 근거: gap_width_range 실측 · 난이도 0.5 의 틈 폭 계산 · 규격 2 성적
> 요지: A 가 왜 0.5 에서 떨어지는지를 한 장으로 보이게 한다
> 상태: 확정

## 왜 만드나

팀장 지시: 「도식화, 곡선 등 추가되어야하는 부분이 있다면 그런 부분도 문제
되지 않게 진행」. 그리고 이번 작업의 목적은 **처음 보는 사람이 레시피의 흐름을
따라갈 수 있게** 하는 것이다.

이야기의 척추는 이 한 줄이다.

    A 가 연습한 최대 틈 0.20 m  <  평가 정본의 틈 0.275 m  <  B 가 연습한 최대 0.40 m

지금 보고서에는 이것이 «표» 로만 있다. 두 범위와 한 점의 관계는 **자 위에
놓아야** 한눈에 들어온다.

## 무엇을 그리나

가로축은 틈 폭(m) 하나다. 그 위에

  · 평가 하네스의 범위 (0.15 ~ 0.40) 와 난이도 눈금
  · A 가 연습한 범위 (0.05 ~ 0.20)
  · B 가 연습한 범위 (0.15 ~ 0.40)
  · 난이도 0.5 의 실제 틈 0.275 m 를 세로선으로
  · 그 선에서의 성적 (A 28 % · B 100 %)

## 색

브랜드 토큰만 쓴다. 파일 안에 팔레트를 넣어 `<img>` 로도 색이 살게 하고,
`tools/svg_theme.py` 가 다크 짝을 굽는다.
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import svg_selfcontained as SC  # noqa: E402

# 자의 범위. 눈금이 예쁘게 떨어지도록 0 ~ 0.45 로 둔다.
LO, HI = 0.0, 0.45
X0, X1 = 90.0, 700.0           # 그림 안에서 자가 차지하는 가로
# 그린 것의 아래끝이 324 이고 여백 규격은 20 이다 (`tools/svg_pad.py`).
# 처음에 360 으로 뒀더니 아래가 56 px 비었다. 브라우저에서 재고 맞췄다.
W, H = 760, 324

EVAL_LO, EVAL_HI = 0.15, 0.40   # 평가 하네스 gap_width_range
A_LO, A_HI = 0.05, 0.20         # A 가 연습한 범위
B_LO, B_HI = 0.15, 0.40         # B 가 연습한 범위
D05 = EVAL_LO + 0.5 * (EVAL_HI - EVAL_LO)   # 난이도 0.5 의 실제 틈


def x(v):
    return X0 + (v - LO) / (HI - LO) * (X1 - X0)


def esc(t):
    return (t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def band(y, lo, hi, fill, label, note, bold=False):
    """범위 막대 하나. 왼쪽에 이름, 막대 끝에 값."""
    o = []
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="22" rx="4" '
             'fill="%s"/>' % (x(lo), y, x(hi) - x(lo), fill))
    o.append('<text x="%.1f" y="%.1f" text-anchor="end" font-size="13" '
             'font-weight="%s" fill="var(--ink)">%s</text>'
             % (X0 - 12, y + 16, '700' if bold else '500', esc(label)))
    o.append('<text x="%.1f" y="%.1f" font-size="11.5" fill="var(--ink-2)">'
             '%s</text>' % (x(hi) + 10, y + 16, esc(note)))
    return o


def build():
    o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="-20 -20 %d %d" '
         'width="%d" height="%d" font-family="Pretendard, Malgun Gothic, '
         'sans-serif">' % (W + 40, H + 40, W, H)]

    o.append(SC.style_block())

    o.append('<text x="0" y="16" font-size="16" font-weight="700" '
             'fill="var(--ink)">연습한 틈과 평가의 틈</text>')
    o.append('<text x="0" y="38" font-size="12" fill="var(--ink-2)">'
             'A 는 평가의 틈을 연습에서 본 적이 없습니다</text>')

    # ── 자 ─────────────────────────────────────────────────────────
    ay = 300
    o.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="var(--rule)" '
             'stroke-width="1.6"/>' % (X0, ay, X1, ay))
    for v in (0.0, 0.10, 0.20, 0.30, 0.40):
        o.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" '
                 'stroke="var(--rule)" stroke-width="1"/>' % (x(v), ay, x(v), ay + 6))
        o.append('<text x="%.1f" y="%d" text-anchor="middle" font-size="11" '
                 'fill="var(--ink-3)">%.2f</text>' % (x(v), ay + 22, v))
    o.append('<text x="%.1f" y="%d" font-size="11" fill="var(--ink-3)">'
             '틈 폭 (m)</text>' % (X1 + 10, ay + 22))

    # ── 평가 범위 ──────────────────────────────────────────────────
    o += band(70, EVAL_LO, EVAL_HI, 'var(--rule-2)',
              '평가 하네스', '0.15 ~ 0.40 m')
    # 난이도 눈금 (0 · 0.5 · 1.0 이 어디인지)
    for d, lab in ((0.0, '난이도 0'), (0.5, '0.5'), (1.0, '1.0')):
        v = EVAL_LO + d * (EVAL_HI - EVAL_LO)
        o.append('<line x1="%.1f" y1="66" x2="%.1f" y2="96" '
                 'stroke="var(--ink-3)" stroke-width="1"/>' % (x(v), x(v)))
        o.append('<text x="%.1f" y="%d" text-anchor="middle" font-size="10.5" '
                 'fill="var(--ink-3)">%s</text>' % (x(v), 108, esc(lab)))

    # ── 두 모델이 연습한 범위 ──────────────────────────────────────
    o += band(150, A_LO, A_HI, 'var(--warn-soft)', 'A 가 연습한 틈',
              '0.05 ~ 0.20 m')
    o += band(200, B_LO, B_HI, 'var(--accent-soft)', 'B = foothold-v1',
              '0.15 ~ 0.40 m', bold=True)

    # ── 난이도 0.5 세로선 ──────────────────────────────────────────
    o.append('<line x1="%.1f" y1="60" x2="%.1f" y2="%d" stroke="var(--bad)" '
             'stroke-width="1.6" stroke-dasharray="4 3"/>' % (x(D05), x(D05), ay))
    o.append('<rect x="%.1f" y="240" width="152" height="40" rx="5" '
             'fill="var(--card)" stroke="var(--bad)" stroke-width="1"/>'
             % (x(D05) - 76))
    o.append('<text x="%.1f" y="256" text-anchor="middle" font-size="12" '
             'font-weight="700" fill="var(--bad)">정본 조건 · %.3f m</text>'
             % (x(D05), D05))
    o.append('<text x="%.1f" y="272" text-anchor="middle" font-size="11.5" '
             'fill="var(--ink-2)">A 28 %%  ·  B 100 %%</text>' % x(D05))

    # ── A 의 오른쪽 끝이 그 선에 못 미친다는 표시 ──────────────────
    o.append('<line x1="%.1f" y1="161" x2="%.1f" y2="161" stroke="var(--bad)" '
             'stroke-width="1" stroke-dasharray="3 3"/>' % (x(A_HI), x(D05)))
    o.append('<text x="%.1f" y="152" text-anchor="middle" font-size="10.5" '
             'fill="var(--bad)">0.075 m 모자람</text>'
             % ((x(A_HI) + x(D05)) / 2))

    o.append('</svg>')
    return '\n'.join(o)


def ay_bottom():
    """그림에서 가장 아래에 그린 것의 y. 축 눈금 글자가 제일 낮다."""
    return 300 + 22 + 4        # 자 y + 눈금 글자 baseline + 글자 아래 여유


def _selftest(svg):
    """그린 것이 말이 되나. 자리와 수를 되짚는다."""
    bad = []
    if not (x(A_HI) < x(D05) < x(B_HI)):
        bad.append('A 끝 < 정본 < B 끝 이 아니다')
    if abs(D05 - 0.275) > 1e-9:
        bad.append('난이도 0.5 의 틈이 0.275 가 아니다: %.4f' % D05)
    if abs((D05 - A_HI) - 0.075) > 1e-9:
        bad.append('모자라는 폭이 0.075 가 아니다')
    for need in ('0.275', 'A 28', 'B 100', '0.05 ~ 0.20', '0.15 ~ 0.40'):
        if need not in svg:
            bad.append('그림에 «%s» 가 없다' % need)
    if 'var(--' not in svg or ':root{' not in svg:
        bad.append('토큰이나 팔레트가 없다')
    # 아래 여백. 그린 것의 아래끝은 축 눈금 글자(ay + 22 = 322) 언저리다.
    bottom = ay_bottom()
    pad = (H + 20) - bottom          # viewBox 는 -20 에서 시작한다
    if not (12 <= pad <= 30):
        bad.append('아래 여백이 %d px (12~30 이어야 한다)' % pad)
    if bad:
        print('  [!] 자기시험 실패: %s' % ' · '.join(bad))
        return False
    print('  자기시험 9/9 통과 (자리 순서 · 수 · 팔레트 · 아래 여백 %d px)' % pad)
    return True


def main():
    svg = build()
    if not _selftest(svg):
        return 1
    n = 0
    for d in (os.path.join(LAB, 'docs', 'assets', 'visual'),
              os.path.join(LAB, 'web', 'assets', 'visual')):
        if not os.path.isdir(d):
            continue
        p = os.path.join(d, 'eval-v2-range.svg')
        io.open(p, 'w', encoding='utf-8', newline='\n').write(svg)
        n += 1
        print('  %s' % os.path.relpath(p, LAB))
    print('  %d곳에 썼습니다' % n)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
