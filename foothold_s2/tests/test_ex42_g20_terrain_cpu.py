import json

import numpy as np
import pytest

from foothold_s2.eval.ex42_terrain_evidence import (
    resolve_video_request, select_cell, tiles_from_assignment, verify_raw_terrain,
)


def test_g20_selection_by_kind_level_including_flat():
    tiles = tiles_from_assignment(["stairs", "flat"], [0, 2, 2], [0, 0, 1])
    assert select_cell(tiles, "flat", 2)["tile"]["env"] == 2
    assert select_cell(tiles, "flat", 0) == {"state": "unmeasured", "kind": "flat",
                                                   "level": 0, "env_count": 0}
    request = {"id": "r1", "terrain_kind": "flat", "terrain_level": 2}
    ready = resolve_video_request(request, column_names=["stairs", "flat"],
        applied_levels=[0, 2, 2], applied_types=[0, 0, 1], assignment_sha256="a" * 64)
    assert (ready["state"], ready["env_id"], ready["col"]) == ("ready", 2, 1)
    request["terrain_level"] = 0
    assert resolve_video_request(request, column_names=["stairs", "flat"],
        applied_levels=[0, 2, 2], applied_types=[0, 0, 1],
        assignment_sha256="a" * 64)["measurement"] == "미측정"


def test_g20_real_sparse50_column_contract_includes_flat():
    from foothold_s2.eval.fixed_terrain import fixed_assignment
    from foothold_s2.terrains import columns

    names = columns.column_types(columns.FULL, columns.FULL_COLS)
    levels, types = fixed_assignment(64, 10, columns.FULL_COLS, level=0)
    chosen = select_cell(tiles_from_assignment(names, levels, types), "flat", 0)
    assert chosen["state"] == "selected"
    assert names[chosen["tile"]["col"]] == "flat"


def test_g20_video_and_raw_terrain_must_match(tmp_path):
    tile = {"env": 4, "kind": "flat", "level": 2, "col": 9}
    selection = {"state": "selected", "tile": tile}
    meta = {"selected_environment": {"env_id": 4, "kind": "flat", "level": 2, "col": 9},
            "task_selection": {"selected_tile": tile,
                               "fixed_assignment": {"assignment_sha256": "a" * 64}},
            "segments": [["walk", [0.5, 0, 0], 1.0], ["stop", [0, 0, 0], 1.0]]}
    review = tmp_path / "review.json"
    review.write_text(json.dumps(meta), encoding="utf-8")
    raw = tmp_path / "review_feet.npz"
    arrays = {"t": np.array([0.0, 0.1]), "seg": np.array([0, 1]),
              "terrain_kind": np.array(["flat", "flat"]),
              "terrain_level": np.array([2, 2]), "terrain_env": np.array([4, 4]),
              "terrain_col": np.array([9, 9]),
              "terrain_assignment_sha256": np.array(["a" * 64] * 2)}
    np.savez(raw, **arrays)
    assert verify_raw_terrain(review, raw, selection)["state"] == "PASS"
    np.savez(raw, **{**arrays, "terrain_kind": np.array(["flat", "stairs"])})
    with pytest.raises(ValueError, match="terrain_kind"):
        verify_raw_terrain(review, raw, selection)
    np.savez(raw, **{key: value for key, value in arrays.items() if key != "terrain_kind"})
    with pytest.raises(ValueError, match="identity"):
        verify_raw_terrain(review, raw, selection)
