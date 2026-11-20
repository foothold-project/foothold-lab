"""Opt-in EX-42 continuous terrain boundary evidence, never a training/exit control.

Decision ccfe67bdc, lead 2026-11-20 23:21/23:25: three-seed means per speed,
GT minus off strictly greater than ten; PRED minus off is record-only.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path

import numpy as np

from foothold_s2.machine_profile import machine_path
from foothold_s2.terrains.columns import CONTINUOUS

SWITCH = 'EX42_CONTINUOUS_CELLS'
KINDS = tuple(CONTINUOUS)
MODES = ('eval_gt', 'eval_pred', 'probe_prop_only', 'probe_flat')
SEEDS = (42, 43, 44)
COMMANDS = ('fwd0.5', 'fwd1.0')
DEFINITION = {
    'name': '연속 넘음 정의 v1 (11/20 lead 승인)',
    'source': 'ccfe67bdc · lead-lx 2026-11-20 23:21/23:25',
    'duration_s': 12.0, 'settle_s': 0.5, 'envs_per_cell': 64,
    'start': 'existing named-kind position reset; yaw fixed +x; coordinates relative to tile center origin',
    'reach': 'root_x_local_m >= 3.5 m; slopes >= 3.85 m, then continuously alive 0.5 s',
    'survival': 'no termination or timeout through the last policy step; first episode only',
    'fall': 'termination_manager.terminated in the first episode; timeout separate, not video-classified fall',
    'flat_map': 'MAPSWAP=flat: g[:,9:11,:].flatten(1).median(1).values broadcast to 32x16',
    'flat_source': '/home/jay/mai/tmp/planner/mapprobe1120/run_child_map.py:24-26',
    'comparison': 'per speed: arithmetic mean of 42/43/44 counts (64 env per seed); any GT-off >10 => HOLD_NEXT_LAYER',
    'decision_use': 'report only; no training, ladder, P1 or stage exit mutation',
}


def enabled(environ=None):
    value = (os.environ if environ is None else environ).get(SWITCH, '0')
    if value not in ('0', '1'):
        raise ValueError(f'{SWITCH} must be 0 or 1')
    return value == '1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, body):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(body, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def build_plan(*, checkpoint, output, device, task, plan_path, plan, mesh_dir, stage_id, opened):
    stages = [r for r in plan['stages'] if r['id'] == stage_id]
    if len(stages) != 1 or stage_id not in ('E2', 'E3', 'E4', 'E5', 'M', 'E6a', 'E6b'):
        raise ValueError('continuous boundary needs an eligible real stage row')
    rows, children = [], []
    for kind in KINDS:
        cap = opened.get('A/' + kind)
        if type(cap) is not int or not 0 <= cap <= 9:
            raise ValueError(f'continuous cap missing or invalid: A/{kind}')
        for seed in SEEDS:
            folder = Path(output) / 'continuous_cells' / kind / f'L{cap}_seed{seed}'
            for command in COMMANDS:
                for mode in MODES:
                    rows.append(dict(kind=kind, family='A', level=cap, seed=seed, command=command,
                                     mode=mode, envs=64, folder=str(folder)))
            argv = [str(machine_path('conda_python')), '-m', 'foothold_s2.eval.ex42_continuous_eval',
                    '--task', task, '--checkpoint', str(checkpoint), '--envs', '64', '--steps', '600',
                    '--modes', ','.join(MODES), '--command-suite', 'core', '--commands', ','.join(COMMANDS),
                    '--fixed-terrain', '--fixed-level', str(cap), '--mesh-dir', str(mesh_dir),
                    '--ex42-kind-family', 'A', '--ex42-kind-name', kind, '--eval-seed', str(seed),
                    '--ex42-evaluation-plan', str(plan_path), '--start-yaw-zero',
                    '--out', str(folder), '--device', device, '--headless',
                    f"--kit_args=--/UJITSO/datastore/localCachePath={machine_path('isaac_cache_root')}"]
            children.append(dict(name=f'continuous_{kind}_s{seed}', argv=argv, folder=str(folder), kind=kind,
                                 level=cap, seed=seed))
    return dict(definition=DEFINITION, stage_id=stage_id, cells=rows, commands=children)


def count_trace(trace, *, fall, timeout, finish_x_m):
    from foothold_s2.eval.ex42_kind_completion import score_last_support
    alive = np.asarray(trace['alive'])
    fall, timeout = np.asarray(fall), np.asarray(timeout)
    if (fall.shape != alive.shape or timeout.shape != alive.shape or
            fall.dtype != np.dtype(bool) or timeout.dtype != np.dtype(bool)):
        raise ValueError('continuous termination telemetry shape/type differs')
    before = np.concatenate([np.ones((1, 64), dtype=bool), alive[:-1]], axis=0)
    if (np.any((fall | timeout) & ~before) or
            not np.array_equal(alive, before & ~(fall | timeout))):
        raise ValueError('continuous first-episode termination telemetry differs')
    counted = score_last_support(trace, finish_x_m=finish_x_m, settle_s=.5, envs=64)
    counted['fall_count'] = int(fall.any(axis=0).sum())
    counted['timeout_count'] = int(timeout.any(axis=0).sum())
    return counted


def summarize(rows):
    expected = {(k, seed, cmd, mode) for k in KINDS for seed in SEEDS for cmd in COMMANDS for mode in MODES}
    by = {}
    for row in rows:
        key = (row['kind'], row['seed'], row['command'], row['mode'])
        if key in by or key not in expected or row.get('envs') != 64:
            raise ValueError('continuous duplicate/unexpected cell or env denominator')
        if type(row.get('level')) is not int or not 0 <= row['level'] <= 9:
            raise ValueError('continuous cell cap invalid')
        for name in ('success_count', 'survival_count', 'fall_count'):
            if type(row.get(name)) is not int or not 0 <= row[name] <= 64:
                raise ValueError('continuous cell count invalid')
        by[key] = row
    if set(by) != expected:
        raise ValueError('continuous cell coverage incomplete')
    kinds = {}
    for kind in KINDS:
        levels = {row['level'] for row in rows if row['kind'] == kind}
        if len(levels) != 1:
            raise ValueError('continuous compared cells have different caps')
        speeds = {}
        for cmd in COMMANDS:
            means = {mode: sum(by[kind, s, cmd, mode]['success_count'] for s in SEEDS) / 3 for mode in MODES}
            # Integer sums implement strictly >10 mean without rounding a threshold.
            gap_sum = sum(by[kind, s, cmd, 'eval_gt']['success_count'] -
                          by[kind, s, cmd, 'probe_prop_only']['success_count'] for s in SEEDS)
            speeds[cmd] = dict(success_mean=means, gt_minus_off=gap_sum / 3,
                               pred_minus_off=means['eval_pred'] - means['probe_prop_only'],
                               pred_comparison_role='record_only',
                               judgement='HOLD_NEXT_LAYER' if gap_sum > 30 else 'PASS')
        kinds[kind] = dict(level=levels.pop(), speeds=speeds,
                          judgement='HOLD_NEXT_LAYER' if any(r['judgement'] == 'HOLD_NEXT_LAYER'
                                                            for r in speeds.values()) else 'PASS')
    return dict(definition=DEFINITION, cells=rows, kinds=kinds,
                judgement='HOLD_NEXT_LAYER' if any(r['judgement'] == 'HOLD_NEXT_LAYER'
                                                  for r in kinds.values()) else 'PASS')


def read_child(child, *, mesh, checkpoint_sha256, plan_path, physical_gpu):
    """Recount raw first episodes; missing/corrupt/mixed evidence never becomes zero/pass."""
    from foothold_s2.eval.ex42_mesh_eval import validate_kind_cell
    from foothold_s2.eval.fixed_terrain import kind_assignment, assignment_sha256
    from foothold_s2.eval.ex42_friction import load_policy
    folder = Path(child['folder'])
    result_path = folder / 'map_modes.json'
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    kind, level, seed = (child[k] for k in ('kind', 'level', 'seed'))
    identity = result.get('run_identity') or {}
    if (result.get('checkpoint_sha256') != checkpoint_sha256 or result.get('eval_seed') != seed or
            result.get('envs') != 64 or result.get('steps') != 600 or
            result.get('ex42_mesh', {}).get('mesh_sha256') != mesh['mesh_sha256'] or
            set(result.get('modes', {})) != set(MODES) or
            any(set(result['modes'][mode]) != set(COMMANDS) for mode in MODES) or
            identity.get('device') != physical_gpu['device'] or
            str(identity.get('gpu_uuid', '')).lower().removeprefix('gpu-') !=
            str(physical_gpu['gpu_uuid']).lower().removeprefix('gpu-')):
        raise ValueError('continuous child identity/mode coverage differs')
    policy = load_policy(plan_path)
    friction = result.get('evaluation_friction') or {}
    if friction.get('state') != 'verified' or any(friction.get(k) != v for k, v in policy.items()):
        raise ValueError('continuous child friction evidence differs')
    validate_kind_cell(result, mesh, family='A', kind=kind, level=level, envs=64, start_yaw_zero=True)
    table = [dict(family=f, kind=k) for f, k in zip(mesh['column_family'], mesh['columns'])]
    levels, cols = kind_assignment(64, 10, table, 'A', kind, level)
    assignment = assignment_sha256(levels, cols)
    rows = []
    for cmd in COMMANDS:
        for mode in MODES:
            key = f'{mode}/{cmd}'
            name = f'env_arrays_{mode}_{cmd}.npz'
            if result.get('env_arrays', {}).get(key) != name:
                raise ValueError('continuous raw path differs')
            raw_path = folder / name
            telemetry_path = folder / f'continuous_telemetry_{mode}_{cmd}.npz'
            with np.load(raw_path, allow_pickle=False) as a, np.load(telemetry_path, allow_pickle=False) as t:
                trace = {k: a[k] for k in ('root_x_local_m', 'root_y_local_m', 'alive', 'dt')}
                if (trace['alive'].shape != (600, 64) or abs(float(a['dt']) * 600 - 12.) > 1e-6 or
                        str(a['assignment_sha256']) != assignment or
                        not np.array_equal(a['terrain_level'], levels) or not np.array_equal(a['terrain_col'], cols) or
                        not np.array_equal(a['kind'], np.repeat(kind, 64)) or
                        str(t['checkpoint_sha256']) != checkpoint_sha256 or int(t['seed']) != seed or
                        str(t['mode']) != mode or str(t['command']) != cmd or
                        int(t['flat_calls']) != (600 if mode == 'probe_flat' else 0) or
                        str(t['flat_definition']) != DEFINITION['flat_map'] or
                        str(t['producer_sha256']) != sha(Path(__file__).parent / 'eval/ex42_continuous_eval.py')):
                    raise ValueError('continuous raw/telemetry identity or duration differs')
                if json.loads(str(a['run_identity'])) != identity:
                    raise ValueError('continuous raw run identity differs')
                counts = result['modes'][mode][cmd]
                used = 600 * 64 if mode in ('eval_gt', 'probe_flat') else 0
                if (counts.get('policy_steps_x_envs') != 600 * 64 or counts.get('gt_used') != used or
                        counts.get('alive_envs_at_end') != int(a['alive'][-1].sum())):
                    raise ValueError('continuous map input or survival evidence differs')
                counted = count_trace(trace, fall=t['fall'], timeout=t['timeout'],
                                      finish_x_m=3.85 if kind.startswith('hf_pyramid_slope') else 3.5)
            rows.append(dict(kind=kind, family='A', level=level, seed=seed, command=cmd, mode=mode,
                             **counted, evidence={p.name: dict(path=str(p), sha256=sha(p))
                                                   for p in (result_path, raw_path, telemetry_path)}))
    return rows


def execute(spec, *, checkpoint, checkpoint_sha256, output, mesh, plan_path, process, env, physical_gpu):
    rows, failures, children = [], {}, {}
    for child in spec['commands']:
        try:
            state = process.hidden_child(child['argv'], Path(output) / 'children' / child['name'], env=env)
            children[child['name']] = state
            if state.get('state') != 'done':
                raise ValueError(f"child state {state.get('state')}: {state.get('reason')}")
            if sha(checkpoint) != checkpoint_sha256:
                raise ValueError('continuous checkpoint changed during evaluation')
            rows.extend(read_child(child, mesh=mesh, checkpoint_sha256=checkpoint_sha256,
                                   plan_path=plan_path, physical_gpu=physical_gpu))
        except (OSError, ValueError, KeyError, TypeError, EOFError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
            failures[child['name']] = f'{type(exc).__name__}: {exc}'
    result = summarize(rows) if not failures else dict(definition=DEFINITION, judgement='HOLD_NO_DATA',
                                                      cells=rows, failures=failures, kinds={})
    result.update(format='foothold-ex42-continuous-cells/1', checkpoint=str(checkpoint),
                  checkpoint_sha256=checkpoint_sha256, stage_id=spec['stage_id'],
                  evaluation_plan=dict(path=str(plan_path), sha256=sha(plan_path)),
                  mesh_sha256=mesh['mesh_sha256'], children=children)
    path = Path(output) / 'continuous_cells.json'
    write(path, result)
    return dict(path=str(path), sha256=sha(path), judgement=result['judgement'], decision_use='record_only')
