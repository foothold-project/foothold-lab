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
PHASES = ('map64', *(f'stand_{m}' for m in MODES), 'axis_v2', 'w78_v2')


def commands(checkpoint, out, cfg):
    """The EX40 measurement sizes are reused, never its stage verdict rules."""
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
             ('w78_v2', 'foothold_s2.eval.eval_map_modes',
              [*maps, '--terrain-skill-v2', '--terrain-levels', '2,5',
               '--stair-start-angles-deg', '0,30,60,90', '--terrain-set', 'default'])]
    return [{'name': name, 'argv': [str(ISAAC_PYTHON), '-m', module, *args,
                                  '--out', str(out/name), '--headless', '--device', 'cuda:1',
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
    }
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
    if name == 'w78_v2' and result.get('state') != 'done':
        return {'state': 'HOLD', 'reason': f'{result_name} state is not done',
                'result_path': str(result_path)}
    return {'state': 'done', 'result_path': str(result_path)}


def reconcile_child_result(name, child, output):
    """A zero process exit cannot override a durable auxiliary HOLD receipt."""
    result = dict(child)
    if result.get('rc') == 0 and name in ('axis_v2', 'w78_v2'):
        artifact = auxiliary_phase_status(name, output)
        if artifact['state'] != 'done':
            result.update(state='HOLD', process_rc=result['rc'], rc=5,
                          reason=artifact['reason'], artifact=artifact)
    return result


def bundle_terminal_status(steps):
    missing = [name for name in ('axis_v2', 'w78_v2')
               if steps.get(name, {}).get('state') != 'done']
    return {'state': 'HOLD' if missing else 'done', 'rc': 5 if missing else 0,
            'auxiliary_missing': missing}


def _evaluate_bundle(checkpoint, out, *, table=DEFAULT_TABLE, eval_config=DEFAULT_CONFIG):
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
           'source_git_head': head, 'device': 'cuda:1', 'eval_config_sha256': sha256(eval_config), 'steps': {}}
    env = dict(os.environ)
    env.pop('CUDA_VISIBLE_DEVICES', None)
    env.update(PYTHONUTF8='1', PYTHONUNBUFFERED='1', PYTHONPATH=str(ROOT),
               CUDA_DEVICE_ORDER='PCI_BUS_ID', KMP_DUPLICATE_LIB_OK='TRUE', OMNI_KIT_ACCEPT_EULA='YES')
    start = time.monotonic()
    _atomic(out/'eval_receipt.json', row)
    try:
        for phase in commands(checkpoint, out, cfg):
            if phase['name']=='w78_v2' and not w78_available:
                row['steps']['w78_v2']={'state':'missing','reason':'W78 v2 parser/implementation not integrated'}
                _atomic(out/'eval_receipt.json',row)
                continue
            prepare_phase_output(phase['argv'])
            result = hidden_child(phase['argv'], out/'children'/phase['name'], env=env)
            result = reconcile_child_result(phase['name'], result, out/phase['name'])
            row['steps'][phase['name']] = result
            _atomic(out/'eval_receipt.json', row)
            if result['rc'] != 0 and phase['name'] not in ('axis_v2','w78_v2'):
                raise RuntimeError(f"EX41 {phase['name']} rc={result['rc']}")
        if sha256(checkpoint) != before: raise ValueError('checkpoint changed during evaluation')
        row.update(bundle_terminal_status(row['steps']))
    except Exception as exc:
        row.update(state='failed', rc=1, reason=f'{type(exc).__name__}: {exc}')
    row['seconds'] = time.monotonic()-start
    _atomic(out/'eval_receipt.json', row)
    return row


def evaluate(checkpoint, out, *, table=DEFAULT_TABLE, eval_config=DEFAULT_CONFIG,
             priority_marker=None):
    """Run the bundle while publishing GPU1 priority to the shared job board."""
    from foothold_s2.eval.ex41_gpu_priority import DEFAULT_MARKER, gpu1_priority

    checkpoint = Path(checkpoint).resolve(strict=True)
    match = re.fullmatch(r'model_(\d+)\.pt', checkpoint.name)
    iteration = int(match.group(1)) if match else 0
    marker_path = DEFAULT_MARKER if priority_marker is None else Path(priority_marker)
    with gpu1_priority(marker_path, job='ex41_evaluation_bundle', iteration=iteration) as owner:
        row = _evaluate_bundle(checkpoint, out, table=table, eval_config=eval_config)
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
    p.add_argument('--execute', action='store_true')
    a = p.parse_args(argv)
    if not a.execute:
        print(json.dumps({'state':'dry', 'commands':commands(a.checkpoint, a.out, config(a.eval_config))}))
        return 0
    result = evaluate(a.checkpoint, a.out, table=a.table, eval_config=a.eval_config,
                      priority_marker=a.priority_marker)
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result['state'] == 'done' else 5


if __name__ == '__main__': raise SystemExit(main())
