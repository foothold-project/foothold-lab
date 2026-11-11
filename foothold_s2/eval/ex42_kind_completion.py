"""CPU completion count for a named EX-42 kind cell.

The START finish support begins at its geometry-defined +x boundary. A policy
failure remains in the denominator; only an explicitly unmeasured env can be
excluded by a later, separately evidenced contract.
"""
from __future__ import annotations

import math

import numpy as np


def score_last_support(trace: dict, *, finish_x_m: float, settle_s: float) -> dict:
    """Count first arrival followed by a continuous alive window on the finish side.

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
    need = math.ceil(settle_s / dt)
    if need > len(x):
        raise ValueError("EX-42 kind trace is shorter than the support window")
    cases = []
    for env in range(64):
        reached = np.flatnonzero((x[:, env] >= finish_x_m) & alive[:, env])
        first = int(reached[0]) if len(reached) else None
        if first is None:
            reason = "not_reached"
        elif first + need > len(x):
            reason = "settle_window_short"
        elif not alive[first:first + need, env].all():
            reason = "reset_before_settle"
        elif not (x[first:first + need, env] >= finish_x_m).all():
            reason = "left_finish_support"
        else:
            reason = "complete"
        cases.append({"env": env, "first_reach_step": first, "success": reason == "complete",
                      "survival": bool(alive[-1, env]), "reason": reason})
    return {"envs": 64, "valid_count": 64,
            "success_count": sum(row["success"] for row in cases),
            "survival_count": sum(row["survival"] for row in cases),
            "per_env": cases}
