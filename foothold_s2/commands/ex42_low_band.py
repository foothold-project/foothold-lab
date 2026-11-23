"""EX-42 low-speed band commands (lead 2026-11-23 12:34 · team lead 12:30 real-robot basic command question). Off by default: only with
EX42_LOW_BAND_SHARE set to a share in (0, 1]. Off, the sampler draws nothing more and every command is the old one bit for bit.

Why: the E2 stage ranges start each moving slot at a minimum magnitude (forward_vx 0.1 · reverse_vx up to -0.2 · side_vy_abs 0.1 ·
spin_wz_abs 0.15), so a command between 0 and that minimum is never trained (a dead band). A real stick passes through it.

On (lead 2026-11-23 13:0x revision): after the stage draw (before the sparse-column paper form, which still overrides its own columns), a
row whose slot is forward · reverse · side_* · spin_* AND whose magnitude on its own axis is above the midpoint of that slot's stage range
(a fast row) is, with probability SHARE, moved into the band of its axis, keeping the slot and the sign. Every band is 0 ~ BAND (0.10):
    forward : vx ~ U[0, 0.10]                      reverse : vx ~ -U[0, 0.10]
    side_*  : |vy| ~ U[0, 0.10]                     spin_*  : |wz| ~ U[0, 0.10]
Rows at or below the midpoint (the slow rows, e.g. the flat 0.1 keep cell) are never moved, so the share comes only out of the fast part of
each range. Midpoints from the env's stage ranges: (lo + hi) / 2 of forward_vx, reverse_vx (compared by magnitude), side_vy_abs, spin_wz_abs.
Two extra draws for every row (pick · magnitude), so the stream does not depend on which rows move. The run's command contract
(curriculum.continuous.command_bad) accepts these band values only while this is on.
Line: EX42_LOW_BAND where=start share=... bands=... ; counts since start in summary(). No Kit import at module level.
"""
from __future__ import annotations

import os

import torch

ENV_SWITCH = "EX42_LOW_BAND_SHARE"
BAND = 0.10
_COUNTS = {"draws": 0, "moved": 0, "forward": 0, "reverse": 0, "side": 0, "spin": 0}
_STARTED = {"done": False}


def share() -> float:
    raw = os.environ.get(ENV_SWITCH, "")
    if raw in ("", "0"):
        return 0.0
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{ENV_SWITCH} must be a share in (0, 1] (got {raw!r})") from None
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{ENV_SWITCH} must be a share in (0, 1] (got {raw!r})")
    return value


def enabled() -> bool:
    return share() > 0.0


def bands(ranges) -> dict:
    """Band upper magnitude of every axis (BAND); `ranges` is read only to refuse a stage without the four slot ranges."""
    for key in ("forward_vx", "reverse_vx", "side_vy_abs", "spin_wz_abs"):
        if key not in ranges:
            raise ValueError(f"EX-42 low band: stage ranges lack {key}")
    return {"forward": BAND, "reverse": BAND, "side": BAND, "spin": BAND}


def midpoints(ranges) -> dict:
    """Magnitude above which a row counts as fast: the midpoint of the slot's own stage range."""
    mid = lambda key: abs(0.5 * (float(ranges[key][0]) + float(ranges[key][1])))      # noqa: E731
    out = {"forward": mid("forward_vx"), "reverse": mid("reverse_vx"), "side": mid("side_vy_abs"), "spin": mid("spin_wz_abs")}
    if any(v <= BAND for v in out.values()):
        raise ValueError(f"EX-42 low band: a range midpoint is not above the band {BAND} (got {out})")
    return out


def start_line(ranges) -> None:
    if _STARTED["done"]:
        return
    _STARTED["done"] = True
    b = bands(ranges)
    m = midpoints(ranges)
    print(f"EX42_LOW_BAND where=start share={share()} forward=[0, {b['forward']}] reverse=[-{b['reverse']}, 0] "
          f"side_abs=[0, {b['side']}] spin_abs=[0, {b['spin']}] from_rows_above_mid forward>{m['forward']} reverse<-{m['reverse']} "
          f"side_abs>{m['side']} spin_abs>{m['spin']} outside_stage_ranges=1", flush=True)


def apply(out: dict, ranges, draw, slots) -> dict:
    """`draw(n, lo, hi)` = the sampler's own uniform draw (same generator) · `slots` = slot names."""
    start_line(ranges)
    b = bands(ranges)
    n = out["cmd"].shape[0]
    pick = draw(n, 0.0, 1.0) < share()
    mag = draw(n, 0.0, 1.0)
    slot = out["slot"]
    names = [slots[int(i)] if 0 <= int(i) < len(slots) else "" for i in slot.tolist()]
    is_ = lambda pred: torch.tensor([pred(s) for s in names], dtype=torch.bool, device=slot.device)
    fwd, rev, side, spin = is_(lambda s: s == "forward"), is_(lambda s: s == "reverse"), is_(lambda s: s.startswith("side_")), is_(lambda s: s.startswith("spin_"))
    mid = midpoints(ranges)
    c0 = out["cmd"].to(slot.device)
    fwd = fwd & (c0[:, 0] > mid["forward"])                   # only fast rows give the share (slow rows, e.g. flat 0.1, are kept)
    rev = rev & (c0[:, 0] < -mid["reverse"])
    side = side & (c0[:, 1].abs() > mid["side"])
    spin = spin & (c0[:, 2].abs() > mid["spin"])
    pick = pick.to(slot.device)
    cmd = out["cmd"].clone()
    m = mag.to(cmd.device)
    cmd[:, 0] = torch.where(pick & fwd, m * b["forward"], cmd[:, 0])
    cmd[:, 0] = torch.where(pick & rev, -m * b["reverse"], cmd[:, 0])
    cmd[:, 1] = torch.where(pick & side, torch.sign(cmd[:, 1]) * m * b["side"], cmd[:, 1])
    cmd[:, 2] = torch.where(pick & spin & ~out["heading"], torch.sign(cmd[:, 2]) * m * b["spin"], cmd[:, 2])
    res = dict(out)
    res["cmd"] = cmd
    _COUNTS["draws"] += n
    for key, mask in (("forward", fwd), ("reverse", rev), ("side", side), ("spin", spin & ~out["heading"])):
        _COUNTS[key] += int((pick & mask).sum())
    _COUNTS["moved"] = _COUNTS["forward"] + _COUNTS["reverse"] + _COUNTS["side"] + _COUNTS["spin"]
    return res


def band_ok(name: str, value: torch.Tensor, ranges, tol: float) -> torch.Tensor:
    """Contract side: True where `value` is inside this slot's band (only consulted while enabled())."""
    b = bands(ranges)
    if name == "forward":
        return (value >= -tol) & (value <= b["forward"] + tol)
    if name == "reverse":
        return (value <= tol) & (value >= -b["reverse"] - tol)
    if name.startswith("side_"):
        return value.abs() <= b["side"] + tol
    if name.startswith("spin_"):
        return value.abs() <= b["spin"] + tol
    return torch.zeros_like(value, dtype=torch.bool)


def summary() -> dict | None:
    if not enabled():
        return None
    return {**_COUNTS, "moved_frac": _COUNTS["moved"] / _COUNTS["draws"] if _COUNTS["draws"] else None, "counting": "rank-local since process start"}
