"""EX41 shadow watcher: immutable evaluations, scores and receipts, no training control."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import subprocess
import time
import uuid

import numpy as np

from foothold_s2.curriculum.continuous import load_plan
from foothold_s2.curriculum.ex41 import digest
from foothold_s2.curriculum.ex41_scoring import enrich_score_metrics, enrich_training_metrics
from foothold_s2.curriculum.ex41_symmetry import map_pairs, combine
from foothold_s2.eval.axis_v2_cells import case_specs, yaw_accumulation, finite_median
from foothold_s2.eval.eval_dr_mode import require_dr_off_document
from foothold_s2.eval.ex41_push_ladder_contract import PUSH_LADDER_EXPECTED_CHILDREN
from foothold_s2.ex40_score import config, sha256
from foothold_s2.ex40_score_watch import _atomic, _manifest_digest, _stable
from foothold_s2.ex41_eval_once import DEFAULT_CONFIG, DEFAULT_TABLE, MODES, commands, hidden_child

MODEL = re.compile(r'model_(0|[1-9][0-9]*)\.pt\Z')
W78_CASES = ('stairs_fwd', 'stairs_side_left', 'stairs_side_right', 'stairs_back',
             'stairs_fwd_turn_return', 'stairs_fwd_back_return', 'slope_fwd1.0',
             'flat_fwd1.0', 'flat_fwd1.0_heading', 'stairs_fwd_stop_back')
W78_PERIODIC_SIDE_CASES = ('stairs_side_left', 'stairs_side_right')
MAX_TECHNICAL_REMEASUREMENTS = 3
MAX_TECHNICAL_MEASUREMENT_ATTEMPTS = 1 + MAX_TECHNICAL_REMEASUREMENTS


def read(path):
    row = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(row, dict): raise ValueError(f'JSON object required: {path}')
    return row


def evidence(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': sha256(path)}


def eval_pred_map_error_record_only(map_modes_path):
    """Summarize existing eval_pred map-error NPZ rows for display only.

    This metric is deliberately not used by maintenance, stage, safety, or
    graduation decisions. Values come from the evaluator's saved per-env
    map_err_* arrays and each source NPZ is returned as evidence.
    """
    source = Path(map_modes_path).resolve(strict=True)
    data = read(source)
    env_arrays = data.get('env_arrays')
    cases = data.get('modes', {}).get('eval_pred')
    if not isinstance(env_arrays, dict) or not isinstance(cases, dict) or not cases:
        raise ValueError('eval_pred map-error source index is missing')
    summary, refs = {}, []

    def finite_summary(values):
        values = np.asarray(values, dtype=np.float64).reshape(-1)
        values = values[np.isfinite(values)]
        if not values.size:
            return {'finite_envs': 0, 'mean_cm': None, 'median_cm': None}
        return {'finite_envs': int(values.size), 'mean_cm': float(values.mean()),
                'median_cm': float(np.median(values))}

    for case in sorted(cases):
        rel = env_arrays.get(f'eval_pred/{case}')
        if not isinstance(rel, str) or Path(rel).name != rel or not rel.endswith('.npz'):
            raise ValueError(f'eval_pred map-error NPZ reference is invalid: {case}')
        path = source.parent / rel
        refs.append(evidence(path))
        with np.load(path, allow_pickle=False) as raw:
            required = {'env', 'alive_end', 'map_err_inrange_mean_cm',
                        'map_err_all_mean_cm', 'map_err_inrange_steps'}
            if not required.issubset(raw.files):
                raise ValueError(f'eval_pred map-error fields are missing: {case}')
            env = np.asarray(raw['env'])
            alive = np.asarray(raw['alive_end'], dtype=bool)
            inrange = np.asarray(raw['map_err_inrange_mean_cm'], dtype=np.float64)
            all_cells = np.asarray(raw['map_err_all_mean_cm'], dtype=np.float64)
            steps = np.asarray(raw['map_err_inrange_steps'])
            if (env.ndim != 1 or alive.shape != env.shape or inrange.shape != env.shape
                    or all_cells.shape != env.shape or steps.shape != env.shape
                    or len(set(int(v) for v in env.tolist())) != env.size):
                raise ValueError(f'eval_pred map-error per-env rows are malformed: {case}')
            summary[case] = {
                'envs': int(env.size),
                'alive_at_end': int(alive.sum()),
                'inrange_mean_cm': finite_summary(inrange),
                'all_cells_mean_cm': finite_summary(all_cells),
                'inrange_step_count': int(np.asarray(steps, dtype=np.int64).sum()),
            }
    return {'format': 'ex41-eval-pred-map-error-record-only/1',
            'decision_use': 'none_record_only',
            'definition': 'per-env mean step error in centimeters from map64 env_arrays; summaries are mean and median across finite env rows',
            'cases': summary}, refs


def map64_stand_error_record_only(map_modes_path, stand_paths):
    """Collect persisted map error summaries for map64 and stance, without verdict use."""
    map_path = Path(map_modes_path).resolve(strict=True)
    map_doc = read(map_path)
    env_arrays = map_doc.get('env_arrays')
    modes = map_doc.get('modes')
    if not isinstance(env_arrays, dict) or not isinstance(modes, dict):
        raise ValueError('map64 record-only map error inputs are missing')
    refs = [evidence(map_path)]

    def require_summary(value, source):
        if (not isinstance(value, dict)
                or value.get('schema') != 'foothold-map-error-record-only/1'
                or value.get('decision_use') != 'none_record_only'
                or value.get('state') not in ('measured', 'unavailable')):
            raise ValueError(f'record-only map error summary invalid: {source}')
        if value['state'] == 'measured':
            for key in ('mean_of_env_step_means_cm', 'maximum_env_step_cellmax_cm'):
                number = value.get(key)
                if type(number) not in (int, float) or not math.isfinite(number):
                    raise ValueError(f'record-only map error value invalid: {source}/{key}')
        return value

    map_summary = {}
    for mode, cases in modes.items():
        if not isinstance(cases, dict):
            raise ValueError(f'map64 mode rows malformed: {mode}')
        map_summary[mode] = {}
        for case, row in cases.items():
            source = f'env_arrays_{mode}_{case}'
            map_summary[mode][case] = require_summary(
                row.get('restoration_error_record_only'), source)
            rel = env_arrays.get(f'{mode}/{case}')
            if isinstance(rel, str) and Path(rel).name == rel and rel.endswith('.npz'):
                refs.append(evidence(map_path.parent / rel))
            elif map_summary[mode][case]['state'] == 'measured':
                raise ValueError(f'map64 record-only source NPZ is missing: {source}')

    stand_summary = {}
    for mode, path in sorted(stand_paths.items()):
        path = Path(path).resolve(strict=True)
        doc = read(path)
        stand_summary[mode] = require_summary(
            doc.get('restoration_error_record_only'), str(path))
        raw = path.parent / 'stand_raw.npz'
        if stand_summary[mode]['state'] == 'measured':
            refs.append(evidence(raw))
    return ({'format': 'ex41-map64-stand-map-error-record-only/1',
             'decision_use': 'none_record_only',
             'definition': 'mean of per-environment step means and maximum per-environment cell maximum, centimeters',
             'map64': map_summary, 'stand': stand_summary}, refs)


def immutable(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False)+'\n').encode('utf-8')
    if path.exists():
        if path.read_bytes() != data: raise ValueError(f'immutable receipt conflict: {path}')
        return
    # Publish a complete JSON, not a partially visible runtime score.
    # A dead publisher may leave an old .pending. Preserve it, but never reuse
    # its pathname or let it block a subsequent complete atomic publication.
    temp = path.with_name(path.name+'.pending.'+uuid.uuid4().hex)
    with temp.open('xb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    if path.exists(): raise ValueError(f'concurrent publisher: {path}')
    temp.rename(path)


def _raw_path(folder, row):
    name = row.get('raw_file')
    if not isinstance(name, str) or Path(name).name != name or not name.endswith('.npz'):
        raise ValueError('raw NPZ must be a local basename')
    path = folder/name
    if sha256(path) != row.get('raw_sha256'): raise ValueError('raw NPZ SHA differs')
    return path


def measure_w57(path, checkpoint, cfg):
    """Recompute accumulated yaw from actual NPZ; never substitute wrapped yaw."""
    path = Path(path); data = read(path)
    require_dr_off_document(data, where=str(path))
    it = int(checkpoint.stem.split('_')[-1])
    if (data.get('schema') != 'foothold-axis-v2/1' or data.get('suite') != 'W57-v2'
        or data.get('checkpoint_sha256') != sha256(checkpoint) or data.get('checkpoint_iter') != it
        or data.get('envs') != 64 or data.get('steps') != cfg['map_steps']
        or data.get('fixed_level') != 2 or data.get('eval_seed') != cfg['eval_seed']
        or set(data.get('modes', {})) != set(MODES)):
        raise ValueError('W57 checkpoint/conditions differ')
    expected = {s['name'] for s in case_specs()}; metrics = {}; refs = [evidence(path)]
    for mode in MODES:
        if set(data['modes'][mode]) != expected: raise ValueError('W57 cases incomplete')
        metrics[mode] = {}
        for name, row in data['modes'][mode].items():
            raw = _raw_path(path.parent, row); refs.append(evidence(raw))
            with np.load(raw, allow_pickle=False) as z:
                if z['yaw'].shape != (cfg['map_steps'], 64) or z['alive'].shape != z['yaw'].shape:
                    raise ValueError('W57 raw shape differs')
                stats = yaw_accumulation(z['start_yaw'], z['yaw'], z['alive'])
            per = row.get('per_env', [])
            if len(per) != 64 or sorted(r['env'] for r in per) != list(range(64)):
                raise ValueError('W57 per-env coverage differs')
            for r in per:
                i = r['env']
                for field, calc in (('yaw_signed_accum_rad', stats['signed_rad'][i]),
                                    ('yaw_absolute_accum_rad', stats['absolute_rad'][i])):
                    value = r.get(field)
                    if (not np.isfinite(calc) and value is not None) or (np.isfinite(calc) and
                        (type(value) not in (float, int) or not math.isclose(value, float(calc), abs_tol=1e-6))):
                        raise ValueError('W57 accumulated yaw disagrees with NPZ')
            metrics[mode][name] = {'alive_at_end': row['alive_at_end'],
                'signed_accum_median_rad': finite_median(stats['signed_rad']),
                'absolute_accum_median_rad': finite_median(stats['absolute_rad']),
                'wrapped_final_median_rad': finite_median(stats['final_minus_start_wrapped_rad']),
                'per_env': copy.deepcopy(per)}
    return metrics, refs


def measure_w78(path, checkpoint, *, selected_cases=None):
    path = Path(path); data = read(path)
    require_dr_off_document(data, where=str(path))
    if (data.get('schema') != 'foothold-terrain-skill-v2/1' or data.get('state') != 'done'
        or data.get('checkpoint_sha256') != sha256(checkpoint)
        or data.get('checkpoint_iter') != int(checkpoint.stem.split('_')[-1])
        or data.get('envs') != 64 or set(data.get('modes', {})) != set(MODES)
        or data.get('levels') != [2, 5] or data.get('start_angles_deg') != [0, 30, 60, 90]):
        raise ValueError('W78 v2 checkpoint/conditions/complete state differ')
    cases = W78_CASES if selected_cases is None else tuple(selected_cases)
    if cases not in (W78_CASES, W78_PERIODIC_SIDE_CASES):
        raise ValueError('W78 case selection is not full or the approved periodic side pair')
    expected = {f'L{level}_a{angle:03d}_{name}' for level in (2, 5)
                for angle in (0, 30, 60, 90) for name in cases}
    if data.get('case_selection') is not None and tuple(data['case_selection']) != cases:
        raise ValueError('W78 case-selection receipt differs')
    refs = [evidence(path)]; assignments = {}; summary = {}
    for mode in MODES:
        if set(data['modes'][mode]) != expected:
            expected_total = 240 if cases == W78_CASES else 48
            raise ValueError(f'W78 v2 requires {expected_total} combinations per mode')
        summary[mode] = {}
        for name, row in data['modes'][mode].items():
            key = (row['level'], row['stair_start_angle_deg'])
            if name != f'L{key[0]}_a{key[1]:03d}_{row["case"]}': raise ValueError('W78 combination identity differs')
            assignment = row['terrain_assignment_sha256']
            if key in assignments and assignments[key] != assignment: raise ValueError('W78 map modes have different tiles')
            assignments[key] = assignment
            tiles, per = row['terrain_tiles'], row['per_env']
            if (len(tiles) != 64 or sorted(t['env'] for t in tiles) != list(range(64))
                or any(t['level'] != key[0] for t in tiles) or len(per) != 64):
                raise ValueError('W78 env coverage differs')
            raw = _raw_path(path.parent, row); refs.append(evidence(raw))
            summary[mode][name] = {'by_terrain_kind': row['by_terrain_kind'], 'per_env': per}
    # Preserve all signed raw ratios including >1; symmetry is a separate field.
    ratios = data.get('w78_min_lr_ratio')
    expected_ratios = {f'L{level}_a{angle:03d}_{mode}_{kind}' for level in (2, 5)
                       for angle in (0, 30, 60, 90) for mode in MODES
                       for kind in ('pyramid_stairs', 'pyramid_stairs_inv')}
    if not isinstance(ratios, dict) or set(ratios) != expected_ratios:
        raise ValueError('W78 left/right ratio cells incomplete')
    for row in ratios.values():
        l, r, m = row.get('left'), row.get('right'), row.get('min_lr_ratio')
        if l is None or r is None:
            if m is not None: raise ValueError('W78 missing side cannot have ratio')
        elif (any(type(v) not in (int, float) or not math.isfinite(v) for v in (l, r, m))
              or not math.isclose(m, min(l, r), abs_tol=1e-12)):
            raise ValueError('W78 signed movement ratio differs')
    return {'cells': summary, 'min_lr_ratio_by_cell': ratios}, refs


def collect(checkpoint, stage, bundle, plan, eval_config=DEFAULT_CONFIG, *, w57_path=None, w78_path=None,
            periodic_w78_path=None,
            w86_path=None, snapshot_dir=None, include_auxiliary=True):
    """Replay actual evaluation files. Each missing component stays explicit."""
    checkpoint, bundle = Path(checkpoint).resolve(strict=True), Path(bundle)
    cfg = config(eval_config)
    row = {'format':'foothold-ex41-score/1', 'iteration':int(checkpoint.stem.split('_')[-1]),
           'stage_id':stage, 'checkpoint_path':str(checkpoint), 'checkpoint_sha256':sha256(checkpoint),
           'parent_sha256':plan.parent_sha256, 'baseline_checkpoint_sha256':plan.parent_sha256,
           'schedule_sha256':plan.effective_sha256, 'created_at':datetime.now(timezone.utc).isoformat(),
           'maintenance_pass':False, 'stage_pass':False, 'safety_stop':False,
           'metrics':{}, 'evidence':[], 'components':{},
           'graduation_status':'not_judged_separate_approved_spec_required'}
    if stage not in {s.id for s in plan.stages}: raise ValueError('unknown EX41 stage')
    try:
        stands = {m:bundle/f'stand_{m}'/'stand.json' for m in MODES}
        row = enrich_score_metrics(row, bundle/'map64/map_modes.json', stands, plan, score_config_path=eval_config)
        try:
            map_stand_error, map_stand_refs = map64_stand_error_record_only(
                bundle/'map64/map_modes.json', stands)
            row['metrics']['map64_stand_map_error_record_only'] = map_stand_error
            row['evidence'].extend(ref for ref in map_stand_refs if ref not in row['evidence'])
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
            row['metrics']['map64_stand_map_error_record_only'] = {
                'format': 'ex41-map64-stand-map-error-record-only/1',
                'decision_use': 'none_record_only', 'state': 'unavailable',
                'reason': f'{type(exc).__name__}: {exc}',
            }
        try:
            map_error, map_error_refs = eval_pred_map_error_record_only(
                bundle/'map64/map_modes.json')
            row['metrics']['eval_pred_map_error_record_only'] = map_error
            row['evidence'].extend(ref for ref in map_error_refs if ref not in row['evidence'])
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
            row['metrics']['eval_pred_map_error_record_only'] = {
                'format': 'ex41-eval-pred-map-error-record-only/1',
                'decision_use': 'none_record_only',
                'state': 'unavailable',
                'reason': f'{type(exc).__name__}: {exc}',
            }
        row['components']['maintenance_stand'] = 'complete'
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        row['components']['maintenance_stand'] = f'HOLD: {type(exc).__name__}: {exc}'
    if include_auxiliary:
        for label, path, function in (
            ('w57', w57_path or bundle/'axis_v2/axis_v2.json', lambda p:measure_w57(p, checkpoint, cfg)),
            ('w78_v2', w78_path or bundle/'w78_v2/terrain_skill_v2.json', lambda p:measure_w78(p, checkpoint))):
            if auxiliary_pending_during_bundle(bundle, path):
                row['components'][label] = 'pending: evaluation bundle has not published the auxiliary result yet'
                continue
            try:
                metrics, refs = function(path)
                json.dumps(metrics,allow_nan=False)  # Auxiliary NaN cannot poison the maintenance row.
                row['metrics'][label] = metrics; row['evidence'].extend(refs)
                row['components'][label] = 'complete'
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
                row['components'][label] = f'HOLD: {type(exc).__name__}: {exc}'
    else:
        row['components']['w57'] = 'deferred_until_stage_end'
        row['components']['w78_v2'] = 'deferred_until_stage_end'
    if periodic_w78_path is not None:
        try:
            metrics, refs = measure_w78(periodic_w78_path, checkpoint,
                                        selected_cases=W78_PERIODIC_SIDE_CASES)
            json.dumps(metrics, allow_nan=False)
            row['metrics']['w78_v2_periodic_sides'] = metrics
            row['evidence'].extend(refs)
            row['components']['w78_v2_periodic_sides'] = 'complete'
            map_doc = read(bundle/'map64/map_modes.json')
            require_dr_off_document(map_doc)
            row['metrics']['critic_mirror_symmetry'] = combine(
                map_pairs(map_doc), metrics.get('min_lr_ratio_by_cell'))
            row['components']['critic_mirror_symmetry'] = 'complete'
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
            row['components']['w78_v2_periodic_sides'] = f'HOLD: {type(exc).__name__}: {exc}'
            row['components']['critic_mirror_symmetry'] = 'HOLD: periodic W78 symmetry evidence unavailable'
    elif not include_auxiliary:
        row['components']['w78_v2_periodic_sides'] = 'missing_periodic_result'
    if w86_path is not None:
        try:
            row = enrich_training_metrics(row, w86_path, snapshot_dir=snapshot_dir)
            row['components']['training_metrics'] = 'complete'
        except (OSError, ValueError, TypeError, KeyError) as exc:
            row['components']['training_metrics'] = f'HOLD: {type(exc).__name__}: {exc}'
    else:
        row['components']['training_metrics'] = 'unavailable_in_EX40_replay'
    if include_auxiliary:
        try:
            map_doc=read(bundle/'map64/map_modes.json')
            require_dr_off_document(map_doc)
            w78=row['metrics'].get('w78_v2',{}).get('min_lr_ratio_by_cell')
            row['metrics']['critic_mirror_symmetry'] = combine(map_pairs(map_doc),w78)
            row['components']['critic_mirror_symmetry'] = 'complete' if w78 is not None else 'partial_missing_w78'
        except (OSError,ValueError,RuntimeError,TypeError,KeyError) as exc:
            row['components']['critic_mirror_symmetry'] = f'HOLD: {type(exc).__name__}: {exc}'
    elif periodic_w78_path is None:
        row['components']['critic_mirror_symmetry'] = 'deferred_until_stage_end_w78'
    # Lead 19:5x: map64 + three stand modes alone produce maintenance 26 and
    # record 39. Missing auxiliary W57/W78/U10 is not a maintenance HOLD.
    row['evaluation_scope'] = ('maintenance_39_and_periodic_w78_sides; graduation_not_judged'
                               if periodic_w78_path is not None else
                               'maintenance_26_and_stand_only; graduation_not_judged')
    row['auxiliary_missing'] = [k for k,v in row['components'].items()
                                if k!='maintenance_stand' and v!='complete'
                                and not str(v).startswith('deferred_until_stage_end')
                                and v != 'missing_periodic_result']
    required_complete = row['components']['maintenance_stand'] == 'complete'
    if periodic_w78_path is not None:
        required_complete = required_complete and row['components'].get('w78_v2_periodic_sides') == 'complete'
    row['evaluation_state'] = 'complete' if required_complete else 'HOLD'
    if row['evaluation_state'] == 'HOLD':
        row['partial_metrics'] = row['metrics']; row['metrics'] = {}
        row['maintenance_pass'] = False  # reader rejects missing stand, creates latest-invalid tombstone.
    json.dumps(row, allow_nan=False)
    return row


def resolve_auxiliary_path(root, iteration, filename):
    """Resolve an auxiliary file from a stage root, bundle root, or phase root."""
    root = Path(root)
    if root.is_file():
        return root
    phase = 'axis_v2' if filename == 'axis_v2.json' else 'w78_v2'
    candidates = (root/f'model_{iteration}'/filename, root/filename,
                  root/phase/filename)
    return next((path for path in candidates if path.is_file()), candidates[0])


def auxiliary_pending_during_bundle(bundle, path):
    """A missing auxiliary artifact is pending, not a FileNotFound HOLD, while its bundle runs."""
    if Path(path).is_file():
        return False
    try:
        receipt = read(Path(bundle) / 'eval_receipt.json')
    except (OSError, ValueError, TypeError):
        return False
    return receipt.get('state') == 'running'


def stage_at(run, iteration, plan):
    rows = []
    text = (run/'ex41_application.jsonl').read_text(encoding='utf-8-sig')
    lines = text.splitlines()
    if text and not text.endswith('\n'): lines = lines[:-1]  # append in progress
    for line in lines:
        if not line.strip(): continue
        r = json.loads(line)
        if r.get('format') == 'foothold-ex41-application/1' and r.get('status') == 'applied' and r['iteration'] <= iteration:
            rows.append(r)
    if not rows: raise ValueError('actual applied EX41 stage receipt missing')
    r = max(rows, key=lambda d:d['iteration'])
    if r['parent_update'] != plan.parent_update or r['stage_after'] not in {s.id for s in plan.stages}:
        raise ValueError('actual EX41 stage identity differs')
    if r.get('after', {}).get('stage_id') != r['stage_after']:
        raise ValueError('actual EX41 readback stage differs')
    return r['stage_after']


def rehearsal_schedule(run):
    path = Path(run) / 'ex41_reports' / 'rehearsal_schedule.json'
    if not path.is_file():
        return None
    row = read(path)
    if row.get('format') != 'foothold-ex41-short-stage-rehearsal/1':
        raise ValueError('short-stage rehearsal schedule format differs')
    from foothold_s2.scripts.ex41_rehearsal_schedule import parse_stage_updates
    updates = tuple(row.get('stage_updates', ()))
    if parse_stage_updates(','.join(str(value) for value in updates)) != updates:
        raise ValueError('short-stage rehearsal table differs')
    injection_count = row.get('inject_measurement_failure_count', 1)
    if type(injection_count) is not int or not 1 <= injection_count <= MAX_TECHNICAL_MEASUREMENT_ATTEMPTS:
        raise ValueError('short-stage measurement failure injection count is invalid')
    return row


def plan_for_run(table, run):
    schedule = rehearsal_schedule(run)
    if schedule is None:
        return load_plan(table, arm='B')
    from foothold_s2.scripts.ex41_rehearsal_schedule import boundary_updates
    from foothold_s2.scripts.ex41_startup import configure_stage_rehearsal_plan
    plan = load_plan(table, arm='B', smoke_boundaries=boundary_updates(tuple(schedule['stage_updates'])))
    configure_stage_rehearsal_plan(plan, tuple(schedule['stage_updates']))
    return plan


def eval_config_for_run(run, default):
    schedule = rehearsal_schedule(run)
    if schedule is None:
        return Path(default).resolve()
    path = Path(schedule.get('eval_config_path', '')).resolve(strict=True)
    root = Path(run).resolve()
    if root not in path.parents:
        raise ValueError('rehearsal evaluation config escaped its run folder')
    return path


def initial_state(run, table, eval_config):
    effective_eval_config = eval_config_for_run(run, eval_config)
    return {'format':'foothold-ex41-score-watch/1', 'run_dir':str(Path(run).resolve()),
            'table_sha256':sha256(table), 'eval_config_sha256':sha256(effective_eval_config),
            'done':{}, 'stage_end_auxiliary':{}, 'measurement_attempts':{},
            'measurement_failures':{}, 'measurement_gaps':{},
            'rehearsal_injected_failures':{}, 'rehearsal_injected_failure_counts':{}}


def candidates(run, plan, *, on_error=None):
    found = []
    short = rehearsal_schedule(run)
    scheduled = set()
    if short is not None:
        total = 0
        for duration in short['stage_updates']:
            total += int(duration)
            scheduled.add(total)
    for p in run.glob('model_*.pt'):
        m = MODEL.fullmatch(p.name)
        if not m:
            continue
        iteration = int(m[1])
        if (short is not None and iteration in scheduled) or (
                short is None and iteration >= 250 and iteration % 250 == 0):
            found.append((iteration, p, None))
    for path in (run/'final_eval_requests').glob('final_*.json'):
        try:
            r = read(path); original = dict(r); request_id = original.pop('request_id', None)
            cp = r.get('checkpoint', {})
            if not isinstance(cp,dict):raise ValueError('final checkpoint must be an object')
            p = Path(cp.get('path', '')).resolve()
            if (request_id != digest(original) or r.get('format') != 'foothold-ex41-final-eval-request/1'
                or r.get('schedule_sha256') != plan.effective_sha256 or r.get('parent_sha256') != plan.parent_sha256
                or r.get('training_finished') is not True or r.get('graduated') is not False
                or type(cp.get('iteration')) is not int or p != (run/f'model_{cp["iteration"]}.pt').resolve()
                or sha256(p) != cp.get('sha256')
                or r.get('stage_id') not in {stage.id for stage in plan.stages}):
                raise ValueError('final checkpoint request invalid')
        except (OSError,ValueError,TypeError,KeyError) as exc:
            if on_error is None:raise
            on_error(path,exc)
            continue  # Keep the periodic checkpoint, reject only its final designation.
        found = [x for x in found if x[0] != cp['iteration']]
        found.append((cp['iteration'], p, path))
    return sorted(found, key=lambda x:x[0])


def nominal_stage_end_updates(plan):
    """Return configured stage-end estimates for capacity planning only."""
    if not getattr(plan, 'fixed_schedule', None): return ()
    completed = 0
    ends = []
    for stage in plan.stages:
        duration = plan.stage_meta[stage.id].get('maximum_updates')
        if type(duration) is not int or duration <= 0:
            raise ValueError(f'EX41 fixed stage duration is invalid: {stage.id}')
        completed += duration
        ends.append(completed)
    return tuple(ends)


def planned_stage_end_updates(plan):
    """Base planned stage ends, distinct from T0' capacity to the hard cap."""
    if not getattr(plan, 'fixed_schedule', None): return ()
    completed = 0
    ends = []
    for stage in plan.stages:
        duration = plan.stage_meta[stage.id].get('minimum_updates')
        if type(duration) is not int or duration <= 0:
            raise ValueError(f'EX41 planned stage duration is invalid: {stage.id}')
        completed += duration
        ends.append(completed)
    return tuple(ends)


def _runtime_clock_stage_ends(run_dir, plan):
    """Read actual stage transitions from the fixed runtime's Clock receipts."""
    run_dir = Path(run_dir)
    path = run_dir / 'stage_log.jsonl'
    if not path.is_file(): return ()
    from foothold_s2.curriculum.ex41_fixed import Clock, finished_at_boundary

    expected_settings = json.loads(json.dumps(plan.clock_settings, sort_keys=True))
    stage_ids = [stage.id for stage in plan.stages]
    rows = []
    text = path.read_text(encoding='utf-8-sig')
    lines = text.splitlines()
    if text and not text.endswith('\n'): lines = lines[:-1]
    for line in lines:
        if not line.strip(): continue
        row = json.loads(line)
        if row.get('event') == 'fixed_schedule_finished':
            rows.append(row)
        elif isinstance(row.get('schedule_clock'), dict) and row.get('stage') in stage_ids:
            rows.append(row)

    def clock_for(row):
        snapshot = row.get('schedule_clock')
        if not isinstance(snapshot, dict):
            raise ValueError('EX41 runtime Clock receipt settings missing or differ')
        recorded_settings = snapshot.get('settings')
        if recorded_settings is not None and recorded_settings != expected_settings:
            raise ValueError('EX41 runtime Clock receipt settings missing or differ')
        clock = Clock(plan.clock_settings)
        state_fields = ('anchor', 'elapsed', 'paused', 'pause_used', 'recovered',
                        'last_score_iteration', 'frozen_scale', 'extension',
                        'extension_decided')
        for key in state_fields:
            if key not in snapshot: raise ValueError(f'EX41 runtime Clock receipt lacks {key}')
            setattr(clock, key, snapshot[key])
        if (type(clock.anchor) is not int or type(clock.elapsed) is not int
                or type(clock.paused) is not bool or type(clock.pause_used) is not int
                or type(clock.recovered) is not int or type(clock.extension) is not int
                or clock.elapsed < 0 or clock.pause_used < 0 or clock.recovered < 0
                or clock.extension not in (0, clock.settings['extension_updates'])):
            raise ValueError('EX41 runtime Clock receipt state invalid')
        return clock

    ends = []
    prior_stage = None
    clock_rows = {}
    for row in rows:
        iteration = row.get('iteration')
        if type(iteration) is not int or iteration < 1: continue
        if row.get('event') == 'fixed_schedule_finished':
            if row.get('graduated') is not False: raise ValueError('EX41 finish receipt claims graduation')
            finished = clock_rows.get(iteration)
            if finished is None: raise ValueError('EX41 finish receipt lacks same-update Clock state')
            clock, stage = finished
            if (stage != stage_ids[clock.position(iteration)]
                    or not finished_at_boundary(iteration,clock.settings)):
                raise ValueError('EX41 finish receipt differs from actual Clock completion')
            ends.append(iteration - 1)
            continue
        clock = clock_for(row)
        if clock.anchor != iteration:
            raise ValueError('EX41 runtime Clock anchor differs from boundary update')
        position = clock.position(iteration)
        if stage_ids[position] != row['stage']:
            raise ValueError('EX41 runtime stage differs from actual Clock position')
        clock_rows[iteration] = (clock, row['stage'])
        if prior_stage is not None and row['stage'] != prior_stage:
            old_index, new_index = stage_ids.index(prior_stage), stage_ids.index(row['stage'])
            if new_index != old_index + 1:
                raise ValueError('EX41 runtime stage transition skipped or regressed')
            ends.append(iteration - 1)
        prior_stage = row['stage']
    return tuple(dict.fromkeys(ends))


def stage_end_updates(plan, run_dir):
    """Return observed checkpoint updates at actual Clock-driven stage ends.

    Nominal YAML lengths are never a scheduling fallback. A stage end becomes
    eligible only after the runtime publishes the Clock transition receipt.
    """
    if not getattr(plan, 'fixed_schedule', None): return ()
    return _runtime_clock_stage_ends(run_dir, plan)


def due_evaluation_scopes(iteration, plan, run_dir):
    """Use actual Clock stage ends for rehearsal; production remains every 250."""
    if type(iteration) is not int or iteration < 1:
        return ()
    short = rehearsal_schedule(run_dir)
    if short is not None:
        updates = set()
        total = 0
        for duration in short['stage_updates']:
            total += int(duration)
            updates.add(total)
        if iteration not in updates:
            return ()
        # The rehearsal table contains no hold or extension evidence by design,
        # so its cumulative checkpoint table is the complete actual stage-end
        # clock, including the first stage before a transition receipt exists.
        return ('periodic', 'auxiliary')
    elif iteration % 250:
        return ()
    scopes = ['periodic']
    if iteration in stage_end_updates(plan, run_dir):
        scopes.append('auxiliary')
    return tuple(scopes)


def _stage_video_contract():
    """Resolve the fixed scripter producer and deterministic 51-cell contract."""
    source_root = Path(os.environ.get(
        'EX41_STAGE_VIDEO_SOURCE_ROOT',
        'D:/mai-wt/foothold-lab/scripter-ex41-stagevideo')).resolve(strict=True)
    module_path = source_root / 'foothold_s2/eval/ex41_stage_video.py'
    if not module_path.is_file():
        raise RuntimeError('scripter EX41 stage-video contract unavailable')
    pinned = subprocess.run(['git', '-C', str(source_root), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True, check=False)
    if pinned.returncode or pinned.stdout.strip() != '3af5b2057fb138357e6ff656abaeb5d8e2194b24':
        raise ValueError('scripter EX41 stage-video source HEAD differs from G11/P9 pin')
    probe = subprocess.run(
        [sys.executable, '-c',
         'import json; from foothold_s2.eval.ex41_stage_video import stage_cases; print(json.dumps(stage_cases()))'],
        cwd=source_root, capture_output=True, text=True, check=False)
    if probe.returncode:
        raise RuntimeError('scripter stage_cases contract failed: ' + probe.stderr[-500:])
    cases = tuple(tuple(row) for row in json.loads(probe.stdout))
    if len(cases) != 51 or len(set(cases)) != 51:
        raise ValueError('stage video contract must expose 51 unique suite/case/mode rows')
    return source_root, cases


def _stage_video_identity(checkpoint, iteration, stage, suite, case, mode):
    payload = [str(Path(checkpoint).resolve()), int(iteration), str(stage), suite, case, mode]
    return hashlib.sha256(json.dumps(payload, separators=(',', ':')).encode()).hexdigest()


def _stage_video_output(checkpoint):
    checkpoint = Path(checkpoint)
    iteration = int(checkpoint.stem.split('_')[-1])
    pinned = sha256(checkpoint)
    root = Path(os.environ.get('EX41_STAGE_VIDEO_OUT_ROOT',
                               'D:/mai-tmp/runner/ex41_stage_video'))
    return root / f'model_{iteration}_{pinned[:12]}'


def stage_end_queue_specs(checkpoint, target, cfg, *, stage='stage_end', gpu0_training_active=False,
                          table=DEFAULT_TABLE, eval_config=DEFAULT_CONFIG):
    """Build four isolated P2 evaluations and 51 independent P3 video jobs."""
    checkpoint = Path(checkpoint).resolve(strict=True)
    iteration = int(checkpoint.stem.split('_')[-1])
    pinned = sha256(checkpoint)
    base = Path(target) / 'stage_end_auxiliary_eval'
    phase_names = ('axis_v2', 'w78_v2', 'push_ladder', 'a_push_video')
    repo_root = Path(__file__).resolve().parents[1]
    rows = []
    for phase in phase_names:
        phase_out = base / phase
        argv = [sys.executable, '-m', 'foothold_s2.ex41_eval_once',
                '--checkpoint', str(checkpoint), '--out', str(phase_out),
                '--table', str(Path(table).resolve()), '--eval-config', str(Path(eval_config).resolve()),
                '--scope', phase, '--device', 'cuda:1', '--execute']
        kind = 'render' if phase == 'a_push_video' else 'evaluation'
        done_files = [str(phase_out / 'eval_receipt.json')]
        rows.append({
            'id': f'ex41-stage-{iteration}-{pinned[:12]}-{phase}',
            'phase': phase,
            'kind': 'render' if kind == 'render' else 'eval',
            'priority': 3 if kind == 'render' else 2,
            'owner': 'ex41_score_watch',
            'authorization_ref': f'stage-end:{iteration}:{pinned}:{phase}',
            'output_path': str(phase_out), 'done_files': done_files,
            'cwd': str(repo_root),
            'gpu': 1, 'gpu_uuid': 'GPU-315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f',
            'argv': argv,
        })
    source_root, cases = _stage_video_contract()
    video_out = _stage_video_output(checkpoint)
    recorder = source_root / 'foothold_s2/eval/video25/record_c_layer.py'
    composer = source_root / 'foothold_s2/eval/video25/compose_25e_v2style10.py'
    gpu_config = Path(os.environ.get(
        'EX41_GPU_JOBS_CONFIG', 'C:/Users/AI-WS01/s2_lab/gpu_jobs/jobs.json'))
    playlist_root = Path(os.environ.get(
        'EX41_PLAYLIST_ROOT', 'C:/Users/AI-WS01/s2_lab/_playlists'))
    for suite, case, mode in cases:
        video_identity = _stage_video_identity(checkpoint, iteration, stage, suite, case, mode)
        argv = [sys.executable, '-m', 'foothold_s2.eval.ex41_stage_video',
                '--checkpoint', str(checkpoint), '--iteration', str(iteration),
                '--stage-name', str(stage), '--suite', suite, '--case', case,
                '--mode', mode, '--source-root', str(source_root),
                '--recorder', str(recorder), '--composer', str(composer),
                '--python', sys.executable, '--gpu-jobs-config', str(gpu_config),
                '--out', str(video_out), '--playlist-root', str(playlist_root),
                '--device', 'cuda:1']
        done_file = video_out / 'receipts' / f'{video_identity}.json'
        rows.append({
            'id': f'ex41-stage-video-{iteration}-{pinned[:12]}-{suite}-{case}-{mode}-{video_identity[:10]}',
            'phase': f'{suite}:{case}:{mode}',
            'kind': 'render', 'priority': 3, 'owner': 'ex41_score_watch',
            'authorization_ref': f'stage-video:{iteration}:{pinned}:{suite}:{case}:{mode}',
            'output_path': str(video_out), 'done_files': [str(done_file)],
            'cwd': str(source_root), 'gpu': 1,
            'gpu_uuid': 'GPU-315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f',
            'argv': argv,
        })
    return rows


def register_stage_end_queue_jobs(queue_path, specs):
    """Register one-shot jobs through this checkout's dispatcher CLI."""
    module_path = (Path(__file__).resolve().parents[1] / '_out/tools/gpu_jobs/dispatch.py').resolve(strict=True)
    queue_path = Path(queue_path).resolve()
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    registered = []
    for item in specs:
        queue = read_dispatch_queue(queue_path)
        existing = next((row for row in queue['items']
                         if row.get('condition') == item['authorization_ref']), None)
        if existing is None:
            argv = [sys.executable, str(module_path), 'queue', 'add', '--queue', str(queue_path),
                    '--title', item['id'], '--priority', str(item['priority']),
                    '--gpu', str(item['gpu']), '--owner', item['owner'],
                    '--cond', item['authorization_ref'], '--kind', item['kind'],
                    '--argv-json', json.dumps(item['argv']), '--cwd', item['cwd']]
            for done_file in item['done_files']:
                argv.extend(['--done-file', done_file])
            if item.get('needs_approval'):
                argv.append('--needs-approval')
            result = subprocess.run(argv, cwd=str(module_path.parents[3]), capture_output=True,
                                    text=True, check=False)
            if result.returncode:
                raise RuntimeError(f'dispatch queue add rc={result.returncode}: {result.stderr.strip()}')
            queue = read_dispatch_queue(queue_path)
            existing = next((row for row in queue['items']
                             if row.get('condition') == item['authorization_ref']), None)
        if existing is None:
            raise RuntimeError(f"gpu_jobs registration missing after add: {item['id']}")
        registered.append({**existing, 'phase': item['phase']})
    return registered


def read_dispatch_queue(queue_path):
    """Read queue.json using this repository's dispatcher schema."""
    import importlib.util
    module_path = (Path(__file__).resolve().parents[1] / '_out/tools/gpu_jobs/dispatch.py').resolve(strict=True)
    spec = importlib.util.spec_from_file_location('foothold_active_gpu_jobs', module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError('active gpu_jobs module unavailable')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read_queue(str(Path(queue_path).resolve()))


def stage_interval_loads(plan, *, train_seconds_per_update, core_seconds,
                         auxiliary_seconds, periodic_side_seconds=0, checkpoint_stride=250):
    """Estimate stage-local GPU1 demand and nonnegative backlog growth."""
    if (checkpoint_stride <= 0 or train_seconds_per_update <= 0 or core_seconds < 0
            or auxiliary_seconds < 0 or periodic_side_seconds < 0):
        raise ValueError('EX41 schedule time inputs must be positive/nonnegative')
    ends = nominal_stage_end_updates(plan)
    rows = []
    prior_end = 0
    pending = 0.0
    for stage, end in zip(plan.stages, ends):
        span = end - prior_end
        checkpoints = end // checkpoint_stride - prior_end // checkpoint_stride
        periodic_seconds = checkpoints * (core_seconds + periodic_side_seconds)
        eval_seconds = periodic_seconds + auxiliary_seconds
        train_seconds = span * train_seconds_per_update
        pending = max(0.0, pending + eval_seconds - train_seconds)
        rows.append({'stage': stage.id, 'end_update': end, 'updates': span,
                     'core_checkpoints': checkpoints, 'periodic_side_runs': checkpoints,
                     'auxiliary_runs': 1,
                     'periodic_side_seconds_per_checkpoint': periodic_side_seconds,
                     'periodic_seconds': periodic_seconds,
                     'evaluation_seconds': eval_seconds, 'training_seconds': train_seconds,
                     'queue_growth_seconds': pending})
        prior_end = end
    return rows


def stage_end_auxiliary_receipt(checkpoint, stage, core_bundle, w57_path, w78_path,
                                plan, eval_config=DEFAULT_CONFIG, push_ladder_path=None,
                                a_push_video_path=None, stage_video_path=None):
    """Create measurements and explicitly unreviewed G11/P9 stage-video evidence."""
    checkpoint = Path(checkpoint).resolve(strict=True)
    row = {'format': 'foothold-ex41-stage-end-auxiliary/1',
           'iteration': int(checkpoint.stem.split('_')[-1]),
           'checkpoint_sha256': sha256(checkpoint), 'stage_id': stage,
           'state': 'complete', 'components': {}, 'metrics': {}, 'evidence': []}
    cfg = config(eval_config)
    for name, path, measure in (
        ('w57', w57_path, lambda p: measure_w57(p, checkpoint, cfg)),
        ('w78_v2', w78_path, lambda p: measure_w78(p, checkpoint))):
        try:
            metrics, refs = measure(path)
            json.dumps(metrics, allow_nan=False)
            row['metrics'][name] = metrics
            row['evidence'].extend(refs)
            row['components'][name] = 'complete'
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
            row['components'][name] = f'HOLD: {type(exc).__name__}: {exc}'
            row['state'] = 'HOLD'
    if push_ladder_path is not None:
        try:
            push_path = Path(push_ladder_path)
            push = read(push_path)
            if push.get('schema') != 'foothold-ex41-push-ladder-bundle/1' or push.get('state') != 'done':
                raise ValueError('push ladder bundle is not complete')
            if push.get('checkpoint_sha256') != row['checkpoint_sha256']:
                raise ValueError('push ladder checkpoint SHA differs from stage checkpoint')
            children = push.get('children')
            if (push.get('expected_children') != PUSH_LADDER_EXPECTED_CHILDREN
                    or not isinstance(children, list)
                    or len(children) != PUSH_LADDER_EXPECTED_CHILDREN
                    or any(c.get('state') != 'done' for c in children)):
                raise ValueError(f'push ladder must contain all {PUSH_LADDER_EXPECTED_CHILDREN} registered children')
            row['metrics']['push_ladder'] = {
                'command': 'walk_0.5 for flat/random_rough/pyramid_stairs; supplementary stand on flat',
                'maximum_tolerated_by_condition': [
                    {'terrain': c['terrain'], 'map_mode': c['map_mode'], 'command': c['command'],
                     'maximum_tolerated_mps': c['summary']['maximum_tolerated_mps'],
                     'magnitudes': c['summary']['magnitudes']}
                    for c in children],
                'bundle_sha256': sha256(push_path),
                'elapsed_s': push.get('elapsed_s'),
            }
            row['evidence'].append(evidence(push_path))
            row['components']['push_ladder'] = 'complete'
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
            row['components']['push_ladder'] = f'HOLD: {type(exc).__name__}: {exc}'
            row['state'] = 'HOLD'
    try:
        if stage_video_path is None:
            raise ValueError('G11/P9 stage-video receipt root is missing')
        source_root, cases = _stage_video_contract()
        expected = {_stage_video_identity(checkpoint, row['iteration'], stage, suite, case, mode):
                    (suite, case, mode) for suite, case, mode in cases}
        receipt_root = Path(stage_video_path) / 'receipts'
        video_rows = {}
        for receipt_path in receipt_root.glob('*.json'):
            video = read(receipt_path)
            if video.get('checkpoint_sha256') != row['checkpoint_sha256']:
                continue
            if video.get('stage_name') != stage or video.get('iteration') != row['iteration']:
                continue
            identity = video.get('id')
            if identity not in expected:
                raise ValueError('unexpected stage-video receipt identity')
            suite, case, mode = expected[identity]
            video_path = Path(video.get('video', ''))
            if (video.get('schema') != 'foothold-ex41-stage-video/1'
                    or (video.get('suite'), video.get('case'), video.get('map_mode')) != (suite, case, mode)
                    or video.get('source_head') != '3af5b2057fb138357e6ff656abaeb5d8e2194b24'
                    or video.get('video_rule_version') != 'v3.4-D168'
                    or not video_path.is_file()
                    or sha256(video_path) != video.get('video_sha256')):
                raise ValueError(f'G11/P9 video receipt or SHA invalid: {receipt_path.name}')
            video_rows[identity] = (receipt_path, video)
        if set(video_rows) != set(expected):
            raise ValueError(f'G11/P9 expected {len(expected)} unique video receipts, found {len(video_rows)}')
        row['metrics']['stage_video'] = {
            'decision_use': 'record_only', 'acceptance': 'pending_lead_kit_scene_review',
            'source_head': '3af5b2057fb138357e6ff656abaeb5d8e2194b24',
            'count': len(video_rows), 'expected_count': len(expected),
            'receipts': [evidence(pair[0]) for _, pair in sorted(video_rows.items())],
        }
        row['components']['stage_video'] = 'captured_pending_lead_kit_scene_review'
        row['evidence'].extend(evidence(pair[0]) for _, pair in sorted(video_rows.items()))
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        row['components']['stage_video'] = f'HOLD: {type(exc).__name__}: {exc}'
        row['state'] = 'HOLD'
    try:
        from foothold_s2.eval.a_push_video import MODES as A_PUSH_MODES, compare_mode_receipts
        video_dir = Path(a_push_video_path) if a_push_video_path is not None else None
        if video_dir is None:
            raise ValueError('stage-end A-layer video receipt path is missing')
        video_status = compare_mode_receipts(video_dir)
        if video_status.get('state') != 'complete' or set(video_status.get('modes', [])) != set(A_PUSH_MODES):
            raise ValueError('all three A-layer map-mode videos are required')
        video_rows = {mode: read(video_dir / f'{mode}.json') for mode in A_PUSH_MODES}
        for mode, video in video_rows.items():
            if (video.get('schema') != 'foothold-ex41-a-push-video/1'
                    or video.get('map_mode') != mode
                    or video.get('iteration') != row['iteration']
                    or video.get('checkpoint_sha256') != row['checkpoint_sha256']
                    or video.get('cadence') != 'stage_end'
                    or video.get('video_rule_version') != 'v3.4-D168'):
                raise ValueError(f'A-layer {mode} receipt identity or D168 rule differs')
            row['evidence'].append(evidence(video_dir / f'{mode}.json'))
            row['evidence'].append(evidence(Path(video['video'])))
        row['metrics']['a_push_video'] = {
            'decision_use': 'record_only', 'video_rule_version': 'v3.4-D168',
            'group_id': video_status['group_id'],
            'map_modes': {mode: {'outcome': video_rows[mode].get('outcome'),
                                 'video_sha256': video_rows[mode].get('video_sha256')}
                          for mode in A_PUSH_MODES}}
        row['components']['a_push_video'] = 'complete'
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        row['components']['a_push_video'] = f'HOLD: {type(exc).__name__}: {exc}'
        row['state'] = 'HOLD'
    try:
        map_path = Path(core_bundle) / 'map64/map_modes.json'
        map_doc = read(map_path)
        require_dr_off_document(map_doc)
        ratios = row['metrics'].get('w78_v2', {}).get('min_lr_ratio_by_cell')
        if ratios is None:
            raise ValueError('stage-end W78 result unavailable for P3 symmetry')
        row['metrics']['critic_mirror_symmetry'] = combine(map_pairs(map_doc), ratios)
        row['components']['critic_mirror_symmetry'] = 'complete'
        row['evidence'].append(evidence(map_path))
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        row['components']['critic_mirror_symmetry'] = f'HOLD: {type(exc).__name__}: {exc}'
        row['state'] = 'HOLD'
    row['p3_symmetry_source'] = 'stage_end_w78'
    row['p3_symmetry_report'] = {
        'format':'foothold-ex41-p3-stage-end/1',
        'state':row['components']['critic_mirror_symmetry'],
        'checkpoint_iteration':row['iteration'],
        'checkpoint_sha256':row['checkpoint_sha256'],
        'source':'stage_end_w78',
        'metrics':row['metrics'].get('critic_mirror_symmetry'),
    }
    json.dumps(row, allow_nan=False)
    return row


def _publish_stage_end_report(run_dir, sidecar, *, deliver=False):
    """Index the P3 sidecar in the training run and alert through existing channels."""
    from foothold_s2.ex41_ops import _alert, deliver_pending_alerts

    run_dir, sidecar = Path(run_dir), Path(sidecar)
    row = read(sidecar)
    if row.get('format') != 'foothold-ex41-stage-end-auxiliary/1':
        raise ValueError('stage-end report sidecar format differs')
    iteration, checkpoint_sha = row.get('iteration'), row.get('checkpoint_sha256')
    if type(iteration) is not int or not isinstance(checkpoint_sha, str) or len(checkpoint_sha) != 64:
        raise ValueError('stage-end report checkpoint identity invalid')
    p3 = row.get('p3_symmetry_report')
    if not isinstance(p3, dict) or p3.get('checkpoint_iteration') != iteration or p3.get('checkpoint_sha256') != checkpoint_sha:
        raise ValueError('stage-end P3 report identity differs')
    sidecar_ref = evidence(sidecar)
    event_id = digest(['ex41-stage-end-report', iteration, checkpoint_sha, sidecar_ref['sha256']])
    report = {'format':'foothold-ex41-stage-end-report/1', 'event_id':event_id,
              'iteration':iteration, 'stage_id':row.get('stage_id'),
              'checkpoint_sha256':checkpoint_sha, 'sidecar':sidecar_ref,
              'state':row.get('state'), 'p3_symmetry_report':p3}
    report_dir = run_dir / 'ex41_reports'
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f'stage_end_auxiliary_{iteration}_{checkpoint_sha[:12]}.json'
    immutable(report_path, report)
    index_path = report_dir / 'stage_end_auxiliary.jsonl'
    index_rows = []
    if index_path.is_file():
        for line in index_path.read_text(encoding='utf-8-sig').splitlines():
            if line.strip(): index_rows.append(json.loads(line))
    if not any(existing.get('event_id') == event_id for existing in index_rows):
        with index_path.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(report, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n')
            stream.flush(); os.fsync(stream.fileno())
    _alert(report_dir / 'alerts.jsonl', event_id, 'stage_end_auxiliary_report', iteration,
           {'stage_id':row.get('stage_id'), 'checkpoint_sha256':checkpoint_sha,
            'report_path':str(report_path.resolve()), 'report_sha256':sha256(report_path),
            'p3_state':p3.get('state'), 'p3_metrics':p3.get('metrics'),
            'delivery':'existing_orchestration_and_telegram_channels'})
    if deliver: deliver_pending_alerts(run_dir)
    return report


def _publish_stage_end_auxiliary(checkpoint, stage, core_bundle, target, plan, state, *,
                                 eval_config=DEFAULT_CONFIG, execute=False,
                                 replay_root=None, w57_root=None, w78_root=None,
                                 table=DEFAULT_TABLE, deliver_reports=False):
    """Publish W57/W78 after core score publication, without changing that score."""
    checkpoint = Path(checkpoint).resolve(strict=True)
    iteration = int(checkpoint.stem.split('_')[-1])
    pinned = sha256(checkpoint)
    key = f'{iteration}_{pinned}'
    aux_state = state.setdefault('stage_end_auxiliary', {})
    target = Path(target)
    sidecar = target / 'stage_end_auxiliary.json'
    if sidecar.is_file():
        prior = read(sidecar)
        if prior.get('iteration') != iteration or prior.get('checkpoint_sha256') != pinned:
            raise ValueError('stage-end auxiliary sidecar identity differs')
        ref = evidence(sidecar)
        if key in aux_state and aux_state[key] != ref:
            raise ValueError('stage-end auxiliary sidecar SHA differs')
        aux_state[key] = ref
        _publish_stage_end_report(checkpoint.parent, sidecar, deliver=deliver_reports)
        return prior

    if execute and getattr(plan, 'rehearsal_stage_updates', None) is not None:
        rehearsal_receipt = target / 'rehearsal_queue_registration.json'
        if rehearsal_receipt.is_file():
            prior = read(rehearsal_receipt)
            if prior.get('iteration') != iteration or prior.get('checkpoint_sha256') != pinned:
                raise ValueError('rehearsal queue registration identity differs')
            aux_state[key] = evidence(rehearsal_receipt)
            return prior
        queue_path = Path(os.environ.get('EX41_GPU_JOBS_QUEUE', 'D:/mai-tmp/gpu/queue.json'))
        specs = stage_end_queue_specs(checkpoint, target, config(eval_config), stage=stage,
                                      table=table, eval_config=eval_config)
        selected = [next(row for row in specs if row['phase'] == 'axis_v2'),
                    next(row for row in specs if row['kind'] == 'render')]
        for row in selected:
            row['id'] = f"REHEARSAL-{row['id']}"
            row['authorization_ref'] = f"REHEARSAL:{iteration}:{pinned}:{row['phase']}"
            row['needs_approval'] = True
        registered = register_stage_end_queue_jobs(queue_path, selected)
        record = {'format':'foothold-ex41-stage-end-rehearsal-queue/1',
                  'state':'registered_pending_approval','rehearsal':True,
                  'iteration':iteration,'checkpoint_sha256':pinned,'stage':stage,
                  'queue_path':str(queue_path.resolve()),
                  'jobs':[{'id':str(row.get('id')),'title':row.get('title'),
                           'phase':row.get('phase'),'kind':row.get('kind'),
                           'priority':row.get('priority'),'needs_approval':row.get('needs_approval'),
                           'state':row.get('state'),'condition':row.get('condition')}
                          for row in registered]}
        _atomic(rehearsal_receipt, record)
        aux_state[key] = evidence(rehearsal_receipt)
        return record
    if execute:
        # Stage-end work is independently registered in the active GPU board.
        queue_path = Path(os.environ.get(
            'EX41_GPU_JOBS_QUEUE', 'D:/mai-tmp/gpu/queue.json'))
        queue_jobs = state.setdefault('stage_end_queue_jobs', {})
        job_ids = queue_jobs.get(key)
        if job_ids is None:
            specs = stage_end_queue_specs(checkpoint, target, config(eval_config), stage=stage,
                                          table=table,
                                          eval_config=eval_config)
            registered = register_stage_end_queue_jobs(queue_path, specs)
            job_ids = {str(row['id']): row['phase'] for row in registered}
            queue_jobs[key] = job_ids
            return {'state':'queued','iteration':iteration,'checkpoint_sha256':pinned,
                    'jobs':list(job_ids), 'queue_path':str(queue_path)}
        queue_doc = read_dispatch_queue(queue_path)
        jobs = {str(row['id']):row for row in queue_doc['items']}
        statuses = {}
        receipts_dir = target / 'stage_end_receipts'; receipts_dir.mkdir(parents=True, exist_ok=True)
        for job_id, phase in job_ids.items():
            job = jobs.get(job_id)
            if job is None: raise ValueError(f'registered gpu_jobs item disappeared: {job_id}')
            if job['state'] in ('대기', '실행'):
                statuses[phase] = {'state':'pending','job_id':job_id,'queue_state':job['state']}
                continue
            receipt_path = receipts_dir / f'{phase}.json'
            if receipt_path.is_file():
                receipt = read(receipt_path)
            else:
                if phase.startswith(('W57:', 'W80:')):
                    output = _stage_video_output(checkpoint)
                    done_path = Path((job.get('done_files') or [''])[0])
                    eval_receipt = None
                else:
                    output = target / 'stage_end_auxiliary_eval' / phase
                    eval_receipt = output / 'eval_receipt.json'
                    done_path = eval_receipt
                state_value = 'failed' if job['state'] != '끝' else 'done'
                reason = None
                if state_value == 'done':
                    if phase.startswith(('W57:', 'W80:')):
                        if not done_path.is_file():
                            state_value, reason = 'failed', 'queue job ended without stage-video receipt'
                        else:
                            video = read(done_path)
                            if (video.get('schema') != 'foothold-ex41-stage-video/1'
                                    or video.get('checkpoint_sha256') != pinned
                                    or video.get('video_rule_version') != 'v3.4-D168'
                                    or not Path(video.get('video', '')).is_file()
                                    or sha256(Path(video['video'])) != video.get('video_sha256')):
                                state_value, reason = 'failed', 'stage-video receipt or video SHA differs'
                    elif eval_receipt is not None and not eval_receipt.is_file():
                        state_value, reason = 'failed', 'queue job ended without eval_receipt.json'
                    elif eval_receipt is not None:
                        phase_doc = read(eval_receipt)
                        step = phase_doc.get('steps', {}).get(phase, {})
                        if (phase_doc.get('state') != 'done' or step.get('state') != 'done'
                                or phase_doc.get('checkpoint_sha256') != pinned):
                            state_value, reason = 'failed', 'phase receipt is not done'
                else:
                    reason = job.get('log') or job.get('missing') or job.get('rc') or 'queue child failed'
                receipt = {'format':'foothold-ex41-stage-phase/1','iteration':iteration,
                           'checkpoint_sha256':pinned,'phase':phase,'state':state_value,
                           'queue_job_id':job_id,'queue_state':job['state'],'reason':reason,
                           'result_path':str(output.resolve()),'ended_at':job.get('done_at')}
                immutable(receipt_path, receipt)
            statuses[phase] = receipt
        if any(row['state'] == 'pending' for row in statuses.values()):
            return {'state':'queued','iteration':iteration,'checkpoint_sha256':pinned,
                    'components':statuses,'queue_path':str(queue_path)}
        aux_out = target / 'stage_end_auxiliary_eval'
        w57_path = aux_out / 'axis_v2/axis_v2.json'
        w78_path = aux_out / 'w78_v2/terrain_skill_v2.json'
        push_ladder_path = aux_out / 'push_ladder/push_ladder_bundle.json'
        a_push_video_path = aux_out / 'a_push_video'
        stage_video_path = _stage_video_output(checkpoint)
        row = stage_end_auxiliary_receipt(checkpoint, stage, core_bundle, w57_path,
                                          w78_path, plan, eval_config, push_ladder_path,
                                          a_push_video_path, stage_video_path)
        row['phase_receipts'] = statuses
        row['evaluation_bundle'] = str(aux_out.resolve())
        immutable(sidecar, row)
        aux_state[key] = evidence(sidecar)
        _publish_stage_end_report(checkpoint.parent, sidecar, deliver=deliver_reports)
        return row
    else:
        if replay_root is not None:
            aux_bundle = Path(replay_root) / f'model_{iteration}_{pinned[:12]}'
        else:
            aux_bundle = Path(core_bundle)
        w57_path = (resolve_auxiliary_path(w57_root, iteration, 'axis_v2.json')
                    if w57_root else aux_bundle / 'axis_v2/axis_v2.json')
        w78_path = (resolve_auxiliary_path(w78_root, iteration, 'terrain_skill_v2.json')
                    if w78_root else aux_bundle / 'w78_v2/terrain_skill_v2.json')
        push_ladder_path = aux_bundle / 'push_ladder/push_ladder_bundle.json'
        a_push_video_path = aux_bundle / 'a_push_video'

    row = stage_end_auxiliary_receipt(checkpoint, stage, core_bundle, w57_path,
                                      w78_path, plan, eval_config, push_ladder_path,
                                      a_push_video_path, _stage_video_output(checkpoint))
    row['evaluation_bundle'] = str(aux_bundle.resolve())
    immutable(sidecar, row)
    aux_state[key] = evidence(sidecar)
    _publish_stage_end_report(checkpoint.parent, sidecar, deliver=deliver_reports)
    return row


def record_final_error(out_root,state,request,exc):
    """Persist and announce a rejected final request without touching its score."""
    try:ref=evidence(request)
    except OSError:ref={'path':str(Path(request).resolve()),'sha256':None}
    row={'format':'foothold-ex41-final-request-error/1','event':'final_request_rejected',
         'request':ref,'reason':f'{type(exc).__name__}: {exc}',
         'alert':True,'graduated':False,'action':'continue_other_checkpoints; final_completion_pending'}
    key=digest(row)
    dest=out_root/'final_request_errors'/f'error_{key}.json'
    immutable(dest,row)
    errors=state.setdefault('final_request_errors',{})
    if key not in errors:
        print(json.dumps(row,ensure_ascii=True,allow_nan=False),flush=True)
    errors[key]=evidence(dest)


def record_measurement_gap(run, out_root, state, iteration, checkpoint_sha256,
                           failed_attempt_count, *, deliver=False):
    """Record exhausted technical measurements without publishing a score."""
    run, out_root = Path(run).resolve(), Path(out_root).resolve()
    key = f'{iteration}_{checkpoint_sha256}'
    failures = list(state.get('measurement_failures', {}).get(key, ()))
    receipt = {
        'format': 'foothold-ex41-measurement-gap/1',
        'state': 'measurement_gap',
        'measurement_state': 'measurement_gap',
        'judgement_state': 'not_judged',
        'iteration': int(iteration),
        'checkpoint_sha256': checkpoint_sha256,
        'failed_attempt_count': int(failed_attempt_count),
        'max_technical_remeasurements': MAX_TECHNICAL_REMEASUREMENTS,
        'remeasurements_used': max(0, int(failed_attempt_count) - 1),
        'failure_evidence': failures,
        'score_path': None,
        'result_eligible': False,
        'dr_action': 'leave_missing_for_dr_hold_missing_evidence',
        'next_action': 'continue_next_checkpoint',
    }
    gap_path = out_root / 'measurement_gaps' / f'model_{iteration}_{checkpoint_sha256[:12]}.json'
    immutable(gap_path, receipt)
    ref = evidence(gap_path)
    gaps = state.setdefault('measurement_gaps', {})
    previous = gaps.get(key)
    if previous is not None and previous != ref:
        raise ValueError('measurement gap receipt changed')
    gaps[key] = ref
    from foothold_s2.ex41_ops import _alert, deliver_pending_alerts
    event_id = digest(['ex41-measurement-gap', str(run), iteration, checkpoint_sha256])
    _alert(run / 'ex41_reports' / 'alerts.jsonl', event_id, 'p1_measurement_gap', iteration,
           {'checkpoint_sha256': checkpoint_sha256, 'gap_path': str(gap_path),
            'gap_sha256': ref['sha256'], 'failed_attempt_count': int(failed_attempt_count),
            'max_technical_remeasurements': MAX_TECHNICAL_REMEASUREMENTS,
            'result_eligible': False, 'next_action': 'continue_next_checkpoint'})
    if deliver:
        deliver_pending_alerts(run)
    return {'state': 'measurement_gap', **receipt, 'gap_path': str(gap_path),
            'gap_sha256': ref['sha256'], 'event_id': event_id}


def require_final_stage(stage):
    if stage!='T0_prime':raise ValueError('final request stage differs from checkpoint stage')


def final_link_valid(request, previous, ref):
    """Verify a separate late-request link without rewriting a score/attempt."""
    if ref is None:return False
    path=Path(ref['path'])
    if sha256(path)!=ref.get('sha256'):raise ValueError('final link receipt SHA differs')
    link=read(path);req=read(request)
    if (link.get('format')!='foothold-ex41-final-score-link/1'
        or link.get('request_id')!=req['request_id'] or link.get('graduated') is not False
        or link.get('checkpoint')!=req['checkpoint']
        or link.get('attempt_digest')!=digest(previous)
        or link.get('score')!={'path':previous['score_path'],'sha256':previous['score_sha256']}
        or link.get('request')!=evidence(request)):
        raise ValueError('final link identity differs')
    for key in ('score','attempt'):
        if evidence(link[key]['path'])!=link[key]:raise ValueError('final link source SHA differs')
    return True


def link_final_request(out_root,request,previous):
    req=read(request);cp=req['checkpoint'];sha=cp['sha256'];iteration=cp['iteration']
    require_final_stage(previous.get('stage_id'))
    if (previous.get('iteration')!=iteration or previous.get('checkpoint_sha256')!=sha
        or sha256(Path(cp['path']))!=sha):
        raise ValueError('final link checkpoint/stage differs from scored attempt')
    candidates=list(out_root.glob(f'model_{iteration}_{sha[:12]}*/attempt.json'))
    candidates+=list((out_root/'recoveries').glob(f'recovered_{iteration}_{sha[:12]}_*.json'))
    attempts=[p for p in candidates if p.is_file() and read(p)==previous]
    if len(attempts)!=1:raise ValueError('final link original attempt receipt missing or ambiguous')
    row={'format':'foothold-ex41-final-score-link/1','request_id':req['request_id'],
         'checkpoint':cp,'request':evidence(request),'attempt':evidence(attempts[0]),
         'attempt_digest':digest(previous),'score':{'path':previous['score_path'],'sha256':previous['score_sha256']},
         'evaluation_state':previous['state'],'graduated':False}
    path=out_root/'final_links'/f'final_{iteration}_{sha[:12]}_{req["request_id"]}.json'
    immutable(path,row)
    ref=evidence(path);final_link_valid(request,previous,ref)
    return ref


def recover_published_score(score_path, cp, stage, plan, out_root):
    """A published score is the commit point; never recollect or overwrite it.

    Recovery validates the immutable collection link and all evidence. Its new
    receipt preserves the original unfinished attempt as crash evidence.
    """
    row=read(score_path);iteration=int(cp.stem.split('_')[-1]);pinned=sha256(cp)
    if (row.get('format')!='foothold-ex41-score/1' or row.get('iteration')!=iteration
        or row.get('checkpoint_sha256')!=pinned or row.get('stage_id')!=stage
        or row.get('parent_sha256')!=plan.parent_sha256
        or row.get('baseline_checkpoint_sha256')!=plan.parent_sha256
        or row.get('schedule_sha256')!=plan.effective_sha256
        or row.get('evaluation_state') not in ('complete','HOLD')
        or not isinstance(row.get('evidence'),list) or not row['evidence']):
        raise ValueError('published recovery score identity invalid')
    collections=[]
    for ref in row['evidence']:
        if evidence(ref['path'])!=ref:raise ValueError('published recovery evidence SHA differs')
        if Path(ref['path']).name=='collection.json':collections.append(ref)
    if len(collections)!=1:raise ValueError('published recovery collection link missing')
    collected=read(collections[0]['path']);original=dict(row)
    original['evidence']=[e for e in row['evidence'] if e!=collections[0]]
    if original!=collected:raise ValueError('published recovery collection differs')
    receipt={'format':'foothold-ex41-score-attempt/1','state':row['evaluation_state'],
        'iteration':iteration,'checkpoint_sha256':pinned,'stage_id':stage,
        'score_path':str(score_path),'score_sha256':sha256(score_path),
        'final_request_id':row.get('final_request_id'),'mode':'recovery',
        'reason':'published score recovered without recollection or source overwrite'}
    dest=out_root/'recoveries'/f'recovered_{iteration}_{pinned[:12]}_{receipt["score_sha256"][:12]}.json'
    immutable(dest,receipt)
    return receipt


def process_once(run, out_root, score_dir, table, state, *, eval_config=DEFAULT_CONFIG,
                 execute=False, replay_root=None, w57_root=None, w78_root=None,
                 deliver_reports=False, sleep=time.sleep):
    run, out_root, score_dir = (Path(p).resolve() for p in (run, out_root, score_dir))
    eval_config = eval_config_for_run(run, eval_config)
    plan, cfg = plan_for_run(table, run), config(eval_config)
    identity = initial_state(run, table, eval_config)
    if any(state.get(k) != v for k,v in identity.items()
           if k not in ('done', 'stage_end_auxiliary', 'measurement_attempts',
                        'measurement_failures', 'stage_end_queue_jobs',
                        'measurement_gaps', 'rehearsal_injected_failures',
                        'rehearsal_injected_failure_counts')):
        raise ValueError('watcher identity differs')
    state.setdefault('stage_end_auxiliary', {})
    state.setdefault('measurement_attempts', {})
    state.setdefault('measurement_failures', {})
    state.setdefault('measurement_gaps', {})
    if execute:
        manifest = read(run/'manifest.json')
        declared = manifest.get('modes', {}).get('ex41', {})
        if (declared.get('effective_sha256') != plan.effective_sha256
            or declared.get('plan_sha256') != plan.sha256
            or declared.get('parent', {}).get('sha256') != plan.parent_sha256):
            raise ValueError('EX41 manifest plan/parent identity differs')
    # A completed measurement with a negative decision is terminal. An older
    # HOLD without a complete measurement is evidence of a failed collection,
    # so preserve it and reopen that exact checkpoint for remeasurement.
    for key, previous in list(state['done'].items()):
        if sha256(Path(previous['score_path'])) != previous['score_sha256']:
            raise ValueError('prior score changed')
        if execute and previous.get('state') == 'HOLD':
            state['measurement_failures'].setdefault(key, []).append(previous)
            del state['done'][key]
    pending = None
    def reject_final(request,exc):record_final_error(out_root,state,request,exc)
    for iteration, cp, final_request in candidates(run, plan,on_error=reject_final):
        stage_end = 'auxiliary' in due_evaluation_scopes(iteration, plan, run)
        pinned = _manifest_digest(run, iteration)
        if pinned is None:
            pending = {'state':'pending', 'iteration':iteration, 'reason':'manifest_not_committed'}; continue
        key = f'{iteration}_{pinned}'
        if key in state['measurement_gaps']:
            continue
        if key in state['done']:
            previous=state['done'][key]
            if final_request:
                try:
                    require_final_stage(previous.get('stage_id'))
                    request_id=read(final_request)['request_id']
                    if previous.get('final_request_id')!=request_id:
                        ref=state.get('final_links',{}).get(request_id)
                        if not final_link_valid(final_request,previous,ref):
                            if not execute and replay_root is None:
                                return {'state':'dry','action':'link_final_request','iteration':iteration,'request_id':request_id}
                            ref=link_final_request(out_root,final_request,previous)
                            state.setdefault('final_links',{})[request_id]=ref
                            return {'state':'final_request_linked','iteration':iteration,'request_id':request_id,
                                    'link_path':ref['path'],'link_sha256':ref['sha256']}
                except (OSError,ValueError,TypeError,KeyError) as exc:
                    reject_final(final_request,exc)
            if stage_end and key not in state['stage_end_auxiliary']:
                target = out_root/f'model_{iteration}_{pinned[:12]}'
                core_bundle = (Path(replay_root)/f'model_{iteration}_{pinned[:12]}'
                               if replay_root is not None else target/'evaluation')
                _publish_stage_end_auxiliary(
                    cp, previous.get('stage_id') or stage_at(run, iteration, plan),
                    core_bundle, target, plan, state, eval_config=eval_config,
                    execute=execute, replay_root=replay_root,
                    w57_root=w57_root, w78_root=w78_root, table=table,
                    deliver_reports=deliver_reports)
            continue
        if final_request is None and any(r['iteration']==iteration and r['checkpoint_sha256']!=pinned
                                         for r in state['done'].values()):
            raise ValueError('completed non-final checkpoint changed')
        if _stable(cp, cfg['checkpoint_stable_seconds'], sleep) != pinned:
            pending = {'state':'pending', 'iteration':iteration, 'reason':'checkpoint_not_stable'}; continue
        try:
            stage = stage_at(run, iteration, plan)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            pending = {'state':'pending','iteration':iteration,'reason':f'stage_receipt: {exc}'}
            continue
        if final_request:
            try:require_final_stage(stage)
            except ValueError as exc:
                reject_final(final_request,exc)
                final_request=None  # Still measure this periodic checkpoint.
        target = out_root/f'model_{iteration}_{pinned[:12]}'
        if not execute and replay_root is None:
            return {'state':'dry', 'iteration':iteration, 'checkpoint_sha256':pinned,
                    'stage_id':stage, 'auxiliary_due':stage_end,
                    'commands':commands(cp, target/'evaluation', cfg, scope='periodic'),
                    'auxiliary_commands':(commands(cp, target/'stage_end_auxiliary_eval', cfg,
                                                    scope='auxiliary') if stage_end else [])}
        score_path = score_dir/f'score_{iteration}_{pinned[:12]}.json'
        if score_path.is_file():
            published = read(score_path)
            if published.get('evaluation_state') == 'complete':
                recovered=recover_published_score(score_path,cp,stage,plan,out_root)
                state['done'][key]=recovered
                if stage_end:
                    core_bundle = (Path(replay_root)/f'model_{iteration}_{pinned[:12]}'
                                   if replay_root is not None else target/'evaluation')
                    _publish_stage_end_auxiliary(
                        cp, stage, core_bundle, target, plan, state,
                        eval_config=eval_config, execute=execute, replay_root=replay_root,
                        w57_root=w57_root, w78_root=w78_root, table=table,
                        deliver_reports=deliver_reports)
                return {**recovered,'recovered_from_score':True,
                        'measurement_state':'complete','judgement_state':
                        'hold' if published.get('maintenance_pass') is False else 'pass'}
            if not execute:
                return {'format':'foothold-ex41-score-attempt/1','state':'HOLD',
                        'iteration':iteration,'checkpoint_sha256':pinned,
                        'score_path':str(score_path),'score_sha256':sha256(score_path),
                        'measurement_state':'failed_retryable','judgement_state':'not_judged',
                        'replay_only':True}
            # Preserve the original immutable failed-measurement score; publish
            # a versioned retry score after a complete remeasurement.
            failures = state['measurement_failures'].setdefault(key, [])
            ref = evidence(score_path)
            if ref not in failures:
                failures.append(ref)
            state['measurement_attempts'][key] = max(
                int(state['measurement_attempts'].get(key, 0)), len(failures))
        attempt_count = int(state['measurement_attempts'].get(key, 0))
        if execute and attempt_count >= MAX_TECHNICAL_MEASUREMENT_ATTEMPTS:
            return record_measurement_gap(run, out_root, state, iteration, pinned,
                                          attempt_count, deliver=deliver_reports)
        if attempt_count:
            score_path = score_dir/f'score_{iteration}_{pinned[:12]}_retry{attempt_count + 1:02d}.json'
        interrupted = target.exists()
        if interrupted:
            saved = target/'attempt.json'
            saved_state = None
            if saved.is_file():
                r = read(saved)
                saved_state = r.get('state')
                if r.get('checkpoint_sha256') == pinned and r.get('state') == 'complete':
                    if Path(r.get('score_path','')).is_file() and sha256(Path(r['score_path'])) == r.get('score_sha256'):
                        state['done'][key] = r; return {**r, 'recovered_from_receipt':True,
                            'measurement_state':'complete'}
                if execute and r.get('state') == 'running' and type(r.get('pid')) is int:
                    import psutil
                    if psutil.pid_exists(r['pid']):
                        return {'state':'measurement_waiting','iteration':iteration,
                                'reason':'prior evaluator child is still alive','attempt_count':attempt_count}
            if execute:
                if saved_state != 'measurement_retry_pending':
                    attempt_count += 1
                state['measurement_attempts'][key] = attempt_count
                if attempt_count:
                    score_path = score_dir/f'score_{iteration}_{pinned[:12]}_retry{attempt_count + 1:02d}.json'
                target = out_root/f'model_{iteration}_{pinned[:12]}_retry{attempt_count + 1:02d}'
                interrupted = False
            else:
                # Replay-only diagnostics retain the old partial-input signal;
                # they do not claim to have retried a Kit measurement.
                base = out_root/f'model_{iteration}_{pinned[:12]}_interrupted'
                target = base
                suffix = 0
                while target.exists():
                    suffix += 1
                    target = base.with_name(base.name + f'_{suffix:03d}')
        # More than one interrupted directory is possible after repeated deaths.
        # Preserve all of them and use a new receipt directory for the HOLD.
        base=target;index=0
        while target.exists():
            index+=1;target=base.with_name(base.name+f'_{index:03d}')
        target.mkdir(parents=True)
        source = (Path(replay_root)/f'model_{iteration}_{pinned[:12]}') if replay_root else target/'evaluation'
        receipt = {'format':'foothold-ex41-score-attempt/1', 'state':'running', 'iteration':iteration,
                   'checkpoint_sha256':pinned, 'source':str(source), 'mode':'replay' if replay_root else 'execute'}
        _atomic(target/'attempt.json', receipt)
        short = rehearsal_schedule(run)
        if execute and short is not None:
            injected = state.setdefault('rehearsal_injected_failure_counts', {})
            inject_iteration = short.get('inject_measurement_failure_at',
                                         short.get('inject_one_measurement_failure_at'))
            inject_total = int(short.get('inject_measurement_failure_count', 1))
            injected_count = int(injected.get(key, 0))
            if iteration == inject_iteration and injected_count < inject_total:
                target.mkdir(parents=True, exist_ok=True)
                failed_attempt_count = attempt_count + 1
                fail = {'format':'foothold-ex41-score-attempt/1','state':'measurement_retry_pending',
                        'mode':'rehearsal_injected_failure','iteration':iteration,
                        'checkpoint_sha256':pinned,'attempt_count':failed_attempt_count,
                        'injection_index':injected_count + 1,
                        'injection_total':inject_total,
                        'reason':'intentional rehearsal technical failure; no W72 evidence'}
                _atomic(target/'attempt.json', fail)
                state['measurement_attempts'][key] = failed_attempt_count
                state['measurement_failures'].setdefault(key, []).append(evidence(target/'attempt.json'))
                injected[key] = injected_count + 1
                if failed_attempt_count >= MAX_TECHNICAL_MEASUREMENT_ATTEMPTS:
                    return record_measurement_gap(run, out_root, state, iteration, pinned,
                                                  failed_attempt_count, deliver=deliver_reports)
                return {'state':'measurement_retry_pending','measurement_state':'failed_retryable',
                        'judgement_state':'not_judged','iteration':iteration,'checkpoint_sha256':pinned,
                        'attempt_count':failed_attempt_count,
                        'reason':'intentional rehearsal failure injection',
                        'injection_index':injected_count + 1,'injection_total':inject_total,
                        'retry_wait_seconds':cfg['check_interval_seconds']}
        child = None
        if execute and not interrupted:
            child_scope = 'core' if short is not None else 'periodic'
            argv = [sys.executable, '-m', 'foothold_s2.ex41_eval_once', '--checkpoint', str(cp), '--out', str(source),
                    '--table', str(Path(table).resolve()), '--eval-config', str(Path(eval_config).resolve()),
                    '--scope', child_scope, '--execute']
            child = hidden_child(argv, target/'bundle_child')
        periodic_w78 = (source/'w78_v2_sides/terrain_skill_v2.json'
                        if execute and replay_root is None and short is None else None)
        row = collect(cp, stage, source, plan, eval_config,
                      periodic_w78_path=periodic_w78,
                      w86_path=run/'ex41_w86.jsonl' if execute else None,
                      snapshot_dir=target/'training', include_auxiliary=False)
        if child is not None:
            row['evidence'].append(evidence(target/'bundle_child/child.json'))
            if child['rc'] != 0:
                row['components']['evaluation_child'] = f'HOLD rc={child["rc"]}'
                if row['evaluation_state'] != 'HOLD': row['partial_metrics'] = row['metrics']
                row.update(evaluation_state='HOLD', metrics={}, maintenance_pass=False)
        if interrupted:
            row['components']['evaluation_child'] = 'HOLD: prior interrupted replay input preserved'
            if row['evaluation_state'] != 'HOLD': row['partial_metrics'] = row['metrics']
            row.update(evaluation_state='HOLD', metrics={}, maintenance_pass=False,
                       measurement_state='failed_retryable', judgement_state='not_judged')
        if sha256(cp) != pinned or _manifest_digest(run, iteration) != pinned:
            raise ValueError('checkpoint changed during scoring; no score published')
        if final_request:
            row['final_request_id'] = read(final_request)['request_id']
            row['evidence'].append(evidence(final_request))
        # Error receipts are immutable evidence, even with no valid measurement.
        row['measurement_attempt'] = attempt_count + 1
        if execute and row['evaluation_state'] != 'complete':
            row['measurement_state'] = 'failed_retryable'
            row['judgement_state'] = 'not_judged'
            immutable(target/'collection.json', row)
            receipt.update(state='measurement_retry_pending', measurement_state='failed_retryable',
                           iteration=iteration, checkpoint_sha256=pinned,
                           attempt_count=attempt_count + 1,
                           collection_path=str((target/'collection.json').resolve()),
                           collection_sha256=sha256(target/'collection.json'),
                           retry_wait_seconds=cfg['check_interval_seconds'])
            _atomic(target/'attempt.json', receipt)
            state['measurement_attempts'][key] = attempt_count + 1
            state['measurement_failures'].setdefault(key, []).append(evidence(target/'attempt.json'))
            if attempt_count + 1 >= MAX_TECHNICAL_MEASUREMENT_ATTEMPTS:
                return record_measurement_gap(run, out_root, state, iteration, pinned,
                                              attempt_count + 1, deliver=deliver_reports)
            return {'state':'measurement_retry_pending','measurement_state':'failed_retryable',
                    'judgement_state':'not_judged','iteration':iteration,
                    'checkpoint_sha256':pinned,'attempt_count':attempt_count + 1,
                    'retry_wait_seconds':cfg['check_interval_seconds'],
                    'reason':row['components'].get('maintenance_stand','measurement incomplete')}
        row['measurement_state'] = ('complete' if row['evaluation_state'] == 'complete'
                                    else 'failed_retryable')
        row['judgement_state'] = (
            ('hold' if row.get('maintenance_pass') is False else 'pass')
            if row['evaluation_state'] == 'complete' else 'not_judged')
        immutable(target/'collection.json', row)
        row['evidence'].append(evidence(target/'collection.json'))
        immutable(score_path, row)
        receipt.update(state=row['evaluation_state'], stage_id=stage,
                       score_path=str(score_path), score_sha256=sha256(score_path),
                       attempt_count=attempt_count + 1,
                       measurement_state=row['measurement_state'],
                       judgement_state=row['judgement_state'],
                       final_request_id=row.get('final_request_id'))
        _atomic(target/'attempt.json', receipt)
        with (out_root/'score_ledger.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(receipt, ensure_ascii=False, allow_nan=False)+'\n'); f.flush(); os.fsync(f.fileno())
        state['done'][key] = receipt
        if stage_end:
            # Core score is durable before any stage-end W57/W78 child begins.
            _publish_stage_end_auxiliary(
                cp, stage, source, target, plan, state, eval_config=eval_config,
                execute=execute, replay_root=replay_root,
                w57_root=w57_root, w78_root=w78_root, table=table,
                deliver_reports=deliver_reports)
        return receipt
    return pending or {'state':'idle'}


def completion(run, plan, state, *, rehearsal=False):
    """A completed training status alone never means graduation or full scores."""
    run=Path(run)
    path=run/'train_start_status.json'
    if not path.is_file(): return {'state':'waiting_for_training_receipt'}
    training=read(path)
    if training.get('state') not in ('done','failed','stopped_saved'):
        return {'state':'waiting_for_training'}
    errors=[]
    saved=candidates(run,plan,on_error=lambda p,e:errors.append({'path':str(p),'reason':str(e)}))
    if errors:return {'state':'final_request_error','errors':errors,'graduated':False}
    for iteration,cp,request in saved:
        pinned=_manifest_digest(run,iteration)
        key=f'{iteration}_{pinned}'
        result=state['done'].get(key)
        if result is None:
            if key in state.get('measurement_gaps', {}):
                continue
            return {'state':'waiting_for_remaining_scores','iteration':iteration}
        if request and result.get('final_request_id')!=read(request)['request_id']:
            ref=state.get('final_links',{}).get(read(request)['request_id'])
            try:
                require_final_stage(result.get('stage_id'))
                if not final_link_valid(request,result,ref):
                    return {'state':'waiting_for_final_request_score','iteration':iteration}
            except (OSError,ValueError,TypeError,KeyError) as exc:
                return {'state':'final_request_error','iteration':iteration,'reason':str(exc),'graduated':False}
    if training['state']=='done' and not any(request for _,_,request in saved) and not rehearsal:
        return {'state':'waiting_for_final_checkpoint_request'}
    holds=sum(row['state']=='HOLD' for row in state['done'].values())
    gap_keys=sorted(state.get('measurement_gaps', {}))
    if gap_keys:
        return {'state':'complete_with_measurement_gaps','hold_count':holds,
                'measurement_gap_count':len(gap_keys),'measurement_gap_keys':gap_keys,
                'training_state':training['state'],'graduated':False}
    return {'state':'complete_with_hold' if holds or training['state']!='done' else 'complete',
            'hold_count':holds,'training_state':training['state'],'graduated':False}


def acquire_watch_lock(lock):
    """Reclaim only a demonstrably dead watcher, preserving its lock evidence.

    A live/reused PID or unknown owner stays blocked. Never kill a process.
    The caller's out-root is dedicated to this watcher.
    """
    import psutil
    if lock.exists():
        original=lock.read_bytes();owner=json.loads(original)
        pid=owner.get('pid')
        if type(pid) is not int or pid<=0 or psutil.pid_exists(pid):
            raise ValueError('watch lock has a live or unknown owner')
        for path in lock.parent.glob('model_*/bundle_child/child.json'):
            child=read(path)
            if child.get('state')=='running' and psutil.pid_exists(child.get('pid',pid)):
                raise ValueError('previous watcher child is still alive; no overlapping evaluation')
        if lock.read_bytes()!=original:raise ValueError('watch lock changed during dead-owner check')
        archived=lock.with_name('watch.lock.dead.'+uuid.uuid4().hex)
        if archived.parent.resolve()!=lock.parent.resolve():raise ValueError('lock archive escaped output')
        lock.rename(archived)
    with lock.open('x',encoding='utf-8') as f:
        json.dump({'pid':os.getpid(),'started_at':datetime.now(timezone.utc).isoformat()},f)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('run-dir','out-root','score-dir'): p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--table', type=Path, default=DEFAULT_TABLE)
    p.add_argument('--eval-config', type=Path, default=DEFAULT_CONFIG)
    p.add_argument('--once', action='store_true')
    p.add_argument('--execute', action='store_true')
    p.add_argument('--rehearsal-stop', action='store_true',
                   help='In a short-stage rehearsal, exit after all scheduled checkpoints are scored or recorded as gaps')
    p.add_argument('--replay-root', type=Path)
    p.add_argument('--w57-root', type=Path)
    p.add_argument('--w78-root', type=Path)
    a = p.parse_args(argv)
    if a.execute and a.replay_root: p.error('--execute and --replay-root are exclusive')
    if a.rehearsal_stop and rehearsal_schedule(a.run_dir) is None:
        p.error('--rehearsal-stop requires a short-stage rehearsal schedule')
    a.out_root.mkdir(parents=True, exist_ok=True)
    lock = a.out_root/'watch.lock'; owned = False
    try:
        acquire_watch_lock(lock)
        owned = True
        path = a.out_root/'watch_state.json'
        state = read(path) if path.exists() else initial_state(a.run_dir, a.table, a.eval_config)
        while True:
            row = process_once(a.run_dir, a.out_root, a.score_dir, a.table, state, eval_config=a.eval_config,
                               execute=a.execute, replay_root=a.replay_root, w57_root=a.w57_root,
                               w78_root=a.w78_root, deliver_reports=a.execute)
            _atomic(path, state)
            print(json.dumps(row, ensure_ascii=True, allow_nan=False), flush=True)
            if a.once or (not a.execute and a.replay_root is None): return 5 if row['state']=='HOLD' else 0
            end=completion(a.run_dir,plan_for_run(a.table,a.run_dir),state,
                           rehearsal=a.rehearsal_stop)
            if end['state'] in ('complete','complete_with_hold','complete_with_measurement_gaps'):
                _atomic(a.out_root/'watch_completion.json',end)
                return 5 if end['state']=='complete_with_hold' else 0
            time.sleep(config(a.eval_config)['check_interval_seconds'])
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        print(json.dumps({'state':'error','reason':f'{type(exc).__name__}: {exc}'}), flush=True)
        return 2
    finally:
        if owned: lock.unlink(missing_ok=True)


if __name__ == '__main__': raise SystemExit(main())
