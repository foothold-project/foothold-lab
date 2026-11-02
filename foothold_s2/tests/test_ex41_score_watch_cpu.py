"""Actual EX40 outputs replayed through EX41; no invented evaluation success."""
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pytest

from foothold_s2 import ex41_score_watch as watch
from foothold_s2.ex41_eval_once import commands, hidden_child
from foothold_s2.curriculum.continuous import load_plan
from foothold_s2.curriculum.ex41_fixed import EX41FixedRuntime
from foothold_s2.ex40_score import config, sha256

SOURCE = Path('C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313')
RUN = SOURCE/'main/EX-40-B-main_20261031_041337_26240'
TABLE = watch.DEFAULT_TABLE


def native(n):
    cp=RUN/f'model_{n}.pt'
    return cp,SOURCE/'score-watch-b'/f'model_{n}_{sha256(cp)[:12]}'


def test_real_m5750_w57_recomputed_from_all30_npz():
    cp,_=native(5750)
    got,refs=watch.measure_w57(SOURCE/'axis250/model_5750/axis_v2.json',cp,config(watch.DEFAULT_CONFIG))
    assert len(refs)==31 and set(got)==set(watch.MODES)
    assert all(len(cases)==10 for cases in got.values())
    raw=SOURCE/'axis250/model_5750/axis_v2_eval_gt_fwd1.0.npz'
    with np.load(raw) as z:
        total=[]
        for i in range(64):
            valid=z['alive'][:,i].astype(bool)
            if valid.any():
                y=np.r_[z['start_yaw'][i],z['yaw'][valid,i]]
                total.append(np.abs(np.arctan2(np.sin(np.diff(y)),np.cos(np.diff(y)))).sum())
    assert got['eval_gt']['fwd1.0']['absolute_accum_median_rad']==pytest.approx(float(np.median(total)),abs=1e-6)


def test_real_m6000_counts_preserved_but_missing_w78_is_not_complete(tmp_path):
    cp,folder=native(6000);plan=load_plan(TABLE,arm='B')
    row=watch.collect(cp,'S2a',folder,plan)
    assert row['components']['maintenance_stand']=='complete'
    assert row['evaluation_state']=='HOLD' and not row['maintenance_pass'] and not row['stage_pass']
    assert row['metrics']=={} and len(row['partial_metrics']['maintenance_counts'])==26
    expected=json.loads(Path(plan.fixed_schedule['maintenance_baseline']['path']).read_text())
    recorded=row['partial_metrics']['record_counts'];assert len(recorded)==39
    for key,value in recorded.items(): assert value['passed']==expected['cells'][key]['alive_envs_at_end']


def replay_run(tmp):
    run=tmp/'run';run.mkdir()
    pins={}
    for n in (5750,6000):
        cp,_=native(n);shutil.copy2(cp,run/cp.name);pins[cp.name]=sha256(cp)
    (run/'manifest.json').write_text(json.dumps({'schema':'foothold-manifest/1',
        'progress':{'completed_updates':6001},'checkpoints':pins}))
    # Only coordinator metadata is a test fixture; all measured numbers and model bytes are real.
    (run/'ex41_application.jsonl').write_text(json.dumps({'format':'foothold-ex41-application/1',
        'status':'applied','iteration':1,'parent_update':6000,'stage_after':'S2a','after':{'stage_id':'S2a'}})+'\n')
    return run


def test_actual_replay_hold_does_not_starve_next_checkpoint_or_become_old_pass(tmp_path):
    run=replay_run(tmp_path);state=watch.initial_state(run,TABLE,watch.DEFAULT_CONFIG)
    def tick():return watch.process_once(run,tmp_path/'out',tmp_path/'scores',TABLE,state,
        replay_root=SOURCE/'score-watch-b',w57_root=SOURCE/'axis250',sleep=lambda _:None)
    first=tick();assert first['iteration']==5750 and first['state']=='HOLD'
    second=tick();assert second['iteration']==6000 and second['state']=='HOLD'
    assert tick()['state']=='idle' and len(state['done'])==2
    plan=load_plan(TABLE,arm='B')
    runtime=EX41FixedRuntime(plan,4,'cpu',tmp_path/'runtime',tmp_path/'scores')
    runtime.effective={'stage_id':'S2a'};runtime.stage_entry_iteration=1
    assert runtime._read_scores(6001)==[]
    assert any(r['iteration']==6000 for r in runtime._score_rejections.values())
    assert len((tmp_path/'out/score_ledger.jsonl').read_text().splitlines())==2


def test_default_dry_never_calls_child_or_creates_score(tmp_path,monkeypatch):
    run=replay_run(tmp_path);state=watch.initial_state(run,TABLE,watch.DEFAULT_CONFIG)
    monkeypatch.setattr(watch,'hidden_child',lambda *a,**k:pytest.fail('DRY spawned a process'))
    row=watch.process_once(run,tmp_path/'out',tmp_path/'scores',TABLE,state,sleep=lambda _:None)
    assert row['state']=='dry' and len(row['commands'])==6
    assert not (tmp_path/'scores').exists() and not state['done']


def test_commands_gpu1_three_modes_w57_then_w78_and_fresh_output(tmp_path):
    rows=commands(Path('model_250.pt'),tmp_path,config(watch.DEFAULT_CONFIG))
    assert [r['name'] for r in rows]==['map64','stand_eval_gt','stand_probe_prop_only','stand_eval_pred','axis_v2','w78_v2']
    for r in rows:
        a=r['argv'];assert a[a.index('--device')+1]=='cuda:1'
        assert not Path(a[a.index('--out')+1]).exists()
    assert '--terrain-skill-v2' in rows[-1]['argv'] and '--axis-v2' in rows[-2]['argv']
    assert '--fixed-level' not in rows[-1]['argv']


def test_hidden_child_actual_stdin_devnull_and_separate_streams(tmp_path):
    code="import sys; assert sys.stdin.read()==''; print('actual stdout'); print('actual stderr',file=sys.stderr)"
    row=hidden_child([sys.executable,'-c',code],tmp_path/'child')
    assert row['rc']==0 and row['stdin']=='DEVNULL' and row['pid']>0
    assert 'actual stdout' in (tmp_path/'child/stdout.log').read_text()
    assert 'actual stderr' in (tmp_path/'child/stderr.log').read_text()


def test_dr_on_actual_map_document_rejected(tmp_path):
    cp,folder=native(6000);dest=tmp_path/'bundle/map64';dest.mkdir(parents=True)
    data=json.loads((folder/'map64/map_modes.json').read_text());data['dr']={'enabled':True}
    (dest/'map_modes.json').write_text(json.dumps(data))
    row=watch.collect(cp,'S2a',dest.parent,load_plan(TABLE,arm='B'))
    assert row['components']['maintenance_stand'].startswith('HOLD') and row['metrics']=={}


def test_w57_false_yaw_summary_detected_against_original_raw(tmp_path):
    cp,_=native(5750);source=SOURCE/'axis250/model_5750'
    doc=json.loads((source/'axis_v2.json').read_text())
    doc['modes']['eval_gt']['fwd0.5']['per_env'][0]['yaw_signed_accum_rad']=999.
    # Copy untouched real NPZ bytes into an isolated corrupted-summary experiment.
    for mode in doc['modes'].values():
        for row in mode.values():shutil.copy2(source/row['raw_file'],tmp_path/row['raw_file'])
    (tmp_path/'axis_v2.json').write_text(json.dumps(doc))
    with pytest.raises(ValueError,match='disagrees'):watch.measure_w57(tmp_path/'axis_v2.json',cp,config(watch.DEFAULT_CONFIG))


def test_interrupted_old_folder_is_hold_and_next_actual_checkpoint_runs(tmp_path):
    run=replay_run(tmp_path);state=watch.initial_state(run,TABLE,watch.DEFAULT_CONFIG)
    digest=sha256(run/'model_5750.pt');partial=tmp_path/'out'/f'model_5750_{digest[:12]}'
    partial.mkdir(parents=True);(partial/'old.log').write_text('preserve exact prior partial')
    def tick():return watch.process_once(run,tmp_path/'out',tmp_path/'scores',TABLE,state,
        replay_root=SOURCE/'score-watch-b',w57_root=SOURCE/'axis250',sleep=lambda _:None)
    assert tick()['state']=='HOLD'
    assert tick()['iteration']==6000 and (partial/'old.log').read_text()=='preserve exact prior partial'


def test_real_json_wrong_sha_mutation_cannot_be_published_as_success(tmp_path):
    cp,folder=native(6000);dst=tmp_path/'map64';dst.mkdir()
    data=json.loads((folder/'map64/map_modes.json').read_text());data['checkpoint_sha256']='0'*64
    (dst/'map_modes.json').write_text(json.dumps(data))
    row=watch.collect(cp,'S2a',tmp_path,load_plan(TABLE,arm='B'))
    assert row['components']['maintenance_stand'].startswith('HOLD') and row['evaluation_state']=='HOLD'


def test_training_done_is_not_implicit_final_score_or_graduation(tmp_path):
    run=replay_run(tmp_path);plan=load_plan(TABLE,arm='B')
    (run/'train_start_status.json').write_text(json.dumps({'state':'done','iter':6000}))
    state=watch.initial_state(run,TABLE,watch.DEFAULT_CONFIG)
    assert watch.completion(run,plan,state)['state']=='waiting_for_remaining_scores'
    for n in (5750,6000):
        sha=sha256(run/f'model_{n}.pt');state['done'][f'{n}_{sha}']={'state':'HOLD'}
    assert watch.completion(run,plan,state)['state']=='waiting_for_final_checkpoint_request'
