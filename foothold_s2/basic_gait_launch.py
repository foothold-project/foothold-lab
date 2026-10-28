"""CPU-only launch receipt for the proposed parent/scratch basic-gait pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from foothold_s2.commands.mixed_core import basic_shares
from foothold_s2.sol23f_contract import TASKS, validate_launch


PARENT_SHA256 = "4d987818c7e25b89e77b7541feca3ddabedd444c5b20651eb29f3681da040d9d"
PARENT_ITER = 1500
ENV_COUNT = 3072
SEED = 42


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_args(kind: str, device: str, end_by: str, share: float, parent: str | None = None) -> list[str]:
    if kind not in ("parent", "scratch"):
        raise ValueError("kind must be parent or scratch")
    if not device.startswith("cuda:") or device[5:] not in ("0", "1"):
        raise ValueError("device must be cuda:0 or cuda:1")
    basic_shares(share)
    if (kind == "parent") != bool(parent):
        raise ValueError("parent requires a checkpoint and scratch forbids it")
    name = f"basic-gait-{kind}-share{round(share * 100):02d}"
    args = ["--headless", "--device", device, "--num_envs", str(ENV_COUNT),
            "--seed", str(SEED), "--run_name", name, "--end-by", end_by,
            "--max-wall-s", "86400", "--max_iterations", "3001" if parent else "1501",
            "--command_mode", "basic_gait", "--basic-new-share", str(share),
            "--clock_scatter", "on", "--p_map_off", "0.1"]
    if parent:
        args += ["--resume_from", parent]
    return args


def receipt(kind: str, args: list[str], check_sha: bool = True) -> dict:
    pairs = {}
    i = 0
    while i < len(args):
        if args[i] == "--headless":
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
                         max_iterations=int(pairs["max_iterations"]), smoke_updates=None,
                         resume_from=pairs.get("resume_from"), p_map_off=float(pairs["p_map_off"]),
                         command_mode=pairs["command_mode"], basic_new_share=float(pairs["basic-new-share"]),
                         clock_scatter=pairs["clock_scatter"])
    validate_launch(ns, verify_parent=check_sha)
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
        "last_update": 3000 if kind == "parent" else 1500,
        "additional_updates": 1500 if kind == "parent" else 1501,
        "command_contract": "basic_gait_v1", "basic_new_share": ns.basic_new_share,
        "terrain_policy": "fixed_l02; generated 10 rows retained; active labels modulo 3; terrain_levels and command_range curriculum off",
        "difference_from_ex35": "command distribution and fixed L0..2 active terrain; physics/reward/PPO otherwise inherited",
        "training_approved": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("parent", "scratch"))
    parser.add_argument("device")
    parser.add_argument("--parent")
    parser.add_argument("--end-by", required=True)
    parser.add_argument("--share", type=float, required=True)
    parser.add_argument("--print-args", action="store_true")
    a = parser.parse_args(argv)
    args = build_args(a.kind, a.device, a.end_by, a.share, a.parent)
    row = receipt(a.kind, args)
    out = "\n".join(args) if a.print_args else json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.buffer.write((out + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
