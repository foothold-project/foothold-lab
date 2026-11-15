"""CPU fake scene through the real A3.3 provider class without calling Kit."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import torch

from s2_physx_probe_diag import ProbeContractError
from s2_physx_probe_live import A33LiveBridge

HERE=Path(__file__).resolve().parent
A33=HERE/"a33"


def provider_class():
    sys.path.insert(0,str(A33))
    spec=importlib.util.spec_from_file_location("s2_11_a33_provider",A33/"s2_connect_diag_17v.py")
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    return mod.IsaacProvider


def fake(cls,types=None):
    p=cls.__new__(cls)
    p.num_envs=8;p._step=-1
    terrain=SimpleNamespace(terrain_types=torch.tensor(types or [0,0,1,1,2,2,3,3]),
                            terrain_levels=torch.zeros(8,dtype=torch.long),collision_group=-1)
    force=torch.zeros(8,5,3);force[6,3,2]=9
    sensor=SimpleNamespace(data=SimpleNamespace(net_forces_w=force),
                           find_bodies=lambda names,preserve_order:([0,1,3,4],list(names)))
    robot=SimpleNamespace(root_ang_vel_w=torch.zeros(8,3),root_quat_w=torch.tensor([[1.,0.,0.,0.]]*8))
    p.robot=SimpleNamespace(data=robot)
    p.scanner=SimpleNamespace(cfg=SimpleNamespace(mesh_prim_paths=["/World/ground"]))
    p.raw=SimpleNamespace(scene=SimpleNamespace(terrain=terrain,
        env_origins=torch.tensor([[10.,20.,5.]]*8),sensors={"contact_forces":sensor}),
        cfg=SimpleNamespace(scene=SimpleNamespace(terrain=terrain)),common_step_counter=17)
    return p


def run():
    cls=provider_class()
    bridge=A33LiveBridge(fake(cls))
    assert bridge.task=="RobotLab-Go2-v0" and bridge.case_count==8
    assert bridge.env0_origin_w==[10.,20.,5.]
    frame=bridge.kinematic_frame()
    assert frame["foot_contact_forces_w"].shape==(8,4,3)
    assert frame["foot_contact_forces_w"][6,2,2]==9
    assert frame["root_ang_vel_w"].shape==(8,3) and frame["root_quat_w"].shape==(8,4)
    print("PASS bridge_sensor_shapes")
    try:A33LiveBridge(fake(cls,[0,0,1,1,2,3,2,3]))
    except ProbeContractError as ex:assert str(ex)=="a33_case_assignment"
    else:raise AssertionError("wrong case assignment accepted")
    print("PASS bridge_case_reject")
    assert not any(k.startswith(("omni.","isaaclab.")) for k in sys.modules)
    print("PASS bridge_no_Kit")


if __name__=="__main__":run()
