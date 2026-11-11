"""Known geometry, exact saved-mesh identity, and separation from training."""
import hashlib
import json

import numpy as np
import pytest

from foothold_s2.terrains import ex42_eval_terrains as et
from foothold_s2.terrains.ex42_mesh_mount import MeshHeights


def heights(tile, xy):
    return MeshHeights(tile.mesh.vertices, tile.mesh.faces).at(np.asarray(xy), radius=10)


def test_landing_is_actual_120cm_not_pyramid_platform_parameter():
    t = et.build_tile('eval_stairs_landing_016', seed=42)
    z = t.origin[2]
    assert heights(t, [[3.401, 4], [4.599, 4], [4, 3.401], [4, 4.599]]) == pytest.approx([z]*4)
    assert heights(t, [[3.399, 4], [4.601, 4], [4, 3.399], [4, 4.601]]) == pytest.approx([z-.16]*4)
    assert heights(t, [[3.099, 4], [2.799, 4]]) == pytest.approx([z-.32, z-.48])
    assert t.dimensions['step_height_m'] == .16
    assert t.dimensions['landing_depth_m'] == 1.2
    assert t.anchors['approach'] == [0.5, 4., 0.]


@pytest.mark.parametrize('kind', et.KINDS)
def test_each_column_has_safe_full_spawn_rectangle(kind):
    t = et.build_tile(kind, seed=42)
    # All points in the 0.70 x 0.50 m support footprint, not just root.
    p = np.array([(x, y) for x in np.linspace(-.35,.35,9) for y in np.linspace(-.25,.25,7)])
    assert heights(t, p+t.origin[:2]) == pytest.approx([t.origin[2]]*len(p), abs=1e-6)


@pytest.mark.parametrize('height', [.10,.15,.20,.25])
def test_stair_rise_and_tread(height):
    t = et.build_tile(f'eval_stairs_{round(height*100):03d}', seed=42)
    assert heights(t, [[.99,4],[1.01,4],[1.31,4],[1.61,4]]) == pytest.approx([0,height,2*height,3*height])
    assert t.origin == pytest.approx([.5,4,0])


@pytest.mark.parametrize('angle', [30,35,45])
def test_slope_keeps_planar_angle_without_vertical_clipping(angle):
    t = et.build_tile(f'eval_slope_{angle}', seed=42)
    h = heights(t, [[1.2,4],[2.2,4]])
    assert h[1]-h[0] == pytest.approx(np.tan(np.deg2rad(angle)), abs=1e-7)


def test_start_nominal_l9_axes_exact_products_and_na_axes():
    both = et.build_tile('start_go2_eval_both__stepping_stones', seed=42)
    d = both.dimensions
    assert d['gap_x_m'] == pytest.approx(.25*1.108*1.15)
    assert d['stone_y_m'] == pytest.approx(.2*.885*.85)
    assert d['stone_x_m'] == pytest.approx(.2*1.108)
    assert d['gap_y_m'] == pytest.approx(.175*.885)
    assert et.build_tile('start_go2_eval_both__balance_beams', seed=42).dimensions['beam_width_m'] == pytest.approx(.175*.885*.85)
    # No support-shrinking axis exists for gaps; no gap-expansion axis for balance beams.
    assert et.build_tile('start_go2_eval_sup085__gaps', seed=42).dimensions['gap_width_m'] == pytest.approx(.7*1.108)
    assert et.build_tile('start_go2_eval_gap115__balance_beams', seed=42).dimensions['beam_width_m'] == pytest.approx(.175*.885)


def test_saved_bytes_repeat_and_manifest_pins_every_input(tmp_path):
    from foothold_s2.eval.ex42_eval_mesh import preflight
    p, q = tmp_path/'one', tmp_path/'two'
    et.write_mesh(p, kinds=et.KINDS, seed=42)
    np.random.seed(176)
    et.write_mesh(q, kinds=et.KINDS, seed=42)
    assert (p/'terrain_mesh.npz').read_bytes() == (q/'terrain_mesh.npz').read_bytes()
    r = preflight(p)
    assert len(r['columns']) == 21
    assert r['origins'].shape == (1,21,3)
    assert r['manifest']['training_allowed'] is False
    assert r['manifest']['rng_provenance']['caller_state_restored']
    assert all(c['sources'] for c in r['columns'])
    assert r['manifest']['mesh_file_sha256'] == hashlib.sha256((p/'terrain_mesh.npz').read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        et.write_mesh(p, kinds=et.KINDS, seed=42)
    doc = json.loads((p/'mesh_manifest.json').read_text())
    doc['columns'][0]['origin_world_m'][0] += 1
    (p/'mesh_manifest.json').write_text(json.dumps(doc))
    with pytest.raises(ValueError, match='origin'):
        preflight(p)


def test_duplicate_or_unknown_columns_cannot_be_published(tmp_path):
    with pytest.raises(ValueError):
        et.write_mesh(tmp_path/'bad', kinds=['unknown'], seed=42)
    with pytest.raises(ValueError):
        et.write_mesh(tmp_path/'bad2', kinds=[et.KINDS[0]]*2, seed=42)


def test_gap_and_beam_actual_mesh_dimensions():
    t = et.build_tile('start_go2_eval_both__gaps', seed=42)
    gap = .7*1.108*1.15
    support = (6-3*gap)/4
    start = 1+support
    assert heights(t, [[start-.001,4],[start+.001,4],[start+gap-.001,4],[start+gap+.001,4]]) == pytest.approx([0,-t.dimensions['depth_m'],-t.dimensions['depth_m'],0])
    t = et.build_tile('start_go2_eval_both__balance_beams', seed=42)
    half = .175*.885*.85/2
    top = heights(t, [[4,4]])[0]
    assert heights(t, [[4,4-half+.001],[4,4+half-.001]]) == pytest.approx([top,top])
    assert heights(t, [[4,4-half-.001],[4,4+half+.001]]) == pytest.approx([-t.dimensions['depth_m']]*2)


def test_training_calibration_refuses_evaluation_mesh(tmp_path):
    from foothold_s2.eval.ex42_mesh_eval import preflight as training_preflight
    et.write_mesh(tmp_path/'eval',kinds=[et.LANDING],seed=42)
    with pytest.raises(ValueError,match='full seed-42 ABCDE'):
        training_preflight(tmp_path/'eval')


def test_saved_mesh_covers_start_scanner_behind_entry_without_filling_pits(tmp_path):
    from foothold_s2.eval.ex42_eval_mesh import preflight
    et.write_mesh(tmp_path/'eval',kinds=['start_go2_eval_both__gaps'],seed=42)
    d=preflight(tmp_path/'eval')
    h=MeshHeights(d['vertices'],d['faces'])
    # Actual S1SceneCfg scanner is 1.6 m along x, centred on x=.5 at reset.
    assert h.at(np.array([[-.3,4.],[-.2,4.]])) == pytest.approx([0.,0.])
    gap_start=1+(6-3*(.7*1.108*1.15))/4
    assert h.at(np.array([[gap_start+.1,4.]]))[0] < -.19


def test_one_row_assignment_using_installed_isaac_importer_method(tmp_path):
    """Actual installed Isaac method, extracted to avoid starting Kit/pxr on CPU."""
    import ast
    from types import SimpleNamespace
    import torch
    source = __import__('pathlib').Path('/home/jay/mai/projects/IsaacLab/source/isaaclab/isaaclab/terrains/terrain_importer.py')
    if not source.exists():
        pytest.skip('installed Isaac source unavailable')
    tree=ast.parse(source.read_text(encoding='utf-8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='TerrainImporter')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_compute_env_origins_curriculum')
    scope={'torch':torch}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(source),'exec'),scope)
    origins=torch.tensor([[[4.,4.,1.44],[.5,12.,0.]]])
    obj=SimpleNamespace(cfg=SimpleNamespace(max_init_terrain_level=0),device='cpu')
    result=scope[method.name](obj,64,origins)
    assert obj.terrain_levels.tolist()==[0]*64
    assert obj.terrain_types.tolist()==[0]*32+[1]*32
    assert torch.equal(result,origins[obj.terrain_levels,obj.terrain_types])
