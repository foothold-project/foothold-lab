"""No Kit: known completion markers, child receipts, SHA drift and mixed runs."""
import json
from pathlib import Path

import pytest

from foothold_s2.scripts import ex42_remeasure as batch


def write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc))
    return path


@pytest.fixture
def finished(tmp_path):
    run = tmp_path / 'run'; run.mkdir()
    write(run/'manifest.json', {'progress': {'completed_updates':1000},
          'run': {'cli_args': {'max_iterations':1000, 'ex42_speed_probe':False}}})
    write(run/'train_start_status.json', {'state':'done','iter':1000,'log_dir':str(run)})
    return run


def test_done_is_run_specific_and_exactly_1000(finished):
    assert batch.training_done(finished)['state'] == 'done'
    write(finished/'train_start_status.json', {'state':'done','iter':50,'log_dir':str(finished)})
    with pytest.raises(ValueError, match='1000'): batch.training_done(finished)


def test_running_marker_waits_and_done_wrong_run_is_rejected(finished):
    write(finished/'train_start_status.json', {'state':'running','iter':999})
    assert batch.training_done(finished) is None
    write(finished/'train_start_status.json', {'state':'done','iter':1000,'log_dir':'/other'})
    with pytest.raises(ValueError, match='run'): batch.training_done(finished)


def test_missing_or_incomplete_manifest_never_starts(finished):
    write(finished/'manifest.json', {'progress':{'completed_updates':999}})
    with pytest.raises(ValueError): batch.training_done(finished)


def test_gpu_admission_rejects_training_and_unknown_query():
    query=lambda: '12, GPU-a, 512, python\n'
    with pytest.raises(ValueError, match='busy'): batch.require_free_gpus(['GPU-a','GPU-b'], query=query)
    batch.require_free_gpus(['GPU-a','GPU-b'], query=lambda:'12, GPU-a, 512, sunshine\n')
    with pytest.raises(ValueError): batch.require_free_gpus(['GPU-a','GPU-b'], query=lambda:'bad csv')


def test_jobs_preserve_order_and_e1_policy_only_for_parent(tmp_path):
    binding={'run':str(tmp_path/'new'),'plan':{'path':'/new.yaml'},'approvals':{'path':'/new-ap.yaml'}}
    request={'parent':{'path':str(tmp_path/'parent/model_1000.pt')},
             'old':{'run':str(tmp_path/'old'),'plan':{'path':'/old.yaml'},'approvals':{'path':'/old-ap.yaml'}},
             'evaluation_plan':{'path':'/eval.yaml'}, 'evaluation_approvals':{'path':'/eval-ap.yaml'},
             'output':str(tmp_path/'out'), 'python':'/python', 'mesh_dir':'/mesh', 'mesh_sha256':'a'*64}
    jobs=batch.jobs(request,binding)
    assert [(j['group'],j['iteration']) for j in jobs]==[
        ('parent',1000), *[('old',i) for i in [250,500,750,1000]], *[('retrain',i) for i in [250,500,750,1000]]]
    for j in jobs:
        argv=j['argv']
        assert argv[argv.index('--device')+1]=='cuda:1'
        assert argv[argv.index('--split-device')+1]=='cuda:0'
        assert '--next-stage-launcher' not in argv
        assert argv[argv.index('--evaluation-plan')+1]=='/eval.yaml'
    assert jobs[0]['comparison_only'] is True
    assert jobs[-1]['output']==str(tmp_path/'out/retrain/m1000')


def test_zero_rc_without_full_receipts_is_not_complete(tmp_path):
    j={'output':str(tmp_path),'checkpoint_sha256':'a'*64,'iteration':250}
    write(tmp_path/'eval_receipt.json',{'state':'done'})
    with pytest.raises((ValueError, FileNotFoundError)): batch.completed_job(j,'b'*64)


def test_pass_gate_is_required_before_any_flag_or_launch_call(tmp_path):
    gate=write(tmp_path/'p1_score.json',{'state':'complete','judgment':'HOLD'})
    calls=[]
    result=batch.bridge({}, {}, tmp_path, gate, guard=lambda:calls.append('GPU'))
    assert result['state']=='gate_not_passed' and calls==[]


def test_request_pins_fail_on_content_change(tmp_path):
    f=tmp_path/'file';f.write_text('known')
    ref=batch.ref(f);assert batch.checked(ref)==f.resolve()
    f.write_text('changed')
    with pytest.raises(ValueError, match='SHA'):batch.checked(ref)


@pytest.fixture
def complete_job(tmp_path):
    from foothold_s2.eval.map_mode_cells import commands
    checkpoint = tmp_path/'model_250.pt'; checkpoint.write_bytes(b'known checkpoint')
    cp_sha=batch.sha(checkpoint);policy='b'*64;source='c'*64
    measured=write(tmp_path/'ex42_score.json', {'checkpoint_sha256':cp_sha, 'maintenance_source_sha256':policy,
                     'judgement':'HOLD', 'map64':{}, 'cell_judgments':{}})
    matrix=[{'map_mode':m,'command':c,'role':'record_only' if m=='probe_prop_only' else 'judge'}
            for m in ('eval_gt','eval_pred','probe_prop_only') for c in commands('extended')]
    write(tmp_path/'p1_score.json', {'state':'complete','judgment':'HOLD','checkpoint_iteration':250,
         'checkpoint_sha256':cp_sha,'evaluation_plan':{'sha256':policy},'plan_sha256':source,
         'measurement':str(measured),'measurement_sha256':batch.sha(measured),
         'map_matrix':matrix,'judge_count':26,'record_only_count':13})
    write(tmp_path/'eval_receipt.json', {'state':'done','checkpoint_sha256':cp_sha,
         'evaluation_plan':{'sha256':policy},'evaluation_friction_requested':{'plan_sha256':policy,'static':.8,'dynamic':.6}})
    friction={'state':'verified','plan_sha256':policy,'static':.8,'dynamic':.6,'combine_mode':'average',
              'robot':{'shape':[64,17,3],'static_min':.8,'static_max':.8,'dynamic_min':.6,'dynamic_max':.6},
              'terrain':[{'static':.8,'dynamic':.6,'combine_mode':'average'}]}
    for name in ['map64/map_modes.json','axis_v2/axis_v2.json',
                 *[f'stand_{mode}/stand.json' for mode in ('eval_gt','eval_pred','probe_prop_only')],
                 'd44/d44_cells.json']:
        write(tmp_path/name,{'evaluation_friction':friction})
    return {'output':str(tmp_path),'checkpoint':str(checkpoint),'checkpoint_sha256':cp_sha,'iteration':250,
            'source_plan_sha256':source,'group':'old','comparison_only':True},policy


def test_complete_hold_is_evidence_not_a_transport_failure(complete_job):
    job,policy=complete_job
    assert batch.completed_job(job,policy)['judgment']=='HOLD'


@pytest.mark.parametrize('bad',['checkpoint','policy','source','measurement','matrix','friction','actual_friction'])
def test_mixed_or_partial_receipt_rejected(complete_job,bad):
    job,policy=complete_job;root=Path(job['output'])
    path=root/('map64/map_modes.json' if bad=='actual_friction' else 'eval_receipt.json' if bad=='friction' else 'p1_score.json')
    doc=batch.read(path)
    if bad=='checkpoint':doc['checkpoint_sha256']='0'*64
    elif bad=='policy':doc['evaluation_plan']['sha256']='0'*64
    elif bad=='source':doc['plan_sha256']='0'*64
    elif bad=='measurement':doc['measurement_sha256']='0'*64
    elif bad=='matrix':doc['map_matrix'].pop()
    elif bad=='actual_friction':doc['evaluation_friction']['robot']['static_min']=1.
    else:doc['evaluation_friction_requested']['static']=1.
    write(path,doc)
    with pytest.raises(ValueError):batch.completed_job(job,policy)


def test_smoke_done_rejected_even_if_markers_claim_1000(finished):
    manifest=batch.read(finished/'manifest.json');manifest['run']['cli_args']['ex42_speed_probe']=True
    write(finished/'manifest.json',manifest)
    with pytest.raises(ValueError):batch.training_done(finished)


def test_other_run_pass_cannot_reach_flags(tmp_path):
    cp=tmp_path/'model_1000.pt';cp.write_bytes(b'new')
    gate=write(tmp_path/'gate.json',{'state':'complete','judgment':'PASS','stage_id':'E1',
        'checkpoint_iteration':1000,'checkpoint_sha256':'0'*64,'plan_sha256':'a'*64})
    evidence=write(tmp_path/'evidence.json',{})
    with pytest.raises(ValueError,match='only this retrain'):
        batch.bridge({}, {'run':str(tmp_path),'plan':{'sha256':'a'*64},
                          'manifest':batch.ref(evidence),'training_log':batch.ref(evidence)},
                     tmp_path,gate,guard=lambda:pytest.fail('GPU'))


# Actual publication and automatic authorization over known CPU traces. Only the
# Kit producer and the training-entry process are substituted, not the validators.
from foothold_s2.tests import test_ex42_calibration_materialize_cpu as chain_tests

known = chain_tests.known
ready = chain_tests.ready


@pytest.mark.parametrize('actual_frozen_source,dry_rc', [(False,0), (True,0), (False,2)])
def test_old_source_new_policy_gate_to_e1f_uses_materialize_and_real_authorization(ready, monkeypatch, actual_frozen_source, dry_rc):
    import shutil
    from types import SimpleNamespace
    from foothold_s2.scripts import ex42_flag_baseline_chain as flag_module
    from foothold_s2.scripts import ex42_e1_materialize_evidence as evidence_module
    root=ready['out'].parent/'bridge';root.mkdir()
    if actual_frozen_source:
        old=Path('/home/jay/mai/wt/foothold-lab/ex42-launch-b379eb98/foothold_s2/curriculum/ex42-prep.yaml')
        if not old.is_file(): pytest.skip('actual frozen b379 source not mounted')
        import yaml
        ready['source_plan']=old
        log=ready['parent_manifest'].parent/'torchrun.stdout.log'
        import re
        log.write_text(re.sub(r'"approvals_sha256": "[a-f0-9]+"',
             '\"approvals_sha256\": \"'+yaml.safe_load(old.read_text())['stage_zero']['approval_sha256']+'\"',log.read_text()))
    gate=batch.read(ready['gate_receipt'])
    gate['plan_sha256']=batch.sha(ready['source_plan'])
    measured=Path(gate['measurement']);score=batch.read(measured)
    score['maintenance_source_sha256']=batch.sha(ready['plan']);write(measured,score)
    gate['measurement_sha256']=batch.sha(measured);write(ready['gate_receipt'],gate)
    ev=batch.read(ready['evidence']);ev['gate_sha256']=batch.sha(ready['gate_receipt']);ev['source_plan_sha256']=batch.sha(ready['source_plan'])
    ev['evaluation_plan']=batch.ref(ready['plan']);ev['exposure_receipt']=batch.ref(ready['parent_manifest'].parent/'torchrun.stdout.log');write(ready['evidence'],ev)
    chain=batch.read(ready['flag_chain']);chain['e1_gate']['sha256']=batch.sha(ready['gate_receipt'])
    chain['e1_gate']['measurement_sha256']=gate['measurement_sha256'];write(ready['flag_chain'],chain)
    mesh=Path(chain['mesh_dir']);write(mesh/'terrain_manifest.json',{})
    calls=[]
    def produced(*args,**kwargs):
        assert kwargs['devices']==('cuda:0','cuda:1') and kwargs['execute'] is True
        target=args[1];target.mkdir()
        # Keep original artifact paths in the receipt, exactly as real publication supports.
        shutil.copy2(ready['flag_chain'],target/'chain_receipt.json')
        shutil.copy2(chain['w09_baseline']['path'],target/'w09_baseline.json')
    def evidence(**kwargs):
        assert kwargs['source_plan_path']==ready['source_plan']
        assert kwargs['evaluation_plan_path']==ready['plan']
        calls.append('evidence')
        shutil.copy2(ready['evidence'],kwargs['out_path'])
    monkeypatch.setattr(flag_module,'run_chain',produced)
    monkeypatch.setattr(evidence_module,'write_evidence',evidence)
    def cpu(argv,**kwargs):
        assert '--ex42_stage_dry_run' in argv and kwargs['env']['CUDA_VISIBLE_DEVICES']==''
        assert any(a=='--max_iterations=750' for a in argv)
        calls.append('cpu-dry-argv');return SimpleNamespace(returncode=dry_rc)
    monkeypatch.setattr(batch.subprocess,'run',cpu)
    binding={'run':str(ready['parent_manifest'].parent), 'plan':batch.ref(ready['source_plan']),
             'manifest':batch.ref(ready['parent_manifest']),
             'training_log':batch.ref(ready['parent_manifest'].parent/'torchrun.stdout.log')}
    req={'evaluation_plan':batch.ref(ready['plan']),'evaluation_approvals':batch.ref(ready['approvals']),
         'mesh_dir':str(mesh),'mesh_sha256':chain['mesh_sha256'],'python':'/cpu/python',
         'launch_env':{'EX42_MESH_DIR':str(mesh),'EX42_MESH_SHA256':chain['mesh_sha256'],
                       'GPU_JOBS_QUEUE':'/not-live-queue.json','EX42_SOURCE_REF':'fixture',
                       'EX42_MAIN_ROOT':str(root/'future-training')}}
    if dry_rc:
        with pytest.raises(ValueError,match='CPU preflight refused: rc 2'):
            batch.bridge(req,binding,root,ready['gate_receipt'],guard=lambda:None,launch=False)
        assert not (root/'E1F-adoption.json').exists()
        return
    result=batch.bridge(req,binding,root,ready['gate_receipt'],guard=lambda:None,launch=False)
    assert result['state']=='ready_not_started' and calls==['evidence','cpu-dry-argv']
    transition=batch.read(root/'E1F-materialized/transition.json')
    assert transition['prior_plan_sha']==binding['plan']['sha256']
    assert transition['gate_sha256']==batch.sha(ready['gate_receipt'])
    assert transition['new_plan_sha']==batch.sha(root/'E1F-materialized/ex42-prep.yaml')
    assert not (root/'next_stage_launch.json').exists()
    assert batch.read(root/'E1F-adoption.json')['budget_used']==1250


@pytest.mark.parametrize('fail_child', [None, 4, 'tamper'])
def test_all_nine_complete_before_bridge_and_child_failure_stays_hold(tmp_path, complete_job, monkeypatch, fail_child):
    from contextlib import contextmanager
    from types import SimpleNamespace
    import shutil
    template,policy=complete_job
    root=tmp_path/'batch';run=tmp_path/'new';old=tmp_path/'old';parent=tmp_path/'parent'
    for directory in (run,old,parent):
        directory.mkdir()
        for n in batch.UPDATES:(directory/f'model_{n}.pt').write_bytes(f'{directory.name}-{n}'.encode())
        write(directory/'manifest.json', {'checkpoints':{f'model_{n}.pt':batch.sha(directory/f'model_{n}.pt') for n in batch.UPDATES}})
    binding={'run':str(run),'plan':{'path':'/new.yaml','sha256':'c'*64},
             'approvals':{'path':'/ap.yaml'},'manifest':{'path':str(run/'manifest.json')},
             'startup':{'path':'/startup.json'},'training_log':{'path':'/log'}}
    request={'source_git_head':'fixture','evaluation_plan':{'path':'/eval.yaml','sha256':policy},
        'evaluation_approvals':{'path':'/eval-ap.yaml'},'parent':{'path':str(parent/'model_1000.pt')},
        'old':{'run':str(old),'plan':{'path':'/old.yaml','sha256':'c'*64},'approvals':{'path':'/ap.yaml'}},
        'output':str(root),'python':'/cpu/python','mesh_dir':'/mesh','mesh_sha256':'a'*64,
        'launch_env':{'GPU_JOBS_QUEUE':'/queue','EX42_MAIN_ROOT':'/out','EX42_SOURCE_REF':'fixture'},
        'retrain_binding':str(write(tmp_path/'binding.json', {'run':str(run),'training_log':'/log','expected_plan_sha256':'c'*64}))}
    calls=[]
    monkeypatch.setattr(batch,'validate_request',lambda r:None)
    monkeypatch.setattr(batch,'training_done',lambda r:{'state':'done'})
    monkeypatch.setattr(batch,'source_binding',lambda *args:binding)
    monkeypatch.setattr(batch,'checked',lambda r:Path(r['path']))
    @contextmanager
    def no_gpu(*args):
        def guard():
            if fail_child=='tamper':(parent/'model_1000.pt').write_bytes(b'changed after pin')
        yield guard
    notices=[]
    monkeypatch.setattr(batch,'notify_hold',lambda output,reason:notices.append(reason) or {'sent':True})
    monkeypatch.setattr(batch,'admission',no_gpu)
    def child(argv,**kwargs):
        index=len(calls);calls.append(argv)
        if index==fail_child:return SimpleNamespace(returncode=5)
        dest=Path(argv[argv.index('--out')+1]);cp=Path(argv[argv.index('--checkpoint')+1])
        dest.mkdir(parents=True)
        for p in Path(template['output']).glob('*.json'):shutil.copy2(p,dest/p.name)
        for sub in ('map64','axis_v2','stand_eval_gt','stand_eval_pred','stand_probe_prop_only','d44'):
            shutil.copytree(Path(template['output'])/sub,dest/sub)
        for name in ('ex42_score.json','eval_receipt.json','p1_score.json'):
            doc=batch.read(dest/name);doc['checkpoint_sha256']=batch.sha(cp)
            if name=='p1_score.json':
                doc.update(checkpoint_iteration=int(cp.stem.split('_')[-1]),measurement=str(dest/'ex42_score.json'),
                           measurement_sha256=batch.sha(dest/'ex42_score.json'),
                           plan_sha256=policy if index==0 else 'c'*64)
            elif name=='eval_receipt.json':doc['source_git_head']='fixture'
            write(dest/name,doc)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(batch.subprocess,'run',child)
    def no_launch(req,bnd,out,gate,**kwargs):
        assert len(calls)==9 and batch.read(out/'comparison.json')['count']==9
        assert Path(gate)==root/'retrain/m1000/p1_score.json'
        return {'state':'gate_not_passed','training_started':False}
    monkeypatch.setattr(batch,'bridge',no_launch)
    if fail_child is None:
        batch.execute(request)
        assert batch.read(root/'batch_receipt.json')['state']=='complete'
    elif fail_child=='tamper':
        with pytest.raises(ValueError,match='checkpoint changed before evaluation'):batch.execute(request)
        assert calls==[] and notices
    else:
        with pytest.raises(ValueError,match='child rc=5'):batch.execute(request)
        assert len(calls)==5 and batch.read(root/'batch_receipt.json')['state']=='HOLD'
        assert not (root/'comparison.json').exists()


def test_queue_live_owner_blocks_cpu_reservation(tmp_path):
    import os
    queue=write(tmp_path/'queue.json',{'format':'foothold-gpu-queue/1','items':[{'id':1,'state':'실행','gpu':0,'external':False,'pid':os.getpid()}]})
    before=queue.read_bytes()
    with pytest.raises(ValueError,match='queue still occupied'):batch.reserve_queue(queue,tmp_path/'not-live.log')
    assert queue.read_bytes()==before


def test_missing_d44_actual_friction_receipt_rejected(complete_job):
    job,policy=complete_job
    (Path(job['output'])/'d44/d44_cells.json').unlink()
    with pytest.raises(FileNotFoundError):batch.completed_job(job,policy)


def test_same_checkpoint_different_gate_plan_is_refused_before_flags(tmp_path):
    cp=tmp_path/'model_1000.pt';cp.write_bytes(b'known')
    gate=write(tmp_path/'gate.json',{'state':'complete','judgment':'PASS','stage_id':'E1',
        'checkpoint_iteration':1000,'checkpoint_sha256':batch.sha(cp),'plan_sha256':'b'*64})
    evidence=write(tmp_path/'evidence.json',{})
    with pytest.raises(ValueError,match='only this retrain'):
        batch.bridge({}, {'run':str(tmp_path),'plan':{'sha256':'a'*64},
                          'manifest':batch.ref(evidence),'training_log':batch.ref(evidence)},
                     tmp_path,gate,guard=lambda:pytest.fail('GPU'))


def test_dirty_source_refused_even_with_all_other_pins_valid(tmp_path,monkeypatch):
    p=tmp_path/'p';p.write_text('known');pin=batch.ref(p)
    request={'source_git_head':'known','evaluation_plan':pin,'evaluation_approvals':pin,'parent':pin,
             'dependencies':[],'old':{k:pin for k in ('plan','approvals','manifest','startup')}}
    monkeypatch.setattr(batch.subprocess,'check_output',lambda argv,**kwargs:'known\n' if 'rev-parse' in argv else ' M foothold_s2/changed.py\n')
    with pytest.raises(ValueError,match='not clean'):batch.validate_request(request)


@pytest.mark.parametrize('rc',[0,4])
def test_hold_notice_uses_run_inbox_and_preserves_delivery_failure(tmp_path,rc):
    from types import SimpleNamespace
    calls=[]
    def fake(argv,**kwargs):
        calls.append(argv);return SimpleNamespace(returncode=rc,stdout='fake messageId' if rc==0 else '',stderr='busy' if rc else '')
    result=batch.notify_hold(tmp_path,'gate HOLD',runner=fake)
    argv=calls[0]
    assert argv[argv.index('--to')+1]=='run:run_5283fa2c059b' and 'terminal' not in argv
    assert result['sent'] is (rc==0) and batch.read(tmp_path/'notification.json')['returncode']==rc
