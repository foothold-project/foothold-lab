"""E3 kinds' crossing line (lead 2026-11-22 08:26 ledger c13a14709 · planner 08:25): pallets, stepping beams and easy stepping stones use the
fixed far line 3.3 m (balance-beam form); the E2 kinds keep the measured first gap end. On the real runs of the current best checkpoint
(rx2qh m250, planner ru1121 out_final/e3kinds_rx2qh250, seed 42, 0.7 m/s) the old line lets a flat map cross near the ceiling; the new one
does not. CPU only (the trimesh ray cast for the old line runs on the real E2 mesh)."""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.tools import ex42_v1_mapgain_boundary as mb

RUNS = Path("/home/jay/mai/tmp/planner/ru1121/out_final/e3kinds_rx2qh250/mapgain_runs")
MESH = Path("/mnt/win-d/mai/data/foothold/sonnet_beam_mesh_1119/b2m_rpy_lv")


def test_fixed_line_only_for_listed_kinds():
    for k in ("B/pallets", "A/stepping_beams", "A/stepping_stones_low", "A/balance_beams"):
        fam, name = k.split("/")
        assert mb.first_gap_end(MESH, fam, name, 0, 0) == 3.0          # no ray cast needed for these
    assert "A/gaps" not in mb.FIXED_GAP_END and "B/gap" not in mb.FIXED_GAP_END and "C/gap" not in mb.FIXED_GAP_END


def _old_gap_end(fam, name, col, lv):
    saved = dict(mb.FIXED_GAP_END)
    try:
        mb.FIXED_GAP_END.clear(); mb.FIXED_GAP_END["A/balance_beams"] = 3.0     # the code before 08:26
        return mb.first_gap_end(MESH, fam, name, col, lv)
    finally:
        mb.FIXED_GAP_END.clear(); mb.FIXED_GAP_END.update(saved)


@pytest.mark.skipif(not RUNS.is_dir() or not MESH.is_dir(), reason="planner E3 runs or E2 mesh not on this machine")
@pytest.mark.parametrize("tag", ["B_pallets_L1", "A_stepping_beams_L1", "A_stepping_stones_low_L0"])   # the E3 start caps (lead 08:26: 1 · 1 · 0)
def test_flat_map_no_longer_at_the_ceiling_on_the_current_checkpoint(tag):
    fam, name = tag.split("_", 1)[0], tag.split("_", 1)[1].rsplit("_L", 1)[0]
    flat = sorted(glob.glob(str(RUNS / f"{tag}_v0.7_s42_flat" / "env_arrays_eval_gt_*.npz")))
    if not flat:
        pytest.skip("flat run missing")
    z = np.load(flat[0])
    old_line = _old_gap_end(fam, name, int(z["terrain_col"][0]), int(z["terrain_level"][0])) + 0.3
    new_line = mb.first_gap_end(MESH, fam, name, int(z["terrain_col"][0]), int(z["terrain_level"][0])) + 0.3
    old, _ = mb.count_crossed(flat[0], old_line)
    new, _ = mb.count_crossed(flat[0], new_line)
    print(f"\n{tag}: old line {old_line:.2f} m flat crossed {old}/64 · new line {new_line:.2f} m flat crossed {new}/64")
    assert new_line == pytest.approx(3.3)
    assert old_line < 2.0 and old > mb.CEILING                                   # the old line: a flat map already at the ceiling
    # (pallets L0 stays at the ceiling even on 3.3 m: flat 59/64 · measured 08:3x, reported; the start cap is 1, not 0)
    assert new <= mb.CEILING                                                     # the new line: no longer counted as graduation by itself
