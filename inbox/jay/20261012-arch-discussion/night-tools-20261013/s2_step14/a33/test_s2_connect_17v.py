"""Independent analytic eight-case CPU packet, plus named counterexamples."""
import math
import numpy as np

from s2_connect_check_17v import CASES, Criteria, GRID, check_arrays
from s2_connect_diag_17v import capture


def fixture():
    t,n,r=256,8,187
    pos=np.zeros((t,n,3),dtype=np.float64)
    pos[...,2]=.5
    pos[64:,:,0]=.1
    pos[128:,:,0]=.3
    pos[128:,:,2]=.7
    quat=np.zeros((t,n,4),dtype=np.float64)
    quat[...,0]=1
    yaw=np.zeros((t,n))
    yaw[:,1::2]=math.pi/2
    yaw[192:]+=math.pi/2
    quat[...,0]=np.cos(yaw/2)
    quat[...,3]=np.sin(yaw/2)
    c,s=np.cos(yaw)[...,None],np.sin(yaw)[...,None]
    hits=np.empty((t,n,r,3),dtype=np.float64)
    hits[...,0]=pos[...,0,None]+c*GRID[None,None,:,0]-s*GRID[None,None,:,1]
    hits[...,1]=pos[...,1,None]+s*GRID[None,None,:,0]+c*GRID[None,None,:,1]
    hits[...,2]=pos[...,2,None]-.5
    hits[:,2:4,40,2]+=.2
    hits[:,6:8,42,2]+=.2
    hits[:,4:6,10,:]=np.inf
    hits[:,4:6,11,2]-=2
    finite=np.isfinite(hits).all(-1)
    height=np.clip(pos[...,2,None]-.5-hits[...,2],-1,1)
    height[~finite]=1
    data={"pos_w":pos,"ray_hits_w":hits,"root_pos_w":pos.copy(),"root_quat_w":quat,
          "env_origin_w":np.zeros_like(pos),"height":height,"mask":finite.astype(np.float64),
          "episode_ids":np.broadcast_to((np.arange(t)>=128)[:,None],(t,n)).astype(np.int64).copy(),
          "sim_step":np.arange(t,dtype=np.int64),
          "sensor_step":np.broadcast_to(np.arange(t)[:,None],(t,n)).copy(),
          "sensor_generation":np.broadcast_to(np.arange(1,t+1)[:,None],(t,n)).copy(),
          "packet_id":np.asarray([f"p{i}" for i in range(t)]),
          "intervention_code":np.asarray([1 if i==64 else 2 if i==128 else 3 if i==192 else 0 for i in range(t)]),
          "mode":np.asarray([0 if i<16 else 1 for i in range(t)]),
          "edge_excluded":np.zeros((t,n,r),dtype=bool),
          "terrain_type":np.broadcast_to(np.asarray([0,0,1,1,2,2,3,3]),(t,n)).copy(),
          "terrain_level":np.zeros((t,n),dtype=np.int64)}
    meta={k:"abc" for k in ("parent_sha256","code_sha256","capture_sha256","env_config_sha256",
         "isaac_version","kit_version","torch_version","driver_version","mesh_prim_path",
         "mesh_vertices_sha256","mesh_faces_sha256","mesh_transform_sha256",
         "collision_mesh_sha256","asset_sha256","boundary_exclusion_sha256","stone_markers_sha256")}
    meta.update(cases=list(CASES),terrain_assignment_verified=True,mesh_collision_verified=True,
                fixed_pose_verified=True,boundary_count=0,optimizer_steps=0,control_steps=256)
    return meta,data


def main():
    c=Criteria(.002,.002,.005,256,16)
    m,d=fixture()
    normal=check_arrays(m,d,c)
    assert normal["verdict"]=="PASS",normal
    print("PASS analytic_8x256")
    changes=[("stale",lambda x:x["sensor_generation"].__setitem__((128,0),127),"stale_packet"),
             ("ray_order",lambda x:x["ray_hits_w"].__setitem__((0,0,0),x["ray_hits_w"][0,0,1]),"grid_or_yaw"),
             ("offset_20m",lambda x:x["height"].__setitem__((0,0,0),20.),"height_or_offset"),
             ("yaw_nan",lambda x:x["root_quat_w"].__setitem__((0,0,0),np.nan),"pose_nonfinite"),
             ("hidden_plane",lambda x:x["ray_hits_w"].__setitem__((slice(None),slice(4,6),10,2),0.),"gap_two_cases"),
             ("boundary_unreported",lambda x:x["edge_excluded"].__setitem__((0,0,0),True),"boundary_unreported")]
    for name,mut,want in changes:
        _,x=fixture()
        mut(x)
        result=check_arrays(m,x,c)
        assert result["verdict"]=="HOLD" and want in result["reasons"],(name,result)
        print("PASS",name,want)

    class FakeProvider:
        num_envs=8
        def __init__(self): self.i=-1; self.actions=[]
        def reset(self): self.actions.append("reset")
        def translate(self): self.actions.append("translate")
        def reset_new_height_position(self): self.actions.append("reset_height")
        def change_yaw(self): self.actions.append("yaw")
        def step_zero(self): self.i+=1
        def sample(self,i): return {"sim_step":np.int64(i)}
    fake=FakeProvider()
    got=capture(fake,steps=256)
    assert fake.actions==["reset","translate","reset_height","yaw"]
    assert len(got["sim_step"])==256 and got["intervention_code"][[64,128,192]].tolist()==[1,2,3]
    print("PASS intervention_schedule")

from test_s2_connect_a2 import fixture as fixture, main as main

if __name__=="__main__": main()
