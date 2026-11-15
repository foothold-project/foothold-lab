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
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
STEP2 = HERE.parent / "s2_step2"
sys.path.insert(0, str(STEP2))
sys.path.insert(0, str(STEP2 / "base_step1"))
from s2_env_config import BASE_TASK, EnvironmentSpec, configure_env
from s2_env_adapter import expected_world_xy, yaw_from_quat_wxyz
from s2_ppo import PPOConfig, S2PPO
from s2_runner import S2Runner
from s2_policy import build_s2, load_parent_cpu, make_optimizer, sha256_file


class FakeS2Env:
    """CPU-only parent-sized fixture. The S2Runner and S2PPO paths are real."""
    def __init__(self, dims: dict, num_envs: int):
        from types import SimpleNamespace
        self.num_envs = num_envs
        self.dims = dims
        self.steps = 0
        self.episodes = torch.zeros(num_envs, dtype=torch.long)
        self.tokens = torch.zeros(num_envs, dtype=torch.long)
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

    def step(self, actions):
        self.steps += 1
        self.tokens += 1
        return self.get_observations(), torch.ones(self.num_envs), torch.zeros(self.num_envs, dtype=torch.bool), {"encounters": []}

    def state_dict(self):
        return {"steps": self.steps, "episodes": self.episodes.clone(), "tokens": self.tokens.clone()}

    def load_state_dict(self, state):
        self.steps = state["steps"]
        self.episodes = state["episodes"].clone()
        self.tokens = state["tokens"].clone()


class IsaacS2Env:
    """Thin bridge using the approved native dump's registry, wrapper and sensor calls."""
    def __init__(self, spec: EnvironmentSpec):
        import gymnasium as gym
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from isaaclab_tasks.utils import load_cfg_from_registry
        import isaaclab_tasks  # noqa: F401
        cfg = configure_env(load_cfg_from_registry(BASE_TASK, "env_cfg_entry_point"), spec,
                            diagnostic_kind=None, reset_yaw_rad=None)
        self.env = RslRlVecEnvWrapper(gym.make(BASE_TASK, cfg=cfg))
        self.raw = self.env.unwrapped
        self.raw.reset()
        self.num_envs = spec.num_envs
        self.episodes = torch.zeros(spec.num_envs, device=self.raw.device, dtype=torch.long)
        self.tokens = torch.zeros_like(self.episodes)

    def get_observations(self): return self.env.get_observations()
    def height_scanner(self): return self.raw.scene.sensors["height_scanner"]
    def base_yaw_w(self): return yaw_from_quat_wxyz(self.raw.scene["robot"].data.root_quat_w)
    def episode_ids(self): return self.episodes
    def frame_tokens(self): return self.tokens

    def step(self, actions):
        obs, rewards, dones, extras = self.env.step(actions)
        self.tokens += 1
        self.episodes += dones.reshape(-1).long()
        # The approved dumper exposes no terrain encounter event interface.
        return obs, rewards, dones, {"encounters": []}

    def state_dict(self):
        raise NotImplementedError("approved Isaac environment restore API is unverified")

    def load_state_dict(self, state):
        raise NotImplementedError("approved Isaac environment restore API is unverified")

    def close(self): self.env.close()


def parser(cpu_dry: bool):
    ap = argparse.ArgumentParser()
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
    if cpu_dry:
        ap.add_argument("--cpu_dry", action="store_true")
    else:
        from isaaclab.app import AppLauncher
        AppLauncher.add_app_launcher_args(ap)
    return ap


def validated(a):
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


def make_runner(a, spec, config, *, cpu_dry):
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
        env = IsaacS2Env(spec)
        policy = policy.to(env.raw.device)
    kw = {} if a.encoder_mode == "full_freeze" else {"encoder_freeze_updates": a.freeze_updates,
                                                     "encoder_lr_ratio": a.encoder_lr_ratio}
    optimizer, ctl = make_optimizer(policy, a.lr, encoder_mode=a.encoder_mode, **kw)
    algo = S2PPO(policy, optimizer, ctl, config)
    runner = S2Runner(env, algo, mode=a.arm, env_config_sha256=spec.sha256(),
                      geometry_tolerance_m=a.geometry_tolerance_m)
    if a.resume:
        runner.load(a.resume)
    return runner, meta


def execute(a, *, cpu_dry, clock=time.time):
    spec, config = validated(a)
    root = Path(a.out_root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    result = {"arm": a.arm, "status": "HOLD", "planned_updates": a.updates,
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
        result["parent_iter"] = meta["iter"]
        result["plan_sha256"] = runner.plan_sha256
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
                result["encounters"] = runner.encounters.report()
                result["nonfinite_count"] += sum(record.get("other_nonfinite", {}).values())
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
            result["status"] = "PASS" if cpu_dry else "HOLD"
            if not cpu_dry:
                result["stop_reason"] = "Isaac restore, encounter and device-wide VRAM unverified"
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


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cpu_dry = "--cpu_dry" in argv
    a = parser(cpu_dry).parse_args(argv)
    if not cpu_dry and not a.headless:
        raise ValueError("headless Isaac launch required")
    if cpu_dry:
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
        result = execute(a, cpu_dry=True)
    else:
        from isaaclab.app import AppLauncher
        launcher = AppLauncher(a)
        try:
            result = execute(a, cpu_dry=False)
        finally:
            launcher.app.close()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 42


if __name__ == "__main__":
    raise SystemExit(main())
