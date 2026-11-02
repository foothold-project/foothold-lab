"""Lead/verifier 080d0a4a counterexamples. No Kit or experiment files."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import torch
import yaml
from foothold_s2.curriculum import ex41, w72
from foothold_s2.curriculum.continuous import load_plan
from foothold_s2.tests.test_ex41_runtime_cpu import runtime, score, TABLE
from foothold_s2.tests.ex41_runtime_fixture import real_runtime
from foothold_s2.tests.test_w86_runtime_cpu import sample
from foothold_s2.rewards import w86_runtime as wr


@pytest.mark.parametrize('kind',['array','directory','disappeared'])
def test_unreadable_score_is_recorded_and_valid_neighbor_consumed(tmp_path,monkeypatch,kind):
    r,_=runtime(tmp_path,monkeypatch); r.on_update_start(1)
    score(r,250)
    bad=r.score_dir/'a_bad.json'
    if kind=='directory': bad.mkdir()
    else: bad.write_text('[]')
    original=ex41.sha256
    def hash_file(path):
        if Path(path)==bad and kind=='disappeared': raise FileNotFoundError('known removed during scan')
        return original(path)
    monkeypatch.setattr(ex41,'sha256',hash_file)
    r.on_update_start(251)
    assert len(r._history)==1 and not r.stop_requested
    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    assert any(x['event']=='score_rejected' and x.get('path')==str(bad) for x in rows)


def test_safety_score_survives_locked_config_error(tmp_path,monkeypatch):
    r,snap=runtime(tmp_path,monkeypatch); r.on_update_start(1)
    f=score(r,250); data=json.loads(f.read_text()); data['safety_stop']=True
    f.write_text(json.dumps(data)); snap['config']['values']['ppo']['clip_param']=.1
    r.on_update_start(251)
    assert r.stop_requested
    assert r.effective['stage_id']=='S2a'


@pytest.mark.parametrize('key',['pair_step','pair_limit'])
def test_yaml_cannot_widen_approved_automatic_bounds(tmp_path,key):
    doc=yaml.safe_load(TABLE.read_text()); doc['automatic'][key]=.05
    p=tmp_path/'bad.yaml'; p.write_text(yaml.safe_dump(doc))
    with pytest.raises(ValueError,match='pair'): load_plan(p,arm='B')


def test_pair_consumer_also_enforces_bounds_and_tie_moves_one_point():
    with pytest.raises(ValueError): w72.adjust_pair(0.,(55,.2),(64,.1),step=.05,limit=.05)
    assert w72.adjust_pair(.02,(64,.1),(64,.1))==pytest.approx(.01)
    assert w72.adjust_pair(-.02,(64,.1),(64,.1))==pytest.approx(-.01)


@pytest.mark.parametrize('parent,scale',[(6000,1.),(7500,.5)])
def test_parent_initial_scale_cannot_disagree(tmp_path,parent,scale):
    doc=yaml.safe_load(TABLE.read_text()); doc['parent_update']=parent
    doc['domain_randomization']['scale']=scale
    p=tmp_path/'bad.yaml'; p.write_text(yaml.safe_dump(doc))
    with pytest.raises(ValueError,match='parent'): load_plan(p,arm='B')


def test_zero_length_dr_change_rejected_without_rollout_crash(tmp_path,monkeypatch):
    r,_=runtime(tmp_path,monkeypatch)
    values=copy.deepcopy(r._config_values); values['dr']={'target_scale':.5,'ramp_updates':0}
    assert not r._apply(1,251,values,[],None,'known forbidden DR step')
    assert r.dr_scale(251)==1. and r.boundary_receipt()['status']=='rejected'


def test_effective_validation_error_is_rejected_before_consumer(tmp_path,monkeypatch):
    r,_=runtime(tmp_path,monkeypatch)
    def fail(*args): raise ValueError('known effective validation failure')
    monkeypatch.setattr(r,'_effective',fail)
    assert not r._apply(1,251,r._config_values,[],None,'known bad effective')
    assert r.boundary_receipt()['status']=='rejected' and not r.stop_requested


def test_smoke_runs_all_declared_boundaries_but_cannot_graduate(tmp_path,monkeypatch):
    r,consumer=real_runtime(tmp_path,smoke=(1,3,5,7),w71=True)
    for n,name in [(1,'S2a'),(3,'S2b'),(5,'S2c'),(7,'T0_prime')]:
        r.on_update_start(n); assert r.effective['stage_id']==name
    r.on_update_start(9)
    assert r.finished and not r.graduated and not r._s2c_pass
    assert consumer.env.unwrapped._ex41_terrain=={'policy':'performance','level_cap':5}


def test_smoke_cannot_skip_missing_terrain_consumer(tmp_path):
    r,_=real_runtime(tmp_path,smoke=(1,3,5,7),w71=False)
    for n in (1,3,5,7,9): r.on_update_start(n)
    assert r.effective['stage_id']=='S2b' and not r.finished
    assert 'w71_not_ready' in (r.log_dir/'stage_log.jsonl').read_text()


def test_next_stage_pair_cannot_remove_command(tmp_path,monkeypatch):
    r,_=runtime(tmp_path,monkeypatch); r.on_update_start(1)
    r.templates[2].shares.update(side_left=.135,side_right=.005)
    # Both templates sum to one. +1 point fits the old but destroys the new
    # right-hand command. Checking only the old stage would apply the change.
    ex41.validate_shares(r.templates[2].shares)
    value={'_sha256':'known-score','iteration':500,
           'metrics':{'pairs':{'side':{'left':[55,.2],'right':[64,.1]}}}}
    changes=r._automatic(copy.deepcopy(r._config_values),value,True,next_pos=2)
    assert not changes and not r._pair_bias
    assert 'would_remove_existing_command' in (r.log_dir/'stage_log.jsonl').read_text()


def test_w71_missing_reason_is_separate_from_missing_performance(tmp_path,monkeypatch):
    r,_=runtime(tmp_path,monkeypatch); r.on_update_start(1)
    for n in (250,500,750,1000): score(r,n); r.on_update_start(n+1)
    assert r.effective['stage_id']=='S2b'
    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    assert rows[-1]['reason']=='w71_not_ready'


def test_world_height_does_not_trigger_relative_guard(tmp_path):
    env=SimpleNamespace(num_envs=3,device='cpu',step_dt=.02,common_step_counter=1)
    d=sample(); d['sole_z']+=1000.; d['ground_z']+=1000.
    a=wr.W86Runtime(env,tmp_path,source=lambda:d)
    assert not a.refresh()['bad'].any()


def test_cost_bound_quarantines_finite_derived_corruption(tmp_path,monkeypatch):
    env=SimpleNamespace(num_envs=3,device='cpu',step_dt=.02,common_step_counter=1)
    monkeypatch.setattr(wr.w86,'swing_clearance_cost',lambda *a:torch.tensor([0.,101.,0.]))
    a=wr.W86Runtime(env,tmp_path,source=lambda:sample())
    assert a.refresh()['bad'].tolist()==[False,True,False]
    assert a.cache['terms']['swing'][1]==0


def test_huge_finite_sole_is_quarantined_before_reward(tmp_path):
    env=SimpleNamespace(num_envs=3,device='cpu',step_dt=.02,common_step_counter=1)
    d=sample(); d['sole_z'][1,0]=1e6
    a=wr.W86Runtime(env,tmp_path,source=lambda:d); env._ex41_w86=a
    assert wr.invalid_env(env).tolist()==[False,True,False]
    assert wr.reward_term(env,'swing')[1]==0


def test_valid_mask_keeps_normal_done_and_remembers_action_fault(tmp_path):
    env=SimpleNamespace(num_envs=3,device='cpu',step_dt=.02,common_step_counter=1)
    a=wr.W86Runtime(env,tmp_path,source=lambda:sample()); env._ex41_w86=a
    runner=SimpleNamespace(env=SimpleNamespace(unwrapped=env),alg=SimpleNamespace())
    obs={'policy':torch.ones(3,4)}; done=torch.tensor([False,True,True])
    *_,extra=wr.quarantine_step(runner,obs,torch.ones(3),done,{})
    assert extra['ex41_ppo_valid'].tolist()==[True,True,True]
    actions=torch.zeros(3,12); actions[2,0]=float('nan'); wr.quarantine_actions(runner,actions)
    *_,extra=wr.quarantine_step(runner,obs,torch.ones(3),done,{})
    assert extra['ex41_ppo_valid'].tolist()==[True,True,False] and not a.pending.any()
