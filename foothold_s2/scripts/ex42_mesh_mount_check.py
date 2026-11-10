"""Short Kit check of the combined-mesh mount (evaluation / diagnosis, no training).

Part A (numpy, before Kit work): terrain_origins z versus the mesh height under each origin,
independent of warp (local trimesh ray casting).
Part B (Kit): the real task env with 64 envs on the mounted mesh, zero actions, a few resets:
  - env_origins equal terrain_origins[level, type] for every env
  - the robot root stands near its column origin (xy offset) and above the mesh (z gap)
  - the height scanner hits equal the independent mesh heights under the same xy
Every number is reported; `state` is "passed" only if all criteria below hold. Thresholds are
stated in CRITERIA and are check limits, not training parameters.

Run through the GPU queue; device is the real card (cuda:0 or cuda:1).
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import traceback
from pathlib import Path
from typing import Any

import numpy as np

TASK_ID = "FootholdS2-Go2-S2-SB-v0"
NUM_ENVS = 64
RESETS = 3
CRITERIA = {
    "origin_height_max_abs_m": 0.10,       # terrain_origins z vs mesh height under the origin
    "root_xy_offset_max_m": 1.0,           # robot root xy vs its env origin xy
    "root_above_mesh_min_m": 0.05,
    "root_above_mesh_max_m": 0.80,
    "scan_error_max_abs_m": 0.02,          # scanner hit z vs independent mesh height
    "scan_finite_fraction_min": 0.99,
}
REPO = Path(__file__).resolve().parents[2]


def part_a(data: dict[str, Any]) -> dict[str, Any]:
    from foothold_s2.terrains.ex42_mesh_mount import local_mesh_heights

    origins, families = data["origins"], data["column_family"]
    rows, cols = origins.shape[:2]
    picks = [(r, c) for c in range(cols) for r in (0, rows - 1)]
    per_family: dict[str, list[float]] = {}
    missing = 0
    for r, c in picks:
        h = local_mesh_heights(data["vertices"], data["faces"], origins[r, c, :2][None], radius=2.0)[0]
        if not np.isfinite(h):
            missing += 1
            continue
        per_family.setdefault(families[c], []).append(float(abs(h - origins[r, c, 2])))
    worst = {f: max(v) for f, v in per_family.items()}
    return {"probed": len(picks), "no_hit": missing, "max_abs_by_family_m": worst,
            "passed": missing == 0 and all(v <= CRITERIA["origin_height_max_abs_m"] for v in worst.values())}


def run(args: argparse.Namespace) -> dict[str, Any]:
    from foothold_s2.terrains.ex42_mesh_mount import (
        expected_sha_from_manifest, load_combined_mesh, local_mesh_heights, mesh_file_generator_cfg)

    npz = Path(args.mesh_dir) / "terrain_mesh.npz"
    sha = expected_sha_from_manifest(Path(args.mesh_dir) / "mesh_manifest.json")
    data = load_combined_mesh(npz, sha)
    result: dict[str, Any] = {"format": "foothold-ex42-mesh-mount-check/1", "mesh_sha256": sha,
                              "device": args.device, "criteria": CRITERIA, "training_started": False,
                              "columns": len(data["column_family"]), "state": "failed"}
    result["part_a_origin_heights"] = part_a(data)

    from isaaclab.app import AppLauncher

    AppLauncher(args)
    import gymnasium as gym
    import torch
    importlib.import_module("isaaclab_tasks")
    from isaaclab_tasks.utils import load_cfg_from_registry
    importlib.import_module("foothold_s2.sb_tasks")

    env_cfg = load_cfg_from_registry(TASK_ID, "env_cfg_entry_point")
    env_cfg.scene.num_envs = NUM_ENVS
    env_cfg.sim.device = args.device
    env_cfg.scene.terrain.terrain_generator = mesh_file_generator_cfg(npz, sha)
    env = gym.make(TASK_ID, cfg=env_cfg)
    raw = env.unwrapped
    terrain = raw.scene.terrain
    result["env"] = {"num_envs": int(raw.num_envs), "terrain_types_used": sorted(set(
        terrain.terrain_types.cpu().tolist()))[:70]}
    checks: dict[str, Any] = {}
    scanner = raw.scene.sensors["height_scanner"] if "height_scanner" in raw.scene.sensors.keys() else None
    resets = []
    action = torch.zeros((raw.num_envs, raw.action_manager.total_action_dim), device=raw.device)
    env.reset(seed=42)
    for k in range(RESETS):
        if k:
            raw.reset()
        env.step(action)
        origins_env = terrain.env_origins
        expected = terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types]
        origin_gap = float((origins_env - expected).abs().max().item())
        root = raw.scene["robot"].data.root_pos_w
        xy_off = (root[:, :2] - origins_env[:, :2]).norm(dim=1)
        heights = local_mesh_heights(data["vertices"], data["faces"],
                                     root[:, :2].detach().cpu().numpy(), radius=3.0)
        above = root[:, 2].detach().cpu().numpy() - heights
        row = {"reset": k, "env_origin_vs_terrain_origin_max_m": origin_gap,
               "root_xy_offset_max_m": float(xy_off.max().item()),
               "root_above_mesh_min_m": float(np.nanmin(above)), "root_above_mesh_max_m": float(np.nanmax(above)),
               "root_no_mesh_under": int(np.isnan(heights).sum())}
        if scanner is not None:
            scanner.update(raw.physics_dt, force_recompute=True)
            hits = scanner.data.ray_hits_w[:8].detach().cpu().numpy()          # 8 envs, all rays
            finite = np.isfinite(hits[..., 2])
            flat = hits.reshape(-1, 3)
            ref = local_mesh_heights(data["vertices"], data["faces"], flat[:, :2], radius=3.0) \
                if len(flat) <= 4000 else None
            if ref is not None:
                err = np.abs(flat[:, 2] - ref)
                row["scan"] = {"rays": int(len(flat)), "finite_fraction": float(finite.mean()),
                               "max_abs_error_m": float(np.nanmax(err)),
                               "ref_missing": int(np.isnan(ref).sum())}
        resets.append(row)
    result["resets"] = resets
    result["height_scanner"] = scanner is not None
    ok = True
    for row in resets:
        ok &= row["env_origin_vs_terrain_origin_max_m"] <= 1e-4
        ok &= row["root_xy_offset_max_m"] <= CRITERIA["root_xy_offset_max_m"]
        ok &= (CRITERIA["root_above_mesh_min_m"] <= row["root_above_mesh_min_m"]
               and row["root_above_mesh_max_m"] <= CRITERIA["root_above_mesh_max_m"])
        scan = row.get("scan")
        if scan is not None:
            ok &= scan["finite_fraction"] >= CRITERIA["scan_finite_fraction_min"]
            ok &= scan["max_abs_error_m"] <= CRITERIA["scan_error_max_abs_m"]
    checks["scanner_checked"] = scanner is not None and all("scan" in r for r in resets)
    result["checks"] = checks
    result["state"] = "passed" if (ok and result["part_a_origin_heights"]["passed"]) else "failed_criteria"
    return result


def build_parser(app_launcher: Any | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mesh-dir", type=Path, required=True,
                        help="folder with terrain_mesh.npz and mesh_manifest.json")
    parser.add_argument("--out", type=Path, required=True)
    if app_launcher is None:
        parser.add_argument("--device", default="cuda:0")
        parser.add_argument("--headless", action="store_true", default=True)
    else:
        app_launcher.add_app_launcher_args(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(REPO))
    from isaaclab.app import AppLauncher

    args, _ = build_parser(AppLauncher).parse_known_args(argv)
    code = 0
    try:
        result = run(args)
    except Exception as exc:
        result = {"format": "foothold-ex42-mesh-mount-check/1", "state": "error",
                  "error_type": type(exc).__name__, "error": str(exc),
                  "traceback": traceback.format_exc(), "training_started": False}
        code = 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: result.get(k) for k in ("state", "error_type", "error")}), flush=True)
    sys.stdout.flush()
    import os
    os._exit(code if result["state"] == "passed" else (code or 2))


if __name__ == "__main__":
    raise SystemExit(main())
