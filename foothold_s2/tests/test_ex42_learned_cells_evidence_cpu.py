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


def test_e2_missing_raw_and_below_threshold_cannot_pass(tmp_path):
    checkpoint = tmp_path / "model_500.pt"
    missing = judge_two_boundaries(checkpoint, stage_id="E2", plan={}, plan_sha256="a" * 64,
                                   interval=250, min_episodes=32, previous_kind_pass=True)
    assert missing["judgement"] == "HOLD" and "원자료" in missing["reason"]
    (tmp_path / "params").mkdir()
    (tmp_path / "params" / "agent.yaml").write_text("perception:\n  p_map_off: 0\n")
    plan = {"stages": [
        {"id": "E0", "terrain": {"kind_task": {"continuous": ["flat"]}}},
        {"id": "E2", "terrain": {"exposure_at_E2": {
            "default": {"exposure": 0, "level_cap": 0},
            "positive": [{"family": "A", "kind": "stepping_stones_low",
                          "exposure": 1, "level_cap": 0}]}}}]}
    for iteration in (250, 500):
        path = _write_boundary(tmp_path, iteration, 15)
        row = json.loads(path.read_text())
        row["cells"] = [[0, 0, "forward", "map_on_adaptive", 15],
                        [0, 0, "flag", "map_on_adaptive", 15]]
        row["total"] = 30
        row.pop("sha256")
        row["sha256"] = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        path.write_text(json.dumps(row, ensure_ascii=False))
    short = judge_two_boundaries(checkpoint, stage_id="E2", plan=plan, plan_sha256="a" * 64,
                                 interval=250, min_episodes=32, previous_kind_pass=True)
    assert short["judgement"] == "HOLD"
    assert {row[3] for row in short["pending"]} == {"forward", "flag"}
    assert {row[-1] for row in short["pending"]} == {30}
