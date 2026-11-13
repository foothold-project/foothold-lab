"""CPU arithmetic and raw-contact audit for the R5/R6 document. Not a reward plugin.

Only reads measurement files. Writes small derived evidence under --out.
Contact calibration uses Fz > 1 N, NOT W86's force-vector norm > 1 N.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np

FEET = ('FL_foot', 'FR_foot', 'RL_foot', 'RR_foot')


def slow_reward(c, vx, vy=0., *, cy=0., cw=0., heading=False,
                flag=False, weight=.2, k=.5, c0=.1):
    """Additional term, 15:41 decision: all planar directions, [0.1, 0.3)."""
    values = (c, vx, vy, cy, cw, weight, k, c0)
    if not all(math.isfinite(x) for x in values) or k <= 0 or c0 <= 0 or weight < 0:
        raise ValueError('invalid analysis input')
    speed = math.hypot(c, cy)
    active = (.1 <= speed < .3 and abs(cw) < 1e-6 and not heading and not flag)
    if not active:
        return 0.
    return weight * math.exp(-((vx-c)**2 + (vy-cy)**2)/(k*max(speed, c0))**2)


def three_terms(c, vx, yaw, slow_weight):
    return (2*math.exp(-(vx-c)**2/.35**2)
            + math.exp(-yaw**2/.5**2)-abs(yaw)
            + slow_reward(c, vx, weight=slow_weight))


def complete_events(contact, alive, dt):
    """Independent edge-pair extraction, all intervals wholly inside the window.

    Return flights [first_air, touchdown) and touchdown-to-touchdown cycles.
    Initial/final airborne intervals and intervals crossing a dead row are excluded.
    """
    c, a = np.asarray(contact, bool), np.asarray(alive, bool)
    if c.shape != a.shape or c.ndim != 1 or dt <= 0:
        raise ValueError('invalid time series')
    up = np.flatnonzero(~c[1:] & c[:-1]) + 1
    down = np.flatnonzero(c[1:] & ~c[:-1]) + 1
    flights = []
    for i in up:
        jpos = np.searchsorted(down, i)
        if jpos < len(down):
            j = down[jpos]
            if a[i-1:j+1].all():
                flights.append((int(i), int(j), float((j-i)*dt)))
    cycles = [(int(i), int(j), float((j-i)*dt))
              for i, j in zip(down[:-1], down[1:]) if a[i-1:j+1].all()]
    return flights, cycles


def known_inputs():
    assert math.isclose(slow_reward(.1, 0, weight=1), math.exp(-4))
    assert math.isclose(slow_reward(.2, 0, weight=1), math.exp(-4))
    assert slow_reward(.1, .1, weight=1) == 1
    assert slow_reward(.3, .3, weight=1) == 0
    assert math.isclose(slow_reward(.1, .05, weight=1), math.exp(-1))
    assert slow_reward(0, 0) == 0
    for c in (.5, 1., 1.5, 2.):
        for vx in (0., .1, c):
            assert slow_reward(c, vx, weight=1) == 0
    for kwargs in ({'cw': .1}, {'heading': True}, {'flag': True}):
        assert slow_reward(.2, .2, **kwargs) == 0
    assert slow_reward(0, 0, .1, cy=.1, weight=1) == 1
    assert slow_reward(-.2, -.2, weight=1) == 1
    assert slow_reward(0, 0, -.2, cy=-.2, weight=1) == 1
    assert slow_reward(.1, .1, .1) < slow_reward(.1, .1)
    assert slow_reward(.1, .2) == slow_reward(.1, 0)
    c = [1, 1, 0, 0, 1, 1, 0, 0, 1, 1]
    f, p = complete_events(c, [1]*10, .02)
    assert np.allclose([x[2] for x in f], [.04, .04])
    assert np.allclose([x[2] for x in p], [.08])
    assert complete_events([0, 0, 1, 1, 0], [1]*5, .02) == ([], [])
    dead = [1]*10
    dead[6] = 0
    f, p = complete_events(c, dead, .02)
    assert len(f) == 1 and p == []
    return 'known inputs: reward endpoints/exclusions, lateral error, censoring, reset gaps PASS'


def pct(values):
    if not values:
        return {'n': 0, 'p10': None, 'median': None, 'p90': None}
    a = np.asarray(values, float)
    return {'n': len(a), 'p10': float(np.quantile(a, .1)),
            'median': float(np.median(a)), 'p90': float(np.quantile(a, .9))}


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def compare_planner(path, out):
    """156 known states against the separately owned CPU reward implementation."""
    import torch
    spec = importlib.util.spec_from_file_location('planner_reward', path)
    actual = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(actual)
    count = 0
    for cx,cy in [(0,0),(.1,0),(.2,0),(.3,0),(.5,0),(1,0),(-.1,0),(-.2,0),
                  (0,.1),(0,-.1),(0,.2),(0,-.2),(.1,.1)]:
        for factor in (0,.5,1,2):
            for excluded,wz in ((False,0),(True,0),(False,.1)):
                c = torch.tensor([[cx,cy]],dtype=torch.float64,device='cpu')
                value = actual.slow_track_value(c*factor,c,torch.tensor([wz],dtype=torch.float64),
                    speed_min=.1,speed_max=.3,sigma=.5,excluded=torch.tensor([excluded]))
                expected = slow_reward(cx,cx*factor,cy*factor,cy=cy,cw=wz,heading=excluded,weight=1)
                assert math.isclose(float(value),expected,rel_tol=1e-12,abs_tol=1e-12)
                count += 1
    record = dict(cases=count,status='PASS',device='CPU',planner_source=str(path),
                  planner_source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  reference_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'planner_formula_check.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')


def run(raw, out, extra_raw=None, planner_source=None):
    check = known_inputs()  # Run before reading unknown data.
    out.mkdir(parents=True, exist_ok=True)
    math_rows = []
    for c in (.1, .2, .3, .5, 1., 1.5):
        for w in (.1, .2, .3, .5, 1.):
            stand = slow_reward(c, 0, weight=w)
            walk = slow_reward(c, c, weight=w)
            math_rows.append(dict(command_mps=c, weight=w, standing=stand,
                                  half_speed=slow_reward(c, c/2, weight=w),
                                  correct_speed=walk, gain=walk-stand,
                                  gain_after_dt_002=(walk-stand)*.02,
                                  three_term_gain_yaw0=three_terms(c,c,0,w)-three_terms(c,0,0,w),
                                  three_term_gain_yaw01=three_terms(c,c,.1,w)-three_terms(c,0,0,w)))
    write_csv(out/'reward_math.csv', math_rows)
    directions = []
    for name, ux, uy in (('forward',1,0), ('backward',-1,0), ('left',0,1), ('right',0,-1)):
        for c in (.1,.2,.5,1.):
            stand = slow_reward(c*ux, 0, 0, cy=c*uy)
            walk = slow_reward(c*ux, c*ux, c*uy, cy=c*uy)
            directions.append(dict(direction=name, command_speed_mps=c, weight=.2,
                                   stationary=stand, tracking=walk, gain=walk-stand))
    write_csv(out/'direction_gain.csv', directions)
    air_math = [dict(air_time_s=t,old_unweighted=t-.5,new_unweighted=t-.04,
                    new_weighted_dt=(t-.04)*.1*.02) for t in (.02,.04,.06,.12,.24)]
    write_csv(out/'air_time_math.csv',air_math)
    flights_rows, summary, evidence, identities, command_rows = [], [], [], [], []
    jobs, originals = [], {}
    for root in (raw, extra_raw):
        if root is None:
            continue
        receipt_path = root/'map_modes.json'
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        assert receipt['checkpoint_sha256']=='680c820b73646d9c11f62f184fd35e6cc096ffd04681951d542b2b4b472d779e'
        evidence.append(dict(path=str(receipt_path),sha256=hashlib.sha256(receipt_path.read_bytes()).hexdigest()))
        for name in receipt['gait_contact_sweep']['commands']:
            if name in originals:
                raise ValueError('duplicate command across receipts')
            originals[name] = receipt['gait_contact_sweep'][name]
            jobs.append((root,name))
    for root, name in jobs:
        raw_path = root/f'gait_raw_{name}.csv'
        npz_path = root/f'env_arrays_eval_gt_{name}.npz'
        for path in (raw_path, npz_path):
            evidence.append(dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        with np.load(npz_path, allow_pickle=False) as z:
            alive, vx, dt = z['alive'], z['vx'], float(z['dt'])
            identities.append(dict(command=name, run_identity=str(z['run_identity']),
                                   kind=sorted(set(z['kind'].tolist())), levels=sorted(set(z['terrain_level'].tolist())),
                                   shape=list(alive.shape), dt=dt, alive_end=int(z['alive_end'].sum())))
        forces = np.full((*alive.shape, 4), np.nan)
        vy = np.zeros_like(vx, dtype=float)
        seen = np.zeros(alive.shape, bool)
        with raw_path.open(newline='', encoding='utf-8') as stream:
            for row in csv.DictReader(stream):
                t, e = int(row['step']), int(row['env'])
                if seen[t,e] or bool(int(row['alive'])) != bool(alive[t,e]):
                    raise ValueError(f'duplicate sample or alive mismatch {raw_path}:{t}:{e}')
                if abs(float(row['body_vx_mps'])-float(vx[t,e])) > 1e-6:
                    raise ValueError('csv/npz velocity mismatch')
                if abs(float(row['t_s'])-t*dt) > 1e-6:
                    raise ValueError('csv/npz time mismatch')
                seen[t,e] = True
                if 'body_vy_mps' in row:
                    vy[t,e] = float(row['body_vy_mps'])
                for f, foot in enumerate(FEET):
                    force = float(row[f'{foot}_fz_n'])
                    if bool(int(row[f'{foot}_contact'])) != (force > 1.):
                        raise ValueError('Fz/contact mismatch')
                    forces[t,e,f] = force
        if not seen.all() or not np.isfinite(forces).all():
            raise ValueError('incomplete or nonfinite force data')
        c = float(name[3:]) if name.startswith('fwd') else (float(name[4:]) if name.startswith('back') else float(name[4:]))
        projection = vx.astype(float) if name.startswith('fwd') else (-vx.astype(float) if name.startswith('back') else np.sign(c)*vy)
        for start_s in (0.,1.):
            i = round(start_s/dt)
            means = [projection[i:,e][alive[i:,e]].mean() for e in range(alive.shape[1]) if alive[i:,e].any()]
            command_rows.append(dict(command=name,start_s=start_s,alive_end=int(alive[-1].sum()),
                                    projection_speed_median_mps=float(np.median(means)),
                                    body_speed_ratio=float(np.median(means)/abs(c)),
                                    all_four_grounded_fraction=float(((forces[i:]>1).all(-1)&alive[i:]).sum()/alive[i:].sum())))
        for start_s in (0., 1.):
            start = round(start_s/dt)
            a, v, contact = alive[start:], vx[start:], forces[start:] > 1.
            for foot_i, foot in enumerate(FEET):
                air, periods, envs_with_cycle, envs_with_flight = [], [], 0, 0
                for e in range(a.shape[1]):
                    f, p = complete_events(contact[:,e,foot_i], a[:,e], dt)
                    envs_with_cycle += bool(p)
                    envs_with_flight += bool(f)
                    air.extend(x[2] for x in f)
                    periods.extend(x[2] for x in p)
                    for left, right, duration in f:
                        flights_rows.append(dict(command=name, start_s=start_s, foot=foot,
                                                env=e, first_air_step=left+start,
                                                touchdown_step=right+start, air_time_s=duration))
                air_stats, cycle_stats = pct(air), pct(periods)
                summary.append(dict(command=name, start_s=start_s, foot=foot,
                                    alive_end=int(alive[-1].sum()),
                                    median_vx_mps=float(np.median([v[:,e][a[:,e]].astype(float).mean() for e in range(a.shape[1]) if a[:,e].any()])),
                                    flights=air_stats['n'], air_p10_s=air_stats['p10'],
                                    air_median_s=air_stats['median'], air_p90_s=air_stats['p90'],
                                    cycles=cycle_stats['n'], cycle_median_s=cycle_stats['median'],
                                    envs_with_cycle=envs_with_cycle,
                                    envs_with_flight=envs_with_flight,
                                    single_frame_flights=int(sum(x <= dt+1e-9 for x in air)),
                                    negative_at_05=int(sum(x < .5-1e-9 for x in air)),
                                    mean_signed_at_05=float(np.mean(air)-.5) if air else None,
                                    mean_signed_at_010=float(np.mean(air)-.1) if air else None))
    # Raw files must not change while being audited.
    for row in evidence:
        if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('measurement file changed during audit')
    write_csv(out/'gait_by_foot.csv', summary)
    write_csv(out/'complete_flights.csv', flights_rows)
    threshold_rows = []
    for _,cmd in jobs:
        for threshold in (.04,.06,.08,.1,.2,.5):
            for foot in (*FEET,'ALL'):
                samples = [r['air_time_s'] for r in flights_rows if r['start_s']==1.
                           and r['command']==cmd and (foot=='ALL' or r['foot']==foot)]
                threshold_rows.append(dict(command=cmd, foot=foot, threshold_s=threshold,
                    n=len(samples), negative_fraction=sum(v<threshold-1e-9 for v in samples)/len(samples) if samples else None,
                    mean_signed_value_s=float(np.mean(samples)-threshold) if samples else None))
    write_csv(out/'threshold_sweep.csv', threshold_rows)
    for row in summary:
        if row['start_s']!=0.:
            continue
        original = originals[row['command']]
        assert row['flights']==original['air_time_s_by_foot'][row['foot']]['n']
        assert row['cycles']==original['complete_cycle_count_by_foot'][row['foot']]
        assert np.isclose(row['median_vx_mps'],original['body_forward_speed_median_mps'])
    write_csv(out/'command_gait_summary.csv',command_rows)
    (out/'identities.json').write_text(json.dumps(identities, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (out/'evidence_sha256.json').write_text(json.dumps(evidence, indent=2)+'\n', encoding='utf-8')
    (out/'validation.json').write_text(json.dumps(dict(test=check, math_rows=len(math_rows),
        gait_rows=len(summary), flights_rows=len(flights_rows), files_verified=len(evidence)), indent=2)+'\n', encoding='utf-8')
    if planner_source:
        compare_planner(planner_source,out)
    print(json.dumps(dict(known_inputs=check, rows=len(summary), out=str(out))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--extra-raw', type=Path)
    parser.add_argument('--planner-source', type=Path)
    args = parser.parse_args()
    run(args.raw, args.out, args.extra_raw, args.planner_source)
