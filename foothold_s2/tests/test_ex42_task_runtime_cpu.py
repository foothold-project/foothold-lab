from types import SimpleNamespace as NS
import torch
import numpy as np
from foothold_s2.eval.ex42_task_runtime import collect_trace


def test_rollout_holds_command_records_first_failure_and_fires_dr_hook():
    n=64;events=[];term=NS(vel_command_b=torch.zeros(n,3),stand=torch.zeros(n,dtype=torch.bool),
        heading=torch.zeros(n,dtype=torch.bool),is_flag_env=torch.zeros(n,dtype=torch.bool))
    robot=NS(data=NS(root_pos_w=torch.zeros(n,3),root_quat_w=torch.tensor([[1.,0,0,0]]*n),
        body_pos_w=torch.zeros(n,4,3),root_lin_vel_b=torch.zeros(n,3),root_ang_vel_b=torch.zeros(n,3)))
    sensor=NS(data=NS(net_forces_w=torch.ones(n,5,3)))
    class Env:
        count=0
        def get_observations(self):
            assert torch.all(term.vel_command_b[:,0]==1)
            return torch.zeros(n,1)
        def step(self,a):
            self.count+=1;robot.data.root_pos_w[:,0]+=.02
            done=torch.zeros(n,dtype=torch.bool)
            if self.count==3:done[0]=True;robot.data.root_pos_w[0,0]=100
            return None,None,done,{}
    class Policy:
        def __call__(self,obs):return torch.zeros(n,12)
        def reset(self,done):events.append(('reset',bool(done.any())))
    class DR:
        def step(self,raw,k):events.append(('dr',k))
    raw=NS(device='cpu');spec=dict(command_b=[1.,0,0],steps=5,dt=.02)
    trace=collect_trace(Env(),raw,robot,sensor,term,Policy(),DR(),spec,
        body_ids=[0,1,2,3],sensor_ids=[0,1,2,3],forbidden_ids=[4],
        offset=np.zeros((n,3)),initial=np.zeros((n,3)),yaw=0.,reset_valid=np.ones(n,bool))
    assert trace['alive'][:,0].tolist()==[True,True,False,False,False]
    assert [v for k,v in events if k=='dr']==list(range(5))
    assert trace['root_pos_w'].shape==(5,64,3)
    assert not trace['forbidden_contact'][3,0]


def test_completion_stop_is_after_goal_and_hold_recomputes_from_real_loop():
    from foothold_s2.eval.ex42_task_cells import summarize
    import pytest
    n=64;term=NS(vel_command_b=torch.zeros(n,3),stand=torch.zeros(n,dtype=torch.bool),
        heading=torch.zeros(n,dtype=torch.bool),is_flag_env=torch.zeros(n,dtype=torch.bool))
    robot=NS(data=NS(root_pos_w=torch.zeros(n,3),root_quat_w=torch.tensor([[1.,0,0,0]]*n),
        body_pos_w=torch.zeros(n,4,3),root_lin_vel_b=torch.zeros(n,3),root_ang_vel_b=torch.zeros(n,3)))
    sensor=NS(data=NS(net_forces_w=torch.zeros(n,5,3)))
    sensor.data.net_forces_w[:,:4,2]=10.
    class Env:
        def get_observations(self):return term.vel_command_b.clone()
        def step(self,action):
            assert torch.equal(action,term.vel_command_b)
            robot.data.root_pos_w+=action*.02
            robot.data.body_pos_w[:]=robot.data.root_pos_w[:,None,:]
            return None,None,torch.zeros(n,dtype=torch.bool),{}
    class Policy:
        def __call__(self,obs):return obs
        def reset(self,done):pass
    spec=dict(command_b=[1.,0.,0.],steps=50,dt=.02,stop_at_goal=True,task='tile_end_reach',
        map_mode='eval_gt',role='judge',hold_s=.5)
    anchors=dict(exit_x=.2,tile_end_x=1.,exit_bounds_y=[-.5,.5])
    trace=collect_trace(Env(),NS(device='cpu'),robot,sensor,term,Policy(),NS(step=lambda raw,k:None),spec,
        body_ids=[0,1,2,3],sensor_ids=[0,1,2,3],forbidden_ids=[4],offset=np.zeros((n,3)),
        initial=np.zeros((n,3)),yaw=0.,reset_valid=np.ones(n,bool),anchors=anchors)
    stops=trace['command_stopped'][:,0];first=int(np.flatnonzero(stops)[0])
    assert trace['root_pos_w'][first-1,0,0]>=.2
    assert np.all(trace['command_b'][first:]==0)
    assert summarize(trace,spec=spec,anchors=anchors)['success_count']==64
    trace['command_stopped'][0]=True;trace['command_stopped'][:]=True;trace['command_b'][:]=0
    with pytest.raises(ValueError,match='before geometry goal'):summarize(trace,spec=spec,anchors=anchors)
