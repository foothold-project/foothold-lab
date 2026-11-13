"""CPU-only m250 evidence snapshot. No mutation of the run or evaluation policy."""
from pathlib import Path
import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import math
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
RUN = Path('/home/jay/data/foothold/s2_lab/ex42_main_20261114_022748/main/EX-42-B-E1-v27_20261114_022748')
CODE = Path('/home/jay/mai/wt/foothold-lab/ex42-launch-e1-v27')
MODES = ('eval_gt', 'eval_pred', 'probe_prop_only')
LIVE_MODES = ('gt', 'pred', 'off')
SCORE = RUN / 'eval/scores/m250'
SOURCES = {}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    path = Path(path)
    raw = path.read_bytes()
    SOURCES[str(path)] = sha(raw)
    return raw


def doc(path):
    return json.loads(read(path))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def csvfile(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def trajectory(vx, alive, dt_s, command):
    """Descriptive speed classes use the existing 0.05 m/s stall threshold, not a new gate."""
    if vx.shape != (300, 64) or alive.shape != vx.shape or not np.isfinite(vx).all():
        raise ValueError('Expected finite 300 x 64 speed and alive evidence')
    if not math.isclose(dt_s, .02, abs_tol=1e-9) or np.any(alive[1:] > alive[:-1]):
        raise ValueError('Invalid time step or resurrected env')
    body = np.where(alive, vx, 0.)
    r = body.mean(0) / command  # full scheduled duration, all starting envs
    seconds = np.stack([x.mean(0) for x in np.array_split(body, 6)])
    early, late = body[:100].mean(0), body[200:].mean(0)
    eligible = alive.all(0)
    onset = []
    for e in range(64):
        # First continuous 0.5 s above threshold; no interpolation or peak-only launch.
        mask = (vx[:, e] >= .05) & alive[:, e]
        starts = np.flatnonzero(np.convolve(mask.astype(int), np.ones(25, int), mode='valid') == 25)
        onset.append(None if not len(starts) else float(starts[0] * dt_s))
    return dict(R=float(np.median(r)), R_mean=float(r.mean()),
                R_without_first_second=float(np.median(body[50:].mean(0) / command)),
                seconds_median=np.median(seconds, axis=1).tolist(),
                seconds_mean=seconds.mean(axis=1).tolist(),
                seconds_below_005=(seconds < .05).sum(axis=1).astype(int).tolist(),
                stalled_2to4s=int((body[100:200].mean(0) < .05).sum()),
                late_below_005=int((body[250:].mean(0) < .05).sum()),
                early_and_late_below=int((eligible & (early < .05) & (late < .05)).sum()),
                early_above_late_below=int((eligible & (early >= .05) & (late < .05)).sum()),
                early_below_late_above=int((eligible & (early < .05) & (late >= .05)).sum()),
                early_and_late_above=int((eligible & (early >= .05) & (late >= .05)).sum()),
                died=int((~eligible).sum()), sustained_onsets_s=onset,
                no_sustained_motion=int(sum(x is None for x in onset)),
                sustained_onset_after_2s=int(sum(x is not None and x >= 2 for x in onset)),
                survival=int(alive[-1].sum()), per_env_R=r.tolist())


def known_input_test():
    a = np.ones((300, 64), dtype=bool)
    late = np.zeros((300, 64)); late[150:] = .1
    result = trajectory(late, a, .02, .1)
    assert result['early_below_late_above'] == 64 and result['sustained_onsets_s'] == [3.] * 64
    assert math.isclose(result['R'], .5)
    early = np.zeros_like(late); early[:100] = .1
    result = trajectory(early, a, .02, .1)
    assert result['early_above_late_below'] == 64 and result['late_below_005'] == 64
    assert trajectory(np.zeros_like(late), a, .02, .1)['no_sustained_motion'] == 64
    dead = a.copy(); dead[150:] = False
    assert math.isclose(trajectory(np.full_like(late, .1), dead, .02, .1)['R'], .5)
    dead[200:] = True
    try:
        trajectory(late, dead, .02, .1)
    except ValueError:
        pass
    else:
        raise AssertionError('Post-reset resurrection accepted')


def forward_cells(cp):
    rows, series, inventories = [], {}, []
    for seed in (42, 7, 13):
        sub = SCORE if seed == 42 else SCORE / f'e1_v2_repeat_seed{seed}'
        for level in (0, 5):
            folder = sub / f'e1_v2/L{level}'
            d = doc(folder / 'map_modes.json')
            reference = doc(SCORE / f'e1_v2/L{level}/map_modes.json')
            assert d['checkpoint_sha256'] == cp and d['eval_seed'] == seed
            assert d['envs'] == 64 and d['steps'] == 300
            for field in ('commands', 'dr_off', 'fixed_terrain'):
                assert d[field] == reference[field], field
            assert d['ex42_mesh']['mesh_sha256'] == reference['ex42_mesh']['mesh_sha256']
            for mode in MODES:
                for speed in (.1, .2):
                    case = f'fwd{speed}'; path = folder / d['env_arrays'][mode + '/' + case]
                    read(path)
                    with np.load(path, allow_pickle=False) as z:
                        identity = json.loads(str(z['run_identity'].item()))
                        assert identity['eval_seed'] == seed and identity['checkpoint_sha256'] == cp
                        assert str(z['assignment_sha256'].item()) == d['fixed_terrain']['assignment_sha256']
                        v, alive = z['vx'].astype(float), z['alive'].astype(bool)
                        measured = trajectory(v, alive, float(z['dt']), speed)
                        expected = d['modes'][mode][case]
                        assert measured['survival'] == expected['alive_envs_at_end']
                        assert abs(measured['stalled_2to4s'] / 64 - expected['stalled_fraction_2to4s']) < 1e-12
                        assert abs(measured['R'] * speed * 6 - expected['body_vx_integral_median_m']) < 1e-6
                        row = dict(seed=seed, level=level, mode=mode, command=speed, **measured)
                        row['path'] = str(path); rows.append(row)
                        inventories.append(dict(path=str(path), keys=list(z.files),
                                                contact_present=any('contact' in k or 'force' in k for k in z.files)))
                        if seed == 42:
                            series[(level, mode, speed)] = v
    return rows, series, inventories


def training(scratch):
    path = RUN / 'ex42_live_metrics.jsonl'
    target = scratch / 'live-through-250.jsonl'
    if not target.exists():
        # Preserve exact complete source lines through checkpoint boundary, not later updates.
        selected = [line for line in path.read_bytes().splitlines(keepends=True)
                    if line.endswith(b'\n') and json.loads(line)['iteration'] <= 250]
        target.write_bytes(b''.join(selected))
    rows = [json.loads(line) for line in read(target).splitlines()]
    assert [r['iteration'] for r in rows] == list(range(1, 251))
    assert all(r['world_size'] == 2 and r['plan_sha256'] == doc(RUN/'startup_receipt.json')['plan_sha256'] for r in rows)
    out = []
    for first, last in ((1, 50), (51, 100), (101, 150), (151, 200), (201, 250), (231, 250)):
        part = [r for r in rows if first <= r['iteration'] <= last]
        for mode in LIVE_MODES:
            for band in ('0.1-0.15', '0.15-0.2', '0.2-0.3'):
                vals = [r['slow_forward_speed_bands'][mode][band] for r in part]
                n = sum(x['samples'] for x in vals)
                assert n > 0
                out.append(dict(first=first, last=last, mode=mode, band=band, samples=n,
                                ratio=sum(x['samples'] * x['tracking_ratio'] for x in vals if x['samples'])/n,
                                stall_fraction=sum(x['samples'] * x['stall_fraction'] for x in vals if x['samples'])/n))
    heading = {}
    for mode in LIVE_MODES:
        part = [r['slow_track_slots'][mode]['forward'] for r in rows[-20:]]
        active = sum(x['active_env_steps'] for x in part)
        n_heading = sum(x['heading_active_env_steps'] for x in part)
        heading[mode] = dict(active=active, heading=n_heading, fraction=n_heading/active)
    return rows, out, heading, dict(original=str(path), snapshot=str(target),
                                   sha256=sha(target.read_bytes()), scope='exact complete lines 1..250')


def curves(scratch):
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    spec = importlib.util.spec_from_file_location('old_curves', Path(__file__).parent.parent/'e1-m750/curves.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    mod.known_input_test()
    events, dup, files = {}, [], []
    for path in sorted(RUN.glob('events.out.tfevents*')):
        target = scratch / path.name
        if not target.exists():
            target.write_bytes(path.read_bytes())
        read(target)
        acc = EventAccumulator(str(target), size_guidance={'scalars': 0}); acc.Reload()
        tags = acc.Tags()['scalars']
        used = []
        for tag in mod.TAGS.values():
            if tag not in tags:
                continue
            for ev in acc.Scalars(tag):
                if 1 <= ev.step <= 250:
                    mod.add_event(events, dup, ev.step, tag, ev.wall_time, ev.value)
                    used.append(ev.step)
        files.append(dict(original=str(path), snapshot=str(target), first=min(used) if used else None,
                          last=max(used) if used else None, sha256=sha(target.read_bytes())))
    rows = [{'iteration': i, **{t: events.get((i,t),(None,None))[1] for t in mod.TAGS.values()}}
            for i in range(1, 251)]
    assert all(r[mod.TAGS['lr']] is not None for r in rows)
    windows = [mod.window(rows, start, start+49) for start in range(1, 251, 50)]
    return rows, windows, files, dup, mod.TAGS


def plot(series, training_rows, scalar_rows, tags, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = ('#147D92', '#B54E2F', '#4F498A')
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)
    for i, level in enumerate((0, 5)):
        for j, speed in enumerate((.1, .2)):
            ax = axes[i, j]
            for mode, color in zip(MODES, colors):
                v = series[(level, mode, speed)].reshape(30, 10, 64).mean(1)
                ax.plot(np.arange(30)*.2+.1, np.median(v, 1), color=color, label=mode)
                ax.fill_between(np.arange(30)*.2+.1, np.quantile(v,.1,axis=1),
                                np.quantile(v,.9,axis=1), color=color, alpha=.08)
            ax.axhline(speed, color='#333333', linestyle='--', label='command')
            ax.axhline(.05, color='#555555', linestyle=':', label='stall reference')
            ax.set(title=f'L{level} forward {speed} m/s: median, env p10-p90', xlabel='Seconds', ylabel='Body vx (m/s)')
            ax.grid(alpha=.15)
    axes[0,0].legend(fontsize=8)
    fig.savefig(out/'velocity_6s.png', dpi=145); plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(14, 7), constrained_layout=True)
    panels = [('lr','End-of-update learning rate'),('ppo_kl','Diagnostic PPO KL'),('std','Action std'),
              ('episode','Episode length (steps)'),('slow_track','Weighted slow_track'),('lin','Weighted linear tracking')]
    for ax, (key, title) in zip(axes.flat, panels):
        ax.plot([r['iteration'] for r in scalar_rows], [r[tags[key]] for r in scalar_rows], color=colors[0], lw=.9)
        ax.set(title=title, xlabel='Local update')
        if key in ('lr','ppo_kl'):
            ax.set_yscale('log')
        ax.grid(alpha=.15)
    fig.savefig(out/'training_1_250.png', dpi=145); plt.close(fig)


def main():
    p = argparse.ArgumentParser(); p.add_argument('--scratch', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True); args = p.parse_args()
    for path in (args.scratch, args.out):
        if path.resolve().is_relative_to(RUN.resolve()) or path.resolve().is_relative_to(CODE.resolve()):
            raise ValueError('Outputs must be outside run and frozen source')
        path.mkdir(parents=True, exist_ok=True)
    known_input_test()
    score = doc(SCORE/'ex42_score.json'); startup = doc(RUN/'startup_receipt.json')
    manifest = doc(RUN/'manifest.json'); cp = score['checkpoint_sha256']
    assert manifest['checkpoints']['model_250.pt'] == cp
    assert startup['plan_sha256'] == score['execution_plan_sha256']
    rows, series, inventories = forward_cells(cp)
    live, live_windows, heading, live_source = training(args.scratch)
    scalar_rows, windows, event_sources, dup, tags = curves(args.scratch)
    # #812 permits an explicit audited producing code root; no source checks are relaxed.
    sys.path.insert(0, str(ROOT/'inbox/jay/20261113-analysis/e1-boundary-rules'))
    import approved_source, boundary_demote
    audit = approved_source.read_audit(SCORE/'ex42_score.json', c1_code_root=CODE)
    assert not audit['errors'], audit['errors']
    demote = boundary_demote.read_review(SCORE/'ex42_score.json', RUN, CODE, audits={250: audit})
    assert not demote['errors'] and demote['state'] == 'BASELINE_ONLY'
    boundary_demote.write_review(demote, args.out/'boundary')
    dump(args.out/'audit.json', audit)
    dump(args.out/'trajectories.json', rows)
    dump(args.out/'contact_inventory.json', inventories)
    csvfile(args.out/'live_windows.csv', live_windows)
    csvfile(args.out/'scalars.csv', scalar_rows)
    dump(args.out/'curves_windows.json', windows)
    csvfile(args.out/'trajectory_summary.csv', [{k:v for k,v in row.items() if not isinstance(v,list)} for row in rows])
    for name in ('foothold_s2/ex42_live_metrics.py', 'foothold_s2/scripts/ex42_training_entry.py',
                 'foothold_s2/runners/start_runner.py', 'foothold_s2/eval/adapters.py',
                 'foothold_s2/eval/eval_map_modes.py', 'foothold_s2/ex42_e1_v2.py',
                 'foothold_s2/curriculum/ex42-prep.yaml'):
        read(CODE/name)
    read(RUN/'params/env.yaml'); read(RUN/'params/agent.yaml')
    dump(args.out/'EVIDENCE.json', dict(format='analyst-v27-m250/1',
         created_at=dt.datetime.now().astimezone().isoformat(), sources=SOURCES,
         checkpoint_sha256=cp, plan_sha256=startup['plan_sha256'],
         live_source=live_source, event_sources=event_sources, duplicate_scalar_keys=dup,
         live_m250=live[-1], slow_heading_last20=heading, known_input='PASS: late launch, decay, stop, death, resurrection',
         boundary_state=demote['state'], independent_forward_checks=len(rows),
         contact_arrays_present=sum(x['contact_present'] for x in inventories)))
    plot(series, live_windows, scalar_rows, tags, args.out)
    print(json.dumps(dict(boundary=demote['state'], raw_checks=len(rows), contact=sum(x['contact_present'] for x in inventories))))


if __name__ == '__main__':
    main()
