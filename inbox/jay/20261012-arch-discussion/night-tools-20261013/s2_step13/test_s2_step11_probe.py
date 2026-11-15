"""Known-answer CPU contract for the 16-step PhysX diagnostic."""
from __future__ import annotations

import json
import math
from pathlib import Path
import tempfile

import numpy as np

from s2_physx_probe_diag import collect, write_record, verify_record, ProbeContractError, query_phase


class Float3:
    def __init__(self,*xyz):self.xyz=tuple(xyz)
    def __repr__(self):return "Float3"+repr(self.xyz)


class Fake:
    num_envs=8
    task="RobotLab-Go2-v0"
    case_count=8
    optimizer_steps=0
    env0_origin_w=(10.0,20.0,5.0)
    flat_ground_z=0.0

    def __init__(self):self.steps=0;self.calls=[]
    def scene_query_context(self):
        return {"scene_paths":["/World/physicsScene"],"mesh_prim_paths":["/World/ground"],"collision_group":-1}
    def step_zero(self):self.steps+=1
    def kinematic_frame(self):
        forces=np.zeros((8,4,3),np.float32);forces[6,2,2]=7.5
        angular=np.zeros((8,3),np.float32);angular[6,0]=self.steps/100
        quat=np.zeros((8,4),np.float32);quat[:,0]=1
        return {"foot_names":["FL_foot","FR_foot","RL_foot","RR_foot"],
                "foot_contact_forces_w":forces,"root_ang_vel_w":angular,
                "root_quat_w":quat,"sim_step":self.steps}
    def physx(self,origin,direction,distance):
        self.calls.append((origin,direction,distance))
        return {"hit":True,"position":(0.0,0.0,5.0),"collision":"/World/ground/terrain/mesh",
                "opaque":Float3(1,2,3)}
    def warp(self,rays):return [(a[0],a[1],5.0) for a,_ in rays]


def check():
    f=Fake();record=collect(f,f.physx,Float3,f.warp)
    assert f.steps==16 and record["judgement"] is None
    print("PASS steps")
    assert len(f.calls)==288 and {q["variant"] for q in record["queries"]}=={
        "tuple_d0p8","carb_float3_d0p8","carb_float3_d80"}
    assert sum(isinstance(x[0],tuple) for x in f.calls)==96
    assert sum(isinstance(x[0],Float3) for x in f.calls)==192
    assert {q["max_distance_world_units"] for q in record["queries"]}=={0.8,80.0}
    print("PASS variants")
    raw=record["queries"][0]["physx_raw"]
    assert raw["python_type"]=="builtins.dict" and raw["fields"]==[
        "hit","position","collision","opaque"]
    assert raw["raw_repr"]==repr({"hit":True,"position":(0.0,0.0,5.0),
        "collision":"/World/ground/terrain/mesh","opaque":Float3(1,2,3)})
    assert raw["hit"] is True
    print("PASS raw_repr")
    assert all(q["start_w"][2]==5.4 and q["direction_w"]==[0.0,0.0,-1.0]
               and q["raycaster_hit_w"][2]==5.0 for q in record["queries"])
    assert record["ground_rays"][0]["start_w"]==[8.0,18.5,5.4]
    print("PASS start_z")
    assert len(record["kinematics"])==16
    assert all(len(k["foot_contact_forces_w"])==8 and
               k["foot_contact_forces_w"][6][2][2]==7.5 and
               math.isclose(k["root_ang_vel_w"][6][0],(i+1)/100,rel_tol=1e-6)
               for i,k in enumerate(record["kinematics"]))
    assert all(len(k["root_quat_w"][6])==4 for k in record["kinematics"])
    print("PASS foot_forces")
    miss=query_phase([tuple((x["start_w"],x["direction_w"])) for x in record["ground_rays"]],
                     f.physx,Float3,lambda rays:[(math.inf,math.inf,math.inf)]*3,
                     phase="after",step=0,**f.scene_query_context())
    assert miss[0]["raycaster_hit_w"]==["+inf","+inf","+inf"]
    json.dumps(miss,allow_nan=False)
    print("PASS raycaster_miss")
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)/"record"
        receipt=write_record(root,record)
        assert receipt["query_count"]==288 and verify_record(root)==record
        path=root/"physx_diag.json";path.write_bytes(path.read_bytes()+b" ")
        try:verify_record(root)
        except ProbeContractError as ex:assert str(ex)=="record_hash"
        else:raise AssertionError("tampered record accepted")
    print("PASS record_hash")


if __name__=="__main__":check()
