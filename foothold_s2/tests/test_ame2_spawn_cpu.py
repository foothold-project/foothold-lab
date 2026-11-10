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
@pytest.mark.parametrize('level', (0, 3, 6, 9))
@pytest.mark.parametrize('seed_mode', ('42', '43', 'adapter42'))
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


@pytest.mark.parametrize('kind', ('pallets', 'stones'))
def test_missing_entry_landing_is_rejected(kind):
    tile = p.build_tile(kind, 9, 42)
    damaged = replace(tile, boxes=tile.boxes[:-1])
    with pytest.raises(ValueError, match='safe entry support'):
        p.spawn_origin(damaged)


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
    for col in (50, 51, 57, 58, 59):
        assert table[col] == {'x': (0., 0.), 'y': (0., 0.), 'yaw': (0., 0.)}
    for col in set(range(50, 62)) - {50, 51, 57, 58, 59}:
        assert table[col] == {'x': (-.5, .5), 'y': (-.5, .5), 'yaw': (-3.14, 3.14)}
    table[50]['x'] = (-.5, .5)
    assert p.RESET_RANGES['stair_up']['x'] == (0., 0.)


@pytest.mark.parametrize('mapping', ({True: 'beam'}, {-1: 'beam'}, {'59': 'beam'}, {59: 'bad'}))
def test_reset_table_rejects_ambiguous_mapping(mapping):
    with pytest.raises(ValueError):
        p.reset_ranges_by_column(mapping)
