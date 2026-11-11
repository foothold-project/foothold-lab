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


def test_e3_registered_kind_requires_two_real_boundaries(tmp_path):
    from foothold_s2.ex42_exposure_receipt import build_receipt
    (tmp_path / "params").mkdir()
    (tmp_path / "params" / "agent.yaml").write_text("perception:\n  p_map_off: 0\n")
    plan = {"stages": [
        {"id": "E0", "terrain": {"kind_task": {"continuous": ["flat"]}}},
        {"id": "E3", "terrain": {"exposure_at_E3": {
            "default": {"exposure": 0, "level_cap": 0},
            "positive": [{"family": "B", "kind": "rough", "exposure": 1, "level_cap": 0}]}}}]}
    for iteration in (250, 500):
        path = _write_boundary(tmp_path, iteration, 32)
        row = json.loads(path.read_text())
        row["stage_id"] = "E3"
        row["columns"] = [{"family": "B", "kind": "rough"}]
        row["cells"] = [[0, 0, "forward", "map_on_adaptive", 32],
                        [0, 0, "flag", "map_on_adaptive", 32]]
        row["total"] = 64
        row.pop("sha256")
        row["sha256"] = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        path.write_text(json.dumps(row, ensure_ascii=False))
    checkpoint = tmp_path / "model_500.pt"
    missing = judge_two_boundaries(
        checkpoint, stage_id="E3", plan=plan, plan_sha256="a" * 64,
        interval=250, min_episodes=32, registered_kind_passes={('B', 'rough'): True})
    assert missing["judgement"] == "HOLD" and "노출" in missing["reason"]
    exposure = build_receipt({"mesh_sha256": "b" * 64, "columns": 1,
                              "families": ["B"], "exposure": [1.0], "level_caps": [0],
                              "shares": [None], "low_floor": None,
                              "k_ladder": {"boundary_index": 0, "moves": []},
                              "column_table": [{"family": "B", "kind": "rough"}]},
                             stage_id="E3", plan_sha256="a" * 64,
                             iteration=500, kind="boundary",
                             live={"envs": 1, "per_level": [1], "columns_used": [0],
                                   "per_column_level": {"0:0": 1}, "levels_max": 0})
    exposure["ladder_outcomes"] = []
    exposure["sha256"] = hashlib.sha256(json.dumps({k: v for k, v in exposure.items() if k != "sha256"},
                                                 sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    receipt = tmp_path / "exposure_receipt_500.json"
    receipt.write_text(json.dumps(exposure, ensure_ascii=False))
    result = judge_two_boundaries(
        checkpoint, stage_id="E3", plan=plan, plan_sha256="a" * 64,
        interval=250, min_episodes=32, registered_kind_passes={('B', 'rough'): True})
    assert result["judgement"] == "PASS"
    assert result["registered_count"] == 2
    exposure.pop("ladder_outcomes")
    exposure["sha256"] = hashlib.sha256(json.dumps({k: v for k, v in exposure.items() if k != "sha256"},
                                                 sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    receipt.write_text(json.dumps(exposure, ensure_ascii=False))
    with pytest.raises(ValueError, match="identity"):
        judge_two_boundaries(checkpoint, stage_id="E3", plan=plan, plan_sha256="a" * 64,
                             interval=250, min_episodes=32,
                             registered_kind_passes={('B', 'rough'): True})
    exposure["ladder_outcomes"] = []
    exposure["live"]["per_column_level"] = {"0:1": 1}
    exposure["live"]["per_level"] = [0, 1]
    exposure["live"]["levels_max"] = 1
    exposure["sha256"] = hashlib.sha256(json.dumps({k: v for k, v in exposure.items() if k != "sha256"},
                                                 sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    receipt.write_text(json.dumps(exposure, ensure_ascii=False))
    with pytest.raises(ValueError, match="outside approved exposure"):
        judge_two_boundaries(checkpoint, stage_id="E3", plan=plan, plan_sha256="a" * 64,
                             interval=250, min_episodes=32,
                             registered_kind_passes={('B', 'rough'): True})
    exposure["live"]["per_column_level"] = {"0:0": 1}
    exposure["live"]["per_level"] = [1]
    exposure["live"]["levels_max"] = 0
    exposure["sha256"] = hashlib.sha256(json.dumps({k: v for k, v in exposure.items() if k != "sha256"},
                                                 sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    receipt.write_text(json.dumps(exposure, ensure_ascii=False))
    pending = judge_two_boundaries(
        checkpoint, stage_id="E3", plan=plan, plan_sha256="a" * 64,
        interval=250, min_episodes=65, registered_kind_passes={('B', 'rough'): True})
    assert pending["judgement"] == "HOLD" and len(pending["pending"]) == 2
    exposure["column_rows"][0]["exposure"] = 0.0
    exposure["column_rows"][0]["open"] = False
    exposure["opened_kinds"] = {}
    exposure["sha256"] = hashlib.sha256(json.dumps({k: v for k, v in exposure.items() if k != "sha256"},
                                                     sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    receipt.write_text(json.dumps(exposure, ensure_ascii=False))
    with pytest.raises(ValueError, match="recomputed exposure"):
        judge_two_boundaries(checkpoint, stage_id="E3", plan=plan, plan_sha256="a" * 64,
                             interval=250, min_episodes=32,
                             registered_kind_passes={('B', 'rough'): True})


def test_e2_missing_raw_and_below_threshold_cannot_pass(tmp_path):
    checkpoint = tmp_path / "model_500.pt"
    raw_missing = read_boundary(checkpoint, stage_id="E2", plan_sha256="a" * 64,
                                interval=250)
    assert raw_missing["judgement"] == "HOLD"
    assert raw_missing["receipts"] == []
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
