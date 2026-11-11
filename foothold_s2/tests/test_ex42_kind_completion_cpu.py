"""Known input checks for the E2 START arrival support window."""

import json

import numpy as np
import pytest

from foothold_s2.eval.ex42_kind_completion import read_start_kind_cell, score_last_support


def _trace():
    root_x = np.zeros((20, 64), dtype=np.float64)
    root_x[5:, :] = 7.0
    alive = np.ones((20, 64), dtype=bool)
    return {"root_x_local_m": root_x, "alive": alive, "dt": np.array(0.1)}


def test_arrival_requires_half_second_alive_after_reach():
    trace = _trace()
    row = score_last_support(trace, finish_x_m=7.0, settle_s=0.5)
    assert row["success_count"] == row["survival_count"] == 64
    trace["root_x_local_m"][:, 0] = 0
    trace["root_x_local_m"][17:, 1] = 7.0
    trace["root_x_local_m"][:17, 1] = 0
    trace["alive"][8:, 2] = False
    row = score_last_support(trace, finish_x_m=7.0, settle_s=0.5)
    assert row["success_count"] == 61
    assert row["survival_count"] == 63
    assert row["per_env"][0]["reason"] == "not_reached"
    assert row["per_env"][1]["reason"] == "settle_window_short"
    assert row["per_env"][2]["reason"] == "reset_before_settle"


def test_reset_and_missing_trace_do_not_silently_pass():
    trace = _trace()
    trace["alive"][5, 0] = False
    trace["alive"][6, 0] = True
    with pytest.raises(ValueError, match="resurrect"):
        score_last_support(trace, finish_x_m=7.0, settle_s=0.5)
    trace = _trace()
    trace["root_x_local_m"][0, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        score_last_support(trace, finish_x_m=7.0, settle_s=0.5)
    trace = _trace()
    del trace["root_x_local_m"]
    with pytest.raises((ValueError, KeyError)):
        score_last_support(trace, finish_x_m=7.0, settle_s=0.5)


def test_arrival_uses_mesh_origin_and_full_half_second_after_reach():
    trace = _trace()
    trace["root_x_local_m"][:, 0] = 6.5
    trace["root_x_local_m"][5:, 1] = 7.0
    trace["root_x_local_m"][6:, 1] = 6.0  # alive after arrival, even if it steps back
    trace["root_x_local_m"][:, 2] = 0.0
    trace["root_x_local_m"][14:, 2] = 7.0  # 5 following steps, t=1.9s is covered
    trace["root_x_local_m"][:, 3] = 0.0
    trace["root_x_local_m"][15:, 3] = 7.0  # only 4 following steps, still too short
    trace["alive"][19, 2] = False
    counted = score_last_support(trace, finish_x_m=7.0, settle_s=0.5)
    assert counted["per_env"][0]["reason"] == "not_reached"
    assert counted["per_env"][1]["success"] is True
    assert counted["per_env"][2]["reason"] == "reset_before_settle"
    assert counted["per_env"][3]["reason"] == "settle_window_short"


def _folder(tmp_path):
    from foothold_s2.eval.fixed_terrain import assignment_sha256

    folder = tmp_path / "kind"
    folder.mkdir()
    mesh = {"mesh_sha256": "a" * 64, "column_family": ["A"],
            "columns": ["stepping_stones_low"]}
    levels = np.zeros(64, dtype=np.int64)
    types = np.zeros(64, dtype=np.int64)
    assignment = assignment_sha256(levels, types)
    modes = {}
    arrays = {}
    for mode in ("eval_gt", "eval_pred", "probe_prop_only"):
        trace = _trace()
        path = folder / f"env_arrays_{mode}_fwd1.0.npz"
        np.savez_compressed(path, **trace,
                            terrain_level=levels, terrain_col=types,
                            kind=np.repeat("stepping_stones_low", 64),
                            dones=np.zeros((20, 64), dtype=bool),
                            assignment_sha256=np.array(assignment),
                            foot_contact=np.ones((20, 64, 4), dtype=bool),
                            foot_pos_local=np.zeros((20, 64, 4, 3)))
        modes[mode] = {"fwd1.0": {"policy_steps_x_envs": 1280,
                                   "gt_used": 1280 if mode == "eval_gt" else 0,
                                   "alive_envs_at_end": 64}}
        arrays[f"{mode}/fwd1.0"] = path.name
    doc = {"checkpoint_sha256": "b" * 64, "eval_seed": 42, "envs": 64,
           "steps": 20, "ex42_mesh": mesh,
           "fixed_terrain": {"rows": 10, "cols": 1, "num_envs": 64,
                             "fixed_level": 0, "family": "A", "kind": "stepping_stones_low",
                             "assignment_sha256": assignment},
           "terrain_tiles": [{"env": i, "column": 0, "level": 0,
                              "kind": "stepping_stones_low"} for i in range(64)],
           "modes": modes, "env_arrays": arrays}
    (folder / "map_modes.json").write_text(json.dumps(doc), encoding="utf-8")
    return folder, mesh


def _read(folder, mesh, mode="eval_gt"):
    return read_start_kind_cell(folder, mesh=mesh, checkpoint_sha256="b" * 64,
                                seed=42, family="A", kind="stepping_stones_low",
                                level=0, mode=mode, seconds=2.0, settle_s=0.5)


def test_kind_folder_recounts_all_modes_and_binds_assignment(tmp_path):
    folder, mesh = _folder(tmp_path)
    for mode in ("eval_gt", "eval_pred", "probe_prop_only"):
        row = _read(folder, mesh, mode)
        assert row["success_count"] == 64
        assert row["role"] == ("record_only" if mode == "probe_prop_only" else "judge")
        assert set(row["evidence"]) == {"map_modes", "arrays"}


def test_kind_folder_rejects_wrong_map_consumption_or_missing_trace(tmp_path):
    folder, mesh = _folder(tmp_path)
    source = folder / "map_modes.json"
    doc = json.loads(source.read_text(encoding="utf-8"))
    doc["modes"]["eval_pred"]["fwd1.0"]["gt_used"] = 1
    source.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="map input"):
        _read(folder, mesh, "eval_pred")
    doc["modes"]["eval_pred"]["fwd1.0"]["gt_used"] = 0
    source.write_text(json.dumps(doc), encoding="utf-8")
    (folder / "env_arrays_eval_pred_fwd1.0.npz").unlink()
    with pytest.raises((OSError, ValueError)):
        _read(folder, mesh, "eval_pred")
