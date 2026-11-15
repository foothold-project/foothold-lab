"""CPU case assignment and per-tile mesh/initial-state fingerprint primitives."""
from __future__ import annotations

import hashlib
import json
import math
import re

import numpy as np

from s2_eval_cases import canonical


class FingerprintHold(RuntimeError):
    pass


def _array(value, *, shape=None):
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    result = np.asarray(value, dtype=np.float64)
    if (shape is not None and result.shape != shape) or not np.isfinite(result).all():
        raise FingerprintHold("physical_array_shape_or_nonfinite")
    return result


def array_sha(value, *, decimals=5):
    arr = _array(value)
    rounded = np.round(arr, decimals).astype("<f8", copy=False)
    return hashlib.sha256(str(rounded.shape).encode() + rounded.tobytes()).hexdigest()


def tile_mesh_sha(meshes, *, center_xy, size_xy):
    """Hash triangles whose world-space centroid belongs to one terrain tile."""
    cx, cy = (float(x) for x in center_xy)
    sx, sy = (float(x) for x in size_xy)
    if not all(math.isfinite(x) for x in (cx, cy, sx, sy)) or min(sx, sy) <= 0:
        raise FingerprintHold("tile_bounds")
    selected = []
    for mesh in meshes:
        if not mesh.get("prim_path", "").startswith("/World/ground"):
            continue
        points = _array(mesh["points"])
        if points.ndim != 2 or points.shape[1] != 3:
            raise FingerprintHold("mesh_points")
        for face in mesh["faces"]:
            if len(face) < 3 or any(type(i) is not int or i < 0 or i >= len(points) for i in face):
                raise FingerprintHold("mesh_face")
            vertices = points[face]
            mid = vertices.mean(axis=0)
            if cx-sx/2 <= mid[0] < cx+sx/2 and cy-sy/2 <= mid[1] < cy+sy/2:
                selected.append((mesh["prim_path"], sorted(np.round(vertices, 5).tolist())))
    if not selected:
        raise FingerprintHold("tile_mesh_empty")
    return hashlib.sha256(canonical(sorted(selected, key=repr))).hexdigest()


def case_row(case):
    match = re.fullmatch(r"[A-Za-z0-9_]+-(\d{3})-s(\d+)", case["case_id"])
    if not match or int(match.group(2)) != case["eval_seed"]:
        raise FingerprintHold("case_id_seed")
    return int(match.group(1)) % 8


def assign_one_case(terrain, case):
    """1043 q_eval_cmdr.py:335-340 uses family column and episode % 8 row."""
    row = case_row(case)
    origins = terrain.terrain_origins
    if origins.ndim != 3 or origins.shape[0] < 8 or origins.shape[1] != 1 or origins.shape[2] != 3:
        raise FingerprintHold("one_case_terrain_layout")
    if _array(terrain.terrain_types).size != 1 or _array(terrain.terrain_levels).size != 1:
        raise FingerprintHold("one_case_env_count")
    terrain.terrain_types[:] = 0
    terrain.terrain_levels[:] = row
    terrain.env_origins[:] = origins[row, 0]
    return {"terrain_row": row, "terrain_column": 0,
            "env_origin_w": _array(terrain.env_origins[0], shape=(3,)).round(5).tolist()}


def initial_state_sha(*, root_state_w, joint_pos, joint_vel, body_masses,
                      body_materials, actuator_state, command, physics_dt, policy_dt,
                      body_coms=None, ground_material=None, motor_offset=None):
    payload = {
        "root_state_w": array_sha(_array(root_state_w, shape=(13,))),
        "joint_pos": array_sha(joint_pos), "joint_vel": array_sha(joint_vel),
        "body_masses": array_sha(body_masses), "body_materials": array_sha(body_materials),
        "actuator_state": actuator_state,
        "command": command, "physics_dt": physics_dt, "policy_dt": policy_dt,
    }
    if body_coms is not None:
        payload["body_coms"] = array_sha(body_coms)
    if ground_material is not None:
        payload["ground_material"] = ground_material
    if motor_offset is not None:
        payload["motor_offset"] = array_sha(motor_offset)
    if not isinstance(actuator_state, dict) or not actuator_state:
        raise FingerprintHold("actuator_state_missing")
    digest = hashlib.sha256(canonical(payload)).hexdigest()
    return digest, payload


def case_fingerprint(case, *, mesh_sha256, initial_sha256, initial_components,
                     origin_x, zone_end_x):
    if len(mesh_sha256) != 64 or len(initial_sha256) != 64:
        raise FingerprintHold("fingerprint_hash")
    return {"mesh_sha256": mesh_sha256, "initial_state_sha256": initial_sha256,
            "initial_components": initial_components,
            "command_sha256": hashlib.sha256(canonical(case["command"])).hexdigest(),
            "friction": case["friction"], "terrain_seed": case["terrain_seed"],
            "eval_seed": case["eval_seed"], "policy_dt": case["policy_dt"],
            "physics_dt": case["physics_dt"], "origin_x": origin_x,
            "zone_end_x": zone_end_x}
