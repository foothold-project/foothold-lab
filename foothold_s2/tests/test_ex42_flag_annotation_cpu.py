"""An added goal table must not impersonate a newly measured terrain."""
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import pytest

from foothold_s2.tools import ex42_execution_manifest as manifest
from foothold_s2.tools import ex42_mesh_flags as tool
from foothold_s2.terrains.ex42_column_reset import build_column_table
from foothold_s2.terrains.columns import CONTINUOUS
from foothold_s2.tests.test_ex42_execution_manifest_cpu import saved_mesh


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def annotation(saved_mesh, tmp_path):
    plan, source, declarations, declaration_paths = saved_mesh
    target = tmp_path/'annotated'
    target.mkdir()
    with np.load(source/'terrain_mesh.npz') as z:
        arrays = {key: z[key] for key in z.files}
    flags = np.ones((10, 76, 4, 2), dtype=np.float32)
    table = build_column_table(arrays['column_family'].tolist())
    for column, row in enumerate(table):
        if row['family'] == 'A' and row['kind'] in CONTINUOUS:
            flags[:, column] = np.nan
    np.savez_compressed(target/'terrain_mesh.npz', **arrays, flags=flags)
    shutil.copyfile(source/'aggregate_measurements.json', target/'aggregate_measurements.json')
    receipt = json.loads((source/'mesh_manifest.json').read_text())
    receipt['aggregate_file'] = 'aggregate_measurements.json'
    (source/'mesh_manifest.json').write_text(json.dumps(receipt))
    receipt.update(mesh_file_sha256=sha(target/'terrain_mesh.npz'),
        flag_annotation_source={'folder': str(source),
            'manifest_sha256': sha(source/'mesh_manifest.json'),
            'npz_sha256': sha(source/'terrain_mesh.npz'),
            'geometry_preserved': True, 'measurements_inherited': True,
            'new_kit_validation': False, 'execution_manifest_regeneration_required': True})
    (target/'mesh_manifest.json').write_text(json.dumps(receipt))
    return plan, target, declarations, declaration_paths


def test_annotation_manifest_retains_inherited_measurement_proof(annotation):
    result = manifest.assemble_saved_mesh(*annotation)
    proof = result['provenance']['flag_annotation']
    assert proof['new_kit_validation'] is False
    assert proof['measurements_inherited'] is True
    assert proof['original_arrays_unchanged'] == ['column_family', 'faces', 'origins', 'vertices']
    assert proof['flags_shape'] == [10, 76, 4, 2]
    assert proof['finite_cells'] == 530 and proof['fallback_cells'] == 230
    assert proof['aggregate_sha256'] == result['provenance']['aggregate_sha256']
    annotation[0].validate_terrain_manifest(result)


@pytest.mark.parametrize('field', ['origins', 'column_family', 'vertices', 'flags_missing', 'flags_nan', 'flags_inf'])
def test_same_geometry_hash_is_not_sufficient(annotation, field):
    _, target, *_ = annotation
    path = target/'terrain_mesh.npz'
    with np.load(path) as z:
        arrays = {key: z[key] for key in z.files}
    if field == 'flags_missing':
        del arrays['flags']
    elif field == 'flags_nan':
        arrays['flags'][:, 23] = np.nan
    elif field == 'flags_inf':
        arrays['flags'][:, 23] = np.inf
    elif field == 'column_family':
        arrays[field][0] = 'B'
    else:
        arrays[field].flat[0] += 1
    np.savez_compressed(path, **arrays)
    receipt_path = target/'mesh_manifest.json'
    receipt = json.loads(receipt_path.read_text())
    receipt['mesh_file_sha256'] = sha(path)  # Even a repinned file cannot change the original.
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        manifest.assemble_saved_mesh(*annotation)


def test_aggregate_replacement_is_not_a_new_measurement(annotation):
    _, target, *_ = annotation
    path = target/'aggregate_measurements.json'
    path.write_text(path.read_text()+'\n')  # Same numbers, different source evidence.
    with pytest.raises(ValueError, match='aggregate'):
        manifest.assemble_saved_mesh(*annotation)


def test_source_pin_and_output_file_pin_are_both_checked(annotation):
    _, target, *_ = annotation
    receipt_path = target/'mesh_manifest.json'
    receipt = json.loads(receipt_path.read_text())
    receipt['flag_annotation_source']['npz_sha256'] = '0'*64
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='source NPZ'):
        manifest.assemble_saved_mesh(*annotation)


def test_output_file_sha_detects_modified_flags_even_when_geometry_matches(annotation):
    _, target, *_ = annotation
    path = target/'terrain_mesh.npz'
    with np.load(path) as z:
        arrays = {key: z[key] for key in z.files}
    arrays['flags'][0, 23, 0, 0] += .1
    np.savez_compressed(path, **arrays)
    with pytest.raises(ValueError, match='file SHA'):
        manifest.assemble_saved_mesh(*annotation)


def test_missing_original_measurement_is_not_bypassed(annotation):
    _, target, *_ = annotation
    receipt = json.loads((target/'mesh_manifest.json').read_text())
    source = Path(receipt['flag_annotation_source']['folder'])
    (source/'aggregate_measurements.json').unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        manifest.assemble_saved_mesh(*annotation)


def test_cli_rejects_partial_publication_contract_before_creating_output(tmp_path):
    with pytest.raises(SystemExit) as exc:
        tool.main(['--source', str(tmp_path/'absent'), '--out', str(tmp_path/'out'),
                   '--table', str(tmp_path/'table')])
    assert exc.value.code == 2 and not (tmp_path/'out').exists()


def test_E2_stage_override_routes_training_and_evaluation_without_changing_E1F(tmp_path):
    from foothold_s2.scripts.ex42_stage_launcher import _need, p1_argv
    env = {'EX42_MESH_DIR': '/old', 'EX42_MESH_DIR_E2': '/flags',
           'EX42_MESH_SHA256': 'a'*64, 'EX42_MESH_SHA256_E2': 'a'*64}
    assert _need(env, 'MESH_DIR', 'E1F') == '/old'
    assert _need(env, 'MESH_DIR', 'E2') == '/flags'
    argv = p1_argv(env, 'E2', '/run', _need(env, 'MESH_DIR', 'E2'),
                   _need(env, 'MESH_SHA256', 'E2'), '/python', tmp_path/'plan', tmp_path/'approvals')
    assert argv[argv.index('--mesh-dir')+1] == '/flags'
    assert argv[argv.index('--expected-mesh-sha256')+1] == 'a'*64
