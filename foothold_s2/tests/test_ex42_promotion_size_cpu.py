"""Promotion distance must come from each env's own tile, never from a (0, 0) size."""
from __future__ import annotations

import types

import numpy as np
import pytest
import torch

from foothold_s2.curriculum import rules
from foothold_s2.terrains.ex42_mesh_mount import column_tile_sizes


def _terrain(tile_x_by_column=None, size=(8.0, 8.0), types_=(0, 1, 1)):
    gen = types.SimpleNamespace(size=size)
    if tile_x_by_column is not None:
        gen.tile_x_by_column = tile_x_by_column
    return types.SimpleNamespace(cfg=types.SimpleNamespace(terrain_generator=gen),
                                 terrain_types=torch.tensor(types_))


def test_zero_size_is_refused_instead_of_promoting_everyone():
    moving = torch.tensor([[1.0, 0.0]] * 3)
    with pytest.raises(ValueError, match="positive"):
        rules.judge_free(torch.tensor([0.3, 0.3, 0.3]), moving, size_x=0.0)
    with pytest.raises(ValueError, match="positive"):
        rules.promotion_size_x(_terrain(size=(0.0, 0.0)), [0])
    with pytest.raises(ValueError, match="positive"):
        rules.promotion_size_x(_terrain(tile_x_by_column=(8.0, 0.0)), [1])
    with pytest.raises(ValueError):
        rules.judge_free(torch.tensor([1.0]), torch.tensor([[1.0, 0.0]]), size_x=float("nan"))


def test_scalar_size_path_is_unchanged_for_plain_generators():
    assert rules.promotion_size_x(_terrain(), [0, 1]) == 8.0
    up = rules.judge_free(torch.tensor([3.9, 4.1]), torch.tensor([[1.0, 0.0]] * 2), size_x=8.0)
    assert up.tolist() == [0, 1]                                         # strictly greater than size / 2


def test_per_env_tile_length_decides_promotion_for_a_mixed_mesh():
    terrain = _terrain(tile_x_by_column=(8.0, 12.0), types_=(0, 1, 1, 0))
    size = rules.promotion_size_x(terrain, [0, 1, 2, 3])
    assert size.tolist() == [8.0, 12.0, 12.0, 8.0]
    far = torch.tensor([5.0, 5.0, 7.0, 5.0])                              # 5 m: past half of 8, not past half of 12
    moves = rules.judge_free(far, torch.tensor([[1.0, 0.0]] * 4), size_x=size)
    assert moves.tolist() == [1, 0, 1, 1]
    # ids select the right columns, not the first ones
    assert rules.promotion_size_x(terrain, torch.tensor([2, 0])).tolist() == [12.0, 8.0]


def test_judge_with_a_per_env_size_keeps_the_flag_envs_untouched():
    size = torch.tensor([8.0, 12.0])
    out = rules.judge(torch.tensor([False, False]), torch.tensor([5.0, 5.0]), torch.tensor([[1.0, 0.0]] * 2),
                      torch.zeros(2), torch.ones(2), size_x=size)
    assert out.tolist() == [1, 0]


def test_tile_sizes_come_from_the_origin_spacing():
    o = np.zeros((10, 5, 3))
    pitch = np.array([8.0, 8.0, 12.0, 9.0, 9.0])
    for c in range(5):
        o[:, c, 0] = np.arange(10) * pitch[c]
        o[:, c, 1] = c * 9.0
    tile_x, tile_y = column_tile_sizes(o)
    assert tile_x.tolist() == pitch.tolist() and tile_y == 9.0
    bad = o.copy()
    bad[3, 2, 0] += 1.0
    with pytest.raises(ValueError, match="one positive tile length"):
        column_tile_sizes(bad)
    with pytest.raises(ValueError):
        column_tile_sizes(o[:1])
    flat = o.copy()
    flat[:, 0, 0] = 0.0
    with pytest.raises(ValueError):
        column_tile_sizes(flat)


def test_call_sites_use_the_shared_helper_not_the_scalar():
    import pathlib
    root = pathlib.Path(rules.__file__).resolve().parent
    for name in ("ex41.py", "terrain_levels_mixed.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "rules.promotion_size_x(" in text and "terrain_generator.size[0]" not in text, name


def test_mount_cfg_never_declares_a_zero_size_and_carries_the_per_column_table():
    import pathlib
    text = (pathlib.Path(rules.__file__).resolve().parents[1] / "terrains" / "ex42_mesh_mount.py").read_text(encoding="utf-8")
    assert "size: tuple = (0.0, 0.0)" not in text
    assert "tile_x_by_column: tuple" in text and "column_tile_sizes(loaded[\"origins\"])" in text
