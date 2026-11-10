"""Lead 2026-11-11 02:16: 0.70 x 0.50 m support, actual triangles, no Kit."""
from types import SimpleNamespace

import numpy as np
import pytest
import trimesh

from foothold_s2.terrains import start_go2_v2 as g
from foothold_s2.tests.test_jeplo_spawn_cpu import vertical_hits

KINDS = ('stepping_stones_low', 'stepping_stones_high', 'balance_beams', 'stepping_beams', 'gaps')


def test_ray_oracle_known_sloping_triangle():
    v = np.array([[0., 0., 0.], [1., 0., 1.], [0., 1., 2.]])
    assert vertical_hits(v, np.array([[0, 1, 2]]), [[.2, .3]]) == pytest.approx([.8])


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('level', range(10))
def test_zero_reset_support_from_returned_mesh(kind, level):
    assert g.RESET_RANGES[kind] == {'x': (0., 0.), 'y': (0., 0.), 'yaw': (0., 0.)}
    difficulty = (level + .5) / 10
    tile = g.build_tile(kind, difficulty)
    boxes_before = tile.boxes.copy()
    meshes, origin = g._tile_function(difficulty, SimpleNamespace(kind=kind))
    mesh = trimesh.util.concatenate(meshes)
    x, y = np.meshgrid(np.linspace(-.35, .35, 15), np.linspace(-.25, .25, 11))
    heights = vertical_hits(mesh.vertices, mesh.faces, origin[:2] + np.c_[x.ravel(), y.ravel()])
    assert heights == pytest.approx(np.zeros(len(heights)), abs=1e-7)
    assert origin == pytest.approx([.5, 4., 0.])
    assert g.spawn_origin(tile, meshes=meshes) == pytest.approx(origin)
    assert np.array_equal(tile.boxes, boxes_before)


def test_old_reset_crosses_real_mesh_pit():
    meshes, origin = g._tile_function(.95, SimpleNamespace(kind='balance_beams'))
    mesh = trimesh.util.concatenate(meshes)
    # Old +0.5 x reset plus front/side footprint: past the 1 m entry platform.
    heights = vertical_hits(mesh.vertices, mesh.faces,
                            origin[:2] + [[0., 0.], [.5 + .35, .25]])
    assert heights[0] == pytest.approx(0)
    assert heights[1] < -.2


def test_old_gaps_reset_can_leave_the_entry_tile():
    meshes, origin = g._tile_function(.95, SimpleNamespace(kind='gaps'))
    mesh = trimesh.util.concatenate(meshes)
    # Reset x=-0.5 plus rear footprint x=-0.35 crosses the first tile boundary.
    with pytest.raises(AssertionError, match='no support'):
        vertical_hits(mesh.vertices, mesh.faces, origin[:2] + [[-.85, 0.]])


def test_reset_mapping_is_explicit_and_detached():
    assert set(g.RESET_RANGES) == set(KINDS)
    table = g.reset_ranges_by_column({23: KINDS[0], 38: KINDS[2], 47: 'gaps', 49: 'flat'})
    assert set(table) == {23, 38, 47, 49}
    assert table[23] == {'x': (0., 0.), 'y': (0., 0.), 'yaw': (0., 0.)}
    assert table[47] == table[23]
    assert table[49] == {'x': (-.5, .5), 'y': (-.5, .5), 'yaw': (-3.14, 3.14)}
    table[23]['x'] = (-.5, .5)
    assert g.RESET_RANGES[KINDS[0]]['x'] == (0., 0.)


@pytest.mark.parametrize('mapping', [{True: KINDS[0]}, {-1: KINDS[0]}, {'23': KINDS[0]}, {23: 'unknown'}])
def test_reset_mapping_rejects_ambiguous_inputs(mapping):
    with pytest.raises(ValueError):
        g.reset_ranges_by_column(mapping)


@pytest.mark.parametrize('kind', KINDS)
def test_missing_or_pit_support_fails_without_origin_fallback(kind):
    tile = g.build_tile(kind, .95)
    meshes, _ = g._tile_function(.95, SimpleNamespace(kind=kind))
    for damaged in ([], meshes[1:]):
        with pytest.raises(ValueError, match='support'):
            g.spawn_origin(tile, meshes=damaged)


def test_centre_only_or_corners_only_cannot_certify_rectangle():
    tile = g.build_tile(KINDS[0], .95)
    def box(x0, x1, y0, y1):
        m = trimesh.creation.box([x1-x0, y1-y0, .2])
        m.apply_translation([(x0+x1)/2, (y0+y1)/2, -.1])
        return m
    # All four corners and centre are supported, but a narrow interior slit is not.
    hole = [box(.15, .52, 3.75, 4.25), box(.53, .85, 3.75, 4.25)]
    mesh = trimesh.util.concatenate(hole)
    xy = np.array([[.15,3.75],[.15,4.25],[.85,3.75],[.85,4.25],[.5,4.]])
    assert vertical_hits(mesh.vertices, mesh.faces, xy) == pytest.approx(np.zeros(5))
    with pytest.raises(ValueError, match='support'):
        g.spawn_origin(tile, meshes=hole)


def test_origin_verifier_is_consumed_by_mesh_callback(monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError('support sentinel')
    monkeypatch.setattr(g, 'spawn_origin', fail)
    with pytest.raises(ValueError, match='support sentinel'):
        g._tile_function(.95, SimpleNamespace(kind=KINDS[0]))


def test_actual_reset_consumer_reads_a_declaration_only_for_sparse_kinds():
    from foothold_s2.terrains.ex42_column_reset import build_column_table, kind_ranges_of, DEFAULT_RANGES
    assert kind_ranges_of('A') == g.RESET_RANGES
    table = build_column_table(['A'] * 50)
    declared = [row for row in table if row['from_declaration']]
    assert len(declared) == 25  # 7 low + 5 high + 5 balance + 5 stepping beams + 3 gaps
    for row in table:
        expected = g.RESET_RANGES.get(row['kind'], DEFAULT_RANGES)
        assert row['ranges'] == expected
    # Follow the same table through the real reset function with a CPU sim sink.
    import torch
    from foothold_s2.terrains.ex42_column_reset import table_tensors, reset_root_state_by_column
    from foothold_s2.tests.test_ex42_column_reset_cpu import _env
    env, asset = _env(list(range(50)))
    lo, hi = table_tensors(table)
    reset_root_state_by_column(env, torch.arange(50), lo, hi, {})
    mask = torch.tensor([row['from_declaration'] for row in table])
    base = env.scene.env_origins + torch.tensor([0., 0., .4])
    assert torch.equal(asset.pose[mask, :3], base[mask])
    assert torch.equal(asset.pose[mask, 3:], torch.tensor([1., 0., 0., 0.]).expand(25, 4))
