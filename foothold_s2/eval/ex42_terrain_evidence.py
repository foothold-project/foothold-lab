"""Select EX-42 capture cells by terrain kind/level and check raw identity."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def tiles_from_assignment(column_names, levels, types):
    """Use applied terrain arrays, never an assumed environment ordinal."""
    if len(levels) != len(types):
        raise ValueError("terrain level/type arrays differ")
    return [{"env": index, "kind": column_names[int(col)], "level": int(level),
             "col": int(col)} for index, (level, col) in enumerate(zip(levels, types))]


def select_cell(tiles: list[dict], kind: str, level: int) -> dict:
    matches = [tile for tile in tiles if tile.get("kind") == kind and tile.get("level") == level]
    if not matches:
        return {"state": "unmeasured", "kind": kind, "level": level, "env_count": 0}
    return {"state": "selected", "kind": kind, "level": level,
            "env_count": len(matches), "tile": min(matches, key=lambda tile: tile["env"])}


def verify_raw_terrain(review_json: Path, raw_npz: Path, selection: dict) -> dict:
    """Require the video segment and NPZ to prove the same tile and assignment."""
    if selection.get("state") != "selected":
        raise ValueError("cannot verify a terrain without a measured tile")
    tile = selection["tile"]
    meta = json.loads(Path(review_json).read_text(encoding="utf-8-sig"))
    selected = meta.get("selected_environment") or {}
    chosen = (meta.get("task_selection") or {}).get("selected_tile") or {}
    expected = {key: tile[key] for key in ("env", "kind", "level", "col")}
    if (any(chosen.get(key) != value for key, value in expected.items())
            or selected.get("env_id") != tile["env"]
            or any(selected.get(key) != tile[key] for key in ("kind", "level", "col"))):
        raise ValueError("video selected terrain differs from applied tile")
    assignment = (meta.get("task_selection") or {}).get("fixed_assignment") or {}
    assignment_sha = assignment.get("assignment_sha256")
    if not isinstance(assignment_sha, str) or len(assignment_sha) != 64:
        raise ValueError("applied terrain assignment SHA missing")
    with np.load(raw_npz, allow_pickle=False) as raw:
        required = ("t", "seg", "terrain_kind", "terrain_level", "terrain_env",
                    "terrain_col", "terrain_assignment_sha256")
        if any(key not in raw for key in required) or len(raw["t"]) == 0:
            raise ValueError("raw terrain identity or ticks missing")
        count = len(raw["t"])
        for key, value in (("terrain_kind", tile["kind"]),
                           ("terrain_level", tile["level"]),
                           ("terrain_env", tile["env"]), ("terrain_col", tile["col"]),
                           ("terrain_assignment_sha256", assignment_sha)):
            if len(raw[key]) != count or not np.all(raw[key] == value):
                raise ValueError(f"raw {key} differs from video terrain")
        segments = meta.get("segments")
        if (not isinstance(segments, list) or not segments or len(raw["seg"]) != count
                or set(np.unique(raw["seg"]).tolist()) != set(range(len(segments)))):
            raise ValueError("raw segments differ from video segment list")
    return {"state": "PASS", "tile": expected, "assignment_sha256": assignment_sha,
            "raw_ticks": count, "segment_count": len(segments)}
