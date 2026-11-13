"""Read-only TensorBoard snapshot, 50-update tables, and learning curves."""
from pathlib import Path
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import subprocess

import numpy as np
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

RUN = Path('/home/jay/data/foothold/s2_lab/ex42_main_20261113_174400/main/EX-42-B-E1-again_20261113_174400')
TAGS = {
    'lr': 'Loss/learning_rate',
    'ppo_kl': 'Loss/kl_probe/ppo_mean',
    'phi_kl': 'Loss/kl_probe/phi_mean',
    'std': 'Policy/mean_noise_std',
    'episode': 'Train/mean_episode_length',
    'reward': 'Train/mean_reward',
    'value_loss': 'Loss/value_function',
    'entropy': 'Loss/entropy',
    'slow_track': 'Episode_Reward/ex42_slow_track',
    'lin': 'Episode_Reward/track_lin_vel',
    'ang': 'Episode_Reward/track_ang_vel',
    'zero_yaw': 'Episode_Reward/ex41_zero_yaw',
    'foot_slip': 'Episode_Reward/ex41_foot_slip',
    'swing': 'Episode_Reward/ex41_swing',
    'air_time': 'Episode_Reward/ex41_feet_air_time',
    'terrain': 'Curriculum/terrain_levels',
    'stalled': 'Loss/reward_split/frac_stalled',
    'orientation_done': 'Episode_Termination/bad_orientation',
    'below_ground_done': 'Episode_Termination/foot_below_ground',
    'timeouts': 'Episode_Termination/time_out',
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def add_event(events, duplicates, step, tag, wall_time, value):
    key = (int(step), tag)
    if key in events:
        duplicates.append({'iteration': int(step), 'tag': tag})
        if events[key][0] == wall_time and events[key][1] != value:
            raise ValueError(f'Conflicting event at identical time: {key}')
    if key not in events or wall_time > events[key][0]:
        events[key] = (wall_time, value)


def window(rows, lo, hi):
    part = [r for r in rows if lo <= r['iteration'] <= hi]
    if [r['iteration'] for r in part] != list(range(lo, hi + 1)):
        raise ValueError(f'Missing/duplicated update in {lo}..{hi}')
    out = {'first': lo, 'last': hi, 'n': len(part)}
    for short, tag in TAGS.items():
        vals = [r.get(tag) for r in part]
        finite = [v for v in vals if v is not None and math.isfinite(v)]
        out[short] = {'n': len(finite), 'missing': len(vals) - len(finite)}
        if finite:
            a = np.asarray(finite)
            out[short].update(mean=float(a.mean()), median=float(np.median(a)),
                              min=float(a.min()), max=float(a.max()), last=vals[-1])
    lrs = [r.get(TAGS['lr']) for r in part]
    out['lr_floor_n'] = sum(v is not None and math.isclose(v, 1e-5, rel_tol=1e-6, abs_tol=0) for v in lrs)
    out['ppo_kl_gt_002_n'] = sum(r.get(TAGS['ppo_kl']) is not None and r[TAGS['ppo_kl']] > .02 for r in part)
    ratios = [r[TAGS['reward']] / r[TAGS['episode']] for r in part
              if r.get(TAGS['reward']) is not None and r.get(TAGS['episode'], 0) > 0]
    out['reward_per_step_mean'] = float(np.mean(ratios)) if ratios else None
    return out


def known_input_test():
    events, duplicates = {}, []
    add_event(events, duplicates, 1, 'lr', 3, 2)
    add_event(events, duplicates, 1, 'lr', 2, 8)
    assert events[(1, 'lr')][1] == 2 and len(duplicates) == 1
    try:
        add_event(events, duplicates, 1, 'lr', 3, 9)
    except ValueError:
        pass
    else:
        raise AssertionError('Ambiguous duplicate accepted')
    rows = [{'iteration': i + 1, TAGS['lr']: lr, TAGS['ppo_kl']: kl,
             TAGS['reward']: reward, TAGS['episode']: length}
            for i, (lr, kl, reward, length) in enumerate([
                (1e-5, .01, 2., 10.), (1e-4, .03, 4., 20.), (1e-5, .02, 6., 30.)])]
    w = window(rows, 1, 2)
    assert w['lr_floor_n'] == 1 and w['ppo_kl_gt_002_n'] == 1
    assert w['std']['n'] == 0 and math.isclose(w['reward_per_step_mean'], .2)
    try:
        window(rows[:1] + rows[2:], 1, 3)
    except ValueError:
        pass
    else:
        raise AssertionError('Missing update accepted')


def snapshot(src, out, evidence):
    relative = src.relative_to(RUN)
    target = out / 'snapshots' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(src.read_bytes())
    raw = target.read_bytes()
    evidence.append({'source': str(src), 'snapshot': str(target), 'bytes': len(raw), 'sha256': digest(raw)})
    return target


def draw(rows, windows, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = ['#147D92', '#B54E2F', '#4F498A', '#437346']
    panels = [(['lr'], 'Learning rate (end of update)', True),
              (['ppo_kl', 'phi_kl'], 'Diagnostic KL (not scheduler minibatch KL)', True),
              (['std'], 'Policy action standard deviation', False),
              (['episode'], 'Episode length (steps; restart buffers reset)', False),
              (['reward'], 'Mean episode reward', False),
              (['value_loss'], 'Value loss', False),
              (['lin', 'ang'], 'Weighted tracking reward / nominal episode second', False),
              (['slow_track'], 'Weighted slow_track / nominal episode second', False),
              (['zero_yaw', 'foot_slip', 'swing'], 'Weighted penalty / nominal episode second', False),
              (['terrain'], 'Training terrain level', False),
              (['stalled'], 'Training stalled fraction (all command/terrain mixture)', False),
              (['orientation_done', 'below_ground_done'], 'Logged termination fractions', False)]
    fig, axes = plt.subplots(6, 2, figsize=(15, 19), constrained_layout=True)
    x = [r['iteration'] for r in rows]
    for ax, (keys, title, log) in zip(axes.flat, panels):
        for i, key in enumerate(keys):
            y = [r.get(TAGS[key], np.nan) for r in rows]
            ax.plot(x, y, color=colors[i], alpha=.35, lw=.55)
            ax.plot([w['last'] - 24.5 for w in windows],
                    [w[key].get('mean', np.nan) for w in windows],
                    color=colors[i], lw=1.4, marker='o', markersize=3, label=key + ' (50-update mean)')
        ax.axvline(250.5, color='#555555', linestyle=':', lw=1)
        ax.axvline(500.5, color='#555555', linestyle=':', lw=1)
        ax.axvspan(500.5, 750, color='#E3C26E', alpha=.12)
        if log:
            ax.set_yscale('log')
        if keys == ['lr']:
            ax.axhline(1e-5, color='#555555', linestyle='--', lw=.8)
        ax.set_title(title, fontsize=10)
        ax.set_xlim(1, 750)
        ax.set_xlabel('Local PPO update (parent cumulative update 13250)')
        ax.grid(alpha=.2)
        ax.legend(fontsize=8, loc='best')
    fig.suptitle('E1 again: three 250-update segments | shaded: slow_track weight 0.2', fontsize=15)
    fig.savefig(out / 'curves_1_750.png', dpi=135)
    plt.close(fig)


def fmt(value, digits=4):
    return '미측정' if value is None else f'{value:.{digits}g}'


def tables(windows):
    lines = ['## 50회 단위 학습 상태', '',
             'LR·KL·std·에피소드·레벨은 창 평균. KL 최대와 LR 바닥 횟수는 별도 표기한다. 모든 값은 rank0 TensorBoard 기록이며 두 rank 합산 실측이 아니다.', '',
             '| 구간 | LR 평균 / 바닥 횟수 | PPO 진단 KL 평균 / 최대 / >0.02 횟수 | 지각 KL 평균 | action std | 에피소드 step | 보상 합 | 보상/step | 지형 레벨 |',
             '|---|---|---|---|---|---|---|---|---|']
    for w in windows:
        m = lambda k: fmt(w[k].get('mean'))
        lines.append(f"| {w['first']}~{w['last']} | {m('lr')} / {w['lr_floor_n']}/{w['n']} | {m('ppo_kl')} / {fmt(w['ppo_kl'].get('max'))} / {w['ppo_kl_gt_002_n']} | {m('phi_kl')} | {m('std')} | {m('episode')} | {m('reward')} | {fmt(w['reward_per_step_mean'])} | {m('terrain')} |")
    lines += ['', '## 50회 단위 보상 항', '',
              '각 항은 가중치와 dt가 반영된 에피소드 누계를 설정된 최대 에피소드 초로 나눈 로그의 창 평균이다. slow_track의 전체 env 평균은 느린 명령의 실제 추종 비율 R이 아니다. 가중 0 로그가 있어도 미측정 비용을 복원할 수 없다.', '',
              '| 구간 | slow_track | track_lin_vel | track_ang_vel | zero_yaw | foot_slip | swing | air_time |',
              '|---|---|---|---|---|---|---|---|']
    for w in windows:
        lines.append('| ' + ' | '.join([f"{w['first']}~{w['last']}"] + [fmt(w[k].get('mean')) for k in ['slow_track','lin','ang','zero_yaw','foot_slip','swing','air_time']]) + ' |')
    return '\n'.join(lines) + '\n'


def main():
    p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True); args = p.parse_args()
    out = args.out.resolve()
    if out == RUN or RUN in out.parents:
        raise ValueError('Output must be outside the live run')
    out.mkdir(parents=True, exist_ok=True)
    known_input_test()
    evidence, files, events, duplicates = [], [], {}, []
    for src in sorted(RUN.glob('events.out.tfevents*')):
        target = snapshot(src, out, evidence)
        acc = EventAccumulator(str(target), size_guidance={'scalars': 0}); acc.Reload()
        tags = [t for t in acc.Tags()['scalars'] if not t.endswith('/time')]
        lr = acc.Scalars(TAGS['lr'])
        files.append({'name': src.name, 'first': min(e.step for e in lr), 'last': max(e.step for e in lr), 'n': len(lr)})
        for tag in tags:
            for ev in acc.Scalars(tag):
                if 1 <= ev.step <= 750:
                    add_event(events, duplicates, ev.step, tag, ev.wall_time, ev.value)
    all_tags = sorted({t for _, t in events})
    rows = [{'iteration': i, **{t: events.get((i,t),(None,None))[1] for t in all_tags}} for i in range(1, 751)]
    for i in range(1, 751):
        if (i, TAGS['lr']) not in events:
            raise ValueError(f'Missing update {i}')
    with (out/'scalars.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['iteration'] + all_tags); w.writeheader(); w.writerows(rows)
    windows = [window(rows, i, i + 49) for i in range(1, 751, 50)]
    segments = [window(rows, i, i + 249) for i in (1,251,501)]
    receipts = {}
    for pattern in ('params/agent.yaml', 'params/env.yaml', 'manifest.json', 'startup_receipt.json', 'segment_commands_b*.json', 'segment_rewards_b*.json', 'exposure_receipt_start_*rank*.json'):
        for src in sorted(RUN.glob(pattern)):
            path = snapshot(src, out, evidence)
            if 'segment_' in src.name:
                receipts[src.name] = json.loads(path.read_text())
    for b in (1, 2):
        a, z = [receipts[f'segment_rewards_b{b}_rank{r}.json']['live'] for r in (0,1)]
        if a != z:
            raise ValueError(f'Rank reward mismatch at b{b}')
    a, z = [receipts[f'segment_commands_b{b}.json'] for b in (1,2)]
    if a['commands'] != z['commands'] or a['low_forward_fraction']['value'] != z['low_forward_fraction']['value']:
        raise ValueError('Commands changed between segment 2 and 3')
    rewards = [receipts[f'segment_rewards_b{b}_rank0.json']['live'] for b in (1,2)]
    delta = {k: [rewards[0].get(k), rewards[1].get(k)] for k in set(rewards[0]) | set(rewards[1]) if rewards[0].get(k) != rewards[1].get(k)}
    doc = {'created_at': dt.datetime.now().astimezone().isoformat(), 'known_input_test': 'PASS', 'run':str(RUN),
           'source_git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
           'generator_sha256':digest(Path(__file__).read_bytes()), 'files':files, 'duplicates':duplicates,
           'reward_delta_b1_b2':delta, 'commands_b1_b2_equal':True, 'rank_rewards_equal':True,
           'windows50':windows, 'segments250':segments, 'evidence':evidence}
    (out/'summary.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2)+'\n')
    flattened = [{'first':w['first'], 'last':w['last'], 'n':w['n'],
                  **{f'{key}_{stat}':val for key in TAGS for stat,val in w[key].items()},
                  **{k:w[k] for k in ('lr_floor_n','ppo_kl_gt_002_n','reward_per_step_mean')}} for w in windows]
    with (out/'windows50.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in flattened for k in r))); w.writeheader(); w.writerows(flattened)
    (out/'TABLES.md').write_text(tables(windows), encoding='utf-8')
    draw(rows, windows, out)
    print(json.dumps({'files':files,'duplicates':len(duplicates),'reward_delta':delta,'segments':segments}, ensure_ascii=False))


if __name__ == '__main__':
    main()
