from __future__ import annotations

import json
from pathlib import Path

import pytest

from foothold_s2 import ex41_score_watch as watch
from foothold_s2.ex41_eval_once import commands
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
    assert watch.due_evaluation_scopes(1750, plan, hold_run) == ('core',)
    assert watch.due_evaluation_scopes(2250, plan, hold_run) == ('core', 'auxiliary')

    extension_run = tmp_path / 'extension_run';extension_run.mkdir()
    _clock_log(extension_run, plan, extension=True)
    extension_ends = watch.stage_end_updates(plan, extension_run)
    assert 5000 in extension_ends and 5500 in extension_ends
    assert watch.due_evaluation_scopes(5000, plan, extension_run) == ('core', 'auxiliary')
    assert watch.due_evaluation_scopes(5500, plan, extension_run) == ('core', 'auxiliary')


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


def test_scope_commands_keep_w78_out_of_250_core_and_include_it_at_stage_end(tmp_path):
    cfg = watch.config(watch.DEFAULT_CONFIG)
    cp = tmp_path / 'model_250.pt'
    cp.write_bytes(b'known checkpoint bytes')
    core = commands(cp, tmp_path / 'core', cfg, scope='core')
    auxiliary = commands(cp, tmp_path / 'aux', cfg, scope='auxiliary')
    assert [row['name'] for row in core] == [
        'map64', 'stand_eval_gt', 'stand_probe_prop_only', 'stand_eval_pred']
    assert [row['name'] for row in auxiliary] == ['axis_v2', 'w78_v2']
    assert '--terrain-skill-v2' in auxiliary[-1]['argv']
    assert all('--terrain-skill-v2' not in row['argv'] for row in core)


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
    assert launched == (['core', 'auxiliary'] if auxiliary_due else ['core'])
    if auxiliary_due:
        aux_path = out / f'model_{iteration}_{sha256(cp)[:12]}' / 'stage_end_auxiliary.json'
        assert json.loads(aux_path.read_text(encoding='utf-8'))['state'] == 'HOLD'
        assert state['done'][f'{iteration}_{sha256(cp)}']['state'] == 'complete'
    else:
        assert not (out / f'model_{iteration}_{sha256(cp)[:12]}' / 'stage_end_auxiliary.json').exists()
