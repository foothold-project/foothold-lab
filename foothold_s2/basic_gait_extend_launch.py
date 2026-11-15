"""Receipt and argv for an EX-36A/B basic-gait continuation. No Kit imports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from foothold_s2 import basic_gait_launch
from foothold_s2.basic_gait_extend_parent import PARENT_UPDATE, check_parent
from foothold_s2.rewards.basic_gait_bundle import WEIGHT_NAMES, validate_settings
from foothold_s2.sol23f_contract import TASKS, validate_launch


def replace_pair(args: list[str], key: str, value: str) -> None:
    i = args.index(key)
    args[i + 1] = value


def prepare(arm: str, device: str, parent_path: str, parent_sha: str, additional_updates: int,
            end_by: str, log_root: str, stop_file: str | None = None,
            fast_gt_only: bool = False, reward_weights: dict | None = None,
            lin_vel_z_schedule: bool = False, feet_regulation_weight: float | None = None) -> tuple[list[str], dict]:
    if arm not in PARENT_UPDATE or not 1 <= additional_updates <= 1500:
        raise ValueError("EX-36 extend arm or additional update budget invalid")
    if stop_file and (not Path(stop_file).is_absolute() or Path(stop_file).exists()):
        raise ValueError("stop file path must be absolute and not already present")
    parent = check_parent(parent_path, arm, parent_sha)
    total = parent["completed_update"] + 1 + additional_updates
    args = basic_gait_launch.build_args("parent", device, end_by, 0.30, parent_path,
                                        log_root=log_root, stage="main")
    replace_pair(args, "--max_iterations", str(total))
    run_name = f"EX-36{arm}-basic-extend{'-fastgt' if fast_gt_only else ''}-share30"
    replace_pair(args, "--run_name", run_name)
    args += ["--basic-extend-arm", arm, "--basic-extend-parent-sha", parent_sha]
    if fast_gt_only:
        args += ["--fast-gt-only"]
    rewards = validate_settings(reward_weights or {name: None for name in WEIGHT_NAMES},
                                lin_vel_z_schedule, feet_regulation_weight)
    reward_flags = {"track_ang_vel": "--basic-track-ang-weight",
                    "track_lin_vel": "--basic-track-lin-weight",
                    "joint_acc": "--basic-joint-acc-weight",
                    "hip_pos_penalty": "--basic-hip-pos-weight"}
    for name, value in rewards["weights"].items():
        args += [reward_flags[name], str(value)]
    if lin_vel_z_schedule:
        args += ["--basic-lin-vel-z-schedule"]
    if stop_file:
        args += ["--stop-file", stop_file]
    contract = SimpleNamespace(
        variant="SB", task=TASKS["SB"], agent="rsl_rl_cfg_entry_point", distributed=False,
        map_input=None, force_gt=False, resume=False, max_wall_s=86400.0, end_by=end_by,
        num_envs=3072, seed=42, max_iterations=total, smoke_updates=None,
        resume_from=parent_path, p_map_off=0.1, command_mode="basic_gait", basic_new_share=0.30,
        clock_scatter="on", basic_log_root=log_root, basic_stage="main",
        basic_extend_arm=arm, basic_extend_parent_sha=parent_sha,
        fast_gt_only=fast_gt_only,
        basic_feet_regulation_weight=feet_regulation_weight,
        basic_track_ang_weight=rewards["weights"].get("track_ang_vel"),
        basic_track_lin_weight=rewards["weights"].get("track_lin_vel"),
        basic_joint_acc_weight=rewards["weights"].get("joint_acc"),
        basic_hip_pos_weight=rewards["weights"].get("hip_pos_penalty"),
        basic_lin_vel_z_schedule=lin_vel_z_schedule,
    )
    deadline = validate_launch(contract)
    receipt = {"kind": "EX36_basic_gait_extend", "arm": arm, "parent": parent,
               "additional_updates": additional_updates, "first_update": parent["completed_update"] + 1,
               "last_update": total - 1, "max_iterations": total, "envs": 3072,
               "steps_per_env": 24, "seed": 42, "command_seed": 42,
               "map_input": "reconstruction", "force_gt": True, "p_map_off": 0.1,
               "basic_new_share": 0.30, "clock_scatter": "on", "terrain_policy": "fixed_l02",
               "new_segment_root": str(Path(log_root).resolve() / "main"),
               "end_by": end_by, "deadline_epoch": deadline,
               "kit_cache_argument": basic_gait_launch.KIT_CACHE_ARG,
               "physical_resume_identical": False, "training_started": False,
               "fast_gt_only": fast_gt_only,
               "depth_camera_enabled": not fast_gt_only,
               "perception_training_enabled": not fast_gt_only,
               "perception_network_shape_changed": False,
               "training_trace_enabled": not fast_gt_only,
               "map_stats_enabled": not fast_gt_only,
               "reward_bundle": rewards,
               "argv": args}
    return args, receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("A", "B"), required=True)
    parser.add_argument("--device", choices=("cuda:0", "cuda:1"), required=True)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--parent-sha256", required=True)
    parser.add_argument("--additional-updates", type=int, required=True)
    parser.add_argument("--end-by", required=True)
    parser.add_argument("--log-root", required=True)
    parser.add_argument("--stop-file")
    parser.add_argument("--fast-gt-only", action="store_true")
    parser.add_argument("--basic-feet-regulation-weight", type=float)
    parser.add_argument("--basic-track-ang-weight", type=float)
    parser.add_argument("--basic-track-lin-weight", type=float)
    parser.add_argument("--basic-joint-acc-weight", type=float)
    parser.add_argument("--basic-hip-pos-weight", type=float)
    parser.add_argument("--basic-lin-vel-z-schedule", action="store_true")
    parser.add_argument("--print-args", action="store_true")
    a = parser.parse_args(argv)
    args, receipt = prepare(a.arm, a.device, a.parent, a.parent_sha256,
                            a.additional_updates, a.end_by, a.log_root, a.stop_file, a.fast_gt_only,
                            {"track_ang_vel": a.basic_track_ang_weight,
                             "track_lin_vel": a.basic_track_lin_weight,
                             "joint_acc": a.basic_joint_acc_weight,
                             "hip_pos_penalty": a.basic_hip_pos_weight},
                            a.basic_lin_vel_z_schedule, a.basic_feet_regulation_weight)
    if a.print_args:
        print("\n".join(args))
    else:
        print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
