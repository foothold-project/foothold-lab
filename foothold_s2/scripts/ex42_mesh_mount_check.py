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
    "root_above_support_min_m": 0.05,      # root over the mesh under the FEET (what it stands on)
    "root_above_support_max_m": 0.80,
    "foot_clearance_max_m": 0.30,          # no foot hovers over the mesh under it (spawn is not airborne)
    "foot_clearance_min_m": -0.10,         # no foot sunk into the mesh (all four feet ON the support)
    "zero_range_xy_offset_max_m": 0.15,    # kinds with a declared 0 start range stand on their origin
    "scan_error_max_abs_m": 0.02,          # scanner hit z vs independent mesh height
    "scan_finite_fraction_min": 0.99,
}
REPO = Path(__file__).resolve().parents[2]


def column_kind(column: int, column_family: list[str]) -> str:
    """Kind name of a mesh column where the code knows it (A: columns.FULL order); else the family."""
    from foothold_s2.terrains import columns

    if column_family[column] == "A":
        return columns.column_types(columns.FULL, columns.FULL_COLS)[column]
    return f"{column_family[column]}[{column - column_family.index(column_family[column])}]"


def part_a(data: dict[str, Any]) -> dict[str, Any]:
    from foothold_s2.terrains.ex42_mesh_mount import MeshHeights

    heights = MeshHeights(data["vertices"], data["faces"])

    origins, families = data["origins"], data["column_family"]
    rows, cols = origins.shape[:2]
    picks = [(r, c) for c in range(cols) for r in (0, rows - 1)]
    per_family: dict[str, list[float]] = {}
    missing = 0
    for r, c in picks:
        h = heights.at(origins[r, c, :2][None], radius=2.0)[0]
        if not np.isfinite(h):
            missing += 1
            continue
        per_family.setdefault(families[c], []).append(float(abs(h - origins[r, c, 2])))
    worst = {f: max(v) for f, v in per_family.items()}
    return {"probed": len(picks), "no_hit": missing, "max_abs_by_family_m": worst,
            "passed": missing == 0 and all(v <= CRITERIA["origin_height_max_abs_m"] for v in worst.values())}


def _worst(idx_order, k, types, levels, data, root_np, root_h, support, above_support, foot_clear):
    """Top-k envs by a score, each with its column / family / kind / level and the heights behind it."""
    out = []
    for e in idx_order[:k]:
        c = int(types[e])
        out.append({"env": int(e), "column": c, "family": data["column_family"][c],
                    "kind": column_kind(c, data["column_family"]), "level": int(levels[e]),
                    "root_z": float(root_np[e, 2]), "mesh_under_root": float(root_h[e]),
                    "support_under_feet": float(support[e]), "root_above_support": float(above_support[e]),
                    "foot_clearance": [float(x) for x in foot_clear[e]]})
    return out


def _per_column_pass(env, raw, terrain, mesh_heights, foot_ids, action, data, table, np, torch):
    """Put envs on EVERY mesh column at levels 0/3/6/9 (in batches of num_envs), reset, step, and check
    that all four feet stand on the mesh and the root is a plausible height above it. A column with a
    declared zero xy range must also start on its origin. Reports per family/kind and every failure."""
    fam = list(data["column_family"])
    rows_n = data["origins"].shape[0]
    levels_pick = sorted({min(l, rows_n - 1) for l in (0, 3, 6, 9)})
    pairs = [(lvl, c) for c in range(len(fam)) for lvl in levels_pick]
    dev = terrain.terrain_types.device
    out: list[dict[str, Any]] = []
    kept = True
    for start in range(0, len(pairs), raw.num_envs):
        chunk = pairs[start:start + raw.num_envs]
        n = len(chunk)
        lv = torch.tensor([p[0] for p in chunk], device=dev)
        ty = torch.tensor([p[1] for p in chunk], device=dev)
        terrain.terrain_levels[:n] = lv
        terrain.terrain_types[:n] = ty
        terrain.env_origins[:n] = terrain.terrain_origins[lv, ty]
        raw.reset()
        env.step(action)
        kept &= bool((terrain.terrain_types[:n] == ty).all() and (terrain.terrain_levels[:n] == lv).all())
        root = raw.scene["robot"].data.root_pos_w[:n].detach().cpu().numpy()
        feet = raw.scene["robot"].data.body_pos_w[:n][:, foot_ids].detach().cpu().numpy()
        origins_np = terrain.env_origins[:n].detach().cpu().numpy()
        for e, (lvl, c) in enumerate(chunk):
            pts = np.vstack([root[e:e + 1, :2], feet[e, :, :2]])
            hs = mesh_heights.at(pts, radius=1.0)
            fh = hs[1:]
            support = float(np.nanmean(fh))
            clear = feet[e, :, 2] - fh
            xy = float(np.linalg.norm(root[e, :2] - origins_np[e, :2]))
            zero = table[c]["from_declaration"] and all(
                table[c]["ranges"].get(a, (0, 0)) == (0.0, 0.0) for a in ("x", "y"))
            above = float(root[e, 2] - support)
            reasons = []
            if not np.isfinite(clear).all():
                reasons.append("no_mesh_under_a_foot")
            else:
                if clear.max() > CRITERIA["foot_clearance_max_m"]:
                    reasons.append("foot_hovers")
                if clear.min() < CRITERIA["foot_clearance_min_m"]:
                    reasons.append("foot_sunk")
            if not CRITERIA["root_above_support_min_m"] <= above <= CRITERIA["root_above_support_max_m"]:
                reasons.append("root_height_off_support")
            if zero and xy > CRITERIA["zero_range_xy_offset_max_m"]:
                reasons.append("zero_range_start_off_origin")
            out.append({"column": c, "family": fam[c], "kind": column_kind(c, fam), "level": lvl,
                        "zero_xy_range": bool(zero), "root_xy_offset_m": xy, "root_z": float(root[e, 2]),
                        "support_under_feet": support, "root_above_support": above,
                        "foot_clearance": [float(x) for x in clear],
                        "foot_clearance_max": float(np.nanmax(clear)) if np.isfinite(clear).any() else None,
                        "reasons": reasons, "passed": not reasons})
    by_family: dict[str, dict[str, Any]] = {}
    for item in out:
        slot = by_family.setdefault(item["family"], {"checked": 0, "failed": 0, "failed_kinds": set()})
        slot["checked"] += 1
        if not item["passed"]:
            slot["failed"] += 1
            slot["failed_kinds"].add(item["kind"])
    for slot in by_family.values():
        slot["failed_kinds"] = sorted(slot["failed_kinds"])
    failed = [r for r in out if not r["passed"]]
    return {"levels": levels_pick, "checked": len(out), "failed_count": len(failed), "by_family": by_family,
            "assignment_kept": kept, "failed": failed, "rows": out}


def run(args: argparse.Namespace) -> dict[str, Any]:
    from foothold_s2.terrains.ex42_mesh_mount import (
        MeshHeights, expected_sha_from_manifest, load_combined_mesh, mesh_file_generator_cfg)

    from foothold_s2.terrains.ex42_column_reset import apply_column_reset, build_column_table

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
    table = build_column_table(list(data["column_family"]))
    apply_column_reset(env_cfg, table)
    result["column_reset_table"] = [{"column": c, "family": r["family"], "kind": r["kind"],
                                     "from_declaration": r["from_declaration"],
                                     "ranges": {k: list(v) for k, v in r["ranges"].items()}}
                                    for c, r in enumerate(table) if r["from_declaration"]]
    env = gym.make(TASK_ID, cfg=env_cfg)
    raw = env.unwrapped
    terrain = raw.scene.terrain
    result["env"] = {"num_envs": int(raw.num_envs), "terrain_types_used": sorted(set(
        terrain.terrain_types.cpu().tolist()))[:70]}
    checks: dict[str, Any] = {}
    scanner = raw.scene.sensors["height_scanner"] if "height_scanner" in raw.scene.sensors.keys() else None
    resets = []
    mesh_heights = MeshHeights(data["vertices"], data["faces"])
    foot_ids = raw.scene["robot"].find_bodies(".*_foot")[0]
    if len(foot_ids) != 4:
        raise RuntimeError(f"expected four foot bodies, found {len(foot_ids)}")
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
        robot = raw.scene["robot"]
        foot_pos = robot.data.body_pos_w[:, foot_ids].detach().cpu().numpy()       # (envs, feet, 3)
        root_np = root.detach().cpu().numpy()
        root_h = np.full(len(root_np), np.nan)
        feet_h = np.full(foot_pos.shape[:2], np.nan)
        for e in range(len(root_np)):
            pts = np.vstack([root_np[e:e + 1, :2], foot_pos[e, :, :2]])
            hs = mesh_heights.at(pts, radius=1.0)
            root_h[e], feet_h[e] = hs[0], hs[1:]
        above_mesh = root_np[:, 2] - root_h                      # root over the mesh under the root xy (pit floor if over a gap)
        support = np.nanmean(feet_h, axis=1)                      # mesh under the feet = what the robot stands on
        above_support = root_np[:, 2] - support
        foot_clear = foot_pos[:, :, 2] - feet_h                   # each foot over the mesh under that foot
        types = terrain.terrain_types.cpu().numpy()
        levels = terrain.terrain_levels.cpu().numpy()
        worst = np.argsort(-np.nan_to_num(above_mesh, nan=-1.0))[:3]
        row = {"reset": k, "env_origin_vs_terrain_origin_max_m": origin_gap,
               "root_xy_offset_max_m": float(xy_off.max().item()),
               "root_above_mesh_min_m": float(np.nanmin(above_mesh)), "root_above_mesh_max_m": float(np.nanmax(above_mesh)),
               "root_above_support_min_m": float(np.nanmin(above_support)),
               "root_above_support_max_m": float(np.nanmax(above_support)),
               "foot_clearance_min_m": float(np.nanmin(foot_clear)), "foot_clearance_max_m": float(np.nanmax(foot_clear)),
               "root_no_mesh_under": int(np.isnan(root_h).sum()),
               "worst_root_above_mesh": _worst(worst, 3, types, levels, data, root_np, root_h, support,
                                               above_support, foot_clear),
               "worst_foot_clearance": _worst(
                   np.argsort(-np.nan_to_num(np.nanmax(foot_clear, axis=1), nan=-9.0)), 3, types, levels, data,
                   root_np, root_h, support, above_support, foot_clear),
               "worst_root_above_support": _worst(
                   np.argsort(-np.nan_to_num(above_support, nan=-9.0)), 3, types, levels, data, root_np, root_h,
                   support, above_support, foot_clear)}
        if scanner is not None:
            scanner.update(raw.physics_dt, force_recompute=True)
            hits = scanner.data.ray_hits_w[:8].detach().cpu().numpy()          # 8 envs, all rays
            finite = np.isfinite(hits[..., 2])
            flat = hits.reshape(-1, 3)
            ref = mesh_heights.at(flat[:, :2], radius=3.0) if len(flat) <= 4000 else None
            if ref is not None:
                err = np.abs(flat[:, 2] - ref)
                row["scan"] = {"rays": int(len(flat)), "finite_fraction": float(finite.mean()),
                               "max_abs_error_m": float(np.nanmax(err)),
                               "ref_missing": int(np.isnan(ref).sum())}
        resets.append(row)
    result["resets"] = resets
    result["per_column"] = _per_column_pass(env, raw, terrain, mesh_heights, foot_ids, action, data, table, np, torch)
    result["height_scanner"] = scanner is not None
    ok = True
    for row in resets:
        ok &= row["env_origin_vs_terrain_origin_max_m"] <= 1e-4
        ok &= row["root_xy_offset_max_m"] <= CRITERIA["root_xy_offset_max_m"]
        ok &= (CRITERIA["root_above_support_min_m"] <= row["root_above_support_min_m"]
               and row["root_above_support_max_m"] <= CRITERIA["root_above_support_max_m"])
        ok &= row["foot_clearance_max_m"] <= CRITERIA["foot_clearance_max_m"]
        scan = row.get("scan")
        if scan is not None:
            ok &= scan["finite_fraction"] >= CRITERIA["scan_finite_fraction_min"]
            ok &= scan["max_abs_error_m"] <= CRITERIA["scan_error_max_abs_m"]
    ok &= result["per_column"]["failed_count"] == 0 and result["per_column"]["assignment_kept"]
    ok &= result["per_column"]["checked"] == len(data["column_family"]) * len(result["per_column"]["levels"])
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
