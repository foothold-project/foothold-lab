"""Known-input proof that E2 flags use the named mesh supports and raw traces."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from foothold_s2.eval.ex42_flag_cells import contract, score_trace
from foothold_s2.eval.ex42_kind_flag_cells import read_kind_flag_cell
from foothold_s2.eval.fixed_terrain import assignment_sha256


ROOT = Path(__file__).resolve().parents[2]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path):
    plan = yaml.safe_load((ROOT / "foothold_s2/curriculum/ex42-prep.yaml").read_text(encoding="utf-8"))
    cells = contract(plan)
    folder = tmp_path / "kind_flag"
    folder.mkdir()
    flags = np.zeros((10, 1, 4, 2), dtype=np.float32)
    flags[..., 0] = np.arange(4, dtype=np.float32) + .5
    mesh_file = tmp_path / "mesh.npz"
    np.savez_compressed(mesh_file, flags=flags)
    mesh = {"mesh_npz": str(mesh_file), "mesh_sha256": "a" * 64,
            "column_family": ["A"], "columns": ["stepping_stones_low"]}
    levels = np.zeros(64, dtype=np.int64)
    types = np.zeros(64, dtype=np.int64)
    receipt = {"format": "foothold-ex42-flag-eval/1", "state": "done", "count": "flag_four",
               "kind_cell": {"family": "A", "kind": "stepping_stones_low", "level": 0},
               "envs": 64, "plan_sha256": "b" * 64, "checkpoint_sha256": "c" * 64,
               "mesh_sha256": mesh["mesh_sha256"], "seed": 42, "cases": {}}
    for mode in ("eval_gt", "eval_pred", "probe_prop_only"):
        case = f"flag_four_{mode}"
        trace_path = folder / f"{case}.npz"
        raw_path = folder / f"{case}.json"
        root = np.zeros((120, 64, 3), dtype=np.float32)
        root[:, :, 0] = np.minimum(np.arange(120) // 10, 3)[:, None] + .5
        trace = {"root_pos_w": root, "root_vel_w": np.zeros_like(root),
                 "alive": np.ones((120, 64), dtype=bool), "flags_w": flags[levels, types],
                 "dt": np.array(.1), "env_origins_w": np.zeros((64, 3)),
                 "terrain_levels": levels, "terrain_types": types}
        np.savez_compressed(trace_path, **trace)
        spec = cells["case_specs"][case]
        measured = score_trace(trace, spec, cells)
        raw = {"case_id": case, **spec, **measured, "trace_file": str(trace_path),
               "trace_sha256": _sha(trace_path), "fixed_terrain": {
                   "cols": 1, "family": "A", "kind": "stepping_stones_low",
                   "assignment_sha256": assignment_sha256(levels, types)}}
        raw_path.write_text(json.dumps(raw), encoding="utf-8")
        receipt["cases"][case] = {"trace_file": str(trace_path), "trace_sha256": _sha(trace_path),
                                  "raw_file": str(raw_path), "raw_sha256": _sha(raw_path),
                                  **{key: measured[key] for key in
                                     ("envs", "valid_count", "success_count", "survival_count")}}
    (folder / "flag_cells.json").write_text(json.dumps(receipt), encoding="utf-8")
    return folder, plan, mesh


def _read(folder, plan, mesh):
    return read_kind_flag_cell(folder, plan=plan, plan_sha256="b" * 64,
                               mesh=mesh, checkpoint_sha256="c" * 64, seed=42,
                               family="A", kind="stepping_stones_low", level=0)


def test_named_kind_four_flags_three_modes_recount_from_pinned_mesh(tmp_path):
    folder, plan, mesh = _fixture(tmp_path)
    result = _read(folder, plan, mesh)
    assert set(result) == {"eval_gt", "eval_pred", "probe_prop_only"}
    assert all(row["success_count"] == 64 and row["survival_count"] == 64 for row in result.values())
    assert result["probe_prop_only"]["role"] == "record_only"


def test_kind_flag_source_change_and_wrong_support_fail(tmp_path):
    folder, plan, mesh = _fixture(tmp_path)
    path = folder / "flag_four_eval_gt.npz"
    with np.load(path, allow_pickle=False) as archive:
        data = {key: archive[key] for key in archive.files}
    data["flags_w"] = data["flags_w"].copy()
    data["flags_w"][:, 0, 0] += .2
    np.savez_compressed(path, **data)
    receipt_path = folder / "flag_cells.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["cases"]["flag_four_eval_gt"]["trace_sha256"] = _sha(path)
    raw_path = folder / "flag_four_eval_gt.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    raw["trace_sha256"] = _sha(path)
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    receipt["cases"]["flag_four_eval_gt"]["raw_sha256"] = _sha(raw_path)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="coordinates"):
        _read(folder, plan, mesh)
