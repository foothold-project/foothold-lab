"""Read boundary episode counts without promoting an unapproved cell definition."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

FORMAT = "foothold-ex42-learned-cells/1"
BANDS = [[0, 2], [3, 5], [6, 9]]
GROUPS = ["forward", "reverse", "side_left", "side_right", "turn_left", "turn_right", "stand", "flag"]
MODES = ["map_on_adaptive", "map_off"]


def read_boundary(checkpoint: Path, *, stage_id: str, plan_sha256: str, interval: int) -> dict:
    """SHA-check both ranks and expose counts; absent registration stays HOLD."""
    checkpoint = Path(checkpoint)
    match = re.fullmatch(r"model_(\d+)\.pt", checkpoint.name)
    if match is None or type(interval) is not int or interval < 1:
        raise ValueError("EX-42 learned_cells boundary identity invalid")
    iteration = int(match.group(1))
    directory = checkpoint.parent
    ranked = sorted(directory.glob(f"learned_cells_{iteration}_rank*.json"))
    single = directory / f"learned_cells_{iteration}.json"
    if single.is_file() and ranked:
        raise ValueError("EX-42 learned_cells single and ranked receipts mixed")
    paths = ranked or ([single] if single.is_file() else [])
    if not paths:
        return {"role": "judge", "judgement": "HOLD", "reason": "학습 종료 에피소드 원자료 없음",
                "source": "assigned_mode_cumulative", "receipts": []}
    seen = set()
    counts = {}
    receipts = []
    world_size = None
    window = None
    columns = None
    for path in paths:
        raw = path.read_bytes()
        row = json.loads(raw.decode("utf-8-sig"))
        checksum = row.pop("sha256", None)
        body_sha = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        expected_name = (f"learned_cells_{iteration}.json" if row.get("world_size") == 1 else
                         f"learned_cells_{iteration}_rank{row.get('rank')}.json")
        if (checksum != body_sha or row.get("format") != FORMAT or path.name != expected_name or
                row.get("stage_id") != stage_id or row.get("plan_sha256") != plan_sha256 or
                row.get("episodes_counted_once") is not True or
                row.get("axes") != {"level_bands": BANDS, "groups": GROUPS,
                                    "modes": MODES, "columns": row.get("axes", {}).get("columns")}):
            raise ValueError(f"EX-42 learned_cells identity or SHA differs: {path}")
        size, rank = row.get("world_size"), row.get("rank")
        if (type(size) is not int or size < 1 or type(rank) is not int or not 0 <= rank < size or
                rank in seen or (world_size is not None and world_size != size)):
            raise ValueError("EX-42 learned_cells rank coverage differs")
        seen.add(rank)
        world_size = size
        span = row.get("window")
        if (not isinstance(span, dict) or type(span.get("from_it")) is not int or
                span.get("to_it") != iteration or not 0 <= span["from_it"] < iteration or
                iteration - span["from_it"] > interval or (window is not None and window != span)):
            raise ValueError("EX-42 learned_cells boundary window differs")
        window = span
        axes = row["axes"]
        ncols = axes["columns"]
        if type(ncols) is not int or ncols < 1 or (columns is not None and columns != ncols):
            raise ValueError("EX-42 learned_cells column count differs")
        columns = ncols
        cells = row.get("cells")
        if not isinstance(cells, list) or type(row.get("total")) is not int or row["total"] < 0:
            raise ValueError("EX-42 learned_cells counts missing")
        local = set()
        subtotal = 0
        for cell in cells:
            if (not isinstance(cell, list) or len(cell) != 5 or type(cell[0]) is not int or
                    not 0 <= cell[0] < ncols or cell[1] not in (0, 3, 6) or
                    cell[2] not in GROUPS or cell[3] not in MODES or
                    type(cell[4]) is not int or cell[4] < 1):
                raise ValueError("EX-42 learned_cells cell invalid")
            key = tuple(cell[:4])
            if key in local:
                raise ValueError("EX-42 learned_cells duplicate cell")
            local.add(key)
            subtotal += cell[4]
            counts[key] = counts.get(key, 0) + cell[4]
        if subtotal != row["total"]:
            raise ValueError("EX-42 learned_cells total differs")
        receipts.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                         "rank": rank, "total": subtotal})
    if seen != set(range(world_size)):
        return {"role": "judge", "judgement": "HOLD", "reason": "학습 종료 에피소드 rank 결측",
                "source": "assigned_mode_cumulative", "receipts": receipts,
                "ranks_present": sorted(seen), "world_size": world_size}
    return {"role": "judge", "judgement": "HOLD", "reason": "등록 칸 기준 미승인",
            "source": "assigned_mode_cumulative", "receipts": receipts,
            "window": window, "world_size": world_size, "total": sum(counts.values()),
            "cells": [[*key, value] for key, value in sorted(counts.items())]}
