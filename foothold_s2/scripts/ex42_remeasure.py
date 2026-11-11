"""Nine fresh P1 measurements, then the existing W09/W08 -> materialize -> E1F path.

Default is CPU preview. Only --execute can create GPU children. An explicitly bound
1000-update run, its done marker, manifests, immutable source pins and idle GPUs are
required together. Old comparison runs can never launch a stage.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
import fcntl
import hashlib
import json
import os
import shlex
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
UPDATES = (250, 500, 750, 1000)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    def reject(value):
        raise ValueError(f'nonfinite JSON: {value}')
    row = json.loads(Path(path).read_text(encoding='utf-8-sig'), parse_constant=reject)
    if not isinstance(row, dict):
        raise ValueError(f'expected object: {path}')
    return row


def save(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(row, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': sha(path)}


def checked(item):
    path = Path(item['path']).resolve(strict=True)
    if sha(path) != item.get('sha256'):
        raise ValueError(f'SHA differs: {path}')
    return path


def training_done(run):
    run = Path(run).resolve(strict=True)
    status = run / 'train_start_status.json'
    if not status.is_file():
        return None
    row = read(status)
    if row.get('state') in ('failed', 'error'):
        raise ValueError('training failed; cannot evaluate automatically')
    if row.get('state') != 'done':
        return None
    if type(row.get('iter')) is not int or row['iter'] != 1000:
        raise ValueError('done marker is not the requested 1000 updates')
    if not row.get('log_dir') or Path(row['log_dir']).resolve() != run:
        raise ValueError('done marker belongs to a different run')
    manifest = read(run / 'manifest.json')
    args = manifest.get('run', {}).get('cli_args', {})
    if (manifest.get('progress', {}).get('completed_updates') != 1000
            or args.get('max_iterations') != 1000 or args.get('ex42_speed_probe') is not False):
        raise ValueError('manifest is not a completed non-probe 1000-update run')
    return row


def require_free_gpus(uuids, *, query=None):
    from foothold_s2.ex42_eval_split import DISPLAY_PROCESS_NAMES
    if query is None:
        def query():
            return subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_memory,process_name',
                                            '--format=csv,noheader,nounits'], text=True, timeout=20)
    normalize = lambda value: value.lower().removeprefix('gpu-')
    wanted = {normalize(u) for u in uuids}
    if len(wanted) != 2:
        raise ValueError('exactly two distinct GPU UUIDs required')
    for fields in csv.reader(query().splitlines()):
        if not fields:
            continue
        if len(fields) != 4 or not fields[0].strip().isdigit() or not fields[1].strip().startswith('GPU-'):
            raise ValueError('unknown GPU process query row')
        if normalize(fields[1].strip()) in wanted and Path(fields[3].strip()).name not in DISPLAY_PROCESS_NAMES:
            raise ValueError(f'GPU busy: {fields[1].strip()} pid={fields[0].strip()}')


def source_binding(run, training_log=None):
    run = Path(run).resolve(strict=True)
    manifest = read(run / 'manifest.json')
    args = manifest['run']['cli_args']
    plan, approvals = ref(args['ex42_plan']), ref(args['ex42_approvals'])
    startup = read(run / 'startup_receipt.json')
    if startup.get('plan_sha256') != plan['sha256']:
        raise ValueError('actual training plan changed since startup')
    import yaml
    doc = yaml.safe_load(checked(plan).read_text())
    if doc['stage_zero']['approval_sha256'] != approvals['sha256']:
        raise ValueError('actual training approval pin differs')
    result = {'run': str(run), 'plan': plan, 'approvals': approvals, 'manifest': ref(run / 'manifest.json'),
              'startup': ref(run / 'startup_receipt.json')}
    if training_log:
        result['training_log'] = ref(training_log)
    return result


def jobs(request, binding):
    rows = []
    for group, source, iterations in (
            ('parent', {'run': str(Path(request['parent']['path']).parent),
                        'plan': request['evaluation_plan'], 'approvals': request['evaluation_approvals']}, (1000,)),
            ('old', request['old'], UPDATES), ('retrain', binding, UPDATES)):
        for iteration in iterations:
            checkpoint = Path(source['run']) / f'model_{iteration}.pt'
            output = Path(request['output']) / group / f'm{iteration}'
            argv = [request['python'], '-m', 'foothold_s2.ex42_eval_once', '--checkpoint', str(checkpoint),
                    '--sha-from-manifest', '--out', str(output), '--device', 'cuda:1', '--split-device', 'cuda:0',
                    '--eval-seed', '42', '--mesh-dir', request['mesh_dir'], '--expected-mesh-sha256', request['mesh_sha256'],
                    '--p1-plan', source['plan']['path'], '--p1-approvals', source['approvals']['path'],
                    '--p1-stage-id', 'E1', '--evaluation-plan', request['evaluation_plan']['path'], '--execute']
            rows.append({'group': group, 'iteration': iteration, 'checkpoint': str(checkpoint), 'output': str(output),
                         'comparison_only': group != 'retrain', 'argv': argv,
                         'source_plan_sha256': source['plan'].get('sha256')})
    return rows


def friction_readbacks(root, policy_sha):
    paths = [root / 'map64/map_modes.json', root / 'axis_v2/axis_v2.json',
             *[root / f'stand_{mode}/stand.json' for mode in ('eval_gt', 'eval_pred', 'probe_prop_only')],
             root / 'd44/d44_cells.json']
    evidence = []
    for path in paths:
        value = read(path).get('evaluation_friction') or {}
        if value.get('state') != 'verified' or value.get('plan_sha256') != policy_sha:
            raise ValueError(f'missing actual friction readback: {path}')
        robot, terrain = value.get('robot') or {}, value.get('terrain') or []
        if not terrain or not robot.get('shape') or value.get('combine_mode') != 'average':
            raise ValueError(f'empty friction material evidence: {path}')
        for key, expected in (('static', .8), ('dynamic', .6)):
            numbers = [value.get(key), robot.get(key+'_min'), robot.get(key+'_max')]
            numbers += [row.get(key) for row in terrain]
            if any(type(x) not in (int, float) or abs(x-expected) > 1e-6 for x in numbers):
                raise ValueError(f'actual {key} friction differs: {path}')
        if any(row.get('combine_mode') != 'average' for row in terrain):
            raise ValueError(f'actual terrain combine mode differs: {path}')
        evidence.append({'receipt': ref(path), 'readback': value})
    return evidence


def completed_job(job, policy_sha):
    root = Path(job['output'])
    receipt, p1, measured = (read(root / p) for p in ('eval_receipt.json', 'p1_score.json', 'ex42_score.json'))
    checkpoint_sha = job['checkpoint_sha256']
    if (receipt.get('state') != 'done' or p1.get('state') != 'complete'
            or p1.get('judgment') not in ('PASS', 'HOLD', 'FAIL')
            or p1.get('checkpoint_iteration') != job['iteration']
            or any(r.get('checkpoint_sha256') != checkpoint_sha for r in (receipt, p1, measured))
            or any(r.get('evaluation_plan', {}).get('sha256') != policy_sha for r in (receipt, p1))
            or measured.get('maintenance_source_sha256') != policy_sha
            or p1.get('measurement_sha256') != sha(root / 'ex42_score.json')
            or Path(p1.get('measurement', '')).resolve() != (root / 'ex42_score.json').resolve()
            or p1.get('plan_sha256') != job.get('source_plan_sha256')):
        raise ValueError(f'incomplete/mixed measurement: {root}')
    friction = receipt.get('evaluation_friction_requested') or {}
    if friction.get('plan_sha256') != policy_sha or friction.get('static') != 0.8 or friction.get('dynamic') != 0.6:
        raise ValueError('requested common evaluation friction differs')
    if job.get('source_git_head') and receipt.get('source_git_head') != job['source_git_head']:
        raise ValueError('evaluator code HEAD differs')
    from foothold_s2.ex42_gate_checks import validate_ex42_map_score
    validate_ex42_map_score(p1, ['gt', 'pred', 'off'])
    actual_friction = friction_readbacks(root, policy_sha)
    return {'friction_readbacks': actual_friction, 'group': job['group'], 'iteration': job['iteration'], 'comparison_only': job['comparison_only'],
            'checkpoint': ref(job['checkpoint']), 'judgment': p1['judgment'],
            'receipt': ref(root / 'eval_receipt.json'), 'p1': ref(root / 'p1_score.json'),
            'measurement': ref(root / 'ex42_score.json'), 'map64': measured['map64'],
            'cell_judgments': measured.get('cell_judgments'), 'e1_exit': measured.get('e1_exit'),
            'd44_cells': measured.get('d44_cells')}


def comparison(root, results):
    save(root / 'comparison.json', {'state': 'complete', 'count': len(results), 'results': results,
          'note': 'Fresh common-policy measurements. Parent m13000 is comparison-only under E1 evaluation policy; '
                  'local iteration 1000 is not EX-42 training age. HOLD is distinct from a technical failure.'})
    with (root / 'comparison.csv').open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['group', 'local_iteration', 'mode', 'command', 'metric', 'value', 'source', 'source_sha256'])
        for item in results:
            for mode, commands in item['map64'].items():
                for command, metrics in commands.items():
                    for metric, value in metrics.items():
                        if value is None or type(value) in (int, float, bool, str):
                            writer.writerow([item['group'], item['iteration'], mode, command, metric, value,
                                             item['measurement']['path'], item['measurement']['sha256']])
    lines = ['> 분류: 평가', '> 작성: verifier-lx 자동 집계', '> 근거: comparison.json의 파일 SHA',
             '> 요지: 동일 평가 정책의 9개 저장본 원자료 비교', '> 상태: 측정 완료 · 인과 해석 아님',
             '', '# EX-42 공통 정책 재측정', '', '| 구분 | 로컬 회차 | 관문 | 원자료 |', '|---|---:|---|---|']
    lines += [f"| {r['group']} | {r['iteration']} | {r['judgment']} | {r['measurement']['path']} |" for r in results]
    (root / 'comparison.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def validate_request(request):
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if head != request['source_git_head']:
        raise ValueError('request code HEAD changed')
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--', 'foothold_s2'], cwd=ROOT, text=True)
    if dirty.strip():
        raise ValueError('evaluator source is not clean')
    for item in (request['evaluation_plan'], request['evaluation_approvals'], request['parent'], *request['dependencies']):
        checked(item)
    for key in ('plan', 'approvals', 'manifest', 'startup'):
        checked(request['old'][key])


def bridge(request, binding, root, gate_path, *, guard, launch=True):
    gate = read(gate_path)
    if gate.get('state') != 'complete' or gate.get('judgment') != 'PASS':
        return {'state': 'gate_not_passed', 'judgment': gate.get('judgment'), 'training_started': False}
    from foothold_s2.scripts.ex42_flag_baseline_chain import run_chain
    from foothold_s2.scripts.ex42_e1_materialize_evidence import write_evidence
    from foothold_s2.ex42_stage_materialize import materialize
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_auto_authorization import validate_automatic_stage_launch
    from foothold_s2.scripts.ex42_stage_launcher import build
    from foothold_s2.ex42_stage_handoff import start_launcher, register_launched_training
    run = Path(binding['run'])
    checkpoint = run / 'model_1000.pt'
    if (gate.get('stage_id') != 'E1' or gate.get('checkpoint_iteration') != 1000
            or gate.get('checkpoint_sha256') != sha(checkpoint)
            or gate.get('plan_sha256') != binding['plan']['sha256']):
        raise ValueError('only this retrain m1000 can be adopted')
    checked(binding['manifest']); checked(binding['training_log'])
    guard()
    flags = Path(root) / 'flags'
    run_chain(checkpoint, flags, None, plan_path=checked(request['evaluation_plan']),
              mesh_dir=Path(request['mesh_dir']), expected_checkpoint_sha256=sha(checkpoint),
              expected_mesh_sha256=request['mesh_sha256'], e1_gate=Path(gate_path),
              task='FootholdS2-Go2-S2-SB-v0', execute=True, devices=('cuda:0', 'cuda:1'))
    evidence = Path(root) / 'E1F-evidence.json'
    write_evidence(out_path=evidence, source_plan_path=checked(binding['plan']),
                   parent_manifest_path=checked(binding['manifest']), gate_receipt_path=gate_path,
                   training_log_path=checked(binding['training_log']),
                   evaluation_mesh_path=Path(request['mesh_dir']) / 'terrain_mesh.npz',
                   w09_baseline_path=flags / 'w09_baseline.json', evaluation_plan_path=checked(request['evaluation_plan']))
    source = EX42Plan.load(checked(binding['plan']))
    template = EX42Plan.load(checked(request['evaluation_plan']))
    predecessor = next(r for r in source.document['stages'] if r['id'] == 'E1')
    origin = next(row for row in template.document['stages'] if row['id'] == 'E0')['parent']['cumulative_update']
    used = predecessor['parent']['cumulative_update'] + 1000 - origin
    excluded = {'stage_zero_updates': origin - template.document['stage_zero']['parent']['cumulative_update'],
                'discarded_first_e1_updates': 1000, 'discarded_run': request.get('old', {}).get('run')}
    made = materialize(plan=template.path, source_plan=source.path, approvals=checked(request['evaluation_approvals']),
                       target='E1F', parent_manifest=checked(binding['manifest']), gate_receipt=gate_path, evidence=evidence,
                       budget_limit=template.document['training_budget']['maximum_updates'], budget_used=used,
                       budget_basis=template.document['training_budget']['basis'],
                       out=Path(root) / 'E1F-materialized', flag_chain=flags / 'chain_receipt.json')
    proof = validate_automatic_stage_launch(EX42Plan.load(made['plan']), made['approvals'], target_stage='E1F',
                parent_manifest_path=checked(binding['manifest']), gate_receipt_path=gate_path,
                expected_gate_sha256=sha(gate_path))
    env = dict(os.environ, **request['launch_env'], **made['launch_env'], EX42_AUTO_ACTION='next_stage',
               EX42_AUTO_TARGET_STAGE='E1F', EX42_AUTO_PARENT_MANIFEST=binding['manifest']['path'],
               EX42_AUTO_PARENT_CHECKPOINT=str(checkpoint), EX42_AUTO_GATE_RECEIPT=str(gate_path),
               EX42_AUTO_GATE_SHA256=sha(gate_path), ISAAC311_PYTHON=request['python'])
    argv, child_env, summary = build(env, dry_run=True)
    with (Path(root) / 'E1F-dry.log').open('x') as log:
        result = subprocess.run(argv, env=child_env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    save(Path(root) / 'E1F-dry.json', {'argv': argv, 'returncode': result.returncode, 'summary': summary})
    if result.returncode:
        raise ValueError(f'E1F CPU preflight refused: rc {result.returncode}')
    decision = {'action': 'launch', 'state': 'next_stage_authorized', 'target_stage': 'E1F',
                'plan': made['plan'], 'approvals': made['approvals'], 'gate_sha256': sha(gate_path), 'authorization': proof}
    save(Path(root) / 'E1F-adoption.json', {'decision': decision, 'materialized': made,
                                         'budget_used': used, 'budget_origin_cumulative_update': origin,
                                         'excluded_branches': excluded, 'training_started': False})
    if not launch:
        return {'state': 'ready_not_started', 'decision': decision}
    guard()
    guard.release()  # No evaluation marker may outlive the handoff to training.
    # start_launcher supplies immutable plan/gate pins; inject the explicit machine
    # environment through its process factory without changing this supervisor's env.
    def spawn(argv, **kwargs):
        kwargs['env'] = dict(kwargs['env'], **env)
        return subprocess.Popen(argv, **kwargs)
    started = start_launcher(decision, ROOT / 'foothold_s2/scripts/ex42_stage_launcher.sh', root,
                parent_manifest=binding['manifest']['path'], parent_checkpoint=checkpoint,
                gate_receipt=gate_path, popen=spawn)
    registered = register_launched_training(env['GPU_JOBS_QUEUE'], ROOT / '_out/tools/gpu_jobs/dispatch.py',
                pid=started['pid'], log=str(Path(root) / 'next_stage_launcher.log'), title='EX-42 retrain -> E1F')
    return {'state': 'launcher_started', 'launch': started, 'queue': registered,
            'note': 'Process started is not proof that the first update or following stages succeeded.'}


def reserve_queue(queue_path, log_path):
    import datetime
    import importlib.util
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location('ex42_remeasure_dispatch', ROOT / '_out/tools/gpu_jobs/dispatch.py')
    dispatch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dispatch)
    cfg = {'queue': str(queue_path)}
    now = datetime.datetime.now()
    with dispatch.queue_lock(cfg['queue']):
        queue = dispatch.read_queue(cfg['queue'])
        for item in queue['items']:
            if item.get('external'):
                dispatch.settle_external(item, now.timestamp())
            if item.get('state') == '실행' and item.get('gpu') in (0, 1):
                raise ValueError(f"GPU queue still occupied: item {item.get('id')}")
        args = SimpleNamespace(qaction='external', gpu=[0, 1], priority=1, pid=os.getpid(),
                  title='EX-42 nine-checkpoint remeasurement', log=str(log_path), owner='ex42-remeasure',
                  start=(now-datetime.timedelta(minutes=1)).strftime('%m-%d %H:%M'),
                  end=(now+datetime.timedelta(hours=12)).strftime('%m-%d %H:%M'))
        return dispatch._queue_cmd(args, cfg, now.timestamp())


@contextmanager
def admission(request, output):
    """Shared dispatcher reservation plus priority markers, with strict fresh hardware checks."""
    from foothold_s2.eval import ex41_gpu_priority as priority
    from foothold_s2.ex42_eval_once import gpu_identity
    uuids = [gpu_identity(f'cuda:{i}')['gpu_uuid'] for i in (0, 1)]
    lock_path = Path(request['admission_lock'])
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        markers = [*priority.DEFAULT_GPU0_MARKERS, priority.DEFAULT_GPU1_TRAINING_MARKER,
                   priority.DEFAULT_GPU0_EVAL_MARKER, priority.DEFAULT_MARKER]
        if priority.gpu0_training_marker_state(markers)['active']:
            raise ValueError('live/unknown GPU reservation marker')
        require_free_gpus(uuids)
        # CPU supervisor reserves both devices before its first Kit child. This is
        # called only under --execute, never by preview or tests.
        registered = reserve_queue(request['launch_env']['GPU_JOBS_QUEUE'], output / 'batch.log')
        save(output / 'queue-reservation.json', {'result': registered})
        owners = []
        try:
            for path in (priority.DEFAULT_GPU0_EVAL_MARKER, priority.DEFAULT_MARKER):
                owners.append((path, priority.publish_marker(path, job='ex42-remeasure', iteration=1000, run=str(output))))
            def guard():
                if priority.gpu0_training_marker_state([*priority.DEFAULT_GPU0_MARKERS,
                                                      priority.DEFAULT_GPU1_TRAINING_MARKER])['active']:
                    raise ValueError('training marker appeared while waiting')
                require_free_gpus(uuids)
            def release():
                while owners:
                    path, owner = owners.pop()
                    if not priority.clear_marker(path, owner):
                        raise ValueError(f'cannot release own GPU marker: {path}')
            guard.release = release
            yield guard
        finally:
            for path, owner in reversed(owners):
                priority.clear_marker(path, owner)


def notify_hold(output, reason, *, runner=None):
    """One run-inbox notice, with durable delivery evidence. Never writes to a terminal."""
    output = Path(output)
    text = f"({time.strftime('%H:%M')}) [verifier-lx] 재측정 HOLD · {output} · {reason}"
    command = shlex.split(os.environ.get('ORCA_CLI_COMMAND') or 'orca-ide')
    command += ['orchestration', 'send', '--to', 'run:run_5283fa2c059b', '--type', 'status',
                '--subject', text, '--body', text]
    try:
        result = (runner or subprocess.run)(command, capture_output=True, text=True,
                                           stdin=subprocess.DEVNULL, timeout=30)
        receipt = {'sent': result.returncode == 0, 'returncode': result.returncode,
                   'stdout': result.stdout, 'stderr': result.stderr, 'reason': reason}
    except (OSError, subprocess.SubprocessError) as exc:
        receipt = {'sent': False, 'reason': reason, 'delivery_error': str(exc)}
    save(output / 'notification.json', receipt)
    if not receipt['sent']:
        print('EX42_REMEASURE_NOTIFICATION_FAILED ' + json.dumps(receipt, ensure_ascii=False), file=sys.stderr)
    return receipt


def execute(request, *, wait=False, poll=30):
    validate_request(request)
    required = ('GPU_JOBS_QUEUE', 'EX42_MAIN_ROOT', 'EX42_SOURCE_REF')
    if any(not request['launch_env'].get(key) for key in required):
        raise ValueError('launch_env misses queue, source ref or new training output root')
    binding_path = Path(request['retrain_binding'])
    while True:
        if binding_path.is_file():
            declaration = read(binding_path)
            if training_done(declaration['run']) is not None:
                break
        if not wait:
            raise ValueError('retrain binding or 1000-update done marker not ready')
        print('WAIT retrain binding and done marker', flush=True)
        time.sleep(poll)
    if declaration.get('startup'):
        checked(declaration['startup'])
    binding = source_binding(declaration['run'], declaration['training_log'])
    for key in ('expected_plan_sha256',):
        if not isinstance(declaration.get(key), str) or len(declaration[key]) != 64:
            raise ValueError(f'retrain binding needs {key}')
    if declaration['expected_plan_sha256'] != binding['plan']['sha256']:
        raise ValueError('retrain binding plan SHA differs')
    from foothold_s2.ex42_eval_once import manifest_checkpoint_sha
    rows = jobs(request, binding)
    for job in rows:
        checkpoint_sha, iteration = manifest_checkpoint_sha(Path(job['checkpoint']))
        if iteration != job['iteration']:
            raise ValueError('iteration differs')
        job.update(checkpoint_sha256=checkpoint_sha, source_git_head=request['source_git_head'])
    if declaration.get('expected_checkpoint_sha256') is not None and rows[-1]['checkpoint_sha256'] != declaration['expected_checkpoint_sha256']:
        raise ValueError('retrain binding checkpoint SHA differs')
    output = Path(request['output'])
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'binding.json', binding)
    save(output / 'jobs.json', {'jobs': rows, 'request': request})
    results = []
    try:
        with admission(request, output) as guard:
            for index, job in enumerate(rows):
                validate_request(request)
                for key in ('plan', 'approvals', 'manifest', 'startup', 'training_log'):
                    checked(binding[key])
                guard()
                if sha(job['checkpoint']) != job['checkpoint_sha256']:
                    raise ValueError('checkpoint changed before evaluation')
                with (output / f'child-{index}.log').open('x') as log:
                    done = subprocess.run(job['argv'], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
                if done.returncode:
                    raise ValueError(f'{job["group"]} m{job["iteration"]} child rc={done.returncode}')
                results.append(completed_job(job, request['evaluation_plan']['sha256']))
            comparison(output, results)
            # All nine receipts must exist before the new run alone may advance.
            outcome = bridge(request, binding, output, Path(rows[-1]['output']) / 'p1_score.json', guard=guard)
        notification = None
        if outcome.get('state') != 'launcher_started':
            notification = notify_hold(output, f"E1F not launched: {outcome.get('state')}, judgment={outcome.get('judgment')}")
        save(output / 'batch_receipt.json', {'state': 'complete', 'measurements': len(results),
                                           'bridge': outcome, 'notification': notification})
    except Exception as exc:
        reason = f'{type(exc).__name__}: {exc}'
        notification = notify_hold(output, reason)
        save(output / 'batch_receipt.json', {'state': 'HOLD', 'completed_measurements': len(results),
                                           'reason': reason, 'results': results, 'notification': notification})
        raise
    return outcome


def prepare(args):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.eval.ex42_friction import load_policy
    plan = EX42Plan.load(args.plan)
    load_policy(args.plan)
    approvals = ref(args.approvals)
    if approvals['sha256'] != plan.document['stage_zero']['approval_sha256']:
        raise ValueError('evaluation approval pin differs')
    mesh = read(Path(args.mesh_dir) / 'mesh_manifest.json')
    dependencies = [ref(p) for p in plan.path.parent.iterdir() if p.is_file() and p.suffix in ('.yaml', '.json')]
    from foothold_s2.ex42_score import config
    dependencies.append(ref(config()[1]))
    dependencies += [ref(Path(args.mesh_dir) / p) for p in ('mesh_manifest.json', 'terrain_manifest.json')]
    document = {'format': 'foothold-ex42-remeasurement/1',
                'source_git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'evaluation_plan': ref(args.plan), 'evaluation_approvals': approvals,
                'dependencies': dependencies, 'parent': ref(args.parent), 'old': source_binding(args.old_run),
                'retrain_binding': str(Path(args.retrain_binding).absolute()), 'output': str(Path(args.output).absolute()),
                'mesh_dir': str(Path(args.mesh_dir).resolve()), 'mesh_sha256': mesh['mesh_sha256'],
                'python': sys.executable, 'launch_env': read(args.launch_env),
                'admission_lock': str(Path.home() / 'mai/tmp/ex42-remeasurement.lock')}
    save(args.request, document)
    return document


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--bind', action='store_true', help='Pin one actual training run at startup; final checkpoint is later pinned from its done manifest')
    parser.add_argument('--run', type=Path)
    parser.add_argument('--training-log', type=Path)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--wait', action='store_true')
    for name in ('plan', 'approvals', 'parent', 'old-run', 'retrain-binding', 'output', 'mesh-dir', 'launch-env'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.bind:
            if args.execute or args.prepare or not args.run or not args.training_log:
                raise ValueError('bind needs run and training-log, cannot execute')
            source = source_binding(args.run)
            cli = read(Path(source['run']) / 'manifest.json')['run']['cli_args']
            if cli.get('max_iterations') != 1000 or cli.get('ex42_speed_probe') is not False:
                raise ValueError('cannot bind a smoke or non-1000 run')
            row = {'run': source['run'], 'training_log': str(args.training_log.resolve(strict=True)),
                   'expected_plan_sha256': source['plan']['sha256'], 'startup': source['startup']}
            save(args.request, row)
        elif args.prepare:
            if args.execute or any(getattr(args, n.replace('-', '_')) is None for n in
                                  ('plan', 'approvals', 'parent', 'old-run', 'retrain-binding', 'output', 'mesh-dir', 'launch-env')):
                raise ValueError('prepare needs all source paths and cannot execute')
            row = prepare(args)
        elif args.execute:
            row = execute(read(args.request), wait=args.wait)
        else:
            request = read(args.request)
            validate_request(request)
            row = {'state': 'CPU_PREVIEW', 'request': ref(args.request), 'training_started': False,
                   'binding_ready': Path(request['retrain_binding']).is_file()}
        print(json.dumps(row, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        if args.execute:
            try:
                request = read(args.request) if args.request.is_file() else {}
            except (ValueError, OSError):
                request = {}
            existing = Path(request.get('output', str(args.request.parent))) / 'notification.json'
            if not existing.is_file():
                import tempfile
                attempt = Path(tempfile.mkdtemp(prefix='remeasure-admission-hold-', dir=args.request.parent))
                notify_hold(attempt, f'{type(exc).__name__}: {exc}')
        print(f'HOLD: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
