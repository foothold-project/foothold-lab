"""EX-42 segment adjustment (CURRICULUM-GATES E.2 E1 「구간 명령 조정」 and the reward cells). No Kit imports.

A resumed segment must carry the plan and approval SHA of the first one, so what changes at a boundary comes from a
file outside both (EX42_SEGMENT_ADJUST):

    {"schema": "ex42-segment-adjust/1", "stage_id": "E1", "plan_sha256": "<the run's plan>",
     "segments": {"3": {"decided_at": "...", "reason": "...", "evidence": "...",
                        "commands": {"shares": {...}, "ranges": {...}, "turn_overlay": {"fraction": f, "wz_abs": [a, b]}},
                        "rewards": {"track_lin_vel_std": s, "track_ang_vel_std": s, "feet_air_time": w, "foot_slip": w}}}}

An entry carries `commands`, `rewards` or both and holds from its boundary on, each kind until a later entry of the
same kind. An entry for a boundary the run has not reached is refused.

* commands: only a stage whose plan row has `command_adjust_limits`, only at a boundary before its level cap first
  rises (E1: 1 and 2), every value inside those limits.
* rewards: any stage, any boundary from 1 on, every value inside `curriculum/ex42-reward-adjust-limits.yaml` (outside
  the plan so that a run already started can use it; its SHA is recorded). The two weights go on the stage's reward
  table, the two tracking widths on the env config (`apply_reward_params`), and the live reward manager is read back
  (`reward_readback`).

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
WEIGHT_CELLS = {"feet_air_time": "ex41_feet_air_time", "foot_slip": "ex41_foot_slip"}       # stage reward key -> live term
STD_CELLS = {"track_lin_vel_std": "track_lin_vel", "track_ang_vel_std": "track_ang_vel"}    # cell -> env reward term
REWARD_CELLS = (*STD_CELLS, *WEIGHT_CELLS)


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
    number = lambda v: type(v) in (int, float) and math.isfinite(v)   # noqa: E731
    if (not isinstance(document, dict) or document.get("schema") != REWARD_LIMITS_SCHEMA or not isinstance(cells, dict)
            or set(cells) != set(REWARD_CELLS)
            or any(not isinstance(pair, list) or len(pair) != 2 or not all(number(v) for v in pair) or pair[0] > pair[1]
                   for pair in cells.values())):
        raise ValueError(f"EX-42 reward adjust limits need schema {REWARD_LIMITS_SCHEMA} and [low, high] for {list(REWARD_CELLS)}")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "cells": {name: (float(a), float(b)) for name, (a, b) in cells.items()}}


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
    if (not isinstance(cell, dict) or set(cell) != set(REWARD_CELLS)
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in cell.values())):
        raise ValueError(f"EX-42 {label} rewards needs exactly {list(REWARD_CELLS)} as numbers")
    for name, value in cell.items():
        low, high = limits["cells"][name]
        if not low - TOL <= value <= high + TOL:
            raise ValueError(f"EX-42 {label} rewards.{name} leaves the approved limits {[low, high]}")
    return {name: float(cell[name]) for name in REWARD_CELLS}


def resolve(plan, stage_id, document, boundary_index, limits=None) -> dict:
    """What is in force in the segment that starts at `boundary_index`: {commands, commands_entry, rewards,
    rewards_entry}. `commands` is None for a stage with no command profile, `rewards` None while no entry changed
    them (the plan values stay); an entry number is None when the plan row holds."""
    base = stage_commands(plan, stage_id)
    out = {"commands": _plain(base), "commands_entry": None, "rewards": None, "rewards_entry": None}
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
                or not set(entry) <= {"decided_at", "reason", "evidence", "commands", "rewards"}
                or not {"commands", "rewards"} & set(entry)
                or any(not isinstance(entry[name], str) or not entry[name].strip() for name in ("decided_at", "reason", "evidence"))):
            raise ValueError(f"EX-42 {label} needs decided_at, reason, evidence (written text) and commands or rewards")
        if "commands" in entry:
            if int(key) not in allowed:
                raise ValueError(f"EX-42 {stage_id} segment adjustment may only name boundaries {list(allowed)} for commands")
            profile = validate_commands(plan, entry["commands"], label)
            _inside(plan, stage_id, profile, label)
            out.update(commands=_plain(profile), commands_entry=int(key))
        if "rewards" in entry:
            out.update(rewards=_rewards(entry["rewards"], limits, label), rewards_entry=int(key))
    return out


def read(path, plan, stage_id, boundary_index, limits=None) -> dict:
    """The record of the segment that starts at `boundary_index`."""
    raw = Path(path).read_bytes() if path else None
    document = json.loads(raw.decode("utf-8")) if path else None
    state = resolve(plan, stage_id, document, boundary_index, limits)
    told = lambda key: (document["segments"][str(key)] if key is not None else {})   # noqa: E731
    entry, reward_entry = told(state["commands_entry"]), told(state["rewards_entry"])
    adjusted = state["commands_entry"] is not None
    return {"format": RECEIPT, "stage_id": stage_id, "plan_sha256": plan.sha256, "boundary_index": int(boundary_index),
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
    """Read, check against the earlier segments of the run folder, put the command profile and the two reward weights
    on the plan view's stage, and (a real start past the first segment, rank 0) leave the record. Raises ValueError
    before anything is applied. The tracking widths go on the env config later (`apply_reward_params`)."""
    limits = reward_limits(limits_path)
    record = read(path, plan, stage_id, boundary_index, limits)
    document, earlier = record.pop("_document"), receipts(log_dir, stage_id)
    for k in range(1, boundary_index):       # what this start says segment k ran with must be what segment k recorded
        said = resolve(plan, stage_id, _as_of(document, k), k, limits)
        ran = earlier.get(k) or {"commands": resolve(plan, stage_id, None, k)["commands"]}
        if said["commands"] != _plain(ran.get("commands")) or said["rewards"] != (ran.get("rewards") or {}).get("values"):
            raise ValueError(f"EX-42 {stage_id} segment adjustment differs from what segment {k} ran with")
    stage, commands, rewards = plan_view.stages[0], record["commands"], record["rewards"]["values"]
    if commands is not None:
        overlay = commands["turn_overlay"]
        stage = replace(stage, shares=dict(commands["shares"]),
                        ranges={k: (v[0], v[1]) for k, v in commands["ranges"].items()},
                        turn_overlay=(overlay["fraction"], overlay["wz_abs"][0], overlay["wz_abs"][1]))
    if rewards is not None:
        stage = replace(stage, rewards={**stage.rewards, **{name: rewards[name] for name in WEIGHT_CELLS}})
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


def apply_reward_params(env_cfg, record) -> dict:
    """Before the env is built: the segment's tracking widths on the env config. {cell: {before, after}}."""
    values = ((record or {}).get("rewards") or {}).get("values")
    out = {}
    for cell, term in STD_CELLS.items():
        params = getattr(env_cfg.rewards, term).params
        before = float(params["std"])
        if values is not None:
            params["std"] = float(values[cell])
        out[cell] = {"before": before, "after": float(params["std"])}
    return out


def reward_readback(env, record) -> dict:
    """After the env is built: the four cells as the live reward manager carries them. An adjusted segment must show
    exactly what its entry asked for; ValueError otherwise, before any rollout."""
    manager = getattr(env, "unwrapped", env).reward_manager
    live = {cell: float(manager.get_term_cfg(term).params["std"]) for cell, term in STD_CELLS.items()}
    live.update({cell: float(manager.get_term_cfg(term).weight) for cell, term in WEIGHT_CELLS.items()})
    rewards = (record or {}).get("rewards") or {}
    asked = rewards.get("values")
    if asked is not None and any(abs(live[name] - asked[name]) > TOL for name in REWARD_CELLS):
        raise ValueError(f"EX-42 segment rewards: the live reward manager carries {live}, the adjustment asked for {asked}")
    return {"source": rewards.get("source", "plan"), "entry": rewards.get("entry"), "asked": asked, "live": live}


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
