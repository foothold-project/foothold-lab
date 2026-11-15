"""Eight-case S2 connection capture. Import is CPU-only; Isaac launches only in main."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback

import numpy as np

from s2_connect_check_17v import CASES, Criteria, check_path, HOLD_CODE
from s2_env_config_17v import BASE_TASK, EnvironmentSpec, configure_env
from s2_capture_journal_a2 import CaptureJournal,atomic_json
from s2_known_scene_a2 import answer_sha256


def sha256_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):
            h.update(block)
    return h.hexdigest()


def capture(provider, *, steps: int, journal=None):
    if steps != 256 or provider.num_envs != 8:
        raise ValueError("eight envs and 256 control steps required")
    rows=[]
    step=-1
    stage="reset"
    try:
        provider.reset()
        for step in range(steps):
            stage="intervention"
            if step==64: provider.translate()
            if step==128: provider.reset_new_height_position()
            if step==192: provider.change_yaw()
            stage="step_zero"
            provider.step_zero()
            if hasattr(provider,"sample_raw"):
                stage="sample_raw"
                raw=provider.sample_raw(step)
                if False:journal.raw(step,raw)
                stage="derive_map"
                row=provider.derive_map(raw)
            else:
                stage="sample"
                row=provider.sample(step)
                if journal is not None:journal.raw(step,row)
            stage="row_bookkeeping"
            row["intervention_code"]=1 if step==64 else 2 if step==128 else 3 if step==192 else 0
            row["mode"]=0 if step<16 else 1
            rows.append(row)
            if journal is not None:
                journal.derived(step,row)
                journal.valid(step)
    except BaseException as ex:
        # 17x: every stage (reset / intervention / step / sampling / mapping) preserves its failure evidence.
        if journal is not None:
            journal.stage_failure(step,stage,repr(ex),getattr(provider,"emergency_raw",None))
        raise
    keys=rows[0].keys()
    if any(row.keys()!=keys for row in rows):
        raise ValueError("capture fields changed")
    out={key:np.stack([row[key] for row in rows]) for key in keys}
    if "ray_index" in out:
        # 17x: the checker contract is one (187,) index vector; per-row copies must be identical.
        index=out["ray_index"]
        if not np.all(index==index[0]):raise ValueError("ray_index changed during capture")
        out["ray_index"]=index[0]
    return out


class IsaacProvider:
    """Static-source-grounded bridge. Unverified mesh and interventions leave stage HOLD."""
    def __init__(self, spec, *, hook_source_path, hook_source_sha256, on_cfg=None):
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
        cfg_blob=json.dumps(cfg.to_dict(),sort_keys=True,default=str).encode()
        self.final_cfg_sha256=hashlib.sha256(cfg_blob).hexdigest()
        self.final_cfg_json=cfg_blob.decode()
        self.initial_asset_path=str(cfg.scene.robot.spawn.usd_path)
        if on_cfg is not None:
            # 17x: declare the final cfg and asset BEFORE gym.make so a creation failure still leaves them on disk.
            on_cfg({"cfg_sha256":self.final_cfg_sha256,"cfg":self.final_cfg_json,
                    "scene_answer_sha256":answer_sha256(),"asset_path":self.initial_asset_path})
        self.env=RslRlVecEnvWrapper(gym.make(BASE_TASK,cfg=cfg))
        self.raw=self.env.unwrapped
        self.robot=self.raw.scene["robot"]
        self.scanner=self.raw.scene.sensors["height_scanner"]
        self.tracker=SensorUpdateTracker(self.scanner,num_envs=8,
                                         step_getter=lambda:self.raw.common_step_counter,
                                         root_pose_getter=lambda:self.robot.data.root_pose_w,
                                         expected_hook_path=hook_source_path,
                                         expected_hook_sha256=hook_source_sha256)
        self.num_envs=8
        self.geometry_tolerance_m=spec.geometry_tolerance_m
        self.episodes=np.zeros(8,dtype=np.int64)
        self._step=-1
        self._interventions=[]
        self.last_obs=None;self.last_dones=None;self.last_extras={}

    def reset(self):
        self.env.reset()
        import torch
        pose=self.robot.data.root_pose_w.detach().clone()
        pose[1::2,3:7]=0
        pose[1::2,3]=math.cos(math.pi/4)
        pose[1::2,6]=math.sin(math.pi/4)
        self.robot.write_root_pose_to_sim(pose)

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
        self.last_obs,_,self.last_dones,self.last_extras=self.env.step(
            torch.zeros_like(self.raw.action_manager.action))
        self.episodes+=self.last_dones.detach().cpu().numpy().astype(np.int64)
        self._step+=1

    def emergency_raw(self,step):
        def cpu(x):return x.detach().cpu().numpy()
        data=self.scanner._data
        return {"step":np.int64(step),"pos_w":cpu(data.pos_w),"ray_hits_w":cpu(data.ray_hits_w),
                "root_pos_w":cpu(self.robot.data.root_pos_w),
                "root_quat_w":cpu(self.robot.data.root_quat_w),
                "error_stage":np.asarray("sensor_receipt_before_map")}

    def sample_raw(self, step):
        import torch
        sensor,receipt=self.tracker.snapshot()
        robot=self.robot.data
        def cpu(x): return x.detach().cpu().numpy()
        quat=robot.root_quat_w.detach().clone()
        scene=self.raw.scene
        terrain=scene.terrain
        if terrain is None or not all(hasattr(terrain,x) for x in
                                      ("terrain_types","terrain_levels")):
            raise ValueError("terrain assignment accessor missing")
        obs=self.last_obs
        policy=obs.get("policy") if hasattr(obs,"get") else None
        critic=obs.get("critic") if hasattr(obs,"get") else None
        extras=self.last_extras or {}
        timeouts=extras.get("time_outs") if isinstance(extras,dict) else None
        return {"pos_w":cpu(sensor.data.pos_w),"ray_hits_w":cpu(sensor.data.ray_hits_w),
                "root_pos_w":cpu(robot.root_pos_w),"root_quat_w":cpu(quat),
                "ray_starts_w":cpu(self.scanner._ray_starts_w),
                "ray_directions_w":cpu(self.scanner._ray_directions_w),
                "ray_index":np.arange(187),
                "env_origin_w":cpu(scene.env_origins),"episode_ids":self.episodes.copy(),
                "sim_step":np.int64(self.raw.common_step_counter),
                "sensor_step":np.full(8,receipt["step"],dtype=np.int64),
                "sensor_generation":np.asarray(receipt["generation_by_env"],dtype=np.int64),
                "sensor_timestamp":np.asarray(receipt["sensor_timestamp_by_env"],dtype=np.float64),
                "sensor_raw_sha256_by_env":np.asarray(receipt["raw_sha256_by_env"]),
                "root_pose_sha256_by_env":np.asarray(receipt["pose_sha256_by_env"]),
                "hook_source_sha256":np.asarray(receipt["hook_source_sha256"]),
                "packet_id":np.asarray(f"{step}:{receipt['raw_sha256']}"),
                "terrain_type":cpu(terrain.terrain_types),
                "terrain_level":cpu(terrain.terrain_levels),
                "obs_policy":cpu(policy) if policy is not None else np.zeros((8,0)),
                "obs_critic":cpu(critic) if critic is not None else np.zeros((8,0)),
                "termination":cpu(self.last_dones),
                "timeout":cpu(timeouts) if timeouts is not None else np.zeros(8,dtype=bool),
                "reset_mask":np.full(8,step==128,dtype=bool)}

    def derive_map(self,row):
        import torch
        from types import SimpleNamespace
        from s2_env_adapter_17v import training_map,yaw_from_quat_wxyz
        from s2_known_scene_a2 import oracle
        sensor=SimpleNamespace(cfg=self.scanner.cfg,data=SimpleNamespace(
            pos_w=torch.as_tensor(row["pos_w"],device=self.robot.data.root_pos_w.device),
            ray_hits_w=torch.as_tensor(row["ray_hits_w"],device=self.robot.data.root_pos_w.device)))
        quat=torch.as_tensor(row["root_quat_w"],device=sensor.data.pos_w.device)
        mapped,_=training_map(sensor,mode="B",yaw_w=yaw_from_quat_wxyz(quat),
                              geometry_tolerance_m=self.geometry_tolerance_m)
        row["height"]=mapped[:,:187].detach().cpu().numpy()
        row["mask"]=mapped[:,187:].detach().cpu().numpy()
        unclipped=row["pos_w"][:,2,None]-.5-row["ray_hits_w"][:,:,2]
        unclipped[np.isposinf(row["ray_hits_w"]).all(axis=-1)]=np.inf
        row["height_unclipped"]=unclipped
        edge=np.zeros((8,187),dtype=bool)
        for env in range(8):
            kind=("flat","obstacles","gap","stepping_stones")[env//2]
            _,_,distance=oracle(kind,row["ray_starts_w"][env,:,:2]-row["env_origin_w"][env,:2])
            edge[env]=distance<=.005
        row["edge_excluded"]=edge
        return row

    def close(self):
        self.tracker.detach()
        self.env.close()


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    early=argparse.ArgumentParser(add_help=False)
    for key in ("out_root","attempt","gpu_uuid","asset_path"):
        early.add_argument("--"+key,required=True)
    e,_=early.parse_known_args(argv)
    root=Path(e.out_root).resolve()
    for forbidden in (Path("C:/isaac/ext/go2_rl_robotlab/_eval"),
                      Path("C:/isaac/ext/go2_rl_robotlab/source")):
        if root==forbidden.resolve() or forbidden.resolve() in root.parents:
            raise ValueError("output inside read-only source")
    journal=CaptureJournal(root,{"attempt":e.attempt,"gpu_uuid":e.gpu_uuid,"argv":argv,
                                 "python":sys.executable,"import_path":list(sys.path),
                                 "asset_path":e.asset_path,"purpose":"stage0_information_only"})
    launcher=None;provider=None;cleanup={}
    try:
        return _main_capture(argv,journal)
    except BaseException as ex:
        journal.fail(repr(ex),traceback.format_exc(),cleanup)
        print(traceback.format_exc(),file=sys.stderr,flush=True)
        return HOLD_CODE


def _main_capture(argv,journal):
    ap=argparse.ArgumentParser()
    for key in ("parent","out_root","criteria","attempt","gpu_uuid","gpu_bus_id","asset_path",
                "hook_source_path","hook_source_sha256","scene_answer_sha256"):
        ap.add_argument("--"+key,required=True)
    for key in ("seed","num_envs","steps"):
        ap.add_argument("--"+key,required=True,type=int)
    for key in ("gap_proportion","stones_proportion","step_height_m","step_width_m",
                "geometry_tolerance_m"):
        ap.add_argument("--"+key,required=True,type=float)
    from isaaclab.app import AppLauncher
    AppLauncher.add_app_launcher_args(ap)
    a=ap.parse_args(argv)
    if (a.num_envs!=8 or a.steps!=256 or not a.headless or a.device!="cuda:0" or
        argv.count("--device")!=1 or not Path(a.parent).is_file() or
        a.scene_answer_sha256!=answer_sha256()):
        raise ValueError("eight-case plan and parent required")
    spec=EnvironmentSpec(a.seed,a.num_envs,a.gap_proportion,a.stones_proportion,
                         a.step_height_m,a.step_width_m,a.geometry_tolerance_m)
    criteria=Criteria(**json.loads(Path(a.criteria).read_text(encoding="utf-8")))
    root=journal.root
    launcher=AppLauncher(a)
    provider=None
    cleanup={"provider_closed":False,"app_closed":False}
    try:
        if launcher.device_id!=0:raise ValueError("Kit requested device is not visible cuda:0")
        from s2_device_binding_a2 import inspect_child_device,DeviceHold
        device_evidence={}
        try:
            device_info=inspect_child_device(a.gpu_uuid,launcher,evidence=device_evidence)
        except DeviceHold as ex:
            atomic_json(root/"device_binding.json",{"hold":str(ex),"evidence":device_evidence,
                                                    "expected_uuid":a.gpu_uuid})
            raise
        atomic_json(root/"device_binding.json",{**device_info,"evidence":device_evidence,
                                                "expected_uuid":a.gpu_uuid})
        def declare_cfg(blob):
            atomic_json(root/"final_cfg.json",blob)
            if Path(blob["asset_path"]).resolve()!=Path(a.asset_path).resolve():
                raise ValueError("asset path differs from approved argv")
        provider=IsaacProvider(spec,hook_source_path=a.hook_source_path,
                               hook_source_sha256=a.hook_source_sha256,on_cfg=declare_cfg)
        from s2_mesh_probe_a2 import probe as mesh_probe
        atomic_json(root/"mesh_probe.json",mesh_probe(provider.scanner))
        arrays=capture(provider,steps=256,journal=journal)
        np.savez_compressed(root/"capture.npz",**arrays)
        # Mesh/collision hashes and fixed-pose evidence need a verified live accessor.
        # Missing provenance is a deliberate HOLD in the independent checker.
        meta={"cases":list(CASES),"parent_sha256":sha256_file(a.parent),
              "code_sha256":sha256_file(__file__),"env_config_sha256":spec.sha256("eight_case"),
              "capture_sha256":sha256_file(root/"capture.npz"),
              "optimizer_steps":0,"control_steps":256,
              "terrain_assignment_verified":False,"mesh_collision_verified":False,
              "fixed_pose_verified":False,
              "started_epoch":journal.started_epoch,"attempt":a.attempt,
              "device_uuid":a.gpu_uuid,"final_cfg_sha256":provider.final_cfg_sha256,
              "device_binding":device_info,
              "scene_answer_sha256":answer_sha256(),"purpose":"stage0_information_only"}
        (root/"meta.json").write_text(json.dumps(meta,sort_keys=True,indent=2),encoding="utf-8")
        result=check_path(root,criteria)
        (root/"check.json").write_text(json.dumps(result,sort_keys=True,indent=2),encoding="utf-8")
        journal.complete(captured=256,cleanup={"provider_close":"pending","app_close":"pending"})
        return HOLD_CODE
    except BaseException as ex:
        journal.fail(repr(ex),traceback.format_exc(),cleanup)
        print(traceback.format_exc(),file=sys.stderr,flush=True)
        return HOLD_CODE
    finally:
        if provider is not None:
            try:provider.close();cleanup["provider_closed"]=True
            except BaseException as ex:cleanup["provider_close_error"]=repr(ex)
        try:launcher.app.close();cleanup["app_closed"]=True
        except BaseException as ex:cleanup["app_close_error"]=repr(ex)
        atomic_json(root/"cleanup.json",cleanup)


if __name__=="__main__":
    raise SystemExit(main())
