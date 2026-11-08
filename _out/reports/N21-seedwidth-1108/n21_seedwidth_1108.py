"""Read-only N21 seed-width analysis. No Kit, torch, or GPU imports.

Each seed contributes one median per cell. Three seeds are never pooled into
192 independent robots or 57,600 independent timesteps. Partial runs are saved
only to scratch, and cannot produce the final report.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime
from itertools import combinations
import argparse
import csv
import hashlib
import json
import math
import statistics
import numpy as np

OLD = Path('D:/mai-tmp/runner/ex42_n21_w63_20261108')
NEW = Path('D:/mai-tmp/lead/n21_seedrep_1108')
OLD_NAMES = {
    ('flat', 'on'): 'gpu0-flat-300',
    ('flat', 'off'): 'gpu1-flat-300-off',
    ('continuous', 'on'): 'gpu0-continuous-300',
    ('continuous', 'off'): 'gpu0-continuous-300-off',
}
MODES = ['eval_gt', 'eval_pred', 'probe_prop_only']
CMDS = ['fwd0.5', 'fwd1.0', 'spin+1.2', 'spin-1.2', 'back0.5', 'side+0.5', 'side-0.5', 'stop']
SEEDS = [42, 43, 44]
TERRAINS = ['flat', 'continuous']
CONDS = ['off', 'on']
PARENT = '1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613'
LABEL = {'eval_gt': '정답', 'eval_pred': '복원', 'probe_prop_only': '끔'}
FIELDS = {
    'vx': ('vx_abs_error_mean_alive_mps', 'm/s'),
    'vy': ('vy_abs_error_mean_alive_mps', 'm/s'),
    'wz': ('wz_abs_error_mean_alive_radps', 'rad/s'),
    'stop_xy': ('body_xy_speed_mean_alive_mps', 'm/s'),
    'stop_wz': ('wz_abs_error_mean_alive_radps', 'rad/s'),
}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def ahash(a):
    a = np.ascontiguousarray(a)
    h = hashlib.sha256(str((a.shape, str(a.dtype))).encode())
    h.update(a.tobytes())
    return h.hexdigest()

def jhash(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def path_for(t, c, s):
    folder = OLD / OLD_NAMES[t, c] if s == 42 else NEW / f'{t}{"-off" if c == "off" else ""}-s{s}'
    return folder / 'n21_record_only.json'

def metrics(cmd):
    if cmd == 'stop':
        return ['stop_xy', 'stop_wz']
    return ['wz' if cmd.startswith('spin') else 'vy' if cmd.startswith('side') else 'vx']

def comparison(off, on):
    """Descriptive width comparison, never a significance test."""
    off, on = np.asarray(off, float), np.asarray(on, float)
    assert off.shape == on.shape == (3,) and np.isfinite(off).all() and np.isfinite(on).all()
    wo, wn = float(np.ptp(off)), float(np.ptp(on))
    delta = on - off
    threshold = max(wo, wn)
    return {
        'off': off.tolist(), 'on': on.tolist(),
        'off_min': float(off.min()), 'off_max': float(off.max()), 'off_width': wo,
        'on_min': float(on.min()), 'on_max': float(on.max()), 'on_width': wn,
        'width_max': threshold, 'delta42': float(delta[0]),
        'morning_over_width': bool(abs(delta[0]) > threshold + 1e-12),
        'delta_by_seed': delta.tolist(), 'delta_min': float(delta.min()), 'delta_max': float(delta.max()),
        'all_positive': bool((delta > 1e-12).all()), 'all_negative': bool((delta < -1e-12).all()),
        'intervals_disjoint': bool(on.min() > off.max() + 1e-12 or off.min() > on.max() + 1e-12),
    }

def known_answers():
    assert np.median([.1, .2, .3, .4]) == .25
    r = comparison([1, 2, 3], [4, 5, 6])
    assert r['width_max'] == 2 and r['delta42'] == 3 and r['morning_over_width']
    assert r['intervals_disjoint'] and r['all_positive']
    r = comparison([1, 2, 3], [3, 4, 5])
    assert not r['morning_over_width'] and not r['intervals_disjoint']  # equality is within
    r = comparison([1, 2, 3], [3.1, 2.2, 2.3])
    assert r['morning_over_width'] and not r['all_positive'] and not r['intervals_disjoint']
    r = comparison([64, 64, 64], [64, 64, 64])
    assert r['delta42'] == 0 and not r['morning_over_width']
    assert np.count_nonzero(np.any(np.array([[0, 0], [1, 0]]) != 0, axis=1)) == 1
    assert ahash(np.array([[1, 2]])) != ahash(np.array([[1, 3]]))
    assert metrics('stop') == ['stop_xy', 'stop_wz'] and metrics('side-0.5') == ['vy']
    try:
        comparison([1, 2, np.nan], [1, 2, 3])
    except AssertionError:
        pass
    else:
        raise AssertionError('nonfinite input accepted')
    return 9

def csvout(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys, lineterminator='\n')
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})

def inspect(out):
    count = known_answers()
    docs, cells, inputs, protocol, signatures, physics = {}, [], [], [], {}, {}
    missing = []
    for t in TERRAINS:
      for c in CONDS:
       for s in SEEDS:
        p = path_for(t, c, s)
        if not p.is_file():
            missing.append(str(p)); continue
        before = (p.stat().st_size, p.stat().st_mtime_ns)
        d = json.loads(p.read_text(encoding='utf-8-sig'))
        assert before == (p.stat().st_size, p.stat().st_mtime_ns), 'input changed while reading'
        assert d['record_only'] is True and d['checkpoint_sha256'] == PARENT
        assert d['eval_seed'] == d['run_identity']['eval_seed'] == s
        assert d['envs'] == 64 and d['steps'] == 300 and d['policy_dt_s'] == .02
        assert set(d['commands']) == set(CMDS) and set(d['modes']) == set(MODES)
        assert all(x['level'] == 2 for x in d['terrain_tiles'])
        assert d['terrain_set'] == f'n21-{t}' and d['dr_mode']['mode'] == c
        assert d['dr_mode']['scale'] == (1.0 if c == 'on' else 0.0)
        docs[t, c, s] = d
        inputs.append({'path': str(p), 'sha256': sha(p), 'kind': 'receipt'})
        identity = d['run_identity']
        protocol.append({'terrain': t, 'dr': c, 'seed_expected': s, 'eval_seed': d['eval_seed'],
                         'identity_seed': identity['eval_seed'], 'code_head': identity['code_head'],
                         'dirty_files': identity.get('code_dirty_files'), 'gpu': identity.get('device'),
                         'gpu_uuid': identity.get('gpu_uuid'), 'checkpoint_sha256': d['checkpoint_sha256'],
                         'assignment_sha256': d['fixed_terrain']['assignment_sha256'],
                         'terrain_counts': dict(Counter(x['kind'] for x in d['terrain_tiles'])),
                         'source_sha256': d['source_sha256'], 'path': str(p)})
        signatures[t, c, s] = {}
        for mode in MODES:
         for cmd in CMDS:
            row = d['modes'][mode][cmd]
            per = sorted(row['per_env'], key=lambda r: r['env'])
            assert [r['env'] for r in per] == list(range(64))
            npath = p.parent / d['env_arrays'][f'{mode}/{cmd}']
            with np.load(npath, allow_pickle=False) as q:
                assert q['vx'].shape == q['alive'].shape == (300, 64)
                assert row['alive_envs_at_end'] == int(q['alive_end'].sum()) == sum(x['alive_at_end'] for x in per)
                assert np.array_equal(q['alive'].sum(0), [x['samples_alive'] for x in per])
                assert np.array_equal(q['alive'][-1], q['alive_end'])
                assert np.all(np.diff(q['alive'].astype(int), axis=0) <= 0)
                qid = json.loads(str(q['run_identity']))
                assert qid['eval_seed'] == s and qid['checkpoint_sha256'] == PARENT
                for key in ['device', 'gpu_uuid', 'code_head']:
                    assert qid[key] == identity[key]
                if cmd.startswith(('fwd', 'back')):
                    calculated = (np.abs(q['vx'] - d['commands'][cmd][0]) * q['alive']).sum(0) / np.maximum(q['alive'].sum(0), 1)
                    np.testing.assert_allclose(calculated, [x[FIELDS['vx'][0]] for x in per], atol=2e-6)
                signatures[t, c, s][mode, cmd] = {k: np.array(q[k]) for k in ['start_xy', 'vx']}
            inputs.append({'path': str(npath), 'sha256': sha(npath), 'kind': 'npz'})
            item = {'terrain': t, 'dr': c, 'seed': s, 'mode': mode, 'command': cmd,
                    'alive': row['alive_envs_at_end'], 'envs': 64,
                    'per_env_error_fingerprint': jhash([{k: x[k] for k, u in FIELDS.values()} for x in per])}
            for met in metrics(cmd):
                a = np.asarray([x[FIELDS[met][0]] for x in per], float)
                assert np.isfinite(a).all()
                item[met] = float(np.median(a))
                assert item[met] == statistics.median([float(x) for x in a])
            cells.append(item)
        if c == 'on':
            reads = d['dr']['readback']; assert len(reads) == 24
            actual = reads['eval_gt/fwd1.0']['actual_values_by_env']
            masses = np.asarray(actual['mass_kg_by_env_body'], float)
            materials = np.asarray(actual['material_coefficients_by_env_shape'], float)
            i = actual['body_names'].index('base')
            delta = masses[:, i] - 6.921000003814697
            assert masses.shape == (64, 19) and materials.shape == (64, 27, 3)
            assert np.isfinite(masses).all() and np.isfinite(materials).all()
            assert ((delta >= -1 - 1e-6) & (delta <= 3 + 1e-6)).all()
            assert ((materials[:, :, :2] >= .2 - 1e-6) & (materials[:, :, :2] <= 1.2 + 1e-6)).all()
            assert (materials[:, :, 1] <= materials[:, :, 0] + 1e-6).all()
            assert (materials[:, :, 2] == 0).all()
            assert all(np.array_equal(masses, v['actual_values_by_env']['mass_kg_by_env_body'])
                       and np.array_equal(materials, v['actual_values_by_env']['material_coefficients_by_env_shape']) for v in reads.values())
            pushes = {k: np.asarray(v['push_events'][0]['dv_xyz_w_mps']) for k, v in reads.items()}
            for k, v in reads.items():
                seed = int.from_bytes(hashlib.sha256(f'{s}|{k}'.encode()).digest()[:4], 'big') & 0x7fffffff
                assert v['push_events'][0]['seed'] == seed
                assert v['push_events'][0]['step'] == 100 and v['push_events'][0]['t_s'] == 2.0
            physics[t, s] = {'masses': masses, 'materials': materials, 'pushes': pushes,
                             'body_index': i, 'base_range': [float(masses[:, i].min()), float(masses[:, i].max())],
                             'static_range': [float(materials[:, :, 0].min()), float(materials[:, :, 0].max())],
                             'dynamic_range': [float(materials[:, :, 1].min()), float(materials[:, :, 1].max())]}
        else:
            assert 'dr' not in d  # no claim about absent off physical readback

    cross = []
    for t in TERRAINS:
      same = [v for (tt, cc, ss), v in docs.items() if tt == t]
      if same:
       for k in ['checkpoint_sha256', 'envs', 'steps', 'policy_dt_s', 'commands', 'terrain_tiles', 'terrain_columns', 'fixed_terrain', 'restored_modes']:
        assert all(v[k] == same[0][k] for v in same), (t, k)
      for c in CONDS:
       for a, b in combinations(SEEDS, 2):
        if (t, c, a) not in docs or (t, c, b) not in docs: continue
        for mode in MODES:
         for cmd in CMDS:
          sa, sb = signatures[t, c, a][mode, cmd], signatures[t, c, b][mode, cmd]
          r = {'terrain': t, 'dr': c, 'seeds': [a, b], 'mode': mode, 'command': cmd}
          for k in sa:
            r[k + '_equal'] = bool(np.array_equal(sa[k], sb[k]))
            r[k + '_changed_envs'] = int(np.any(sa[k] != sb[k], axis=1 if k == 'start_xy' else 0).sum())
            r[k + '_sha_a'], r[k + '_sha_b'] = ahash(sa[k]), ahash(sb[k])
          cross.append(r)
    physrows = []
    for t in TERRAINS:
     for a, b in combinations(SEEDS, 2):
      if (t, a) not in physics or (t, b) not in physics: continue
      aa, bb = physics[t, a], physics[t, b]
      physrows.append({'terrain': t, 'seeds': [a, b],
                       'mass_changed_envs': int(np.any(aa['masses'] != bb['masses'], axis=1).sum()),
                       'material_changed_envs': int(np.any(aa['materials'] != bb['materials'], axis=(1, 2)).sum()),
                       'mass_sha_a': ahash(aa['masses']), 'mass_sha_b': ahash(bb['masses']),
                       'material_sha_a': ahash(aa['materials']), 'material_sha_b': ahash(bb['materials']),
                       'push_changed_cells': sum(not np.array_equal(aa['pushes'][k], bb['pushes'][k]) for k in aa['pushes'])})

    comp = []
    lookup = {(r['terrain'], r['dr'], r['seed'], r['mode'], r['command']): r for r in cells}
    for t in TERRAINS:
     if not all((t, c, s) in docs for c in CONDS for s in SEEDS): continue
     for m in MODES:
      for cmd in CMDS:
       for met in ['alive'] + metrics(cmd):
        off = [lookup[t, 'off', s, m, cmd][met] for s in SEEDS]
        on = [lookup[t, 'on', s, m, cmd][met] for s in SEEDS]
        comp.append({'terrain': t, 'mode': m, 'command': cmd, 'metric': met,
                     'unit': 'env/64' if met == 'alive' else FIELDS[met][1], **comparison(off, on)})
    source_changes = []
    for t in TERRAINS:
     for c in CONDS:
      if (t, c, 42) not in docs: continue
      old = docs[t, c, 42]['source_sha256']
      for s in [43, 44]:
       if (t, c, s) not in docs: continue
       new = docs[t, c, s]['source_sha256']
       source_changes.append({'terrain': t, 'dr': c, 'seeds': [42, s],
                              'changes': {k: [old.get(k), new.get(k)] for k in sorted(set(old) | set(new)) if old.get(k) != new.get(k)}})
    shared_physics = []
    for s in SEEDS:
     if ('flat', s) in physics and ('continuous', s) in physics:
      shared_physics.append({'seed': s, 'mass_equal': bool(np.array_equal(physics['flat', s]['masses'], physics['continuous', s]['masses'])),
                             'material_equal': bool(np.array_equal(physics['flat', s]['materials'], physics['continuous', s]['materials']))})
    morning_path = Path('D:/mai-wt/foothold-lab/analyst-ex41-score-name-1102/_out/reports/N21-1108/audit.json')
    morning = json.loads(morning_path.read_text(encoding='utf-8'))
    for old in morning['cells']:
      for c in CONDS:
        current = lookup[old['terrain'], c, 42, old['mode'], old['command']]
        assert current['alive'] == old[c]['alive']
        assert [current[k] for k in metrics(old['command'])] == old[c]['error_medians']
    inputs.append({'path': str(morning_path), 'sha256': sha(morning_path), 'kind': 'morning_audit'})
    summary = {'read_at': datetime.now().isoformat(timespec='seconds'), 'complete': not missing,
               'missing': missing, 'known_answer_tests': count, 'protocol': protocol,
               'cells': cells, 'comparison': comp, 'array_seed_checks': cross, 'physical_seed_checks': physrows,
               'physical_ranges': [{'terrain': t, 'seed': s, **{k: v for k, v in p.items() if k.endswith('_range')}} for (t, s), p in physics.items()],
               'source_changes': source_changes, 'shared_physics_across_terrain': shared_physics,
               'inputs': inputs, 'npz_count': sum(x['kind'] == 'npz' for x in inputs)}
    out.mkdir(parents=True, exist_ok=True)
    (out / 'audit.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    for name, rows in [('cells', cells), ('comparison', comp), ('seed_array_checks', cross), ('physics_seed_checks', physrows), ('protocol', protocol)]:
        csvout(out / (name + '.csv'), rows)
    print(json.dumps({'complete': not missing, 'missing': missing, 'npz_checked': summary['npz_count'],
                      'cells': len(cells), 'comparisons': len(comp), 'physics_seed_checks': physrows,
                      'all_trajectory_pairs_different': all(not r['vx_equal'] for r in cross)}, ensure_ascii=False))
    return summary

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=Path('D:/mai-tmp/analyst/n21-seedwidth-1108'))
    args = parser.parse_args()
    inspect(args.out)
