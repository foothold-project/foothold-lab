"""Actual EX40 outputs replayed through EX41; no invented evaluation success."""
import json
from pathlib import Path
from copy import deepcopy
import shutil
import sys

import numpy as np
import pytest

from foothold_s2 import ex41_score_watch as watch
from foothold_s2 import ex41_eval_once as evaluator
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


def test_real_m6000_maintenance_complete_without_w78(tmp_path):
    cp,folder=native(6000);plan=load_plan(TABLE,arm='B')
    row=watch.collect(cp,'S2a',folder,plan)
    assert row['components']['maintenance_stand']=='complete'
    assert row['evaluation_state']=='complete' and row['maintenance_pass'] and not row['stage_pass']
    assert 'w78_v2' in row['auxiliary_missing'] and 'critic_mirror_symmetry' in row['auxiliary_missing']
    assert len(row['metrics']['maintenance_counts'])==26
    expected=json.loads(Path(plan.fixed_schedule['maintenance_baseline']['path']).read_text(encoding='utf-8'))
    recorded=row['metrics']['record_counts'];assert len(recorded)==39
    for key,value in recorded.items(): assert value['passed']==expected['cells'][key]['alive_envs_at_end']


def test_eval_pred_map_error_is_recorded_with_npz_hash_and_no_decision_effect(tmp_path):
    folder=tmp_path/'map64';folder.mkdir()
    raw=folder/'env_arrays_eval_pred_fwd1.0.npz'
    np.savez(raw,env=np.arange(3),alive_end=np.array([True,True,False]),
             map_err_inrange_mean_cm=np.array([2.0,4.0,np.nan],dtype=np.float32),
             map_err_all_mean_cm=np.array([8.0,10.0,99.0],dtype=np.float32),
             map_err_inrange_steps=np.array([20,10,0],dtype=np.int32))
    source=folder/'map_modes.json'
    source.write_text(json.dumps({'env_arrays':{'eval_pred/fwd1.0':raw.name},
                                  'modes':{'eval_pred':{'fwd1.0':{}}}}),encoding='utf-8')
    got,refs=watch.eval_pred_map_error_record_only(source)
    cell=got['cases']['fwd1.0']
    assert got['decision_use']=='none_record_only'
    assert cell['inrange_mean_cm']=={'finite_envs':2,'mean_cm':3.0,'median_cm':3.0}
    assert cell['all_cells_mean_cm']=={'finite_envs':3,'mean_cm':39.0,'median_cm':10.0}
    assert cell['inrange_step_count']==30 and len(refs)==1 and refs[0]['sha256']==sha256(raw)


def test_eval_pred_map_error_record_only_rejects_missing_npz(tmp_path):
    source=tmp_path/'map_modes.json'
    source.write_text(json.dumps({'env_arrays':{'eval_pred/fwd1.0':'absent.npz'},
                                  'modes':{'eval_pred':{'fwd1.0':{}}}}),encoding='utf-8')
    with pytest.raises(OSError):
        watch.eval_pred_map_error_record_only(source)


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
    # Known interruption, not lack of W78, creates the first HOLD.
    (tmp_path/'out'/f'model_5750_{sha256(run/"model_5750.pt")[:12]}').mkdir(parents=True)
    def tick():return watch.process_once(run,tmp_path/'out',tmp_path/'scores',TABLE,state,
        replay_root=SOURCE/'score-watch-b',w57_root=SOURCE/'axis250',sleep=lambda _:None)
    first=tick();assert first['iteration']==5750 and first['state']=='HOLD'
    second=tick();assert second['iteration']==6000 and second['state']=='complete'
    assert tick()['state']=='idle' and len(state['done'])==2
    plan=load_plan(TABLE,arm='B')
    runtime=EX41FixedRuntime(plan,4,'cpu',tmp_path/'runtime',tmp_path/'scores')
    runtime.effective={'stage_id':'S2a'};runtime.stage_entry_iteration=1
    rows=runtime._read_scores(6001)
    assert [r['iteration'] for r in rows]==[6000]
    assert any(r['iteration']==5750 for r in runtime._score_rejections.values())
    assert len((tmp_path/'out/score_ledger.jsonl').read_text(encoding='utf-8').splitlines())==2


def test_default_dry_never_calls_child_or_creates_score(tmp_path,monkeypatch):
    run=replay_run(tmp_path);state=watch.initial_state(run,TABLE,watch.DEFAULT_CONFIG)
    monkeypatch.setattr(watch,'hidden_child',lambda *a,**k:pytest.fail('DRY spawned a process'))
    row=watch.process_once(run,tmp_path/'out',tmp_path/'scores',TABLE,state,sleep=lambda _:None)
    assert row['state']=='dry' and len(row['commands'])==5
    assert row['commands'][-1]['name']=='w78_v2_sides'
    side_args=row['commands'][-1]['argv']
    assert side_args[side_args.index('--terrain-skill-v2-cases')+1]=='stairs_side_left,stairs_side_right'
    assert row['auxiliary_due'] is False and row['auxiliary_commands']==[]
    assert not (tmp_path/'scores').exists() and not state['done']


def test_auxiliary_root_resolves_w57_bundle_phase_and_iteration_layouts(tmp_path):
    cp = tmp_path/'model_10.pt'; cp.write_bytes(b'fixture')
    model_root = tmp_path/'axis250'/'model_10'; model_root.mkdir(parents=True)
    expected = model_root/'axis_v2.json'; expected.write_text('{}', encoding='utf-8')
    assert watch.resolve_auxiliary_path(tmp_path/'axis250', 10, 'axis_v2.json') == expected

    bundle = tmp_path/'bundle'; phase = bundle/'axis_v2'; phase.mkdir(parents=True)
    phase_file = phase/'axis_v2.json'; phase_file.write_text('{}', encoding='utf-8')
    assert watch.resolve_auxiliary_path(bundle, 10, 'axis_v2.json') == phase_file
    assert watch.resolve_auxiliary_path(phase, 10, 'axis_v2.json') == phase_file


def test_missing_w57_during_running_bundle_is_pending_not_file_not_found(tmp_path):
    bundle = tmp_path/'bundle'; bundle.mkdir()
    receipt = bundle/'eval_receipt.json'
    receipt.write_text(json.dumps({'state':'running'}), encoding='utf-8')
    assert watch.auxiliary_pending_during_bundle(bundle, bundle/'axis_v2/axis_v2.json')
    receipt.write_text(json.dumps({'state':'HOLD'}), encoding='utf-8')
    assert not watch.auxiliary_pending_during_bundle(bundle, bundle/'axis_v2/axis_v2.json')


def test_zero_exit_with_w78_hold_error_makes_bundle_hold_and_nonzero(tmp_path):
    error_dir = tmp_path/'w78_v2'; error_dir.mkdir()
    (error_dir/'terrain_skill_v2.error.json').write_text(json.dumps({
        'state':'HOLD', 'reason':'known W78 HOLD', 'completed':0, 'expected':240,
    }), encoding='utf-8')
    child = {'state':'done', 'rc':0, 'pid':123}
    result = evaluator.reconcile_child_result('w78_v2', child, error_dir)
    steps = {name:{'state':'done','rc':0} for name in evaluator.CORE_PHASES}
    steps['w78_v2'] = result
    terminal = evaluator.bundle_terminal_status(steps)
    assert result['process_rc'] == 0 and result['state'] == 'HOLD' and result['rc'] != 0
    assert terminal == {'state':'done', 'rc':0,
                        'auxiliary_missing':['axis_v2','w78_v2','push_ladder','a_push_video']}


def test_commands_gpu1_three_modes_w57_then_w78_and_fresh_output(tmp_path):
    rows=commands(Path('model_250.pt'),tmp_path,config(watch.DEFAULT_CONFIG),gpu0_training_active=False)
    assert [r['name'] for r in rows]==[
        'map64','stand_eval_gt','stand_probe_prop_only','stand_eval_pred',
        'axis_v2','w78_v2','push_ladder','a_push_video']
    for r in rows:
        a=r['argv'];assert a[a.index('--device')+1]==r['device']
        assert not Path(a[a.index('--out')+1]).exists()
    assert rows[-2]['device'] == 'cuda:0'
    assert '--axis-v2' in rows[4]['argv']
    assert '--a-layer-marker' in rows[-1]['argv']
    assert '--fixed-level' not in rows[-1]['argv']


def test_hidden_child_actual_stdin_devnull_and_separate_streams(tmp_path,monkeypatch):
    original=evaluator.subprocess.Popen;observed=[]
    def checked(*args,**kwargs):
        observed.append(kwargs)
        assert kwargs.get('stdin')==evaluator.subprocess.DEVNULL
        return original(*args,**kwargs)
    monkeypatch.setattr(evaluator.subprocess,'Popen',checked)
    code="import sys; assert sys.stdin.read()==''; print('actual stdout'); print('actual stderr',file=sys.stderr)"
    row=hidden_child([sys.executable,'-c',code],tmp_path/'child')
    assert row['rc']==0 and row['stdin']=='DEVNULL' and row['pid']>0
    assert len(observed)==1
    assert 'actual stdout' in (tmp_path/'child/stdout.log').read_text(encoding='utf-8')
    assert 'actual stderr' in (tmp_path/'child/stderr.log').read_text(encoding='utf-8')


def test_dr_on_actual_map_document_rejected(tmp_path):
    cp,folder=native(6000);dest=tmp_path/'bundle/map64';dest.mkdir(parents=True)
    data=json.loads((folder/'map64/map_modes.json').read_text(encoding='utf-8'))
    for mode in watch.MODES:
        shutil.copytree(folder/f'stand_{mode}',dest.parent/f'stand_{mode}')
    (dest/'map_modes.json').write_text(json.dumps(data))
    good=watch.collect(cp,'S2a',dest.parent,load_plan(TABLE,arm='B'))
    assert good['components']['maintenance_stand']=='complete'
    data['dr']={'enabled':True}
    (dest/'map_modes.json').write_text(json.dumps(data))
    row=watch.collect(cp,'S2a',dest.parent,load_plan(TABLE,arm='B'))
    assert row['components']['maintenance_stand'].startswith('HOLD') and row['metrics']=={}
    assert 'DR' in row['components']['maintenance_stand']


def test_w57_false_yaw_summary_detected_against_original_raw(tmp_path):
    cp,_=native(5750);source=SOURCE/'axis250/model_5750'
    doc=json.loads((source/'axis_v2.json').read_text(encoding='utf-8'))
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
    assert tick()['iteration']==6000 and (partial/'old.log').read_text(encoding='utf-8')=='preserve exact prior partial'


def test_real_json_wrong_sha_mutation_cannot_be_published_as_success(tmp_path):
    cp,folder=native(6000);dst=tmp_path/'map64';dst.mkdir()
    data=json.loads((folder/'map64/map_modes.json').read_text(encoding='utf-8'));data['checkpoint_sha256']='0'*64
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


@pytest.mark.parametrize('late',[False,True])
def test_final_request_same_sha_before_or_after_regular_score_never_waits_forever(tmp_path,late):
    run=replay_run(tmp_path);plan=load_plan(TABLE,arm='B')
    application=watch.read(run/'ex41_application.jsonl')
    application.update(stage_after='T0_prime',after={'stage_id':'T0_prime'})
    (run/'ex41_application.jsonl').write_text(json.dumps(application)+'\n')
    (run/'train_start_status.json').write_text(json.dumps({'state':'done'}))
    state=watch.initial_state(run,TABLE,watch.DEFAULT_CONFIG)
    def tick():return watch.process_once(run,tmp_path/'out',tmp_path/'scores',TABLE,state,
        replay_root=SOURCE/'score-watch-b',sleep=lambda _:None)
    cp=run/'model_6000.pt';sha=sha256(cp)
    req={'format':'foothold-ex41-final-eval-request/1','training_finished':True,'graduated':False,
        'checkpoint':{'iteration':6000,'path':str(cp.resolve()),'sha256':sha},'stage_id':'T0_prime',
        'parent_sha256':plan.parent_sha256,'schedule_sha256':plan.effective_sha256,'plan_sha256':plan.sha256}
    req['request_id']=watch.digest(req)
    def publish():
        dest=run/'final_eval_requests';dest.mkdir()
        (dest/f'final_6000_{sha[:12]}.json').write_text(json.dumps(req))
    if not late:publish()
    assert tick()['iteration']==5750
    regular=tick();assert regular['iteration']==6000
    score_path=Path(regular['score_path']);score_bytes=score_path.read_bytes()
    attempt=tmp_path/'out'/f'model_6000_{sha[:12]}'/'attempt.json';attempt_bytes=attempt.read_bytes()
    if late:
        publish()
        assert watch.completion(run,plan,state)['state']=='waiting_for_final_request_score'
        linked=tick();assert linked['state']=='final_request_linked'
        assert watch.read(linked['link_path'])['request_id']==req['request_id']
        assert score_path.read_bytes()==score_bytes and attempt.read_bytes()==attempt_bytes
        # A crash after receipt publication but before state persistence reuses it.
        state.pop('final_links'); assert tick()['state']=='final_request_linked'
        assert len(list((tmp_path/'out/final_links').glob('*.json')))==1
    assert tick()['state']=='idle'
    assert watch.completion(run,plan,state)=={'state':'complete','hold_count':0,
                                             'training_state':'done','graduated':False}
    if late:
        Path(linked['link_path']).write_text('{}')
        failed=watch.completion(run,plan,state)
        assert failed['state']=='final_request_error' and not failed['graduated']
        assert 'final link' in failed['reason']


def replay_tick(tmp,run,state):
    return watch.process_once(run,tmp/'out',tmp/'scores',TABLE,state,
                              replay_root=SOURCE/'score-watch-b',sleep=lambda _:None)


def test_crash_after_score_before_attempt_finalization_recovers_immutable_score(tmp_path,monkeypatch):
    run=replay_run(tmp_path);state=watch.initial_state(run,TABLE,watch.DEFAULT_CONFIG)
    original=watch._atomic
    def crash(path,row):
        if path.name=='attempt.json' and row.get('state')=='complete':
            raise OSError('injected death after score publication')
        return original(path,row)
    monkeypatch.setattr(watch,'_atomic',crash)
    with pytest.raises(OSError,match='injected'):replay_tick(tmp_path,run,state)
    path=next((tmp_path/'scores').glob('score_5750_*.json'));before=path.read_bytes()
    attempt=next((tmp_path/'out').glob('model_5750_*/attempt.json'));partial=attempt.read_bytes()
    assert not state['done'] and watch.read(attempt)['state']=='running'
    monkeypatch.setattr(watch,'_atomic',original)
    recovered=replay_tick(tmp_path,run,state)
    assert recovered['iteration']==5750 and recovered['state']=='complete' and recovered['recovered_from_score']
    assert path.read_bytes()==before and attempt.read_bytes()==partial
    assert len(list((tmp_path/'out/recoveries').glob('*.json')))==1
    assert replay_tick(tmp_path,run,state)['iteration']==6000
    # Losing only state after recovery does not create a second evaluation.
    state=watch.initial_state(run,TABLE,watch.DEFAULT_CONFIG)
    assert replay_tick(tmp_path,run,state)['recovered_from_score']
    assert len(list((tmp_path/'out/recoveries').glob('*.json')))==1


def test_two_interrupted_folders_and_no_receipt_preserved_and_next_runs(tmp_path):
    run=replay_run(tmp_path);state=watch.initial_state(run,TABLE,watch.DEFAULT_CONFIG)
    name=f'model_5750_{sha256(run/"model_5750.pt")[:12]}'
    for suffix in ('','_interrupted'):
        p=tmp_path/'out'/(name+suffix);p.mkdir(parents=True)
        (p/'partial.txt').write_text(suffix or 'original')
    row=replay_tick(tmp_path,run,state)
    assert row['state']=='HOLD' and row['iteration']==5750
    scored=watch.read(row['score_path'])
    assert scored['metrics']=={} and scored['components']['maintenance_stand']=='complete'
    assert 'prior interrupted' in scored['components']['evaluation_child']
    assert (tmp_path/'out'/name/'partial.txt').read_text()=='original'
    assert (tmp_path/'out'/(name+'_interrupted')/'partial.txt').read_text()=='_interrupted'
    assert (tmp_path/'out'/(name+'_interrupted_001')/'attempt.json').is_file()
    assert replay_tick(tmp_path,run,state)['state']=='complete'


def test_stale_pending_never_blocks_publication_or_next_checkpoint(tmp_path):
    run=replay_run(tmp_path);state=watch.initial_state(run,TABLE,watch.DEFAULT_CONFIG)
    scores=tmp_path/'scores';scores.mkdir()
    stale=scores/f'score_5750_{sha256(run/"model_5750.pt")[:12]}.pending'
    stale.write_bytes(b'{interrupted')
    assert replay_tick(tmp_path,run,state)['state']=='complete'
    assert stale.read_bytes()==b'{interrupted'
    assert replay_tick(tmp_path,run,state)['iteration']==6000


def test_main_loop_replays_actual_outputs_past_hold_until_final_receipt(tmp_path,monkeypatch):
    run=replay_run(tmp_path)
    (tmp_path/'out'/f'model_5750_{sha256(run/"model_5750.pt")[:12]}').mkdir(parents=True)
    (run/'train_start_status.json').write_text(json.dumps({'state':'stopped_saved'}))
    stable=watch._stable
    monkeypatch.setattr(watch,'_stable',lambda p,t,s:stable(p,0,lambda _:None))
    monkeypatch.setattr(watch.time,'sleep',lambda _:None)
    rc=watch.main(['--run-dir',str(run),'--out-root',str(tmp_path/'out'),
                   '--score-dir',str(tmp_path/'scores'),'--replay-root',str(SOURCE/'score-watch-b')])
    assert rc==5
    saved=watch.read(tmp_path/'out/watch_state.json')
    assert [(r['iteration'],r['state']) for r in saved['done'].values()]==[(5750,'HOLD'),(6000,'complete')]
    end=watch.read(tmp_path/'out/watch_completion.json')
    assert end['state']=='complete_with_hold' and end['hold_count']==1 and not end['graduated']


def test_w78_unintegrated_coordinator_still_schedules_map_stand_w57(tmp_path,monkeypatch):
    # Coordinator-only spy, not a claim that mocked children measured anything.
    root=tmp_path/'source';p=root/'foothold_s2/eval';p.mkdir(parents=True)
    (p/'eval_map_modes.py').write_text('# no W78 parser',encoding='utf-8')
    plan=load_plan(evaluator.DEFAULT_TABLE,arm='B')
    baseline_relative=Path(plan.fixed_schedule['push_baseline']['path'])
    baseline_source=(Path(evaluator.ROOT)/baseline_relative).resolve(strict=True)
    baseline_target=root/baseline_relative
    baseline_target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(baseline_source,baseline_target)
    monkeypatch.setattr(evaluator,'ROOT',root)
    monkeypatch.setattr(evaluator.subprocess,'check_output',lambda args,**kw:'' if 'status' in args else '1'*40)
    launched=[]
    def spy(argv,folder,**kwargs):
        launched.append(folder.name)
        # An auxiliary failure also must not turn maintenance into failed rc.
        return {'rc':7,'state':'failed'} if folder.name=='axis_v2' else {'rc':0,'state':'done'}
    monkeypatch.setattr(evaluator,'hidden_child',spy)
    row=evaluator.evaluate(native(6000)[0],tmp_path/'evaluation',priority_marker=tmp_path/'p1-marker')
    assert launched==['map64','stand_eval_gt','stand_probe_prop_only','stand_eval_pred',
                      'axis_v2','push_ladder','a_push_video']
    assert row['state']=='done' and row['rc']==0 and row['auxiliary_missing']==[
        'axis_v2','w78_v2','push_ladder','a_push_video']


def test_stage_receipt_at_next_update_does_not_relabel_previous_checkpoint(tmp_path):
    run=replay_run(tmp_path);plan=load_plan(TABLE,arm='B')
    row=watch.read(run/'ex41_application.jsonl')
    second={**row,'iteration':251,'stage_after':'S2b','after':{'stage_id':'S2b'}}
    with (run/'ex41_application.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(second)+'\n')
    assert watch.stage_at(run,250,plan)=='S2a'
    assert watch.stage_at(run,251,plan)=='S2b'
    # local250, not parent6000 + local250. Parent identity is independently pinned.
    row['parent_update']=5999
    (run/'ex41_application.jsonl').write_text(json.dumps(row)+'\n')
    with pytest.raises(ValueError,match='identity'):watch.stage_at(run,250,plan)


def test_stage_end_auxiliary_receipt_records_a_push_videos_and_holds_missing_receipts(
        tmp_path, monkeypatch):
    from foothold_s2.eval import a_push_video

    checkpoint = tmp_path / 'model_6000.pt'
    checkpoint.write_bytes(b'known EX41 stage checkpoint')
    video_dir = tmp_path / 'a_push_video'
    video_dir.mkdir()
    modes = a_push_video.MODES
    monkeypatch.setattr(a_push_video, 'compare_mode_receipts', lambda _path: {
        'state': 'complete', 'group_id': 'known-stage-group', 'modes': list(modes)})
    for mode in modes:
        video_path = video_dir / f'{mode}.mp4'
        video_path.write_bytes(f'known {mode} video'.encode())
        (video_dir / f'{mode}.json').write_text(json.dumps({
            'schema': 'foothold-ex41-a-push-video/1',
            'map_mode': mode,
            'iteration': 6000,
            'checkpoint_sha256': watch.sha256(checkpoint),
            'cadence': 'stage_end',
            'video_rule_version': 'v3.4-D168',
            'outcome': 'captured',
            'video': str(video_path),
            'video_sha256': watch.sha256(video_path),
        }), encoding='utf-8')

    plan = watch.load_plan(watch.DEFAULT_TABLE, arm='B')
    missing = watch.stage_end_auxiliary_receipt(
        checkpoint, 'B0', tmp_path / 'missing-core', tmp_path / 'missing-w57',
        tmp_path / 'missing-w78', plan)
    assert missing['components']['a_push_video'].startswith('HOLD:')

    recorded = watch.stage_end_auxiliary_receipt(
        checkpoint, 'B0', tmp_path / 'missing-core', tmp_path / 'missing-w57',
        tmp_path / 'missing-w78', plan, a_push_video_path=video_dir)
    assert recorded['components']['a_push_video'] == 'complete'
    assert recorded['metrics']['a_push_video']['decision_use'] == 'record_only'
    assert recorded['metrics']['a_push_video']['video_rule_version'] == 'v3.4-D168'
    assert set(recorded['metrics']['a_push_video']['map_modes']) == set(modes)


def test_g11_p9_stage_video_receipts_remain_pending_scene_review(tmp_path):
    checkpoint = tmp_path / 'model_750.pt'
    checkpoint.write_bytes(b'known EX41 stage checkpoint')
    stage = 'S2a'
    video_root = tmp_path / 'stage_video'
    receipt_root = video_root / 'receipts'
    receipt_root.mkdir(parents=True)
    _, cases = watch._stage_video_contract()
    for suite, case, mode in cases:
        identity = watch._stage_video_identity(checkpoint, 750, stage, suite, case, mode)
        video = video_root / f'{identity}.mp4'
        video.write_bytes(f'known {suite} {case} {mode}'.encode())
        (receipt_root / f'{identity}.json').write_text(json.dumps({
            'schema':'foothold-ex41-stage-video/1','id':identity,
            'suite':suite,'case':case,'map_mode':mode,'iteration':750,
            'stage_name':stage,'checkpoint_sha256':watch.sha256(checkpoint),
            'source_head':'3af5b2057fb138357e6ff656abaeb5d8e2194b24',
            'video_rule_version':'v3.4-D168','video':str(video),
            'video_sha256':watch.sha256(video)}), encoding='utf-8')
    plan = watch.load_plan(watch.DEFAULT_TABLE, arm='B')
    row = watch.stage_end_auxiliary_receipt(
        checkpoint, stage, tmp_path / 'missing-core', tmp_path / 'missing-w57',
        tmp_path / 'missing-w78', plan, stage_video_path=video_root)
    assert row['metrics']['stage_video']['count'] == 51
    assert row['metrics']['stage_video']['acceptance'] == 'pending_lead_kit_scene_review'
    assert row['components']['stage_video'] == 'captured_pending_lead_kit_scene_review'


def test_stage_end_push_ladder_consumes_shared_39_child_contract(tmp_path, monkeypatch):
    from foothold_s2.eval.ex41_push_ladder_bundle import bundle_cases
    from foothold_s2.eval.ex41_push_ladder_contract import PUSH_LADDER_EXPECTED_CHILDREN

    checkpoint = tmp_path / 'model_6000.pt'
    checkpoint.write_bytes(b'known EX41 stage checkpoint')
    monkeypatch.setattr(watch, 'measure_w57', lambda *_a: ({'known': True}, []))
    monkeypatch.setattr(watch, 'measure_w78', lambda *_a: ({'known': True}, []))
    children = []
    for case in bundle_cases():
        children.append({
            **case, 'state': 'done',
            'summary': {'maximum_tolerated_mps': 1.5,
                        'magnitudes': {'1.5': {'survival_fraction': 0.95}}},
        })
    push_path = tmp_path / 'push_ladder_bundle.json'
    push_path.write_text(json.dumps({
        'schema': 'foothold-ex41-push-ladder-bundle/1', 'state': 'done',
        'checkpoint_sha256': watch.sha256(checkpoint),
        'expected_children': PUSH_LADDER_EXPECTED_CHILDREN,
        'children': children,
    }), encoding='utf-8')
    plan = watch.load_plan(watch.DEFAULT_TABLE, arm='B')

    accepted = watch.stage_end_auxiliary_receipt(
        checkpoint, 'B0', tmp_path / 'core', tmp_path / 'w57', tmp_path / 'w78',
        plan, push_ladder_path=push_path)
    assert accepted['components']['push_ladder'] == 'complete'
    assert len(accepted['metrics']['push_ladder']['maximum_tolerated_by_condition']) == 39

    children.pop()
    push_path.write_text(json.dumps({
        'schema': 'foothold-ex41-push-ladder-bundle/1', 'state': 'done',
        'checkpoint_sha256': watch.sha256(checkpoint),
        'expected_children': PUSH_LADDER_EXPECTED_CHILDREN,
        'children': children,
    }), encoding='utf-8')
    rejected = watch.stage_end_auxiliary_receipt(
        checkpoint, 'B0', tmp_path / 'core', tmp_path / 'w57', tmp_path / 'w78',
        plan, push_ladder_path=push_path)
    assert rejected['components']['push_ladder'].startswith('HOLD: ValueError')


def test_dead_watcher_lock_archived_but_live_owner_never_reclaimed(tmp_path):
    import os
    import subprocess
    child=subprocess.Popen([sys.executable,'-c','pass'],stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    assert child.wait()==0
    lock=tmp_path/'watch.lock';raw=json.dumps({'pid':child.pid}).encode()
    lock.write_bytes(raw)
    watch.acquire_watch_lock(lock)
    assert next(tmp_path.glob('watch.lock.dead.*')).read_bytes()==raw
    assert watch.read(lock)['pid']==os.getpid()
    with pytest.raises(ValueError,match='live'):watch.acquire_watch_lock(lock)
    assert watch.read(lock)['pid']==os.getpid()


def test_w78_producer_to_p3_metric_no_hand_inserted_runtime_scalar(tmp_path):
    # Known-input W78 contract fixture, not measured robot performance.
    # Map/stand still use untouched EX40 outputs. The real JSON reader and
    # collect() must produce the derived metric consumed by runtime.
    from foothold_s2.curriculum.ex41_symmetry import validate
    from foothold_s2.eval.eval_dr_mode import EXPECTED_DR_OFF
    cp,folder=native(6000);plan=load_plan(TABLE,arm='B')
    raw=tmp_path/'known.npz';np.savez(raw,known=np.array([1.4,.7]))
    data={'schema':'foothold-terrain-skill-v2/1','state':'done','checkpoint_sha256':sha256(cp),
        'checkpoint_iter':6000,'envs':64,'levels':[2,5],'start_angles_deg':[0,30,60,90],
        'modes':{},'w78_min_lr_ratio':{},'dr_off':list(EXPECTED_DR_OFF)}
    for mode in watch.MODES:
        data['modes'][mode]={}
        for level in (2,5):
            for angle in (0,30,60,90):
                for name in watch.W78_CASES:
                    data['modes'][mode][f'L{level}_a{angle:03d}_{name}']={
                        'level':level,'stair_start_angle_deg':angle,'case':name,
                        'terrain_assignment_sha256':'a'*64,'raw_file':raw.name,'raw_sha256':sha256(raw),
                        'terrain_tiles':[{'env':i,'level':level} for i in range(64)],
                        'per_env':[{'env':i} for i in range(64)],'by_terrain_kind':{}}
                for kind in ('pyramid_stairs','pyramid_stairs_inv'):
                    data['w78_min_lr_ratio'][f'L{level}_a{angle:03d}_{mode}_{kind}']={
                        'left':1.4,'right':.7,'min_lr_ratio':.7}
    path=tmp_path/'terrain_skill_v2.json';path.write_text(json.dumps(data))
    row=watch.collect(cp,'S2a',folder,plan,w78_path=path)
    assert row['components']['critic_mirror_symmetry']=='complete'
    metric=row['metrics']['critic_mirror_symmetry'];validate(metric)
    assert metric['modes']['eval_gt']['w78/L2_a000_pyramid_stairs']['symmetry']==.5
    assert len(row['metrics']['w78_v2']['min_lr_ratio_by_cell'])==48
    assert row['metrics']['w78_v2']['min_lr_ratio_by_cell']==data['w78_min_lr_ratio']
    assert 'w78_min_lr_ratio' not in row['metrics']  # no ambiguous scalar
    scores=tmp_path/'scores';scores.mkdir()
    watch.immutable(scores/f'score_6000_{sha256(cp)[:12]}.json',row)
    runtime=EX41FixedRuntime(plan,4,'cpu',tmp_path/'runtime',scores)
    runtime.effective={'stage_id':'S2a'};runtime.stage_entry_iteration=1
    loaded=runtime._read_scores(6001)
    assert len(loaded)==1 and loaded[0]['metrics']['critic_mirror_symmetry']==metric
    # Broken auxiliary numbers stay missing without destroying the 26 counts.
    data['modes']['eval_gt']['L2_a000_stairs_fwd']['per_env'][0]['untrusted_metric']=float('nan')
    path.write_text(json.dumps(data))
    bad=watch.collect(cp,'S2a',folder,plan,w78_path=path)
    assert bad['evaluation_state']=='complete' and len(bad['metrics']['maintenance_counts'])==26
    assert 'w78_v2' in bad['auxiliary_missing'] and 'critic_mirror_symmetry' in bad['auxiliary_missing']

    # D166 periodic receipt: only the exact side pair is accepted, while its
    # derived S is combined with all 39 core counts and the complete map64 set.
    sides=deepcopy(data)
    selected=set(watch.W78_PERIODIC_SIDE_CASES)
    sides['case_selection']=list(watch.W78_PERIODIC_SIDE_CASES)
    sides['modes']={mode:{key:row for key,row in cases.items()
                          if row['case'] in selected}
                    for mode,cases in sides['modes'].items()}
    partial=tmp_path/'terrain_skill_v2_sides.json'
    partial.write_text(json.dumps(sides),encoding='utf-8')
    side_metrics,side_refs=watch.measure_w78(partial,cp,
                                              selected_cases=watch.W78_PERIODIC_SIDE_CASES)
    assert len(side_metrics['min_lr_ratio_by_cell'])==48 and len(side_refs)==49
    periodic=watch.collect(cp,'S2a',folder,plan,periodic_w78_path=partial,
                           include_auxiliary=False)
    assert periodic['evaluation_state']=='complete'
    assert periodic['evaluation_scope']=='maintenance_39_and_periodic_w78_sides; graduation_not_judged'
    assert len(periodic['metrics']['record_counts'])==39
    assert periodic['components']['critic_mirror_symmetry']=='complete'
    assert periodic['metrics']['critic_mirror_symmetry']['modes']['eval_gt']['w78/L2_a000_pyramid_stairs']['symmetry']==.5


def test_execute_measurement_failure_retries_same_checkpoint_and_separates_judgement(tmp_path, monkeypatch):
    run = replay_run(tmp_path)
    plan = load_plan(TABLE, arm='B')
    manifest_path = run / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['modes'] = {'ex41': {'effective_sha256': plan.effective_sha256,
                                  'plan_sha256': plan.sha256,
                                  'parent': {'sha256': plan.parent_sha256}}}
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    state = watch.initial_state(run, TABLE, watch.DEFAULT_CONFIG)
    monkeypatch.setattr(watch, '_stable', lambda path, *_args: sha256(path))
    children = iter(({'rc':7,'state':'failed','pid':91}, {'rc':0,'state':'done','pid':92}))
    def child(_argv, folder, **_kwargs):
        folder.mkdir(parents=True, exist_ok=False)
        result = next(children)
        (folder / 'child.json').write_text(json.dumps(result), encoding='utf-8')
        return result
    monkeypatch.setattr(watch, 'hidden_child', child)
    def collection(_cp, _stage, _bundle, _plan, *args, **kwargs):
        failed = kwargs.get('force_failed', False)
        return {'evaluation_state':'HOLD' if failed else 'complete',
                'maintenance_pass':False, 'stage_pass':False, 'metrics':{} if failed else {'counts':{}},
                'components':{'maintenance_stand':'HOLD: child rc=7' if failed else 'complete'},
                'evidence':[], 'auxiliary_missing':[]}
    # First child failure is converted into a missing collection, then second
    # collection is a real, complete measurement whose decision happens to HOLD.
    results = iter((
        {'evaluation_state':'HOLD','maintenance_pass':False,'stage_pass':False,'metrics':{},
         'components':{'maintenance_stand':'HOLD: child rc=7'},'evidence':[],'auxiliary_missing':[]},
        {'evaluation_state':'complete','maintenance_pass':False,'stage_pass':False,'metrics':{'counts':{}},
         'components':{'maintenance_stand':'complete'},'evidence':[],'auxiliary_missing':[]},
    ))
    monkeypatch.setattr(watch, 'collect', lambda *_args, **_kwargs: next(results))
    out, scores = tmp_path / 'out', tmp_path / 'scores'
    first = watch.process_once(run, out, scores, TABLE, state, execute=True,
                               sleep=lambda _seconds:None)
    assert first['state'] == 'measurement_retry_pending'
    assert first['measurement_state'] == 'failed_retryable'
    assert first['judgement_state'] == 'not_judged'
    assert not list(scores.glob('score_5750_*.json'))
    second = watch.process_once(run, out, scores, TABLE, state, execute=True,
                                sleep=lambda _seconds:None)
    assert second['state'] == 'complete'
    assert second['measurement_state'] == 'complete'
    assert second['judgement_state'] == 'hold'
    assert second['attempt_count'] == 2
    score = json.loads(Path(second['score_path']).read_text(encoding='utf-8'))
    assert score['measurement_state'] == 'complete' and score['judgement_state'] == 'hold'
    assert len(state['measurement_failures'][f"5750_{sha256(run/'model_5750.pt')}"]) == 1


def test_three_remeasurements_leave_gap_and_allow_next_boundary(tmp_path, monkeypatch):
    run = replay_run(tmp_path)
    plan = load_plan(TABLE, arm='B')
    manifest_path = run / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['modes'] = {'ex41': {'effective_sha256': plan.effective_sha256,
                                  'plan_sha256': plan.sha256,
                                  'parent': {'sha256': plan.parent_sha256}}}
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    out, scores = tmp_path / 'out', tmp_path / 'scores'
    schedule = run / 'ex41_reports' / 'rehearsal_schedule.json'
    schedule.parent.mkdir(parents=True, exist_ok=True)
    rehearsal_config = schedule.parent / 'eval_config.json'
    shutil.copy2(watch.DEFAULT_CONFIG, rehearsal_config)
    schedule.write_text(json.dumps({
        'format': 'foothold-ex41-short-stage-rehearsal/1',
        'stage_updates': [1, 1, 1, 1, 1, 1],
        'eval_config_path': str(rehearsal_config.resolve()),
        'inject_measurement_failure_at': 5750,
        'inject_measurement_failure_count': watch.MAX_TECHNICAL_MEASUREMENT_ATTEMPTS,
        'w72_evidence_allowed': False,
    }), encoding='utf-8')
    state = watch.initial_state(run, TABLE, watch.DEFAULT_CONFIG)
    checkpoint_sha = sha256(run / 'model_5750.pt')
    key = f'5750_{checkpoint_sha}'
    monkeypatch.setattr(watch, 'plan_for_run', lambda *_a, **_k: plan)
    monkeypatch.setattr(watch, 'candidates', lambda *_a, **_k: [
        (5750, run / 'model_5750.pt', None), (6000, run / 'model_6000.pt', None)])
    monkeypatch.setattr(watch, '_stable', lambda path, *_args: sha256(path))
    monkeypatch.setattr(watch, 'stage_at', lambda *_a, **_k: 'T0_prime')
    monkeypatch.setattr(watch, 'due_evaluation_scopes', lambda *_a, **_k: ('periodic',))
    monkeypatch.setattr(watch, 'hidden_child',
                        lambda *_a, **_k: pytest.fail('injected failures must precede Kit'))
    gap = None
    for attempt in range(1, watch.MAX_TECHNICAL_MEASUREMENT_ATTEMPTS + 1):
        result = watch.process_once(run, out, scores, TABLE, state, execute=True,
                                    sleep=lambda _seconds: None)
        if attempt < watch.MAX_TECHNICAL_MEASUREMENT_ATTEMPTS:
            assert result['state'] == 'measurement_retry_pending'
            assert result['attempt_count'] == attempt
        else:
            gap = result
    assert gap['state'] == 'measurement_gap'
    assert gap['remeasurements_used'] == 3
    assert gap['result_eligible'] is False and gap['score_path'] is None
    assert key not in state['done'] and (scores / f'score_5750_{checkpoint_sha[:12]}.json').exists() is False
    gap_path = Path(gap['gap_path'])
    persisted_gap = json.loads(gap_path.read_text(encoding='utf-8'))
    assert persisted_gap['dr_action'] == 'leave_missing_for_dr_hold_missing_evidence'
    assert persisted_gap['failed_attempt_count'] == 4
    assert state['rehearsal_injected_failure_counts'][key] == 4
    alert_path = run / 'ex41_reports' / 'alerts.jsonl'
    first_alert = alert_path.read_text(encoding='utf-8').splitlines()
    assert len(first_alert) == 1 and json.loads(first_alert[0])['kind'] == 'p1_measurement_gap'

    def child(_argv, folder, **_kwargs):
        folder.mkdir(parents=True, exist_ok=False)
        row = {'state': 'done', 'rc': 0, 'pid': 92}
        (folder / 'child.json').write_text(json.dumps(row), encoding='utf-8')
        return row

    monkeypatch.setattr(watch, 'hidden_child', child)
    monkeypatch.setattr(watch, 'collect', lambda *_a, **_k: {
        'evaluation_state': 'complete', 'maintenance_pass': False, 'stage_pass': False,
        'metrics': {'counts': {}}, 'components': {'maintenance_stand': 'complete'},
        'evidence': [], 'auxiliary_missing': []})
    next_boundary = watch.process_once(run, out, scores, TABLE, state, execute=True,
                                      sleep=lambda _seconds: None)
    assert next_boundary['state'] == 'complete' and next_boundary['iteration'] == 6000
    assert key not in state['done']
    assert f"6000_{sha256(run / 'model_6000.pt')}" in state['done']
    assert key in state['measurement_gaps']
    assert len(alert_path.read_text(encoding='utf-8').splitlines()) == 1
