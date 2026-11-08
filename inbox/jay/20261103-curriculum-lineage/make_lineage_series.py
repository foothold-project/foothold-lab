"""Figures for the lineage series [계보 0] and [계보 4] from raw records (lead 11/08 23:2x, team lead: 글만 넣지 않을 것).

- S4-1 map share per update: EX-41 local 0~6000 and EX-42 stage zero 0~1000 (map_stats.jsonl use_gt_frac)
- S4-2 hard terrain fast-forward error, parent m12000 / m12750 / m13000, L3~L5 x map mode (map_modes.json, same numbers as [계보 4] 4 절)
- S0-1 EX-36A parent vs EX-38 survival by command (RESULT-EX36A-EX38-1029.md table)
Outputs go to docs/assets/visual/ex41-lineage and web/assets/visual/ex41-lineage (same bytes).
"""
import json, os, re, shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = ['Malgun Gothic', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OUTS = [os.path.join(LAB, 'docs', 'assets', 'visual', 'ex41-lineage'), os.path.join(LAB, 'web', 'assets', 'visual', 'ex41-lineage')]
EX41 = 'C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/map_stats.jsonl'
S0 = 'C:/Users/AI-WS01/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914/map_stats.jsonl'
HARD = {'m12000': 'D:/mai-tmp/lead/ex42_s0_map64/hard/m12000_L{L}/map64',
        'm12750': 'D:/mai-tmp/lead/ex42_s0_map64/hard/m12750_L{L}/map64',
        'm13000': 'D:/mai-tmp/lead/ex42_s0_end/map64_L{L}/map64'}
EX38 = os.path.join(LAB, 'inbox', 'jay', '20261029-experiments', 'RESULT-EX36A-EX38-1029.md')


def save(fig, name):
    p0 = os.path.join(OUTS[0], name)
    fig.savefig(p0, dpi=150, bbox_inches='tight')
    plt.close(fig)
    shutil.copyfile(p0, os.path.join(OUTS[1], name))
    print('wrote', name)


def load(p):
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]


def fig_map_share():
    a, b = load(EX41), load(S0)
    assert len(a) == 6000 and len(b) == 1000, (len(a), len(b))
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.plot([r['it'] for r in a], [100 * r['use_gt_frac'] for r in a], color='#5b6b7a', lw=1.2, label='EX-41 (로컬 0~5999)')
    ax.plot([6000 + r['it'] for r in b], [100 * r['use_gt_frac'] for r in b], color='#d9822b', lw=1.0, label='EX-42 0 단계 (6000~6999)')
    ax.axvline(6000, color='#999', ls=':', lw=1)
    lo = min(100 * r['use_gt_frac'] for r in b)
    ax.set_ylim(0, 105)
    ax.set_xlabel('회차 (EX-41 로컬 회차 기준 · 6000 = 누적 m12000)')
    ax.set_ylabel('정답 지도를 쓴 몫 (%)')
    ax.set_title('정답 지도 몫: EX-41 은 5501 회까지 100 %%, 0 단계는 %.1f~%.1f %%' % (lo, max(100 * r['use_gt_frac'] for r in b)))
    ax.legend(loc='lower left', frameon=False)
    ax.grid(alpha=.25)
    save(fig, 's4-1-map-share.png')


def err(model, L, mode):
    d = json.load(open(os.path.join(HARD[model].format(L=L), 'map_modes.json'), encoding='utf-8'))
    return d


def fig_hard():
    # same reading as [계보 4] 4 절 table: fast forward 1.0 error per level x mode
    table = {}
    src = open(os.path.join(LAB, 'docs', 'research', '20261108-lineage-4-ex42-stage0.md'), encoding='utf-8').read()
    for L in (5, 4, 3):
        for mode in ('정답', '복원', '끔'):
            m = re.search(r'^\| L%d \| %s \| ([0-9.]+) \| ([0-9.]+) \| ([0-9.]+) \|' % (L, mode), src, re.M)
            assert m, (L, mode)
            table[(L, mode)] = [float(x) for x in m.groups()]
    for L in (3, 4, 5):
        for k in HARD:
            assert os.path.isfile(os.path.join(HARD[k].format(L=L), 'map_modes.json')), (k, L)
    fig, axs = plt.subplots(1, 3, figsize=(11, 3.4), sharey=True)
    cols = ['#9aa5b1', '#c7a26b', '#d9822b']
    for ax, mode in zip(axs, ('정답', '복원', '끔')):
        xs = range(3)
        for i, (lab, c) in enumerate(zip(('부모 m12000', 'm12750', 'm13000'), cols)):
            ax.bar([x + (i - 1) * 0.26 for x in xs], [table[(L, mode)][i] for L in (3, 4, 5)], 0.26, color=c, label=lab)
        ax.set_xticks(list(xs)); ax.set_xticklabels(['L3', 'L4', 'L5'])
        ax.set_title('지도 %s' % mode)
        ax.grid(axis='y', alpha=.25)
        ax.set_ylim(0.08, 0.15)
    axs[0].set_ylabel('빠른 전진 1.0 m/s 오차 (m/s, 낮을수록 좋음)')
    axs[2].legend(frameon=False, fontsize=8, loc='upper left')
    fig.suptitle('어려운 지형 (--fixed-level · core 명령 · 시드 42 하나). 부모는 GPU0, m13000 은 GPU1 에서 잼', fontsize=10, y=1.06)
    save(fig, 's4-2-hard-terrain.png')


def fig_ex38():
    t = open(EX38, encoding='utf-8').read().split('\n')
    rows = []
    for l in t[:30]:
        m = re.match(r'^\| (\S+) \| ([0-9.]+) · [0-9.]+ · [0-9.]+ \| [0-9.]+ · [0-9.]+ · [0-9.]+ \| ([0-9.]+) · ', l)
        if m:
            rows.append((m.group(1), float(m.group(2)), float(m.group(3))))
    assert len(rows) >= 8, rows
    fig, ax = plt.subplots(figsize=(11, 3.6))
    xs = range(len(rows))
    ax.bar([x - .2 for x in xs], [r[1] for r in rows], .4, color='#9aa5b1', label='부모 m1500 (EX-36A · EX-38 의 출발점)')
    ax.bar([x + .2 for x in xs], [r[2] for r in rows], .4, color='#d9822b', label='EX-38 (m2500 · 2750 · 3000 평균)')
    ax.set_xticks(list(xs)); ax.set_xticklabels([r[0] for r in rows], rotation=35, ha='right', fontsize=8)
    ax.set_ylabel('64 판 중 살아남은 판 (정답 지도)')
    ax.set_ylim(0, 66)
    ax.set_title('이어 붙이기로 명령을 늘린 EX-38: 후진 칸이 크게 올랐다 (RESULT-EX36A-EX38-1029.md 표)')
    ax.legend(frameon=False, loc='upper center', bbox_to_anchor=(0.5, -0.32), ncol=2)
    ax.grid(axis='y', alpha=.25)
    save(fig, 's0-1-ex38-survival.png')


if __name__ == '__main__':
    fig_map_share()
    fig_hard()
    fig_ex38()
