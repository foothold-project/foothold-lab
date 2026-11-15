"""Spawn support is separate from matching the JEPLO reference heightfield."""
from types import SimpleNamespace

import numpy as np
import pytest

from foothold_s2.terrains import jeplo_preset as jp


def vertical_hits(vertices, faces, xy):
    """Independent vertical line/triangle intersection, not heightfield lookup."""
    t = vertices[faces].astype(float)
    a, b, c = t[:, 0], t[:, 1], t[:, 2]
    u, v = b[:, :2] - a[:, :2], c[:, :2] - a[:, :2]
    det = u[:, 0]*v[:, 1] - u[:, 1]*v[:, 0]
    valid = abs(det) > 1e-12
    a, u, v, det, t = a[valid], u[valid], v[valid], det[valid], t[valid]
    result = []
    for point in xy:
        q = point-a[:, :2]
        s = (q[:, 0]*v[:, 1]-q[:, 1]*v[:, 0])/det
        r = (u[:, 0]*q[:, 1]-u[:, 1]*q[:, 0])/det
        hit = (s >= -1e-7) & (r >= -1e-7) & (s+r <= 1+1e-7)
        assert hit.any(), f'no support at {point}'
        z = t[:, 0, 2] + s*(t[:, 1, 2]-t[:, 0, 2]) + r*(t[:, 2, 2]-t[:, 0, 2])
        result.append(z[hit].max())
    return np.asarray(result)


def test_known_triangle_intersection():
    v = np.array([[0., 0., 0.], [1., 0., 1.], [0., 1., 2.]])
    np.testing.assert_allclose(vertical_hits(v, np.array([[0, 1, 2]]), [[.2, .3]]), [.8])


@pytest.mark.parametrize('kind', ['gap', 'box', 'discrete_obstacles'])
@pytest.mark.parametrize('level', range(10))
@pytest.mark.parametrize('seed', [0, 42, 2026])
def test_spawn_has_support_under_entire_footprint(kind, level, seed):
    tile = jp.build_heightfield(kind, level, seed)
    before = tile.height_units.copy()
    vertices, faces = jp.mesh_arrays(tile)
    origin = jp.spawn_origin(tile, vertices=vertices, faces=faces)
    dx, dy = np.meshgrid(np.linspace(-.35, .35, 7), np.linspace(-.25, .25, 7))
    heights = vertical_hits(vertices, faces, origin[:2] + np.c_[dx.ravel(), dy.ravel()])
    assert heights.min() >= -.1
    assert heights.max() <= .15 + 1e-6
    assert heights.ptp() <= .15 + 1e-6
    assert max(abs(heights - origin[2])) <= .15 + 1e-6
    np.testing.assert_allclose(vertical_hits(vertices, faces, [origin[:2]]), [origin[2]], atol=1e-7)
    assert .35 <= origin[0] <= 1.6  # entry, never pit bottom or far finish platform
    assert abs(origin[1]-4.48) <= .4 + 1e-7
    np.testing.assert_array_equal(before, tile.height_units)


def test_old_gap_centre_cannot_certify_nearby_feet():
    tile = jp.build_heightfield('gap', 0, 42)
    v, f = jp.mesh_arrays(tile)
    # Centre has ground, but reset (.5,-.5) plus lateral foot extent crosses a pit.
    old = vertical_hits(v, f, tile.origin[:2] + np.array([[0., 0.], [.5, -.65625]]))
    assert abs(old[0]) < .1
    assert old.min() < -.5  # the regression is real, not only an API test
    assert jp.spawn_origin(tile)[0] < 1.6


def test_adapter_consumes_spawn_origin_not_reference_centre():
    pytest.importorskip('trimesh')
    cfg = SimpleNamespace(size=(9., 9.), kind='gap', seed=42)
    meshes, origin = jp.tile_function(.05, cfg)
    tile = jp.build_heightfield('gap', 0, jp.adapter_seed('gap', .05, 42))
    np.testing.assert_allclose(origin, jp.spawn_origin(tile))
    assert origin[0] < 1.6
    assert meshes[0].bounds[1, 0] == 9.


@pytest.mark.parametrize('kind', ['flat', 'discrete_grid', 'pyramid_stairs', 'inverted_pyramid_stairs'])
def test_direct_command_terrain_origin_unchanged(kind):
    tile = jp.build_heightfield(kind, 9, 42)
    np.testing.assert_array_equal(jp.spawn_origin(tile), tile.origin)


def test_reset_table_uses_actual_global_columns_and_only_three_zero_ranges():
    assert set(jp.RESET_RANGES) == {'gap', 'box', 'discrete_obstacles'}
    table = jp.reset_ranges_by_column({50+i: kind for i, kind in enumerate(jp.KINDS)})
    assert set(table) == set(range(50, 57))
    for col in (50, 52, 53):
        assert table[col] == {'x': (0., 0.), 'y': (0., 0.), 'yaw': (0., 0.)}
    for col in (51, 54, 55, 56):
        assert table[col] == {'x': (-.5, .5), 'y': (-.5, .5), 'yaw': (-3.14, 3.14)}
    table[50]['x'] = (-.5, .5)
    assert jp.RESET_RANGES['gap']['x'] == (0., 0.)


@pytest.mark.parametrize('mapping', [{0: 'unknown'}, {-1: 'gap'}, {True: 'gap'}, {'50': 'gap'}])
def test_reset_table_rejects_ambiguous_column_or_kind(mapping):
    with pytest.raises(ValueError):
        jp.reset_ranges_by_column(mapping)


def test_no_safe_support_raises_instead_of_returning_centre():
    tile = jp.HeightTile('gap', 0, 42, np.full((113, 113), -300, dtype=np.int16), 0.)
    with pytest.raises(ValueError, match='support'):
        jp.spawn_origin(tile)
