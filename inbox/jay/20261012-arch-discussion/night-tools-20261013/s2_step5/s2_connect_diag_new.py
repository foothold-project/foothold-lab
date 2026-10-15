"""Eight-case S2 connection capture. Import is CPU-only; Isaac launches only in main."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from s2_connect_check_17v import CASES, Criteria, check_path, HOLD_CODE
from s2_env_config_17v import BASE_TASK, EnvironmentSpec, configure_env


def sha256_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):
            h.update(block)
    return h.hexdigest()


def capture(provider, *, steps: int):
    if steps != 256 or provider.num_envs != 8:
        raise ValueError("eight envs and 256 control steps required")
    provider.reset()
    rows=[]
    for step in range(steps):
        if step==64: provider.translate()
        if step==128: provider.reset_new_height_position()
        if step==192: provider.change_yaw()
        provider.step_zero()
        row=provider.sample(step)
        row["intervention_code"]=1 if step==64 else 2 if step==128 else 3 if step==192 else 0
        row["mode"]=0 if step<16 else 1
        rows.append(row)
    keys=rows[0].keys()
    if any(row.keys()!=keys for row in rows):
        raise ValueError("capture fields changed")
    return {key:np.stack([row[key] for row in rows]) for key in keys}


class IsaacProvider:
    """Static-source-grounded bridge. Unverified mesh and interventions leave stage HOLD."""
    def __init__(self, spec):
        import gymnasium as gym
        import torch
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from isaaclab_tasks.utils import load_cfg_from_registry
        import isaaclab_tasks  # noqa: F401
        from s2_sensor_tracker_17v import SensorUpdateTracker
        if spec.num_envs!=8:
            raise ValueError("eight envs required")
        cfg=configure_env(load_cfg_from_registry(BASE_TASK,"env_cfg_entry_point"),spec,
                          diagnostic_kind="eight_case",reset_yaw_rad=0.0)
        self.env=RslRlVecEnvWrapper(gym.make(BASE_TASK,cfg=cfg))
        self.raw=self.env.unwrapped
        self.robot=self.raw.scene["robot"]
        self.scanner=self.raw.scene.sensors["height_scanner"]
        self.tracker=SensorUpdateTracker(self.scanner,num_envs=8,
                                         step_getter=lambda:self.raw.common_step_counter)
        self.num_envs=8
        self.episodes=np.zeros(8,dtype=np.int64)
        self._step=-1
        self._interventions=[]

    def reset(self):
        self.env.reset()

    def _pose(self, *, dx=0., dz=0., yaw_delta=0., reset=False):
        import torch
        pose=self.robot.data.root_pose_w.detach().clone()
        pose[:,0]+=dx
        pose[:,2]+=dz
        if yaw_delta:
            yaw=torch.atan2(2*(pose[:,3]*pose[:,6]+pose[:,4]*pose[:,5]),
                            1-2*(pose[:,5]**2+pose[:,6]**2))+yaw_delta
            pose[:,3:7]=0
            pose[:,3]=torch.cos(yaw/2)
            pose[:,6]=torch.sin(yaw/2)
        self.robot.write_root_pose_to_sim(pose)
        if reset:
            self.raw.scene.reset()
            self.episodes+=1
        self._interventions.append((dx,dz,yaw_delta,reset))

    def translate(self): self._pose(dx=.1)
    def reset_new_height_position(self): self._pose(dx=.2,dz=.2,reset=True)
    def change_yaw(self): self._pose(yaw_delta=1.5707963267948966)

    def step_zero(self):
        import torch
        self.env.step(torch.zeros_like(self.raw.action_manager.action))
        self._step+=1

    def sample(self, step):
        import torch
        from s2_env_adapter_17v import training_map, yaw_from_quat_wxyz
        sensor,receipt=self.tracker.snapshot()
        robot=self.robot.data
        def cpu(x): return x.detach().cpu().numpy()
        quat=robot.root_quat_w.detach().clone()
        mapped,_=training_map(sensor,mode="B",yaw_w=yaw_from_quat_wxyz(quat),
                              geometry_tolerance_m=.002)
        scene=self.raw.scene
        terrain=scene.terrain
        if terrain is None or not all(hasattr(terrain,x) for x in
                                      ("terrain_types","terrain_levels")):
            raise ValueError("terrain assignment accessor missing")
        return {"pos_w":cpu(sensor.data.pos_w),"ray_hits_w":cpu(sensor.data.ray_hits_w),
                "root_pos_w":cpu(robot.root_pos_w),"root_quat_w":cpu(quat),
                "env_origin_w":cpu(scene.env_origins),"height":cpu(mapped[:,:187]),
                "mask":cpu(mapped[:,187:]),"episode_ids":self.episodes.copy(),
                "sim_step":np.int64(self.raw.common_step_counter),
                "sensor_step":np.full(8,receipt["step"],dtype=np.int64),
                "sensor_generation":np.full(8,receipt["generation"],dtype=np.int64),
                "packet_id":np.asarray(f"{step}:{receipt['raw_sha256']}"),
                "edge_excluded":np.zeros((8,187),dtype=bool),
                "terrain_type":cpu(terrain.terrain_types),
                "terrain_level":cpu(terrain.terrain_levels)}

    def close(self):
        self.tracker.detach()
        self.env.close()


def main(argv=None):
    ap=argparse.ArgumentParser()
    for key in ("parent","out_root","criteria"):
        ap.add_argument("--"+key,required=True)
    for key in ("seed","num_envs","steps"):
        ap.add_argument("--"+key,required=True,type=int)
    for key in ("gap_proportion","stones_proportion","step_height_m","step_width_m",
                "geometry_tolerance_m"):
        ap.add_argument("--"+key,required=True,type=float)
    from isaaclab.app import AppLauncher
    AppLauncher.add_app_launcher_args(ap)
    a=ap.parse_args(argv)
    if a.num_envs!=8 or a.steps!=256 or not a.headless or not Path(a.parent).is_file():
        raise ValueError("eight-case plan and parent required")
    spec=EnvironmentSpec(a.seed,a.num_envs,a.gap_proportion,a.stones_proportion,
                         a.step_height_m,a.step_width_m,a.geometry_tolerance_m)
    criteria=Criteria(**json.loads(Path(a.criteria).read_text(encoding="utf-8")))
    root=Path(a.out_root).resolve()
    for forbidden in (Path("C:/isaac/ext/go2_rl_robotlab/_eval"),
                      Path("C:/isaac/ext/go2_rl_robotlab/source")):
        if root==forbidden.resolve() or forbidden.resolve() in root.parents:
            raise ValueError("output inside read-only source")
    root.mkdir(parents=True,exist_ok=False)
    launcher=AppLauncher(a)
    provider=None
    try:
        provider=IsaacProvider(spec)
        arrays=capture(provider,steps=256)
        np.savez_compressed(root/"capture.npz",**arrays)
        # Mesh/collision hashes and fixed-pose evidence need a verified live accessor.
        # Missing provenance is a deliberate HOLD in the independent checker.
        meta={"cases":list(CASES),"parent_sha256":sha256_file(a.parent),
              "code_sha256":sha256_file(__file__),"env_config_sha256":spec.sha256("eight_case"),
              "capture_sha256":sha256_file(root/"capture.npz"),
              "terrain_assignment_verified":False,"mesh_collision_verified":False,
              "started_epoch":time.time()}
        (root/"meta.json").write_text(json.dumps(meta,sort_keys=True,indent=2),encoding="utf-8")
        result=check_path(root,criteria)
        (root/"check.json").write_text(json.dumps(result,sort_keys=True,indent=2),encoding="utf-8")
        return 0 if result["verdict"]=="PASS" else HOLD_CODE
    finally:
        if provider is not None: provider.close()
        launcher.app.close()


if __name__=="__main__":
    raise SystemExit(main())
