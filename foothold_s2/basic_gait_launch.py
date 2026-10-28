"""CPU-only launch receipt for the proposed parent/scratch basic-gait pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from foothold_s2.basic_gait_kit import KIT_CACHE_ARG, KIT_CACHE_VALUE
from foothold_s2.commands.mixed_core import basic_shares
from foothold_s2.sol23f_contract import TASKS, validate_launch


PARENT_SHA256 = "4d987818c7e25b89e77b7541feca3ddabedd444c5b20651eb29f3681da040d9d"
PARENT_ITER = 1500
ENV_COUNT = 3072
SEED = 42
PRIOR_PARENT_SMOKE = ("C:/mai/wt/foothold-lab/impl-sb/logs/rsl_rl/foothold_s2_sb/"
                      "2026-10-26_01-17-47_sb-main_resume_20261028_221302_105496")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_args(kind: str, device: str, end_by: str, share: float, parent: str | None = None,
               *, log_root: str, stage: str, ex38: bool = False) -> list[str]:
    if kind not in ("parent", "scratch"):
        raise ValueError("kind must be parent or scratch")
    if not device.startswith("cuda:") or device[5:] not in ("0", "1"):
        raise ValueError("device must be cuda:0 or cuda:1")
    basic_shares(share)
    if (kind == "parent") != bool(parent):
        raise ValueError("parent requires a checkpoint and scratch forbids it")
    if not Path(log_root).is_absolute() or stage not in ("smoke", "main"):
        raise ValueError("absolute log root and smoke|main stage required")
    if ex38 and (kind != "parent" or stage != "main" or share != 0.30):
        raise ValueError("EX-38 requires the parent main stage and basic share 0.30")
    name = ("EX-38-basic-e1rew" if ex38 else
            f"EX-36{'A' if kind == 'parent' else 'B'}-basic-share{round(share * 100):02d}")
    args = ["--headless", "--device", device, "--num_envs", str(ENV_COUNT),
            "--seed", str(SEED), "--run_name", name, "--end-by", end_by,
            "--max-wall-s", "86400", "--max_iterations", "20001" if ex38 else "3001" if parent and stage == "main" else "1501",
            "--command_mode", "basic_gait", "--basic-new-share", str(share),
            "--basic-log-root", str(Path(log_root).resolve()), "--basic-stage", stage,
            "--clock_scatter", "on", "--p_map_off", "0.1", KIT_CACHE_ARG]
    if parent:
        args += ["--resume_from", parent]
    if ex38:
        args += ["--basic-ex38", "--basic-track-ang-weight", "1.0",
                 "--basic-track-lin-weight", "2.0", "--basic-joint-acc-weight", "-1e-7",
                 "--basic-hip-pos-weight", "-0.05", "--basic-lin-vel-z-schedule"]
    if stage == "smoke":
        args += ["--smoke-updates", "2" if parent else "10"]
    return args


def receipt(kind: str, args: list[str], check_sha: bool = True) -> dict:
    pairs = {}
    i = 0
    while i < len(args):
        if args[i] in ("--headless", "--basic-ex38", "--basic-lin-vel-z-schedule"):
            pairs[args[i][2:]] = True
            i += 1
            continue
        if args[i].startswith("--kit_args="):
            if "kit_args" in pairs:
                raise ValueError("duplicate Kit arguments")
            pairs["kit_args"] = args[i].split("=", 1)[1]
            i += 1
            continue
        if not args[i].startswith("--") or i + 1 >= len(args):
            raise ValueError("malformed launch argv")
        pairs[args[i][2:]] = args[i + 1]
        i += 2
    ns = SimpleNamespace(variant="SB", task=TASKS["SB"], agent="rsl_rl_cfg_entry_point",
                         distributed=False, map_input=None, force_gt=False, resume=False,
                         max_wall_s=float(pairs["max-wall-s"]), end_by=pairs["end-by"],
                         num_envs=int(pairs["num_envs"]), seed=int(pairs["seed"]),
                         max_iterations=int(pairs["max_iterations"]), smoke_updates=int(pairs["smoke-updates"]) if "smoke-updates" in pairs else None,
                         resume_from=pairs.get("resume_from"), p_map_off=float(pairs["p_map_off"]),
                         command_mode=pairs["command_mode"], basic_new_share=float(pairs["basic-new-share"]),
                         clock_scatter=pairs["clock_scatter"], basic_log_root=pairs["basic-log-root"],
                         basic_stage=pairs["basic-stage"], basic_ex38=bool(pairs.get("basic-ex38")),
                         basic_extend_arm=None, basic_extend_parent_sha=None,
                         fast_gt_only=False, basic_feet_regulation_weight=None,
                         basic_track_ang_weight=float(pairs["basic-track-ang-weight"]) if "basic-track-ang-weight" in pairs else None,
                         basic_track_lin_weight=float(pairs["basic-track-lin-weight"]) if "basic-track-lin-weight" in pairs else None,
                         basic_joint_acc_weight=float(pairs["basic-joint-acc-weight"]) if "basic-joint-acc-weight" in pairs else None,
                         basic_hip_pos_weight=float(pairs["basic-hip-pos-weight"]) if "basic-hip-pos-weight" in pairs else None,
                         basic_lin_vel_z_schedule=bool(pairs.get("basic-lin-vel-z-schedule")))
    validate_launch(ns, verify_parent=check_sha)
    if pairs.get("kit_args") != KIT_CACHE_VALUE:
        raise ValueError("W33b basic gait Kit cache argument missing or changed")
    if (kind == "parent") != bool(ns.resume_from):
        raise ValueError("receipt kind and checkpoint disagree")
    actual = None
    if kind == "parent" and check_sha:
        actual = sha256_file(ns.resume_from)
        if actual != PARENT_SHA256:
            raise ValueError("S-B10 model_1500.pt SHA256 mismatch")
    return {
        "kind": kind, "task": TASKS["SB"], "variant": "SB", "args": pairs,
        "seed": SEED, "num_envs": ENV_COUNT, "steps_per_env": 24,
        "parent_checkpoint": str(Path(ns.resume_from).resolve()) if ns.resume_from else None,
        "parent_sha256": actual, "expected_parent_sha256": PARENT_SHA256 if kind == "parent" else None,
        "parent_completed_update": PARENT_ITER if kind == "parent" else None,
        "first_update": 1501 if kind == "parent" else 0,
        "last_update": (1502 if kind == "parent" else 9) if ns.basic_stage == "smoke" else (int(pairs["max_iterations"]) - 1),
        "additional_updates": (2 if kind == "parent" else 10) if ns.basic_stage == "smoke" else (int(pairs["max_iterations"]) - (1501 if kind == "parent" else 0)),
        "run_name": pairs["run_name"], "stage": ns.basic_stage,
        "ex38": ns.basic_ex38,
        "fast_gt_only": False, "depth_camera_enabled": True,
        "perception_training_enabled": True,
        "reward_schedule_start_iteration": 1501 if ns.basic_ex38 else 0,
        "reward_schedule_span_updates": 1500 if ns.basic_ex38 else None,
        "log_root": ns.basic_log_root, "expected_log_parent": str(Path(ns.basic_log_root) / ns.basic_stage),
        "env_seed": SEED, "command_seed": SEED, "kit_cache_argument": KIT_CACHE_ARG,
        "start_terrain_receipt": "basic_start_receipt.json in actual log_dir, written after placement and parent restore",
        "prior_parent_smoke_output": {"path": PRIOR_PARENT_SMOKE, "classification": "예행 산출, 정본 아님"} if kind == "parent" else None,
        "command_contract": "basic_gait_v1", "basic_new_share": ns.basic_new_share,
        "terrain_policy": "fixed_l02; generated 10 rows retained; active labels modulo 3; terrain_levels and command_range curriculum off",
        "difference_from_ex35": ("basic gait and L0..2 plus five E1-style reward changes; PPO and ordinary perception retained"
                                 if ns.basic_ex38 else
                                 "command distribution and fixed L0..2 active terrain; physics/reward/PPO otherwise inherited"),
        "training_approved": None if ns.basic_ex38 else False,
        "training_started": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("parent", "scratch"))
    parser.add_argument("device")
    parser.add_argument("--parent")
    parser.add_argument("--end-by", required=True)
    parser.add_argument("--share", type=float, required=True)
    parser.add_argument("--log-root", required=True)
    parser.add_argument("--stage", choices=("smoke", "main"), required=True)
    parser.add_argument("--print-args", action="store_true")
    parser.add_argument("--ex38", action="store_true")
    a = parser.parse_args(argv)
    args = build_args(a.kind, a.device, a.end_by, a.share, a.parent, log_root=a.log_root,
                      stage=a.stage, ex38=a.ex38)
    row = receipt(a.kind, args)
    out = "\n".join(args) if a.print_args else json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.buffer.write((out + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
