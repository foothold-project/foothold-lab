"""Sequential EX41 evaluation bundle. No Kit import in the coordinator."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from foothold_s2.curriculum.continuous import load_plan
from foothold_s2.ex40_score import config, sha256
from foothold_s2.ex40_score_watch import _atomic

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / 'foothold_s2/curriculum/ex40_score_config.json'
DEFAULT_TABLE = ROOT / 'foothold_s2/curriculum/ex41-fixed5000.yaml'
ISAAC_PYTHON = Path('C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe')
MODES = ('eval_gt', 'probe_prop_only', 'eval_pred')
CORE_PHASES = ('map64', *(f'stand_{m}' for m in MODES))
AUXILIARY_PHASES = ('axis_v2', 'w78_v2', 'push_ladder', 'a_push_video')
PERIODIC_W78_PHASE = 'w78_v2_sides'
PERIODIC_PHASES = (*CORE_PHASES, PERIODIC_W78_PHASE)
PHASES = (*CORE_PHASES, *AUXILIARY_PHASES)
PERIODIC_W78_CASES = 'stairs_side_left,stairs_side_right'
FULL_W78_CASES = ('stairs_fwd', 'stairs_side_left', 'stairs_side_right', 'stairs_back',
                  'stairs_fwd_turn_return', 'stairs_fwd_back_return', 'slope_fwd1.0',
                  'flat_fwd1.0', 'flat_fwd1.0_heading', 'stairs_fwd_stop_back')


def commands(checkpoint, out, cfg, *, scope='all', gpu0_training_markers=None,
             gpu0_training_active=None):
    """The EX40 measurement sizes are reused, never its stage verdict rules."""
    from foothold_s2.eval.ex41_gpu_priority import (
        DEFAULT_GPU1_TRAINING_MARKER, gpu0_training_marker_state,
    )

    active = (gpu0_training_marker_state(gpu0_training_markers)['active']
              if gpu0_training_active is None else bool(gpu0_training_active))
    push_ladder_device = 'cuda:1' if active else 'cuda:0'
    common = ['--task', 'FootholdS2-Go2-S2-SB-v0', '--checkpoint', str(checkpoint),
              '--envs', str(cfg['envs'])]
    maps = [*common, '--modes', ','.join(MODES), '--fixed-terrain',
            '--eval-seed', str(cfg['eval_seed'])]
    rows = [('map64', 'foothold_s2.eval.eval_map_modes',
             [*maps, '--steps', str(cfg['map_steps']), '--command-suite', 'extended', '--commands', 'all'])]
    for mode in MODES:
        rows.append((f'stand_{mode}', 'foothold_s2.eval.ex40_stand_eval',
                     [*common, '--mode', mode, '--seconds', str(cfg['stand_seconds']),
                      '--skip-seconds', str(cfg['stand_skip_seconds']),
                      '--contact-n', str(cfg['stand']['contact_force_n']), '--seed', str(cfg['eval_seed'])]))
    rows += [('axis_v2', 'foothold_s2.eval.eval_map_modes',
              [*maps, '--axis-v2', '--fixed-level', '2', '--terrain-set', 'default',
               '--steps', str(cfg['map_steps'])]),
             (PERIODIC_W78_PHASE, 'foothold_s2.eval.eval_map_modes',
              [*maps, '--terrain-skill-v2', '--terrain-skill-v2-cases', PERIODIC_W78_CASES,
               '--terrain-levels', '2,5', '--stair-start-angles-deg', '0,30,60,90',
               '--terrain-set', 'default']),
             ('w78_v2', 'foothold_s2.eval.eval_map_modes',
              [*maps, '--terrain-skill-v2', '--terrain-levels', '2,5',
               '--stair-start-angles-deg', '0,30,60,90', '--terrain-set', 'default'])]
    iteration_match = re.fullmatch(r'model_(\d+)\.pt', Path(checkpoint).name)
    iteration = int(iteration_match.group(1)) if iteration_match else 0
    rows.append(('push_ladder', 'foothold_s2.eval.ex41_push_ladder_bundle',
                 ['--checkpoint', str(checkpoint), '--checkpoint-iteration', str(iteration),
                  '--task', 'FootholdS2-Go2-S2-SB-v0', '--seed', str(cfg['eval_seed'])]))
    rows.append(('a_push_video', 'foothold_s2.eval.a_push_video', [
        '--source-root', str(ROOT), '--checkpoint', str(checkpoint),
        '--recorder', str(ROOT / 'foothold_s2/eval/record_sol23f.py'),
        '--composer', str(ROOT / 'foothold_s2/eval/video25/compose_25e_v2style10.py'),
        '--python', str(ISAAC_PYTHON),
        '--gpu-jobs-config', str(ROOT / '_out/tools/gpu_jobs/jobs.json'),
        '--c-layer-lock', 'C:/Users/AI-WS01/s2_lab/c_layer_m6000/out/c_layer.lock',
        '--a-layer-marker', 'C:/Users/AI-WS01/s2_lab/c_layer_m6000/priority/A_LAYER_BUSY',
        # This is the target GPU's training marker. GPU0 training does not
        # yield a GPU1 capture; GPU1 training and the GPU1 P1 board still do.
        '--training-marker', str(DEFAULT_GPU1_TRAINING_MARKER),
        '--iteration', str(iteration), '--seed', str(cfg['eval_seed']),
        '--push-seed', str(cfg['eval_seed']), '--cadence', 'stage_end',
    ]))
    selected = {'core': CORE_PHASES, 'periodic': PERIODIC_PHASES,
                'auxiliary': AUXILIARY_PHASES,
                'all': PHASES}.get(scope)
    if selected is None:
        raise ValueError(f'unknown EX41 evaluation scope: {scope}')
    rows = [row for row in rows if row[0] in selected]
    return [{'name': name, 'device': (push_ladder_device if name == 'push_ladder' else 'cuda:1'),
             'argv': [str(ISAAC_PYTHON), '-m', module, *args,
                      '--out', str(out/name), '--headless', '--device',
                      (push_ladder_device if name == 'push_ladder' else 'cuda:1'),
                      '--kit_args=--/UJITSO/datastore/localCachePath=D:/mai-cache/isaacsim-5.1/DerivedDataCache']}
            for name, module, args in rows]


def hidden_child(argv, folder, *, env=None, cwd=ROOT):
    """W71: no inherited Windows standard handle, logs outside fresh Kit out."""
    folder.mkdir(parents=True, exist_ok=False)
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    row = {'argv': list(argv), 'cwd': str(cwd), 'stdin': 'DEVNULL',
           'stdout': str(folder/'stdout.log'), 'stderr': str(folder/'stderr.log'),
           'state': 'running'}
    _atomic(folder/'child.json', row)
    start = time.monotonic()
    try:
        with (folder/'stdout.log').open('wb') as stdout, (folder/'stderr.log').open('wb') as stderr:
            child = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                     stdout=stdout, stderr=stderr, creationflags=flags, close_fds=True)
            row['pid'] = child.pid
            _atomic(folder/'child.json', row)
            row['rc'] = child.wait()
        row['state'] = 'done' if row['rc'] == 0 else 'failed'
    except OSError as exc:
        row.update(rc=-1, state='failed', reason=f'{type(exc).__name__}: {exc}')
    row['seconds'] = time.monotonic()-start
    _atomic(folder/'child.json', row)
    return row


def completed_process_receipt(result, *, seconds):
    """Return receipt fields available from subprocess.run's CompletedProcess.

    CompletedProcess exposes returncode, stdout and stderr, but not the child
    PID. Callers that need a PID must use Popen and record it before waiting.
    """
    rc = result.returncode
    return {'rc': int(rc), 'seconds': float(seconds),
            'state': 'done' if rc == 0 else 'failed'}


def prepare_phase_output(argv):
    """Create a fresh evaluator output directory before its Kit process starts."""
    try:
        output_index = argv.index('--out') + 1
        output = Path(argv[output_index])
    except (ValueError, IndexError) as exc:
        raise ValueError('EX41 evaluator command must provide --out <directory>') from exc
    output.mkdir(parents=True, exist_ok=False)
    return output


def auxiliary_phase_status(name, output):
    """Read the phase's durable result, not only the child process exit code."""
    output = Path(output)
    contracts = {
        'axis_v2': ('axis_v2.json', 'axis_v2.error.json', 'foothold-axis-v2/1'),
        'w78_v2': ('terrain_skill_v2.json', 'terrain_skill_v2.error.json',
                   'foothold-terrain-skill-v2/1'),
        PERIODIC_W78_PHASE: ('terrain_skill_v2.json', 'terrain_skill_v2.error.json',
                             'foothold-terrain-skill-v2/1'),
        'push_ladder': ('push_ladder_bundle.json', 'push_ladder_bundle.error.json',
                        'foothold-ex41-push-ladder-bundle/1'),
    }
    if name == 'a_push_video':
        try:
            from foothold_s2.eval.a_push_video import MODES as A_PUSH_MODES, compare_mode_receipts
            rows = [json.loads((output / f'{mode}.json').read_text(encoding='utf-8-sig'))
                    for mode in A_PUSH_MODES]
            if any(row.get('schema') != 'foothold-ex41-a-push-video/1'
                   or row.get('video_rule_version') != 'v3.4-D168'
                   for row in rows):
                raise ValueError('A-layer receipt schema or D168 video rule differs')
            comparison = compare_mode_receipts(output)
            if comparison.get('state') != 'complete' or len(comparison.get('modes', [])) != 3:
                raise ValueError('A-layer map-mode receipts are incomplete or incompatible')
            return {'state': 'done', 'result_path': str(output), 'modes': comparison['modes'],
                    'group_id': comparison['group_id']}
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
            return {'state': 'HOLD', 'reason': f'A-layer video receipts invalid: {exc}',
                    'result_path': str(output)}
    if name not in contracts:
        return {'state': 'done'}
    result_name, error_name, schema = contracts[name]
    error_path = output / error_name
    if error_path.is_file():
        try:
            error = json.loads(error_path.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as exc:
            return {'state': 'HOLD', 'reason': f'{error_name} unreadable: {exc}'}
        return {'state': 'HOLD', 'reason': str(error.get('reason', 'child error receipt')),
                'error_path': str(error_path)}
    result_path = output / result_name
    if not result_path.is_file():
        return {'state': 'HOLD', 'reason': f'{result_name} absent',
                'result_path': str(result_path)}
    try:
        result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        return {'state': 'HOLD', 'reason': f'{result_name} unreadable: {exc}',
                'result_path': str(result_path)}
    if result.get('schema') != schema:
        return {'state': 'HOLD', 'reason': f'{result_name} schema differs',
                'result_path': str(result_path)}
    if name in ('w78_v2', PERIODIC_W78_PHASE) and result.get('state') != 'done':
        return {'state': 'HOLD', 'reason': f'{result_name} state is not done',
                'result_path': str(result_path)}
    if name == 'push_ladder':
        children = result.get('children')
        expected = 12
        if (result.get('state') != 'done' or result.get('expected_children') != expected
                or not isinstance(children, list) or len(children) != expected
                or any(not isinstance(child, dict) or child.get('state') != 'done' for child in children)):
            return {'state': 'HOLD', 'reason': 'push ladder bundle is incomplete',
                    'result_path': str(result_path)}
    if name in ('w78_v2', PERIODIC_W78_PHASE):
        cases = (set(FULL_W78_CASES) if name == 'w78_v2'
                 else {'stairs_side_left', 'stairs_side_right'})
        selection = result.get('case_selection')
        modes = result.get('modes')
        expected_keys = {f'L{level}_a{angle:03d}_{case}' for level in (2, 5)
                         for angle in (0, 30, 60, 90) for case in cases}
        selection_ok = (isinstance(selection, list) and len(selection) == len(cases)
                        and all(isinstance(value, str) for value in selection)
                        and set(selection) == cases)
        modes_ok = (isinstance(modes, dict)
                    and all(isinstance(modes.get(mode), dict)
                            and set(modes[mode]) == expected_keys for mode in MODES))
        if not (selection_ok and modes_ok):
            coverage = 'full W78' if name == 'w78_v2' else 'periodic W78 side-case'
            return {'state': 'HOLD', 'reason': f'{coverage} coverage differs',
                    'result_path': str(result_path)}
    return {'state': 'done', 'result_path': str(result_path)}


def reconcile_child_result(name, child, output):
    """A zero process exit cannot override a durable auxiliary HOLD receipt."""
    result = dict(child)
    if result.get('rc') == 0 and name in (
            'axis_v2', 'w78_v2', PERIODIC_W78_PHASE, 'push_ladder', 'a_push_video'):
        artifact = auxiliary_phase_status(name, output)
        if artifact['state'] != 'done':
            result.update(state='HOLD', process_rc=result['rc'], rc=5,
                          reason=artifact['reason'], artifact=artifact)
    return result


def bundle_terminal_status(steps, *, scope='all'):
    core_missing = [name for name in CORE_PHASES
                    if steps.get(name, {}).get('state') != 'done']
    auxiliary_missing = [name for name in AUXILIARY_PHASES
                         if steps.get(name, {}).get('state') != 'done']
    if scope == 'auxiliary':
        missing = auxiliary_missing
    elif scope == 'periodic':
        missing = [name for name in PERIODIC_PHASES
                   if steps.get(name, {}).get('state') != 'done']
    elif scope in ('core', 'all'):
        # Auxiliary failures are diagnostic and never block the 26-cell score.
        missing = core_missing
    else:
        raise ValueError(f'unknown EX41 evaluation scope: {scope}')
    return {'state': 'HOLD' if missing else 'done', 'rc': 5 if missing else 0,
            'auxiliary_missing': auxiliary_missing if scope == 'all' else []}


def _evaluate_bundle(checkpoint, out, *, table=DEFAULT_TABLE, eval_config=DEFAULT_CONFIG,
                     scope='all', gpu1_owner=None, gpu0_training_markers=None):
    checkpoint, out = Path(checkpoint).resolve(strict=True), Path(out).resolve()
    plan, cfg = load_plan(table, arm='B'), config(eval_config)
    if not getattr(plan, 'fixed_schedule', None) or out.exists():
        raise ValueError('EX41 fixed plan and fresh evaluation output required')
    if Path(sys.executable).resolve() != ISAAC_PYTHON.resolve():
        raise ValueError('EX41 evaluation requires isaac311 Python')
    dirty = subprocess.check_output(['git', 'status', '--short', '--', 'foothold_s2'], cwd=ROOT, text=True)
    if dirty.strip(): raise ValueError('EX41 evaluator source is not frozen')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    # W78 is auxiliary. Lack of integration must not block map64/stand.
    parser = (ROOT/'foothold_s2/eval/eval_map_modes.py').read_text(encoding='utf-8')
    w78_available=('--terrain-skill-v2' in parser and
                   (ROOT/'foothold_s2/eval/terrain_skill_v2_run.py').is_file())
    out.mkdir(parents=True)
    before = sha256(checkpoint)
    row = {'format': 'foothold-ex41-eval-bundle/1', 'state': 'running',
           'checkpoint': str(checkpoint), 'checkpoint_sha256': before,
           'schedule_sha256': plan.effective_sha256, 'parent_sha256': plan.parent_sha256,
           'source_git_head': head, 'device': 'cuda:1', 'scope': scope,
           'eval_config_sha256': sha256(eval_config), 'steps': {}}
    from foothold_s2.eval.ex41_gpu_priority import gpu0_training_marker_state
    gpu0_state = gpu0_training_marker_state(gpu0_training_markers)
    row['gpu0_training_marker_state'] = gpu0_state
    row['stage_end_push_ladder_device'] = 'cuda:1' if gpu0_state['active'] else 'cuda:0'
    env = dict(os.environ)
    env.pop('CUDA_VISIBLE_DEVICES', None)
    env.update(PYTHONUTF8='1', PYTHONUNBUFFERED='1', PYTHONPATH=str(ROOT),
               CUDA_DEVICE_ORDER='PCI_BUS_ID', KMP_DUPLICATE_LIB_OK='TRUE', OMNI_KIT_ACCEPT_EULA='YES')
    if gpu1_owner is not None:
        env['EX41_PARENT_EVAL_PID'] = str(gpu1_owner['pid'])
        env['EX41_PARENT_EVAL_CREATED_AT'] = str(gpu1_owner['process_created_at'])
    start = time.monotonic()
    _atomic(out/'eval_receipt.json', row)
    try:
        for phase in commands(checkpoint, out, cfg, scope=scope,
                              gpu0_training_active=gpu0_state['active']):
            if phase['name'] in ('w78_v2', PERIODIC_W78_PHASE) and not w78_available:
                row['steps'][phase['name']]={'state':'missing','reason':'W78 v2 parser/implementation not integrated'}
                _atomic(out/'eval_receipt.json',row)
                continue
            prepare_phase_output(phase['argv'])
            result = hidden_child(phase['argv'], out/'children'/phase['name'], env=env)
            result = reconcile_child_result(phase['name'], result, out/phase['name'])
            row['steps'][phase['name']] = result
            _atomic(out/'eval_receipt.json', row)
            if result['rc'] != 0 and (phase['name'] in CORE_PHASES
                                      or scope == 'periodic' and phase['name'] == PERIODIC_W78_PHASE):
                raise RuntimeError(f"EX41 {phase['name']} rc={result['rc']}")
        if sha256(checkpoint) != before: raise ValueError('checkpoint changed during evaluation')
        row.update(bundle_terminal_status(row['steps'], scope=scope))
    except Exception as exc:
        row.update(state='failed', rc=1, reason=f'{type(exc).__name__}: {exc}')
    row['seconds'] = time.monotonic()-start
    _atomic(out/'eval_receipt.json', row)
    return row


def evaluate(checkpoint, out, *, table=DEFAULT_TABLE, eval_config=DEFAULT_CONFIG,
             priority_marker=None, scope='all', gpu0_training_markers=None):
    """Run the bundle while publishing GPU1 priority to the shared job board."""
    from foothold_s2.eval.ex41_gpu_priority import DEFAULT_MARKER, gpu1_priority

    checkpoint = Path(checkpoint).resolve(strict=True)
    match = re.fullmatch(r'model_(\d+)\.pt', checkpoint.name)
    iteration = int(match.group(1)) if match else 0
    marker_path = DEFAULT_MARKER if priority_marker is None else Path(priority_marker)
    with gpu1_priority(marker_path, job='ex41_evaluation_bundle', iteration=iteration) as owner:
        row = _evaluate_bundle(checkpoint, out, table=table, eval_config=eval_config,
                               scope=scope, gpu1_owner=owner,
                               gpu0_training_markers=gpu0_training_markers)
    row['gpu1_priority_marker'] = {
        'path': str(marker_path), 'state': 'cleared', 'owner': owner,
    }
    _atomic(Path(out).resolve()/'eval_receipt.json', row)
    return row


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--table', type=Path, default=DEFAULT_TABLE)
    p.add_argument('--eval-config', type=Path, default=DEFAULT_CONFIG)
    p.add_argument('--priority-marker', type=Path)
    p.add_argument('--gpu0-training-marker', type=Path, action='append', default=None,
                   help='Optional GPU0 training marker path override, repeatable')
    p.add_argument('--scope', choices=('core', 'periodic', 'auxiliary', 'all'), default='all')
    p.add_argument('--execute', action='store_true')
    a = p.parse_args(argv)
    if not a.execute:
        print(json.dumps({'state':'dry', 'scope':a.scope,
                          'commands':commands(a.checkpoint, a.out, config(a.eval_config), scope=a.scope,
                                              gpu0_training_markers=a.gpu0_training_marker)}))
        return 0
    result = evaluate(a.checkpoint, a.out, table=a.table, eval_config=a.eval_config,
                      priority_marker=a.priority_marker, scope=a.scope,
                      gpu0_training_markers=a.gpu0_training_marker)
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result['state'] == 'done' else 5


if __name__ == '__main__': raise SystemExit(main())
