"""E0 exposure: exposure-0 columns get no env, levels stop at the cap; plan values only."""
from __future__ import annotations

import ast
import pathlib
import types

import numpy as np
import pytest
import torch

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as te
from foothold_s2.terrains import ex42_exposure as ex
from foothold_s2.terrains import ex42_column_reset as cr

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2" / "curriculum" / "ex42-prep.yaml"
REAL = pathlib.Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_ABCDE_b613")
IMPORTER = pathlib.Path("/home/jay/mai/projects/IsaacLab/source/isaaclab/isaaclab/terrains/terrain_importer.py")
needs_real = pytest.mark.skipif(not (REAL.is_dir() and IMPORTER.is_file()), reason="real mesh / Isaac source missing")


def _stage_terrain():
    plan = EX42Plan.load(PLAN)
    return plan, te._e0_stage(plan)["terrain"]


def _installed_update():
    """TerrainImporter.update_env_origins exactly as installed, compiled on its own."""
    tree = ast.parse(IMPORTER.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "update_env_origins")
    fn.decorator_list = []
    mod = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(mod)
    ns = {"torch": torch}
    exec(compile(mod, str(IMPORTER), "exec"), ns)
    return ns["update_env_origins"]


def _terrain(origins, num_envs=64):
    rows, cols = origins.shape[:2]
    t = types.SimpleNamespace(
        terrain_origins=torch.as_tensor(origins, dtype=torch.float32), max_terrain_level=rows,
        terrain_levels=torch.randint(0, rows, (num_envs,)),
        terrain_types=torch.arange(num_envs) % cols, env_origins=torch.zeros(num_envs, 3))
    t.update_env_origins = types.MethodType(_installed_update(), t)
    return t


@needs_real
def test_plan_values_give_positive_exposure_only_on_the_continuous_columns_of_a():
    data = np.load(REAL / "terrain_mesh.npz", allow_pickle=False)
    fam = [str(v) for v in data["column_family"]]
    table = cr.build_column_table(fam)
    plan, terrain = _stage_terrain()
    exposure, caps = ex.exposure_by_column(terrain, table)
    cont = set(terrain["kind_task"]["continuous"])
    for row, w, c in zip(table, exposure, caps):
        on = row["family"] == "A" and row["kind"] in cont
        assert (w > 0) == on and c == (5 if on else 0), row
    assert sum(w > 0 for w in exposure) > 0


@needs_real
def test_ten_thousand_assignments_and_reassignments_never_leave_exposed_columns_or_pass_the_cap():
    data = np.load(REAL / "terrain_mesh.npz", allow_pickle=False)
    table = cr.build_column_table([str(v) for v in data["column_family"]])
    _plan, terrain_spec = _stage_terrain()
    exposure, caps = ex.exposure_by_column(terrain_spec, table)
    t = _terrain(data["origins"])
    receipt = ex.apply_exposure(t, exposure, caps)
    exposed = torch.tensor([w > 0 for w in exposure])
    cap = torch.tensor(caps)
    seen_cols = torch.zeros(len(exposure), dtype=torch.long)
    gen = torch.Generator().manual_seed(0)
    for step in range(10000):
        if step % 2500 == 0:                                   # fresh assignments too
            t = _terrain(data["origins"]); ex.apply_exposure(t, exposure, caps)
        ids = torch.nonzero(torch.rand(64, generator=gen) < 0.5).flatten()
        up = torch.rand(len(ids), generator=gen) < 0.6
        t.update_env_origins(ids, up, ~up)
        assert exposed[t.terrain_types].all(), step           # exposure-0 column: zero envs, every time
        assert (t.terrain_levels <= cap[t.terrain_types]).all(), step
        seen_cols[t.terrain_types] += 1
        assert torch.equal(t.env_origins, t.terrain_origins[t.terrain_levels, t.terrain_types])
    assert seen_cols[~exposed].sum() == 0 and (seen_cols[exposed] > 0).all()
    assert receipt["exposed_columns"] == torch.nonzero(exposed).flatten().tolist()


def test_unwrapped_stock_importer_does_leave_the_cap_so_the_test_can_fail():
    origins = np.zeros((10, 4, 3))
    t = _terrain(origins) if IMPORTER.is_file() else None
    if t is None:
        pytest.skip("Isaac source missing")
    t.terrain_levels[:] = 5
    ids = torch.arange(64)
    t.update_env_origins(ids, torch.ones(64, dtype=torch.bool), torch.zeros(64, dtype=torch.bool))
    assert (t.terrain_levels == 6).all()                        # stock moves past a cap of 5 without the wrapper


def test_missing_or_bad_plan_values_fail_closed():
    table = [{"family": "A", "kind": "pyramid_stairs"}, {"family": "E", "kind": "slope_steep"}]
    _plan, terrain = _stage_terrain()
    bad = dict(terrain); bad.pop("exposure_at_E0")
    with pytest.raises(ValueError, match="exposure_at_E0"):
        ex.exposure_by_column(bad, table)
    zero = {**terrain, "exposure_at_E0": {"default": {"exposure": 0.0, "level_cap": 0}, "positive": []}}
    with pytest.raises(ValueError, match="no column"):
        ex.exposure_by_column(zero, table)
    nolist = {**terrain, "exposure_at_E0": {"default": {"exposure": 0.0, "level_cap": 0},
              "positive": [{"family": "A", "kinds_of": "nothing", "exposure": 1.0, "level_cap": 5}]}}
    with pytest.raises(ValueError, match="kind list"):
        ex.exposure_by_column(nolist, table)
    neg = {**terrain, "exposure_at_E0": {"default": {"exposure": -1.0, "level_cap": 0}}}
    with pytest.raises(ValueError, match=">= 0"):
        ex.exposure_by_column(neg, table)
    with pytest.raises(ValueError, match="mesh column count"):
        t = types.SimpleNamespace(terrain_origins=torch.zeros(10, 3, 3), terrain_levels=torch.zeros(4, dtype=torch.long))
        ex.apply_exposure(t, [1.0, 0.0], [0, 0])


def test_proportional_assignment_counts():
    types_ = ex.assign_exposed_columns(10, [0.0, 3.0, 0.0, 1.0, 1.0])
    counts = torch.bincount(types_, minlength=5).tolist()
    assert counts[0] == counts[2] == 0 and sum(counts) == 10 and counts[1] == 6
