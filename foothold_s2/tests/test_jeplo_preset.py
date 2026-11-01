"""Independent answers for the execution-preset geometry, no Isaac imports."""
import numpy as np
import pytest
from types import SimpleNamespace

from foothold_s2.terrains.jeplo_preset import build_heightfield, mesh_arrays, tile_function


def test_flat_without_roughness_is_zero_including_full_border():
    tile = build_heightfield('flat', 9, 42, roughness=False)
    assert tile.height_units.shape == (113, 113)
    assert np.count_nonzero(tile.height_units) == 0


@pytest.mark.parametrize('level,maximum', [(0, 60), (9, 300)])
def test_box_height_is_three_steps_not_one(level, maximum):
    tile = build_heightfield('box', level, 42, roughness=False)
    assert tile.height_units.max() == maximum
    assert not tile.height_units[:7].any()
    assert not tile.height_units[-7:].any()


def test_mesh_reaches_nine_metres_without_stretching_internal_cells():
    tile = build_heightfield('flat', 0, 42, roughness=False)
    vertices, triangles = mesh_arrays(tile)
    assert vertices.shape == (12769, 3)
    assert triangles.shape == (25088, 3)
    assert vertices[:, 0].max() == 9.0
    assert vertices[:, 1].max() == 9.0
    assert np.isclose(vertices[113, 0], 0.08)


@pytest.mark.parametrize('kind,level', [('unknown', 0), ('flat', -1), ('box', 10), ('flat', 0.5)])
def test_unknown_geometry_and_noncanonical_level_are_rejected(kind, level):
    with pytest.raises(ValueError):
        build_heightfield(kind, level, 42)


def test_generating_tile_does_not_change_global_random_stream():
    np.random.seed(17)
    before = np.random.get_state()
    build_heightfield('gap', 8, 42)
    after = np.random.get_state()
    assert before[0] == after[0]
    np.testing.assert_array_equal(before[1], after[1])
    assert before[2:] == after[2:]


def test_adapter_rejects_existing_eight_metre_layout_instead_of_silently_resizing():
    with pytest.raises(ValueError, match='9x9'):
        tile_function(0.2, SimpleNamespace(size=(8, 8), kind='box', seed=42))


def test_adapter_returns_mesh_and_origin_at_exact_explicit_level():
    cfg = SimpleNamespace(size=(9, 9), kind='box', seed=42, jeplo_level=9)
    meshes, origin = tile_function(0.2, cfg)
    tile = build_heightfield('box', 9, 42)
    assert len(meshes) == 1
    np.testing.assert_array_equal(origin, tile.origin)
    assert meshes[0].bounds[1, 0] == 9.0
