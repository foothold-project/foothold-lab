"""The plan's per-stage start exposure (planner 11/11 table): every stage block resolves on the real mesh and respects the sparse cap."""
from __future__ import annotations

import numpy as np
import pytest
import yaml

from foothold_s2.terrains import ex42_column_reset as cr
from foothold_s2.terrains import ex42_exposure as ex
from foothold_s2.tests.test_ex42_exposure_cpu import PLAN, REAL

needs_mesh = pytest.mark.skipif(not (REAL / "terrain_mesh.npz").is_file(), reason="real mesh missing")
STAGES = ["E2", "E3", "E4", "E5", "M", "E6a", "E6b"]
# sparse share added up at the stage start (planner table, computed): the sparse part must stay inside 57.1 % (CG:380)
SPARSE = {"E2": 0.05, "E3": 0.15, "E4": 0.245, "E5": 0.56, "M": 0.56, "E6a": 0.56, "E6b": 0.47}


def _rows():
    return {row["id"]: row for row in yaml.safe_load(PLAN.read_text(encoding="utf-8-sig"))["stages"]}


@needs_mesh
@pytest.mark.parametrize("stage", STAGES)
def test_each_stage_start_block_resolves_on_the_real_mesh_with_its_planned_shares(stage):
    rows = _rows()
    data = np.load(REAL / "terrain_mesh.npz", allow_pickle=False)
    table = cr.build_column_table([str(v) for v in data["column_family"]])
    terrain = {**rows[stage]["terrain"], "kind_task": rows["E0"]["terrain"]["kind_task"]}
    exposure, caps = ex.exposure_by_column(terrain, table, stage)
    eligible, counts = ex.env_counts(6144, exposure)
    assert int(sum(counts)) == 6144
    shares = [s for s in ex.column_shares(terrain, table, stage) if s]
    assert sum(shares) == pytest.approx(SPARSE[stage], abs=1e-9) and sum(shares) <= 0.571
    assert all(cap >= 0 for cap in caps)


def test_a_later_stage_block_is_present_for_every_stage_and_the_sparse_columns_grow_by_stage():
    rows = _rows()
    assert all(f"exposure_at_{stage}" in rows[stage]["terrain"] for stage in STAGES)
    assert [len(rows[s]["terrain"][f"exposure_at_{s}"]["positive"]) for s in ("E2", "E3", "E4", "E5", "E6b")] == [2, 3, 15, 29, 30]
