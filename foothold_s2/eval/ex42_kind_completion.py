"""CPU completion count for a named EX-42 kind cell.

The START finish support begins at its geometry-defined +x boundary. A policy
failure remains in the denominator; only an explicitly unmeasured env can be
excluded by a later, separately evidenced contract.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np


def score_last_support(trace: dict, *, finish_x_m: float, settle_s: float) -> dict:
    """Count first arrival followed by a continuous alive window.

    `root_x_local_m` is relative to the mesh origin, as recorded by the Kit
    child. The arrival surface is the first x coordinate of the finish support.
    This deliberately does not infer success from the final root position alone.
    """
    x = np.asarray(trace["root_x_local_m"], dtype=np.float64)
    alive = np.asarray(trace["alive"])
    dt = float(trace["dt"])
    if (x.ndim != 2 or x.shape[1] != 64 or alive.shape != x.shape or
            alive.dtype != np.dtype(bool) or x.shape[0] < 1):
        raise ValueError("EX-42 kind trace shape or 64-env denominator differs")
    if not np.isfinite(x).all() or any(not math.isfinite(v) for v in (dt, finish_x_m, settle_s)):
        raise ValueError("EX-42 kind trace contains a nonfinite value")
    if dt <= 0 or settle_s <= 0:
        raise ValueError("EX-42 kind trace sample period or settle time invalid")
    if np.any(np.diff(alive.astype(np.int8), axis=0) > 0):
        raise ValueError("EX-42 kind trace resurrects an env after reset")
    following_steps = math.ceil(settle_s / dt)
    if following_steps >= len(x):
        raise ValueError("EX-42 kind trace is shorter than the support window")
    cases = []
    for env in range(64):
        reached = np.flatnonzero((x[:, env] >= finish_x_m) & alive[:, env])
        first = int(reached[0]) if len(reached) else None
        if first is None:
            reason = "not_reached"
        elif first + following_steps >= len(x):
            reason = "settle_window_short"
        elif not alive[first:first + following_steps + 1, env].all():
            reason = "reset_before_settle"
        else:
            reason = "complete"
        cases.append({"env": env, "first_reach_step": first, "success": reason == "complete",
                      "survival": bool(alive[-1, env]), "reason": reason})
    return {"envs": 64, "valid_count": 64,
            "success_count": sum(row["success"] for row in cases),
            "survival_count": sum(row["survival"] for row in cases),
            "per_env": cases}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_start_kind_cell(folder: Path, *, mesh: dict, checkpoint_sha256: str,
                         seed: int, family: str, kind: str, level: int,
                         mode: str, seconds: float, settle_s: float) -> dict:
    """Recount one pinned START forward cell from Kit's JSON and step arrays.

    This is limited to the START finish platform geometry. Other terrain
    families need their own approved finish anchor and completion method.
    """
    from foothold_s2.eval import fixed_terrain
    from foothold_s2.eval.ex42_mesh_eval import validate_kind_cell
    from foothold_s2.eval.start_sheet import GOAL_X

    if family != "A" or kind not in (
            "stepping_stones_low", "stepping_stones_high", "balance_beams",
            "stepping_beams", "gaps"):
        raise ValueError("EX-42 START finish scorer cannot judge this named kind")
    if mode not in ("eval_gt", "eval_pred", "probe_prop_only"):
        raise ValueError("EX-42 kind map mode invalid")
    folder = Path(folder)
    result_path = folder / "map_modes.json"
    result = json.loads(result_path.read_text(encoding="utf-8-sig"))
    key = f"{mode}/fwd1.0"
    expected_modes = {"eval_gt", "eval_pred", "probe_prop_only"}
    if (result.get("checkpoint_sha256") != checkpoint_sha256 or
            result.get("eval_seed") != seed or result.get("envs") != 64 or
            result.get("ex42_mesh", {}).get("mesh_sha256") != mesh.get("mesh_sha256") or
            set(result.get("modes", {})) != expected_modes or
            any(set(result["modes"][name]) != {"fwd1.0"} for name in expected_modes) or
            result.get("env_arrays", {}).get(key) != f"env_arrays_{mode}_fwd1.0.npz"):
        raise ValueError("EX-42 kind evaluation identity or mode coverage differs")
    validate_kind_cell(result, mesh, family=family, kind=kind, level=level)
    row = result["modes"][mode]["fwd1.0"]
    total = row.get("policy_steps_x_envs")
    used = row.get("gt_used")
    if (type(total) is not int or total != result["steps"] * 64 or type(used) is not int or
            used != (total if mode == "eval_gt" else 0)):
        raise ValueError("EX-42 kind map input was not consumed in the named mode")
    arrays_path = folder / result["env_arrays"][key]
    with np.load(arrays_path, allow_pickle=False) as arrays:
        a = {name: arrays[name] for name in arrays.files}
    table = [{"family": f, "kind": k} for f, k in zip(
        mesh["column_family"], mesh["columns"])]
    levels, types = fixed_terrain.kind_assignment(64, result["fixed_terrain"]["rows"],
                                                  table, family, kind, level)
    if (not np.array_equal(a["terrain_level"], levels) or
            not np.array_equal(a["terrain_col"], types) or
            not np.array_equal(a["kind"], np.repeat(kind, 64)) or
            str(a["assignment_sha256"]) != fixed_terrain.assignment_sha256(levels, types) or
            a["alive"].shape != (result["steps"], 64) or
            a["dones"].shape != a["alive"].shape or
            np.any(a["dones"] & a["alive"]) or
            row.get("alive_envs_at_end") != int(a["alive"][-1].sum()) or
            not math.isclose(float(a["dt"]) * result["steps"], seconds,
                             abs_tol=float(a["dt"]) / 2, rel_tol=0)):
        raise ValueError("EX-42 kind step arrays differ from pinned tile or duration")
    fixed_terrain.verify_kind_foot_arrays(a["foot_contact"], a["foot_pos_local"], a["alive"])
    counted = score_last_support(a, finish_x_m=GOAL_X, settle_s=settle_s)
    return {"case_id": f"{family}/{kind}/L{level}/fwd1.0/{mode}",
            "role": "record_only" if mode == "probe_prop_only" else "judge",
            "completion": "last_support_0.5s", **counted,
            "evidence": {"map_modes": {"path": str(result_path), "sha256": _sha(result_path)},
                         "arrays": {"path": str(arrays_path), "sha256": _sha(arrays_path)}}}
