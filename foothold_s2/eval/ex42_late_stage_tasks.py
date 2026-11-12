"""E4 paper / E5 direction evidence, recounted from immutable task-suite NPZ.

This is an exit consumer, not a training controller. A missing child, changed
identity or an unavailable raw trace is HOLD. First E5 direction windows remain
record-only; two judged windows are needed before this task can support exit.
"""
from __future__ import annotations

import re
from pathlib import Path
from zipfile import BadZipFile

from foothold_s2.eval.ex42_task_cells import sha256
from foothold_s2.eval.ex42_task_evidence import read_evidence
from foothold_s2.eval.ex42_task_suite import validate_request, cross_settings

PAPER = {
    'slope': ['eval_slope_30', 'eval_slope_35'],
    'stairs_forward': ['eval_stairs_015', 'eval_stairs_020', 'eval_stairs_025'],
    'stairs_reverse': ['eval_stairs_010'],
}
MODES = ('eval_gt', 'eval_pred', 'probe_prop_only')
DATA_ERRORS = (OSError, ValueError, KeyError, TypeError, EOFError, BadZipFile)


def requirements(plan: dict, stage_id: str) -> list[dict]:
    """Named geometry cells, independent of column order and of measured results.

    E5 uses the pinned stage plan's positive kinds/caps. Materialization must
    preserve inherited E4 caps there. Training-exposure evidence is a separate
    common gate; a template cap alone is not evidence of having learned it.
    """
    cross_settings(plan)
    if stage_id == 'E4':
        paper = plan['evaluation']['paper_cells']
        if paper.get('judge_from_stage') != 'E4' or any(paper[k]['judge'] != v for k, v in PAPER.items()):
            raise ValueError('E4 paper judge cells differ from CG v0.17')
        return [dict(family='V', kind=kind, level=0, group='paper')
                for kinds in PAPER.values() for kind in kinds]
    if stage_id != 'E5':
        raise ValueError('late task stage must be E4 or E5')
    stage = next(s for s in plan['stages'] if s['id'] == stage_id)
    initial = next(s for s in plan['stages'] if s['id'] == 'E0')
    declarations = initial['terrain']['kind_task']
    exposure = stage['terrain']['exposure_at_E5']
    if exposure['default']['exposure'] != 0:
        raise ValueError('E5 default exposure must remain zero')
    found = {}
    for rule in exposure['positive']:
        weight = rule.get('exposure', rule.get('share'))
        if type(weight) not in (float, int) or not 0 < weight <= 1:
            raise ValueError('E5 positive rule is not a positive finite exposure')
        level = rule['level_cap']
        if type(level) is not int or not 0 <= level <= 9:
            raise ValueError('E5 representative level is absent or outside mesh levels')
        kinds = list(declarations[rule['kinds_of']]) if 'kinds_of' in rule else [rule['kind']]
        for kind in kinds:
            key = rule['family'], kind
            if key in found or any(re.fullmatch(r'[A-Za-z0-9_]+', x) is None for x in key):
                raise ValueError('duplicate or invalid E5 named kind')
            found[key] = dict(family=key[0], kind=kind, level=level, group='directions')
    if not found:
        raise ValueError('empty E5 exposure cannot prove exit')
    return [found[key] for key in sorted(found)]


def suite_name(spec: dict) -> str:
    return f"{spec['family']}_{spec['kind']}_L{spec['level']}_{spec['group']}"


def combine_cases(cases: dict) -> str:
    if not cases:
        raise ValueError('empty task suite')
    states = [v['judgement'] for v in cases.values() if v.get('role') == 'judge']
    if not states or any(s not in ('PASS', 'HOLD', 'FAIL') for s in states):
        raise ValueError('task suite has no valid judge cases')
    return 'FAIL' if 'FAIL' in states else 'HOLD' if 'HOLD' in states else 'PASS'


def read_suite(request_path: Path, *, expected: dict, stage_id: str, checkpoint: Path,
               plan_sha256: str, seed: int, window_index: int,
               training_mesh_sha256: str) -> dict:
    """Read every mode and recount raw NPZ, with identity supplied by the scorer.

    The public read_evidence function verifies request/replica/index/raw hashes,
    exact role lists and identical flat pairs. This wrapper also binds the
    request to the actual checkpoint, stage, boundary and required named kind.
    """
    path = Path(request_path).resolve()
    try:
        req = validate_request(path)
        wanted = {**expected, 'stage_id': stage_id, 'plan_sha256': plan_sha256,
                  'seed': seed, 'window_index': window_index, 'envs': 64, 'dr_mode': 'off',
                  'checkpoint_sha256': sha256(checkpoint)}
        if any(req.get(k) != v for k, v in wanted.items()) or Path(req['checkpoint']).resolve() != Path(checkpoint).resolve():
            raise ValueError('task request identity differs from scored boundary')
        if expected['group'] == 'directions' and req['source_mesh_sha256'] != training_mesh_sha256:
            raise ValueError('direction source mesh differs from pinned map64 mesh')
        recounted = read_evidence(path.parent / 'result', request_path=path)
        cases = recounted['cases']
        prefix = expected['kind'] if expected['family'] == 'V' else expected['family'] + '_' + expected['kind']
        directions = ('reverse', 'side_left', 'side_right') if expected['group'] == 'directions' else (
            'reverse' if expected['kind'] == 'eval_stairs_010' else 'forward',)
        judge_cases = {f'{prefix}_{direction}_{mode}' for direction in directions for mode in MODES[:2]}
        record_cases = set(cases) - judge_cases
        first = expected['group'] == 'directions' and window_index == 1
        actual_judges = {k for k, v in cases.items() if v.get('role') == 'judge'}
        if actual_judges != (set() if first else judge_cases):
            raise ValueError('required task judge roles differ')
        result = {'role': 'judge', 'judgement': 'HOLD' if first else combine_cases(cases),
                  'cases': cases, 'judge_cases': sorted(judge_cases), 'record_cases': sorted(record_cases),
                  'request_file': str(path), 'request_sha256': sha256(path),
                  'receipt_file': recounted['receipt_file'], 'receipt_sha256': recounted['receipt_sha256'],
                  'source_mesh_sha256': req['source_mesh_sha256'], 'spec': expected,
                  'window_index': window_index}
        if first:
            result['reason'] = 'first_direction_window_record_only'
        return result
    except DATA_ERRORS as exc:
        return {'role': 'judge', 'judgement': 'HOLD', 'reason': f'{type(exc).__name__}: {exc}',
                'request_file': str(path), 'spec': expected, 'window_index': window_index}


def read_window(evaluation: Path, *, plan: dict, plan_sha256: str, stage_id: str,
                checkpoint: Path, seed: int, window_index: int,
                training_mesh_sha256: str) -> dict:
    if type(window_index) is not int or window_index < 1:
        raise ValueError('positive stage-local window index required')
    specs = requirements(plan, stage_id)
    suites = {suite_name(spec): read_suite(
        Path(evaluation) / 'task_cells' / suite_name(spec) / 'request.json',
        expected=spec, stage_id=stage_id, checkpoint=checkpoint, plan_sha256=plan_sha256,
        seed=seed, window_index=window_index, training_mesh_sha256=training_mesh_sha256)
        for spec in specs}
    return {'role': 'judge', 'judgement': combine_cases(suites), 'suites': suites,
            'required_suites': [suite_name(s) for s in specs], 'stage_id': stage_id,
            'window_index': window_index}


def read_two_windows(evaluation: Path, *, checkpoint: Path, previous: dict | None,
                     stage_id: str, plan: dict, plan_sha256: str, seed: int,
                     training_mesh_sha256: str) -> dict:
    """Only adjacent local stage boundaries can provide the two task windows.

    Caller must obtain previous through StageJudge.previous_window, which also
    checks its published score/P1/checkpoint/config identities. This function
    recounts its task NPZ again instead of reusing previous stage_exit numbers.
    """
    match = re.fullmatch(r'model_([1-9][0-9]*)\.pt', Path(checkpoint).name)
    interval = plan['evaluation']['interval_updates']
    if match is None or type(interval) is not int or interval <= 0:
        raise ValueError('named local checkpoint and positive interval required')
    iteration = int(match.group(1))
    if iteration % interval or plan['evaluation']['promotion']['windows'] != 2:
        raise ValueError('task exit requires an exact boundary and two windows')
    now = read_window(evaluation, plan=plan, plan_sha256=plan_sha256, stage_id=stage_id,
        checkpoint=checkpoint, seed=seed, window_index=iteration // interval,
        training_mesh_sha256=training_mesh_sha256)
    before = {'role': 'judge', 'judgement': 'HOLD', 'reason': 'previous_task_window_missing'}
    expected_cp = Path(checkpoint).with_name(f'model_{iteration - interval}.pt')
    if previous is not None:
        if (iteration <= interval or previous.get('stage_id') != stage_id or
                Path(previous.get('checkpoint', '')).resolve() != expected_cp.resolve() or
                previous.get('checkpoint_sha256') != sha256(expected_cp) or
                previous.get('maintenance_source_sha256') != plan_sha256 or
                previous.get('conditions', {}).get('eval_seed') != seed):
            raise ValueError('previous task boundary stage/checkpoint/plan/seed differs')
        before = read_window(Path(evaluation).parent / f'm{iteration - interval}',
            plan=plan, plan_sha256=plan_sha256, stage_id=stage_id, checkpoint=expected_cp,
            seed=seed, window_index=iteration // interval - 1,
            training_mesh_sha256=training_mesh_sha256)
        # A different paper source is not a second measurement of the same task.
        for key in now['required_suites']:
            a, b = now['suites'][key], before['suites'][key]
            if a.get('source_mesh_sha256') and b.get('source_mesh_sha256') and a['source_mesh_sha256'] != b['source_mesh_sha256']:
                before['suites'][key] = {**b, 'judgement': 'HOLD', 'reason': 'task_geometry_changed_between_windows'}
        before['judgement'] = combine_cases(before['suites'])
    return {'current': now, 'previous': before}
