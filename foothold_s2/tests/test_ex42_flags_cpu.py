"""Mesh-sized flag table: read from the npz, served by (level, column), NaN -> straight line, wrong column -> error."""
from __future__ import annotations

import types
from pathlib import Path

import numpy as np
import pytest
import torch

from foothold_s2.terrains import ex42_flags as fl

REAL = Path("/home/jay/data/foothold/s2_lab/ex42_mesh_1111/seed42_E1_4cc3/terrain_mesh.npz")


def _npz(tmp_path, flags=None, rows=3, cols=76):
    arrays = {"vertices": np.zeros((3, 3), np.float32), "faces": np.zeros((1, 3), np.int32),
              "origins": np.zeros((rows, cols, 3)), "column_family": np.array(["A"] * cols)}
    if flags is not None:
        arrays["flags"] = flags
    path = tmp_path / "m.npz"
    np.savez(path, **arrays)
    return path


def _terrain(levels, columns, origins=None):
    n = len(levels)
    return types.SimpleNamespace(terrain_levels=torch.tensor(levels), terrain_types=torch.tensor(columns),
                                 env_origins=torch.zeros(n, 3) if origins is None else origins)


def test_a_mesh_without_a_flag_table_changes_nothing(tmp_path):
    assert fl.load_flag_table(_npz(tmp_path), 3, 76) is None
    cfg = types.SimpleNamespace(commands=types.SimpleNamespace(base_velocity=types.SimpleNamespace(flag_provider=None)))
    assert fl.attach_mesh_flags(cfg, _npz(tmp_path), 3, 76) is None and cfg.commands.base_velocity.flag_provider is None


@pytest.mark.skipif(not REAL.is_file(), reason="real mesh missing")
def test_the_shipped_mesh_has_no_flag_table_yet_and_that_is_reported_not_hidden():
    assert fl.load_flag_table(REAL, 10, 76) is None


def test_a_table_for_every_mesh_column_is_served_by_level_and_column_and_nan_cells_fall_back_to_the_straight_line(tmp_path):
    flags = np.full((3, 76, 4, 2), np.nan, np.float32)
    flags[1, 60] = np.arange(8, dtype=np.float32).reshape(4, 2)           # a column past the old 50-column layout
    table = fl.load_flag_table(_npz(tmp_path, flags), 3, 76)
    provider = fl.MeshFlagProvider(table)
    terrain = _terrain([1, 0], [60, 5])
    out = provider(terrain, torch.tensor([0, 1]), 4)
    assert torch.equal(out[0], torch.arange(8, dtype=torch.float32).reshape(4, 2))
    assert not torch.isnan(out[1]).any() and out[1][0, 0] == 0.5          # straight line from the env origin


def test_a_column_the_table_lacks_and_a_wrong_shape_are_refused(tmp_path):
    provider = fl.MeshFlagProvider(np.zeros((3, 50, 4, 2), np.float32))
    with pytest.raises(ValueError, match="flag table has 50"):
        provider(_terrain([0], [60]), torch.tensor([0]), 4)
    with pytest.raises(ValueError, match="must be"):
        fl.load_flag_table(_npz(tmp_path, np.zeros((3, 50, 4, 2), np.float32)), 3, 76)
    with pytest.raises(ValueError, match="infinite"):
        bad = np.zeros((3, 76, 4, 2), np.float32)
        bad[0, 0, 0, 0] = np.inf
        fl.load_flag_table(_npz(tmp_path, bad), 3, 76)


def test_attach_puts_the_provider_on_the_command_term(tmp_path):
    flags = np.zeros((3, 76, 4, 2), np.float32)
    cfg = types.SimpleNamespace(commands=types.SimpleNamespace(base_velocity=types.SimpleNamespace(flag_provider=None)))
    receipt = fl.attach_mesh_flags(cfg, _npz(tmp_path, flags), 3, 76)
    assert isinstance(cfg.commands.base_velocity.flag_provider, fl.MeshFlagProvider) and receipt["columns"] == 76
