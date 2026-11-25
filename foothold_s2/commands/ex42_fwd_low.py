"""E2 forward command lower end (lead 2026-11-26 01:23 (가)). EX42_FWD_LOW unset or empty leaves everything untouched.

Why: the judged forward 0.1 cell sits at the very bottom of the drawn forward range (E2 plan forward_vx [0.1, ...];
planner 01:22 TABLE9: drawn vx minimum 0.100~0.108), so the policy sees almost no command below it. With
EX42_FWD_LOW=0.05 the E2 stage's forward_vx lower end becomes 0.05 at runtime start; the sampler (mixed_core
resample_stage, low_forward_fraction band U[low, 0.3]) and the per-step command check (continuous.command_bad, bounded
forward_vx) both read the same stage ranges, so they stay consistent. The plan file and its SHA do not change.

Stand is its own slot (term.stand, zero command), so a 0.05 forward command never reads as a stop: four_foot_contact_at_stop,
ex40 stand terms and ex42_stop_bundle.stop_mask use term.stand, not a speed threshold. What does see 0.05..0.1 as "not slow":
ex42_slow_track / ex42_slow_progress (speed_min 0.1 in the plan) and the live slow_forward metrics (slow_min = that value).

Monitor: EX42_FWD_LOW where=start (old and new range) and EX42_FWD_LOW_MON (forward rows drawn, rows below 0.1, min vx)
at the first draws and then every MONITOR_EVERY resamples. No Kit import at module level.
"""
from __future__ import annotations

import dataclasses
import math
import os

import torch

ENV_SWITCH = "EX42_FWD_LOW"
STAGE = "E2"
OLD_LOW = 0.1
MONITOR_EVERY = 200
_COUNTS = {"calls": 0, "forward_rows": 0, "below_0p1": 0, "min_vx": math.inf}


def value() -> float | None:
    raw = os.environ.get(ENV_SWITCH, "")
    if raw == "":
        return None
    try:
        v = float(raw)
    except ValueError:
        raise ValueError(f"{ENV_SWITCH} must be a number in [0.02, 0.1) (got {raw!r})") from None
    if not math.isfinite(v) or not 0.02 <= v < OLD_LOW:
        raise ValueError(f"{ENV_SWITCH} must be a number in [0.02, 0.1) (got {raw!r})")
    return v


def apply_stages(stages, stage_id: str):
    """Returns the stage list with stages[0].ranges['forward_vx'] lowered (E2 only); the input list is not changed."""
    v = value()
    if v is None:
        return stages
    if stage_id != STAGE:
        raise ValueError(f"{ENV_SWITCH} is for stage {STAGE} only (runtime stage {stage_id})")
    first = stages[0]
    old = tuple(first.ranges["forward_vx"])
    if not v < old[1]:
        raise ValueError(f"{ENV_SWITCH}={v} is not below the forward_vx upper end {old[1]}")
    ranges = dict(first.ranges)
    ranges["forward_vx"] = (v, old[1])
    out = list(stages)
    out[0] = dataclasses.replace(first, ranges=ranges)
    print(f"EX42_FWD_LOW where=start stage={stage_id} forward_vx_old={list(old)} forward_vx_new={[v, old[1]]} "
          f"low_forward_fraction={getattr(first, 'low_forward_fraction', None)}", flush=True)
    return out


def observe(cmd: torch.Tensor, slot: torch.Tensor, forward_slot: int = 0) -> None:
    """Called after each free-env resample with the drawn commands and slots (record only)."""
    if value() is None or cmd.numel() == 0:
        return
    fwd = slot == forward_slot
    vx = cmd[fwd, 0]
    _COUNTS["calls"] += 1
    if vx.numel():
        _COUNTS["forward_rows"] += int(vx.numel())
        _COUNTS["below_0p1"] += int((vx < OLD_LOW - 1e-9).sum())
        _COUNTS["min_vx"] = min(_COUNTS["min_vx"], float(vx.min()))
    if _COUNTS["calls"] in (1, 20) or _COUNTS["calls"] % MONITOR_EVERY == 0:
        if int(os.environ.get("RANK", "0") or 0) == 0:
            print("EX42_FWD_LOW_MON " + " ".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}"
                                                 for k, v in summary().items()), flush=True)


def summary() -> dict:
    return {"calls": _COUNTS["calls"], "forward_rows": _COUNTS["forward_rows"], "below_0p1": _COUNTS["below_0p1"],
            "min_vx": _COUNTS["min_vx"] if math.isfinite(_COUNTS["min_vx"]) else None}
