from __future__ import annotations

import json
from pathlib import Path

import pytest

from foothold_s2 import ex41_score_watch as watch
from foothold_s2.ex41_eval_once import commands
from foothold_s2.curriculum.continuous import load_plan
from foothold_s2.ex40_score import sha256


TABLE = watch.DEFAULT_TABLE


def test_fixed_plan_stage_ends_drive_auxiliary_scope_and_measured_queue_load():
    plan = load_plan(TABLE, arm='B')
    assert watch.stage_end_updates(plan) == (750, 1750, 2750, 4000, 4500, 5000)
    assert watch.due_evaluation_scopes(250, plan) == ('core',)
    assert watch.due_evaluation_scopes(500, plan) == ('core',)
    assert watch.due_evaluation_scopes(750, plan) == ('core', 'auxiliary')
    assert [row['end_update'] for row in watch.stage_interval_loads(
        plan, train_seconds_per_update=27, core_seconds=1093,
        auxiliary_seconds=9480)] == [750, 1750, 2750, 4000, 4500, 5000]
    loads = watch.stage_interval_loads(plan, train_seconds_per_update=27,
                                       core_seconds=1093, auxiliary_seconds=9480)
    assert [row['core_checkpoints'] for row in loads] == [3, 4, 4, 5, 2, 2]
    assert all(row['queue_growth_seconds'] == 0 for row in loads)
    assert loads[-2]['evaluation_seconds'] == 11666
    assert loads[-2]['training_seconds'] == 13500


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
