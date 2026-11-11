"""Pinned flag mesh selection is automatic, independent of a user's shell overrides."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from foothold_s2.scripts import ex42_stage_launcher as launcher
from foothold_s2.tests.test_ex42_stage_launcher_cpu import _env, _flag
from foothold_s2.tests import test_ex42_materialize_cpu as publication

known = publication.known
STAGES = ('E2', 'E3', 'E4', 'E5', 'M', 'E6a', 'E6b')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def pinned(tmp_path):
    root = tmp_path / 'flag-mesh'; root.mkdir()
    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
    faces = np.array([[0, 1, 2]], dtype=np.int32)
    geometry = hashlib.sha256(vertices.tobytes() + faces.tobytes()).hexdigest()
    np.savez(root / 'terrain_mesh.npz', vertices=vertices, faces=faces,
             origins=np.zeros((1, 1, 3)), column_family=['A'], flags=np.zeros((1, 1, 4, 2)))
    (root / 'mesh_manifest.json').write_text(json.dumps({'mesh_sha256': geometry,
        'mesh_file_sha256': sha(root / 'terrain_mesh.npz')}))
    (root / 'terrain_manifest.json').write_text('{}')
    return dict(directory=str(root), geometry_sha256=geometry,
                files={name: sha(root / name) for name in ('terrain_mesh.npz', 'mesh_manifest.json', 'terrain_manifest.json')})


def document(pinned):
    d = yaml.safe_load(launcher.PLAN.read_text())
    d['training_mesh_profiles'] = {'known': deepcopy(pinned)}
    for row in d['stages']:
        if row['id'] in STAGES:
            row['training_mesh_profile'] = 'known'
            row['parent'] = dict(source_stage_id='E1F', manifest_local_update=750,
                cumulative_update=15000, checkpoint_key='model_750.pt', sha256='a' * 64)
    return d


def test_shipped_stage_mesh_selection_is_explicit_and_e1f_keeps_common_path():
    d = yaml.safe_load(launcher.PLAN.read_text())
    for stage in STAGES:
        row = next(r for r in d['stages'] if r['id'] == stage)
        assert row['training_mesh_profile'] == 'e2_named_flags_v2'
    assert 'training_mesh_profile' not in next(r for r in d['stages'] if r['id'] == 'E1F')


@pytest.mark.parametrize('stage', STAGES)
def test_launcher_chooses_profile_without_stage_env_and_pins_training_and_p1(tmp_path, pinned, stage):
    d = document(pinned)
    # M remains disabled in production; this fixture only tests argv construction.
    if stage == 'M':
        next(r for r in d['stages'] if r['id'] == 'M')['enabled'] = True
    plan = tmp_path / 'plan.yaml'; plan.write_text(yaml.safe_dump(d))
    env = _env(tmp_path, stage=stage)
    env.update(EX42_AUTO_PLAN=str(plan), EX42_AUTO_APPROVALS=str(launcher.APPROVALS))
    argv, child, receipt = launcher.build(env, dry_run=True)
    assert _flag(argv, '--ex42_terrain_mesh_dir') == pinned['directory']
    p1 = json.loads(_flag(argv, '--ex42_p1_score_argv_json'))
    assert p1[p1.index('--expected-mesh-sha256') + 1] == pinned['geometry_sha256']
    assert receipt['training_mesh']['files']['terrain_mesh.npz']['sha256'] == pinned['files']['terrain_mesh.npz']
    assert receipt['training_mesh']['files']['terrain_manifest.json']['sha256'] == pinned['files']['terrain_manifest.json']
    assert child[f'EX42_MESH_DIR_{stage}'] == pinned['directory']
    assert child[f'EX42_MESH_SHA256_{stage}'] == pinned['geometry_sha256']
    assert 'CUDA_VISIBLE_DEVICES' in child and child['CUDA_VISIBLE_DEVICES'] == ''
    with pytest.raises(launcher.LaunchRefused, match='override'):
        launcher.build({**env, f'EX42_MESH_DIR_{stage}': '/wrong-mesh'}, dry_run=True)


@pytest.mark.parametrize('filename', ['terrain_mesh.npz', 'mesh_manifest.json', 'terrain_manifest.json'])
@pytest.mark.parametrize('change', ['missing', 'sha'])
def test_missing_or_modified_pinned_file_is_refused(tmp_path, pinned, filename, change):
    from foothold_s2.ex42_stage_mesh import pinned_stage_mesh
    d = document(pinned); path = Path(pinned['directory']) / filename
    if change == 'missing': path.unlink()
    else: path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='mesh'):
        pinned_stage_mesh(d, 'E2')


def test_geometric_hash_is_not_the_npz_file_hash_and_no_empty_flags(tmp_path, pinned):
    from foothold_s2.ex42_stage_mesh import pinned_stage_mesh
    d = document(pinned); d['training_mesh_profiles']['known']['geometry_sha256'] = pinned['files']['terrain_mesh.npz']
    with pytest.raises(ValueError, match='mesh'):
        pinned_stage_mesh(d, 'E2')
    d = document(pinned); d['training_mesh_profiles']['known']['directory'] = str(tmp_path / 'absent')
    with pytest.raises(ValueError, match='mesh'):
        pinned_stage_mesh(d, 'E2')


def test_materialize_preserves_profile_and_records_file_refs(known, pinned):
    # The generic publisher is exercised on its fully proven E1 -> E1F fixture;
    # the additional profile here tests publication, not an actual E1F mesh change.
    d = yaml.safe_load(known['plan'].read_text())
    d['training_mesh_profiles'] = {'known': pinned}
    next(r for r in d['stages'] if r['id'] == 'E1F')['training_mesh_profile'] = 'known'
    known['plan'].write_text(yaml.safe_dump(d))
    gate=json.loads(known['gate_receipt'].read_text());gate['plan_sha256']=sha(known['plan']);publication.dump(known['gate_receipt'],gate)
    ev=json.loads(known['evidence'].read_text());ev['source_plan_sha256']=sha(known['plan']);ev['gate_sha256']=sha(known['gate_receipt']);publication.dump(known['evidence'],ev)
    out = publication.run(known)
    transition=json.loads(Path(out['transition']).read_text())
    assert transition['training_mesh']['files']['terrain_mesh.npz']['sha256']==pinned['files']['terrain_mesh.npz']
    assert transition['artifacts']['training_mesh.terrain_manifest.json']['sha256']==pinned['files']['terrain_manifest.json']
    assert out['launch_env']['EX42_MESH_DIR_E1F']==pinned['directory']


def test_training_preflight_rechecks_mesh_before_the_dry_manifest_fallback(tmp_path, pinned, monkeypatch):
    from types import SimpleNamespace
    from foothold_s2.scripts import ex42_training_entry as entry
    plan=SimpleNamespace(document=document(pinned))
    monkeypatch.setattr(entry, 'validate_ex42_stage_e_cli', lambda **kw: (plan, {}, {}))
    monkeypatch.setattr(entry, 'read_e0_terrain_manifest', lambda *a: {'state': 'measured'})
    monkeypatch.setattr(entry, 'e0_terrain_mesh_swap_receipt', lambda x: x)
    args=dict(dry_run=True, stage_zero_requested=False, resume_requested=False, e0_approved=True,
        stage_id='E2', terrain_manifest_path=Path(pinned['directory'])/'terrain_manifest.json')
    result=entry.run_ex42_stage_e0_entry(**args)
    assert result['training_mesh']['files']['terrain_mesh.npz']['sha256']==pinned['files']['terrain_mesh.npz']
    with pytest.raises(ValueError, match='mesh'):
        entry.run_ex42_stage_e0_entry(**{**args,'terrain_manifest_path':tmp_path/'old/terrain_manifest.json'})
    path=Path(pinned['directory'])/'terrain_mesh.npz';path.write_bytes(path.read_bytes()+b'x')
    with pytest.raises(ValueError, match='mesh'):
        entry.run_ex42_stage_e0_entry(**args)


def test_environment_mount_refuses_a_different_directory_before_importing_kit(tmp_path, pinned):
    from types import SimpleNamespace
    from foothold_s2.scripts.ex42_training_entry import prepare_e0_env_cfg
    with pytest.raises(ValueError, match='mesh'):
        prepare_e0_env_cfg(SimpleNamespace(), SimpleNamespace(document=document(pinned)), tmp_path/'old', stage_id='E2')
