"""Read-only CPU census of closed renderer attempts, fixed at the request cutoff.

No simulator imports, no video retry, no queue or source writes. Output is beside
this script. Fatal logs retain only the final stuck frame, not first darkness.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = Path('D:/mai-tmp/lead/canon216_m12000')
STAGE = Path('D:/mai-tmp/runner/ex41_stage_video')
TZ = timezone(timedelta(hours=9))
CUTOFF = datetime(2026, 11, 7, 11, 30, tzinfo=TZ).timestamp()
SOURCES = {}


def read(path):
    path = Path(path)
    b = path.read_bytes()
    SOURCES[str(path)] = {'sha256': hashlib.sha256(b).hexdigest(), 'bytes': len(b)}
    return b.decode('utf-8-sig', errors='replace')


def doc(path):
    return json.loads(read(path))


def fatal(log):
    rows = []
    for n, line in enumerate(log.splitlines(), 1):
        marker = 'render_still_dark {'
        if marker in line:
            tail = line.split('render_still_dark ', 1)[1]
            try:
                d, _ = json.JSONDecoder().raw_decode(tail)
            except json.JSONDecodeError:
                continue  # traceback source text is not a JSON event
            rows.append((n, d))
    return rows


def yaw(q):
    w, x, y, z = q
    return math.degrees(math.atan2(2 * (w*z+x*y), 1-2*(y*y+z*z)))


def position(pos, quat, level, col):
    # TerrainGenerator centers 10 x 23 tiles of 8 x 8 m around world XY zero.
    x0, y0 = level*8-40, col*8-92
    u, v = float(pos[0])-x0, float(pos[1])-y0
    return dict(x=float(pos[0]), y=float(pos[1]), z=float(pos[2]),
                u=u, v=v, edge=min(u, 8-u, v, 8-v), yaw=yaw(quat),
                tile_x0=x0, tile_y0=y0)


def selftest():
    assert yaw([1, 0, 0, 0]) == 0
    assert abs(yaw([2**-.5, 0, 0, 2**-.5])-90) < 1e-12
    p = position([-36, -88, .4], [1, 0, 0, 0], 0, 0)
    assert p['u'] == p['v'] == p['edge'] == 4
    assert position([-41, -88, .4], [1, 0, 0, 0], 0, 0)['edge'] == -1
    assert len(fatal('raise RuntimeError("render_still_dark " + json.dumps(\nRuntimeError: render_still_dark {"retry_count": 30}')) == 1
    # Validated video may record locomotion failure. It is not render failure.
    assert outcome({'state': 'validated', 'result': 'fail'}, [])[0] == 'validated'
    assert outcome({'state': 'failed'}, [(1, {})])[0] == 'dark_failure'


def outcome(closed, fs):
    if closed.get('state') == 'validated':
        assert not fs
        return 'validated', closed.get('result')
    return ('dark_failure' if fs else 'other_failure'), None


def csvwrite(name, rows):
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                    for k, v in r.items()} for r in rows)


def jsonwrite(name, obj):
    (OUT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def describe(xs):
    a = np.asarray(xs, dtype=float)
    return dict(n=len(a), min=float(a.min()), median=float(np.median(a)), max=float(a.max())) if len(a) else {'n': 0}


def run():
    selftest()
    for src in ('D:/mai-wt/foothold-lab/canon216-m12000-gpu0/foothold_s2/eval/video25/record_c_layer.py',
                'C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains/terrain_generator.py'):
        read(src)
    plan = doc(ROOT/'plan.json')
    jobs = {f"{j['kind']}_L{j['level']}_{j['map_mode']}": j for j in plan['jobs']}
    paths = sorted((ROOT/'out/attempts').glob('*/*/closed.json'), key=lambda p: p.stat().st_mtime)
    rows, recovered, trajectories, excluded = [], [], {}, []
    for p in paths:
        mtime = p.stat().st_mtime
        if mtime > CUTOFF:
            excluded.append({'path': str(p), 'closed_mtime': datetime.fromtimestamp(mtime, TZ).isoformat()})
            continue
        a = p.parent
        cell = a.parent.name
        j = jobs[cell]
        closed = doc(p)
        log = read(a/'child.log')
        fs = fatal(log)
        status, locomotion = outcome(closed, fs)
        start = doc(a/'started.json') if (a/'started.json').exists() else {}
        fail = doc(a/'failure.json') if (a/'failure.json').exists() else {}
        seed = start.get('seed', fail.get('seed'))
        logged_seeds = re.findall(r'Environment seed\s*:\s*(\d+)', log)
        if logged_seeds:
            assert set(map(int, logged_seeds)) == {seed}
        r = dict(cell=cell, ordinal=int(a.name), status=status, locomotion_result=locomotion,
                 kind=j['kind'], level=j['level'], mode=j['map_mode'], env=j['env_id'],
                 col=j['policy']['col'], seed=seed, geometry_seed=j['policy']['geometry_seed'],
                 attempt_path=str(a), closed_mtime=datetime.fromtimestamp(mtime, TZ).isoformat(),
                 checkpoint_sha256=start.get('checkpoint_sha256'), recorder_sha256=start.get('recorder_sha256'))
        if fs:
            assert len(fs) == 1
            n, f = fs[0]
            c = f['last_check']
            b = c['before']
            r.update(fatal_line=n, fatal_sim_time=b['sim_time_s'], fatal_env_step=b['env_step'],
                     fatal_retry_count=f['retry_count'], fatal_brightness=f['mean_brightness'],
                     fatal_before_after_equal=c['before'] == c['after'],
                     command=b['command'], fatal_quat_wxyz=b['root_quat_w'])
            r.update({'fatal_'+k: v for k, v in position(b['root_pos_w'], b['root_quat_w'], r['level'], r['col']).items()})
            # Derived eye/target, not measured camera pose.
            r['fatal_eye_derived'] = (np.asarray(b['root_pos_w']) + [-.6, -1.6, .85]).tolist()
            r['fatal_target_derived'] = (np.asarray(b['root_pos_w']) + [.25, 0, -.05]).tolist()
        elif status == 'other_failure':
            r['error'] = next((s for s in reversed(log.splitlines()) if 'Error:' in s), fail.get('reason'))
        else:
            receipt = doc(a/'attempt.json')
            q = next(a.glob('*/review.json'))
            d = doc(q)
            assert SOURCES[str(q)]['sha256'] == receipt['files']['review.json']
            assert d['seed'] == seed
            assert d['checkpoint_sha256'] == plan['checkpoint_sha256']
            tile = d['task_selection']['selected_tile']
            assert tile == {'env': r['env'], 'kind': r['kind'], 'level': r['level'], 'col': r['col']}
            cfg = d['physics']['applied_config']['scene']['terrain']['terrain_generator']
            assert cfg['size'] == [8, 8] and cfg['num_rows'] == 10 and cfg['num_cols'] == 23
            r.update(review_path=str(q), review_sha256=SOURCES[str(q)]['sha256'],
                     capture_s=d['duration_s'], frames=d['frames'],
                     minimum_accepted_brightness=d['min_mean_brightness'],
                     capture_wall_s=d['capture_wall_elapsed_s'],
                     measured_camera_count=len(d['camera_screen_projection']))
            r['camera_first_measured'] = d['camera_screen_projection'][0]
            r['camera_last_measured'] = d['camera_screen_projection'][-1]
            r['camera_pose_max_offset_error'] = 0.0
            arrpath = q.with_name('review_feet.npz')
            h = hashlib.sha256()
            with arrpath.open('rb') as f:
                for chunk in iter(lambda: f.read(1024*1024), b''):
                    h.update(chunk)
            assert h.hexdigest() == receipt['files']['review_feet.npz']
            SOURCES[str(arrpath)] = {'sha256': h.hexdigest(), 'bytes': arrpath.stat().st_size}
            with np.load(arrpath, allow_pickle=False) as z:
                traj = {k: z[k].copy() for k in ('t', 'root_pos_w', 'root_quat_w')}
            trajectories[cell] = traj
            for c in d['camera_screen_projection']:
                root = traj['root_pos_w'][c['physics_tick']]
                err = max(np.max(np.abs(np.asarray(c['camera_eye_w'])-root-[-.6,-1.6,.85])),
                          np.max(np.abs(np.asarray(c['camera_target_w'])-root-[.25,0,-.05])))
                r['camera_pose_max_offset_error'] = max(r['camera_pose_max_offset_error'], float(err))
            for label, idx in [('start', 0), ('end', -1)]:
                r.update({label+'_'+k: v for k, v in position(traj['root_pos_w'][idx], traj['root_quat_w'][idx], r['level'], r['col']).items()})
            # RGB retries are distinct from segmentation retries.
            checks = [c for c in d['render_retry_checks'] if not c.get('segmentation')]
            groups = defaultdict(list)
            for c in checks:
                groups[c['physics_tick']].append(c)
            r['rgb_recovered_frames'] = len(groups)
            r['rgb_retry_calls'] = len(checks)
            r['first_recovered_dark_sim_time'] = min((cs[0]['before']['sim_time_s'] for cs in groups.values()), default=None)
            for tick, cs in groups.items():
                b = cs[0]['before']
                e = dict(cell=cell, kind=r['kind'], level=r['level'], mode=r['mode'],
                         tick=tick, sim_time=b['sim_time_s'], retries=len(cs),
                         final_brightness=cs[-1]['mean_brightness'],
                         all_states_equal=all(c['before'] == c['after'] for c in cs))
                e.update(position(b['root_pos_w'], b['root_quat_w'], r['level'], r['col']))
                recovered.append(e)
        rows.append(r)
    # Risk-set controls: validated sibling maps at the fatal tick, same kind/level/env/seed.
    matches = []
    for f in rows:
        if f['status'] != 'dark_failure':
            continue
        for s in rows:
            if s['status'] != 'validated' or any(f[k] != s[k] for k in ('kind', 'level', 'env', 'seed')):
                continue
            tr = trajectories[s['cell']]
            ix = int(f['fatal_env_step'])
            if not 0 <= ix < len(tr['t']):
                continue
            pp = position(tr['root_pos_w'][ix], tr['root_quat_w'][ix], s['level'], s['col'])
            dd = (pp['yaw']-f['fatal_yaw']+180) % 360-180
            matches.append(dict(failed=f['cell'], control=s['cell'], tick=ix,
                                failure_edge=f['fatal_edge'], control_edge=pp['edge'],
                                xyz_difference=float(np.linalg.norm(np.array([pp[k] for k in ('x','y','z')])-np.array([f['fatal_'+k] for k in ('x','y','z')]))),
                                yaw_difference=dd))
    stage_rows = []
    stage_census = Counter()
    for p in sorted(STAGE.glob('*/attempts/*/*/child.log')):
        if p.stat().st_mtime > CUTOFF:
            continue
        log = read(p)
        fs = fatal(log)
        cp = p.parent/'closed.json'
        cls = doc(cp) if cp.exists() else {}
        stage_census[outcome(cls, fs)[0] if cls else 'open'] += 1
        if not fs:
            continue
        a = p.parent
        labels = [d.name for d in a.iterdir() if d.is_dir() and d.name.startswith('EX41-')]
        r = dict(path=str(a), model=a.parents[2].name, identity=a.parent.name,
                 ordinal=int(a.name), label=labels[0] if len(labels) == 1 else None,
                 line=fs[-1][0])
        f = fs[-1][1]
        b = f['last_check']['before']
        r.update(sim_time=b['sim_time_s'], env_step=b['env_step'], root_pos_w=b['root_pos_w'],
                 yaw=yaw(b['root_quat_w']), retries=f['retry_count'], brightness=f['mean_brightness'],
                 last_state_equal=b == f['last_check']['after'])
        logged_seeds = re.findall(r'Environment seed\s*:\s*(\d+)', log)
        if logged_seeds:
            assert len(set(logged_seeds)) == 1
            r['seed'] = int(logged_seeds[0])
            r['seed_source'] = 'child.log Environment seed'
        # Failure files often omit seed. Do not inherit a sibling attempt's seed.
        for name in ('attempt.json', 'started.json', 'failure.json', 'closed.json'):
            if (a/name).exists():
                rd = doc(a/name)
                if 'seed' in rd:
                    r['seed'] = rd['seed']
        m = re.match(r'EX41-(.+)_L(\d+)_env(\d+)-m(\d+)-(.+)-1x$', r['label'] or '')
        if m:
            r.update(kind=m[1], level=int(m[2]), env=int(m[3]), local_iteration=int(m[4]), case=m[5])
            r['mode'] = next((v for v in ('probe_prop_only','eval_pred','eval_gt') if r['case'].endswith(v)), None)
            # Original fixed64 continuous geometry; keep label-derived provenance explicit.
            if r['env'] == 5 and r['kind'] == 'pyramid_stairs_inv':
                r.update(position(b['root_pos_w'], b['root_quat_w'], r['level'], 5))
        successes = []
        for sib in sorted(a.parent.iterdir()):
            if not sib.is_dir() or not (sib/'closed.json').exists():
                continue
            c = doc(sib/'closed.json')
            if c.get('state') == 'validated' and (sib/'closed.json').stat().st_mtime <= CUTOFF:
                q = next(sib.glob('*/review.json'), None)
                rd = doc(q) if q else {}
                successes.append({'ordinal': sib.name, 'seed': rd.get('seed'),
                                  'source_head': rd.get('source_validation', {}).get('git_head')})
        r['sibling_validated'] = successes
        r['later_same_seed_pass'] = any(int(s['ordinal']) > r['ordinal'] and s['seed'] == r.get('seed') for s in successes)
        stage_rows.append(r)
    summary = {'cutoff': datetime.fromtimestamp(CUTOFF, TZ).isoformat(),
               'captured_at': datetime.now(TZ).isoformat(), 'counts': dict(Counter(r['status'] for r in rows)),
               'attempts': len(rows), 'eligible_render_attempts': sum(r['status'] != 'other_failure' for r in rows),
               'excluded_after_cutoff': excluded, 'selftests': '7 assertions PASS',
               'by_kind': {}, 'by_mode': {}, 'by_level': {},
               'fatal_time': describe([r['fatal_sim_time'] for r in rows if r['status'] == 'dark_failure']),
               'fatal_edge': describe([r['fatal_edge'] for r in rows if r['status'] == 'dark_failure']),
               'fatal_yaw': describe([r['fatal_yaw'] for r in rows if r['status'] == 'dark_failure']),
               'recovered_frames': len(recovered), 'recovered_attempts': sum(r.get('rgb_recovered_frames', 0)>0 for r in rows),
               'recovered_retry_calls': sum(e['retries'] for e in recovered),
               'recovery_retries': describe([e['retries'] for e in recovered]),
               'stage_dark_failures': len(stage_rows),
               'stage_dark_cells': len(set((r['model'], r['identity']) for r in stage_rows)),
               'stage_census': dict(stage_census),
               'stage_dark_cells_later_same_seed_pass': len(set((r['model'],r['identity']) for r in stage_rows if r['later_same_seed_pass'])),
               'stage_dark_attempts_later_same_seed_pass': sum(r['later_same_seed_pass'] for r in stage_rows),
               'stage_by_mode': dict(Counter(r.get('mode', 'unknown') for r in stage_rows))}
    assert all(r['fatal_before_after_equal'] and r['fatal_brightness'] == 0 and r['fatal_retry_count'] == 30
               for r in rows if r['status'] == 'dark_failure')
    assert all(e['all_states_equal'] and e['final_brightness'] > 10 for e in recovered)
    for key in ('kind', 'mode', 'level'):
        for v in sorted(set(r[key] for r in rows), key=str):
            summary['by_'+key][str(v)] = dict(Counter(r['status'] for r in rows if r[key] == v))
    csvwrite('attempts.csv', rows)
    csvwrite('recovered_frames.csv', recovered)
    csvwrite('matched_other_map_controls.csv', matches)
    csvwrite('earlier_stage_dark.csv', stage_rows)
    jsonwrite('summary.json', summary)
    jsonwrite('attempts.json', rows)
    jsonwrite('earlier_stage_dark.json', stage_rows)
    jsonwrite('source_sha256.json', SOURCES)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
