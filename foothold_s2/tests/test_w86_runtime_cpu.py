"""Known physics arrays and late fault paths, without Kit or CUDA."""
from pathlib import Path
from types import SimpleNamespace
import math
import json
import pytest
import torch
from foothold_s2.rewards import w86_runtime as wr


def sample(n=3):
    return dict(sole_z=torch.full((n,4),.02), velocity_xy=torch.ones(n,4,2)*.2,
                ground_z=torch.zeros(n,4,3), forces=torch.zeros(n,4,3),
                command=torch.tensor([[.5,0.,0.]]*n), heading=torch.zeros(n,dtype=torch.bool),
                yaw=torch.zeros(n), joint_pos=torch.zeros(n,12), torque=torch.zeros(n,12),
                effort_limits=torch.ones(n,12)*20, joint_limits=torch.tensor([[[-1.,1.]]*12]*n),
                physical_valid=torch.ones(n,dtype=torch.bool),knee_ids=[8,9,10,11])


def test_registration_existing_single_stumble_and_zero_recording(monkeypatch):
    import sys
    cfg=SimpleNamespace(rewards=SimpleNamespace(collision=SimpleNamespace(weight=-10),
        action_smoothness=SimpleNamespace(weight=-.01),joint_power=SimpleNamespace(weight=-2e-5),
        stumble=SimpleNamespace(weight=-1)),terminations=SimpleNamespace(),events=SimpleNamespace())
    monkeypatch.setitem(sys.modules,'isaaclab.managers',SimpleNamespace(
        RewardTermCfg=lambda **kw:SimpleNamespace(**kw), TerminationTermCfg=lambda **kw:SimpleNamespace(**kw),
        EventTermCfg=lambda **kw:SimpleNamespace(**kw)))
    plan=SimpleNamespace(is_ex41=True, stages=[SimpleNamespace(rewards={'zero_yaw':-.5,'swing':-10,'stumble':-2})])
    out=wr.prepare_env_cfg(cfg,plan)
    assert cfg.rewards.stumble.weight==-2 and cfg.rewards.collision.weight==-10
    assert len([n for n in vars(cfg.rewards) if 'stumble' in n])==1
    assert cfg.rewards.ex41_swing.weight==-10 and cfg.rewards.ex41_foot_slip.weight==0
    assert out['zero_weight_recorder_required']
    with pytest.raises(ValueError): wr.prepare_env_cfg(cfg,plan)


def test_cache_termination_before_reward_and_invalid_ray(tmp_path):
    env=SimpleNamespace(num_envs=3,device='cpu',step_dt=.02,common_step_counter=1)
    data=sample(); data['ground_z'][1,0,1]=float('inf'); data['sole_z'][2,0]=float('nan')
    count=[0]
    def source(): count[0]+=1; return data
    a=wr.W86Runtime(env,tmp_path,source=source); env._ex41_w86=a
    assert wr.invalid_env(env).tolist()==[False,False,True]
    cost=wr.reward_term(env,'swing')
    assert count==[1] and torch.isfinite(cost).all()
    assert cost[0]>cost[1]>0 and cost[2]==0
    row=a.flush(1)
    assert row['feet']['invalid_ray_frames'][0]==1
    assert row['quarantine_env_count']==1
    assert 'foot_slip' in row['terms'] and Path(tmp_path/'ex41_w86.jsonl').is_file()


def test_finite_input_overflow_quarantines_one_env_before_metric_flush(tmp_path):
    env=SimpleNamespace(num_envs=3,device='cpu',step_dt=.02,common_step_counter=1)
    data=sample(); data['torque'][1,8]=1e30
    a=wr.W86Runtime(env,tmp_path,source=lambda:data); env._ex41_w86=a
    assert wr.invalid_env(env).tolist()==[False,True,False]
    row=a.flush(1)
    assert row['quarantine_env_count']==1
    assert all(math.isfinite(t['sum']) for t in row['terms'].values())


def test_swing_cost_order_and_stationary_zero(tmp_path):
    env=SimpleNamespace(num_envs=4,device='cpu',step_dt=.02,common_step_counter=1)
    d=sample(4); d['sole_z'][:]=.08; d['sole_z'][:,0]=torch.tensor([.04,0.,-.05,.08])
    d['velocity_xy'][:]=0; d['velocity_xy'][:,0,0]=.5
    a=wr.W86Runtime(env,tmp_path,source=lambda:d)
    row=a.refresh(); expected=torch.tensor([.04**2,.08**2,.13**2,0.])*math.tanh(1)
    torch.testing.assert_close(row['terms']['swing'],expected)
    d['command'][:]=0; env.common_step_counter+=1
    assert a.refresh()['terms']['swing'].eq(0).all()


def test_complete_swing_cycles_ignore_reset_truncation(tmp_path):
    env=SimpleNamespace(num_envs=1,device='cpu',step_dt=.02,common_step_counter=1)
    d=sample(1); d['forces'][:,:,2]=2
    a=wr.W86Runtime(env,tmp_path,source=lambda:d); a.refresh()
    env.common_step_counter+=1; d['forces'][:,:,2]=0; d['sole_z'][:]=.10; a.refresh()
    env.common_step_counter+=1; d['forces'][:,:,2]=2; a.refresh()
    assert a.flush(3)['feet']['complete_swing_count']==[1]*4
    env.common_step_counter+=1; d['forces'][:,:,2]=0; a.refresh(); a.on_reset(torch.tensor([0]))
    env.common_step_counter+=1; d['forces'][:,:,2]=2; a.refresh()
    assert a.flush(5)['feet']['complete_swing_count']==[0]*4


def test_contact_force_is_averaged_per_foot_and_command_only_while_in_contact(tmp_path):
    env=SimpleNamespace(num_envs=3,device='cpu',step_dt=.02,common_step_counter=1)
    d=sample(3)
    d['command_slot_names']=('walk','stand')
    d['command_slot']=torch.tensor([0,0,1])
    d['command_is_flag']=torch.zeros(3,dtype=torch.bool)
    # Rows are envs, columns are feet. Exactly 1 N is outside the >1 N contact rule.
    d['forces'][:,:,2]=torch.tensor([[2.,0.,3.,5.],[4.,6.,0.,1.],[100.,2.,2.,0.]])
    recorder=wr.W86Runtime(env,tmp_path,source=lambda:d)
    recorder.refresh()
    restored=wr.W86Runtime(env,tmp_path/'restored',source=lambda:d)
    restored.load_state_dict(recorder.state_dict())
    row=recorder.flush(1)
    metric=row['foot_contact_force_by_command']
    assert metric['status']=='measured'
    assert metric['source']=='contact_forces.net_forces_w'
    walk=metric['commands']['walk']['feet']
    assert walk['FL_foot']=={'contact_frames':2,'contact_time_s':pytest.approx(.04),
                             'force_sum_n':6.0,'mean_force_n':3.0}
    assert walk['FR_foot']['contact_frames']==1 and walk['FR_foot']['mean_force_n']==6.0
    assert walk['RL_foot']['contact_frames']==1 and walk['RL_foot']['mean_force_n']==3.0
    assert walk['RR_foot']['contact_frames']==1 and walk['RR_foot']['mean_force_n']==5.0
    stand=metric['commands']['stand']['feet']
    assert stand['FL_foot']['mean_force_n']==100.0
    assert stand['RR_foot']['contact_frames']==0 and stand['RR_foot']['mean_force_n'] is None
    assert restored.flush(1)['foot_contact_force_by_command']==metric
    saved=json.loads((tmp_path/'ex41_w86.jsonl').read_text(encoding='utf-8').splitlines()[0])
    assert saved['foot_contact_force_by_command']==metric


def test_quarantine_only_bad_rows_and_transition_std(tmp_path):
    env=SimpleNamespace(num_envs=3,device='cpu',step_dt=.02,common_step_counter=0)
    a=wr.W86Runtime(env,tmp_path,source=lambda:sample()); env._ex41_w86=a
    transition=SimpleNamespace(observations={'policy':torch.ones(3,4)},values=torch.ones(3,1),
        actions=torch.ones(3,12),actions_log_prob=torch.ones(3),action_mean=torch.ones(3,12),action_sigma=torch.ones(3,12))
    runner=SimpleNamespace(env=SimpleNamespace(unwrapped=env),alg=SimpleNamespace(transition=transition))
    actions=torch.ones(3,12); actions[1,0]=float('nan')
    got=wr.quarantine_actions(runner,actions)
    assert got[1].eq(0).all() and got[0].eq(1).all()
    obs={'policy':torch.ones(3,4)}; rew=torch.ones(3); dones=torch.tensor([False,True,False])
    out,r,d,e=wr.quarantine_step(runner,obs,rew,dones,{'time_outs':torch.ones(3,dtype=torch.bool)})
    assert r.tolist()==[1.,0.,1.] and d.tolist()==[False,True,False]
    assert e['time_outs'].tolist()==[True,False,True]
    assert transition.observations['policy'][1].eq(0).all()
    assert transition.action_sigma[1].eq(1).all() and transition.values[0]==1
    assert not a.pending.any()


def test_quaternion_sole_world_offset():
    q=torch.tensor([[1.,0.,0.,0.],[0.,0.,0.,1.]])
    v=torch.tensor([[-.002,0.,0.]]*2)
    torch.testing.assert_close(wr.rotate(q,v),torch.tensor([[-.002,0,0],[.002,0,0]]))


def test_physical_source_ray_geometry_rotation_and_names():
    # Robot yaw 90 degrees, command forward points world +y. World origin z=3.
    q=torch.tensor([[math.sqrt(.5),0.,0.,math.sqrt(.5)]])
    feet=torch.tensor([[[1.2,2.1,3.022],[1.2,1.9,3.022],[.8,2.1,3.022],[.8,1.9,3.022]]])
    d=SimpleNamespace(body_pos_w=feet,body_quat_w=q[:,None,:].expand(1,4,4),
        root_quat_w=q,root_pos_w=torch.tensor([[1.,2.,3.3]]),root_state_w=torch.zeros(1,13),
        body_state_w=torch.zeros(1,4,13),joint_pos=torch.zeros(1,12),joint_vel=torch.zeros(1,12),
        applied_torque=torch.zeros(1,12),body_lin_vel_w=torch.zeros(1,4,3),root_ang_vel_b=torch.zeros(1,3),
        joint_effort_limits=torch.ones(1,12)*1e9,soft_joint_pos_limits=torch.tensor([[[-1.,1.]]*12]))
    term=SimpleNamespace(heading=torch.zeros(1,dtype=torch.bool),slot_names=('forward',),
                         slot_current=torch.tensor([0]),is_flag_env=torch.zeros(1,dtype=torch.bool))
    env=SimpleNamespace(num_envs=1,device='cpu',action_manager=SimpleNamespace(action=torch.zeros(1,12)),
        command_manager=SimpleNamespace(get_command=lambda n:torch.tensor([[.5,0.,0.]]),
                                        get_term=lambda n:term))
    s=wr.PhysicalSource.__new__(wr.PhysicalSource); s.env=env; s.robot=SimpleNamespace(data=d,
        actuators={'motor':SimpleNamespace(joint_indices=slice(None),effort_limit=torch.ones(1,12)*45.43)})
    s.sensor=SimpleNamespace(data=SimpleNamespace(net_forces_w=torch.zeros(1,4,3)))
    s.feet=list(range(4)); s.force_ids=list(range(4)); s.knees=[8,9,10,11]; s.mesh=object(); s.link_names=wr.FEET
    seen={}
    def cast(starts,directions,mesh,max_dist):
        seen['starts']=starts.clone(); seen['directions']=directions.clone()
        out=starts.clone(); out[...,2]=3.
        return out,None,None,None
    s.cast=cast; r=s()
    torch.testing.assert_close(r['effort_limits'],torch.ones(1,12)*45.43)
    assert r['all_link_names']==wr.FEET and r['all_forces'].shape==(1,4,3)
    assert r['command_slot_names']==('forward',) and r['command_slot'].tolist()==[0]
    assert r['command_is_flag'].tolist()==[False]
    assert seen['starts'].shape==(1,4,3,3)
    torch.testing.assert_close(seen['starts'][0,0,1]-seen['starts'][0,0,0],torch.tensor([0.,.05,0.]),atol=1e-6,rtol=0)
    torch.testing.assert_close(r['sole_z'],torch.full((1,4),3.))
    assert r['ground_z'].eq(3.).all() and r['physical_valid'].tolist()==[True]


def test_observation_fault_resets_only_that_env_and_preserves_other_rows(tmp_path):
    env=SimpleNamespace(num_envs=3,device='cpu',step_dt=.02,common_step_counter=0)
    a=wr.W86Runtime(env,tmp_path,source=lambda:sample()); env._ex41_w86=a
    resets=[]; env._reset_idx=lambda ids:resets.extend(ids.tolist())
    env.scene=SimpleNamespace(write_data_to_sim=lambda:None); env.sim=SimpleNamespace(forward=lambda:None)
    env.observation_manager=SimpleNamespace(compute=lambda update_history:{'policy':torch.full((3,4),2.)})
    runner=SimpleNamespace(env=SimpleNamespace(unwrapped=env),alg=SimpleNamespace())
    obs={'policy':torch.ones(3,4)}; obs['policy'][1,0]=float('nan')
    out,r,d,e=wr.quarantine_step(runner,obs,torch.ones(3),torch.zeros(3,dtype=torch.bool),{})
    assert resets==[1] and out['policy'][0].eq(1).all() and out['policy'][1].eq(2).all()
    assert d.tolist()==[False,True,False] and r.tolist()==[1.,0.,1.]


def test_save_restore_metrics_without_fake_complete_physical_cycle(tmp_path):
    env=SimpleNamespace(num_envs=1,device='cpu',step_dt=.02,common_step_counter=1)
    d=sample(1); a=wr.W86Runtime(env,tmp_path/'a',source=lambda:d); a.refresh()
    b=wr.W86Runtime(env,tmp_path/'b',source=lambda:d); b.load_state_dict(a.state_dict())
    assert b.count==1 and not b.observed.any()
    assert b.flush(1500)['feet']['complete_swing_count']==[0]*4


@pytest.mark.parametrize('tensordict',[False,True])
def test_sanitize_owns_storage_without_changing_policy_or_observations(tensordict):
    from tensordict import TensorDict
    std=torch.nn.Parameter(torch.full((12,),.46))
    obs=torch.ones(3,4)
    source={'nested':{'policy':obs},'sigma':std.detach().expand(3,12)}
    if tensordict: source=TensorDict(source,batch_size=[3])
    out=wr._sanitize(source,torch.tensor([False,True,False]),fill=0.)
    assert std.eq(.46).all() and obs.eq(1).all()
    assert source['sigma'].eq(.46).all()
    assert source['nested']['policy'].eq(1).all()
    assert out['sigma'][1].eq(0).all() and out['sigma'][0].eq(.46).all()
    assert out['nested']['policy'][1].eq(0).all()
    assert out['nested']['policy'][2].eq(1).all()
    if tensordict: assert isinstance(out,TensorDict) and out.batch_size==torch.Size([3])
