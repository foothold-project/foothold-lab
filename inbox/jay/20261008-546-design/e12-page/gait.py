# -*- coding: utf-8 -*-
"""저속 걸음 그림: 발 접촉 시간표 (gait diagram) + 쌍 동기율 표. page.html 의 <!--GAIT--> 자리에 넣을 HTML 을 만든다.

원자료: _eval/out/legacy/<tag>/timeseries/flat_fwd0X_ep000.parquet (lab 93 열 · foot_contact_*_n = 발 수직 접촉력 크기 N)
접촉 = 5 N 넘음. 창 = 2~19 s (출발 2 s 제외). 그림은 8~11 s (3 s).
"""
import os

import numpy as np
import pandas as pd

LEG = 'C:/isaac/ext/go2_rl_robotlab/_eval/out/legacy'
FEET = [('fl', '앞 왼발'), ('fr', '앞 오른발'), ('rl', '뒤 왼발'), ('rr', '뒤 오른발')]
SPEEDS = [('fwd01', 0.1), ('fwd02', 0.2), ('fwd03', 0.3), ('fwd05', 0.5)]
RUNS = [('E1', 'fr_m20499_flat'), ('E2', 'e2_m20499_flat')]


def load(tag, cell):
    d = pd.read_parquet(os.path.join(LEG, tag, 'timeseries', f'flat_{cell}_ep000.parquet'))
    t = d['t_s'].to_numpy()
    c = {k: d[f'foot_contact_{k}_n'].to_numpy() > 5 for k, _ in FEET}
    return t, c, d['vx_mps'].to_numpy()


def stats(t, c, vx):
    w = (t >= 2) & (t <= 19)
    C = {k: v[w] for k, v in c.items()}
    same = lambda a, b: float((C[a] == C[b]).mean())
    steps = {k: int(((~C[k][:-1]) & (C[k][1:])).sum()) for k in C}
    return {'vx': float(vx[w].mean()), 'front': same('fl', 'fr'), 'diag': (same('fl', 'rr') + same('fr', 'rl')) / 2,
            'fsteps': steps['fl'] + steps['fr'], 'hsteps': steps['rl'] + steps['rr'],
            'fduty': (C['fl'].mean() + C['fr'].mean()) / 2}


def svg(run, tag):
    W, rowh, lab, top = 980, 13, 86, 26
    span = (8.0, 11.0)
    blockh = 4 * rowh + 30
    H = top + len(SPEEDS) * blockh + 26
    out = [f'<svg viewBox="0 0 {W} {H}" class="gaitsvg" role="img" aria-label="{run} model_20499 평지 전진 속도별 발 접촉 시간표">']
    x0, x1 = lab + 8, W - 150
    X = lambda tt: x0 + (x1 - x0) * (tt - span[0]) / (span[1] - span[0])
    for s in np.arange(span[0], span[1] + 1e-9, 0.5):
        out.append(f'<line x1="{X(s):.1f}" x2="{X(s):.1f}" y1="{top - 6}" y2="{H - 22}" class="gl"/>')
        out.append(f'<text x="{X(s):.1f}" y="{H - 8}" class="tk mid">{s:.1f} s</text>')
    for i, (cell, v) in enumerate(SPEEDS):
        t, c, vx = load(tag, cell)
        st = stats(t, c, vx)
        y0 = top + i * blockh
        out.append(f'<text x="0" y="{y0 + 10}" class="hd">전진 {v:.1f} m/s 명령</text>')
        out.append(f'<text x="{x1 + 12}" y="{y0 + 10}" class="st">실제 {st["vx"]:.2f} m/s</text>')
        out.append(f'<text x="{x1 + 12}" y="{y0 + 28}" class="st">앞발 같이 {st["front"] * 100:.0f} %</text>')
        out.append(f'<text x="{x1 + 12}" y="{y0 + 44}" class="st">대각선 같이 {st["diag"] * 100:.0f} %</text>')
        out.append(f'<text x="{x1 + 12}" y="{y0 + 60}" class="st">디딤 앞 {st["fsteps"]} · 뒤 {st["hsteps"]}</text>')
        m = (t >= span[0]) & (t <= span[1])
        tt = t[m]
        for j, (k, name) in enumerate(FEET):
            y = y0 + 16 + j * rowh
            out.append(f'<text x="{lab}" y="{y + rowh - 3}" class="ft end">{name}</text>')
            out.append(f'<rect x="{x0}" y="{y + 1}" width="{x1 - x0}" height="{rowh - 3}" class="air"/>')
            on = c[k][m]
            j0 = None
            for q in range(len(tt) + 1):
                if q < len(tt) and on[q] and j0 is None:
                    j0 = q
                if (q == len(tt) or not on[q]) and j0 is not None:
                    a, b = tt[j0], tt[q - 1] + 0.02
                    cls = 'cf' if k in ('fl', 'fr') else 'ch'
                    out.append(f'<rect x="{X(a):.1f}" y="{y + 1}" width="{max(1.0, X(b) - X(a)):.1f}" height="{rowh - 3}" class="{cls}"/>')
                    j0 = None
    out.append('</svg>')
    return '\n'.join(out)


if __name__ == '__main__':
    parts = []
    for run, tag in RUNS:
        parts.append(f'<figure class="gaitfig"><h3>{run} · model_20499 · 평지 · episode 0</h3><div class="gaitbox">{svg(run, tag)}</div></figure>')
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gait_block.html'), 'w', encoding='utf-8').write('\n'.join(parts))
    for run, tag in RUNS:
        for cell, v in SPEEDS:
            print(run, cell, {k: round(x, 2) for k, x in stats(*load(tag, cell)).items()})
