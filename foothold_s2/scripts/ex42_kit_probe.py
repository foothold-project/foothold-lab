"""Queued EX-42 Kit-only probe for task import and family-E mesh generation.

This is a bounded probe: it does not construct a vector environment, train, or
evaluate a policy. Use the GPU dispatch queue; do not launch this directly.
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


def build_parser(app_launcher: Any | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--done-file", type=Path, required=True)
    if app_launcher is None:
        parser.add_argument("--device", default="cuda:1")
        parser.add_argument("--headless", action="store_true", default=True)
    else:
        app_launcher.add_app_launcher_args(parser)
    return parser


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _timeout_exit(receipt: Path) -> None:
    _write_json(receipt, {
        "format": "foothold-ex42-kit-probe/1",
        "state": "timeout",
        "timeout_seconds": KIT_PROBE_TIMEOUT_S,
        "kit_started": True,
        "training_started": False,
    })
    sys.stdout.write(f"EX42_KIT_PROBE_TIMEOUT seconds={KIT_PROBE_TIMEOUT_S}\n")
    sys.stdout.flush()
    os._exit(124)


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    if args.device != "cuda:1":
        raise ValueError("EX-42 queued Kit probe is restricted to --device cuda:1")
    from isaaclab.app import AppLauncher

    app = AppLauncher(args).app
    result: dict[str, Any] = {
        "format": "foothold-ex42-kit-probe/1",
        "task_id": TASK_ID,
        "device": args.device,
        "kit_started": True,
        "training_started": False,
        "environment_created": False,
    }
    result["kit_started"] = app is not None
    import gymnasium as gym
    importlib.import_module("isaaclab_tasks")
    from isaaclab_tasks.utils import load_cfg_from_registry
    importlib.import_module("foothold_s2.sb_tasks")

    spec = gym.spec(TASK_ID)
    entry = spec.kwargs.get("env_cfg_entry_point")
    if not isinstance(entry, str) or ":" not in entry:
        raise RuntimeError("registered task has no env_cfg_entry_point")
    env_cfg = load_cfg_from_registry(TASK_ID, "env_cfg_entry_point")
    result["environment_import"] = {
        "entry": entry,
        "class": type(env_cfg).__name__,
        "instantiated": True,
        "environment_created": False,
    }

    from isaaclab.terrains import TerrainGenerator
    from isaaclab.terrains.terrain_generator_cfg import TerrainGeneratorCfg
    from foothold_s2.terrains.ex42 import paper_ext_subterrains

    # Probe-only equal proportions select all four mesh routines; this is
    # not the training exposure schedule and is never written to the plan.
    probe_mix = {name: 0.25 for name in (
        "slope_steep", "slope_steep_inv", "stairs_high", "stairs_high_inv")}
    cfg = TerrainGeneratorCfg(
        size=(8.0, 8.0), border_width=1.0, num_rows=1, num_cols=4,
        horizontal_scale=0.1, vertical_scale=0.005, slope_threshold=0.75,
        use_cache=False, seed=42, curriculum=True,
        sub_terrains=paper_ext_subterrains(probe_mix),
    )
    generator = TerrainGenerator(cfg)
    mesh = generator.terrain_mesh
    vertices = mesh.vertices
    faces = mesh.faces
    result["family_e_generation"] = {
        "kinds": sorted(cfg.sub_terrains),
        "probe_only_proportions": probe_mix,
        "tile_count": 4,
        "vertex_count": int(len(vertices)),
        "face_count": int(len(faces)),
        "bounds_m": [[float(v) for v in row] for row in mesh.bounds.tolist()],
        "mesh_sha256": hashlib.sha256(vertices.tobytes() + faces.tobytes()).hexdigest(),
        "training_schedule_used": False,
    }
    result["state"] = "passed"
    return result


def main(argv: list[str] | None = None) -> int:
    args, _unknown = build_parser().parse_known_args(argv)
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
        result = {"format": "foothold-ex42-kit-probe/1", "state": "failed",
                  "error_type": type(exc).__name__, "error": str(exc),
                  "traceback": traceback.format_exc(), "kit_started": True,
                  "training_started": False}
        _write_json(args.receipt, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        watchdog.cancel()
        sys.stdout.flush()
        os._exit(1)


if __name__ == "__main__":
    raise SystemExit(main())
