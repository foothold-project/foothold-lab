"""Basic gait output isolation and pre-learning receipt. No Isaac imports."""

from __future__ import annotations

import json
import re
from pathlib import Path


def isolated_run_dir(root: str, stage: str, name: str, stamp: str, pid: int,
                     parent_checkpoint: str | None = None) -> Path:
    base = Path(root)
    if not base.is_absolute():
        raise ValueError("basic log root must be absolute")
    if stage not in ("smoke", "main") or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise ValueError("basic stage or run name is invalid")
    base = base.resolve()
    if parent_checkpoint and base == Path(parent_checkpoint).resolve().parent.parent:
        raise ValueError("basic log root cannot be the parent checkpoint log root")
    target = base / stage / f"{name}_{stamp}_{pid}"
    if target.exists():
        raise FileExistsError(target)
    return target


def write_start_receipt(log_dir: str, *, stage: str, name: str, env_seed: int,
                        command_seed: int, terrain: dict, num_envs: int) -> dict:
    counts = terrain["new_counts"]
    if len(counts) != 3 or sum(counts) != num_envs or any(n < 0 for n in counts):
        raise ValueError("basic terrain start counts do not match env count")
    if env_seed != command_seed:
        raise ValueError("basic environment and command seeds differ")
    row = {"stage": stage, "run_name": name, "env_seed": env_seed,
           "command_seed": command_seed, "num_envs": num_envs,
           "terrain_levels_l0_l1_l2": counts,
           "terrain_labels_sha256": terrain["labels_sha256"],
           "terrain_policy": terrain["policy"],
           "measurement": "actual labels after placement and parent restore, before learning"}
    path = Path(log_dir) / "basic_start_receipt.json"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, indent=2) + "\n")
    return row
