import json
from pathlib import Path

import pytest

from foothold_s2.eval.ex41_w78_units_ops import (
    PROOF, compare, merge_if_complete, numeric_leaves, unit_argv,
)


def test_unit_argv_is_one_case_one_mode_but_keeps_required_map_contract(tmp_path):
    command = unit_argv(tmp_path / "model_750.pt", tmp_path / "out", *PROOF[0])
    assert command[command.index("--terrain-skill-v2-cases") + 1] == "stairs_side_left"
    assert command[command.index("--terrain-skill-v2-modes") + 1] == "eval_gt"
    assert command[command.index("--modes") + 1] == "eval_gt,probe_prop_only,eval_pred"
    assert command[command.index("--envs") + 1] == "64"
    assert command[command.index("--eval-seed") + 1] == "42"
    assert command[command.index("--device") + 1] == "cuda:1"
    assert "--headless" in command
    with pytest.raises(ValueError, match="unknown"):
        unit_argv(tmp_path / "model_750.pt", tmp_path / "out", "wrong", "stairs_side_left")


def _fixture(tmp_path: Path):
    rows = {}
    identity = {"envs": 64, "eval_seed": 42, "levels": [2, 5],
                "start_angles_deg": [0, 30, 60, 90], "dt_s": 0.02,
                "dr_off": ["physics_material"], "curriculum_off": ["terrain_levels"]}
    for mode, case in PROOF:
        row = {"by_terrain_kind": {"stairs": {"alive_at_end": 4,
                                             "movement_ratio_median": 0.75}},
               "per_env": [{"distance": 1.0}, {"distance": 2.0}],
               "raw_file": "full.npz", "raw_sha256": "f" * 64}
        unit_rows = {}
        for level in (2, 5):
            for angle in (0, 30, 60, 90):
                key = f"L{level}_a{angle:03d}_" + case
                rows.setdefault(mode, {})[key] = row
                unit_rows[key] = dict(row, raw_file="unit.npz", raw_sha256="u" * 64)
        out = tmp_path / mode / case
        out.mkdir(parents=True)
        (out / "terrain_skill_v2.json").write_text(json.dumps({
            "state": "done", "checkpoint_sha256": "a" * 64,
            "case_selection": [case], "mode_selection": [mode],
            "modes": {mode: unit_rows}, **identity,
        }), encoding="utf-8")
    full = tmp_path / "full.json"
    full.write_text(json.dumps({"checkpoint_sha256": "a" * 64, "modes": rows,
                                **identity}), encoding="utf-8")
    return full


def test_known_equal_and_changed_numeric_value(tmp_path):
    full = _fixture(tmp_path)
    assert compare(full, tmp_path)["state"] == "same"
    part_path = tmp_path / PROOF[0][0] / PROOF[0][1] / "terrain_skill_v2.json"
    part = json.loads(part_path.read_text(encoding="utf-8"))
    key = "L2_a000_" + PROOF[0][1]
    part["modes"][PROOF[0][0]][key]["by_terrain_kind"]["stairs"]["alive_at_end"] = 3
    part_path.write_text(json.dumps(part), encoding="utf-8")
    result = compare(full, tmp_path)
    assert result["state"] == "different"
    assert result["differences"] == [{"unit": "eval_gt/stairs_side_left", "row": key,
                                       "field": "/by_terrain_kind/stairs/alive_at_end",
                                       "old": 4, "new": 3}]


def test_missing_one_angle_is_rejected(tmp_path):
    full = _fixture(tmp_path)
    part_path = tmp_path / PROOF[0][0] / PROOF[0][1] / "terrain_skill_v2.json"
    part = json.loads(part_path.read_text(encoding="utf-8"))
    part["modes"][PROOF[0][0]].pop("L5_a090_stairs_side_left")
    part_path.write_text(json.dumps(part), encoding="utf-8")
    with pytest.raises(ValueError, match="coverage"):
        compare(full, tmp_path)


def test_numeric_leaves_excludes_raw_identity_but_not_metric():
    assert dict(numeric_leaves({"raw_file": "x", "raw_sha256": "y",
                                "metric": [True, 0, 1.5]})) == {
                                    "/metric/1": 0, "/metric/2": 1.5}


def test_merge_waits_for_all_thirty_units(tmp_path):
    checkpoint = tmp_path / "model_750.pt"
    checkpoint.write_bytes(b"known")
    result = merge_if_complete(tmp_path / "units", checkpoint, tmp_path / "units/terrain_skill_v2.json")
    assert result["state"] == "pending"
    assert len(result["missing"]) == 30
    assert "eval_gt/stairs_fwd" in result["missing"]
