"""Known geometry, real ray intersections, and the existing mesh/flag consumers."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from foothold_s2.terrains import jump_preset as jp
from foothold_s2.terrains.ex42_mesh_mount import local_mesh_heights, load_combined_mesh


EXPECTED = {
    'jump_up_low': (.10, .20, .30),
    'jump_down_low': (.10, .20, .30),
    'jump_gap': (.15, .30, .45, .60),
    'jump_up_high': (.40, .50, .60, .65, .70, .75),
}


def mesh_of(tile):
    trimesh = pytest.importorskip('trimesh')
    return trimesh.util.concatenate(jp.meshes_for(tile))


@pytest.mark.parametrize('kind,values', EXPECTED.items())
def test_exact_ladder_and_actual_top_surfaces(kind, values):
    assert jp.LEVEL_VALUES_M[kind] == values
    for level, value in enumerate(values):
        tile = jp.build_tile(kind, level, seed=42)
        mesh = mesh_of(tile)
        heights = local_mesh_heights(mesh.vertices, mesh.faces, [[2, 4], [4, 4], [6, 4]])
        if kind == 'jump_gap':
            assert heights == pytest.approx([0, -1, 0])
            edge = np.array([[4-value/2-.001, 4], [4-value/2+.001, 4],
                             [4+value/2-.001, 4], [4+value/2+.001, 4]])
            assert local_mesh_heights(mesh.vertices, mesh.faces, edge) == pytest.approx([0, -1, -1, 0])
        elif kind == 'jump_down_low':
            assert heights == pytest.approx([value, value, 0])
            assert tile.origin[2] == value
        else:
            assert heights == pytest.approx([0, value, value])
        assert mesh.is_watertight
        assert tile.dimensions['gap_width_m' if kind == 'jump_gap' else 'ledge_height_m'] == value


@pytest.mark.parametrize('kind', EXPECTED)
def test_reset_rectangle_and_flags_are_supported_for_every_physical_level(kind):
    from foothold_s2.terrains.ex42_flag_producer import tile_flags
    for level in range(len(EXPECTED[kind])):
        tile = jp.build_tile(kind, level, seed=42)
        mesh = mesh_of(tile)
        # All yaw angles fit in this circumscribed foot rectangle plus reset XY jitter.
        radius = np.hypot(.70/2, .50/2)
        extent = .5 + radius
        xy = tile.origin[:2] + np.array([[x, y] for x in (-extent, 0, extent)
                                       for y in (-extent, 0, extent)])
        assert local_mesh_heights(mesh.vertices, mesh.faces, xy) == pytest.approx([tile.origin[2]]*9)
        flags, meta = tile_flags('F', kind, mesh.triangles, tile.origin, tile.size)
        assert flags == pytest.approx(np.array([[2, 4], [3, 4], [5, 4], [7.25, 4]]))
        assert np.diff(flags[:, 0]).min() > 0
        actual = local_mesh_heights(mesh.vertices, mesh.faces, flags)
        assert actual == pytest.approx(meta['support_z_m'])
        assert np.min(actual) >= 0
        assert flags[1, 0] < 3.7 and flags[2, 0] > 4.3


@pytest.mark.parametrize('overrides', [dict(seed=None), dict(seed=True), dict(seed=-1),
    dict(level=-1), dict(level=3), dict(level=True), dict(size=(1.,8.)),
    dict(size=(8., float('nan'))), dict(gap_depth_m=float('inf'))])
def test_invalid_geometry_fails_before_optional_isaac_import(overrides):
    args = dict(kind='jump_up_low', level=0, seed=42)
    args.update(overrides)
    with pytest.raises(ValueError):
        jp.build_tile(**args)


def test_clamped_storage_rows_do_not_invent_levels():
    from types import SimpleNamespace
    for kind, values in EXPECTED.items():
        cfg = SimpleNamespace(kind=kind, seed=42, size=(8.,8.), layout_rows=10,
                              jump_level=None, gap_depth_m=1., floor_thickness_m=.1)
        for row in range(10):
            meshes, origin = jp.tile_function((row+.75)/10, cfg)
            mesh = pytest.importorskip('trimesh').util.concatenate(meshes)
            height = local_mesh_heights(mesh.vertices, mesh.faces, [[2,4], [6,4]])
            expected = values[min(row, len(values)-1)]
            if kind == 'jump_down_low':
                assert height == pytest.approx([expected, 0])
            elif kind != 'jump_gap':
                assert height == pytest.approx([0, expected])
            assert origin.shape == (3,)


def test_cpu_grid_preserves_rng_and_uses_existing_consumers(tmp_path):
    from foothold_s2.tools.ex42_jump_mesh import write_bundle
    from foothold_s2.terrains.ex42_flags import load_flag_table, MeshFlagProvider
    from foothold_s2.terrains.ex42_column_reset import build_column_table
    from types import SimpleNamespace
    import torch

    np.random.seed(812)
    torch.manual_seed(981)
    before_np, before_torch = np.random.get_state(), torch.get_rng_state().clone()
    manifest = write_bundle(tmp_path/'bundle', seed=42)
    after_np = np.random.get_state()
    assert np.array_equal(before_np[1], after_np[1]) and before_np[2:] == after_np[2:]
    assert torch.equal(before_torch, torch.get_rng_state())
    data = load_combined_mesh(tmp_path/'bundle/terrain_mesh.npz', manifest['mesh_sha256'])
    assert data['origins'].shape == (10,4,3) and data['column_family'] == ['F']*4
    flags = load_flag_table(tmp_path/'bundle/terrain_mesh.npz',10,4)
    assert flags.shape == (10,4,4,2) and np.isfinite(flags).all()
    terrain = SimpleNamespace(terrain_levels=torch.tensor([0,9]), terrain_types=torch.tensor([1,2]),
                              env_origins=torch.as_tensor(data['origins'][[0,9],[1,2]]))
    assert MeshFlagProvider(flags)(terrain,torch.tensor([0,1]),4).numpy() == pytest.approx(flags[[0,9],[1,2]])
    assert [r['kind'] for r in build_column_table(['F']*4)] == list(EXPECTED)
    assert all(r['ranges']['x'] == (-.5,.5) for r in build_column_table(['F']*4))
    assert manifest['status'] == 'cpu_generated'
    assert manifest['measurements'] == {} and manifest['training_ready'] is False
    assert manifest['row_physical_levels']['jump_up_high'] == [0,1,2,3,4,5,5,5,5,5]
    support = json.loads((tmp_path/'bundle/cpu_support.json').read_text())
    assert support['cells_checked'] == 40 and support['articulated_robot_mount_test'] is False
    # Final manifest is not a fabricated GPU/Kit receipt.
    assert not (tmp_path/'bundle/aggregate_measurements.json').exists()
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    plan = EX42Plan(Path('unused'), {'terrain_manifest_contract':{}}, '')
    with pytest.raises(ValueError, match='not measured'):
        plan.validate_terrain_manifest(json.loads((tmp_path/'bundle/terrain_manifest.json').read_text()))
    with pytest.raises(FileExistsError):
        write_bundle(tmp_path/'bundle', seed=43)


def test_two_independent_builds_have_identical_npz_and_manifest_bytes(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    for name in ('one','two'):
        result = subprocess.run([sys.executable,'-m','foothold_s2.tools.ex42_jump_mesh',
                                 '--seed','42','--out',str(tmp_path/name)], cwd=repo,
                                env={**os.environ,'CUDA_VISIBLE_DEVICES':''}, capture_output=True,text=True)
        assert result.returncode == 0, result.stderr + result.stdout
    for name in ('terrain_mesh.npz','mesh_manifest.json','terrain_manifest.json','cpu_support.json'):
        assert hashlib.sha256((tmp_path/'one'/name).read_bytes()).hexdigest() == hashlib.sha256((tmp_path/'two'/name).read_bytes()).hexdigest()
    manifest = json.loads((tmp_path/'one/mesh_manifest.json').read_text())
    assert manifest['npz_sha256'] == hashlib.sha256((tmp_path/'one/terrain_mesh.npz').read_bytes()).hexdigest()


def test_optional_F_does_not_change_default_family_selection():
    from foothold_s2.scripts.ex42_mesh_build import ALL_FAMILIES, build_parser
    assert ALL_FAMILIES == ('A','B','C','D','E')
    assert build_parser().parse_args(['--out','unused','--family','F']).family == ['F']


def test_flags_reject_pit_floor_at_an_exit_goal():
    from foothold_s2.terrains.ex42_flag_producer import tile_flags
    tile = jp.build_tile('jump_gap',3,seed=42)
    # Remove the exit support so the physical pit floor is visible at x=5 and 7.25.
    import dataclasses
    damaged = dataclasses.replace(tile, boxes=tile.boxes[:2])
    mesh = mesh_of(damaged)
    with pytest.raises(ValueError,match='support'):
        tile_flags('F','jump_gap',mesh.triangles,tile.origin,tile.size)


def test_cpu_receipt_rejects_bad_stored_origin_and_bad_flag():
    from foothold_s2.tools.ex42_jump_mesh import verify_support
    from foothold_s2.terrains.ex42_combined import combine_family_parts
    from foothold_s2.scripts.ex42_mesh_build import build_flags
    part = jp.build_family_cpu(seed=42)
    combined = combine_family_parts([part])
    flags, _ = build_flags([part],combined)
    bad = {**combined,'origins':combined['origins'].copy()}
    bad['origins'][0,1,2] = 0.  # Descending terrain needs 0.1 m here.
    with pytest.raises(ValueError,match='support mismatch'):
        verify_support(bad,flags)
    flags[0,2,2,0] = -36.  # Row0, gap center local x4.
    with pytest.raises(ValueError,match='support mismatch'):
        verify_support(combined,flags)


def test_aggregate_family_F_is_optional_and_never_passes_as_ABCDE():
    from foothold_s2.scripts.ex42_mesh_build import aggregate_files
    numbers = {'peak_memory_gib':1.,'generation_seconds':1.,'ray_count_per_second':1.}
    assert aggregate_files(['F'],numbers)[1]['valid_for_manifest'] is False
    assert aggregate_files(list('ABCDEF'),numbers)[0] == 'aggregate_measurements.json'
    with pytest.raises(ValueError):
        aggregate_files(list('ABCDEFF'),numbers)
