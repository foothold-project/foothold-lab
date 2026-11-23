"""E2 command-width candidate. EX42_CMD_WIDE=0 leaves draws and commands untouched.

Only E2 free-speed rows change. Diagonal |vx| is redrawn from [0.3, 1.2].
Among non-heading forward rows with vx > 1.2, EX42_CMD_WIDE_SHARE (default 0.5)
gets wz = +/-U[0.1, 0.6]. All draws use the existing command generator.
"""
from __future__ import annotations

import os

import torch


ENV_SWITCH = "EX42_CMD_WIDE"
SHARE_ENV = "EX42_CMD_WIDE_SHARE"
DIAG_VX_ABS = (0.3, 1.2)
FAST_FORWARD_VX = 1.2
FORWARD_WZ_ABS = (0.1, 0.6)
_COUNTS = {"diag_rows": 0, "diag_above_old_max": 0, "fast_forward_rows": 0,
           "turned_forward": 0, "turned_left": 0, "turned_right": 0}
_STARTED = {"done": False}


def enabled() -> bool:
    raw = os.environ.get(ENV_SWITCH, "0")
    if raw not in ("0", "1", ""):
        raise ValueError(f"{ENV_SWITCH} must be 0 or 1 (got {raw!r})")
    return raw == "1"


def active(stage_id: str | None) -> bool:
    return enabled() and stage_id == "E2"


def share() -> float:
    raw = os.environ.get(SHARE_ENV, "0.5")
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{SHARE_ENV} must be in [0, 1] (got {raw!r})") from None
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{SHARE_ENV} must be in [0, 1] (got {raw!r})")
    return value


def _start_line(value: float) -> None:
    if not _STARTED["done"]:
        _STARTED["done"] = True
        print(f"EX42_CMD_WIDE where=start stage=E2 share={value:g} "
              f"diag_vx_abs={list(DIAG_VX_ABS)} forward_vx_gt={FAST_FORWARD_VX:g} "
              f"forward_wz_abs={list(FORWARD_WZ_ABS)}", flush=True)


def apply(out: dict, stage, draw, slots, eligible: torch.Tensor | None = None,
          *, stage_id: str | None = None) -> dict:
    """`draw(n,lo,hi)` uses the caller's command RNG. The EX-42 runtime owns stage_id."""
    if not active(stage_id):
        return out
    value = share()
    _start_line(value)
    cmd = out["cmd"].clone()
    n = len(cmd)
    if eligible is None:
        eligible = torch.ones(n, dtype=torch.bool, device=cmd.device)
    elif eligible.shape != (n,):
        raise ValueError("EX42_CMD_WIDE eligible mask has wrong shape")
    eligible = eligible.to(cmd.device).bool()
    slot = out["slot"].to(cmd.device)
    heading = out["heading"].to(cmd.device)
    diagonal = eligible & (slot >= slots.index("diag_fwd_left")) & (slot <= slots.index("diag_back_right"))
    fast = eligible & (slot == slots.index("forward")) & ~heading & (cmd[:, 0] > FAST_FORWARD_VX)
    # Fixed-size draws keep on-mode RNG independent of how many rows hit a slot.
    diag_mag = draw(n, *DIAG_VX_ABS).to(cmd.device)
    pick = draw(n, 0.0, 1.0).to(cmd.device) < value
    turn_mag = draw(n, *FORWARD_WZ_ABS).to(cmd.device)
    turn_left = draw(n, 0.0, 1.0).to(cmd.device) < 0.5
    turned = fast & pick
    cmd[:, 0] = torch.where(diagonal, torch.sign(cmd[:, 0]) * diag_mag, cmd[:, 0])
    cmd[:, 2] = torch.where(turned, torch.where(turn_left, turn_mag, -turn_mag), cmd[:, 2])
    _COUNTS["diag_rows"] += int(diagonal.sum())
    _COUNTS["diag_above_old_max"] += int((diagonal & (cmd[:, 0].abs() > stage.ranges["diag_vx_abs"][1])).sum())
    _COUNTS["fast_forward_rows"] += int(fast.sum())
    _COUNTS["turned_forward"] += int(turned.sum())
    _COUNTS["turned_left"] += int((turned & turn_left).sum())
    _COUNTS["turned_right"] += int((turned & ~turn_left).sum())
    return {**out, "cmd": cmd}


def summary() -> dict | None:
    if not enabled():
        return None
    n = _COUNTS["fast_forward_rows"]
    return {**_COUNTS, "share": share(), "turned_forward_frac": _COUNTS["turned_forward"] / n if n else None,
            "counting": "rank-local since process start, E2 free commands after sparse exclusion"}
