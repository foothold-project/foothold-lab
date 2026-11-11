"""Known-input checks for E2's episode-count evidence reader."""
import hashlib
import json

import pytest

from foothold_s2.ex42_learned_cells_evidence import judge_two_boundaries, read_boundary


def _write_boundary(folder, iteration, count):
    body = {
        "format": "foothold-ex42-learned-cells/1", "stage_id": "E2",
        "plan_sha256": "a" * 64,
        "window": {"from_it": iteration - 250, "to_it": iteration},
        "rank": 0, "world_size": 1,
        "axes": {"level_bands": [[0, 2], [3, 5], [6, 9]],
                 "groups": ["forward", "reverse", "side_left", "side_right",
                            "turn_left", "turn_right", "stand", "flag"],
                 "modes": ["map_on_adaptive", "map_off"], "columns": 1},
        "columns": [{"family": "A", "kind": "stepping_stones_low"}],
        "cells": [[0, 0, "forward", "map_on_adaptive", count]],
        "total": count, "episodes_counted_once": True,
    }
    body["sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    path = folder / f"learned_cells_{iteration}.json"
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return path


def test_missing_previous_boundary_is_hold(tmp_path):
    checkpoint = tmp_path / "model_500.pt"
    _write_boundary(tmp_path, 500, 32)
    result = judge_two_boundaries(checkpoint, stage_id="E2", plan={}, plan_sha256="a" * 64,
                                  interval=250, min_episodes=32, previous_kind_pass=True)
    assert result["judgement"] == "HOLD"
    assert "두 경계" in result["reason"]


def test_boundary_count_is_sha_checked(tmp_path):
    checkpoint = tmp_path / "model_250.pt"
    path = _write_boundary(tmp_path, 250, 33)
    result = read_boundary(checkpoint, stage_id="E2", plan_sha256="a" * 64, interval=250)
    assert result["total"] == 33
    row = json.loads(path.read_text(encoding="utf-8"))
    row["cells"][0][-1] = 34
    path.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA"):
        read_boundary(checkpoint, stage_id="E2", plan_sha256="a" * 64, interval=250)
