"""EX-42 M: fixed-level map-off survival cells from per-env raw records (CPU only, fail closed).

The CG E.1 M row judges the off survival against the GT survival at the three FIXED levels L3 / L6 / L9. This module turns
the per-env raw records of one saved checkpoint into `map_off_cells.json` and re-reads that file to recount it. A result of
the general map64 run at an arbitrary level is never renamed to a fixed level here: the caller names the level of each
record list, and the file keeps stage, boundary iteration, mode names and the checkpoint / plan / mesh SHA-256.

raw[level][mode] is a list of per-env dicts {"env": int, "alive": bool, ...}, mode in `MODES`. Exactly 64 distinct envs
0..63 per list, `alive` a real bool, every other number finite; anything else raises ValueError (no row, no cell).
The counts in the file are recomputed from `raw` on every read: the file's own `levels` numbers are never trusted.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

FORMAT = "foothold-ex42-mapoff-cells/1"
LEVELS = ("L3", "L6", "L9")
MODES = ("eval_gt", "map_off")
ENVS = 64
SHA = re.compile(r"[0-9a-f]{64}")
FILE = "map_off_cells.json"


def _alive_list(records, where: str) -> list:
    if not isinstance(records, list) or len(records) != ENVS:
        raise ValueError(f"{where}: needs exactly {ENVS} env records")
    alive = [None] * ENVS
    for row in records:
        if not isinstance(row, dict) or type(row.get("env")) is not int or not 0 <= row["env"] < ENVS:
            raise ValueError(f"{where}: env id missing or outside 0..{ENVS - 1}")
        if alive[row["env"]] is not None:
            raise ValueError(f"{where}: env {row['env']} is duplicated")
        if type(row.get("alive")) is not bool:
            raise ValueError(f"{where}: env {row['env']} alive is not a bool")
        for key, value in row.items():
            if type(value) in (int, float) and not math.isfinite(value):
                raise ValueError(f"{where}: env {row['env']} {key} is not finite")
        alive[row["env"]] = row["alive"]
    return alive


def build_cells(raw: dict, *, checkpoint_sha256: str, plan_sha256: str, mesh_sha256: str, stage_id: str,
                boundary_iteration: int) -> dict:
    """The cells document. Raises ValueError when a level, mode, env or identity is missing or wrong."""
    for name, value in (("checkpoint_sha256", checkpoint_sha256), ("plan_sha256", plan_sha256),
                        ("mesh_sha256", mesh_sha256)):
        if not isinstance(value, str) or not SHA.fullmatch(value):
            raise ValueError(f"{name} is not a SHA-256")
    if not isinstance(stage_id, str) or not stage_id or type(boundary_iteration) is not int or boundary_iteration <= 0:
        raise ValueError("stage id or boundary iteration invalid")
    if not isinstance(raw, dict) or set(raw) != set(LEVELS):
        raise ValueError(f"map-off raw must name exactly the fixed levels {LEVELS}")
    levels, stored = {}, {}
    for level in LEVELS:
        if not isinstance(raw[level], dict) or set(raw[level]) != set(MODES):
            raise ValueError(f"{level}: needs exactly the modes {MODES}")
        lists = {mode: _alive_list(raw[level][mode], f"{level}/{mode}") for mode in MODES}
        stored[level] = lists
        levels[level] = {"eval_gt_alive": sum(lists["eval_gt"]), "map_off_alive": sum(lists["map_off"])}
    return {"format": FORMAT, "checkpoint_sha256": checkpoint_sha256, "plan_sha256": plan_sha256,
            "mesh_sha256": mesh_sha256, "stage_id": stage_id, "boundary_iteration": boundary_iteration,
            "envs": ENVS, "levels": levels, "raw": stored}


def write_cells(folder, cells: dict) -> Path:
    path = Path(folder) / "map_off_cells"
    path.mkdir(parents=True, exist_ok=True)
    out = path / FILE
    with open(out, "x", encoding="utf-8") as handle:      # one file per boundary evaluation, never overwritten
        json.dump(cells, handle, ensure_ascii=False, sort_keys=True)
    return out


def recount(row: dict) -> dict:
    """The per-level counts recomputed from `raw`; ValueError when the file's own counts or shape differ."""
    if not isinstance(row, dict) or row.get("format") != FORMAT or row.get("envs") != ENVS:
        raise ValueError("map-off cells format or env count differ")
    raw = row.get("raw")
    if not isinstance(raw, dict) or set(raw) != set(LEVELS):
        raise ValueError("map-off cells raw levels differ")
    counts = {}
    for level in LEVELS:
        lists = raw[level]
        if not isinstance(lists, dict) or set(lists) != set(MODES):
            raise ValueError(f"{level}: modes differ")
        for mode in MODES:
            if (not isinstance(lists[mode], list) or len(lists[mode]) != ENVS
                    or any(type(x) is not bool for x in lists[mode])):
                raise ValueError(f"{level}/{mode}: raw is not {ENVS} bools")
        counts[level] = {"eval_gt_alive": sum(lists["eval_gt"]), "map_off_alive": sum(lists["map_off"])}
    if row.get("levels") != counts:
        raise ValueError("map-off cells counts differ from their raw records")
    return counts


def read_cells(path, *, checkpoint_sha256: str, plan_sha256: str | None = None, mesh_sha256: str | None = None,
               stage_id: str | None = None) -> dict | None:
    """None when the file is absent (the caller reads that as HOLD, never as a pass). ValueError when it is not for this
    checkpoint (or plan / mesh / stage when given) or when its counts differ from its raw records."""
    path = Path(path)
    if not path.is_file():
        return None
    row = json.loads(path.read_text(encoding="utf-8-sig"))
    recount(row)
    if row.get("checkpoint_sha256") != checkpoint_sha256:
        raise ValueError("map-off cells belong to another saved checkpoint")
    for key, want in (("plan_sha256", plan_sha256), ("mesh_sha256", mesh_sha256), ("stage_id", stage_id)):
        if want is not None and row.get(key) != want:
            raise ValueError(f"map-off cells {key} differs")
    return row
