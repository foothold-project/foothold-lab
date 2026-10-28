"""Receipt and argv for an EX-36A/B basic-gait continuation. No Kit imports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from foothold_s2 import basic_gait_launch
from foothold_s2.basic_gait_extend_parent import PARENT_UPDATE, check_parent
from foothold_s2.sol23f_contract import TASKS, validate_launch


def replace_pair(args: list[str], key: str, value: str) -> None:
    i = args.index(key)
    args[i + 1] = value


def prepare(arm: str, device: str, parent_path: str, parent_sha: str, additional_updates: int,
            end_by: str, log_root: str, stop_file: str | None = None) -> tuple[list[str], dict]:
    if arm not in PARENT_UPDATE or not 1 <= additional_updates <= 1500:
        raise ValueError("EX-36 extend arm or additional update budget invalid")
    if stop_file and (not Path(stop_file).is_absolute() or Path(stop_file).exists()):
        raise ValueError("stop file path must be absolute and not already present")
    parent = check_parent(parent_path, arm, parent_sha)
    total = parent["completed_update"] + 1 + additional_updates
    args = basic_gait_launch.build_args("parent", device, end_by, 0.30, parent_path,
                                        log_root=log_root, stage="main")
    replace_pair(args, "--max_iterations", str(total))
    replace_pair(args, "--run_name", f"EX-36{arm}-basic-extend-share30")
    args += ["--basic-extend-arm", arm, "--basic-extend-parent-sha", parent_sha]
    if stop_file:
        args += ["--stop-file", stop_file]
    contract = SimpleNamespace(
        variant="SB", task=TASKS["SB"], agent="rsl_rl_cfg_entry_point", distributed=False,
        map_input=None, force_gt=False, resume=False, max_wall_s=86400.0, end_by=end_by,
        num_envs=3072, seed=42, max_iterations=total, smoke_updates=None,
        resume_from=parent_path, p_map_off=0.1, command_mode="basic_gait", basic_new_share=0.30,
        clock_scatter="on", basic_log_root=log_root, basic_stage="main",
        basic_extend_arm=arm, basic_extend_parent_sha=parent_sha,
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
    parser.add_argument("--print-args", action="store_true")
    a = parser.parse_args(argv)
    args, receipt = prepare(a.arm, a.device, a.parent, a.parent_sha256,
                            a.additional_updates, a.end_by, a.log_root, a.stop_file)
    if a.print_args:
        print("\n".join(args))
    else:
        print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
