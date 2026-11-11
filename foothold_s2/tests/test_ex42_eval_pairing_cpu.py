"""Paired terrain seed, physical stair treads, and evaluator start anchors."""
import numpy as np
import pytest

from foothold_s2.terrains import ex42_eval_terrains as et
from foothold_s2.terrains.ex42_mesh_mount import MeshHeights


@pytest.mark.parametrize('base', et.ss.KINDS)
def test_variants_share_seed_and_observed_pit_and_first_support(base):
    tiles = [et.build_tile(f'{variant}__{base}', seed=42)
             for variant in et.START_VARIANTS]
    assert len({t.dimensions['kind_seed'] for t in tiles}) == 1
    # Geometry itself must agree, not only the manifest's claimed seed.
    assert len({float(t.mesh.vertices[:, 2].min()) for t in tiles}) == 1
    assert len({t.dimensions['depth_m'] for t in tiles}) == 1
    if base != 'gaps':
        # _frame has three boxes. The first support's sampled height is shared
        # even when changed dimensions produce different total support counts.
        first_z = [float(t.mesh.vertices[3*8:4*8, 2].max()) for t in tiles]
        assert first_z == pytest.approx([first_z[0]]*3, abs=1e-14)
    if base == 'stepping_stones':
        jitters = []
        for tile in tiles:
            d = tile.dimensions
            first = tile.mesh.vertices[24:32]
            ox = 1+(6-(d['columns']*d['stone_x_m']+(d['columns']-1)*d['gap_x_m']))/2
            oy = 2+(4-(d['rows']*d['stone_y_m']+(d['rows']-1)*d['gap_y_m']))/2
            # Compare normalized random offsets; physical gap scaling is the
            # treatment and therefore deliberately changes x displacement.
            jitters.append([(first[:,0].min()-ox)/d['gap_x_m'],
                            (first[:,1].min()-oy)/d['gap_y_m']])
        assert np.array(jitters) == pytest.approx(np.tile(jitters[0], (3,1)), abs=1e-14)
    other = et.build_tile(f'{et.START_VARIANTS[0]}__{base}', seed=43)
    assert other.dimensions['kind_seed'] != tiles[0].dimensions['kind_seed']
    assert other.dimensions['depth_m'] != tiles[0].dimensions['depth_m']


def test_surface_spin_has_canonical_rise_run_and_safe_approach():
    tile = et.build_tile('eval_stair_surface_spin', seed=42)
    heights = MeshHeights(tile.mesh.vertices, tile.mesh.faces)
    assert tile.dimensions['step_height_m'] == .15
    assert tile.dimensions['tread_m'] == .25
    assert tile.dimensions['role'] == 'record'
    assert tile.origin == pytest.approx([.5, 4., 0.])
    xy = np.array([[.99, 4], [1.01, 4], [1.24, 4], [1.26, 4], [1.51, 4]])
    assert heights.at(xy) == pytest.approx([0, .15, .15, .30, .45])
    anchor = tile.anchors['stair_surface_center']
    assert heights.at(np.array([anchor[:2]]))[0] == pytest.approx(anchor[2])
    assert tile.layout_assumptions['spin_entry'] == 'walk from approach; do not reset on narrow tread'


def test_landing_restart_stop_band_precedes_landing_and_has_actual_step():
    tile = et.build_tile(et.LANDING, seed=42)
    lo, hi = tile.anchors['stop_band_x']
    assert tile.anchors['approach'][0] < lo < hi < tile.anchors['landing_bounds_xy'][0]
    z = MeshHeights(tile.mesh.vertices, tile.mesh.faces).at(np.array([[(lo+hi)/2, 4.]]))[0]
    assert 0 < z < tile.origin[2]


def test_cli_group_selection_does_not_shift_start_variants():
    from foothold_s2.scripts.ex42_eval_mesh_build import GROUPS
    assert len(GROUPS['start']) == 12
    assert all(k.startswith('start_go2_eval_') for k in GROUPS['start'])
    assert GROUPS['surface'] == ('eval_stair_surface_spin',)
    assert set(GROUPS['all']) == set(GROUPS['landing'] + GROUPS['paper']
                                      + GROUPS['start'] + GROUPS['surface'])
