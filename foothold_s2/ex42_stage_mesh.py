"""CPU verification of a stage's immutable mesh profile, including flags in NPZ bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

FILES = ('terrain_mesh.npz', 'mesh_manifest.json', 'terrain_manifest.json')


def _digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def pinned_stage_mesh(document, stage):
    """None preserves the legacy common profile; a declared profile never falls back."""
    row = next((r for r in document['stages'] if r['id'] == stage), None)
    if row is None:
        raise ValueError(f'unknown mesh stage {stage}')
    if 'training_mesh_profile' not in row:
        return None
    name = row['training_mesh_profile']
    profiles = document.get('training_mesh_profiles')
    profile = profiles.get(name) if isinstance(profiles, dict) and isinstance(name, str) else None
    if not isinstance(profile, dict):
        raise ValueError('stage mesh profile is missing')
    directory, hashes = profile.get('directory'), profile.get('files')
    geometry = profile.get('geometry_sha256')
    if (not isinstance(directory, str) or not Path(directory).is_absolute()
            or not isinstance(hashes, dict) or set(hashes) != set(FILES)
            or any(not isinstance(v, str) or re.fullmatch('[0-9a-f]{64}', v) is None
                   for v in [geometry, *hashes.values()])):
        raise ValueError('stage mesh profile path or SHA contract is invalid')
    root = Path(directory)
    refs = {}
    for filename in FILES:
        path = root / filename
        if not path.is_file() or _digest(path) != hashes[filename]:
            raise ValueError(f'stage mesh file missing or SHA differs: {path}')
        refs[filename] = {'path': str(path.resolve()), 'sha256': hashes[filename]}
    manifest = json.loads((root / 'mesh_manifest.json').read_text(encoding='utf-8-sig'))
    if (not isinstance(manifest, dict) or manifest.get('mesh_sha256') != geometry
            or manifest.get('mesh_file_sha256') != hashes['terrain_mesh.npz']):
        raise ValueError('stage mesh manifest geometry/NPZ SHA differs')
    from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh
    from foothold_s2.terrains.ex42_flags import load_flag_table
    import numpy as np
    data = load_combined_mesh(root / 'terrain_mesh.npz', geometry)
    flags = load_flag_table(root / 'terrain_mesh.npz', *data['origins'].shape[:2])
    if flags is None or not np.isfinite(flags).all(axis=(2, 3)).any():
        raise ValueError('stage mesh has no usable named-kind flag table')
    return {'profile': name, 'directory': str(root.resolve()), 'geometry_sha256': geometry,
            'files': refs, 'flag_cells': int(np.isfinite(flags).all(axis=(2, 3)).sum())}


def mesh_launch_env(receipt, stage):
    if receipt is None:
        return {}
    return {f'EX42_MESH_DIR_{stage}': receipt['directory'],
            f'EX42_MESH_SHA256_{stage}': receipt['geometry_sha256']}
