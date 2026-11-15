"""Evaluation rollout only. Imports Isaac lazily in the separate CLI."""
from __future__ import annotations

import numpy as np
import torch


def collect_trace(env,raw,robot,sensor,term,policy,dr,spec,*,body_ids,sensor_ids,
                  forbidden_ids,offset,initial,yaw,reset_valid,anchors=None):
    from foothold_s2.eval.map_mode_cells import assert_heading_off_for_fixed_eval
    n=64;alive=torch.ones(n,dtype=torch.bool,device=raw.device)
    keys=('root_pos_w','root_quat_w','foot_pos_w','contact','body_vel_b','body_ang_vel_b',
          'alive','command_b','forbidden_contact','dones','command_stopped')
    rows={key:[] for key in keys}
    command=torch.tensor(spec['command_b'],device=raw.device)
    stopped=torch.zeros(n,dtype=torch.bool,device=raw.device)
    for k in range(spec['steps']):
        term.vel_command_b[:,:3]=command
        term.vel_command_b[stopped,:3]=0
        term.stand.copy_(stopped)
        assert_heading_off_for_fixed_eval(term)
        if bool(term.is_flag_env.any()):raise RuntimeError('fixed task contains a flag env')
        # Observe the current requested command, not the previous step's buffer.
        obs=env.get_observations()
        requested=term.vel_command_b[:,:3].clone()
        dr.step(raw,k)
        with torch.inference_mode():action=policy(obs)
        _obs,_reward,done,_extras=env.step(action)
        done=done.bool();was_alive=alive.clone();alive &= ~done
        if bool(alive.any()) and not torch.allclose(term.vel_command_b[alive,:3],requested[alive],atol=1e-5,rtol=0):
            raise RuntimeError('command changed inside policy step')
        policy.reset(done)
        force=torch.linalg.vector_norm(sensor.data.net_forces_w,dim=-1)
        data=robot.data
        sample={'root_pos_w':data.root_pos_w,'root_quat_w':data.root_quat_w,
            'foot_pos_w':data.body_pos_w[:,body_ids],'contact':force[:,sensor_ids]>1.,
            'body_vel_b':data.root_lin_vel_b,'body_ang_vel_b':data.root_ang_vel_b,
            'alive':alive,'dones':done&was_alive,'command_b':requested,'command_stopped':stopped,
            'forbidden_contact':(force[:,forbidden_ids]>.1).any(-1)&was_alive}
        for key,value in sample.items():rows[key].append(value.detach().cpu().numpy().copy())
        if spec.get('stop_at_goal'):
            if anchors is None:raise ValueError('completion stop needs geometry anchors')
            local=data.root_pos_w-torch.as_tensor(offset,device=raw.device)
            reached=(local[:,0]>=anchors['exit_x'])&(local[:,0]<=anchors['tile_end_x'])&\
                    (local[:,1]>=anchors['exit_bounds_y'][0])&(local[:,1]<=anchors['exit_bounds_y'][1])&alive
            stopped |= reached
    trace={key:np.stack(value) for key,value in rows.items()}
    trace.update(tile_offset_w=np.asarray(offset),initial_root_pos_w=np.asarray(initial),
        initial_yaw_rad=np.full(n,yaw),reset_valid=np.asarray(reset_valid,bool))
    return trace


def initial_support_valid(feet,*,replica):
    """CPU ray check of the actual reset feet, not the commanded root position.

    Same mounting diagnostic gap limit 0.30 m; this is reset validity, never a
    policy-success exclusion. A failure after the first step remains a failure.
    """
    import trimesh
    mesh=trimesh.Trimesh(replica['vertices'],replica['faces'],process=False)
    feet=np.asarray(feet,float)
    if feet.shape!=(64,4,3) or not np.isfinite(feet).all():raise ValueError('reset feet invalid')
    starts=feet.reshape(-1,3).copy();starts[:,2]+=.01
    loc,indices,_=mesh.ray.intersects_location(starts,np.tile([0.,0.,-1.],(256,1)),multiple_hits=True)
    gap=np.full(256,np.inf)
    for hit,i in zip(loc,indices):gap[i]=min(gap[i],starts[i,2]-hit[2]-.01)
    return ((gap.reshape(64,4)>=-.011)&(gap.reshape(64,4)<=.30)).all(-1)
