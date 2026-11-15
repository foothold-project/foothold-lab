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

from s2_connect_check_17v import CASES, Criteria, check_path, HOLD_CODE, scene_expectation
from s2_env_config_17v import BASE_TASK, EnvironmentSpec, configure_env
from s2_capture_journal_a2 import CaptureJournal,atomic_json
from s2_known_scene_a2 import answer_sha256
from s2_a34_provenance import asset_snapshot, assert_asset_unchanged, usd_evidence, ProvenanceHold
from s2_physx_probe_diag import ProbeContractError

EXPECTED_URDF_SHA256 = "f130b1d2cc61f3c1e54dab8f8b9ad27b0b54f85c968d89ea242c6d70ab2a5810"
ROBOTLAB_ASSET_CFG = Path("C:/isaac/ext/go2_rl_robotlab/source/robot_lab/robot_lab/assets/unitree.py")
CONVERTER_SOURCE = Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab/sim/converters/asset_converter_base.py")


def sha256_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):
            h.update(block)
    return h.hexdigest()


def asset_sha256_of(asset):
    """Hash the RobotLab URDF asset, or a remote reference if one is explicitly supplied.
    Empty string when neither is readable (the checker then HOLDs provenance_missing)."""
    try:
        p=Path(asset)
        if p.is_file():
            return sha256_file(p)
    except (OSError,ValueError):
        pass
    try:
        import omni.client
        result,_,content=omni.client.read_file(str(asset))
        if result==omni.client.Result.OK:
            return hashlib.sha256(bytes(memoryview(content))).hexdigest()
    except Exception:
        pass
    return ""


def versions_snapshot():
    """A3.2: tool versions the checker requires. An empty string stays empty on purpose (the checker HOLDs)."""
    out={"isaac_version":"","kit_version":"","torch_version":"","driver_version":""}
    try:
        import importlib.metadata as md
        parts=[]
        for name in ("isaaclab","isaacsim"):
            try:parts.append(name+"="+md.version(name))
            except Exception:pass
        out["isaac_version"]=";".join(parts)
    except Exception:pass
    try:
        import omni.kit.app
        out["kit_version"]=str(omni.kit.app.get_app().get_kit_version())
    except Exception:pass
    try:
        import torch
        out["torch_version"]=str(torch.__version__)
    except Exception:pass
    try:
        import pynvml
        pynvml.nvmlInit()
        v=pynvml.nvmlSystemGetDriverVersion()
        out["driver_version"]=v.decode() if isinstance(v,bytes) else str(v)
    except Exception:pass
    return out


def fixed_pose_ok(arrays,tolerance=.002):
    return bool(np.max(np.abs(arrays["root_pos_w"][:16]-arrays["root_pos_w"][0]),initial=0)<=tolerance and
                np.max(np.abs(arrays["root_quat_w"][:16]-arrays["root_quat_w"][0]),initial=0)<=tolerance and
                np.max(np.abs(arrays["pos_w"][:16]-arrays["pos_w"][0]),initial=0)<=tolerance)


def terrain_assignment_ok(arrays):
    t=arrays["terrain_type"]
    return bool(np.array_equal(t[0],[0,0,1,1,2,2,3,3]) and np.all(t==t[0]) and
                not np.any(arrays["terrain_level"]!=0) and np.isfinite(arrays["env_origin_w"]).all())


def finalize_provenance(root,arrays,edge,observed,versions,asset_sha256,mount):
    """Write the boundary and mesh evidence files and return the meta fields the checker reads.
    `observed` is the result of observe_collision_kit (or a stand-in): {'evidence': dict|None, 'errors': [...], 'usd': {...}}."""
    root=Path(root)
    edge=np.asarray(edge,dtype=bool)
    boundary=root/"boundary_evidence.bin"
    boundary.write_bytes(edge.tobytes())
    meta={**versions,"asset_sha256":asset_sha256 or "",
          "boundary_count":int(edge.sum()),
          "boundary_exclusion_sha256":hashlib.sha256(edge.tobytes()).hexdigest(),
          "boundary_evidence_path":str(boundary),
          "boundary_evidence_sha256":sha256_file(boundary),
          "root_sensor_offset_b":mount,
          "terrain_assignment_verified":terrain_assignment_ok(arrays),
          "fixed_pose_verified":fixed_pose_ok(arrays),
          "mesh_collision_verified":False}
    atomic_json(root/"a32_probe_report.json",{"errors":observed.get("errors",[]),"usd":observed.get("usd"),
                                              "evidence_kind":(observed.get("evidence") or {}).get("kind"),
                                              "sensor_frame":observed.get("sensor_frame"),
                                              "recorded_edge_differences":observed.get("recorded_edge_differences")})
    evidence=observed.get("evidence")
    raw=observed.get("raw")
    if evidence and raw is not None:
        raw_file=root/"physx_queries.npz"
        np.savez_compressed(raw_file,**raw)
        evidence=dict(evidence,raw_query_file=str(raw_file),raw_query_file_sha256=sha256_file(raw_file))
    if evidence:
        mesh=root/"mesh_evidence.json"
        mesh.write_text(json.dumps(evidence,sort_keys=True,indent=2,default=str),encoding="utf-8")
        meta.update(mesh_evidence_path=str(mesh),mesh_evidence_sha256=sha256_file(mesh),
                    mesh_prim_path=evidence["prim_path"],mesh_vertices_sha256=evidence["vertices_sha256"],
                    mesh_faces_sha256=evidence["faces_sha256"],mesh_transform_sha256=evidence["world_transform_sha256"],
                    collision_mesh_sha256=evidence["collision_sha256"],
                    mesh_collision_verified=evidence["kind"]=="observed_collision_mesh")
    return meta


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
            if step<16 and hasattr(provider,"observe_a34"):
                stage="a34_probe"
                provider.observe_a34(step)
            if hasattr(provider,"sample_raw"):
                stage="sample_raw"
                raw=provider.sample_raw(step)
                if journal is not None:journal.raw(step,raw)
                stage="derive_map"
                row=provider.derive_map(raw)
                if hasattr(provider,"observe_physx"):
                    stage="physx_sample"
                    provider.observe_physx(step,row)
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
        import robot_lab.tasks  # noqa: F401  registers RobotLab-Go2-v0
        from s2_sensor_tracker_17v import SensorUpdateTracker
        if spec.num_envs!=8:
            raise ValueError("eight envs required")
        base_cfg=load_cfg_from_registry(BASE_TASK,"env_cfg_entry_point")
        base_scene_query=base_cfg.sim.enable_scene_query_support
        cfg=configure_env(base_cfg,spec,
                          diagnostic_kind="eight_case",reset_yaw_rad=0.0)
        if cfg.sim.enable_scene_query_support is not True:
            raise ValueError("scene_query_disabled_before_creation")
        self.query_cfg_pre_create=True
        cfg_blob=json.dumps(cfg.to_dict(),sort_keys=True,default=str).encode()
        self.final_cfg_sha256=hashlib.sha256(cfg_blob).hexdigest()
        self.final_cfg_json=cfg_blob.decode()
        self.initial_asset_path=str(cfg.scene.robot.spawn.asset_path)
        if on_cfg is not None:
            # 17x: declare the final cfg and asset BEFORE gym.make so a creation failure still leaves them on disk.
            on_cfg({"cfg_sha256":self.final_cfg_sha256,"cfg":self.final_cfg_json,
                    "cfg_diff_scene_query":{"parent":base_scene_query,"diagnostic":cfg.sim.enable_scene_query_support},
                    "scene_answer_sha256":answer_sha256(),"asset_path":self.initial_asset_path})
        self.env=RslRlVecEnvWrapper(gym.make(BASE_TASK,cfg=cfg))
        self.raw=self.env.unwrapped
        if self.raw.sim.cfg.enable_scene_query_support is not True:
            raise ValueError("scene_query_disabled_after_creation")
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
        self.physx=None;self.physx_error=None
        self._step=-1
        self._interventions=[]
        self.last_obs=None;self.last_dones=None;self.last_extras={}
        self.a34_probe=None

    def reset(self):
        self.env.reset()
        import torch
        pose=self.robot.data.root_pose_w.detach().clone()
        pose[1::2,3:7]=0
        pose[1::2,3]=math.cos(math.pi/4)
        pose[1::2,6]=math.sin(math.pi/4)
        self.robot.write_root_pose_to_sim(pose)
        from s2_physx_probe_live import A34LiveProbe
        self.a34_probe=A34LiveProbe(self)

    def observe_a34(self,step):
        if self.a34_probe is None:raise ProbeContractError("a34_probe_missing")
        self.a34_probe.observe(step)

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

    def observe_physx(self,step,row):
        """A3.2: fire this step's RayCaster rays through PhysX while the scene is exactly as the sensor saw it.
        Python exceptions are recorded, never raised (a native fault is not catchable here)."""
        try:
            if self.physx is None:
                from s2_mesh_probe_a2 import PhysxSampler
                self.physx=PhysxSampler(str(self.scanner.cfg.mesh_prim_paths[0]))
            self.physx.observe(step,row["ray_starts_w"],row["ray_directions_w"])
        except Exception as ex:
            self.physx_error=repr(ex)

    def sensor_frame_info(self):
        """Facts about the sensor frame that the checker's root_sensor_transform and ray checks rely on."""
        info={}
        try:
            cfg=self.scanner.cfg
            info["cfg_prim_path"]=str(cfg.prim_path)
            info["ray_alignment"]=str(getattr(cfg,"ray_alignment",None))
            info["cfg_offset_pos_ray_starts"]=[float(x) for x in cfg.offset.pos]
            info["cfg_offset_rot"]=[float(x) for x in cfg.offset.rot]
            pos,quat=self.scanner._offset
            info["view_offset_pos_envs_equal"]=bool(np.all(pos.detach().cpu().numpy()==pos[0].detach().cpu().numpy()))
            info["view_offset_quat"]=[float(x) for x in quat[0].detach().cpu().numpy()]
            info["drift_max_abs"]=float(self.scanner.drift.abs().max().item())
            info["ray_cast_drift_max_abs"]=float(self.scanner.ray_cast_drift.abs().max().item())
            info["tracked_body_names"]=[str(x) for x in getattr(self.robot,"body_names",[])][:3]
        except Exception as ex:
            info["error"]=repr(ex)
        return info

    def mount_offset(self):
        """Offset of the sensor frame from the tracked body (RayCaster._offset), None unless every env agrees and the
        rotation is identity. cfg.offset.pos (+20 m) moves the RAY STARTS, not pos_w, so it is not this value."""
        try:
            pos,quat=self.scanner._offset
            pos=pos.detach().cpu().numpy();quat=quat.detach().cpu().numpy()
            if not (np.all(pos==pos[0]) and np.all(quat==quat[0]) and np.allclose(quat[0],[1,0,0,0],atol=1e-6)):
                return None
            if float(self.scanner.drift.abs().max().item())!=0.0 or float(self.scanner.ray_cast_drift.abs().max().item())!=0.0:
                return None
            return [float(x) for x in pos[0]]
        except Exception:
            return None

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
    # A3.1 (10/15 attempt two crashed with an access violation importing tensordict AFTER Kit started).
    # Same Windows DLL preload, in the same place, as _eval/q_eval.py:24-25, scripts/rsl_rl/play.py and
    # ce12/dump_native_v2.py:32-33: load these before `isaaclab.app` boots the Kit kernel.
    import h5py  # noqa: F401
    import torch  # noqa: F401
    import tensordict  # noqa: F401
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
    phase_times={"child_start_epoch":journal.started_epoch,"asset_check_start_epoch":time.time()}
    asset_before=asset_snapshot(a.asset_path,ROBOTLAB_ASSET_CFG,CONVERTER_SOURCE)
    if asset_before["urdf"]["sha256"]!=EXPECTED_URDF_SHA256:
        raise ProvenanceHold("urdf_known_hash")
    atomic_json(root/"asset_before.json",asset_before)
    phase_times["asset_check_end_epoch"]=time.time()
    phase_times["kit_start_epoch"]=time.time()
    launcher=AppLauncher(a)
    phase_times["kit_ready_epoch"]=time.time()
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
        phase_times["environment_ready_epoch"]=time.time()
        from s2_mesh_probe_a2 import probe as mesh_probe
        atomic_json(root/"mesh_probe.json",mesh_probe(provider.scanner))
        phase_times["capture_start_epoch"]=time.time()
        arrays=capture(provider,steps=256,journal=journal)
        phase_times["capture_end_epoch"]=time.time()
        a34_record=provider.a34_probe.record
        a34_record["elapsed_s"]=time.time()-journal.started_epoch
        atomic_json(root/"physx_first16.json",a34_record)
        try:a34_verdict=provider.a34_probe.verdict()
        except ProbeContractError as ex:a34_verdict={"status":"HOLD","reason":str(ex)}
        atomic_json(root/"physx_first16_check.json",a34_verdict)
        asset_after=asset_snapshot(a.asset_path,ROBOTLAB_ASSET_CFG,CONVERTER_SOURCE)
        atomic_json(root/"asset_after.json",asset_after)
        assert_asset_unchanged(asset_before,asset_after,EXPECTED_URDF_SHA256)
        usd_root=os.environ.get("FOOTHOLD_USD_ROOT")
        if not usd_root:raise ProvenanceHold("usd_root_env_missing")
        from isaaclab.sim.utils import get_current_stage
        prim=get_current_stage().GetPrimAtPath("/World/envs/env_0/Robot")
        refs=prim.GetMetadata("references") if prim.IsValid() else None
        paths=sorted({str(ref.assetPath) for field in
            ("explicitItems","prependedItems","addedItems","appendedItems")
            for ref in (getattr(refs,field,[]) if refs is not None else []) if ref.assetPath})
        usd=usd_evidence(usd_root,a.asset_path,paths,environment_created=True)
        atomic_json(root/"usd_evidence.json",usd)
        phase_times["usd_evidence_epoch"]=time.time()
        atomic_json(root/"phase_times.json",phase_times)
        # A3.2: the boundary mask uses the checker's own float64 formula (attempt 3 had a 1-sample float32 mismatch).
        scene=scene_expectation(arrays,criteria.boundary_exclusion_m)
        edge=scene[5]
        # ASTRA 17ac: keep the mask as recorded from the rays and the differences; the recomputed mask only replaces
        # edge_excluded, it never hides the original.
        arrays["edge_excluded_recorded"]=np.asarray(arrays["edge_excluded"]).astype(bool).copy()
        differing=np.argwhere(arrays["edge_excluded_recorded"]!=edge)
        recorded_edge_mismatch=int(len(differing))
        arrays["edge_excluded"]=edge
        np.savez_compressed(root/"capture.npz",**arrays)
        # A3.2: collision / mesh probes (PhysX samples were taken inside the capture loop), errors swallowed.
        try:
            from s2_mesh_probe_a2 import observe_collision_kit
            observed=observe_collision_kit(provider.scanner,arrays,edge,scene,provider.physx)
        except BaseException as ex:
            observed={"evidence":None,"errors":["observe_collision:"+repr(ex)],"usd":None,"raw":None}
        observed.setdefault("errors",[])
        if provider.physx_error:observed["errors"].append("observe_physx:"+provider.physx_error)
        observed["sensor_frame"]=provider.sensor_frame_info()
        observed["recorded_edge_differences"]=[[int(x) for x in row] for row in differing[:20]]
        provenance=finalize_provenance(root,arrays,edge,observed,versions_snapshot(),
                                       asset_sha256_of(a.asset_path),provider.mount_offset())
        meta={"cases":list(CASES),"parent_sha256":sha256_file(a.parent),
              "code_sha256":sha256_file(__file__),"env_config_sha256":spec.sha256("eight_case"),
              "capture_sha256":sha256_file(root/"capture.npz"),
              "optimizer_steps":0,"control_steps":256,
              "recorded_edge_mismatch_before_recompute":recorded_edge_mismatch,
              "recorded_edge_differences_first20":observed["recorded_edge_differences"],
              "started_epoch":journal.started_epoch,"attempt":a.attempt,
              "device_uuid":a.gpu_uuid,"final_cfg_sha256":provider.final_cfg_sha256,
              "device_binding":device_info,
              "scene_answer_sha256":answer_sha256(),"purpose":"stage0_information_only",**provenance}
        (root/"meta.json").write_text(json.dumps(meta,sort_keys=True,indent=2),encoding="utf-8")
        result=check_path(root,criteria)
        if a34_verdict.get("status")!="INFORMATION_ONLY":
            result={**result,"verdict":"HOLD",
                    "reasons":sorted(set(result.get("reasons",[])+["a34_probe_"+a34_verdict.get("reason","unknown")]))}
        result["a34_probe_status"]=a34_verdict.get("status")
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
