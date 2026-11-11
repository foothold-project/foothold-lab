"""Known-input CPU evidence; never launch Kit or infer PASS from an adapter name."""
import copy
import json
from pathlib import Path

import pytest
import yaml

from foothold_s2.eval import ex42_late_stage_tasks as late
from foothold_s2.eval.ex42_task_cells import sha256
from foothold_s2.tests.test_ex42_task_cells_cpu import trace

PLAN = Path(__file__).parents[1] / 'curriculum/ex42-prep.yaml'


def plan():
    return yaml.safe_load(PLAN.read_text(encoding='utf-8'))


def test_e4_exact_paper_tasks_and_e5_all_named_kinds():
    p = plan()
    e4 = late.requirements(p, 'E4')
    assert {s['kind'] for s in e4} == {
        'eval_slope_30', 'eval_slope_35', 'eval_stairs_015',
        'eval_stairs_020', 'eval_stairs_025', 'eval_stairs_010'}
    assert all(s['family'] == 'V' and s['level'] == 0 and s['group'] == 'paper' for s in e4)
    e5 = late.requirements(p, 'E5')
    assert len(e5) == 35
    assert len({(s['family'], s['kind']) for s in e5}) == 35
    assert next(s for s in e5 if s['family'] == 'E' and s['kind'] == 'slope_steep')['level'] == 6
    changed = copy.deepcopy(p)
    changed['evaluation']['paper_cells']['slope']['judge'] = []
    with pytest.raises(ValueError, match='paper'):
        late.requirements(changed, 'E4')


def test_missing_and_empty_evidence_never_passes(tmp_path):
    cp = tmp_path / 'model_500.pt'; cp.write_bytes(b'CPU fixture model')
    row = late.read_window(tmp_path, plan=plan(), plan_sha256=sha256(PLAN),
        stage_id='E4', checkpoint=cp, seed=42, window_index=2,
        training_mesh_sha256='a' * 64)
    assert row['judgement'] == 'HOLD'
    assert len(row['suites']) == 6
    assert all(s['judgement'] == 'HOLD' for s in row['suites'].values())
    with pytest.raises(ValueError, match='empty'):
        late.combine_cases({})


def make_suite(tmp_path, *, window=2, ratio=.8):
    from foothold_s2.terrains.ex42_eval_terrains import write_mesh
    from foothold_s2.eval.ex42_task_suite import create_request, validate_request
    from foothold_s2.eval.ex42_task_evidence import publish_case, write_json, FORMAT
    from foothold_s2.eval.ex42_task_mesh import preflight
    source = tmp_path / 'source'; write_mesh(source, kinds=['eval_slope_35'], seed=42)
    cp = tmp_path / 'model_500.pt'; cp.write_bytes(b'CPU fixture, not a runnable policy')
    reqpath = create_request(plan_path=PLAN, checkpoint=cp, source_mesh=source,
        out=tmp_path / 'suite', family='V', kind='eval_slope_35', level=0,
        stage='E5', group='directions', window_index=window, steps=300)
    req = validate_request(reqpath)
    identity = {k: req[k] for k in ('checkpoint_sha256', 'plan_sha256', 'seed')}
    identity['request_sha256'] = sha256(reqpath)
    for flat in (True, False):
        folder = reqpath.parent / ('flat_result' if flat else 'result'); folder.mkdir()
        replica = preflight(req['flat_replica_dir' if flat else 'replica_dir'])['receipt']
        cases = {}
        for name, spec in req['case_specs'].items():
            values = trace(steps=300)
            values['command_b'][:] = spec['command_b']
            values['initial_yaw_rad'][:] = spec['approach_yaw_rad']
            values['root_pos_w'][..., 0] *= 1 if flat else ratio
            cases[name] = publish_case(folder, spec, values, anchors=replica['task_anchors'], identity=identity)
        write_json(folder / 'task_cells.json', dict(format=FORMAT, state='done', flat_reference=flat,
            identity=identity, source_mesh_sha256=req['source_mesh_sha256'],
            replica_mesh_sha256=replica['mesh_sha256'], cases=cases, dr=None))
    expected = dict(family='V', kind='eval_slope_35', level=0, group='directions')
    kwargs = dict(expected=expected, stage_id='E5', checkpoint=cp, plan_sha256=sha256(PLAN),
        seed=42, window_index=window, training_mesh_sha256=req['source_mesh_sha256'])
    return reqpath, kwargs


def test_real_npz_cross_half_flat_and_first_window_record(tmp_path):
    path, kwargs = make_suite(tmp_path / 'second')
    value = late.read_suite(path, **kwargs)
    assert value['judgement'] == 'PASS'
    assert len(value['judge_cases']) == 6
    assert len(value['record_cases']) == 6
    assert value['cases']['eval_slope_35_reverse_eval_gt']['ratio'] == pytest.approx(.8)
    first, first_kwargs = make_suite(tmp_path / 'first', window=1)
    value = late.read_suite(first, **first_kwargs)
    assert value['judgement'] == 'HOLD'
    assert value['reason'] == 'first_direction_window_record_only'


def test_failed_raw_distance_not_promoted_by_forged_index(tmp_path):
    path, kwargs = make_suite(tmp_path, ratio=.49)
    assert late.read_suite(path, **kwargs)['judgement'] == 'FAIL'
    index = path.parent / 'result/task_cells.json'
    row = json.loads(index.read_text(encoding='utf-8'))
    row['cases']['eval_slope_35_reverse_eval_gt']['success_count'] = 63
    index.write_text(json.dumps(row), encoding='utf-8')
    value = late.read_suite(path, **kwargs)
    assert value['judgement'] == 'HOLD'
    assert 'count differs' in value['reason']


@pytest.mark.parametrize('field,value', [
    ('seed', 43), ('window_index', 3), ('stage_id', 'E4'),
    ('plan_sha256', 'b' * 64), ('training_mesh_sha256', 'c' * 64)])
def test_wrong_identity_is_hold(tmp_path, field, value):
    path, kwargs = make_suite(tmp_path)
    kwargs[field] = value
    result = late.read_suite(path, **kwargs)
    assert result['judgement'] == 'HOLD'


def test_truncated_npz_is_hold_not_an_exception(tmp_path):
    path, kwargs = make_suite(tmp_path)
    raw = next((path.parent / 'result').glob('*.npz'))
    raw.write_bytes(raw.read_bytes()[:24])
    assert late.read_suite(path, **kwargs)['judgement'] == 'HOLD'


def test_one_record_only_mode_cannot_satisfy_a_judge_task():
    with pytest.raises(ValueError, match='judge'):
        late.combine_cases({'x': {'role': 'record_only', 'judgement': 'RECORD'}})


def test_previous_checkpoint_cannot_skip_a_window_or_switch_stage(tmp_path):
    cp = tmp_path / 'model_750.pt'; cp.write_bytes(b'current')
    prior = tmp_path / 'model_500.pt'; prior.write_bytes(b'previous')
    p = plan()
    previous = dict(stage_id='E4', checkpoint=str(prior), checkpoint_sha256=sha256(prior),
                    maintenance_source_sha256=sha256(PLAN), conditions={'eval_seed': 42})
    args = dict(checkpoint=cp, previous=previous, stage_id='E4', plan=p,
                plan_sha256=sha256(PLAN), seed=42, training_mesh_sha256='a' * 64)
    value = late.read_two_windows(tmp_path / 'm750', **args)
    assert value['current']['judgement'] == value['previous']['judgement'] == 'HOLD'
    for field, wrong in [('stage_id', 'E3'), ('maintenance_source_sha256', 'b' * 64),
                          ('checkpoint', str(tmp_path / 'model_250.pt'))]:
        bad = {**previous, field: wrong}
        with pytest.raises(ValueError, match='previous'):
            late.read_two_windows(tmp_path / 'm750', **{**args, 'previous': bad})


def test_paper_npz_is_recounted_with_measured_geometry_time(tmp_path):
    from foothold_s2.terrains.ex42_eval_terrains import write_mesh
    from foothold_s2.eval.ex42_task_mesh import select_tile, task_anchors, preflight
    from foothold_s2.eval.ex42_task_suite import create_request, validate_request
    from foothold_s2.eval.ex42_task_evidence import publish_case, write_json, FORMAT
    source = tmp_path / 'source'; write_mesh(source, kinds=['eval_slope_35'], seed=42)
    tile = select_tile(source, family='V', kind='eval_slope_35', level=0)
    table = tmp_path / 'geometry.json'
    table.write_text(json.dumps({'sources': {'fixture': {'mesh_sha256': tile['source_mesh_sha256']}},
        'rows': [{'family': 'V', 'kind': 'eval_slope_35', 'level': 0,
                  'origin_m': tile['origin'].tolist(), 'anchors': task_anchors(tile)}]}), encoding='utf-8')
    p = plan(); p['evaluation']['forward_completion_timing']['calibration_table'] = {
        'path': str(table), 'sha256': sha256(table)}
    planpath = tmp_path / 'plan.yaml'; planpath.write_text(yaml.safe_dump(p), encoding='utf-8')
    cp = tmp_path / 'model_500.pt'; cp.write_bytes(b'CPU test fixture')
    reqpath = create_request(plan_path=planpath, checkpoint=cp, source_mesh=source,
        out=tmp_path / 'suite', family='V', kind='eval_slope_35', level=0,
        stage='E4', group='paper', window_index=2, steps=300)
    req = validate_request(reqpath)
    replica = preflight(req['replica_dir'])['receipt']; anchors = replica['task_anchors']
    identity = {k: req[k] for k in ('checkpoint_sha256', 'plan_sha256', 'seed')}
    identity['request_sha256'] = sha256(reqpath)
    folder = reqpath.parent / 'result'; folder.mkdir(); cases = {}
    for name, spec in req['case_specs'].items():
        t = trace(steps=spec['steps'])
        t['root_pos_w'][..., 0] = anchors['exit_x'] + .05
        t['root_pos_w'][..., 1] = sum(anchors['exit_bounds_y']) / 2
        t['foot_pos_w'][..., 0] = t['root_pos_w'][..., 0, None]
        t['foot_pos_w'][..., 1] = t['root_pos_w'][..., 1, None]
        t['foot_pos_w'][..., 2] = anchors['support_floor_m']
        cases[name] = publish_case(folder, spec, t, anchors=anchors, identity=identity)
    write_json(folder / 'task_cells.json', dict(format=FORMAT, state='done', flat_reference=False,
        identity=identity, source_mesh_sha256=req['source_mesh_sha256'],
        replica_mesh_sha256=replica['mesh_sha256'], cases=cases, dr=None))
    kwargs = dict(expected=dict(family='V', kind='eval_slope_35', level=0, group='paper'),
        stage_id='E4', checkpoint=cp, plan_sha256=sha256(planpath), seed=42,
        window_index=2, training_mesh_sha256='a' * 64)
    result = late.read_suite(reqpath, **kwargs)
    assert result['judgement'] == 'PASS', result
    assert len(result['judge_cases']) == 2 and len(result['record_cases']) == 1
    # A paper cell must use its measured route length, not the direction probe's 300 steps.
    assert next(iter(req['case_specs'].values()))['steps'] == req['completion_timing']['steps']
    data = json.loads(reqpath.read_text(encoding='utf-8'))
    data['completion_timing']['steps'] -= 1
    reqpath.write_text(json.dumps(data), encoding='utf-8')
    assert late.read_suite(reqpath, **kwargs)['judgement'] == 'HOLD'
