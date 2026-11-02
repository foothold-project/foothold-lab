"""Real state-machine consumers with known CPU evidence, no simulator import."""
import copy
from pathlib import Path
from types import SimpleNamespace
import pytest
import torch
import yaml
import json
from datetime import datetime,timezone
from foothold_s2.curriculum.continuous import sha256
from foothold_s2.curriculum.continuous import load_plan, make_runtime
from foothold_s2.curriculum import w72

TABLE=Path(__file__).parents[1]/'curriculum/ex41.yaml'


def snapshot():
    return dict(commit='a'*40,config_sha256='b'*64,approval_sha256='c'*64,
                config=yaml.safe_load(TABLE.with_name('ex41-boundary.yaml').read_text()),
                approvals=yaml.safe_load(TABLE.with_name('ex41-approvals.yaml').read_text()))


def runtime(tmp_path,monkeypatch):
    snap=snapshot()
    monkeypatch.setattr(w72,'read_committed_pair',lambda *a: copy.deepcopy(snap))
    p=load_plan(TABLE,arm='B'); r=make_runtime(p,4,'cpu',tmp_path)
    r.set_stage_changed_hook(lambda s,e: copy.deepcopy(e))
    r.start(p.parent_sha256)
    return r,snap


def test_n0_to_first_rollout_preserves_dr_and_episode_command_version(tmp_path,monkeypatch):
    r,_=runtime(tmp_path,monkeypatch)
    assert r.effective['dr']['scale']==1.
    r.on_update_start(1)
    assert r.plan.stages[r.active].id=='S2a'
    assert r.env_stage.tolist()==[0]*4
    r.on_reset(torch.tensor([1,3]))
    assert r.env_stage[1]==r.active and r.env_stage[0]==0
    assert r.plan.stages[0].shares['forward']==.25
    assert r.plan.stages[r.active].shares['forward']==.23


def test_rejected_boundary_keeps_previous_and_no_callback(tmp_path,monkeypatch):
    r,snap=runtime(tmp_path,monkeypatch); r.on_update_start(1)
    calls=[]; r.set_stage_changed_hook(lambda s,e: calls.append(e) or e)
    snap['config']['values']['ppo']['clip_param']=.1
    before=copy.deepcopy(r.effective)
    r.on_update_start(251)
    assert not calls
    assert r.effective==before
    assert r.boundary_receipt()['status']=='rejected'


def test_resume_preserves_boundary_state_and_never_repeats_receipt(tmp_path,monkeypatch):
    r,_=runtime(tmp_path/'a',monkeypatch); r.on_update_start(1)
    state=r.state_dict()
    p=load_plan(TABLE,arm='B'); b=make_runtime(p,4,'cpu',tmp_path/'b',segment_index=1)
    b.set_stage_changed_hook(lambda s,e: e)
    b.load_state_dict(state)
    assert b.effective==r.effective and b.stage_entry_iteration==1
    b.on_update_start(1)
    assert b.boundary_receipt()==r.boundary_receipt()


def test_resume_changed_mirror_approval_stays_off_and_records_rejection(tmp_path,monkeypatch):
    r,_=runtime(tmp_path/'a',monkeypatch); r.on_update_start(1)
    values=copy.deepcopy(r._config_values); values['critic_mirror']=True
    assert r._apply(1,251,values,[],None,'known enabled mirror')
    state=r.state_dict()
    b=make_runtime(load_plan(TABLE,arm='B'),4,'cpu',tmp_path/'b',segment_index=1)
    calls=[]
    def hook(stage,e):
        calls.append(e['critic_mirror'])
        if e['critic_mirror']: raise ValueError('W72 actual approval bytes changed after save')
        return e
    b.set_stage_changed_hook(hook)
    b.load_state_dict(state)
    assert calls==[True,False]
    assert b.effective['critic_mirror'] is False
    assert b.boundary_receipt()['status']=='rejected'
    assert b.boundary_receipt()['reason'].startswith('resume_mirror_rejected_off')
    b.on_update_start(2)
    assert not b.stop_requested


def test_failed_application_rolls_back(tmp_path,monkeypatch):
    r,_=runtime(tmp_path,monkeypatch)
    calls=[]
    def apply(stage,e):
        calls.append(stage.id)
        if stage.id=='S2a': raise ValueError('known failed consumer')
        return e
    r.set_stage_changed_hook(apply)
    r.on_update_start(1)
    assert calls==['S2a','S2-0']
    assert r.plan.stages[r.active].id=='S2-0'
    assert r.boundary_receipt()['status']=='rejected'


def test_wrong_consumed_readback_is_rejected_before_command_version(tmp_path,monkeypatch):
    r,_=runtime(tmp_path,monkeypatch)
    def hook(stage,e):
        out=copy.deepcopy(e)
        if stage.id=='S2a': out['ppo']['entropy_coef']=.09
        return out
    r.set_stage_changed_hook(hook); r.on_update_start(1)
    assert r.effective['stage_id']=='S2-0'
    assert r.boundary_receipt()['status']=='rejected'
    assert 'readback differs' in r.boundary_receipt()['reason']


def test_mirror_authorization_matches_shared_fixture(tmp_path,monkeypatch):
    r,_=runtime(tmp_path,monkeypatch)
    fixture=json.loads((Path(__file__).parent/'fixtures/ex41_authorization.json').read_text())
    fixture.update(boundary_file=str(r.plan.boundary_path.resolve()),
                   approval_file=str(r.plan.approvals_path.resolve()))
    values=copy.deepcopy(r._config_values); values['critic_mirror']=True
    assert r._apply(1,501,values,[dict(path='critic_mirror',before=False,after=True,decision_id='D101')],None,'boundary_config')
    assert r.effective['authorization']==fixture
    assert r.boundary_receipt()['readback']['authorization']==fixture


def test_changed_approval_after_snapshot_rolls_back_mirror_off(tmp_path,monkeypatch):
    from foothold_s2.tests.ex41_authorization_fixture import real_authorization
    auth=real_authorization(tmp_path/'committed')
    r,_=runtime(tmp_path/'run',monkeypatch)
    r.plan.boundary_path=Path(auth['boundary_file']); r.plan.approvals_path=Path(auth['approval_file'])
    r._snapshot={
        'commit':auth['config_commit'],'config_sha256':auth['config_sha256'],'approval_sha256':auth['approval_sha256']}
    actual={'mirror':False,'calls':[]}
    def setter_hook(stage,e):
        a=e['authorization']; actual['calls'].append(e['critic_mirror'])
        if e['critic_mirror']:
            if sha256(a['boundary_file'])!=a['config_sha256'] or sha256(a['approval_file'])!=a['approval_sha256']:
                actual['mirror']=False
                raise ValueError('W72 actual bytes changed after snapshot')
            assert a==auth
        actual['mirror']=e['critic_mirror']
        return copy.deepcopy(e)
    r.set_stage_changed_hook(setter_hook)
    v=copy.deepcopy(r._config_values); v['critic_mirror']=True
    dec=[dict(path='critic_mirror',before=False,after=True,decision_id='D101')]
    assert r._apply(1,501,v,dec,None,'boundary_config')
    assert actual['mirror'] and r.effective['authorization']==auth
    with r.plan.approvals_path.open('a') as f: f.write('# real file changed after snapshot\n')
    assert not r._apply(1,751,v,[],None,'boundary_config')
    assert actual['calls'][-3:]==[True,True,False]
    assert not actual['mirror'] and not r.effective['critic_mirror']
    assert r.boundary_receipt()['status']=='rejected'
    assert r.boundary_receipt()['rollback_error'] and not r.boundary_receipt()['after']['critic_mirror']
    assert not r.stop_requested


def test_real_stage_hook_catches_setter_valueerror_and_keeps_learning(tmp_path,monkeypatch):
    from functools import partial
    from foothold_s2.curriculum.ex41 import apply_runtime_fields
    r,_=runtime(tmp_path,monkeypatch)
    env=SimpleNamespace(scene=SimpleNamespace(terrain=SimpleNamespace(
        terrain_origins=torch.zeros(10,2,3),terrain_levels=torch.tensor([0,1,2,0]))),
        cfg=SimpleNamespace(episode_length_s=20.))
    runner=SimpleNamespace(env=SimpleNamespace(unwrapped=env),alg=SimpleNamespace(
        entropy_coef=.01,desired_kl=.01,mirror_enabled=False),ex41_critic_mirror=False,continuous_curriculum=r)
    def setter(enabled,approval=None):
        runner.ex41_critic_mirror=False; runner.alg.mirror_enabled=False
        if enabled: raise ValueError('EX-41 W72 HOLD: changed actual approval')
    runner.set_ex41_critic_mirror=setter
    r.set_stage_changed_hook(partial(apply_runtime_fields,runner))
    values=copy.deepcopy(r._config_values); values['critic_mirror']=True
    assert not r._apply(1,501,values,[dict(path='critic_mirror',before=False,after=True,decision_id='D101')],None,'boundary_config')
    assert not r.effective['critic_mirror'] and not runner.ex41_critic_mirror
    assert r.boundary_receipt()['status']=='rejected' and 'W72 HOLD' in r.boundary_receipt()['reason']
    r.on_update_start(1)
    assert r.effective['stage_id']=='S2a' and not r.stop_requested


def test_capped_performance_term_and_spin_neutral():
    from foothold_s2.curriculum.ex41 import ex41_terrain_levels,terrain_distribution
    levels=torch.tensor([5,4,0,2])
    cfg=SimpleNamespace(curriculum=True,num_cols=2,num_rows=10,size=(8.,8.),
        sub_terrains={'flat':SimpleNamespace(proportion=.5),'rough':SimpleNamespace(proportion=.5)})
    terrain=SimpleNamespace(terrain_levels=levels,terrain_types=torch.tensor([0,0,1,1]),
        cfg=SimpleNamespace(terrain_generator=cfg))
    def move(ids,up,down): levels[ids]+=up.long()-down.long()
    terrain.update_env_origins=move
    term=SimpleNamespace(cmd_sum_w=torch.tensor([[200.,0],[200.,0],[200.,0],[0.,0]]),
        max_dist=torch.tensor([5.,5.,0.,0.]),is_flag_env=torch.zeros(4,dtype=torch.bool))
    env=SimpleNamespace(device='cpu',step_dt=.02,scene=SimpleNamespace(terrain=terrain),
        command_manager=SimpleNamespace(get_term=lambda k:term),_ex41_terrain={'policy':'performance','level_cap':5})
    ex41_terrain_levels(env,torch.arange(4))
    assert levels.tolist()==[5,5,0,2]
    manifest=terrain_distribution(env)
    assert manifest['columns']==['flat','rough']
    assert manifest['by_terrain']['flat']['levels'][5]==2
    assert manifest['by_terrain']['rough']['levels'][2]==1


def score(r,n,passed=True,metrics=None,folder=None):
    root=r.log_dir; root.mkdir(parents=True,exist_ok=True)
    r.score_dir=root/'scores'; r.score_dir.mkdir(exist_ok=True)
    cp=root/f'model_{n}.pt'; cp.write_bytes(f'known-cpu-checkpoint-{n}'.encode())
    raw=root/f'raw_{n}.json'; raw.write_text('{}')
    row=dict(format='foothold-ex41-score/1',iteration=n,stage_id=r.effective['stage_id'],
        schedule_sha256=r.plan.effective_sha256,parent_sha256=r.plan.parent_sha256,
        checkpoint_path=str(cp),checkpoint_sha256=sha256(cp),created_at=datetime.now(timezone.utc).isoformat(),
        maintenance_pass=True,stage_pass=passed,safety_stop=False,metrics=metrics or {},
        baseline_checkpoint_sha256=r._stage_baseline_sha,evidence=[{'path':str(raw),'sha256':sha256(raw)}])
    out=r.score_dir/(folder or f'score_{n}.json'); out.write_text(json.dumps(row),encoding='utf-8')
    return out


def test_two_real_files_promote_at_500_and_missing_w71_holds(tmp_path,monkeypatch):
    r,_=runtime(tmp_path,monkeypatch); r.on_update_start(1)
    score(r,250); r.on_update_start(251)
    assert r.effective['stage_id']=='S2a'
    score(r,500); r.on_update_start(501)
    assert r.effective['stage_id']=='S2b'
    score(r,750); r.on_update_start(751)
    score(r,1000); r.on_update_start(1001)
    assert r.effective['stage_id']=='S2b' and not r.stop_requested


def test_same_checkpoint_conflict_is_not_two_passes(tmp_path,monkeypatch):
    r,_=runtime(tmp_path,monkeypatch); r.on_update_start(1)
    score(r,500,folder='a.json'); score(r,500,folder='b.json')
    r.on_update_start(501)
    assert r.effective['stage_id']=='S2a' and not r._history


@pytest.mark.parametrize('mutate',[lambda d:d.update(checkpoint_sha256='0'*64),
    lambda d:d.update(stage_id='S2c'), lambda d:d.update(maintenance_pass='PASS'),
    lambda d:d.update(metrics={'x':float('nan')}),lambda d:d.update(evidence=[])])
def test_bad_score_never_promotes(tmp_path,monkeypatch,mutate):
    r,_=runtime(tmp_path,monkeypatch); r.on_update_start(1)
    f=score(r,500); data=json.loads(f.read_text()); mutate(data); f.write_text(json.dumps(data))
    r.on_update_start(501)
    assert r.effective['stage_id']=='S2a' and not r._history


def test_s2c_extension_once_then_cap_transition_without_false_graduation(tmp_path,monkeypatch):
    r,_=runtime(tmp_path,monkeypatch)
    r._apply(3,1001,r._config_values,[],None,'cpu edge setup')
    r._level_history=[(n,1. if n<=1250 else 1.5) for n in range(1050,1501,50)]
    score(r,1500,False,{'stand_min_passed':61})
    r.on_update_start(1501)
    assert r._extensions==1 and r.effective['stage_id']=='S2c'
    score(r,2000,False,{'stand_min_passed':61})
    r.on_update_start(2001)
    assert r.effective['stage_id']=='T0_prime' and not r._s2c_pass and not r.stop_requested
    r.on_update_start(2501)
    assert r.finished and not r.graduated


def test_stale_or_absent_score_does_not_stop_s2a(tmp_path,monkeypatch):
    r,_=runtime(tmp_path,monkeypatch); r.on_update_start(1)
    score(r,250); r.on_update_start(1001)
    assert not r._history and not r.finished and not r.stop_requested
    assert r.effective['stage_id']=='S2a'


def test_invalid_automatic_metric_is_rejected_and_training_continues(tmp_path,monkeypatch):
    r,_=runtime(tmp_path,monkeypatch); r.on_update_start(1)
    score(r,250,metrics={'gait_sync':'bad'}); r.on_update_start(251)
    assert not r._history and not r.stop_requested
    score(r,500,metrics={'pairs':{'side':{'left':[100,.1],'right':[64,.1]}}})
    r.on_update_start(501)
    assert not r._history and r.effective['stage_id']=='S2a'


def test_delayed_scores_adjust_only_once_per_boundary(tmp_path,monkeypatch):
    r,_=runtime(tmp_path,monkeypatch); r.on_update_start(1)
    metric={'pairs':{'side':{'left':[55,.2],'right':[64,.1]}}}
    score(r,250,False,metric); score(r,500,False,metric)
    r.on_update_start(501)
    assert r._pair_bias['side_left|side_right']==pytest.approx(.01)
    r.on_update_start(751)
    assert r._pair_bias['side_left|side_right']==pytest.approx(.01)


def test_dr_ramp_starts_from_current_value_and_n0_is_not_ex40_zero(tmp_path,monkeypatch):
    from foothold_s2.curriculum.ex41 import EX41DRReadback
    r,_=runtime(tmp_path,monkeypatch)
    b=SimpleNamespace(scale=0.,env=SimpleNamespace(_ex40_dr_scale=0.,_ex40_dr_samples={},
        action_manager=SimpleNamespace(get_term=lambda n:SimpleNamespace())),_first_update=True)
    dr=EX41DRReadback(b,r); dr.update_start(1)
    assert b.scale==1.
    values=copy.deepcopy(r._config_values); values['dr']={'target_scale':.5,'ramp_updates':100}
    r._apply(1,251,values,[],None,'known ramp')
    assert r.dr_scale(251)==1. and r.dr_scale(301)==.75 and r.dr_scale(351)==.5


@pytest.mark.parametrize('parent,initial',[(6000,.5),(7500,1.)])
def test_parent_and_initial_dr_are_configuration_not_hardcoded(tmp_path,monkeypatch,parent,initial):
    from foothold_s2.curriculum.ex41 import EX41DRReadback
    doc=yaml.safe_load(TABLE.read_text()); doc['parent_update']=parent
    doc['domain_randomization']['scale']=initial
    doc['parent_sha256']=('d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5' if parent==6000 else doc['parent_sha256'])
    table=tmp_path/'candidate.yaml'; table.write_text(yaml.safe_dump(doc),encoding='utf-8')
    snap=snapshot(); snap['config']['values']['dr']={'target_scale':initial,'ramp_updates':0}
    monkeypatch.setattr(w72,'read_committed_pair',lambda *a:copy.deepcopy(snap))
    p=load_plan(table,arm='B'); assert p.initial_dr_scale==initial
    r=make_runtime(p,4,'cpu',tmp_path/'run'); r.set_stage_changed_hook(lambda s,e:e); r.start(p.parent_sha256)
    base=SimpleNamespace(scale=0.,env=SimpleNamespace(_ex40_dr_scale=0.))
    EX41DRReadback(base,r)
    assert r.dr_scale(0)==base.env._ex40_dr_scale==initial
    assert r.boundary_receipt()['parent_update']==parent
    values=copy.deepcopy(r._config_values); values['dr']={'target_scale':.7,'ramp_updates':500}
    r._apply(1,1,values,[],None,'known candidate ramp')
    assert r.dr_scale(1)==initial
    assert r.dr_scale(251)==pytest.approx((initial+.7)/2)
    assert r.dr_scale(501)==.7


def test_initial_boundary_cannot_silently_jump_parent_dr(tmp_path,monkeypatch):
    doc=yaml.safe_load(TABLE.read_text()); doc['parent_update']=6000; doc['domain_randomization']['scale']=.5
    table=tmp_path/'candidate.yaml'; table.write_text(yaml.safe_dump(doc),encoding='utf-8')
    monkeypatch.setattr(w72,'read_committed_pair',lambda *a:snapshot())  # initial target1 differs
    p=load_plan(table,arm='B'); r=make_runtime(p,4,'cpu',tmp_path/'run'); r.set_stage_changed_hook(lambda s,e:e)
    with pytest.raises(ValueError,match='initial DR'): r.start(p.parent_sha256)
