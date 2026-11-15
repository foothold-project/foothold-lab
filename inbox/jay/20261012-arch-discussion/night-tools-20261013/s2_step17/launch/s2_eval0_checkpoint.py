"""Create fresh, CPU-only S2 update-0 checkpoints for one evaluation attempt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys

from s2_launch_common import BUNDLE, sha, write_json, LaunchHold


def fresh_checkpoint_target(path):
    if Path(path).exists():
        raise LaunchHold("checkpoint_reuse_forbidden")


def check_eval_seeds(eval_seeds, learning):
    if len(eval_seeds) != 4 or len(set(eval_seeds)) != 4 or set(eval_seeds) & set(learning):
        raise LaunchHold("evaluation_learning_seed_overlap")


def _plan_request(mode):
    req = json.loads((BUNDLE / f"request_short_{mode}.json").read_text(encoding="utf-8"))
    plan = req["plan"]
    if (plan["arm"] != mode or plan["encoder_mode"] != "full_freeze" or
        plan["parent_sha256"] != "c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8"):
        raise LaunchHold("frozen_training_plan_identity")
    return plan


def learning_seeds():
    seeds = {11, 7, 42, 1043}
    def visit(value, key=""):
        if isinstance(value, dict):
            for k, v in value.items():
                visit(v, k)
        elif isinstance(value, list):
            for v in value:
                visit(v, key)
        elif "seed" in key.lower() and type(value) is int:
            seeds.add(value)
    visit(json.loads((BUNDLE / "request_short_B.json").read_text(encoding="utf-8")))
    return sorted(seeds)


def create_pair(run):
    if str(BUNDLE) not in sys.path:
        sys.path.insert(0, str(BUNDLE))
    import torch
    from s2_policy import load_parent_cpu, build_s2, make_optimizer
    from s2_ppo_17v import PPOConfig
    from s2_env_config_17v import EnvironmentSpec
    from s2_runner_17v import S2Runner, _hash_plan
    from s2_eval_cpu import strict_load, compare_training_forward
    from s2_eval_driver import PARENT_E1_SHA256, AGENT_YAML_SHA256

    specs = {mode: _plan_request(mode) for mode in ("A", "B")}
    if any(specs["A"][k] != specs["B"][k] for k in
           ("parent", "agent_yaml", "map_init_seed", "num_envs", "gap_proportion",
            "stones_proportion", "step_height_m", "step_width_m", "geometry_tolerance_m")):
        raise LaunchHold("arm_plan_asymmetry")
    parent_path = Path(specs["A"]["parent"])
    yaml_path = Path(specs["A"]["agent_yaml"])
    if sha(parent_path) != PARENT_E1_SHA256 or sha(yaml_path) != AGENT_YAML_SHA256:
        raise LaunchHold("parent_or_agent_yaml_sha256")
    parent, meta = load_parent_cpu(str(parent_path), str(yaml_path))
    if meta["iter"] != 20000:
        raise LaunchHold("parent_iteration")
    arms = {}
    receipts = {}
    for mode, p in specs.items():
        path = run / "in" / f"checkpoint_{mode}_update000000.pt"
        fresh_checkpoint_target(path)
        torch.manual_seed(p["seed"])
        policy, _, _ = build_s2(mode, parent=parent, map_init_seed=p["map_init_seed"])
        optimizer, ctl = make_optimizer(policy, p["lr"], encoder_mode="full_freeze",
                                        betas=meta["betas"], weight_decay=meta["weight_decay"])
        config = PPOConfig(p["rollout_steps"], p["num_envs"], p["epochs"], p["minibatches"],
                           p["clip_param"], p["gamma"], p["lam"], p["value_loss_coef"],
                           p["entropy_coef"], p["max_grad_norm"], p["desired_kl"],
                           p["schedule"], p["use_clipped_value_loss"] == "true")
        plan = {"mode": mode, "ppo": config.as_dict(), "encoder_mode": ctl.encoder_mode,
                "freeze_updates": ctl.freeze_updates, "encoder_lr_ratio": ctl.encoder_lr_ratio,
                "geometry_tolerance_m": p["geometry_tolerance_m"]}
        env = EnvironmentSpec(p["seed"], p["num_envs"], p["gap_proportion"],
                              p["stones_proportion"], p["step_height_m"],
                              p["step_width_m"], p["geometry_tolerance_m"])
        runner = S2Runner.__new__(S2Runner)
        runner.mode, runner.plan, runner.plan_sha256 = mode, plan, _hash_plan(plan)
        runner.env_config_sha256 = env.sha256()
        runner.discarded_transitions = 0
        runner.encounters = SimpleNamespace(states={})
        runner.algo = SimpleNamespace(policy=policy, optimizer=optimizer, ctl=ctl)
        runner.save(path, plumbing_meta={"plumbing_only": True, "stage": "eval_update_0",
                         "manifest_sha256": sha(BUNDLE / f"request_short_{mode}.json"),
                         "parent_sha256": PARENT_E1_SHA256})
        loaded, info = strict_load(path, expected_sha256=sha(path), parent=parent, mode=mode,
                expected_env_config_sha256=runner.env_config_sha256,
                map_init_seed=p["map_init_seed"], expected_update=0,
                expected_plan_sha256=runner.plan_sha256,
                expected_encoder_mode="full_freeze", expected_parent_sha256=PARENT_E1_SHA256)
        forward = compare_training_forward(policy, loaded, meta["dims"], mode)
        if (info["completed_updates"] != 0 or info["next_update_index"] != 0 or
            info["optimizer_slot_count"] != 0 or ctl.steps_total != 0):
            raise LaunchHold("update_zero_control_or_optimizer")
        arms[mode] = {"checkpoint": str(path), "checkpoint_sha256": sha(path),
                      "env_config_sha256": runner.env_config_sha256,
                      "map_init_seed": p["map_init_seed"],
                      "plan_sha256": runner.plan_sha256, "encoder_mode": "full_freeze",
                      "parent_sha256": PARENT_E1_SHA256}
        receipts[mode] = {"checkpoint_sha256": sha(path), "control": info,
                          "fixed_forward": forward, "training_plan_sha256": sha(BUNDLE / f"request_short_{mode}.json")}
    if arms["A"]["env_config_sha256"] != arms["B"]["env_config_sha256"]:
        raise LaunchHold("arm_environment_sha_diff")
    write_json(run / "in" / "checkpoint_receipt.json", receipts)
    return {"arms": arms,
            "parent": {"path": str(parent_path), "sha256": PARENT_E1_SHA256},
            "agent_yaml": {"path": str(yaml_path), "sha256": AGENT_YAML_SHA256}}
