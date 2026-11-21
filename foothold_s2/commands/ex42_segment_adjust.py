"""EX-42 segment adjustment (CURRICULUM-GATES E.2 E1 「구간 명령 조정」 and the reward cells). No Kit imports.

A resumed segment must carry the plan and approval SHA of the first one, so what changes at a boundary comes from a
file outside both (EX42_SEGMENT_ADJUST):

    {"schema": "ex42-segment-adjust/1", "stage_id": "E1", "plan_sha256": "<the run's plan>",
     "segments": {"3": {"decided_at": "...", "reason": "...", "evidence": "...",
                        "commands": {"shares": {...}, "ranges": {...}, "turn_overlay": {"fraction": f, "wz_abs": [a, b]}},
                        "rewards": {"track_lin_vel_std": s, "track_ang_vel_std": s, "feet_air_time": w, "foot_slip": w, "zero_yaw": w,
                                    "feet_air_time_threshold": s, "slow_track": w, "slow_track_sigma": s,
                                    "slow_track_speed_min": v, "slow_track_speed_max": v}}}}

An entry carries `commands`, `rewards`, `low_forward_fraction` or several of them and holds from its boundary on, each
kind until a later entry of the same kind. An entry for a boundary the run has not reached is refused.

* commands: only a stage whose plan row has `command_adjust_limits`, only at a boundary before its level cap first
  rises (E1: 1 and 2), every value inside those limits.
* rewards: the stage's plan row may register the cells for the whole stage (`rewards`, from its first update); a file
  entry changes them at any boundary from 1 on. Every value is inside `curriculum/ex42-reward-adjust-limits.yaml` (outside
  the plan so that a run already started can use it; its SHA is recorded). The EX-41 weight cells go on the stage's
  reward table; the parameter cells (the two tracking widths, the feet_air_time threshold, the constants of
  `ex42_slow_track`) and the weight of `ex42_slow_track` go on the env config (`apply_reward_params`, which also
  registers that term at weight 0); the live reward manager is read back (`reward_readback`).

* low_forward_fraction (2026-11-13): the share of the forward commands drawn from the slow end of the forward range
  (`mixed_core.resample_stage`: below 0.3 m/s; the source stage has 0.20). The stage's plan row may register it for
  the whole stage (`low_forward_fraction`, from its first update); a file entry changes it at the boundaries where
  commands may change. Every value is inside `command_cells.low_forward_fraction` of the same limits file; without
  that cell a row or an entry that names it is refused. The command ranges do not change, so the per-step command
  check is untouched.

* low_side_fraction (2026-11-16): the share of the side commands drawn with |vy| in [0.1, 0.3] (`mixed_core.resample_stage`;
  the rest from 0.3 to the upper end of side_vy_abs). Registered and changed exactly like low_forward_fraction, inside
  `command_cells.low_side_fraction` of the limits file. Off (no cell) draws nothing extra: the sampler is bit for bit the old one.

* slow_hold_range_s (2026-11-16): how long the slow forward commands are held (`mixed_command._apply_slow_hold`). The stage's plan row
  registers it (`slow_hold_range_s`: [lo, hi] seconds, or no cell = off); a file entry turns it off (null) or sets another range
  at any boundary from 1 on, inside the row's own fence `slow_hold_fence_s: [low, high]` (a row without that cell takes no entry) and
  0 < lo <= hi <= 30. Without a file the row's value stays. The record carries source plan | adjust_file.

Each started segment leaves `segment_commands_b<k>.json` in the run folder, in the shape of the input (a record's
`commands` / `rewards.values` can be pasted into the next file); a later start must reproduce what the earlier
segments recorded.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

from foothold_s2.commands.ex42_shares import command_adjust_limits, stage_commands, validate_commands

SCHEMA = "ex42-segment-adjust/1"
RECEIPT = "ex42-segment-commands/1"
TOL = 1e-9
REWARD_LIMITS = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-reward-adjust-limits.yaml"
REWARD_LIMITS_SCHEMA = "ex42-reward-adjust-limits/1"
WEIGHT_CELLS = {"feet_air_time": "ex41_feet_air_time", "foot_slip": "ex41_foot_slip",        # stage reward key -> live term
                "zero_yaw": "ex41_zero_yaw"}       # yaw rate while the turn command is zero (heading drift, 2026-11-13)
STD_CELLS = {"track_lin_vel_std": "track_lin_vel", "track_ang_vel_std": "track_ang_vel"}    # cell -> env reward term
# decisions.tsv 2026-11-13 15:30 (slow forward): cells of the env config, in force from the env build.
# cell -> (env reward term, parameter, value when the config does not carry the parameter)
PARAM_CELLS = {**{cell: (term, "std", None) for cell, term in STD_CELLS.items()},
               "feet_air_time_threshold": ("ex41_feet_air_time", "threshold", 0.5),
               "slow_track_sigma": ("ex42_slow_track", "sigma", None),
               "slow_track_speed_min": ("ex42_slow_track", "speed_min", None),
               "slow_track_speed_max": ("ex42_slow_track", "speed_max", None)}
ENV_WEIGHT_CELLS = {"slow_track": "ex42_slow_track",       # cell -> env reward term whose weight it is
                    "slow_progress": "ex42_slow_progress",     # decisions.tsv 2026-11-14 01:21: registered at weight 0
                    "slow_overspeed": "ex42_slow_overspeed"}   # candidate C (lead 2026-11-19 23:03): a penalty, registered at weight 0
REWARD_CELLS = (*STD_CELLS, *WEIGHT_CELLS, "feet_air_time_threshold", "slow_track", "slow_track_sigma",
                "slow_track_speed_min", "slow_track_speed_max", "slow_progress", "slow_overspeed")
# Cells added after plans and receipts already existed: a row, an entry, a limits file or a readback without them means
# this value (the term is off), so the older ten-cell documents stay readable.
OPTIONAL_CELLS = {"slow_progress": 0.0, "slow_overspeed": 0.0}


def complete_cells(cell):
    """The cells with the optional ones filled in. Anything that is not a dict is returned as it is (refused later)."""
    if not isinstance(cell, dict):
        return cell
    return {**{name: default for name, default in OPTIONAL_CELLS.items() if name not in cell}, **cell}
HOLD_CELL = "slow_hold_range_s"            # a [lo, hi] pair or null, fenced by the plan row (`slow_hold_fence_s`), not by the limits file
HOLD_MAX_S = 30.0
COMMAND_CELLS = ("low_forward_fraction", "low_side_fraction")          # command distribution cells outside the 13-slot profile
# Run-time cells (decisions.tsv 2026-11-14 12:42, v28): off or at the first segment's value at the start of a run, changed
# only through the update-boundary adjustment file. policy_std_cap: 0 = off, else a ceiling on the policy action std.
# terrain_level_cap: the promotion cap of the continuous columns (an integer, raised only).
RUNTIME_CELLS = ("policy_std_cap", "terrain_level_cap")


def adjustable_boundaries(plan, stage_id) -> tuple[int, ...]:
    """The boundaries where the command profile may change: after the first segment, before the level cap first rises."""
    row = next((s for s in plan.document["stages"] if s["id"] == stage_id), {})
    first = (row.get("terrain", {}).get("continuous_level_cap") or {}).get("first_raise_boundary", 1)
    return tuple(range(1, first)) if row.get("command_adjust_limits") is not None and type(first) is int else ()


def reward_limits(path=REWARD_LIMITS) -> dict | None:
    """{sha256, cells: {name: (low, high)}} from the limits file; None when there is none (no reward adjustment)."""
    import yaml

    path = Path(path)
    if not path.is_file():
        return None
    raw = path.read_bytes()
    document = yaml.safe_load(raw.decode("utf-8"))
    cells = document.get("cells") if isinstance(document, dict) else None
    if isinstance(cells, dict):      # a limits file older than an optional cell keeps that cell closed on its default
        cells = {**{name: [default, default] for name, default in OPTIONAL_CELLS.items() if name not in cells}, **cells}
    number = lambda v: type(v) in (int, float) and math.isfinite(v)   # noqa: E731
    if (not isinstance(document, dict) or document.get("schema") != REWARD_LIMITS_SCHEMA or not isinstance(cells, dict)
            or set(cells) != set(REWARD_CELLS)
            or any(not isinstance(pair, list) or len(pair) != 2 or not all(number(v) for v in pair) or pair[0] > pair[1]
                   for pair in cells.values())):
        raise ValueError(f"EX-42 reward adjust limits need schema {REWARD_LIMITS_SCHEMA} and [low, high] for {list(REWARD_CELLS)}")
    extra = document.get("command_cells", {})
    if (not isinstance(extra, dict) or not set(extra) <= set(COMMAND_CELLS)
            or any(not isinstance(pair, list) or len(pair) != 2 or not all(number(v) for v in pair)
                   or not 0.0 <= pair[0] <= pair[1] <= 1.0 for pair in extra.values())):
        raise ValueError(f"EX-42 adjust limits: command_cells may hold [low, high] inside 0..1 for {list(COMMAND_CELLS)} only")
    runtime = document.get("runtime_cells")
    if runtime is not None and (not isinstance(runtime, dict) or set(runtime) != set(RUNTIME_CELLS)
                                or any(not isinstance(pair, list) or len(pair) != 2 or not all(number(v) for v in pair)
                                       or not 0.0 <= pair[0] <= pair[1] for pair in runtime.values())):
        raise ValueError(f"EX-42 adjust limits: runtime_cells must hold [low, high] (0 <= low <= high) for {list(RUNTIME_CELLS)}")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "cells": {name: (float(a), float(b)) for name, (a, b) in cells.items()},
            "command_cells": {name: (float(a), float(b)) for name, (a, b) in extra.items()},
            "runtime_cells": {name: (float(a), float(b)) for name, (a, b) in (runtime or {}).items()}}


def _plain(profile) -> dict | None:
    """A validated profile, or a recorded one in either shape, in the shape of the input file."""
    if profile is None:
        return None
    overlay = profile["turn_overlay"]
    if not isinstance(overlay, dict):                      # the validated tuple, or the list of a record written before
        overlay = {"fraction": overlay[0], "wz_abs": [overlay[1], overlay[2]]}
    return json.loads(json.dumps({"shares": dict(profile["shares"]),
                                  "ranges": {k: list(v) for k, v in profile["ranges"].items()},
                                  "turn_overlay": {"fraction": overlay["fraction"], "wz_abs": list(overlay["wz_abs"])}}))


def _inside(plan, stage_id, profile, label) -> None:
    limits = command_adjust_limits(plan, stage_id)
    for key, (low, high) in profile["ranges"].items():
        if low < limits["ranges"][key][0] - TOL or high > limits["ranges"][key][1] + TOL:
            raise ValueError(f"EX-42 {label} ranges.{key} leaves the approved limits {list(limits['ranges'][key])}")
    (fraction, low, high), (top, floor, ceiling) = profile["turn_overlay"], limits["turn_overlay"]
    if fraction > top + TOL or low < floor - TOL or high > ceiling + TOL:
        raise ValueError(f"EX-42 {label} turn_overlay leaves the approved limits: fraction {top}, wz {[floor, ceiling]}")
    for slot, share in profile["shares"].items():
        if not limits["shares"][slot][0] - TOL <= share <= limits["shares"][slot][1] + TOL:
            raise ValueError(f"EX-42 {label} shares.{slot} leaves the approved limits {list(limits['shares'][slot])}")


def _rewards(cell, limits, label) -> dict:
    if limits is None:
        raise ValueError(f"EX-42 {label} rewards: there is no reward adjust limits file")
    cell = complete_cells(cell)
    if (not isinstance(cell, dict) or set(cell) != set(REWARD_CELLS)
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in cell.values())):
        raise ValueError(f"EX-42 {label} rewards needs exactly {list(REWARD_CELLS)} as numbers")
    for name, value in cell.items():
        low, high = limits["cells"][name]
        if not low - TOL <= value <= high + TOL:
            raise ValueError(f"EX-42 {label} rewards.{name} leaves the approved limits {[low, high]}")
    if (not 0.0 < cell["slow_track_speed_min"] < cell["slow_track_speed_max"] or cell["slow_track_sigma"] <= 0.0
            or cell["feet_air_time_threshold"] <= 0.0):
        raise ValueError(f"EX-42 {label} rewards: slow_track needs 0 < speed_min < speed_max and sigma > 0, "
                         f"feet_air_time_threshold > 0")
    return {name: float(cell[name]) for name in REWARD_CELLS}


def _command_cell(name, value, limits, label) -> float:
    fence = ((limits or {}).get("command_cells") or {}).get(name)
    if fence is None:
        raise ValueError(f"EX-42 {label} {name}: the limits file has no approved limits for it")
    if type(value) not in (int, float) or not math.isfinite(value) or not fence[0] - TOL <= value <= fence[1] + TOL:
        raise ValueError(f"EX-42 {label} {name} must be a number inside the approved limits {list(fence)}")
    return float(value)


def _low_forward(value, limits, label) -> float:
    return _command_cell("low_forward_fraction", value, limits, label)


def stage_low_forward(plan, stage_id, limits=None) -> float | None:
    """The slow-forward share the stage's own plan row registers (`low_forward_fraction`): in force from the first
    update of the stage. None when the row has no cell (the source stage's 0.20 stays)."""
    row = next((s for s in plan.document["stages"] if s["id"] == stage_id), {})
    if "low_forward_fraction" not in row:
        return None
    return _low_forward(row["low_forward_fraction"], limits if limits is not None else reward_limits(), f"{stage_id} plan row")


# Reward cells a stage row may fence wider than the limits file (E1F, E2; 2026-11-16 lead 15:20, planner 15:17). The file keeps its bytes
# (the source E1 row pins its sha, ex42_stage_materialize reads the template's file against it), so the wider fence is the row's own
# `live_adjustment.extra_reward_limits.<cell>` (or `reward_fence.<cell>` on a stage without a live adjustment): it widens the file's pair or leaves it (a narrower row pair is ignored here; limits_from_plan refuses it), and only the cells in PLAN_WIDENABLE may differ.
PLAN_WIDENABLE = ("slow_progress", "slow_track_sigma", "slow_overspeed")


def row_reward_fence(row, base_cells, stage_id) -> dict:
    """{cell: (low, high)} the stage row widens beyond `base_cells` (the limits file's pairs); {} when it widens nothing.
    A row pair that does not contain the file's pair widens nothing (a row cannot narrow the fence)."""
    extra = {**(row.get("reward_fence") or {}), **((row.get("live_adjustment") or {}).get("extra_reward_limits") or {})}
    out = {}
    for name in PLAN_WIDENABLE:
        if name not in extra:
            continue
        pair = extra[name]
        if (not isinstance(pair, list) or len(pair) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in pair)
                or pair[0] > pair[1]):
            raise ValueError(f"EX-42 {stage_id} plan row extra_reward_limits.{name} must be [low, high]")
        low, high = base_cells[name]
        if pair[0] > low + TOL or pair[1] < high - TOL:
            continue            # a row pair inside the file's never widens: the file's fence stands (the live adjustment refuses such a row)
        if (float(pair[0]), float(pair[1])) != (low, high):
            out[name] = (float(pair[0]), float(pair[1]))
    return out


def _plan_fenced(limits, plan, stage_id):
    """E1F keeps ex42-reward-adjust-limits.yaml byte for byte (the source E1 row pins its sha and the materialization reads that file against it),
    so the fence of `low_side_fraction` is the stage row's own `live_adjustment.command_limits.low_side_fraction`, and the fence of the two
    reward cells in PLAN_WIDENABLE is the row's own `live_adjustment.extra_reward_limits` when that is wider than the file's. A fence the file
    itself carries wins for the command cell; a row without those cells leaves `limits` exactly as it is (None stays None)."""
    row = next((s for s in plan.document["stages"] if s["id"] == stage_id), {})
    fence = ((row.get("live_adjustment") or {}).get("command_limits") or {}).get("low_side_fraction")
    base = limits if limits is not None else reward_limits()
    widened = row_reward_fence(row, base["cells"], stage_id) if base is not None else {}
    if widened:
        base = {**base, "cells": {**base["cells"], **widened}}
    elif fence is None:
        return limits
    if fence is None:
        return base
    cells = dict((base or {}).get("command_cells") or {})
    if "low_side_fraction" in cells:
        return base
    if (not isinstance(fence, list) or len(fence) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in fence)
            or not 0 <= fence[0] <= fence[1] <= 1):
        raise ValueError(f"EX-42 {stage_id} plan row low_side_fraction limit must be [low, high] inside 0..1")
    return {**base, "command_cells": {**cells, "low_side_fraction": (float(fence[0]), float(fence[1]))}}


def stage_low_side(plan, stage_id, limits=None) -> float | None:
    """The slow-side share the stage's own plan row registers (`low_side_fraction`, 2026-11-16): in force from the first
    update of the stage. None when the row has no cell (the sampler stays as it was, bit for bit)."""
    row = next((s for s in plan.document["stages"] if s["id"] == stage_id), {})
    if "low_side_fraction" not in row:
        return None
    return _command_cell("low_side_fraction", row["low_side_fraction"],
                         _plan_fenced(limits if limits is not None else reward_limits(), plan, stage_id), f"{stage_id} plan row")


def _hold_pair(value, label, what="slow_hold_range_s"):
    if (not isinstance(value, (list, tuple)) or len(value) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)
            or not 0.0 < value[0] <= value[1] <= HOLD_MAX_S):
        raise ValueError(f"EX-42 {label} {what} must be [lo, hi] with 0 < lo <= hi <= {HOLD_MAX_S:g} seconds")
    return (float(value[0]), float(value[1]))


def _hold_fence(plan, stage_id):
    """The fence of `slow_hold_range_s` entries: the stage row's `slow_hold_fence_s`; None when the row has none."""
    row = next((s for s in plan.document["stages"] if s["id"] == stage_id), {})
    fence = row.get("slow_hold_fence_s")
    return None if fence is None else _hold_pair(fence, f"{stage_id} plan row", "slow_hold_fence_s")


def stage_slow_hold(plan, stage_id):
    """(registered, value): the plan row's `slow_hold_range_s`. registered is False for a row with no cell (null = no cell: the E1 row)."""
    row = next((s for s in plan.document["stages"] if s["id"] == stage_id), {})
    if row.get(HOLD_CELL) is None:
        return False, None
    return True, _hold_pair(row[HOLD_CELL], f"{stage_id} plan row")


def _hold_entry(value, fence, label):
    """An entry value: None (off) or a pair inside the fence. A row without a fence takes no entry."""
    if fence is None:
        raise ValueError(f"EX-42 {label} {HOLD_CELL}: the plan row has no slow_hold_fence_s")
    if value is None:
        return None
    pair = _hold_pair(value, label)
    if pair[0] < fence[0] - TOL or pair[1] > fence[1] + TOL:
        raise ValueError(f"EX-42 {label} {HOLD_CELL} leaves the approved fence {list(fence)}")
    return pair


def stage_rewards(plan, stage_id, limits=None) -> dict | None:
    """The reward cells the stage's own plan row registers (`rewards`): in force from the first update of the stage,
    inside the same limits as an adjustment. None when the row has no cell (the source stage's values stay)."""
    row = next((s for s in plan.document["stages"] if s["id"] == stage_id), {})
    cell = row.get("rewards")
    if cell is None:
        return None
    return _rewards(cell, _plan_fenced(limits if limits is not None else reward_limits(), plan, stage_id), f"{stage_id} plan row")


def stage_slow_track_heading(plan, stage_id) -> bool:
    """The stage's own plan row cell `slow_track_heading` (decisions.tsv 2026-11-14 00:28): heading envs inside the slow
    band count for ex42_slow_track. False when the row has no cell; anything but a bool is refused."""
    row = next((s for s in plan.document["stages"] if s["id"] == stage_id), {})
    value = row.get("slow_track_heading", False)
    if type(value) is not bool:
        raise ValueError(f"EX-42 {stage_id} plan row slow_track_heading must be true or false")
    return value


def resolve(plan, stage_id, document, boundary_index, limits=None) -> dict:
    """What is in force in the segment that starts at `boundary_index`: {commands, commands_entry, rewards,
    rewards_entry}. `commands` is None for a stage with no command profile, `rewards` None while neither the plan row
    nor an entry names them (the source stage's values stay); an entry number is None when the plan row holds."""
    base = stage_commands(plan, stage_id)
    limits = _plan_fenced(limits, plan, stage_id)
    out = {"commands": _plain(base), "commands_entry": None, "rewards": stage_rewards(plan, stage_id, limits),
           "rewards_entry": None, "low_forward_fraction": stage_low_forward(plan, stage_id, limits),
           "low_forward_fraction_entry": None, "low_side_fraction": stage_low_side(plan, stage_id, limits),
           "low_side_fraction_entry": None}
    registered, hold = stage_slow_hold(plan, stage_id)
    out.update(slow_hold_registered=registered, slow_hold_range_s=hold, slow_hold_range_s_entry=None)
    if document is None:
        return out
    if (not isinstance(document, dict) or set(document) != {"schema", "stage_id", "plan_sha256", "segments"}
            or document["schema"] != SCHEMA):
        raise ValueError(f"EX-42 segment adjustment needs exactly schema {SCHEMA}, stage_id, plan_sha256 and segments")
    if document["stage_id"] != stage_id or document["plan_sha256"] != plan.sha256:
        raise ValueError("EX-42 segment adjustment belongs to another stage or plan")
    segments = document["segments"]
    allowed = adjustable_boundaries(plan, stage_id)
    if (not isinstance(segments, dict) or not segments
            or any(not (isinstance(key, str) and key.isdigit() and int(key) >= 1) for key in segments)):
        raise ValueError(f"EX-42 {stage_id} segment adjustment may only name boundaries from 1 on")
    for key in sorted(segments, key=int):
        entry, label = segments[key], f"{stage_id} segment {key}"
        if int(key) > boundary_index:
            raise ValueError(f"EX-42 {stage_id} segment adjustment names boundary {key} before the run reached it")
        if (not isinstance(entry, dict) or not {"decided_at", "reason", "evidence"} <= set(entry)
                or not set(entry) <= {"decided_at", "reason", "evidence", "commands", "rewards", *COMMAND_CELLS, HOLD_CELL}
                or not {"commands", "rewards", *COMMAND_CELLS, HOLD_CELL} & set(entry)
                or any(not isinstance(entry[name], str) or not entry[name].strip() for name in ("decided_at", "reason", "evidence"))):
            raise ValueError(f"EX-42 {label} needs decided_at, reason, evidence (written text) and commands, rewards "
                             f"or low_forward_fraction or low_side_fraction or slow_hold_range_s")
        if "commands" in entry:
            if int(key) not in allowed:
                raise ValueError(f"EX-42 {stage_id} segment adjustment may only name boundaries {list(allowed)} for commands")
            profile = validate_commands(plan, entry["commands"], label)
            _inside(plan, stage_id, profile, label)
            out.update(commands=_plain(profile), commands_entry=int(key))
        if "rewards" in entry:
            out.update(rewards=_rewards(entry["rewards"], limits, label), rewards_entry=int(key))
        if "low_forward_fraction" in entry:
            if int(key) not in allowed:
                raise ValueError(f"EX-42 {stage_id} segment adjustment may only name boundaries {list(allowed)} for "
                                 f"low_forward_fraction")
            out.update(low_forward_fraction=_low_forward(entry["low_forward_fraction"], limits, label),
                       low_forward_fraction_entry=int(key))
        if "low_side_fraction" in entry:
            if int(key) not in allowed:
                raise ValueError(f"EX-42 {stage_id} segment adjustment may only name boundaries {list(allowed)} for "
                                 f"low_side_fraction")
            out.update(low_side_fraction=_command_cell("low_side_fraction", entry["low_side_fraction"], limits, label),
                       low_side_fraction_entry=int(key))
        if HOLD_CELL in entry:         # any boundary from 1 on, like the rewards: the fence is the row's own
            out.update(slow_hold_range_s=_hold_entry(entry[HOLD_CELL], _hold_fence(plan, stage_id), label),
                       slow_hold_range_s_entry=int(key), slow_hold_registered=True)
    return out


def read(path, plan, stage_id, boundary_index, limits=None) -> dict:
    """The record of the segment that starts at `boundary_index`."""
    raw = Path(path).read_bytes() if path else None
    document = json.loads(raw.decode("utf-8")) if path else None
    state = resolve(plan, stage_id, document, boundary_index, limits)
    told = lambda key: (document["segments"][str(key)] if key is not None else {})   # noqa: E731
    entry, reward_entry = told(state["commands_entry"]), told(state["rewards_entry"])
    low_entry, side_entry = told(state["low_forward_fraction_entry"]), told(state["low_side_fraction_entry"])
    adjusted = state["commands_entry"] is not None
    # only a run that uses the cell records it: the record of every other segment keeps the shape it had before
    low = {} if state["low_forward_fraction"] is None else {"low_forward_fraction": {
        "source": "plan" if state["low_forward_fraction_entry"] is None else "adjust_file",
        "entry": state["low_forward_fraction_entry"], "value": state["low_forward_fraction"],
        "decided_at": low_entry.get("decided_at"), "reason": low_entry.get("reason"),
        "evidence": low_entry.get("evidence"), "limits_sha256": limits["sha256"]}}
    if state["low_side_fraction"] is not None:          # same rule: only a run that uses the cell records it
        low["low_side_fraction"] = {
            "source": "plan" if state["low_side_fraction_entry"] is None else "adjust_file",
            "entry": state["low_side_fraction_entry"], "value": state["low_side_fraction"],
            "decided_at": side_entry.get("decided_at"), "reason": side_entry.get("reason"),
            "evidence": side_entry.get("evidence"), "limits_sha256": limits["sha256"]}
    if state["slow_hold_registered"]:        # same rule: only a run whose row has the cell records it
        hold_entry = told(state["slow_hold_range_s_entry"])
        low["slow_hold_range_s"] = {
            "source": "plan" if state["slow_hold_range_s_entry"] is None else "adjust_file",
            "entry": state["slow_hold_range_s_entry"],
            "value": None if state["slow_hold_range_s"] is None else list(state["slow_hold_range_s"]),
            "decided_at": hold_entry.get("decided_at"), "reason": hold_entry.get("reason"), "evidence": hold_entry.get("evidence")}
    # same rule: only a plan row that turns it on records it
    if stage_slow_track_heading(plan, stage_id):
        low["slow_track_heading"] = True
    return {**low, "format": RECEIPT, "stage_id": stage_id, "plan_sha256": plan.sha256, "boundary_index": int(boundary_index),
            "source": "adjust_file" if adjusted else "plan", "entry": state["commands_entry"],
            "file_sha256": hashlib.sha256(raw).hexdigest() if path else None,
            "decided_at": entry.get("decided_at"), "reason": entry.get("reason"), "evidence": entry.get("evidence"),
            "commands": state["commands"],
            "rewards": {"source": "plan" if state["rewards_entry"] is None else "adjust_file",
                        "entry": state["rewards_entry"], "values": state["rewards"],
                        "decided_at": reward_entry.get("decided_at"), "reason": reward_entry.get("reason"),
                        "evidence": reward_entry.get("evidence"),
                        "limits_sha256": limits["sha256"] if limits is not None else None},
            "_document": document}


def _as_of(document, k):
    """The file as the segment starting at boundary k saw it: its entries up to k (None = no entry yet)."""
    kept = {name: entry for name, entry in (document or {}).get("segments", {}).items() if int(name) <= k}
    return {**document, "segments": kept} if kept else None


def receipts(log_dir, stage_id) -> dict[int, dict]:
    out = {}
    for path in sorted(Path(log_dir).glob("segment_commands_b*.json")) if log_dir and Path(log_dir).is_dir() else []:
        body = json.loads(path.read_text(encoding="utf-8"))
        if body.get("format") == RECEIPT and body.get("stage_id") == stage_id and type(body.get("boundary_index")) is int:
            out[body["boundary_index"]] = body
    return out


def start_segment(plan_view, plan, stage_id, *, boundary_index, path, log_dir, write, limits_path=REWARD_LIMITS) -> dict:
    """Read, check against the earlier segments of the run folder, put the command profile and the reward weight cells
    on the plan view's stage, and (a real start past the first segment, rank 0) leave the record. Raises ValueError
    before anything is applied. The tracking widths go on the env config later (`apply_reward_params`)."""
    limits = reward_limits(limits_path)
    record = read(path, plan, stage_id, boundary_index, limits)
    document, earlier = record.pop("_document"), receipts(log_dir, stage_id)
    for k in range(1, boundary_index):       # what this start says segment k ran with must be what segment k recorded
        said = resolve(plan, stage_id, _as_of(document, k), k, limits)
        ran = earlier.get(k) or {"commands": resolve(plan, stage_id, None, k, limits)["commands"]}
        if (said["commands"] != _plain(ran.get("commands")) or said["rewards"] != (ran.get("rewards") or {}).get("values")
                or said["low_forward_fraction"] != (ran.get("low_forward_fraction") or {}).get("value")
                or said["low_side_fraction"] != (ran.get("low_side_fraction") or {}).get("value")
                or (None if said["slow_hold_range_s"] is None else list(said["slow_hold_range_s"]))
                != (ran.get("slow_hold_range_s") or {}).get("value")):
            raise ValueError(f"EX-42 {stage_id} segment adjustment differs from what segment {k} ran with")
    stage, commands, rewards = plan_view.stages[0], record["commands"], record["rewards"]["values"]
    if commands is not None:
        overlay = commands["turn_overlay"]
        stage = replace(stage, shares=dict(commands["shares"]),
                        ranges={k: (v[0], v[1]) for k, v in commands["ranges"].items()},
                        turn_overlay=(overlay["fraction"], overlay["wz_abs"][0], overlay["wz_abs"][1]))
    if rewards is not None:
        stage = replace(stage, rewards={**stage.rewards, **{name: rewards[name] for name in WEIGHT_CELLS}})
    if "low_forward_fraction" in record:
        stage = replace(stage, low_forward_fraction=record["low_forward_fraction"]["value"])
    if "low_side_fraction" in record:
        stage = replace(stage, low_side_fraction=record["low_side_fraction"]["value"])
    if "slow_hold_range_s" in record:
        held = record["slow_hold_range_s"]["value"]
        stage = replace(stage, slow_hold_range_s=None if held is None else (float(held[0]), float(held[1])))
    plan_view.stages = [stage]
    if write and boundary_index >= 1:
        target = Path(log_dir) / f"segment_commands_b{boundary_index}.json"
        text = json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True)
        try:
            with open(target, "x", encoding="utf-8", newline=chr(10)) as handle:
                handle.write(text)
        except FileExistsError:                # the same segment started again: it must be the same record
            if json.loads(target.read_text(encoding="utf-8")) != record:
                raise ValueError(f"EX-42 {target.name} already records another command profile for this segment") from None
    return record


def apply_reward_params(env_cfg, record, term_cfg_class=None) -> dict:
    """Before the env is built: the cells that live on the env config. Registers `ex42_slow_track` at weight 0 when
    the config does not have it yet (every E stage carries the term), then puts the segment's parameter cells and the
    slow_track weight on the config. {cell: {before, after}}; without reward cells nothing but the registration changes.
    `ex42_slow_progress` is registered the same way and follows the speed band of slow_track."""
    from foothold_s2.rewards import ex42_slow_overspeed, ex42_slow_progress, ex42_slow_track

    ex42_slow_track.register(env_cfg, term_cfg_class)
    ex42_slow_progress.register(env_cfg, term_cfg_class)
    ex42_slow_overspeed.register(env_cfg, term_cfg_class)
    values = ((record or {}).get("rewards") or {}).get("values")
    out = {}
    for cell, (term, param, default) in PARAM_CELLS.items():
        params = getattr(env_cfg.rewards, term).params
        before = float(params[param] if default is None else params.get(param, default))
        if values is not None:
            params[param] = float(values[cell])
        out[cell] = {"before": before, "after": float(params[param] if default is None else params.get(param, default))}
    for cell, term in ENV_WEIGHT_CELLS.items():
        target = getattr(env_cfg.rewards, term)
        before = float(target.weight)
        if values is not None:
            target.weight = float(values[cell])
        out[cell] = {"before": before, "after": float(target.weight)}
    band = getattr(env_cfg.rewards, "ex42_slow_track").params          # one band for both slow terms
    progress = getattr(env_cfg.rewards, "ex42_slow_progress").params
    progress["speed_min"], progress["speed_max"] = band["speed_min"], band["speed_max"]
    over = getattr(env_cfg.rewards, "ex42_slow_overspeed").params
    over["speed_min"], over["speed_max"] = band["speed_min"], band["speed_max"]
    progress["taper_from"] = min(max(progress.get("taper_from", band["speed_max"]), band["speed_min"]), band["speed_max"])
    if (record or {}).get("slow_track_heading"):       # the plan row includes heading envs (2026-11-14 00:28)
        params = getattr(env_cfg.rewards, "ex42_slow_track").params
        before = bool(params.get("include_heading", False))
        params["include_heading"] = True
        out["slow_track_heading"] = {"before": before, "after": True}
    return out


def reward_readback(env, record) -> dict:
    """After the env is built: the cells as the live reward manager carries them. An adjusted segment must show
    exactly what its entry asked for; ValueError otherwise, before any rollout."""
    manager = getattr(env, "unwrapped", env).reward_manager
    live = {}
    for cell, (term, param, default) in PARAM_CELLS.items():
        params = manager.get_term_cfg(term).params
        live[cell] = float(params[param] if default is None else params.get(param, default))
    for cell, term in {**WEIGHT_CELLS, **ENV_WEIGHT_CELLS}.items():
        try:
            live[cell] = float(manager.get_term_cfg(term).weight)
        except (KeyError, ValueError):
            if cell not in OPTIONAL_CELLS:
                raise
            live[cell] = OPTIONAL_CELLS[cell]      # the term is not on this env: it is off (an asked weight above 0 fails below)
    rewards = (record or {}).get("rewards") or {}
    asked = complete_cells(rewards.get("values"))
    if asked is not None and any(abs(live[name] - asked[name]) > TOL for name in REWARD_CELLS):
        raise ValueError(f"EX-42 segment rewards: the live reward manager carries {live}, the adjustment asked for {asked}")
    out = {"source": rewards.get("source", "plan"), "entry": rewards.get("entry"), "asked": asked, "live": live}
    if (record or {}).get("slow_track_heading"):       # outside `live`: the ten reward cells keep their shape
        carried = bool(manager.get_term_cfg("ex42_slow_track").params.get("include_heading", False))
        if not carried:
            raise ValueError("EX-42 segment rewards: the plan row includes heading envs in slow_track, the live term does not")
        out["slow_track_heading"] = carried
    return out


def write_reward_readback(env, record, run_dir) -> dict:
    """`reward_readback`, left in the run folder as segment_rewards_b<k>[_rank<r>].json from the second segment on
    (every rank reads its own env). A file that exists is left alone: the same segment was started again."""
    import os

    body = {"format": "ex42-segment-rewards/1", "stage_id": record["stage_id"], "plan_sha256": record["plan_sha256"],
            "boundary_index": record["boundary_index"], "limits_sha256": record["rewards"]["limits_sha256"],
            **reward_readback(env, record)}
    if record["boundary_index"] >= 1 and run_dir:
        ranks = int(os.environ.get("WORLD_SIZE", "1"))
        suffix = "" if ranks <= 1 else f"_rank{int(os.environ.get('RANK', '0'))}"
        target = Path(run_dir) / f"segment_rewards_b{record['boundary_index']}{suffix}.json"
        if not target.exists():
            target.write_text(json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return body
