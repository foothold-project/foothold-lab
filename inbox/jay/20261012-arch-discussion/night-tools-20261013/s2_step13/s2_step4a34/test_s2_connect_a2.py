"""Static world scene known answers and ASTRA 17w false-PASS cases. CPU only."""
import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile

import numpy as np

from s2_connect_check_17v import CASES,Criteria,GRID,check_arrays
from s2_known_scene_a2 import answer_sha256,oracle


def fixture():
    t,n,r=256,8,187
    pos=np.zeros((t,n,3),dtype=np.float64);pos[...,2]=.5
    pos[64:,:,0]=.1;pos[128:,:,0]=.3;pos[128:,:,2]=.7
    quat=np.zeros((t,n,4),dtype=np.float64)
    yaw=np.zeros((t,n));yaw[:,1::2]=math.pi/2;yaw[192:]+=math.pi/2
    quat[...,0]=np.cos(yaw/2);quat[...,3]=np.sin(yaw/2)
    c,s=np.cos(yaw)[...,None],np.sin(yaw)[...,None]
    hits=np.empty((t,n,r,3),dtype=np.float64)
    hits[...,0]=pos[...,0,None]+c*GRID[None,None,:,0]-s*GRID[None,None,:,1]
    hits[...,1]=pos[...,1,None]+s*GRID[None,None,:,0]+c*GRID[None,None,:,1]
    start_xy=hits[...,:2].copy()  # the rays' own XY, also where the hit is a miss
    edge=np.zeros((t,n,r),dtype=bool)
    for env in range(n):
        kind=("flat","obstacles","gap","stepping_stones")[env//2]
        z,finite,distance=oracle(kind,hits[:,env,:,:2])
        hits[:,env,:,2]=z
        hits[:,env][~finite]=np.inf
        edge[:,env]=distance<=.005
    finite=np.isfinite(hits).all(-1)
    height=np.clip(pos[...,2,None]-.5-hits[...,2],-1,1);height[~finite]=1
    starts=np.empty_like(hits);starts[...,:2]=start_xy
    starts[...,2]=pos[...,2,None]+20
    dirs=np.zeros_like(hits);dirs[...,2]=-1
    data={"pos_w":pos,"ray_hits_w":hits,"root_pos_w":pos.copy(),"root_quat_w":quat,
          "env_origin_w":np.zeros_like(pos),"height":height,"mask":finite.astype(np.float64),
          "episode_ids":np.broadcast_to((np.arange(t)>=128)[:,None],(t,n)).astype(np.int64).copy(),
          "sim_step":np.arange(t,dtype=np.int64),
          "sensor_step":np.broadcast_to(np.arange(t)[:,None],(t,n)).copy(),
          "sensor_generation":np.broadcast_to(np.arange(1,t+1)[:,None],(t,n)).copy(),
          "sensor_timestamp":np.broadcast_to((np.where(np.arange(t)>=128,np.arange(t)-127,np.arange(t))*.02)[:,None],(t,n)).copy(),
          "packet_id":np.asarray([f"p{i}" for i in range(t)]),
          "intervention_code":np.asarray([1 if i==64 else 2 if i==128 else 3 if i==192 else 0 for i in range(t)]),
          "mode":np.asarray([0 if i<16 else 1 for i in range(t)]),
          "edge_excluded":edge,"terrain_type":np.broadcast_to(np.asarray([0,0,1,1,2,2,3,3]),(t,n)).copy(),
          "terrain_level":np.zeros((t,n),dtype=np.int64),
          "ray_starts_w":starts,"ray_directions_w":dirs,"ray_index":np.arange(r),
          "termination":np.zeros((t,n),dtype=np.int64),"timeout":np.zeros((t,n),dtype=bool),
          "reset_mask":np.broadcast_to((np.arange(t)==128)[:,None],(t,n)).copy()}
    root=Path(tempfile.mkdtemp(prefix="s2_a2_fixture_"))
    boundary=root/"boundary.bin";boundary.write_bytes(edge.tobytes())
    mesh=root/"mesh.json"
    mesh.write_text(json.dumps({"kind":"observed_collision_mesh","scope":"sampled_collision_response","branches_ok":True,
                                "prim_path":"/World/ground",
                                "vertices_sha256":"v"*64,"faces_sha256":"f"*64,
                                "collision_sha256":"c"*64}),encoding="utf-8")
    meta={k:"fixture" for k in ("parent_sha256","code_sha256","capture_sha256","env_config_sha256",
         "isaac_version","kit_version","torch_version","driver_version","mesh_transform_sha256",
         "asset_sha256")}
    meta.update(cases=list(CASES),terrain_assignment_verified=True,mesh_collision_verified=True,
                fixed_pose_verified=True,boundary_count=int(edge.sum()),optimizer_steps=0,control_steps=256,
                scene_answer_sha256=answer_sha256(),mesh_prim_path="/World/ground",
                mesh_vertices_sha256="v"*64,mesh_faces_sha256="f"*64,
                collision_mesh_sha256="c"*64,root_sensor_offset_b=[0.,0.,0.],
                boundary_exclusion_sha256=hashlib.sha256(edge.tobytes()).hexdigest(),
                boundary_evidence_path=str(boundary),boundary_evidence_sha256=hashlib.sha256(boundary.read_bytes()).hexdigest(),
                mesh_evidence_path=str(mesh),mesh_evidence_sha256=hashlib.sha256(mesh.read_bytes()).hexdigest())
    return meta,data


def check(name,good):
    print(("PASS" if good else "FAIL")+" "+name,flush=True)
    assert good,name


def main():
    c=Criteria(.002,.002,.005,256,16)
    m,d=fixture()
    normal=check_arrays(m,d,c)
    check("analytic_static_world_8x256",normal["verdict"]=="PASS")
    cases=[
        ("height_nan",lambda x:x["height"].__setitem__((0,2,0),np.nan),"height_nonfinite"),
        ("fixed_one",lambda x:x["mode"].__setitem__(slice(1,16),1),"fixed_schedule"),
        ("root_100m",lambda x:x["root_pos_w"].__setitem__((slice(None),slice(None),0),x["root_pos_w"][:,:,0]+100),"root_sensor_transform"),
        ("marker_step90",lambda x:x["ray_hits_w"].__setitem__((slice(None),3,slice(None),2),0.),"scene_hit_z"),
        ("marker_stones90",lambda x:x["ray_hits_w"].__setitem__((slice(None),7,slice(None),2),0.),"scene_hit_z"),
        ("flat_reset_static",lambda x:x["height"].__setitem__((slice(128,None),slice(0,2),slice(None)),0.),"height_or_offset"),
        ("boundary_one",lambda x:x["edge_excluded"].__setitem__((0,2,0),True),"boundary_mask"),
    ]
    for name,mut,want in cases:
        x=copy.deepcopy(d);mut(x)
        got=check_arrays(m,x,c)
        check(name+"_"+want,got["verdict"]=="HOLD" and want in got["reasons"])
    bad=dict(m);bad["mesh_evidence_sha256"]="0"*64
    check("mesh_external_hash_rejected","mesh_evidence_hash" in check_arrays(bad,d,c)["reasons"])
    bad=dict(m);bad["boundary_evidence_sha256"]="0"*64
    check("boundary_external_hash_rejected","boundary_evidence_hash" in check_arrays(bad,d,c)["reasons"])

if __name__=="__main__":main()
