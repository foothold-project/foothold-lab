"""B/gap fixed start (RESET_RANGES zero like A and C): the start cell is a supported platform before the gap, both the
training and the evaluation reset read the same table, and 32 gap envs all start facing +x (none backwards). CPU only."""
from __future__ import annotations

import numpy as np
import pytest
import torch

from foothold_s2.terrains import ame2_preset as p
from foothold_s2.terrains import ex42_column_reset as cr
from foothold_s2.tests.test_ame2_spawn_cpu import mesh_top_heights
from foothold_s2.tests.test_ex42_column_reset_cpu import _env

ZERO = {"x": (0., 0.), "y": (0., 0.), "yaw": (0., 0.)}
GAP_COLUMN = p.KINDS.index("gap")


def test_gap_is_declared_fixed_and_the_two_other_default_kinds_are_not():
    assert p.RESET_RANGES["gap"] == ZERO
    assert "gap" not in p.SAFE_ENTRY_KINDS and p.FIXED_START_KINDS == {"gap"}      # no anchor search: Tile.origin is already the start
    assert "climb_up" not in p.RESET_RANGES and "climb_down" not in p.RESET_RANGES
    table = p.reset_ranges_by_column({50 + i: k for i, k in enumerate(p.KINDS)})
    assert table[56] == ZERO and table[54] == table[55] == {"x": (-.5, .5), "y": (-.5, .5), "yaw": (-3.14, 3.14)}


@pytest.mark.parametrize("level", range(10))
@pytest.mark.parametrize("seed", (0, 1, 42, 43, 2026))
def test_the_start_cell_is_flat_supported_platform_well_before_the_gap_edge(level, seed):
    tile = p.build_tile("gap", level, seed)
    origin = p.spawn_origin(tile)
    dx, dy = np.meshgrid(np.linspace(-.35, .35, 7), np.linspace(-.25, .25, 7))
    heights = mesh_top_heights(tile, origin[:2] + np.c_[dx.ravel(), dy.ravel()])         # asserts every point hits a triangle
    assert np.ptp(heights) <= 1e-7 and abs(heights.max() - origin[2]) <= 1e-7 and origin[2] == 0.0
    near_edge = min(b.x1 for b in tile.boxes if b.z1 == 0 and b.x1 < 8)                   # near platform edge = gap start
    assert near_edge - (origin[0] + .35) >= 3.0                                           # >= 3 m of platform ahead of the body


def test_training_and_evaluation_read_the_same_table_and_the_gap_row_is_fixed():
    table = cr.build_column_table(["B"] * len(p.KINDS))
    row = table[GAP_COLUMN]
    assert (row["family"], row["kind"], row["from_declaration"]) == ("B", "gap", True)
    assert {k: row["ranges"][k] for k in ("x", "y", "yaw")} == ZERO
    lo, hi = cr.table_tensors(table)                                  # the training reset (apply_column_reset) and the flag eval (pin midpoint) both start from this
    assert torch.equal(lo[GAP_COLUMN], hi[GAP_COLUMN])
    ev = types_event(lo, hi)
    cr.pin_column_reset_midpoint(ev)
    assert float(ev.params["lo"][GAP_COLUMN].abs().max()) == 0.0


def types_event(lo, hi):
    import types
    return types.SimpleNamespace(func=cr.reset_root_state_by_column, params={"lo": lo.clone(), "hi": hi.clone(), "velocity_range": {}})


def _yaws(table, n=32, seed=7):
    lo, hi = cr.table_tensors(table)
    env, asset = _env([GAP_COLUMN] * n)
    torch.manual_seed(seed)
    cr.reset_root_state_by_column(env, torch.arange(n), lo, hi, {})
    quat = asset.pose[:, 3:]
    yaw = 2 * torch.atan2(quat[:, 3], quat[:, 0])
    pos = asset.pose[:, :3] - env.scene.env_origins
    return yaw, pos


def test_cpu_rehearsal_32_gap_envs_start_forward_with_zero_backward_and_the_old_table_did_not():
    yaw, pos = _yaws(cr.build_column_table(["B"] * len(p.KINDS)))
    assert yaw.shape == (32,) and float((yaw.abs() > np.pi / 2).sum()) == 0.0 and float(yaw.abs().max()) == 0.0
    assert torch.equal(pos[:, :2], torch.zeros(32, 2))                    # also no x / y jitter: all 32 on the checked start cell
    old = cr.build_column_table(["B"] * len(p.KINDS), {"B": {k: v for k, v in p.RESET_RANGES.items() if k != "gap"}})
    yaw_old, _ = _yaws(old)
    assert 8 <= int((yaw_old.abs() > np.pi / 2).sum()) <= 24             # the default +-3.14 faces about half backwards
