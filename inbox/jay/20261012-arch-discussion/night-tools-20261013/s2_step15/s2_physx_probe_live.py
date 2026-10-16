"""Kit adapter for s2_physx_probe_diag. No standalone launch entry is authorized.

A3.3's owner pins s2_connect_diag_17v.py and 256 steps. This adapter is ready
for a separate attended 16-step contract, and intentionally cannot bypass it.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

from s2_physx_probe_diag import collect, write_record, ProbeContractError


class A33LiveBridge:
    def __init__(self, provider):
        """Provider must be a33.s2_connect_diag_17v.IsaacProvider after reset."""
        a33 = Path(__file__).resolve().parent/"a33"
        source = a33/"s2_connect_diag_17v.py"
        cfg = ast.parse((a33/"s2_env_config_17v.py").read_text(encoding="utf-8"))
        task = next((ast.literal_eval(node.value) for node in cfg.body if isinstance(node,ast.Assign)
                     and any(isinstance(t,ast.Name) and t.id=="BASE_TASK" for t in node.targets)),None)
        if (task != "RobotLab-Go2-v0" or provider.num_envs != 8 or
            Path(inspect.getfile(type(provider))).resolve()!=source.resolve()):
            raise ProbeContractError("a33_environment_required")
        terrain=provider.raw.scene.terrain
        types=terrain.terrain_types.detach().cpu().tolist()
        levels=terrain.terrain_levels.detach().cpu().tolist()
        if types!=[0,0,1,1,2,2,3,3] or levels!=[0]*8:
            raise ProbeContractError("a33_case_assignment")
        self.p = provider
        self.num_envs = 8
        self.task = task
        self.case_count = 8
        self.optimizer_steps = 0
        self.env0_origin_w = provider.raw.scene.env_origins[0].detach().cpu().tolist()
        self.flat_ground_z = 0.0

    def scene_query_context(self):
        import omni.usd
        from pxr import UsdPhysics
        stage = omni.usd.get_context().get_stage()
        scenes = [str(prim.GetPath()) for prim in stage.Traverse() if prim.IsA(UsdPhysics.Scene)]
        if not scenes:
            raise ProbeContractError("physics_scene_path_missing")
        return {"scene_paths":scenes,
                "mesh_prim_paths":[str(x) for x in self.p.scanner.cfg.mesh_prim_paths],
                "collision_group":int(self.p.raw.cfg.scene.terrain.collision_group)}

    def step_zero(self):
        self.p.step_zero()

    def kinematic_frame(self):
        sensor = self.p.raw.scene.sensors["contact_forces"]
        ids,names = sensor.find_bodies(["FL_foot","FR_foot","RL_foot","RR_foot"],preserve_order=True)
        if names != ["FL_foot","FR_foot","RL_foot","RR_foot"]:
            raise ProbeContractError("four_feet_names")
        robot = self.p.robot.data
        return {"foot_names":names,
                "foot_contact_forces_w":sensor.data.net_forces_w[:,ids,:].detach().cpu().numpy(),
                "root_ang_vel_w":robot.root_ang_vel_w.detach().cpu().numpy(),
                "root_quat_w":robot.root_quat_w.detach().cpu().numpy(),
                "sim_step":self.p.raw.common_step_counter}


def collect_inside_approved_owner(provider, out_root):
    """Call only from a new attended owner with a separately reviewed manifest."""
    import carb
    import torch
    from omni.physx import get_physx_scene_query_interface
    from isaaclab.sensors.ray_caster.ray_caster import RayCaster
    from isaaclab.utils.warp.ops import raycast_mesh

    if provider._step != -1:
        raise ProbeContractError("provider_not_fresh")
    provider.reset()
    bridge = A33LiveBridge(provider)
    query = get_physx_scene_query_interface()
    mesh_path = str(provider.scanner.cfg.mesh_prim_paths[0])
    mesh = RayCaster.meshes[mesh_path]
    device = provider.robot.data.root_pos_w.device

    def warp_cast(rays):
        starts = torch.tensor([x[0] for x in rays],device=device,dtype=torch.float32)
        dirs = torch.tensor([x[1] for x in rays],device=device,dtype=torch.float32)
        hits,*_ = raycast_mesh(starts,dirs,mesh,max_dist=80.0)
        return hits.detach().cpu().tolist()

    record = collect(bridge,query.raycast_closest,carb.Float3,warp_cast)
    return write_record(out_root,record)


if __name__ == "__main__":
    raise SystemExit("supervisor_contract_extension_required: no standalone Kit launch")
