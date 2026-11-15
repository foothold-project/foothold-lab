"""Bounded Kit probe that creates an EX-42 E-terrain environment and steps zeros.

Queue through gpu_jobs on cuda:1. This is an environment construction smoke
test, not a policy evaluation or a training run.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import threading
import traceback
from typing import Any


TASK_ID = "FootholdS2-Go2-S2-SB-v0"
KIT_PROBE_TIMEOUT_S = 810
PROBE_STEPS_MAX = 5
PROBE_MIX = {
    "slope_steep": 0.25,
    "slope_steep_inv": 0.25,
    "stairs_high": 0.25,
    "stairs_high_inv": 0.25,
}


def build_parser(app_launcher: Any | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--done-file", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=3)
    if app_launcher is None:
        parser.add_argument("--device", default="cuda:1")
        parser.add_argument("--headless", action="store_true", default=True)
    else:
        app_launcher.add_app_launcher_args(parser)
    return parser


def validate_probe_request(device: str, steps: int) -> int:
    if device != "cuda:1":
        raise ValueError("EX-42 environment probe is restricted to --device cuda:1")
    if type(steps) is not int or not 1 <= steps <= PROBE_STEPS_MAX:
        raise ValueError(f"--steps must be between 1 and {PROBE_STEPS_MAX}")
    return steps


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _timeout_exit(receipt: Path) -> None:
    _write_json(receipt, {
        "format": "foothold-ex42-env-probe/1",
        "state": "timeout",
        "timeout_seconds": KIT_PROBE_TIMEOUT_S,
        "kit_started": True,
        "environment_created": None,
        "training_started": False,
    })
    sys.stdout.write(f"EX42_ENV_PROBE_TIMEOUT seconds={KIT_PROBE_TIMEOUT_S}\n")
    sys.stdout.flush()
    os._exit(124)


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    validate_probe_request(args.device, args.steps)
    from isaaclab.app import AppLauncher

    app = AppLauncher(args).app
    result: dict[str, Any] = {
        "format": "foothold-ex42-env-probe/1",
        "task_id": TASK_ID,
        "device": args.device,
        "requested_zero_action_steps": args.steps,
        "probe_only_proportions": PROBE_MIX,
        "kit_started": app is not None,
        "training_started": False,
        "environment_created": False,
    }

    import gymnasium as gym
    import torch
    importlib.import_module("isaaclab_tasks")
    from isaaclab.terrains.terrain_generator_cfg import TerrainGeneratorCfg
    from isaaclab_tasks.utils import load_cfg_from_registry
    from foothold_s2.terrains.ex42 import PAPER_EXT_SPECS, paper_ext_subterrains

    importlib.import_module("foothold_s2.sb_tasks")
    spec = gym.spec(TASK_ID)
    entry = spec.kwargs.get("env_cfg_entry_point")
    if not isinstance(entry, str) or ":" not in entry:
        raise RuntimeError("registered task has no env_cfg_entry_point")
    env_cfg = load_cfg_from_registry(TASK_ID, "env_cfg_entry_point")
    env_cfg.scene.num_envs = 1
    env_cfg.sim.device = args.device
    env_cfg.scene.terrain.max_init_terrain_level = 0
    env_cfg.scene.terrain.terrain_generator = TerrainGeneratorCfg(
        size=(8.0, 8.0), border_width=1.0, num_rows=1, num_cols=4,
        horizontal_scale=0.1, vertical_scale=0.005, slope_threshold=0.75,
        use_cache=False, seed=42, curriculum=True,
        sub_terrains=paper_ext_subterrains(PROBE_MIX),
    )
    result["environment_cfg"] = {
        "entry": entry,
        "class": type(env_cfg).__name__,
        "num_envs": env_cfg.scene.num_envs,
        "terrain_generator_rows": env_cfg.scene.terrain.terrain_generator.num_rows,
        "terrain_generator_cols": env_cfg.scene.terrain.terrain_generator.num_cols,
        "terrain_kinds": sorted(spec.kind for spec in PAPER_EXT_SPECS),
        "terrain_mix_is_training_schedule": False,
    }

    env = gym.make(TASK_ID, cfg=env_cfg)
    raw = env.unwrapped
    result["environment_created"] = True
    result["environment"] = {
        "class": type(raw).__name__,
        "num_envs": int(raw.num_envs),
        "device": str(raw.device),
        "action_dim": int(raw.action_manager.total_action_dim),
    }
    reset_result = env.reset(seed=42)
    result["reset"] = {"returned_items": len(reset_result) if isinstance(reset_result, tuple) else None}

    action = torch.zeros(
        (raw.num_envs, raw.action_manager.total_action_dim),
        dtype=torch.float32,
        device=raw.device,
    )
    step_rows = []
    for index in range(args.steps):
        step_result = env.step(action)
        if not isinstance(step_result, tuple) or len(step_result) < 3:
            raise RuntimeError("environment step returned an unexpected result")
        reward = torch.as_tensor(step_result[1])
        done = torch.as_tensor(step_result[2])
        step_rows.append({
            "index": index + 1,
            "returned_items": len(step_result),
            "reward_shape": list(reward.shape),
            "reward_finite": bool(torch.isfinite(reward).all().item()),
            "done_count": int(done.bool().sum().item()),
        })
        if not step_rows[-1]["reward_finite"]:
            raise RuntimeError(f"non-finite reward during zero-action probe step {index + 1}")
    result["steps"] = step_rows
    raw_scene = getattr(raw, "scene", None)
    terrain = getattr(raw_scene, "terrain", None)
    terrain_mesh = getattr(terrain, "terrain_mesh", None)
    if terrain_mesh is not None:
        vertices = terrain_mesh.vertices
        faces = terrain_mesh.faces
        result["generated_terrain"] = {
            "vertex_count": int(len(vertices)),
            "face_count": int(len(faces)),
            "mesh_sha256": hashlib.sha256(vertices.tobytes() + faces.tobytes()).hexdigest(),
        }
    result["state"] = "passed"
    return result


def main(argv: list[str] | None = None) -> int:
    args, _unknown = build_parser().parse_known_args(argv)
    validate_probe_request(args.device, args.steps)
    watchdog = threading.Timer(KIT_PROBE_TIMEOUT_S, _timeout_exit, args=(args.receipt,))
    watchdog.daemon = True
    watchdog.start()
    try:
        from isaaclab.app import AppLauncher

        args, _unknown = build_parser(AppLauncher).parse_known_args(argv)
        result = run_probe(args)
        _write_json(args.receipt, result)
        args.done_file.parent.mkdir(parents=True, exist_ok=True)
        args.done_file.write_text("passed\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        watchdog.cancel()
        sys.stdout.flush()
        os._exit(0)
    except Exception as exc:
        result = {"format": "foothold-ex42-env-probe/1", "state": "failed",
                  "error_type": type(exc).__name__, "error": str(exc),
                  "traceback": traceback.format_exc(), "kit_started": True,
                  "environment_created": None, "training_started": False}
        _write_json(args.receipt, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        watchdog.cancel()
        sys.stdout.flush()
        os._exit(1)


if __name__ == "__main__":
    raise SystemExit(main())
