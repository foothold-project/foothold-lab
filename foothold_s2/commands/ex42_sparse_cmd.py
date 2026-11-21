"""EX-42 sparse-column commands in the START paper's form (lead 2026-11-22 07:44 ledger ef5bf2b33 · planner 07:43). Off by default: only with
EX42_SPARSE_PAPER_CMD=1. Off, the sampler draws nothing more and every command is the old one bit for bit.

Why: START trains sparse terrain with forward 0.3~1.5 m/s (no side) or a turn in place (a forward draw below 0.3 becomes 0 and the yaw rate is
U[-1.2, 1.2] rad/s). Our A sparse columns get the stage mix of every slot (forward 19 %, side 20 %, back 11 % ...).

On: an env whose terrain column is an A-family sparse kind (stepping_stones_low, stepping_stones_high, balance_beams, stepping_beams, gaps:
terrains.columns.SPARSE without flat) has its freshly drawn command replaced after every other draw (the same place as stone_forward_floor):
    v  ~ U[0, 1.5]
    v >= 0.3 : forward  (vx = v, vy = 0, wz = 0) · slot forward · no heading
    v <  0.3 : turn     (vx = 0, vy = 0, wz = ±U[0.15, 1.2], sign 50/50) · slot spin_left / spin_right by sign · no heading
               (|wz| from 0.15, not 0: the stage's spin slot contract is |wz| in spin_wz_abs [0.15, 1.5] and a turn of almost 0 would
               break the run's command contract check; the paper range is otherwise kept)
    stand is cleared. Continuous columns, flat and the B~E families keep the stage mix.
Lines: EX42_SPARSE_PAPER_CMD where=start (kinds · ranges · outside the stage mix), and the counts since start (sparse env draws, forward,
turn) in every command_shares record (key sparse_paper_cmd). No Kit import at module level.
"""
from __future__ import annotations

import os

import torch

ENV_SWITCH = "EX42_SPARSE_PAPER_CMD"
KINDS_ENV = "EX42_SPARSE_PAPER_CMD_KINDS"       # lead 08:10 (E3 prep): comma list of family/kind, e.g. A/gaps,B/pallets,B/beam,B/gap,C/gap
FAMILY = "A"
KINDS = ("stepping_stones_low", "stepping_stones_high", "balance_beams", "stepping_beams", "gaps")
DEFAULT_COLUMNS = tuple(f"{FAMILY}/{k}" for k in KINDS)
V_MAX, V_TURN, WZ_MAX = 1.5, 0.3, 1.2          # START: forward 0.3~1.5 · below 0.3 = turn in place U[-1.2, 1.2]
WZ_MIN = 0.15                                   # the E2 stage spin_wz_abs low end (command contract)
_COUNTS = {"sparse_draws": 0, "forward": 0, "turn": 0, "beam_draws": 0, "beam_forward": 0, "beam_turn": 0}   # beam = A/balance_beams only (lead 07:46)
_STARTED = {"done": False}


def enabled() -> bool:
    value = os.environ.get(ENV_SWITCH, "")
    if value not in ("", "0", "1"):
        raise ValueError(f"{ENV_SWITCH} must be 0 or 1 (got {value!r})")
    return value == "1"


def columns() -> tuple:
    """The family/kind names that take the paper form: EX42_SPARSE_PAPER_CMD_KINDS (comma list) or the five A sparse kinds."""
    raw = os.environ.get(KINDS_ENV, "")
    if raw == "":
        return DEFAULT_COLUMNS
    names = tuple(k.strip() for k in raw.split(",") if k.strip())
    if not names or any(k.count("/") != 1 or not all(k.split("/")) for k in names):
        raise ValueError(f"{KINDS_ENV} must be a comma list of family/kind (got {raw!r})")
    return names


def column_mask(table, kinds=None) -> torch.Tensor:
    """(columns,) bool: the column's family/kind is in columns() (or, with `kinds`, an A-family kind in that tuple). Names not in the table refuse."""
    if table is None:
        raise ValueError("EX-42 sparse paper commands need the column table (raw._ex42_column_table) on the environment")
    want = set(f"{FAMILY}/{k}" for k in kinds) if kinds is not None else set(columns())
    have = {f"{row['family']}/{row['kind']}" for row in table}
    if kinds is None and os.environ.get(KINDS_ENV, "") and want - have:   # an explicit list must name real columns (the default five need not all be there)
        raise ValueError(f"{KINDS_ENV}: not in the column table: {sorted(want - have)}")
    return torch.tensor([f"{row['family']}/{row['kind']}" in want for row in table], dtype=torch.bool)


def start_line(table) -> None:
    if _STARTED["done"]:
        return
    _STARTED["done"] = True
    mask = column_mask(table)
    print(f"EX42_SPARSE_PAPER_CMD where=start columns={int(mask.sum())} of={len(mask)} kinds={','.join(columns())} "
          f"forward=[{V_TURN}, {V_MAX}] side=0 turn_below={V_TURN} wz_abs=[{WZ_MIN}, {WZ_MAX}] outside_stage_mix=1", flush=True)


def apply(out: dict, sparse: torch.Tensor, draw, slots, beam: torch.Tensor | None = None) -> dict:
    """Replace the drawn command of the sparse rows. `draw(n, lo, hi)` is the sampler's own uniform draw (same generator); `slots` the slot names.
    Three extra draws for all rows (so the stream does not depend on which rows are sparse)."""
    n = out["cmd"].shape[0]
    v = draw(n, 0.0, V_MAX)
    mag = draw(n, WZ_MIN, WZ_MAX)
    wz = torch.where(draw(n, 0.0, 1.0) < 0.5, mag, -mag)
    turn = v < V_TURN
    sp = sparse.to(out["cmd"].device).bool()
    cmd = out["cmd"].clone()
    cmd[sp, 0] = torch.where(turn[sp], torch.zeros_like(v[sp]), v[sp])
    cmd[sp, 1] = 0.0
    cmd[sp, 2] = torch.where(turn[sp], wz[sp], torch.zeros_like(wz[sp]))
    slot = out["slot"].clone()
    fwd_i, left_i, right_i = slots.index("forward"), slots.index("spin_left"), slots.index("spin_right")
    slot[sp] = torch.where(turn[sp], torch.where(wz[sp] > 0, torch.full_like(slot[sp], left_i), torch.full_like(slot[sp], right_i)),
                           torch.full_like(slot[sp], fwd_i))
    res = dict(out)
    res["cmd"], res["slot"] = cmd, slot
    res["stand"] = out["stand"] & ~sp
    res["spin"] = torch.where(sp, turn, out["spin"])
    res["heading"] = out["heading"] & ~sp
    res["psi_star"] = torch.where(sp, torch.zeros_like(out["psi_star"]), out["psi_star"])
    _COUNTS["sparse_draws"] += int(sp.sum())
    _COUNTS["turn"] += int((sp & turn).sum())
    _COUNTS["forward"] += int((sp & ~turn).sum())
    if beam is not None:
        bm = beam.to(sp.device).bool() & sp
        _COUNTS["beam_draws"] += int(bm.sum()); _COUNTS["beam_turn"] += int((bm & turn).sum()); _COUNTS["beam_forward"] += int((bm & ~turn).sum())
    return res


def summary() -> dict | None:
    if not enabled():
        return None
    total, beam = _COUNTS["sparse_draws"], _COUNTS["beam_draws"]
    return {**_COUNTS, "forward_frac": _COUNTS["forward"] / total if total else None,
            "turn_frac": _COUNTS["turn"] / total if total else None,
            "beam_forward_frac": _COUNTS["beam_forward"] / beam if beam else None, "beam_turn_frac": _COUNTS["beam_turn"] / beam if beam else None,
            "counting": "rank-local since process start"}
