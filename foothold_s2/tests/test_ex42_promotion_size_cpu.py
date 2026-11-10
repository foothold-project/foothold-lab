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


def test_tile_sizes_are_the_median_origin_spacing_and_irregular_columns_are_reported():
    o = np.zeros((10, 5, 3))
    pitch = np.array([8.0, 8.0, 12.0, 9.0, 9.0])
    for c in range(5):
        o[:, c, 0] = np.arange(10) * pitch[c]
        o[:, c, 1] = c * 9.0
    tile_x, tile_y, irregular = column_tile_sizes(o)
    assert tile_x.tolist() == pitch.tolist() and tile_y == 9.0 and irregular == []
    wobbly = o.copy()
    wobbly[4:, 3, 0] += 0.16                                  # an origin moved to a support patch (8.92 / 9.16 style)
    tile_x, _ty, irregular = column_tile_sizes(wobbly)
    assert tile_x[3] == 9.0 and [r["column"] for r in irregular] == [3]
    assert irregular[0]["max_deviation"] == pytest.approx(0.16) and irregular[0]["median"] == 9.0
    small = o.copy()
    small[4:, 3, 0] += 0.05                                   # inside the tolerance: not reported
    assert column_tile_sizes(small)[2] == []
    bad = o.copy()
    bad[3:, 2, 0] += 5.0                                      # origins no longer one per tile row
    with pytest.raises(ValueError, match="quarter tile"):
        column_tile_sizes(bad)
    with pytest.raises(ValueError):
        column_tile_sizes(o[:1])
    flat = o.copy()
    flat[:, 0, 0] = 0.0
    with pytest.raises(ValueError, match="positive"):
        column_tile_sizes(flat)
    nan = o.copy()
    nan[2, 1, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        column_tile_sizes(nan)


MESH_ROOT = "/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111"
REAL_MESHES = ("seed42_ABCDE", "seed42_ABCDE_b613", "seed42_ABCDE_v2", "seed42_ABCDE_v3")


@pytest.mark.parametrize("name", REAL_MESHES)
def test_real_combined_meshes_give_the_expected_tile_length_per_family(name):
    import pathlib
    path = pathlib.Path(MESH_ROOT) / name / "terrain_mesh.npz"
    if not path.is_file():
        pytest.skip(f"{path} not on this machine")
    data = np.load(path, allow_pickle=True)
    fam = list(data["column_family"])
    tile_x, tile_y, irregular = column_tile_sizes(data["origins"])           # used to raise ValueError on the C columns
    expected = {"A": 8.0, "B": 12.0, "C": 9.0, "D": 8.0, "E": 8.0}
    for family, length in expected.items():
        got = [float(v) for v, f in zip(tile_x, fam) if f == family]
        assert got and all(abs(v - length) < 0.01 for v in got), (name, family, got)   # B has one column at 12.0033
    assert tile_y > 0 and all(r["column"] < len(fam) for r in irregular)
    assert {fam[r["column"]] for r in irregular} <= {"B", "C"}                # only the columns that really wobble
    terrain = _terrain(tile_x_by_column=tuple(tile_x), types_=(0, 55, 62, 70, 74))
    size = rules.promotion_size_x(terrain, [0, 1, 2, 3, 4])
    assert size.tolist() == [tile_x[c] for c in (0, 55, 62, 70, 74)]


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
