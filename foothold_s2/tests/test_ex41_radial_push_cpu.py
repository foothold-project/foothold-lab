from __future__ import annotations

import math
import sys
import types

import torch

from foothold_s2.curriculum.ex40_dr_runtime import _sample_radial_push_xy, interval_push
from foothold_s2.curriculum.ex41 import EX41DRReadback


def test_radial_magnitude_and_angle_are_independently_uniform_coordinates():
    generator=torch.Generator(device='cpu').manual_seed(13579)
    xy,magnitude,angle=_sample_radial_push_xy(5000,2.0,device='cpu',dtype=torch.float64,generator=generator)
    norm=torch.linalg.vector_norm(xy,dim=1)
    assert torch.all(magnitude>=0) and torch.all(magnitude<=2.0)
    assert torch.all(angle>=0) and torch.all(angle<2*math.pi)
    assert torch.allclose(norm,magnitude,atol=1e-12,rtol=1e-12)
    assert float(magnitude.max()) <= 2.0
    assert float(xy.abs().max()) <= 2.0
    assert abs(float(magnitude.mean())-1.0) < .04
    magnitude_bins=torch.histc(magnitude,bins=10,min=0.0,max=2.0)
    angle_bins=torch.histc(angle,bins=12,min=0.0,max=2*math.pi)
    assert int(magnitude_bins.min()) >= 430 and int(magnitude_bins.max()) <= 570
    assert int(angle_bins.min()) >= 340 and int(angle_bins.max()) <= 500


def test_axis_box_corner_mutant_exceeds_requested_horizontal_cap():
    vmax=1.5
    bad_axis_box=torch.tensor([[vmax,vmax]],dtype=torch.float64)
    assert float(torch.linalg.vector_norm(bad_axis_box,dim=1).item()) > vmax
    good_xy,_,_=_sample_radial_push_xy(512,vmax,device='cpu',dtype=torch.float64,
                                       generator=torch.Generator(device='cpu').manual_seed(2468))
    assert float(torch.linalg.vector_norm(good_xy,dim=1).max()) <= vmax


def test_interval_push_uses_stage_vmax_not_dr_scale_and_writes_xy_only(monkeypatch):
    mdp=types.ModuleType('isaaclab.envs.mdp')
    mdp.events=types.SimpleNamespace()
    monkeypatch.setitem(sys.modules,'isaaclab.envs.mdp',mdp)

    class PhysX:
        def __init__(self,vel): self.vel=vel
        def get_root_velocities(self): return self.vel

    class Asset:
        def __init__(self):
            self.device='cpu'
            self.data=types.SimpleNamespace(root_vel_w=torch.zeros((256,6)))
            self.root_physx_view=PhysX(self.data.root_vel_w)
        def write_root_velocity_to_sim(self,vel,env_ids):
            self.data.root_vel_w[env_ids]=vel

    asset=Asset()
    asset.data.root_vel_w[:,0]=.25
    asset.data.root_vel_w[:,1]=-.1
    asset.data.root_vel_w[:,2]=.3
    asset.data.root_vel_w[:,3]=.02
    initial=asset.data.root_vel_w.clone()
    env=types.SimpleNamespace(scene={'robot':asset},_ex41_push_vmax_mps=1.65,
                             _ex40_dr_scale=.5,_ex40_dr_samples={})
    interval_push(env,torch.arange(256),types.SimpleNamespace(name='robot'),
                  {'x':(-1,1),'y':(-1,1)})
    delta=asset.data.root_vel_w[:,:2]-initial[:,:2]
    assert torch.all(torch.linalg.vector_norm(delta,dim=1)<=1.65+1e-6)
    assert torch.allclose(asset.data.root_vel_w[:,2:],initial[:,2:])
    sampled=env._ex40_dr_samples['push_radial_magnitude_mps']
    assert sampled['count']==256 and sampled['max']<=1.65
    assert sampled['target_envs']==256


def test_dr_readback_records_stage_vmax_separately_from_dr_scale():
    env=types.SimpleNamespace(_ex40_dr_scale=.5)
    base=types.SimpleNamespace(scale=.5,env=env,_first_update=True,summary=lambda:{'scale':.65})
    runtime=types.SimpleNamespace(plan=types.SimpleNamespace(initial_dr_scale=.5),
        effective={'stage_id':'S2b'},dr_scale=lambda _n:.65,push_vmax=lambda _n:1.65)
    readback=EX41DRReadback(base,runtime)
    readback.update_start(751)
    summary=readback.summary()
    assert summary['scale']==.65
    assert summary['push_schedule']=={'stage_id':'S2b','vmax_mps':1.65,
        'independent_of_dr_scale':True,
        'sampling':'magnitude U[0,Vmax] m/s; direction U[0,360) degrees; horizontal radial vector'}
    assert env._ex40_dr_scale==.65 and env._ex41_push_vmax_mps==1.65
