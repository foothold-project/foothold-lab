"""W91 CPU-only receipt for the existing turn_probe output, never a gate.

Runner owns the GPU1 chain, rc.txt, and dynamic stage-end checkpoint selection.
This reader requires all eight rotation cases plus both forward gait arrays in
each of three modes. Q is signed mean yaw rate in rad/s, not the follow ratio.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import numpy as np

from foothold_s2.eval import judge_stats as S, turn_probe_plan as P
from foothold_s2.eval.fixed_terrain import assignment_sha256

MODES = ('eval_gt', 'probe_prop_only', 'eval_pred')
CASES = (*S.SIX_CASES, *S.WALK_CASES)
FORWARD = {'fwd0.5': (0.5, 0., 0.), 'fwd1.0': (1., 0., 0.)}
TILE_SHA = '7f49a1e935ea1dd741b0db47fe6da965eaa772c03f30c94f9fa976125db33506'
STAGES = ('S2-0', 'S2a', 'S2b', 'S2c', 'S2d', 'S2e', 'T0_prime')
SCHEMA = 'foothold-ex41-turn-diagnostic/1'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def evidence(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': S.sha256_file(path)}


def read_mode(directory, *, mode, checkpoint_sha256, iteration):
    """Validate raw output and recompute Q/C. No launch/receipt claims here."""
    directory = Path(directory)
    path = directory / 'probe_result.json'
    doc = json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(doc, dict), 'probe document must be an object')
    require(doc.get('envs') == 16 and doc.get('map_mode') == mode, 'env count or map mode differs')
    require(doc.get('checkpoint_sha256') == checkpoint_sha256, 'checkpoint SHA differs')
    require(doc.get('checkpoint_iter') == iteration, 'local checkpoint iteration differs')
    require(doc.get('map_input') == 'reconstruction', 'expected reconstruction network in three modes')
    static = doc['static']
    require(static.get('sample_hz') == 200. and static.get('physics_dt') == .005, 'sample timing differs')
    feet = S.feet_from_probe(doc)
    fixed = doc['fixed_terrain']
    tiles = fixed['tiles']
    require(len(tiles) == 16 and [t['env'] for t in tiles] == list(range(16)), 'tile env mapping differs')
    require(all(t['level'] == 0 for t in tiles), 'W91 requires level zero')
    levels = np.asarray([t['level'] for t in tiles], dtype=np.int64)
    columns = np.asarray([t['col'] for t in tiles], dtype=np.int64)
    require(fixed.get('assignment_sha256') == TILE_SHA == assignment_sha256(levels, columns), 'tile SHA differs')
    require([t['kind'] for t in tiles] == ['hf_pyramid_slope'] * 8 + ['random_rough'] * 8,
            'tile names differ')
    sources = [evidence(path)]
    rows = {}
    for name in (*CASES, *FORWARD):
        rotation = name in CASES
        protocol = P.PROTOCOLS[name] if rotation else {'cmd': FORWARD[name]}
        meta = doc['protocols' if rotation else 'forward_gaits'][name]
        require(meta.get('cmd') == list(protocol['cmd']), name + ': command differs')
        if rotation:
            pre = protocol['pre']
            require(meta.get('pre') == (list(pre) if pre is not None else None), name + ': pre command differs')
            require(meta.get('terrain_levels_per_env') == levels.tolist()
                    and meta.get('terrain_types_per_env') == columns.tolist(), name + ': per-case tiles differ')
        array_path = directory / ('arrays_' + name + '.npz')
        # Retain all original arrays; load one case at a time to bound CPU RAM.
        with np.load(array_path, allow_pickle=False) as arrays:
            shapes = {'alive': (16, 1600), 'kept': (16,), 'wz': (16, 1600), 'vx': (16, 1600),
                      'force': (16, 1600, len(static['link_names'])), 'feet_pos': (16, 1600, 4, 3),
                      'root_pos': (16, 1600, 3), 'root_quat': (16, 1600, 4)}
            shapes.update({k: (16, 1600, 12) for k in ('q', 'qd', 'target', 'computed', 'applied')})
            values = {}
            for key, shape in shapes.items():
                x = arrays[key]
                require(x.shape == shape, name + ': array shape differs: ' + key)
                require(np.isfinite(x).all(), name + ': nonfinite raw input: ' + key)
                if key in ('alive', 'kept'):
                    require(x.dtype == np.bool_, name + ': alive/kept must be bool')
                values[key] = x
        a, k = values['alive'], values['kept']
        require(not (a[:, 1:] & ~a[:, :-1]).any(), name + ': alive cannot resurrect')
        require(not (k & ~a.all(axis=1)).any(), name + ': kept conflicts with alive')
        require(meta.get('kept_envs') == k.tolist() and meta.get('alive_at_end') == int(k.sum()),
                name + ': kept metadata differs')
        if rotation:
            stats = S.turn_stats(values, name, feet)
            rows[name] = {key: stats[key] for key in ('Q', 'C', 'kept', 'n_env', 'alive_end')}
            if stats['kept'] == 0:
                rows[name].update(Q=None, C=None)
            rows[name]['follow_ratio'] = None if not stats['kept'] else stats['Q'] / abs(protocol['cmd'][2])
        else:
            four = (values['force'][..., list(feet)] > S.CONTACT_N).all(-1)
            rows[name] = {'kept': int(k.sum()), 'n_env': 16, 'alive_end': int(a[:, -1].sum()),
                          'C': float(four[k].mean()) if k.any() else None,
                          'body_vx_integral_kept_mean_m': float((values['vx'][k].sum(1) / 200.).mean()) if k.any() else None}
        rows[name]['statistics_available'] = bool(k.any())
        sources.append(evidence(array_path))
    return {'mode': mode, 'rows': rows, 'sources': sources, 'fixed_terrain': fixed,
            'dr_off': doc.get('dr_off'), 'run_identity': doc.get('run_identity'),
            'flat_note': fixed.get('flat_note')}


def collect(root, *, checkpoint, iteration, stage):
    """Root contains turn16_<mode>/{rc.txt,run.log,probe_result.json,arrays_*}."""
    require(type(iteration) is int and iteration >= 0, 'iteration must be local nonnegative int')
    require(stage in STAGES, 'unknown stage-end label')
    checkpoint = Path(checkpoint)
    digest = S.sha256_file(checkpoint)
    out = {'schema': SCHEMA, 'record_only': True, 'decision': None,
           'checkpoint': evidence(checkpoint), 'iteration': iteration, 'stage': stage,
           'expected_modes': list(MODES), 'expected_cases': [*CASES, *FORWARD],
           'status': 'INCOMPLETE', 'errors': {}, 'modes': {},
           'units': {'Q': 'rad/s', 'C': 'fraction', 'follow_ratio': 'dimensionless'},
           'definition': 'Q=mean_kept(sign(cmd_wz)*mean_alive(wz)); C=mean_kept(mean_alive(all4 force>1N))'}
    for mode in MODES:
        folder = Path(root) / ('turn16_' + mode)
        try:
            rc = (folder / 'rc.txt').read_text(encoding='utf-8').strip()
            require(rc == '0', 'child return code is not 0')
            log = (folder / 'run.log').read_text(encoding='utf-8', errors='replace')
            require(re.search(r'^TURNPROBE_DONE(?:\s|$)', log, re.MULTILINE) is not None, 'completion marker absent')
            row = read_mode(folder, mode=mode, checkpoint_sha256=digest, iteration=iteration)
            row['sources'].extend(evidence(folder / name) for name in ('rc.txt', 'run.log'))
            out['modes'][mode] = row
        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
            out['errors'][mode] = type(exc).__name__ + ': ' + str(exc)
    if not out['errors']:
        out['status'] = 'COMPLETE'
    # Completeness is not a performance gate or proof of GPU1 routing.
    out['reported_cuda1_with_uuid'] = all(out['modes'].get(m, {}).get('run_identity')
        and out['modes'][m]['run_identity'].get('device') == 'cuda:1'
        and out['modes'][m]['run_identity'].get('gpu_uuid') not in (None, '', 'None') for m in MODES)
    out['reported_cuda1_with_uuid'] = bool(out['reported_cuda1_with_uuid'])
    out['physical_gpu1_verified'] = False  # Runner must match UUID to physical GPU inventory.
    out['reader_sources'] = [evidence(p) for p in (__file__, S.__file__, P.__file__)]
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('root', 'checkpoint', 'stage', 'out'):
        parser.add_argument('--' + flag, required=True)
    parser.add_argument('--iteration', type=int, required=True)
    args = parser.parse_args(argv)
    result = collect(args.root, checkpoint=args.checkpoint, iteration=args.iteration, stage=args.stage)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
    if path.exists():
        require(path.read_text(encoding='utf-8') == data, 'immutable diagnostic receipt conflict; use new retry folder')
    else:
        with path.open('x', encoding='utf-8') as out:
            out.write(data)
    print(result['status'])
    return 0 if result['status'] == 'COMPLETE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
