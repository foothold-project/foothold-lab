"""CPU-only EX-38 continuation receipt and pinned launch arguments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from foothold_s2.basic_gait_launch import build_args, sha256_file
from foothold_s2.rewards.basic_gait_bundle import E1_CANDIDATE
from foothold_s2.sol23f_contract import resume_parent


ORIGIN = 1501
LAST = 3001


def check_parent(path: str, expected_sha256: str) -> dict:
    checkpoint = Path(path).resolve(strict=True)
    if len(expected_sha256) != 64 or checkpoint.name == "latest.pt" or not checkpoint.name.startswith("model_"):
        raise ValueError("completed model_N.pt and full SHA256 required")
    actual = sha256_file(str(checkpoint))
    if actual != expected_sha256:
        raise ValueError("EX-38 continuation checkpoint SHA256 mismatch")
    parent = resume_parent(str(checkpoint), "SB")
    iteration = parent["completed_update"]
    if checkpoint.name != f"model_{iteration}.pt" or not ORIGIN <= iteration < LAST:
        raise ValueError("EX-38 continuation iteration or model_N name mismatch")
    directory = checkpoint.parent
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    status = json.loads((directory / "train_start_status.json").read_text(encoding="utf-8"))
    modes = manifest.get("modes") or {}
    run = manifest.get("run") or {}
    command = modes.get("command_settings") or {}
    reward = modes.get("basic_reward_bundle") or {}
    if (run.get("name") != "EX-38-basic-e1rew" or modes.get("basic_ex38") is not True
            or modes.get("basic_reward_schedule_start_iteration") != ORIGIN
            or reward.get("lin_vel_z_schedule") is not True
            or reward.get("weights") != E1_CANDIDATE
            or command.get("command_mode") != "basic_gait"
            or command.get("basic_new_share") != 0.30 or command.get("clock_scatter") is not True
            or modes.get("seed") != 42 or modes.get("p_map_off") != 0.1
            or modes.get("basic_terrain_cfg_difference") is None
            or modes.get("depth_camera_enabled") is not True
            or modes.get("perception_training_enabled") is not True
            or modes.get("fast_gt_only") is not False):
        raise ValueError("EX-38 parent manifest settings differ")
    if ((manifest.get("checkpoints") or {}).get(checkpoint.name) != actual
            or status.get("state") not in ("stopped_saved", "done")
            or status.get("iter") != iteration
            or Path(status.get("checkpoint", "")).resolve() != checkpoint
            or status.get("sha256") != actual):
        raise ValueError("EX-38 checkpoint lacks a matching completed receipt")
    return {**parent, "source_run": str(directory), "source_status": status["state"],
            "reward_schedule_start_iteration": ORIGIN, "physical_resume_identical": False}


def prepare(device: str, parent_path: str, parent_sha256: str, end_by: str,
            log_root: str) -> tuple[list[str], dict]:
    parent = check_parent(parent_path, parent_sha256)
    args = build_args("parent", device, end_by, 0.30, parent_path,
                      log_root=log_root, stage="main", ex38=True)
    i = args.index("--max_iterations")
    args[i + 1] = str(LAST + 1)
    args += ["--basic-ex38-continue-parent-sha", parent_sha256]
    return args, {"run_name": "EX-38-basic-e1rew", "parent": parent,
                  "first_update": parent["completed_update"] + 1, "last_update": LAST,
                  "max_iterations": LAST + 1, "reward_schedule_start_iteration": ORIGIN,
                  "reward_schedule_at_first_update": max(-2.0, min(0.0,
                      -2.0 + 2.0 * (parent["completed_update"] + 1 - ORIGIN) / 1500)),
                  "env_seed": 42, "command_seed": 42, "terrain": "fixed L0..2",
                  "physical_resume_identical": False, "argv": args, "training_started": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cuda:0", "cuda:1"), required=True)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--parent-sha256", required=True)
    parser.add_argument("--end-by", required=True)
    parser.add_argument("--log-root", required=True)
    parser.add_argument("--print-args", action="store_true")
    a = parser.parse_args(argv)
    args, row = prepare(a.device, a.parent, a.parent_sha256, a.end_by, a.log_root)
    print("\n".join(args) if a.print_args else json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
