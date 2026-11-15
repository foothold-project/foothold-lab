"""Read-only CPU inspection of the copied A3.2 capture and original PhysX sample."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def analyze(capture_path: Path, physx_path: Path, cfg_path: Path):
    with np.load(capture_path) as cap, np.load(physx_path) as phys:
        steps = phys["steps"]
        status = phys["status"]
        starts = cap["ray_starts_w"]
        dirs = cap["ray_directions_w"]
        quat = cap["root_quat_w"][:16, 6]
        dev = np.abs(quat - quat[0])
        ij = np.unravel_index(np.argmax(dev), dev.shape)
        sample_starts = starts[steps]
        sample_dirs = dirs[steps]
        finite = np.isfinite(cap["ray_hits_w"][steps]).all(axis=-1)
        world = cap["ray_hits_w"][steps, ..., 2]
        span = sample_starts[..., 2] - world
        flat = starts[steps[0], 0, :, :]
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        snapshot = cfg.get("cfg", cfg)
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot)
        scene = snapshot["scene"]
        return {
            "physx_steps": len(steps), "physx_status_counts": {str(int(x)): int(n) for x, n in
                                                            zip(*np.unique(status, return_counts=True))},
            "physx_paths": phys["paths"].tolist(),
            "sample_start_z_minmax": [float(np.min(sample_starts[..., 2])), float(np.max(sample_starts[..., 2]))],
            "sample_direction_z_minmax": [float(np.min(sample_dirs[..., 2])), float(np.max(sample_dirs[..., 2]))],
            "sample_direction_norm_minmax": [float(np.min(np.linalg.norm(sample_dirs, axis=-1))),
                                             float(np.max(np.linalg.norm(sample_dirs, axis=-1)))],
            "sample_finite_rays": int(np.sum(finite)),
            "finite_expected_distance_minmax_m": [float(np.min(span[finite])), float(np.max(span[finite]))],
            "sample_flat_start_xyz_first": flat[0].astype(float).tolist(),
            "sample_flat_hit_xyz_first": cap["ray_hits_w"][steps[0], 0, 0].astype(float).tolist(),
            "sample_flat_dir_xyz_first": sample_dirs[0, 0, 0].astype(float).tolist(),
            "robotlab_old_cfg_terrain_collision_group": scene["terrain"].get("collision_group"),
            "quat_env6_first16": quat.astype(float).tolist(),
            "quat_env6_abs_deviation_max": float(dev[ij]),
            "quat_env6_max_step_and_component": [int(ij[0]), int(ij[1])],
            "quat_env6_last16_component_deviation": dev[-1].astype(float).tolist(),
            "env6_pos_first16": cap["root_pos_w"][:16, 6].astype(float).tolist(),
            "env6_termination_first16": cap["termination"][:16, 6].tolist(),
            "env6_reset_first16": cap["reset_mask"][:16, 6].tolist(),
            "env6_hit_z_minmax_first16": [float(np.nanmin(cap["ray_hits_w"][:16, 6, :, 2])),
                                             float(np.nanmax(cap["ray_hits_w"][:16, 6, :, 2]))],
        }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("capture", type=Path)
    ap.add_argument("physx", type=Path)
    ap.add_argument("cfg", type=Path)
    a = ap.parse_args()
    print(json.dumps(analyze(a.capture, a.physx, a.cfg), indent=2, sort_keys=True))
