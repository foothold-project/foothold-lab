"""Saved-mesh manifest checks, with known geometry and no Kit bootstrap."""
import copy
import hashlib
import json

import numpy as np
import pytest

from foothold_s2.tools import ex42_execution_manifest as m


def test_known_triangle_hash_uses_geometry_not_declaration():
    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0],
                         [5, 0, 0], [6, 0, 0], [5, 1, 0]], dtype=np.float32)
    faces = np.array([[0, 1, 2], [3, 4, 5]], dtype=np.int32)
    row = m.hash_selected_faces(vertices, faces, np.array([True, False]))
    expected = hashlib.sha256(vertices[:3].tobytes() + faces[:1].tobytes()).hexdigest()
    assert row['geometry_sha256'] == expected
    assert row['vertex_count'] == 3 and row['face_count'] == 1
    changed = vertices.copy()
    changed[0, 2] = .1
    assert m.hash_selected_faces(changed, faces, np.array([True, False]))['geometry_sha256'] != expected
    with pytest.raises(ValueError, match='empty'):
        m.hash_selected_faces(vertices, faces, np.zeros(2, dtype=bool))


def test_kind_inventory_comes_from_generator_code():
    inventory = m.generator_inventory()
    assert {f: len(v) for f, v in inventory.items()} == {
        'A': 13, 'B': 12, 'C': 7, 'D': 3, 'E': 4, 'continuous': 7}
    assert set(inventory['continuous']).issubset(inventory['A'])
    assert m.generator_parameters('B', 'gap')['levels']['9']['gap_m'] == .70
    assert m.generator_parameters('D', 'wall')['levels']['0']['wall_height_m'] == 1.2
    assert m.generator_parameters('E', 'stairs_high')['range_value'] == [0.23, 0.30]


def test_declaration_absence_is_not_filled_with_training_dimensions():
    row = {'preset_id': 'p', 'training_dimensions_m': {'x': .7}}
    assert 'original_dimensions_m' in m.declaration_errors(row)
    assert 'evaluation_dimensions_m' in m.declaration_errors(row)
    assert row == {'preset_id': 'p', 'training_dimensions_m': {'x': .7}}


def declaration():
    return dict(preset_id='p', original_dimensions_m={'x': 1.},
                training_dimensions_m={'x': 1.}, evaluation_dimensions_m={'x': 1.1},
                evaluation_axis_directions={'x': 'higher'}, paper_reference='fixture', physical_flag=False)


@pytest.mark.parametrize('change', [
    {'physical_flag': None}, {'training_dimensions_m': {'x': float('nan')}},
    {'evaluation_dimensions_m': {'x': .9}}, {'evaluation_axis_directions': {'y': 'higher'}},
    {'paper_reference': ''}, {'preset_id': None}])
def test_invalid_declarations_cannot_become_measured(change):
    row = declaration() | change
    assert m.declaration_errors(row)


def test_overlay_conflict_is_not_silently_overwritten(tmp_path):
    first, second = tmp_path/'a.json', tmp_path/'b.json'
    row = declaration()
    first.write_text(json.dumps({'A': {'flat': row}}))
    second.write_text(json.dumps({'B': {'gap': row}}))
    assert set(m.read_declarations([first, second])) == {'A', 'B'}
    second.write_text(json.dumps({'A': {'flat': row | {'preset_id': 'changed'}}}))
    with pytest.raises(ValueError, match='conflicting'):
        m.read_declarations([first, second])


def test_atomic_output_never_replaces_different_manifest(tmp_path):
    path = tmp_path/'terrain_manifest.json'
    m.write_once(path, {'state': 'measured'})
    m.write_once(path, {'state': 'measured'})
    with pytest.raises(FileExistsError):
        m.write_once(path, {'state': 'partial'})
    assert json.loads(path.read_text()) == {'state': 'measured'}


def test_aggregate_values_must_match_measurement_receipt():
    keys = ['generation_seconds', 'peak_memory_gib', 'ray_count_per_second']
    values = dict(zip(keys, [1., 2., 3.]))
    m.check_measurements(values, {'aggregates': values}, keys)
    with pytest.raises(ValueError, match='differs'):
        m.check_measurements(values | {'generation_seconds': 9.}, {'aggregates': values}, keys)
    with pytest.raises(ValueError, match='invalid'):
        m.check_measurements(values | {'generation_seconds': float('nan')}, {'aggregates': values}, keys)


def test_column_slicing_ignores_safe_spawn_shift():
    # A 1 m tile with a shifted spawn. The geometry grid stays centred at zero.
    centroids = np.array([[0., -.25, 0], [0., .25, 0], [4., .25, 0]])
    mask = m.column_face_mask(centroids, columns=[1], total_columns=2,
                              size=(1., 1.), rows=1, offset=0.)
    assert mask.tolist() == [False, True, False]


@pytest.fixture
def saved_mesh(tmp_path):
    plan = m.EX42Plan.load(m.REPO/'foothold_s2/curriculum/ex42-prep.yaml')
    plan.document['environment']['training_presets']['D'] = m.d.PRESET_ID
    inventory = m.generator_inventory()
    declarations = {f: {k: declaration() | {'preset_id': plan.document['environment']['training_presets'][f]}
                        for k in kinds} for f, kinds in inventory.items()}
    for family in ('B', 'D'):
        for kind in inventory[family]:
            levels = m.generator_parameters(family, kind)['levels']
            dims = {k: v for k, v in levels[max(levels, key=int)].items() if v > 0}
            declarations[family][kind].update(original_dimensions_m=dims,
                training_dimensions_m=dims, evaluation_dimensions_m=dims,
                evaluation_axis_directions={k: 'same' for k in dims})
    decl_file = tmp_path/'declarations.json'
    decl_file.write_text(json.dumps(declarations))
    counts = {'A': 50, 'B': 12, 'C': 7, 'D': 3, 'E': 4}
    sizes = {'A': (8, 8), 'B': (12, 12), 'C': (9, 9), 'D': (8, 8), 'E': (8, 8)}
    vertices, families, offsets = [], [], {}
    for index, (family, count) in enumerate(counts.items()):
        offset = index*1000.
        offsets[family] = offset
        for col in range(count):
            y = offset + (col+.5-count/2)*sizes[family][1]
            vertices += [[0., y, 0.], [.1, y, 0.], [0., y+.1, 0.]]
            families.append(family)
    v = np.asarray(vertices, dtype=np.float32)
    f = np.arange(len(v), dtype=np.int32).reshape(-1, 3)
    sha = hashlib.sha256(v.tobytes()+f.tobytes()).hexdigest()
    origins = np.zeros((10, 76, 3))
    np.savez(tmp_path/'terrain_mesh.npz', vertices=v, faces=f, origins=origins, column_family=families)
    metrics = {'generation_seconds': 1., 'peak_memory_gib': 2., 'ray_count_per_second': 3.}
    receipt = dict(format='foothold-ex42-combined-mesh/1', training_started=False,
                   families_missing=[], join_axis=1, columns_by_family=counts, origins_shape=[10, 76, 3],
                   mesh_sha256=sha, offsets_m=offsets, aggregates=metrics, seed=42, device='cuda:0',
                   ray_measurement={'envs': 3072, 'pattern': 'proxy fixture'})
    (tmp_path/'mesh_manifest.json').write_text(json.dumps(receipt))
    (tmp_path/'aggregate_measurements.json').write_text(json.dumps(metrics))
    plan.document['assumptions_pending_lead']['terrain_manifest_measurements']['value'] = metrics | {'mesh_sha256': sha}
    return plan, tmp_path, declarations, [decl_file]


def test_complete_46_rows_pass_real_validator_and_aliases_share_geometry(saved_mesh):
    doc = m.assemble_saved_mesh(*saved_mesh)
    saved_mesh[0].validate_terrain_manifest(doc)
    assert doc['status'] == 'measured' and len(doc['kinds']) == 46
    rows = {(r['family'], r['kind']): r for r in doc['kinds']}
    for kind in m.columns.CONTINUOUS:
        assert rows['A', kind]['geometry_sha256'] == rows['continuous', kind]['geometry_sha256']
    assert doc['provenance']['ray_measurement']['envs'] == 3072
    assert doc['provenance']['evaluation_geometry_measured'] is False


def test_missing_family_stays_partial_and_is_rejected_by_runtime_contract(saved_mesh):
    del saved_mesh[2]['D']
    doc = m.assemble_saved_mesh(*saved_mesh)
    assert doc['status'] == 'partial' and len(doc['kinds']) == 43
    assert len(doc['missing_declarations']) == 3
    with pytest.raises(ValueError, match='not measured'):
        saved_mesh[0].validate_terrain_manifest(doc)


def test_plan_null_preset_cannot_be_hidden_by_complete_declaration(saved_mesh):
    saved_mesh[0].document['environment']['training_presets']['D'] = None
    doc = m.assemble_saved_mesh(*saved_mesh)
    assert doc['status'] == 'partial'
    assert all('plan.training_presets.D' in row['fields'] for row in doc['missing_declarations'])


def test_bad_actual_mesh_is_rejected_even_with_good_receipt(saved_mesh):
    plan, path, declarations, files = saved_mesh
    p = path/'terrain_mesh.npz'
    with np.load(p) as z:
        data = {key: z[key] for key in z.files}
    data['vertices'][0, 2] = .1
    np.savez(p, **data)
    with pytest.raises(ValueError, match='sha256'):
        m.assemble_saved_mesh(plan, path, declarations, files)


def test_measurement_from_other_plan_is_rejected(saved_mesh):
    saved_mesh[0].document['assumptions_pending_lead']['terrain_manifest_measurements']['value']['mesh_sha256'] = 'a'*64
    with pytest.raises(ValueError, match='plan measurement pin'):
        m.assemble_saved_mesh(*saved_mesh)


def test_unknown_kind_and_nonmatching_preset_are_not_accepted(saved_mesh):
    saved_mesh[2]['A']['typo_kind'] = declaration()
    with pytest.raises(ValueError, match='unknown declaration'):
        m.assemble_saved_mesh(*saved_mesh)
    del saved_mesh[2]['A']['typo_kind']
    saved_mesh[2]['A']['flat']['preset_id'] = 'another-preset'
    doc = m.assemble_saved_mesh(*saved_mesh)
    assert doc['missing_declarations'][0]['fields'] == ['preset_id differs from plan']


def test_declaration_cannot_invent_a_training_dimension(saved_mesh):
    saved_mesh[2]['D']['wall']['training_dimensions_m']['wall_height_m'] = 99.
    saved_mesh[2]['D']['wall']['evaluation_dimensions_m']['wall_height_m'] = 99.
    with pytest.raises(ValueError, match='declaration/code dimension mismatch'):
        m.assemble_saved_mesh(*saved_mesh)
