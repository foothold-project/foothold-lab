"""EX41 shadow watcher: immutable evaluations, scores and receipts, no training control."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sys
import time

import numpy as np

from foothold_s2.curriculum.continuous import load_plan
from foothold_s2.curriculum.ex41 import digest
from foothold_s2.curriculum.ex41_scoring import enrich_score_metrics, enrich_training_metrics
from foothold_s2.eval.axis_v2_cells import case_specs, yaw_accumulation, finite_median
from foothold_s2.eval.eval_dr_mode import require_dr_off_document
from foothold_s2.ex40_score import config, sha256
from foothold_s2.ex40_score_watch import _atomic, _manifest_digest, _stable
from foothold_s2.ex41_eval_once import DEFAULT_CONFIG, DEFAULT_TABLE, MODES, commands, hidden_child

MODEL = re.compile(r'model_(0|[1-9][0-9]*)\.pt\Z')
W78_CASES = ('stairs_fwd', 'stairs_side_left', 'stairs_side_right', 'stairs_back',
             'stairs_fwd_turn_return', 'stairs_fwd_back_return', 'slope_fwd1.0',
             'flat_fwd1.0', 'flat_fwd1.0_heading', 'stairs_fwd_stop_back')


def read(path):
    row = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(row, dict): raise ValueError(f'JSON object required: {path}')
    return row


def evidence(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': sha256(path)}


def immutable(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False)+'\n').encode('utf-8')
    if path.exists():
        if path.read_bytes() != data: raise ValueError(f'immutable receipt conflict: {path}')
        return
    # Publish a complete JSON, not a partially visible runtime score.
    temp = path.with_suffix('.pending')
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


def measure_w78(path, checkpoint):
    path = Path(path); data = read(path)
    require_dr_off_document(data, where=str(path))
    if (data.get('schema') != 'foothold-terrain-skill-v2/1' or data.get('state') != 'done'
        or data.get('checkpoint_sha256') != sha256(checkpoint)
        or data.get('checkpoint_iter') != int(checkpoint.stem.split('_')[-1])
        or data.get('envs') != 64 or set(data.get('modes', {})) != set(MODES)
        or data.get('levels') != [2, 5] or data.get('start_angles_deg') != [0, 30, 60, 90]):
        raise ValueError('W78 v2 checkpoint/conditions/complete state differ')
    expected = {f'L{level}_a{angle:03d}_{name}' for level in (2, 5)
                for angle in (0, 30, 60, 90) for name in W78_CASES}
    refs = [evidence(path)]; assignments = {}; summary = {}
    for mode in MODES:
        if set(data['modes'][mode]) != expected: raise ValueError('W78 v2 requires 240 combinations')
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
    # Preserve signed ratios including >1. No unapproved scalar aggregation.
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
    return {'cells': summary, 'min_lr_ratio_by_cell': ratios,
            'scalar_observation': 'not_selected_pending_D101_cell_aggregation'}, refs


def collect(checkpoint, stage, bundle, plan, eval_config=DEFAULT_CONFIG, *, w57_path=None, w78_path=None,
            w86_path=None, snapshot_dir=None):
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
        row['components']['maintenance_stand'] = 'complete'
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        row['components']['maintenance_stand'] = f'HOLD: {type(exc).__name__}: {exc}'
    for label, path, function in (
        ('w57', w57_path or bundle/'axis_v2/axis_v2.json', lambda p:measure_w57(p, checkpoint, cfg)),
        ('w78_v2', w78_path or bundle/'w78_v2/terrain_skill_v2.json', lambda p:measure_w78(p, checkpoint))):
        try:
            metrics, refs = function(path)
            row['metrics'][label] = metrics; row['evidence'].extend(refs)
            row['components'][label] = 'complete'
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
            row['components'][label] = f'HOLD: {type(exc).__name__}: {exc}'
    if w86_path is not None:
        try:
            row = enrich_training_metrics(row, w86_path, snapshot_dir=snapshot_dir)
            row['components']['training_metrics'] = 'complete'
        except (OSError, ValueError, TypeError, KeyError) as exc:
            row['components']['training_metrics'] = f'HOLD: {type(exc).__name__}: {exc}'
    else:
        row['components']['training_metrics'] = 'unavailable_in_EX40_replay'
    required = ['maintenance_stand', 'w57', 'w78_v2'] + (['training_metrics'] if w86_path else [])
    row['evaluation_state'] = 'complete' if all(row['components'][k] == 'complete' for k in required) else 'HOLD'
    if row['evaluation_state'] == 'HOLD':
        row['partial_metrics'] = row['metrics']; row['metrics'] = {}
        row['maintenance_pass'] = False  # reader rejects missing stand, creates latest-invalid tombstone.
    json.dumps(row, allow_nan=False)
    return row


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


def initial_state(run, table, eval_config):
    return {'format':'foothold-ex41-score-watch/1', 'run_dir':str(Path(run).resolve()),
            'table_sha256':sha256(table), 'eval_config_sha256':sha256(eval_config), 'done':{}}


def candidates(run, plan):
    found = []
    for p in run.glob('model_*.pt'):
        m = MODEL.fullmatch(p.name)
        if m and int(m[1]) >= 250 and int(m[1]) % 250 == 0: found.append((int(m[1]), p, None))
    for path in (run/'final_eval_requests').glob('final_*.json'):
        r = read(path); original = dict(r); request_id = original.pop('request_id', None)
        cp = r.get('checkpoint', {}); p = Path(cp.get('path', '')).resolve()
        if (request_id != digest(original) or r.get('format') != 'foothold-ex41-final-eval-request/1'
            or r.get('schedule_sha256') != plan.effective_sha256 or r.get('parent_sha256') != plan.parent_sha256
            or r.get('training_finished') is not True or r.get('graduated') is not False
            or type(cp.get('iteration')) is not int or p != (run/f'model_{cp["iteration"]}.pt').resolve()
            or sha256(p) != cp.get('sha256') or r.get('stage_id') != 'T0_prime'):
            raise ValueError('final checkpoint request invalid')
        found = [x for x in found if x[0] != cp['iteration']]
        found.append((cp['iteration'], p, path))
    return sorted(found, key=lambda x:x[0])


def process_once(run, out_root, score_dir, table, state, *, eval_config=DEFAULT_CONFIG,
                 execute=False, replay_root=None, w57_root=None, w78_root=None, sleep=time.sleep):
    run, out_root, score_dir = (Path(p).resolve() for p in (run, out_root, score_dir))
    plan, cfg = load_plan(table, arm='B'), config(eval_config)
    identity = initial_state(run, table, eval_config)
    if any(state.get(k) != v for k,v in identity.items() if k != 'done'): raise ValueError('watcher identity differs')
    if execute:
        manifest = read(run/'manifest.json')
        declared = manifest.get('modes', {}).get('ex41', {})
        if (declared.get('effective_sha256') != plan.effective_sha256
            or declared.get('plan_sha256') != plan.sha256
            or declared.get('parent', {}).get('sha256') != plan.parent_sha256):
            raise ValueError('EX41 manifest plan/parent identity differs')
    # Completed HOLD is a finished attempt, not a stop instruction.
    for previous in state['done'].values():
        if sha256(Path(previous['score_path'])) != previous['score_sha256']:
            raise ValueError('prior score changed')
    pending = None
    for iteration, cp, final_request in candidates(run, plan):
        pinned = _manifest_digest(run, iteration)
        if pinned is None:
            pending = {'state':'pending', 'iteration':iteration, 'reason':'manifest_not_committed'}; continue
        key = f'{iteration}_{pinned}'
        if key in state['done']: continue
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
        target = out_root/f'model_{iteration}_{pinned[:12]}'
        if not execute and replay_root is None:
            return {'state':'dry', 'iteration':iteration, 'checkpoint_sha256':pinned,
                    'stage_id':stage, 'commands':commands(cp, target/'evaluation', cfg)}
        interrupted = target.exists()
        if interrupted:
            saved = target/'attempt.json'
            if saved.is_file():
                r = read(saved)
                if (r.get('checkpoint_sha256') == pinned and Path(r.get('score_path','')).is_file()
                    and sha256(Path(r['score_path'])) == r.get('score_sha256')):
                    state['done'][key] = r; return {**r, 'recovered_from_receipt':True}
            # Never overwrite or rerun an interrupted evaluator. Give it a
            # HOLD tombstone and keep later checkpoints moving.
            target = out_root/f'model_{iteration}_{pinned[:12]}_interrupted'
            if (target/'attempt.json').is_file():
                r=read(target/'attempt.json')
                if (r.get('checkpoint_sha256')==pinned and Path(r.get('score_path','')).is_file()
                    and sha256(Path(r['score_path']))==r.get('score_sha256')):
                    state['done'][key]=r;return {**r,'recovered_from_receipt':True}
        target.mkdir(parents=True)
        source = (Path(replay_root)/f'model_{iteration}_{pinned[:12]}') if replay_root else target/'evaluation'
        receipt = {'format':'foothold-ex41-score-attempt/1', 'state':'running', 'iteration':iteration,
                   'checkpoint_sha256':pinned, 'source':str(source), 'mode':'replay' if replay_root else 'execute'}
        _atomic(target/'attempt.json', receipt)
        child = None
        if execute and not interrupted:
            argv = [sys.executable, '-m', 'foothold_s2.ex41_eval_once', '--checkpoint', str(cp), '--out', str(source),
                    '--table', str(Path(table).resolve()), '--eval-config', str(Path(eval_config).resolve()), '--execute']
            child = hidden_child(argv, target/'bundle_child')
        row = collect(cp, stage, source, plan, eval_config,
                      w57_path=(Path(w57_root)/f'model_{iteration}'/'axis_v2.json') if w57_root else None,
                      w78_path=(Path(w78_root)/f'model_{iteration}'/'terrain_skill_v2.json') if w78_root else None,
                      w86_path=run/'ex41_w86.jsonl' if execute else None, snapshot_dir=target/'training')
        if interrupted:
            row['components']['evaluation_child'] = 'HOLD: prior interrupted attempt preserved'
            if row['evaluation_state'] != 'HOLD': row['partial_metrics'] = row['metrics']
            row.update(evaluation_state='HOLD', metrics={}, maintenance_pass=False)
        if child is not None:
            row['evidence'].append(evidence(target/'bundle_child/child.json'))
            if child['rc'] != 0:
                row['components']['evaluation_child'] = f'HOLD rc={child["rc"]}'
                if row['evaluation_state'] != 'HOLD': row['partial_metrics'] = row['metrics']
                row.update(evaluation_state='HOLD', metrics={}, maintenance_pass=False)
        if sha256(cp) != pinned or _manifest_digest(run, iteration) != pinned:
            raise ValueError('checkpoint changed during scoring; no score published')
        if final_request:
            row['final_request_id'] = read(final_request)['request_id']
            row['evidence'].append(evidence(final_request))
        # Error receipts are immutable evidence, even with no valid measurement.
        immutable(target/'collection.json', row)
        row['evidence'].append(evidence(target/'collection.json'))
        score_path = score_dir/f'score_{iteration}_{pinned[:12]}.json'
        immutable(score_path, row)
        receipt.update(state=row['evaluation_state'], stage_id=stage,
                       score_path=str(score_path), score_sha256=sha256(score_path),
                       final_request_id=row.get('final_request_id'))
        _atomic(target/'attempt.json', receipt)
        with (out_root/'score_ledger.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(receipt, ensure_ascii=False, allow_nan=False)+'\n'); f.flush(); os.fsync(f.fileno())
        state['done'][key] = receipt
        return receipt
    return pending or {'state':'idle'}


def completion(run, plan, state):
    """A completed training status alone never means graduation or full scores."""
    run=Path(run)
    path=run/'train_start_status.json'
    if not path.is_file(): return {'state':'waiting_for_training_receipt'}
    training=read(path)
    if training.get('state') not in ('done','failed','stopped_saved'):
        return {'state':'waiting_for_training'}
    saved=candidates(run,plan)
    for iteration,cp,request in saved:
        pinned=_manifest_digest(run,iteration)
        result=state['done'].get(f'{iteration}_{pinned}')
        if result is None:return {'state':'waiting_for_remaining_scores','iteration':iteration}
        if request and result.get('final_request_id')!=read(request)['request_id']:
            return {'state':'waiting_for_final_request_score','iteration':iteration}
    if training['state']=='done' and not any(request for _,_,request in saved):
        return {'state':'waiting_for_final_checkpoint_request'}
    holds=sum(row['state']=='HOLD' for row in state['done'].values())
    return {'state':'complete_with_hold' if holds or training['state']!='done' else 'complete',
            'hold_count':holds,'training_state':training['state'],'graduated':False}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('run-dir','out-root','score-dir'): p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--table', type=Path, default=DEFAULT_TABLE)
    p.add_argument('--eval-config', type=Path, default=DEFAULT_CONFIG)
    p.add_argument('--once', action='store_true')
    p.add_argument('--execute', action='store_true')
    p.add_argument('--replay-root', type=Path)
    p.add_argument('--w57-root', type=Path)
    p.add_argument('--w78-root', type=Path)
    a = p.parse_args(argv)
    if a.execute and a.replay_root: p.error('--execute and --replay-root are exclusive')
    a.out_root.mkdir(parents=True, exist_ok=True)
    lock = a.out_root/'watch.lock'; owned = False
    try:
        with lock.open('x', encoding='utf-8') as f:
            json.dump({'pid':os.getpid(),'started_at':datetime.now(timezone.utc).isoformat()}, f)
        owned = True
        path = a.out_root/'watch_state.json'
        state = read(path) if path.exists() else initial_state(a.run_dir, a.table, a.eval_config)
        while True:
            row = process_once(a.run_dir, a.out_root, a.score_dir, a.table, state, eval_config=a.eval_config,
                               execute=a.execute, replay_root=a.replay_root, w57_root=a.w57_root, w78_root=a.w78_root)
            _atomic(path, state)
            print(json.dumps(row, ensure_ascii=False, allow_nan=False), flush=True)
            if a.once or not a.execute: return 5 if row['state']=='HOLD' else 0
            end=completion(a.run_dir,load_plan(a.table,arm='B'),state)
            if end['state'] in ('complete','complete_with_hold'):
                _atomic(a.out_root/'watch_completion.json',end)
                return 0 if end['state']=='complete' else 5
            time.sleep(config(a.eval_config)['check_interval_seconds'])
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        print(json.dumps({'state':'error','reason':f'{type(exc).__name__}: {exc}'}), flush=True)
        return 2
    finally:
        if owned: lock.unlink(missing_ok=True)


if __name__ == '__main__': raise SystemExit(main())
