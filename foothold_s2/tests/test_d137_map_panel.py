"""D137 known-input checks for map and attention display scales."""

import numpy as np
import pytest

from foothold_s2.eval.video25 import compose_25e_v2style10 as hud


def test_map_has_five_centimetre_minimum_span_and_saturates():
    grid = np.zeros((32, 16), np.float32)
    grid[0, 0] = 0.05
    grid[0, 1] = 0.50
    grid[0, 2] = -0.05
    grid[0, 3] = -0.50
    tile = hud.map_tile(grid, True, cell=1)
    # The two positive cells share the endpoint colour; likewise the negatives.
    assert np.array_equal(tile[31, 15], tile[31, 14])
    assert np.array_equal(tile[31, 13], tile[31, 12])
    assert np.array_equal(tile, hud.map_tile(grid, True, cell=1, scale=(0.0, 0.01)))
    assert hud.MAP_MIN_SPAN_M == 0.05


def test_attention_all_128_cells_fixed_scale_and_endpoint_clamp():
    a = np.full((16, 8), 0.15, np.float32)
    a[0, 0] = 0.0
    a[0, 1] = 0.30
    a[0, 2] = 0.90
    base = np.full((32, 16, 3), 120, np.uint8)
    painted = hud.attention_heatmap_tile(a, base, cell=1)
    assert painted.shape == (32, 16, 3)
    assert np.array_equal(painted[30, 12], painted[30, 10])  # 0.30 and 0.90
    assert not np.array_equal(painted[30, 14], painted[30, 12])  # 0 and 0.30
    assert not np.array_equal(painted[30, 12], painted[30, 8])  # endpoint and 0.15
    assert hud.ATTENTION_MAX == 0.30


def test_attention_rejects_missing_or_nonfinite_tokens():
    base = np.full((32, 16, 3), 120, np.uint8)
    with pytest.raises(ValueError):
        hud.attention_heatmap_tile(np.zeros(127), base, cell=1)
    a = np.zeros(128)
    a[2] = np.nan
    with pytest.raises(ValueError, match="finite"):
        hud.attention_heatmap_tile(a, base, cell=1)
