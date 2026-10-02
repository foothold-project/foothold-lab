"""U209 · 그래프 두 장을 꺾은선으로 (2026-10-02 팀장: 「막대만 고집하지 말자」).

23쪽 「전체 지형에서 무엇이 달라졌는지 먼저 보겠습니다」
    rr-double(표 둘) -> 두 패널 slopegraph. x = NVIDIA -> v1 -> v2, 지형마다 선 하나.
    숫자는 research_revision 의 _read/_rate 로 같은 CSV 를 같은 집계로 읽는다.
25쪽 「목표 속도를 바꾸면 기준선의 차이가 더 크게 드러납니다」
    .speedchart(막대) -> 꺾은선. x = 0.5/1.0/1.5 m/s, 선 3개.
    숫자는 build_presentation.speed_chart() 를 그대로 불러 쓴다(같은 CSV, 같은 집계).
    확장 고리는 '__SPEED_CHART__' 치환 «앞» 에 돌므로(build_presentation.build) 자리표와
    완성 블록 두 경우를 모두 받는다.

거는 법: FOOTHOLD_DECK_EXTRA=design.charts_u209 FOOTHOLD_DECK_EXTRA_CSS=charts_u209.css
"""
from pathlib import Path
import html
import re
import sys

from design.research_revision import _read, _rate, ROOTS, MODELS, NAMES, ROUGH, UNSEEN

HERE = Path(__file__).resolve().parents[1]
T_SLOPE = '전체 지형에서 무엇이 달라졌는지 먼저 보겠습니다'
T_SPEED = '목표 속도를 바꾸면 기준선의 차이가 더 크게 드러납니다'
ACCENT, WARN, NEUTRAL, DARK = '#0e7a6e', '#8a3a2f', '#61707d', '#20333d'
LOW_CUT = 50.0   # v2 성공률이 이 미만이면 「끝까지 낮은 선」(경고색)


def _spread(desired, gap, lo, hi):
    """오름차순 desired(y) 목록을 서로 gap 이상 떨어지게, [lo,hi] 안에서 밀어낸다."""
    pos = list(desired)
    n = len(pos)
    for _ in range(600):
        moved = False
        for i in range(n - 1):
            d = pos[i + 1] - pos[i]
            if d < gap - 1e-6:
                push = (gap - d) / 2
                pos[i] -= push
                pos[i + 1] += push
                moved = True
        for i in range(n):
            if pos[i] < lo:
                pos[i] = lo
                moved = True
            elif pos[i] > hi:
                pos[i] = hi
                moved = True
        if not moved:
            break
    for i in range(1, n):
        pos[i] = max(pos[i], pos[i - 1] + gap)
    over = pos[-1] - hi                      # 마지막 정리로 아래가 넘치면 묶음째 위로
    if over > 0:
        pos = [p - over for p in pos]
    assert pos[0] >= lo - 0.01 and pos[-1] <= hi + 0.01, ('label overflow', pos, lo, hi)
    return pos


def _place(items, gap, lo, hi):
    """items: [(desired_y, tiebreak, key)] -> {key: y}. 같은 y 는 tiebreak 로 위아래를 정한다."""
    order = sorted(items, key=lambda it: (it[0], it[1]))
    ys = _spread([it[0] for it in order], gap, lo, hi)
    return {it[2]: y for it, y in zip(order, ys)}


def _fmt(v):
    return f'{v:.1f}%'


# ---------------------------------------------------------------- 23쪽 slopegraph
def _slope_panel(terrains, data):
    W, H = 717, 380
    xs = {'NVIDIA': 96, 'v1': 282, 'v2': 468}
    top, bot = 62, 352                       # y(100%) · y(0%)
    y = lambda v: bot - (bot - top) * v / 100
    rows = []
    for t in terrains:
        vals = []
        for m in MODELS:
            r = [r for r in data[m] if r['terrain'] == t]
            assert len(r) == 300, (t, m, len(r))
            vals.append(_rate(r))
        rows.append((t, vals))
    assert len(rows) == 8, len(rows)
    cls = {t: ('c-low' if v[2] < LOW_CUT else 'c-up') for t, v in rows}
    right = _place([(y(v[2]), (-v[1], -v[0]), t) for t, v in rows], 22, top - 2, bot + 6)
    left = _place([(y(v[0]), (-v[1], -v[2]), t) for t, v in rows], 21, top - 2, bot + 6)

    s = [f'<svg class="u209" viewBox="0 0 {W} {H}" role="img" aria-label="세 모델의 지형별 성공률 변화">']
    for m, x in xs.items():
        s.append(f'<line class="u209-grid" x1="{x}" y1="{top}" x2="{x}" y2="{bot}"/>')
        s.append(f'<text class="u209-head" x="{x}" y="24" text-anchor="middle" dy="0.35em">{m}</text>')
    s.append(f'<line class="u209-grid" x1="{xs["NVIDIA"]}" y1="{top}" x2="{xs["v2"]}" y2="{top}"/>')
    s.append(f'<line class="u209-grid" x1="{xs["NVIDIA"]}" y1="{bot}" x2="{xs["v2"]}" y2="{bot}"/>')
    # 지시선(라벨이 점에서 밀려났을 때만) -> 선 -> 점 -> 글자 순서로 겹침을 정리한다.
    for t, v in rows:
        yl, yr = left[t], right[t]
        if abs(yl - y(v[0])) > 3:
            s.append(f'<line class="u209-lead" x1="{xs["NVIDIA"] - 12}" y1="{yl:.1f}" x2="{xs["NVIDIA"] - 6}" y2="{y(v[0]):.1f}"/>')
        if abs(yr - y(v[2])) > 3:
            s.append(f'<line class="u209-lead" x1="{xs["v2"] + 6}" y1="{y(v[2]):.1f}" x2="{xs["v2"] + 12}" y2="{yr:.1f}"/>')
    for want in ('c-up', 'c-low'):                 # 경고색 선을 맨 위에 그린다
        for t, v in rows:
            if cls[t] != want:
                continue
            pts = ' '.join(f'{x},{y(val):.1f}' for x, val in zip(xs.values(), v))
            s.append(f'<polyline class="u209-line {cls[t]}" points="{pts}"/>')
    for t, v in rows:
        for x, val in zip(xs.values(), v):
            s.append(f'<circle class="u209-dot {cls[t]}" cx="{x}" cy="{y(val):.1f}" r="5"/>')
    for t, v in rows:
        s.append(f'<text class="u209-lv" x="{xs["NVIDIA"] - 14}" y="{left[t]:.1f}" text-anchor="end" dy="0.35em">{_fmt(v[0])}</text>')
        s.append(f'<text x="{xs["v2"] + 16}" y="{right[t]:.1f}" dy="0.35em">{html.escape(NAMES[t])} <tspan class="u209-val">{_fmt(v[2])}</tspan></text>')
    s.append('</svg>')
    return ''.join(s)


def _slope_body(body):
    data = {m: _read(p) for m, p in ROOTS.items()}
    assert all(len(r) == 4800 for r in data.values()), [len(r) for r in data.values()]
    a = body.find('<div class="rr-double">')
    b = body.find('<p class="rr-condition">')
    assert a >= 0 and b > a and body.count('<div class="rr-double">') == 1, 'rr-double block not found once'
    key = (f'<div class="u209-key"><span><i style="background:{ACCENT}"></i>v2 50% 이상</span>'
           f'<span><i style="background:{WARN}"></i>v2 50% 미만 · 끝까지 낮음</span>'
           '<span>왼쪽 값 NVIDIA · 오른쪽 값 v2</span></div>')
    new = ('<div class="u209-slope"><div><h3>기존 6종 + 추가학습 관련 gap·rails</h3>' + _slope_panel(ROUGH + ['gap', 'rails'], data)
           + '</div><div><h3>세 정책에 공통으로 학습되지 않은 8종</h3>' + _slope_panel(UNSEEN, data) + '</div></div>' + key)
    return body[:a] + new + body[b:]


# ---------------------------------------------------------------- 25쪽 속도 꺾은선
def _speed_svg(data):
    labels = {'nv': 'NVIDIA', 'v1': 'v1', 'v2': 'v2'}
    colors = {'nv': NEUTRAL, 'v1': DARK, 'v2': ACCENT}
    assert list(data) == ['nv', 'v1', 'v2'] and all(len(v) == 3 for v in data.values()), data
    assert all(0 <= x <= 100 for v in data.values() for x in v), data
    W, H = 1472, 430
    xs = [250, 720, 1190]
    top, bot = 72, 372
    y = lambda v: bot - (bot - top) * v / 100
    s = [f'<svg class="u209 u209-speed" viewBox="0 0 {W} {H}" role="img" aria-label="목표 속도별 세 모델의 성공률">']
    # 범례(위) · 눈금(0/50/100) · 축 라벨
    lx = 250
    for m in data:
        s.append(f'<circle cx="{lx}" cy="20" r="6" fill="{colors[m]}"/>')
        s.append(f'<text class="u209-leg" x="{lx + 14}" y="20" dy="0.35em">{labels[m]}</text>')
        lx += 70 + 11 * len(labels[m])
    for tick in (0, 50, 100):
        s.append(f'<line class="u209-grid" x1="{xs[0] - 60}" y1="{y(tick):.1f}" x2="{xs[-1] + 20}" y2="{y(tick):.1f}"/>')
        s.append(f'<text class="u209-tick" x="{xs[0] - 72}" y="{y(tick):.1f}" text-anchor="end" dy="0.35em">{tick}%</text>')
    for x, lab in zip(xs, ['0.5 m/s', '1.0 m/s', '1.5 m/s *']):
        s.append(f'<text class="u209-x" x="{x}" y="{bot + 36}" text-anchor="middle" dy="0.35em">{lab}</text>')
    # 선: NVIDIA 1.0->1.5 는 학습 명령 범위 밖이라 점선
    for m, v in data.items():
        pts = [(x, y(val)) for x, val in zip(xs, v)]
        if m == 'nv':
            s.append(f'<polyline class="u209-line" stroke="{colors[m]}" points="{pts[0][0]},{pts[0][1]:.1f} {pts[1][0]},{pts[1][1]:.1f}"/>')
            s.append(f'<polyline class="u209-line u209-dash" stroke="{colors[m]}" points="{pts[1][0]},{pts[1][1]:.1f} {pts[2][0]},{pts[2][1]:.1f}"/>')
        else:
            s.append(f'<polyline class="u209-line" stroke="{colors[m]}" points="{" ".join(f"{x},{yy:.1f}" for x, yy in pts)}"/>')
    for m, v in data.items():
        for i, (x, val) in enumerate(zip(xs, v)):
            hollow = (m == 'nv' and i == 2)
            fill = 'var(--p-bg)' if hollow else colors[m]
            stroke = colors[m] if hollow else 'var(--p-bg)'
            s.append(f'<circle class="u209-dot" cx="{x}" cy="{y(val):.1f}" r="6" style="fill:{fill};stroke:{stroke}"/>')
    # 값 라벨: v2·NVIDIA 는 점 위, v1 은 점 아래(v2 선이 v1 선 위에 있으므로 위치가 곧 소속).
    # 예외: NVIDIA 1.5 는 점선이 위에서 내려오므로 점 아래. 마지막 열은 끝 라벨과 안 닿게 왼쪽으로.
    for m, v in data.items():
        for i, (x, val) in enumerate(zip(xs, v)):
            dy = 24 if (m == 'v1' or (m == 'nv' and i == 2)) else -20
            dx = -24 if i == 2 else 0
            s.append(f'<text class="u209-pv" x="{x + dx}" y="{y(val) + dy:.1f}" text-anchor="middle" dy="0.35em">{_fmt(val)}</text>')
    # 점선 구간 주석: 구간 가운데 «아래» (선이 글자를 지나지 않게)
    mx = (xs[1] + xs[2]) / 2
    my = y((data['nv'][1] + data['nv'][2]) / 2)
    s.append(f'<text class="u209-note" x="{mx:.0f}" y="{my + 48:.1f}" text-anchor="middle" dy="0.35em">* NVIDIA 학습 범위 밖</text>')
    # 오른쪽 끝 모델 이름(겹치면 밀어내고 지시선)
    ends = _place([(y(v[2]), (0,), m) for m, v in data.items()], 26, top - 4, bot + 4)
    for m, v in data.items():
        ye = ends[m]
        if abs(ye - y(v[2])) > 3:
            s.append(f'<line class="u209-lead" x1="{xs[2] + 8}" y1="{y(v[2]):.1f}" x2="{xs[2] + 22}" y2="{ye:.1f}"/>')
        s.append(f'<circle cx="{xs[2] + 30}" cy="{ye:.1f}" r="5" fill="{colors[m]}"/>')
        s.append(f'<text class="u209-end" x="{xs[2] + 42}" y="{ye:.1f}" dy="0.35em">{labels[m]}</text>')
    s.append('</svg>')
    return ''.join(s)


def _speed_body(body):
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import build_presentation as bp       # 같은 CSV · 같은 집계(speed_chart) 를 그대로 쓴다
    chart, data = bp.speed_chart()
    foot = re.findall(r'<p class="small">.*?</p>', chart)
    assert len(foot) == 1, foot
    svg = _speed_svg(data)
    if '__SPEED_CHART__' in body:                       # 현재 빌드 순서: 자리표가 아직 남아 있다
        assert body.count('__SPEED_CHART__') == 1
        return body.replace('__SPEED_CHART__', svg + foot[0])
    new, n = re.subn(r'<div class="speedchart">[\s\S]*?</div>(?=<p class="small">)', svg, body)
    assert n == 1, ('speedchart block not found once', n)
    return new


def apply(slides):
    hit = 0
    for s in slides:
        if s['title'] == T_SLOPE:
            s['body'] = _slope_body(s['body'])
            hit += 1
        elif s['title'] == T_SPEED:
            s['body'] = _speed_body(s['body'])
            hit += 1
    assert hit == 2, ('expected both chart slides', hit)
    for s in slides:
        assert '—' not in s['body']
    return slides
