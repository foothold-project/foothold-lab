"""CPU-only checker for S2 raw RayCaster connection captures.

All pass/fail thresholds are explicit. This module never imports Isaac.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "s2_step2"))
from s2_env_adapter import expected_world_xy, yaw_from_quat_wxyz
from base_step1.s2_map_obs import NUM_RAYS, height_and_mask

CASES = ("flat", "flat_yaw", "step", "gap", "stepping_stones")
HOLD_CODE = 42


@dataclass(frozen=True)
class Criteria:
    grid_xy_tolerance_m: float
    height_tolerance_m: float
    flat_z_span_m: float
    step_min_height_m: float
    gap_min_bad_cells: int
    stones_min_holes: int
    stones_max_height_m: float
    stones_min_spacing_cells: int
    stones_max_spacing_cells: int
    yaw_min_rad: float

    def __post_init__(self):
        for key, value in asdict(self).items():
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"nonnegative finite {key} required")
        if self.stones_min_spacing_cells > self.stones_max_spacing_cells:
            raise ValueError("stone spacing bounds reversed")


# Single change point for ASTRA's connection verdict. Each key is a hold reason.
CONNECTION_HOLD_TABLE = (
    "artifact_missing", "provenance_missing", "shape_or_case", "terrain_assignment_missing", "origin_missing",
    "reset_stale", "sensor_nonfinite", "ray_packet_bad", "grid_order_or_yaw",
    "yaw_probe_missing", "height_or_offset", "flat_not_flat", "step_not_seen",
    "gap_not_seen", "stones_not_seen", "stones_spacing", "strict_map_mismatch",
)


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_arrays(meta: dict, arrays: dict, criteria: Criteria) -> dict:
    reasons = []
    def add(key, bad):
        if bad and key not in reasons:
            reasons.append(key)

    for key in ("isaac_version", "torch_version", "driver_version", "env_config_sha256", "code_sha256",
                "parent_sha256", "capture_sha256"):
        add("provenance_missing", not meta.get(key))
    add("shape_or_case", meta.get("cases") != list(CASES))
    add("terrain_assignment_missing", meta.get("terrain_assignment_verified") is not True)
    add("reset_stale", meta.get("reset_evidence") != "sensor_timestamp")
    required = ("pos_w", "ray_hits_w", "root_pos_w", "root_quat_w", "env_origin_w", "height", "mask",
                "episode_ids", "frame_tokens", "reset_receipt")
    if any(key not in arrays for key in required):
        return {"verdict": "HOLD", "reasons": sorted(set(reasons + ["artifact_missing"])),
                "criteria": asdict(criteria)}
    pos, hits, roots, quat, origins = (np.asarray(arrays[k]) for k in required[:5])
    height, mask = np.asarray(arrays["height"]), np.asarray(arrays["mask"])
    episodes = np.asarray(arrays["episode_ids"])
    tokens = np.asarray(arrays["frame_tokens"])
    receipts = np.asarray(arrays["reset_receipt"])
    n = pos.shape[2] if pos.ndim == 4 else -1
    shapes = (pos.shape == (5, 2, n, 3) and hits.shape == (5, 2, n, NUM_RAYS, 3)
              and roots.shape == pos.shape and quat.shape == (5, 2, n, 4)
              and origins.shape == pos.shape and height.shape == (5, 2, n, NUM_RAYS)
              and mask.shape == height.shape and episodes.shape == (5, 2, n)
              and tokens.shape == episodes.shape and receipts.shape == (5, n))
    add("shape_or_case", not shapes or n < 1)
    if not shapes or n < 1:
        return {"verdict": "HOLD", "reasons": sorted(set(reasons)), "criteria": asdict(criteria)}
    add("origin_missing", not np.isfinite(origins).all())
    add("reset_stale", bool((episodes[:, 1] < episodes[:, 0]).any() or
                             (tokens[:, 1] <= tokens[:, 0]).any() or
                             not np.all(receipts == 1)))
    add("sensor_nonfinite", not np.isfinite(pos).all() or not np.isfinite(roots).all() or not np.isfinite(quat).all())
    finite = np.isfinite(hits).all(axis=-1)
    miss = np.isposinf(hits).all(axis=-1)
    add("ray_packet_bad", bool((~(finite | miss)).any()))
    if np.isfinite(pos).all() and np.isfinite(quat).all():
        p = torch.as_tensor(pos.reshape(-1, n, 3), dtype=torch.float64).reshape(-1, 3)
        q = torch.as_tensor(quat.reshape(-1, 4), dtype=torch.float64)
        yaw = yaw_from_quat_wxyz(q)
        xy = expected_world_xy(p, yaw).numpy().reshape(5, 2, n, NUM_RAYS, 2)
        add("grid_order_or_yaw", bool((np.abs(hits[..., :2] - xy)[finite].max(initial=0)
                                       > criteria.grid_xy_tolerance_m)))
        add("yaw_probe_missing", bool(np.abs(yaw.reshape(5, 2, n)[1]).max() < criteria.yaw_min_rad))
    if np.isfinite(pos).all() and not bool((~(finite | miss)).any()):
        hm, mm, faults = height_and_mask(torch.as_tensor(pos.reshape(-1, 3)),
                                          torch.as_tensor(hits.reshape(-1, NUM_RAYS, 3)), strict=False)
        expected_h = hm.numpy().reshape(height.shape)
        expected_m = mm.numpy().reshape(mask.shape)
        add("height_or_offset", bool(not np.isfinite(height).all() or
                                      np.abs(height - expected_h).max(initial=0) > criteria.height_tolerance_m))
        add("strict_map_mismatch", bool(faults.total or not np.array_equal(mask, expected_m)))
    local_z = hits[..., 2] - origins[..., 2, None]
    flat_values = local_z[0, 0][finite[0, 0]]
    add("flat_not_flat", bool(flat_values.size == 0 or
                              np.ptp(flat_values) > criteria.flat_z_span_m or
                              np.ptp(pos[0, 0, :, 2]) > criteria.flat_z_span_m))
    flat_ref = float(np.median(flat_values)) if flat_values.size else math.nan
    step_heights = local_z[2, 0][finite[2, 0]]
    add("step_not_seen", bool(step_heights.size == 0 or
                               np.max(np.abs(step_heights - flat_ref)) < criteria.step_min_height_m))
    gap_bad = miss[3].sum() + int((local_z[3][finite[3]] < flat_ref - criteria.step_min_height_m).sum())
    add("gap_not_seen", bool(gap_bad < criteria.gap_min_bad_cells))
    deep_stones = finite[4] & (local_z[4] < flat_ref - criteria.step_min_height_m)
    stones_holes = int(miss[4].sum() + deep_stones.sum())
    stones_top = np.max(local_z[4][finite[4]], initial=-math.inf)
    add("stones_not_seen", bool(stones_holes < criteria.stones_min_holes or
                                 stones_top - flat_ref > criteria.stones_max_height_m))
    center = (miss[4, 0, 0] | deep_stones[0, 0]).reshape(11, 17)[5]
    hole_at = np.flatnonzero(center)
    if len(hole_at) >= 2:
        spacing = np.diff(hole_at)
        add("stones_spacing", bool((spacing < criteria.stones_min_spacing_cells).any() or
                                     (spacing > criteria.stones_max_spacing_cells).any()))
    else:
        add("stones_spacing", True)
    return {"verdict": "PASS" if not reasons else "HOLD", "reasons": sorted(set(reasons)),
            "criteria": asdict(criteria), "counts": {"normal_miss": int(miss.sum()),
                                                      "bad_packets": int((~(finite | miss)).sum())}}


def check_path(root: Path, criteria: Criteria) -> dict:
    meta_path, data_path = root / "meta.json", root / "capture.npz"
    if not meta_path.is_file() or not data_path.is_file():
        return {"verdict": "HOLD", "reasons": ["artifact_missing"]}
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("capture_sha256") != _sha_file(data_path):
        return {"verdict": "HOLD", "reasons": ["artifact_missing", "provenance_missing"]}
    with np.load(data_path, allow_pickle=False) as data:
        return check_arrays(meta, {k: data[k] for k in data.files}, criteria)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--criteria", type=Path, required=True)
    a = ap.parse_args(argv)
    result = check_path(a.root, Criteria(**json.loads(a.criteria.read_text(encoding="utf-8"))))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["verdict"] == "PASS" else HOLD_CODE


if __name__ == "__main__":
    raise SystemExit(main())
