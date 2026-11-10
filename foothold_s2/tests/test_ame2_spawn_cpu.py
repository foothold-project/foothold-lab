"""B-family entry support measured on triangles, independently of box lookup."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from foothold_s2.terrains import ame2_preset as p


def mesh_top_heights(tile, points):
    triangles = np.concatenate([m.vertices[m.faces] for m in p.mesh_arrays(tile)])
    result = []
    for px, py in points:
        near = ((triangles[:, :, 0].min(1) <= px + 1e-9)
                & (triangles[:, :, 0].max(1) >= px - 1e-9)
                & (triangles[:, :, 1].min(1) <= py + 1e-9)
                & (triangles[:, :, 1].max(1) >= py - 1e-9))
        a, b, c = triangles[near].transpose(1, 0, 2)
        u, v = b[:, :2] - a[:, :2], c[:, :2] - a[:, :2]
        det = u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]
        keep = np.abs(det) > 1e-12
        a, u, v, det = a[keep], u[keep], v[keep], det[keep]
        q = np.array([px, py]) - a[:, :2]
        s = (q[:, 0] * v[:, 1] - q[:, 1] * v[:, 0]) / det
        t = (u[:, 0] * q[:, 1] - u[:, 1] * q[:, 0]) / det
        hit = (s >= -1e-7) & (t >= -1e-7) & (s + t <= 1 + 1e-7)
        assert hit.any(), (tile.kind, tile.level, px, py)
        z = a[:, 2] + s * (b[keep, 2] - a[:, 2]) + t * (c[keep, 2] - a[:, 2])
        result.append(z[hit].max())
    return np.asarray(result)


@pytest.mark.parametrize('kind', sorted(p.SAFE_ENTRY_KINDS))
@pytest.mark.parametrize('level', range(10))
@pytest.mark.parametrize('seed_mode', ('0', '42', '43', '2026', 'adapter42'))
def test_safe_entry_is_supported_by_generated_triangles(kind, level, seed_mode):
    seed = (p._tile_seed(kind, level / 10, 42) if seed_mode == 'adapter42'
            else int(seed_mode))
    tile = p.build_tile(kind, level, seed)
    origin = p.spawn_origin(tile)
    dx, dy = np.meshgrid(np.linspace(-.35, .35, 7), np.linspace(-.25, .25, 7))
    heights = mesh_top_heights(tile, origin[:2] + np.c_[dx.ravel(), dy.ravel()])
    assert np.ptp(heights) <= .15 + 1e-7
    assert np.max(np.abs(heights - origin[2])) <= .15 + 1e-7
    assert np.isfinite(origin).all()
    if kind in ('boxes', 'obstacles'):
        assert origin[2] == 0  # never a pillar top or pit floor
        assert origin[0] <= 1.5  # enter before the obstacle run


@pytest.mark.parametrize('kind', ('pallets', 'stones'))
def test_missing_entry_landing_is_rejected(kind):
    tile = p.build_tile(kind, 9, 42)
    damaged = replace(tile, boxes=tile.boxes[:-1])
    with pytest.raises(ValueError, match='safe entry support'):
        p.spawn_origin(damaged)


def test_rough_entry_is_part_of_heightfield_and_joins_without_box_edge():
    tile = p.build_tile('rough', 9, 42)
    assert tile.rough_height_m is not None
    assert not tile.boxes
    assert p.spawn_origin(tile)[0] < 1.
    np.testing.assert_allclose(tile.rough_height_m[:11], tile.rough_height_m[5, 60])
    sample = mesh_top_heights(tile, [(x, 6.) for x in (.9, 1., 1.1)])
    assert np.max(np.abs(np.diff(sample))) < .06


def test_rough_relief_guard_rejects_surviving_mutation():
    tile = p.build_tile('rough', 9, 42)
    damaged = tile.rough_height_m.copy()
    damaged[5, 60] += .3
    with pytest.raises(ValueError, match='rough entry support relief'):
        p.spawn_origin(replace(tile, rough_height_m=damaged))


def test_consecutive_start_precedes_first_riser():
    tile = p.build_tile('consecutive', 9, 42)
    assert p.spawn_origin(tile)[0] < tile.boxes[1].x0


@pytest.mark.parametrize('kind', ('boxes', 'obstacles'))
def test_flat_entry_search_rejects_pillar_only_support(kind):
    tile = p.build_tile(kind, 9, 42)
    pillar = p._box(0, p.SIZE, 0, p.SIZE, 2.)
    with pytest.raises(ValueError, match='level-zero safe entry'):
        p.spawn_origin(replace(tile, boxes=(pillar,)))


@pytest.mark.parametrize('kind', ('stair_up', 'stair_down'))
def test_stairs_are_ahead_of_entry_and_keep_six_declared_risers(kind):
    tile = p.build_tile(kind, 9, 42)
    entry = p.spawn_origin(tile)
    assert entry[0] < tile.boxes[1].x0
    heights = mesh_top_heights(tile, [(1.5 + .3 * i + .15, 6.) for i in range(6)])
    step = p.dimensions(kind, 9)['step_height_m']
    expected = np.arange(1, 7) * step * (1 if kind == 'stair_up' else -1)
    np.testing.assert_allclose(heights, expected, atol=1e-9)


def test_adapter_returns_safe_anchor_and_other_kinds_keep_old_origin():
    cfg = SimpleNamespace(size=(12., 12.), kind='stones', seed=42, ame2_level=9)
    meshes, origin = p.tile_function(.9, cfg)
    tile = p.build_tile('stones', 9, p._tile_seed('stones', .9, 42))
    np.testing.assert_array_equal(origin, p.spawn_origin(tile))
    assert meshes[0].faces.shape[0] > 0
    other = p.build_tile('gap', 9, 42)
    np.testing.assert_array_equal(p.spawn_origin(other), other.origin)


def test_reset_table_uses_actual_B_columns_and_only_target_kinds():
    table = p.reset_ranges_by_column({50 + i: kind for i, kind in enumerate(p.KINDS)})
    for col in (50, 51, 52, 53, 57, 58, 59, 60, 61):
        assert table[col] == {'x': (0., 0.), 'y': (0., 0.), 'yaw': (0., 0.)}
    for col in set(range(50, 62)) - {50, 51, 52, 53, 57, 58, 59, 60, 61}:
        assert table[col] == {'x': (-.5, .5), 'y': (-.5, .5), 'yaw': (-3.14, 3.14)}
    table[50]['x'] = (-.5, .5)
    assert p.RESET_RANGES['stair_up']['x'] == (0., 0.)


@pytest.mark.parametrize('mapping', ({True: 'beam'}, {-1: 'beam'}, {'59': 'beam'}, {59: 'bad'}))
def test_reset_table_rejects_ambiguous_mapping(mapping):
    with pytest.raises(ValueError):
        p.reset_ranges_by_column(mapping)
