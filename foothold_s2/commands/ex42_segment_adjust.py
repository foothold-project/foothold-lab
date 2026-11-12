"""EX-42 segment command adjustment (CURRICULUM-GATES E.2 E1 「구간 명령 조정」). No Kit imports.

A stage whose plan row carries a `commands` profile may change that profile at a boundary that comes before its level
cap first rises (E1: boundaries 1 and 2 = updates 250 and 500). The change comes from a file outside the plan and the
approval file (EX42_SEGMENT_ADJUST), because a resumed segment must carry the plan and approval SHA of the first one:

    {"schema": "ex42-segment-adjust/1", "stage_id": "E1", "plan_sha256": "<the run's plan>",
     "segments": {"1": {"decided_at": "...", "reason": "...", "evidence": "...",
                        "commands": {"shares": {...}, "ranges": {...}, "turn_overlay": {...}}}}}

`segments[k]` holds from boundary k on; the segments where the cap rises keep the last entry. An entry for a boundary
the run has not reached is refused. Every value stays inside the row's `command_adjust_limits` (the lines the plan
fixed before the run started; a stage without that cell takes no adjustment). Each started segment leaves
`segment_commands_b<k>.json` in the run folder; a later start must reproduce what the earlier segments recorded.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

from foothold_s2.commands.ex42_shares import command_adjust_limits, stage_commands, validate_commands

SCHEMA = "ex42-segment-adjust/1"
RECEIPT = "ex42-segment-commands/1"
TOL = 1e-9


def adjustable_boundaries(plan, stage_id) -> tuple[int, ...]:
    """The boundaries where the profile may change: after the first segment, before the level cap first rises."""
    row = next((s for s in plan.document["stages"] if s["id"] == stage_id), {})
    first = (row.get("terrain", {}).get("continuous_level_cap") or {}).get("first_raise_boundary", 1)
    return tuple(range(1, first)) if row.get("command_adjust_limits") is not None and type(first) is int else ()


def _plain(profile) -> dict:
    return {"shares": dict(profile["shares"]), "ranges": {k: list(v) for k, v in profile["ranges"].items()},
            "turn_overlay": list(profile["turn_overlay"])}


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


def resolve(plan, stage_id, document, boundary_index):
    """(profile in force in the segment that starts at `boundary_index`, the entry it came from or None = plan row)."""
    base = stage_commands(plan, stage_id)
    if document is None:
        return _plain(base), None
    allowed = {str(k) for k in adjustable_boundaries(plan, stage_id)}
    if (not isinstance(document, dict) or set(document) != {"schema", "stage_id", "plan_sha256", "segments"}
            or document["schema"] != SCHEMA):
        raise ValueError(f"EX-42 segment adjustment needs exactly schema {SCHEMA}, stage_id, plan_sha256 and segments")
    if document["stage_id"] != stage_id or document["plan_sha256"] != plan.sha256:
        raise ValueError("EX-42 segment adjustment belongs to another stage or plan")
    segments = document["segments"]
    if not isinstance(segments, dict) or not segments or not set(segments) <= allowed:
        raise ValueError(f"EX-42 {stage_id} segment adjustment may only name boundaries {sorted(allowed)}")
    profiles = {}
    for key, entry in segments.items():
        if int(key) > boundary_index:
            raise ValueError(f"EX-42 {stage_id} segment adjustment names boundary {key} before the run reached it")
        if (not isinstance(entry, dict) or set(entry) != {"decided_at", "reason", "evidence", "commands"}
                or any(not isinstance(entry[name], str) or not entry[name].strip() for name in ("decided_at", "reason", "evidence"))):
            raise ValueError(f"EX-42 {stage_id} segment {key} needs decided_at, reason, evidence (written text) and commands")
        profile = validate_commands(plan, entry["commands"], f"{stage_id} segment {key}")
        _inside(plan, stage_id, profile, f"{stage_id} segment {key}")
        profiles[int(key)] = profile
    held = max(profiles)
    return _plain(profiles[held]), held


def read(path, plan, stage_id, boundary_index) -> dict | None:
    """The command record of the segment that starts at `boundary_index`; None for a stage with no command profile."""
    if stage_commands(plan, stage_id) is None:
        if path:
            raise ValueError(f"EX-42 {stage_id} has no command profile to adjust")
        return None
    raw = Path(path).read_bytes() if path else None
    document = json.loads(raw.decode("utf-8")) if path else None
    commands, key = resolve(plan, stage_id, document, boundary_index)
    entry = document["segments"][str(key)] if key is not None else {}
    return {"format": RECEIPT, "stage_id": stage_id, "plan_sha256": plan.sha256, "boundary_index": int(boundary_index),
            "source": "plan" if key is None else "adjust_file", "entry": key,
            "file_sha256": hashlib.sha256(raw).hexdigest() if path else None,
            "decided_at": entry.get("decided_at"), "reason": entry.get("reason"), "evidence": entry.get("evidence"),
            "commands": json.loads(json.dumps(commands)), "_document": document}


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


def start_segment(plan_view, plan, stage_id, *, boundary_index, path, log_dir, write) -> dict | None:
    """Read, check against the earlier segments of the run folder, put the profile on the plan view's stage, and
    (a real start past the first segment, rank 0) leave the receipt. Raises ValueError before anything is applied."""
    record = read(path, plan, stage_id, boundary_index)
    if record is None:
        return None
    document, earlier = record.pop("_document"), receipts(log_dir, stage_id)
    for k in range(1, boundary_index):       # what this start says segment k ran with must be what segment k recorded
        said = resolve(plan, stage_id, _as_of(document, k), k)[0]
        ran = earlier[k]["commands"] if k in earlier else resolve(plan, stage_id, None, k)[0]
        if said != ran:
            raise ValueError(f"EX-42 {stage_id} segment adjustment differs from what segment {k} ran with")
    stage, commands = plan_view.stages[0], record["commands"]
    plan_view.stages = [replace(stage, shares=dict(commands["shares"]),
                                ranges={k: (v[0], v[1]) for k, v in commands["ranges"].items()},
                                turn_overlay=tuple(commands["turn_overlay"]))]
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
