"""S2 Isaac training entry candidate and CPU dry path. No Isaac import on CPU dry.

Real environment restore, verified terrain encounters and device-wide VRAM
measurement have no approved call in the named tools. Real runs therefore hold
before claiming a restorable checkpoint or stage pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time

if "--cpu_dry" in sys.argv:
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import h5py  # noqa: F401  Windows DLL preload before isaaclab.app
import torch
import tensordict  # noqa: F401  native extension preload before isaaclab.app
import numpy as np

HERE = Path(__file__).resolve().parent
from s2_env_config_17v import BASE_TASK, EnvironmentSpec, configure_env
from s2_foot_config import add_foot_reward, validate_variant, manager_reward_receipt
from s2_task_contract import contact_termination_for
from s2_env_adapter_17v import expected_world_xy, yaw_from_quat_wxyz
from s2_ppo_17v import PPOConfig, S2PPO
from s2_runner_17v import S2Runner
from s2_packet_17v import AtomicPacket, raw_sha
from s2_sensor_tracker_17v import SensorUpdateTracker
from s2_increment_barrier import IncrementBarrier, BarrierHold
from s2_policy import build_s2, load_parent_cpu, make_optimizer, sha256_file
from s2_plumbing import (WARNING,assert_training_cfg,fixed_policy_input,
                         known_input_probe,policy_sha,roundtrip_policy,group_snapshot,group_change,
                         verify_synthetic_capture_packet,training_cfg_evidence)

def cfg_diff(before,after,prefix=""):
    if isinstance(before,dict) and isinstance(after,dict):
        return {key:value for name in sorted(set(before)|set(after))
                for key,value in cfg_diff(before.get(name),after.get(name),prefix+"/"+str(name)).items()}
    return {} if before==after else {prefix:{"before":before,"after":after}}

def runtime_imports():
    return {name:{"path":str(__file__ if name=="s2_train_entry_17v" else getattr(sys.modules.get(name),"__file__",None)),
                  "version":str(getattr(sys.modules.get(name),"__version__",None))}
            for name in ("torch","rsl_rl","isaaclab","robot_lab","gymnasium",
                         "s2_train_entry_17v","s2_plumbing","s2_env_config_17v")}

def checked_mount(scanner):
    """A3.2 RayCaster view offset, distinct from cfg.offset.pos ray start."""
    try:
        pos,quat=scanner._offset
        pos=pos.detach();quat=quat.detach()
        if pos.ndim!=2 or quat.ndim!=2 or pos.shape[1]!=3 or quat.shape!=(pos.shape[0],4):
            raise ValueError("sensor mount shape")
        if not bool(torch.isfinite(pos).all() and torch.isfinite(quat).all()):
            raise ValueError("sensor mount nonfinite")
        if not bool(torch.all(pos==pos[0])) or not bool(torch.all(quat==quat[0])):
            raise ValueError("sensor mount varies by env")
        if not bool(torch.allclose(quat[0],torch.tensor([1.,0.,0.,0.],device=quat.device,dtype=quat.dtype),atol=1e-6)):
            raise ValueError("sensor mount rotation")
        value=tuple(float(x) for x in pos[0].tolist())
        if value!=(0.,0.,0.):raise ValueError("sensor mount nonzero")
        return value
    except Exception as ex:
        raise ValueError("sensor_mount_unverified: "+str(ex)) from ex


class FakeS2Env:
    """CPU-only parent-sized fixture. The S2Runner and S2PPO paths are real."""
    def __init__(self, dims: dict, num_envs: int):
        from types import SimpleNamespace
        self.num_envs = num_envs
        self.dims = dims
        self.steps = 0
        self.episodes = torch.zeros(num_envs, dtype=torch.long)
        self.tokens = torch.zeros(num_envs, dtype=torch.long)
        self.sensor_reads=0;self.reset_sensor_reads=0;self.last_done=None
        self.cfg = SimpleNamespace(ray_alignment="yaw", offset=SimpleNamespace(pos=(0., 0., 20.)),
                                   pattern_cfg=SimpleNamespace(ordering="xy", size=(1.6, 1.0),
                                                               resolution=.1, direction=(0., 0., -1.)))

    def get_observations(self):
        n = self.num_envs
        return {"policy": torch.zeros(n, self.dims["policy"]),
                "single_obs": torch.zeros(n, self.dims["single_obs"]),
                "critic": torch.zeros(n, self.dims["critic"])}

    def height_scanner(self):
        from types import SimpleNamespace
        pos = torch.zeros(self.num_envs, 3)
        pos[:, 2] = 1.0
        xy = expected_world_xy(pos, self.base_yaw_w())
        hits = torch.cat((xy, torch.full((self.num_envs, 187, 1), .5)), dim=-1)
        return SimpleNamespace(cfg=self.cfg, data=SimpleNamespace(pos_w=pos, ray_hits_w=hits))

    def base_yaw_w(self): return torch.zeros(self.num_envs)
    def episode_ids(self): return self.episodes
    def frame_tokens(self): return self.tokens

    def capture_packet_after_sensor_update(self):
        self.sensor_reads+=1
        if self.last_done is not None:self.reset_sensor_reads+=int(self.last_done.sum())
        sensor = self.height_scanner()
        digest = raw_sha(sensor.data.pos_w, sensor.data.ray_hits_w)
        step = int(self.steps)
        receipt = {"generation": step + 1, "step": step, "raw_sha256": digest,
                   "generation_by_env":[step+1]*self.num_envs,
                   "sensor_timestamp_by_env":[float(step)]*self.num_envs,
                   "hook_source_sha256":"synthetic-cpu-fixture"}
        self._receipt = receipt
        quat = torch.zeros(self.num_envs, 4)
        quat[:, 0] = 1.0
        return AtomicPacket(self.get_observations(), sensor, sensor.data.pos_w.clone(), quat,
                            self.episodes.clone(), step, step, step + 1, digest,
                            f"fake:{step}", receipt,(0.,0.,0.))

    def read_sensor_source_receipt(self):
        return self._receipt

    def step(self, actions):
        self.steps += 1
        self.tokens += 1
        self.last_done=torch.zeros(self.num_envs,dtype=torch.bool)
        return (self.get_observations(), torch.ones(self.num_envs),
                torch.zeros(self.num_envs, dtype=torch.bool),
                {"encounters": [], "time_outs": torch.zeros(self.num_envs, dtype=torch.bool)})

    def state_dict(self):
        return {"steps": self.steps, "episodes": self.episodes.clone(), "tokens": self.tokens.clone()}

    def load_state_dict(self, state):
        self.steps = state["steps"]
        self.episodes = state["episodes"].clone()
        self.tokens = state["tokens"].clone()


class IsaacS2Env:
    """Thin bridge using the approved native dump's registry, wrapper and sensor calls."""
    def __init__(self, spec: EnvironmentSpec, *,hook_source_path,hook_source_sha256,
                 synthetic_map=False,arm=None,reward_variant="none",foot_spacing_m=None):
        import gymnasium as gym
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from isaaclab_tasks.utils import load_cfg_from_registry
        import robot_lab.tasks  # noqa: F401  registers RobotLab-Go2-v0
        from robot_lab.tasks.go2.rsl_rl_cfg import MoECTSRunnerCfg
        base=load_cfg_from_registry(BASE_TASK, "env_cfg_entry_point")
        cfg = configure_env(base, spec,
                            diagnostic_kind=None, reset_yaw_rad=None)
        add_foot_reward(cfg, variant=reward_variant, spacing_m=foot_spacing_m)
        assert_training_cfg(cfg)
        self.training_cfg_guard=training_cfg_evidence(cfg)
        for path in (("scene","robot","spawn","rigid_props"),("scene","robot","init_state"),
                     ("terminations",contact_termination_for(BASE_TASK)),("events","reset_base")):
            old,new=base,cfg
            for name in path:old=getattr(old,name);new=getattr(new,name)
            if repr(old)!=repr(new):raise ValueError("training cfg diagnostic override: "+"/".join(path))
        self.final_cfg=json.loads(json.dumps(cfg.to_dict(),sort_keys=True,default=str))
        self.parent_cfg=json.loads(json.dumps(base.to_dict(),sort_keys=True,default=str))
        self.cfg_diff=cfg_diff(self.parent_cfg,self.final_cfg)
        reward_path="/rewards/feet_center_any9_v1"
        unexpected=[key for key in self.cfg_diff if key not in ("/seed","/scene/num_envs") and
                    not key.startswith("/scene/terrain/terrain_generator/") and
                    not (reward_variant=="feet_center_any9_v1" and
                         (key==reward_path or key.startswith(reward_path+"/")))]
        if unexpected:raise ValueError("unexpected_training_cfg_diff: "+repr(unexpected[:8]))
        self.final_cfg_sha256=hashlib.sha256(json.dumps(self.final_cfg,sort_keys=True,default=str).encode()).hexdigest()
        self.env = RslRlVecEnvWrapper(gym.make(BASE_TASK, cfg=cfg),
                                       clip_actions=MoECTSRunnerCfg().clip_actions)
        self.raw = self.env.unwrapped
        self.reward_manager_receipt=manager_reward_receipt(self.raw.reward_manager,
                                                            variant=reward_variant)
        self.num_envs = spec.num_envs
        from isaaclab.sim.utils import get_current_stage
        prim=get_current_stage().GetPrimAtPath("/World/envs/env_0/Robot")
        refs=prim.GetMetadata("references") if prim.IsValid() else None
        self.usd_reference_paths=sorted({str(ref.assetPath) for field in
            ("explicitItems","prependedItems","addedItems","appendedItems")
            for ref in (getattr(refs,field,[]) if refs is not None else []) if ref.assetPath})
        if not self.usd_reference_paths:raise ValueError("robot_usd_reference_unverified")
        self.episodes = torch.zeros(spec.num_envs, device=self.raw.device, dtype=torch.long)
        self.mount_translation_b=checked_mount(self.raw.scene.sensors["height_scanner"])
        self.synthetic_map=synthetic_map
        self.synthetic_arm=arm
        self.synthetic_geometry_tolerance_m=spec.geometry_tolerance_m
        self.synthetic_capture_checks=0
        self.synthetic_capture_answer=None
        self.synthetic_generation=0
        self.sensor_reads=0;self.reset_sensor_reads=0;self.last_done=None
        self.tracker = None if synthetic_map else SensorUpdateTracker(self.raw.scene.sensors["height_scanner"],
                                           num_envs=spec.num_envs,
                                           step_getter=lambda: self.raw.common_step_counter,
                                           root_pose_getter=lambda:self.raw.scene["robot"].data.root_pose_w,
                                           expected_hook_path=hook_source_path,
                                           expected_hook_sha256=hook_source_sha256)
        self._obs = self._dict_obs(self.env.reset()[0])
        self._source_receipt = None

    @staticmethod
    def _dict_obs(obs):
        return {key: value.detach().clone() for key, value in obs.items()}

    def get_observations(self): return self._obs
    def height_scanner(self): return self.raw.scene.sensors["height_scanner"]
    def base_yaw_w(self): return yaw_from_quat_wxyz(self.raw.scene["robot"].data.root_quat_w)
    def episode_ids(self): return self.episodes

    def capture_packet_after_sensor_update(self):
        self.sensor_reads+=1
        if self.last_done is not None:self.reset_sensor_reads+=int(self.last_done.sum())
        if self.synthetic_map:
            from types import SimpleNamespace
            robot=self.raw.scene["robot"].data
            pos=robot.root_pos_w.detach().clone()
            yaw=self.base_yaw_w()
            xy=expected_world_xy(pos,yaw)
            hits=torch.cat((xy,(pos[:,2:3]-.25).unsqueeze(1).expand(-1,187,-1)),dim=-1)
            hits[:,0]=math.inf
            sensor=SimpleNamespace(cfg=self.height_scanner().cfg,
                data=SimpleNamespace(pos_w=pos,ray_hits_w=hits))
            self.synthetic_generation+=1
            step=int(self.raw.common_step_counter)
            receipt={"generation":self.synthetic_generation,"step":step,
                     "raw_sha256":raw_sha(pos,hits),
                     "generation_by_env":[self.synthetic_generation]*self.num_envs,
                     "sensor_timestamp_by_env":[float(step)]*self.num_envs,
                     "hook_source_sha256":"synthetic_known_answer_no_sensor_read"}
        else:
            sensor, receipt = self.tracker.snapshot()
        self._source_receipt = dict(receipt)
        robot = self.raw.scene["robot"].data
        packet=AtomicPacket(self._obs, sensor, robot.root_pos_w.detach().clone(),
                            robot.root_quat_w.detach().clone(), self.episodes.clone(),
                            receipt["step"], receipt["step"], receipt["generation"],
                            receipt["raw_sha256"],
                            f"{receipt['step']}:{receipt['generation']}:{receipt['raw_sha256']}",
                            receipt,self.mount_translation_b)
        if self.synthetic_map:
            self.synthetic_capture_answer=verify_synthetic_capture_packet(
                packet,arm=self.synthetic_arm,
                geometry_tolerance_m=self.synthetic_geometry_tolerance_m)
            self.synthetic_capture_checks+=1
        return packet

    def read_sensor_source_receipt(self):
        return dict(self._source_receipt) if self.synthetic_map else self.tracker.source_receipt()

    def step(self, actions):
        obs, rewards, dones, extras = self.env.step(actions)
        self._obs = self._dict_obs(obs)
        self.episodes += dones.reshape(-1).long()
        self.last_done=dones.reshape(-1).bool().clone()
        if "time_outs" not in extras:
            raise ValueError("Isaac wrapper did not expose time_outs")
        # Encounter extraction remains unverified, so a live stage cannot PASS.
        return self._obs, rewards, dones, {"encounters": [], "time_outs": extras["time_outs"]}

    def state_dict(self):
        raise NotImplementedError("approved Isaac environment restore API is unverified")

    def load_state_dict(self, state):
        raise NotImplementedError("approved Isaac environment restore API is unverified")

    def close(self):
        if self.tracker is not None:self.tracker.detach()
        self.env.close()


def parser(cpu_dry: bool):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage",choices=("smoke","short","plumbing"),required=not cpu_dry)
    ap.add_argument("--input_path",choices=("live_raycaster_unverified","synthetic_known_answer"))
    ap.add_argument("--reward_variant", choices=("none", "feet_center_any9_v1"), default="none")
    ap.add_argument("--foot_spacing_m", type=float)
    for name in ("parent", "agent_yaml", "out_root", "stop_file", "arm", "encoder_mode", "schedule"):
        ap.add_argument("--" + name, required=True)
    for name in ("seed", "num_envs", "updates", "rollout_steps", "epochs", "minibatches",
                 "checkpoint_interval", "map_init_seed"):
        ap.add_argument("--" + name, required=True, type=int)
    for name in ("gap_proportion", "stones_proportion", "step_height_m", "step_width_m",
                 "geometry_tolerance_m", "deadline_epoch", "lr", "clip_param", "gamma", "lam",
                 "value_loss_coef", "entropy_coef", "max_grad_norm", "desired_kl"):
        ap.add_argument("--" + name, required=True, type=float)
    ap.add_argument("--use_clipped_value_loss", choices=("true", "false"), required=True)
    ap.add_argument("--freeze_updates", type=int)
    ap.add_argument("--encoder_lr_ratio", type=float)
    ap.add_argument("--resume", type=Path)
    ap.add_argument("--barrier_contract", type=Path)
    ap.add_argument("--extension_disabled",action="store_true")
    if cpu_dry:
        ap.add_argument("--cpu_dry", action="store_true")
    else:
        from isaaclab.app import AppLauncher
        AppLauncher.add_app_launcher_args(ap)
        ap.add_argument("--manifest",required=True)
        ap.add_argument("--approval",required=True)
    return ap


def validated(a,*,live=False):
    validate_variant(getattr(a,"reward_variant","none"),getattr(a,"foot_spacing_m",None))
    if a.arm not in ("A", "B") or a.encoder_mode not in ("full_freeze", "schedule"):
        raise ValueError("arm A/B and explicit encoder mode required")
    if a.encoder_mode == "schedule":
        if a.freeze_updates is None or a.encoder_lr_ratio is None:
            raise ValueError("schedule requires W and r")
    elif a.freeze_updates is not None or a.encoder_lr_ratio is not None:
        raise ValueError("full_freeze forbids W and r")
    if any(type(getattr(a, key)) is not int or getattr(a, key) < 1 for key in
           ("num_envs", "updates", "rollout_steps", "epochs", "minibatches", "checkpoint_interval")):
        raise ValueError("positive plan counts required")
    if not math.isfinite(a.deadline_epoch) or not math.isfinite(a.lr) or a.lr <= 0:
        raise ValueError("finite deadline and positive LR required")
    if not Path(a.parent).is_file() or not Path(a.agent_yaml).is_file():
        raise ValueError("parent checkpoint and agent YAML required")
    if live:
        stage=getattr(a,"stage",None)
        if (a.num_envs!=1024 and not (stage=="plumbing" and 2<=a.num_envs<=1024)) or \
           a.gap_proportion!=.15 or a.stones_proportion!=.15:
            raise ValueError("approved sparse N1024 required")
        if stage=="plumbing":
            if a.updates not in (1,2) or a.checkpoint_interval!=a.updates:
                raise ValueError("plumbing 1/2 PPO iteration boundary required")
        elif a.updates not in (200,2000) or a.checkpoint_interval!=200:
            raise ValueError("approved 200/2000 boundary required")
    out = Path(a.out_root).resolve()
    forbidden = (Path("C:/isaac/ext/go2_rl_robotlab/_eval").resolve(),
                 Path("C:/isaac/ext/go2_rl_robotlab/source").resolve())
    if any(out == p or p in out.parents for p in forbidden):
        raise ValueError("output inside read-only source")
    spec = EnvironmentSpec(a.seed, a.num_envs, a.gap_proportion, a.stones_proportion,
                           a.step_height_m, a.step_width_m, a.geometry_tolerance_m)
    config = PPOConfig(a.rollout_steps, a.num_envs, a.epochs, a.minibatches, a.clip_param,
                       a.gamma, a.lam, a.value_loss_coef, a.entropy_coef, a.max_grad_norm,
                       a.desired_kl, a.schedule, a.use_clipped_value_loss == "true")
    return spec, config


def make_runner(a, spec, config, *, cpu_dry, synthetic_map=False, pre_optimizer_hook=None):
    if a.resume:
        raise ValueError("environment resume is unsupported; keep learner process alive")
    parent, meta = load_parent_cpu(a.parent, a.agent_yaml)  # CPU strict load first.
    if meta["iter"] != 20000:
        raise ValueError("expected E1 parent iteration 20000")
    torch.manual_seed(a.seed)
    np.random.seed(a.seed % (2**32))
    random.seed(a.seed)
    policy, _, _ = build_s2(a.arm, parent=parent, map_init_seed=a.map_init_seed)
    if cpu_dry:
        env = FakeS2Env(meta["dims"], a.num_envs)
    else:
        env = IsaacS2Env(spec,hook_source_path=a.sensor_hook_path,
                         hook_source_sha256=a.sensor_hook_sha256,synthetic_map=synthetic_map,
                         arm=a.arm,reward_variant=getattr(a,"reward_variant","none"),
                         foot_spacing_m=getattr(a,"foot_spacing_m",None))
        policy = policy.to(env.raw.device)
    if pre_optimizer_hook is not None:pre_optimizer_hook(env)
    kw = {} if a.encoder_mode == "full_freeze" else {"encoder_freeze_updates": a.freeze_updates,
                                                     "encoder_lr_ratio": a.encoder_lr_ratio}
    optimizer, ctl = make_optimizer(policy, a.lr, encoder_mode=a.encoder_mode, **kw)
    algo = S2PPO(policy, optimizer, ctl, config)
    runner = S2Runner(env, algo, mode=a.arm, env_config_sha256=spec.sha256(),
                      geometry_tolerance_m=a.geometry_tolerance_m)
    return runner, meta


def execute(a, *, cpu_dry, clock=time.time):
    spec, config = validated(a,live=not cpu_dry)
    root = Path(a.out_root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    result = {"arm": a.arm, "status": "HOLD", "planned_updates": a.updates,
              "reward_variant":getattr(a,"reward_variant","none"),
              "foot_spacing_m":getattr(a,"foot_spacing_m",None),
              "executed_updates": 0, "fault_counts": {}, "discarded_transitions": 0,
              "encounters": {}, "device_peak_mib": None, "device_min_free_mib": None,
              "iterations_per_hour": None, "stop_reason": None, "cpu_dry": cpu_dry,
              "optimizer_steps_actual": 0, "optimizer_steps_expected": a.updates*a.epochs*a.minibatches,
              "nonfinite_count": 0, "map_time_valid": False, "encounters_verified": False,
              "parent_sha256": sha256_file(a.parent), "env_config_sha256": spec.sha256(),
              "code_sha256": sha256_file(__file__), "traceback": False}
    started = clock()
    runner = None
    try:
        runner, meta = make_runner(a, spec, config, cpu_dry=cpu_dry)
        if not cpu_dry and meta["ckpt_sha256"]!="c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8":
            raise ValueError("E1 parent SHA changed")
        result["parent_iter"] = meta["iter"]
        result["plan_sha256"] = runner.plan_sha256
        if not cpu_dry:
            result["final_cfg_sha256"]=runner.env.final_cfg_sha256
            if hasattr(runner.env,"reward_manager_receipt"):
                result["reward_manager_terms"]=runner.env.reward_manager_receipt
            result["device_binding"]=getattr(a,"device_binding",None)
            runner.save(root/"checkpoint_000000.pt")
        with (root / "updates.jsonl").open("w", encoding="utf-8") as log:
            for _ in range(a.updates):
                if Path(a.stop_file).exists():
                    result["stop_reason"] = "STOP file"
                    break
                if clock() >= a.deadline_epoch:
                    result["stop_reason"] = "deadline"
                    break
                record = runner.update_once()
                log.write(json.dumps(record, default=str, sort_keys=True) + "\n")
                log.flush()
                result["fault_counts"] = record.get("fault_counts", {})
                result["discarded_transitions"] = runner.discarded_transitions
                result["encounters"] = runner.encounters.report() if cpu_dry else "unmeasured"
                result["nonfinite_count"] += sum(record.get("other_nonfinite", {}).values())
                if record["status"]=="updated" and not all(math.isfinite(float(record[key])) for key in
                    ("surrogate","value","entropy","kl")):
                    result["stop_reason"]="nonfinite_loss_kl_entropy"
                    break
                if record["status"] != "updated":
                    result["stop_reason"] = record.get("stop_reason") or record["status"]
                    break
                result["executed_updates"] += 1
                result["optimizer_steps_actual"] += record["optimizer_steps"]
                if result["executed_updates"] % a.checkpoint_interval == 0:
                    runner.save(root / f"checkpoint_{result['executed_updates']:06d}.pt")
        elapsed = max(clock() - started, 1e-9)
        result["iterations_per_hour"] = result["executed_updates"] * 3600 / elapsed
        if result["executed_updates"] == a.updates and not result["stop_reason"]:
            result["map_time_valid"] = bool(cpu_dry)
            result["status"] = "PASS" if cpu_dry else "RUN_COMPLETE_UNVERIFIED"
            if not cpu_dry:result["stage_gate"]="HOLD until encounter and sensor evidence review"
        else:
            result["status"] = "HOLD"
    except Exception as ex:
        result["stop_reason"] = f"{type(ex).__name__}: {ex}"
    finally:
        if runner is not None and hasattr(runner.env, "close"):
            runner.env.close()
        result["ended_epoch"] = clock()
        (root / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def execute_plumbing(a,*,input_path,manifest_sha256,cpu_dry=False,clock=time.time):
    """One or two full PPO iterations; evidence only, with no environment resume."""
    if input_path not in ("live_raycaster_unverified","synthetic_known_answer"):
        raise ValueError("input_path_required")
    if a.stage!="plumbing" or getattr(a,"resume",None) or getattr(a,"barrier_contract",None) or a.updates not in (1,2) or a.checkpoint_interval!=a.updates:
        raise ValueError("plumbing_scope_only")
    spec,config=validated(a,live=not cpu_dry)
    root=Path(a.out_root).resolve()
    if root.exists():
        if cpu_dry or {p.name for p in root.iterdir()}!={"usd"}:
            raise ValueError("plumbing_output_not_isolated")
    else:root.mkdir(parents=True,exist_ok=False)
    (root/"PLUMBING_ONLY.txt").write_text(
        WARNING+"\nmanifest_sha256="+manifest_sha256+"\n",encoding="utf-8")
    parent_before=sha256_file(a.parent)
    result={"stage":"plumbing","status":"HOLD","plumbing_only":True,
            "reward_variant":getattr(a,"reward_variant","none"),
            "foot_spacing_m":getattr(a,"foot_spacing_m",None),
            "cpu_dry":bool(cpu_dry),
            "plumbing_checks":"HOLD","stage0_passed":False,"performance_verified":False,
            "arm":a.arm,"input_path":input_path,
            "input_limitation":("success is limited to plumbing connection" if
                                input_path=="live_raycaster_unverified" else
                                "synthetic known-answer input; no terrain performance claim"),
            "manifest_sha256":manifest_sha256,"parent_sha256_before":parent_before,
            "planned_updates":a.updates,"executed_updates":0,
            "rollout_steps":a.rollout_steps,"num_envs":a.num_envs,
            "environment_steps":0,"vector_steps":0,"optimizer_steps_actual":0,
            "start_iteration":0,"completed_iteration":0,
            "gradient_norm_min":None,"gradient_norm_max":None,"nonfinite_count":0,
            "parameter_sha256_before":None,"parameter_sha256_after":None,
            "parameter_changed":False,"roundtrip":None,"records":[],"stop_reason":None,
            "encounters":"unmeasured"}
    runner=None
    try:
        if parent_before!="c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8":
            raise ValueError("parent_before_changed")
        result["function_only_probe"]=known_input_probe()
        def pre_optimizer(env):
            if cpu_dry:return
            guard={**env.training_cfg_guard,
                   "parent_cfg_diff":env.cfg_diff,
                   "allowed_cfg_diff":["/seed","/scene/num_envs","/scene/terrain/terrain_generator/*"]+
                   (["/rewards/feet_center_any9_v1/*"] if getattr(a,"reward_variant","none")!="none" else []),
                   "runtime_imports":runtime_imports(),"final_cfg_sha256":env.final_cfg_sha256,
                   "observation_shapes":{k:list(v.shape) for k,v in env.get_observations().items()},
                   "stage":"before_optimizer"}
            if any(k not in ("/seed","/scene/num_envs") and
                   not k.startswith("/scene/terrain/terrain_generator/") and
                   not (getattr(a,"reward_variant","none")!="none" and
                        (k=="/rewards/feet_center_any9_v1" or
                         k.startswith("/rewards/feet_center_any9_v1/"))) for k in env.cfg_diff):
                raise ValueError("pre_optimizer_cfg_diff")
            for name in ("robot_lab","isaaclab","s2_train_entry_17v","s2_plumbing"):
                path=guard["runtime_imports"][name]["path"]
                if not Path(path).is_file():raise ValueError("pre_optimizer_import_"+name)
            (root/"pre_optimizer_guard.json").write_text(json.dumps(guard,sort_keys=True,indent=2),encoding="utf-8")
            result["pre_optimizer_guard"]=guard
        runner,meta=make_runner(a,spec,config,cpu_dry=cpu_dry,
                                synthetic_map=input_path=="synthetic_known_answer",
                                pre_optimizer_hook=pre_optimizer)
        if meta["ckpt_sha256"]!=parent_before:raise ValueError("parent_load_changed")
        result["parent_iter"]=meta["iter"]
        observed=runner.env.get_observations()
        for key in ("policy","single_obs","critic"):
            if key not in observed or list(observed[key].shape)!=[a.num_envs,meta["dims"][key]]:
                raise ValueError("parent_observation_shape_mismatch: "+key)
        result["parent_obs_dims"]={key:meta["dims"][key] for key in ("policy","single_obs","critic")}
        result["action_dim"]=runner.algo.policy.num_actions
        if not cpu_dry:
            result["final_cfg_sha256"]=runner.env.final_cfg_sha256
            if hasattr(runner.env,"reward_manager_receipt"):
                result["reward_manager_terms"]=runner.env.reward_manager_receipt
            result["final_cfg"]=runner.env.final_cfg
            result["parent_cfg_diff"]=runner.env.cfg_diff
            result["sensor_mount_translation_b"]=runner.env.mount_translation_b
            result["usd_reference_paths"]=runner.env.usd_reference_paths
            result["runtime_imports"]=runtime_imports()
            result["device_binding"]=getattr(a,"device_binding",None)
            result["observation_contract"]={key:{"shape":list(v.shape),"dtype":str(v.dtype),
                "device":str(v.device),"nonfinite":int((~torch.isfinite(v)).sum())}
                for key,v in runner.env.get_observations().items()}
            result["input_injection"]=("IsaacS2Env.capture_packet synthetic rays after real Isaac observation; actor map injection does not read RayCaster data"
                                       if input_path=="synthetic_known_answer" else "RayCaster tracker snapshot")
            if input_path=="synthetic_known_answer":
                result["synthetic_sensor_scope"]="actor map injection does not read real sensor; critic height_scan reads height_scanner"
        else:
            result["input_injection"]="FakeS2Env CPU fixture; no Isaac observation"
        fixed_policy_input(meta["dims"],a.arm,next(runner.algo.policy.parameters()).device)
        result["parameter_sha256_before"]=policy_sha(runner.algo.policy)
        checkpoint_meta={"plumbing_only":True,"stage":"plumbing","manifest_sha256":manifest_sha256,
                         "parent_sha256":parent_before,"input_path":input_path}
        runner.save(root/"PLUMBING_ONLY_checkpoint_000000.pt",plumbing_meta=checkpoint_meta)
        previous_hash=result["parameter_sha256_before"]
        for index in range(a.updates):
            if Path(a.stop_file).exists():raise ValueError("STOP")
            if clock()>=a.deadline_epoch:raise ValueError("deadline")
            groups_before=group_snapshot(runner.algo.policy)
            record=runner.update_once()
            if record.get("status")!="updated":raise ValueError("update_held:"+str(record.get("stop_reason")))
            for field in ("loss","kl","entropy","gradient_norm_min","gradient_norm_max","base_lr"):
                if not math.isfinite(float(record[field])):raise ValueError("nonfinite_"+field)
            if record["gradient_norm_min"]<=0:raise ValueError("zero_gradient_norm")
            nans=int(record.get("nonfinite_count",0))+sum(record.get("other_nonfinite",{}).values())
            if nans!=0:raise ValueError("nonfinite_record")
            expected_frozen=(a.encoder_mode=="full_freeze" or index<a.freeze_updates)
            if record.get("frozen") is not expected_frozen:raise ValueError("encoder_freeze_schedule")
            changes=group_change(runner.algo.policy,groups_before,runner.algo.optimizer)
            if (not all(v["finite"] for v in changes.values()) or
                (expected_frozen and changes["student_encoder"]["changed_tensors"]!=0) or
                changes["actor"]["changed_tensors"]==0 or
                changes["critic"]["changed_tensors"]==0 or
                (a.arm=="B" and changes["map_projection"]["changed_tensors"]==0) or
                (a.arm=="B" and index>=1 and changes["map_encoder"]["changed_tensors"]==0)):
                raise ValueError("group_gradient_or_parameter_path")
            current_hash=policy_sha(runner.algo.policy)
            if current_hash==previous_hash:raise ValueError("weights_unchanged")
            previous_hash=current_hash
            result["records"].append({"iteration":index,"rollout_steps":a.rollout_steps,
                "loss":record["loss"],"kl":record["kl"],"entropy":record["entropy"],
                "gradient_norm_min":record["gradient_norm_min"],
                "gradient_norm_max":record["gradient_norm_max"],
                "learning_rate":record["base_lr"],"encoder_frozen":record["frozen"],
                "parameter_sha256_after":current_hash,"nonfinite_count":nans,
                "optimizer_steps":record["optimizer_steps"]})
            result["records"][-1]["group_changes"]=changes
            result["records"][-1]["preclip_group_grad_norms"]=record["preclip_group_grad_norms"]
            result["records"][-1]["tensor_contract"]=record["tensor_contract"]
            result["records"][-1]["map_input_sha256"]=record["map_input_sha256"]
            result["records"][-1]["last_packet_receipt"]=record["last_packet_receipt"]
            result["executed_updates"]+=1
            result["completed_iteration"]+=1
            result["vector_steps"]+=a.rollout_steps
            result["environment_steps"]+=a.rollout_steps*a.num_envs
            result["optimizer_steps_actual"]+=record["optimizer_steps"]
        result["parameter_sha256_after"]=previous_hash
        result["sensor_reads_total"]=runner.env.sensor_reads
        if not cpu_dry and input_path=="synthetic_known_answer":
            result["synthetic_capture_checks"]=runner.env.synthetic_capture_checks
            result["synthetic_capture_answer"]=runner.env.synthetic_capture_answer
        result["sensor_bootstrap_reads"]=1
        result["sensor_reset_env_reads"]=runner.env.reset_sensor_reads
        result["discarded_transitions"]=runner.discarded_transitions
        if result["discarded_transitions"]:raise ValueError("discarded_transitions")
        result["parameter_changed"]=previous_hash!=result["parameter_sha256_before"]
        result["gradient_norm_min"]=min(x["gradient_norm_min"] for x in result["records"])
        result["gradient_norm_max"]=max(x["gradient_norm_max"] for x in result["records"])
        final=root/f"PLUMBING_ONLY_checkpoint_{a.updates:06d}.pt"
        runner.save(final,plumbing_meta=checkpoint_meta)
        result["roundtrip"]=roundtrip_policy(runner,final,meta["dims"],a.arm)
        if not result["parameter_changed"]:raise ValueError("weights_unchanged")
        result["status"]="RUN_COMPLETE_UNVERIFIED"
        result["plumbing_checks"]="PASS"
    except Exception as ex:
        result["status"]="HOLD"
        result["stop_reason"]=f"{type(ex).__name__}: {ex}"
    finally:
        if runner is not None and hasattr(runner.env,"close"):runner.env.close()
        try:result["parent_sha256_after"]=sha256_file(a.parent)
        except Exception as ex:
            result["parent_sha256_after"]=None
            result["cleanup_errors"].append("parent_rehash:"+repr(ex))
        if result["parent_sha256_after"]!=parent_before:
            result["status"]="HOLD";result["stop_reason"]="parent_after_changed"
        result["ended_epoch"]=clock()
        (root/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True),encoding="utf-8")
    return result


def execute_barrier(a, *, cpu_dry, barrier_callback=None):
    """Short comparison and finite extensions in one runner/environment process."""
    spec, config = validated(a,live=not cpu_dry)
    contract = json.loads(a.barrier_contract.read_text(encoding="utf-8"))
    if contract["arm"] != a.arm or contract["initial_short_updates"] != a.updates:
        raise ValueError("barrier contract and entry plan mismatch")
    root = Path(a.out_root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    runner = None
    try:
        runner, meta = make_runner(a, spec, config, cpu_dry=cpu_dry)
        if not cpu_dry:runner.save(root/"checkpoint_000000.pt")
        class LearnerAdapter:
            def __init__(self, live_runner): self.live_runner=live_runner; self.records=[]
            def run_updates(self, count):
                segment=[]
                for _ in range(count):
                    if Path(a.stop_file).exists() or time.time()>=a.deadline_epoch:
                        return {"status":"HOLD","updates":len(segment),"faults":1,"discarded":0}
                    record=self.live_runner.update_once()
                    segment.append(record)
                    if (record["status"]!="updated" or
                        not all(math.isfinite(float(record[key])) for key in
                                ("surrogate","value","entropy","kl"))):
                        return {"status":"HOLD","updates":len(segment),"faults":1,
                                "discarded":self.live_runner.discarded_transitions}
                    if not cpu_dry:
                        count_now=self.live_runner.algo.ctl.next_update_index
                        if count_now==200 or count_now==2000 or (count_now>2000 and (count_now-2000)%500==0):
                            self.live_runner.save(root/f"checkpoint_{count_now:06d}.pt")
                self.records.extend(segment)
                with (root/"updates.jsonl").open("a",encoding="utf-8") as f:
                    for record in segment:f.write(json.dumps(record,sort_keys=True,default=str)+"\n")
                return {"status":"PASS","updates":count,"faults":0,
                        "discarded":self.live_runner.discarded_transitions,
                        "optimizer_steps":sum(x["optimizer_steps"] for x in segment),
                        "packet_count":count*a.rollout_steps*a.num_envs}
            def checkpoint_at(self,update):
                path=root/f"checkpoint_{update:06d}.pt"
                self.live_runner.save(path)
                return path
        adapter=LearnerAdapter(runner)
        barrier=IncrementBarrier(contract,adapter)
        receipts=[barrier.initial()]
        if barrier_callback is not None:barrier_callback(barrier,receipts[-1])
        while barrier.update<contract["max_total_updates"]:
            receipts.append(barrier.wait_grant_and_extend())
            if barrier_callback is not None:barrier_callback(barrier,receipts[-1])
        result={"status":"COMPLETE" if cpu_dry else "RUN_COMPLETE_UNVERIFIED",
                "updates_per_arm":barrier.update,"segments":len(receipts),
                "same_runner_process":True,"parent_iter":meta["iter"],
                "reason":None if cpu_dry else "stage gate awaits independent raw evidence"}
    except (BarrierHold,ValueError,RuntimeError) as ex:
        result={"status":"HOLD","reason":str(ex),"same_runner_process":runner is not None}
    finally:
        result["reward_variant"]=getattr(a,"reward_variant","none")
        result["foot_spacing_m"]=getattr(a,"foot_spacing_m",None)
        if runner is not None and not cpu_dry and hasattr(runner.env,"reward_manager_receipt"):
            result["reward_manager_terms"]=runner.env.reward_manager_receipt
        if runner is not None and hasattr(runner.env,"close"):runner.env.close()
    (root/"chain_result.json").write_text(json.dumps(result,sort_keys=True,indent=2),encoding="utf-8")
    return result


def prepare_short_root(root, *, cpu_dry):
    root=Path(root).resolve()
    if root.exists():
        if cpu_dry or {p.name for p in root.iterdir()}!={"usd"}:
            raise ValueError("short_output_not_isolated")
    else:root.mkdir(parents=True,exist_ok=False)
    return root


def execute_short_single(a, *, cpu_dry, clock=time.time, mono=time.monotonic,
                         meter_factory=None,manifest_sha256=None):
    """One sealed E1 to 2000 run, with no resume or increment path."""
    if (a.stage!="short" or a.extension_disabled is not True or
        a.updates!=2000 or a.checkpoint_interval!=200 or
        a.barrier_contract or a.resume):
        raise ValueError("short_single_2000_only")
    spec,config=validated(a,live=not cpu_dry)
    root=prepare_short_root(a.out_root,cpu_dry=cpu_dry)
    parent_before=sha256_file(a.parent)
    result={"stage":"short","extension_disabled":True,"status":"HOLD",
            "reward_variant":getattr(a,"reward_variant","none"),
            "foot_spacing_m":getattr(a,"foot_spacing_m",None),
            "cpu_dry":bool(cpu_dry),
            "manifest_sha256":manifest_sha256,
            "arm":a.arm,"planned_updates":2000,"executed_updates":0,
            "last_completed_update":0,"first_failure":None,"stop_reason":None,
            "optimizer_steps_actual":0,"optimizer_steps_expected":2000*a.epochs*a.minibatches,
            "vector_steps":0,"environment_steps":0,"discarded_transitions":0,
            "nonfinite_count":0,"encounters":"unmeasured","performance_verified":False,
            "parent_sha256_before":parent_before,"checkpoint_boundaries":list(range(0,2001,200)),
            "resource_samples":0,"min_free_vram_bytes":None,"peak_used_vram_bytes_observed":None,
            "cleanup_errors":[]}
    runner=None;meter=None
    try:
        if parent_before!="c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8":
            raise ValueError("parent_before_changed")
        runner,meta=make_runner(a,spec,config,cpu_dry=cpu_dry)
        if meta["ckpt_sha256"]!=parent_before or meta["iter"]!=20000:
            raise ValueError("parent_load_changed")
        result["parent_iter"]=meta["iter"]
        result["plan_sha256"]=runner.plan_sha256
        result["env_config_sha256"]=runner.env_config_sha256
        if not cpu_dry:
            observed=runner.env.get_observations()
            result["parent_obs_dims"]={key:meta["dims"][key] for key in ("policy","single_obs","critic")}
            for key in result["parent_obs_dims"]:
                value=observed.get(key)
                if (value is None or list(value.shape)!=[a.num_envs,meta["dims"][key]] or
                    not bool(torch.isfinite(value).all())):
                    raise ValueError("short_initial_observation_contract:"+key)
            result["initial_observation_contract"]={key:{"shape":list(observed[key].shape),
                "dtype":str(observed[key].dtype),"device":str(observed[key].device)}
                for key in result["parent_obs_dims"]}
            fixed_policy_input(meta["dims"],a.arm,next(runner.algo.policy.parameters()).device)
            result["final_cfg_sha256"]=runner.env.final_cfg_sha256
            if hasattr(runner.env,"reward_manager_receipt"):
                result["reward_manager_terms"]=runner.env.reward_manager_receipt
            result["final_cfg"]=runner.env.final_cfg
            result["usd_reference_paths"]=runner.env.usd_reference_paths
            result["sensor_mount_translation_b"]=runner.env.mount_translation_b
            result["device_binding"]=getattr(a,"device_binding",None)
            result["runtime_imports"]=runtime_imports()
            if meter_factory is None:
                from s2_stage0_resources_a2 import NvmlMeter
                meter_factory=NvmlMeter
            meter=meter_factory()
        result["parameter_sha256_before"]=policy_sha(runner.algo.policy)
        runner.save(root/"checkpoint_000000.pt")
        with (root/"updates.jsonl").open("x",encoding="utf-8") as log:
            for index in range(1,2001):
                if Path(a.stop_file).exists():raise ValueError("STOP")
                if clock()>=a.deadline_epoch:raise ValueError("deadline")
                started=mono()
                if not cpu_dry:torch.cuda.reset_peak_memory_stats()
                record=runner.update_once()
                if not cpu_dry:torch.cuda.synchronize()
                measure={"update":index,"iteration_wall_s":mono()-started,
                         "torch_cuda_max_memory_allocated_bytes":None,
                         "torch_cuda_max_memory_reserved_bytes":None,
                         "nvml_used_vram_bytes":None,"nvml_free_vram_bytes":None,
                         "min_free_vram_bytes_so_far":None}
                if not cpu_dry:
                    sample=meter.probe(0)
                    measure.update(torch_cuda_max_memory_allocated_bytes=int(torch.cuda.max_memory_allocated()),
                        torch_cuda_max_memory_reserved_bytes=int(torch.cuda.max_memory_reserved()),
                        nvml_used_vram_bytes=sample["total_vram_bytes"]-sample["free_vram_bytes"],
                        nvml_free_vram_bytes=sample["free_vram_bytes"])
                    result["resource_samples"]+=1
                    result["min_free_vram_bytes"]=(sample["free_vram_bytes"] if result["min_free_vram_bytes"] is None
                        else min(result["min_free_vram_bytes"],sample["free_vram_bytes"]))
                    result["peak_used_vram_bytes_observed"]=(measure["nvml_used_vram_bytes"]
                        if result["peak_used_vram_bytes_observed"] is None else
                        max(result["peak_used_vram_bytes_observed"],measure["nvml_used_vram_bytes"]))
                    measure["min_free_vram_bytes_so_far"]=result["min_free_vram_bytes"]
                line={**record,**measure}
                log.write(json.dumps(line,sort_keys=True,default=str)+"\n");log.flush()
                print(json.dumps(measure,sort_keys=True),flush=True)
                if record.get("status")!="updated":
                    raise ValueError("update_held:"+str(record.get("stop_reason") or record.get("status")))
                if not all(math.isfinite(float(record[k])) for k in
                           ("surrogate","value","entropy","kl","loss","gradient_norm_min",
                            "gradient_norm_max","base_lr")):
                    raise ValueError("nonfinite_loss_kl_entropy")
                if record["gradient_norm_min"]<=0 or record.get("frozen") is not True:
                    raise ValueError("short_gradient_or_freeze")
                if (record.get("s2_update_index")!=index-1 or
                    record.get("rollout_steps")!=a.rollout_steps or
                    record.get("num_envs")!=a.num_envs or
                    record.get("epochs")!=a.epochs or
                    record.get("minibatches")!=a.minibatches or
                    not record.get("map_input_sha256") or
                    not (record.get("last_packet_receipt") or {}).get("raw_sha256")):
                    raise ValueError("short_update_input_or_count")
                tensor=record.get("tensor_contract") or {}
                if not tensor or any(value.get("nonfinite")!=0 for value in tensor.values()):
                    raise ValueError("short_tensor_contract")
                nans=int(record.get("nonfinite_count",0))+sum(record.get("other_nonfinite",{}).values())
                if nans or runner.discarded_transitions:
                    raise ValueError("nonfinite_or_discarded_transitions")
                if record.get("optimizer_steps")!=a.epochs*a.minibatches:
                    raise ValueError("optimizer_step_mismatch")
                result["executed_updates"]=index;result["last_completed_update"]=index
                result["optimizer_steps_actual"]+=record["optimizer_steps"]
                result["vector_steps"]+=a.rollout_steps
                result["environment_steps"]+=a.rollout_steps*a.num_envs
                if index%200==0:runner.save(root/f"checkpoint_{index:06d}.pt")
        result["parameter_sha256_after"]=policy_sha(runner.algo.policy)
        if result["parameter_sha256_after"]==result["parameter_sha256_before"]:
            raise ValueError("weights_unchanged")
        result["roundtrip"]=roundtrip_policy(runner,root/"checkpoint_002000.pt",meta["dims"],a.arm)
        result["completed_iteration"]=2000
        result["status"]="RUN_COMPLETE_UNVERIFIED"
    except Exception as ex:
        result["first_failure"]=f"{type(ex).__name__}: {ex}"
        result["stop_reason"]=result["first_failure"]
        with (root/"updates.jsonl").open("a",encoding="utf-8") as log:
            log.write(json.dumps({"status":"HOLD","last_completed_update":result["last_completed_update"],
                                  "first_failure":result["first_failure"]},sort_keys=True)+"\n")
            log.flush()
    finally:
        if meter is not None:
            try:meter.close()
            except Exception as ex:
                result["status"]="HOLD";result["cleanup_errors"].append("meter_close:"+repr(ex))
        if runner is not None and hasattr(runner.env,"close"):
            try:runner.env.close()
            except Exception as ex:
                result["status"]="HOLD";result["cleanup_errors"].append("env_close:"+repr(ex))
        result["parent_sha256_after"]=sha256_file(a.parent)
        if result["parent_sha256_after"]!=parent_before:
            result["status"]="HOLD"
            result["cleanup_errors"].append("parent_after_changed")
        if result["status"]=="HOLD" and result["first_failure"] is None:
            result["first_failure"]=(result["cleanup_errors"][0] if result["cleanup_errors"]
                                     else "short_single_incomplete")
            result["stop_reason"]=result["first_failure"]
        result["ended_epoch"]=clock()
        (root/"result.json").write_text(json.dumps(result,sort_keys=True,indent=2),encoding="utf-8")
    return result


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cpu_dry = "--cpu_dry" in argv
    if not cpu_dry:
        # Verify the exact approved argv before importing isaaclab.app or opening Kit.
        from s2_train_contract import TrainHold,validate
        early=argparse.ArgumentParser(add_help=False)
        early.add_argument("--manifest",required=True);early.add_argument("--approval",required=True)
        e,_=early.parse_known_args(argv)
        manifest=json.loads(Path(e.manifest).read_text(encoding="utf-8"))
        approval=json.loads(Path(e.approval).read_text(encoding="utf-8"))
        if Path(e.manifest).resolve()!=Path(manifest.get("manifest_path","missing")).resolve() or \
           Path(e.approval).resolve()!=Path(manifest.get("approval_path","missing")).resolve():
            raise TrainHold("approval_file_path_differs")
        if argv!=manifest.get("entry_argv",[])[4:]:raise TrainHold("entry_argv_exact")
        validate(manifest,approval,phase="child")
    a = parser(cpu_dry).parse_args(argv)
    if cpu_dry:
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
        result=(execute_plumbing(a,input_path=a.input_path,manifest_sha256="cpu_dry_fixture",cpu_dry=True)
                if a.stage=="plumbing" else
                 execute_short_single(a,cpu_dry=True,manifest_sha256="cpu_dry_fixture") if a.extension_disabled else
                 execute_barrier(a, cpu_dry=True) if a.barrier_contract else execute(a, cpu_dry=True))
    else:
        if not a.headless or a.device!="cuda:0" or argv.count("--device")!=1:
            raise ValueError("headless cuda:0 exactly once required")
        a.sensor_hook_path=manifest["plan"]["sensor_hook_path"]
        a.sensor_hook_sha256=manifest["plan"]["sensor_hook_sha256"]
        from isaaclab.app import AppLauncher
        launcher=AppLauncher(a)
        try:
            from s2_device_binding_a2 import inspect_child_device
            binding_evidence={}
            try:
                a.device_binding=inspect_child_device(manifest["gpu_uuid"],launcher,
                                                      evidence=binding_evidence)
            finally:
                path=Path(manifest["usd_root"])/"device_binding.json"
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(json.dumps({"expected_uuid":manifest["gpu_uuid"],
                    "evidence":binding_evidence},sort_keys=True),encoding="utf-8")
            result=(execute_plumbing(a,input_path=manifest["input_path"],
                    manifest_sha256=approval["manifest_sha256"],cpu_dry=False)
                    if a.stage=="plumbing" else
                     execute_short_single(a,cpu_dry=False,manifest_sha256=approval["manifest_sha256"]) if a.extension_disabled else
                     execute_barrier(a,cpu_dry=False) if a.barrier_contract else execute(a,cpu_dry=False))
        finally:launcher.app.close()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in ("PASS", "COMPLETE", "RUN_COMPLETE_UNVERIFIED") else 42


if __name__ == "__main__":
    raise SystemExit(main())
