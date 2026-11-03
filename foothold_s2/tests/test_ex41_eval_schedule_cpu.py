from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from foothold_s2 import ex41_score_watch as watch
from foothold_s2.ex41_eval_once import (
    PERIODIC_W78_PHASE, auxiliary_phase_status, bundle_terminal_status, commands,
)
from foothold_s2.curriculum.continuous import load_plan
from foothold_s2.ex40_score import sha256


TABLE = watch.DEFAULT_TABLE


def test_nominal_plan_lengths_are_only_capacity_estimates():
    plan = load_plan(TABLE, arm='B')
    assert watch.nominal_stage_end_updates(plan) == (750, 1750, 2750, 4000, 4500, 5000)
    assert [row['end_update'] for row in watch.stage_interval_loads(
        plan, train_seconds_per_update=27, core_seconds=1093,
        auxiliary_seconds=9480)] == [750, 1750, 2750, 4000, 4500, 5000]
    loads = watch.stage_interval_loads(plan, train_seconds_per_update=27,
                                       core_seconds=1093, auxiliary_seconds=9480)
    assert [row['core_checkpoints'] for row in loads] == [3, 4, 4, 5, 2, 2]
    assert all(row['queue_growth_seconds'] == 0 for row in loads)
    assert loads[-2]['evaluation_seconds'] == 11666
    assert loads[-2]['training_seconds'] == 13500


def _clock_log(run, plan, *, hold=False, extension=False):
    from foothold_s2.curriculum.ex41_fixed import Clock

    clock = Clock(plan.clock_settings)
    rows = []
    boundaries = list(range(1, 6502, 250))
    if hold:
        # The verifier's actual sequence: hold at 1001, recover at 1251/1501.
        boundaries = sorted(set(boundaries + [1001, 1251, 1501]))
    for n in boundaries:
        if n > 6001: break
        failed = True if hold and n == 1001 else False
        score_iteration = n - 1 - 250
        clock.boundary(n, failed, score_iteration if score_iteration > 0 else None)
        if extension and n == 4501:
            clock.extension = 500
            clock.extension_decided = True
        stage = plan.stages[clock.position(n)].id
        rows.append({'event': 'schedule_continue', 'iteration': n,
                     'schedule_clock': clock.__dict__.copy(), 'stage': stage})
        if (stage == plan.stages[-1].id and
                clock.time(n) >= clock.settings['duration_updates'] + clock.extension):
            rows.append({'event': 'fixed_schedule_finished', 'iteration': n,
                         'graduated': False})
            break
    (run / 'stage_log.jsonl').write_text(
        ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows), encoding='utf-8')


def test_actual_clock_receipts_move_auxiliary_to_recovered_stage_end(tmp_path):
    plan = load_plan(TABLE, arm='B')
    hold_run = tmp_path / 'hold_run';hold_run.mkdir()
    _clock_log(hold_run, plan, hold=True)
    hold_ends = watch.stage_end_updates(plan, hold_run)
    assert 1750 not in hold_ends and 2250 in hold_ends and 5000 in hold_ends
    assert 5500 in hold_ends
    assert watch.due_evaluation_scopes(1750, plan, hold_run) == ('periodic',)
    assert watch.due_evaluation_scopes(2250, plan, hold_run) == ('periodic', 'auxiliary')

    extension_run = tmp_path / 'extension_run';extension_run.mkdir()
    _clock_log(extension_run, plan, extension=True)
    extension_ends = watch.stage_end_updates(plan, extension_run)
    assert 5000 in extension_ends and 5500 in extension_ends
    assert watch.due_evaluation_scopes(5000, plan, extension_run) == ('periodic', 'auxiliary')
    assert watch.due_evaluation_scopes(5500, plan, extension_run) == ('periodic', 'auxiliary')


def test_stage_end_requires_runtime_clock_evidence(tmp_path):
    plan = load_plan(TABLE, arm='B')
    run = tmp_path / 'run'
    run.mkdir()
    assert watch.stage_end_updates(plan, run) == ()
    (run / 'stage_log.jsonl').write_text(
        json.dumps({'event': 'schedule_continue', 'iteration': 751,
                    'schedule_clock': {'elapsed': 750}, 'stage': plan.stages[1].id}) + '\n',
        encoding='utf-8')
    with pytest.raises(ValueError, match='runtime Clock receipt lacks'):
        watch.stage_end_updates(plan, run)


def test_scope_commands_use_side_w78_every_250_and_full_w78_at_stage_end(tmp_path):
    cfg = watch.config(watch.DEFAULT_CONFIG)
    cp = tmp_path / 'model_250.pt'
    cp.write_bytes(b'known checkpoint bytes')
    core = commands(cp, tmp_path / 'core', cfg, scope='periodic')
    # No live GPU0 training marker means a standalone ladder can use GPU0.
    auxiliary = commands(cp, tmp_path / 'aux', cfg, scope='auxiliary',
                         gpu0_training_markers=[])
    assert [row['name'] for row in core] == [
        'map64', 'stand_eval_gt', 'stand_probe_prop_only', 'stand_eval_pred', 'w78_v2_sides']
    assert [row['name'] for row in auxiliary] == [
        'axis_v2', 'w78_v2', 'push_ladder', 'a_push_video']
    assert '--terrain-skill-v2' in auxiliary[1]['argv']
    assert auxiliary[2]['argv'][2] == 'foothold_s2.eval.ex41_push_ladder_bundle'
    assert auxiliary[2]['device'] == 'cuda:0'
    assert auxiliary[2]['argv'][auxiliary[2]['argv'].index('--device') + 1] == 'cuda:0'
    assert auxiliary[3]['argv'][2] == 'foothold_s2.eval.a_push_video'
    assert auxiliary[3]['device'] == 'cuda:1'
    assert '--cadence' in auxiliary[3]['argv']
    assert auxiliary[3]['argv'][auxiliary[3]['argv'].index('--cadence') + 1] == 'stage_end'
    side_args = core[-1]['argv']
    assert '--terrain-skill-v2' in side_args
    assert side_args[side_args.index('--terrain-skill-v2-cases') + 1] == 'stairs_side_left,stairs_side_right'
    assert '--terrain-skill-v2-cases' not in auxiliary[1]['argv']
    assert len(core) == 5 and all(row['argv'][row['argv'].index('--device') + 1] == 'cuda:1'
                                  for row in core)


def test_live_gpu0_training_routes_stage_end_children_to_gpu1_and_they_finish(
        tmp_path, monkeypatch):
    """Stage-end bundle starts and finishes real CPU children under a live GPU0 owner."""
    import psutil
    from foothold_s2.eval import ex41_gpu_priority as priority
    from foothold_s2 import ex41_eval_once

    marker = tmp_path / 'TRAINING_BUSY_GPU0'
    owner = psutil.Process()
    priority.publish_marker(marker, job='fake-live-training', iteration=1000,
                            pid=owner.pid, process_created_at=owner.create_time())
    marker_state = priority.gpu0_training_marker_state([marker])
    assert marker_state['active'] is True
    assert marker_state['markers'][0]['state'] == 'live'

    checkpoint = tmp_path / 'model_1000.pt'
    checkpoint.write_bytes(b'known CPU fixture checkpoint')
    eval_config = tmp_path / 'eval.json'
    eval_config.write_text('{}', encoding='utf-8')
    p1_marker = tmp_path / 'PRIORITY_BUSY_GPU1'
    cfg = {'envs': 64, 'eval_seed': 42, 'map_steps': 2,
           'stand_seconds': 1, 'stand_skip_seconds': 0,
           'stand': {'contact_force_n': 1}}

    class Plan:
        fixed_schedule = True
        parent_sha256 = 'p' * 64
        effective_sha256 = 's' * 64

    monkeypatch.setattr(ex41_eval_once, 'load_plan', lambda *_args, **_kwargs: Plan())
    monkeypatch.setattr(ex41_eval_once, 'config', lambda *_args: cfg)
    monkeypatch.setattr(ex41_eval_once, 'ISAAC_PYTHON', Path(sys.executable))
    monkeypatch.setattr(ex41_eval_once.subprocess, 'check_output',
                        lambda argv, **_kwargs: '' if 'status' in argv else 'cpu-test-head')
    # This test exercises scheduling and process routing, not evaluator receipt schemas.
    monkeypatch.setattr(ex41_eval_once, 'reconcile_child_result',
                        lambda name, child, _output: {**child, 'name': name})

    # Exercise the production hidden-child launcher, but replace Kit entrypoints
    # with CPU-only children that prove the GPU0 owner and GPU1 P1 claim stay live.
    child_code = (
        'import json, os, pathlib, psutil, sys, time; '
        'marker=pathlib.Path(sys.argv[1]); p1=pathlib.Path(sys.argv[2]); '
        'out=pathlib.Path(sys.argv[3]); '
        'owner=json.loads(marker.read_text()); '
        'p1_owner=json.loads(p1.read_text()); '
        'alive=psutil.pid_exists(owner["pid"]); p1_live=psutil.pid_exists(p1_owner["pid"]); '
        'out.write_text(json.dumps({"state":"started","device":sys.argv[4],"gpu0_owner_live":alive,"gpu1_p1_live":p1_live})); '
        'time.sleep(0.05); '
        'out.write_text(json.dumps({"state":"finished","device":sys.argv[4],"gpu0_owner_live":psutil.pid_exists(owner["pid"]),"gpu1_p1_live":psutil.pid_exists(p1_owner["pid"])})); '
        'print("child_started", sys.argv[4]); print("child_finished", sys.argv[4])'
    )
    real_hidden_child = ex41_eval_once.hidden_child
    observed = []

    def cpu_child(argv, folder, *, env=None, cwd=ex41_eval_once.ROOT):
        argv = list(argv)
        device = argv[argv.index('--device') + 1]
        phase = argv[argv.index('-m') + 1]
        training_marker = None
        if phase == 'foothold_s2.eval.a_push_video':
            training_marker = Path(argv[argv.index('--training-marker') + 1])
            assert training_marker == priority.DEFAULT_GPU1_TRAINING_MARKER
            assert training_marker != marker
        else:
            assert phase != 'foothold_s2.eval.ex41_push_ladder_bundle' or device == 'cuda:1'
        receipt_path = tmp_path / f'{phase.rsplit(".", 1)[-1]}.receipt.json'
        result = real_hidden_child(
            [sys.executable, '-c', child_code, str(marker), str(p1_marker),
             str(receipt_path), device], folder, env=env, cwd=tmp_path)
        observed.append({'phase': phase, 'device': device,
                         'training_marker': str(training_marker) if training_marker else None,
                         'result': result,
                         'receipt': json.loads(receipt_path.read_text(encoding='utf-8')),
                         'stdout': (Path(folder) / 'stdout.log').read_text(encoding='utf-8')})
        return result

    monkeypatch.setattr(ex41_eval_once, 'hidden_child', cpu_child)
    row = ex41_eval_once.evaluate(
        checkpoint, tmp_path / 'stage-end-bundle', eval_config=eval_config,
        priority_marker=p1_marker, scope='auxiliary', gpu0_training_markers=[marker])
    assert row['state'] == 'done' and row['rc'] == 0
    assert row['stage_end_push_ladder_device'] == 'cuda:1'
    assert [entry['phase'] for entry in observed] == [
        'foothold_s2.eval.eval_map_modes', 'foothold_s2.eval.eval_map_modes',
        'foothold_s2.eval.ex41_push_ladder_bundle', 'foothold_s2.eval.a_push_video']
    ladder = next(entry for entry in observed
                  if entry['phase'] == 'foothold_s2.eval.ex41_push_ladder_bundle')
    video = next(entry for entry in observed if entry['phase'] == 'foothold_s2.eval.a_push_video')
    assert ladder['device'] == video['device'] == 'cuda:1'
    assert video['training_marker'] == str(priority.DEFAULT_GPU1_TRAINING_MARKER)
    assert all(entry['result']['state'] == 'done' and entry['result']['rc'] == 0
               for entry in observed)
    assert all(entry['receipt'] == {'state': 'finished', 'device': 'cuda:1',
                                    'gpu0_owner_live': True, 'gpu1_p1_live': True}
               for entry in observed)
    assert all('child_started cuda:1' in entry['stdout']
               and 'child_finished cuda:1' in entry['stdout'] for entry in observed)
    assert priority.gpu0_training_marker_state([marker])['active'] is True
    assert not p1_marker.exists()


def test_measured_periodic_side_cost_fits_one_250_update_training_interval():
    plan = load_plan(TABLE, arm='B')
    # core 18m13s plus GPU0 side W78 measurement 25m13s; 250 updates at 27s/update.
    rows = watch.stage_interval_loads(plan, train_seconds_per_update=27,
                                      core_seconds=1093, periodic_side_seconds=1513,
                                      auxiliary_seconds=9480)
    assert all(row['periodic_seconds'] == row['core_checkpoints'] * 2606 for row in rows)
    assert 1093 + 1513 < 60 * 60
    assert [row['queue_growth_seconds'] for row in rows] == [0, 0, 0, 0, 1192, 2384]


def test_periodic_bundle_requires_exact_side_pair_but_not_full_stage_end_w78(tmp_path):
    output=tmp_path/'w78';output.mkdir()
    cases=('stairs_side_left','stairs_side_right')
    result={'schema':'foothold-terrain-skill-v2/1','state':'done',
            'case_selection':list(cases),'modes':{}}
    for mode in ('eval_gt','probe_prop_only','eval_pred'):
        result['modes'][mode]={
            f'L{level}_a{angle:03d}_{case}':{}
            for level in (2,5) for angle in (0,30,60,90) for case in cases}
    (output/'terrain_skill_v2.json').write_text(json.dumps(result),encoding='utf-8')
    assert auxiliary_phase_status(PERIODIC_W78_PHASE,output)['state']=='done'
    steps={name:{'state':'done'} for name in (
        'map64','stand_eval_gt','stand_probe_prop_only','stand_eval_pred')}
    steps[PERIODIC_W78_PHASE]={'state':'done'}
    periodic=bundle_terminal_status(steps,scope='periodic')
    assert periodic['state']=='done' and periodic['auxiliary_missing']==[]
    assert bundle_terminal_status(steps,scope='auxiliary')['state']=='HOLD'
    del result['modes']['eval_pred']['L5_a090_stairs_side_right']
    (output/'terrain_skill_v2.json').write_text(json.dumps(result),encoding='utf-8')
    assert auxiliary_phase_status(PERIODIC_W78_PHASE,output)['state']=='HOLD'

    full_cases = watch.W78_CASES
    full = {'schema':'foothold-terrain-skill-v2/1','state':'done',
            'case_selection':list(full_cases),'modes':{}}
    expected_full = {f'L{level}_a{angle:03d}_{case}'
                     for level in (2,5) for angle in (0,30,60,90) for case in full_cases}
    for mode in ('eval_gt','probe_prop_only','eval_pred'):
        full['modes'][mode] = {key:{} for key in expected_full}
    (output/'terrain_skill_v2.json').write_text(json.dumps(full),encoding='utf-8')
    assert auxiliary_phase_status('w78_v2',output)['state']=='done'

    full['case_selection'] = list(cases)
    for mode in ('eval_gt','probe_prop_only','eval_pred'):
        full['modes'][mode] = {
            f'L{level}_a{angle:03d}_{case}':{}
            for level in (2,5) for angle in (0,30,60,90) for case in cases}
    (output/'terrain_skill_v2.json').write_text(json.dumps(full),encoding='utf-8')
    status = auxiliary_phase_status('w78_v2',output)
    assert status['state']=='HOLD' and 'full W78 coverage differs' in status['reason']
    full['case_selection'] = [{}]
    (output/'terrain_skill_v2.json').write_text(json.dumps(full),encoding='utf-8')
    assert auxiliary_phase_status('w78_v2',output)['state']=='HOLD'


def test_stage_end_push_ladder_requires_all_12_children(tmp_path):
    from foothold_s2.ex41_eval_once import auxiliary_phase_status

    output = tmp_path / 'push_ladder'; output.mkdir()
    children = [{'state':'done'} for _ in range(12)]
    doc = {'schema':'foothold-ex41-push-ladder-bundle/1','state':'done',
           'expected_children':12,'children':children}
    (output/'push_ladder_bundle.json').write_text(json.dumps(doc),encoding='utf-8')
    assert auxiliary_phase_status('push_ladder',output)['state']=='done'
    doc['children'].pop()
    (output/'push_ladder_bundle.json').write_text(json.dumps(doc),encoding='utf-8')
    assert auxiliary_phase_status('push_ladder',output)['state']=='HOLD'


def test_stage_end_a_push_video_requires_all_three_d168_map_mode_receipts(tmp_path, monkeypatch):
    from foothold_s2.eval import a_push_video
    from foothold_s2.ex41_eval_once import auxiliary_phase_status, reconcile_child_result

    output = tmp_path / 'a_push_video'
    output.mkdir()
    modes = a_push_video.MODES
    for mode in modes:
        (output / f'{mode}.json').write_text(json.dumps({
            'schema': 'foothold-ex41-a-push-video/1',
            'video_rule_version': 'v3.4-D168',
            'map_mode': mode,
        }), encoding='utf-8')
    monkeypatch.setattr(a_push_video, 'compare_mode_receipts', lambda _path: {
        'state': 'complete', 'group_id': 'known-group', 'modes': list(modes)})
    assert auxiliary_phase_status('a_push_video', output)['state'] == 'done'
    child = {'rc': 0, 'state': 'done'}
    assert reconcile_child_result('a_push_video', child, output)['state'] == 'done'

    (output / f'{modes[-1]}.json').unlink()
    held = reconcile_child_result('a_push_video', child, output)
    assert held['state'] == 'HOLD' and held['rc'] == 5
    assert 'receipt' in held['reason']

def _fake_run(tmp_path: Path, iteration: int):
    run = tmp_path / 'run'
    run.mkdir()
    cp = run / f'model_{iteration}.pt'
    cp.write_bytes(f'known model {iteration}'.encode())
    plan = load_plan(TABLE, arm='B')
    manifest = {'schema':'foothold-manifest/1',
        'progress':{'completed_updates':iteration + 1},
        'checkpoints':{cp.name:sha256(cp)},
        'modes':{'ex41':{'effective_sha256':plan.effective_sha256,
            'plan_sha256':plan.sha256,'parent':{'sha256':plan.parent_sha256}}}}
    (run / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    application = {'format':'foothold-ex41-application/1','status':'applied',
        'iteration':1,'parent_update':6000,'stage_after':'S2a','after':{'stage_id':'S2a'}}
    (run / 'ex41_application.jsonl').write_text(json.dumps(application) + '\n', encoding='utf-8')
    return run, cp, plan


@pytest.mark.parametrize(('iteration', 'auxiliary_due'), [(250, False), (750, True)])
def test_core_score_is_published_before_stage_end_auxiliary_dispatch(
        tmp_path, monkeypatch, iteration, auxiliary_due):
    run, cp, plan = _fake_run(tmp_path, iteration)
    _clock_log(run, plan)
    out, scores = tmp_path / 'out', tmp_path / 'scores'
    state = watch.initial_state(run, TABLE, watch.DEFAULT_CONFIG)
    monkeypatch.setattr(watch, '_stable', lambda path, _seconds, _sleep: sha256(path))
    monkeypatch.setattr(watch, 'collect', lambda checkpoint, stage, bundle, active_plan,
                        *args, **kwargs: {
        'format':'foothold-ex41-score/1','iteration':iteration,'stage_id':stage,
        'checkpoint_path':str(checkpoint),'checkpoint_sha256':sha256(checkpoint),
        'parent_sha256':active_plan.parent_sha256,
        'baseline_checkpoint_sha256':active_plan.parent_sha256,
        'schedule_sha256':active_plan.effective_sha256,
        'maintenance_pass':True,'stage_pass':False,'safety_stop':False,
        'metrics':{'maintenance_counts':{}},'evidence':[],'components':{},
        'graduation_status':'not_judged','evaluation_state':'complete',
        'evaluation_scope':'maintenance_26_and_stand_only'} )
    launched = []

    def fake_child(argv, folder, **_kwargs):
        argv = list(argv)
        scope = argv[argv.index('--scope') + 1]
        launched.append(scope)
        if scope == 'auxiliary':
            score_path = scores / f'score_{iteration}_{sha256(cp)[:12]}.json'
            assert score_path.is_file()
            assert json.loads(score_path.read_text(encoding='utf-8'))['evaluation_state'] == 'complete'
        folder.mkdir(parents=True, exist_ok=True)
        rc = 5 if scope == 'auxiliary' else 0
        (folder / 'child.json').write_text(json.dumps({'state':'done','rc':rc}), encoding='utf-8')
        return {'state':'failed' if rc else 'done','rc':rc,'pid':123}

    monkeypatch.setattr(watch, 'hidden_child', fake_child)
    result = watch.process_once(run, out, scores, TABLE, state, execute=True,
                                sleep=lambda _seconds:None)
    assert result['state'] == 'complete'
    assert launched == (['periodic', 'auxiliary'] if auxiliary_due else ['periodic'])
    if auxiliary_due:
        aux_path = out / f'model_{iteration}_{sha256(cp)[:12]}' / 'stage_end_auxiliary.json'
        assert json.loads(aux_path.read_text(encoding='utf-8'))['state'] == 'HOLD'
        assert state['done'][f'{iteration}_{sha256(cp)}']['state'] == 'complete'
    else:
        assert not (out / f'model_{iteration}_{sha256(cp)[:12]}' / 'stage_end_auxiliary.json').exists()
