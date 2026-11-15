"""Figures for the lineage series [계보 0] and [계보 4] from raw records (lead 11/08 23:2x, team lead: 글만 넣지 않을 것).

- S4-1 map share per update: EX-41 local 0~6000 and EX-42 stage zero 0~1000 (map_stats.jsonl use_gt_frac)
- S4-0 stage zero terrain level mean and use_gt_frac on one update axis, EX-41 last 1000 updates on the left (map_switch.jsonl · map_stats.jsonl), two panels, no second y axis
- S4-2 hard terrain, all four core commands x map mode x L3~L5, parent m12000 / m12750 / m13000 (median of per_env mean error in map_modes.json; vx for forward, wz for spin). 11/09 audit: the old fast-forward-only figure read as 'only map off improved'
- S4-3 RR drag under two denominators, four feet (W86 json record.feet: drag_frames / valid_foot_frames vs drag_frames / contact_moving_frames)
- S4-4 analyst gap map figure copied as is (gap-map-1108/gaps_L0_maps.png)
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
S0_DIR = 'C:/Users/AI-WS01/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914'
EX41_DIR = 'C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522'
W86 = 'C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/eval/score-watch/model_6000_1c6af6319c82/training/w86_6000_7b74699e5de6.json'
GAP_PNG = 'D:/mai-wt/foothold-lab/analyst-ex41-score-name-1102/_out/reports/gap-map-1108/gaps_L0_maps.png'
# categorical slots 1~3 of the dataviz reference palette (validated, light mode)
C1, C2, C3 = '#2a78d6', '#eb6834', '#1baf7a'


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


def fig_terrain_level():
    """[계보 4] 1 절: stage zero terrain level restarts, so it is not a same-condition extension."""
    a_sw, b_sw = load(os.path.join(EX41_DIR, 'map_switch.jsonl')), load(os.path.join(S0_DIR, 'map_switch.jsonl'))
    a_st, b_st = load(EX41), load(S0)
    assert len(b_sw) == 1000 and len(b_st) == 1000 and a_sw[-1]['it'] == 6000, (len(b_sw), len(b_st), a_sw[-1]['it'])
    a_sw = [r for r in a_sw if r['it'] > 5000]
    a_st = [r for r in a_st if r['it'] >= 5000]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 5.8), sharex=True)
    ax1.plot([r['it'] for r in a_sw], [r['on']['terrain_level_mean'] for r in a_sw], color=C1, lw=2, label='EX-41 마지막 1,000 회 (로컬 5001~6000)')
    ax1.plot([6000 + r['it'] for r in b_sw], [r['on']['terrain_level_mean'] for r in b_sw], color=C2, lw=2, label='EX-42 0 단계 (6001~7000)')
    b0, b1 = b_sw[0]['on']['terrain_level_mean'], b_sw[-1]['on']['terrain_level_mean']
    a1 = a_sw[-1]['on']['terrain_level_mean']
    ax1.annotate('0 단계 시작 %.2f' % b0, (6001, b0), xytext=(6120, 0.6), fontsize=9, arrowprops=dict(arrowstyle='-', color='#888'))
    ax1.annotate('EX-41 끝 %.2f' % a1, (6000, a1), xytext=(5600, 3.2), fontsize=9, arrowprops=dict(arrowstyle='-', color='#888'))
    ax1.annotate('0 단계 끝 %.2f' % b1, (7000, b1), xytext=(6650, 3.2), fontsize=9, arrowprops=dict(arrowstyle='-', color='#888'))
    ax1.set_ylabel('지형 레벨 평균\n(지도 켠 로봇)')
    ax1.set_ylim(0, 5.5)
    ax1.legend(loc='lower left', frameon=False, fontsize=9)
    ax2.plot([r['it'] for r in a_st], [100 * r['use_gt_frac'] for r in a_st], color=C1, lw=1.5)
    ax2.plot([6000 + r['it'] for r in b_st], [100 * r['use_gt_frac'] for r in b_st], color=C2, lw=1.2)
    ax2.set_ylabel('정답 지도 몫 (%)')
    ax2.set_ylim(0, 105)
    ax2.set_xlabel('회차 (EX-41 로컬 회차 기준 · 6000 = 누적 m12000 · 7000 = m13000)')
    for ax in (ax1, ax2):
        ax.axvline(6000, color='#999', ls=':', lw=1)
        ax.grid(alpha=.25)
    fig.suptitle('0 단계는 지형 레벨이 이어지지 않고 약 1 에서 다시 올랐다 (앞 약 400 회는 EX-41 끝보다 쉬운 지형)', fontsize=11)
    fig.tight_layout()
    save(fig, 's4-0-terrain-level.png')


def hard_err(model, L, mode, cmd):
    d = json.load(open(os.path.join(HARD[model].format(L=L), 'map_modes.json'), encoding='utf-8'))
    key = 'vx_abs_error_mean_alive_mps' if cmd.startswith('fwd') else 'wz_abs_error_mean_alive_radps'
    vals = sorted(e[key] for e in d['modes'][mode][cmd]['per_env'] if e[key] is not None)
    assert len(vals) >= 60, (model, L, mode, cmd, len(vals))
    n = len(vals)
    med = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    return med, d['run_identity']['device']


def fig_hard():
    """[계보 4] 4 절: every core command, not only fast forward (11/09 audit)."""
    cmds = [('fwd0.5', '전진 0.5\nvx 오차 (m/s)'), ('fwd1.0', '빠른 전진 1.0\nvx 오차 (m/s)'),
            ('spin+1.2', '회전 +1.2\nwz 오차 (rad/s)'), ('spin-1.2', '회전 -1.2\nwz 오차 (rad/s)')]
    modes = [('eval_gt', '정답'), ('eval_pred', '복원'), ('probe_prop_only', '끔')]
    models = [('m12000', '부모 m12000', C1), ('m12750', 'm12750', C2), ('m13000', 'm13000', C3)]
    # guard: parent fast-forward numbers must equal the [계보 4] 4 절 table (L5 정답 0.125 · 복원 0.132 · 끔 0.145)
    for mode, want in (('eval_gt', 0.125), ('eval_pred', 0.132), ('probe_prop_only', 0.145)):
        got = hard_err('m12000', 5, mode, 'fwd1.0')[0]
        assert abs(got - want) < 0.0006, (mode, got, want)
    devs = {k: hard_err(k, 5, 'eval_gt', 'fwd1.0')[1] for k, _, _ in models}
    fig, axs = plt.subplots(len(cmds), len(modes), figsize=(11, 10.5), sharex=True)
    for r, (cmd, clab) in enumerate(cmds):
        lo, hi = 1.0, 0.0
        for c, (mode, mlab) in enumerate(modes):
            ax = axs[r][c]
            for k, lab, col in models:
                ys = [hard_err(k, L, mode, cmd)[0] for L in (3, 4, 5)]
                lo, hi = min(lo, min(ys)), max(hi, max(ys))
                ax.plot([3, 4, 5], ys, color=col, lw=2, marker='o', ms=8, mec='white', mew=2,
                        label='%s (%s)' % (lab, devs[k].replace('cuda:', 'GPU')))
            ax.grid(alpha=.25)
            if r == 0:
                ax.set_title('지도 %s' % mlab)
            if c == 0:
                ax.set_ylabel(clab, fontsize=9)
            ax.set_xticks([3, 4, 5])
            ax.set_xticklabels(['L3', 'L4', 'L5'])
        for c in range(len(modes)):
            axs[r][c].set_ylim(lo - 0.006, hi + 0.006)
    axs[0][0].legend(frameon=False, fontsize=8, loc='lower left')
    fig.suptitle('어려운 지형 core 4 명령 × 지도 3 (낮을수록 좋음). 지도 끔 · 복원만 줄어든 것은 빠른 전진 1.0 하나다\n'
                 '시드 42 하나 · 64 마리 중앙값 · 부모 · m12750 은 GPU0, m13000 은 GPU1 에서 잼 (장치 교란)', fontsize=10)
    fig.tight_layout()
    save(fig, 's4-2-hard-terrain.png')


def fig_rr_drag():
    """[계보 4] 8 절: the same drag count under two denominators."""
    rec = json.load(open(W86, encoding='utf-8'))['record']
    f = rec['feet']
    names = [n.replace('_foot', '') for n in rec['feet_order']]
    assert names == ['FL', 'FR', 'RL', 'RR'], names
    all_t = [d / v for d, v in zip(f['drag_frames'], f['valid_foot_frames'])]
    moving = [d / m for d, m in zip(f['drag_frames'], f['contact_moving_frames'])]
    assert abs(all_t[3] - 0.323) < 0.0006 and abs(moving[3] - 0.653) < 0.0006, (all_t, moving)
    fig, ax = plt.subplots(figsize=(9, 4))
    xs = range(4)
    b1 = ax.bar([x - .2 for x in xs], all_t, .38, color=C1, label='끌림 ÷ 전체 유효 시간')
    b2 = ax.bar([x + .2 for x in xs], moving, .38, color=C2, label='끌림 ÷ 움직임 명령 중 접지 시간')
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.01, '%.3f' % b.get_height(), ha='center', fontsize=9)
    ax.set_xticks(list(xs))
    ax.set_xticklabels(['FL (왼앞)', 'FR (오른앞)', 'RL (왼뒤)', 'RR (오른뒤)'])
    ax.set_ylim(0, 0.78)
    ax.set_ylabel('끌린 비율')
    ax.set_title('같은 끌림 수, 분모 둘: 전체 시간으로는 RR 이 가장 낮고, 접지 중으로는 가장 높다\n'
                 'EX-41 m12000 학습 끝 한 갱신 묶음 (3,072 env × 24 step) · 운동학 지표 · 발이 걸려 막힌다는 판정 아님', fontsize=10)
    ax.legend(frameon=False, fontsize=9, loc='upper left')
    ax.grid(axis='y', alpha=.25)
    save(fig, 's4-3-rr-drag.png')


def copy_gap_maps():
    """[계보 4] 9 절: analyst figure copied byte for byte."""
    for o in OUTS:
        shutil.copyfile(GAP_PNG, os.path.join(o, 's4-4-gap-maps.png'))
    print('copied s4-4-gap-maps.png')


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
    fig_terrain_level()
    fig_hard()
    fig_rr_drag()
    copy_gap_maps()
    fig_ex38()
