"""CPU readback of the E2 mesh and the pinned PR713 named-kind guard, no Kit imports."""
from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import numpy as np
import torch

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.eval.ex42_mesh_eval import preflight
from foothold_s2.eval.fixed_terrain import kind_assignment
from foothold_s2.terrains.ex42_flags import load_flag_table, MeshFlagProvider
from foothold_s2.tools.ex42_mesh_flags import verify_annotation


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def guard(source_text, mesh, kind):
    # Execute the exact pure-CPU kind guard only. Importing Isaac's AppLauncher
    # itself bootstraps Kit in this installation, so do not import that module.
    tree = ast.parse(source_text)
    nodes = [n for n in tree.body if isinstance(n, ast.If)
             and isinstance(n.test, ast.Name) and n.test.id == 'kind_cell']
    assert len(nodes) == 1, 'pinned consumer guard changed'
    parser = argparse.ArgumentParser()
    scope = dict(kind_cell=True, args=SimpleNamespace(envs=64, kind_family='A',
        kind_name=kind, kind_level=0, count='flag_four'), mesh=mesh,
        parser=parser, COUNTS={'flag_four': 4})
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr):
            exec(compile(ast.Module(body=nodes, type_ignores=[]), '<PR713 kind guard>', 'exec'), scope)
    except SystemExit as exc:
        return {'rc': exc.code, 'stderr': stderr.getvalue().strip()}
    return {'rc': 0, 'stderr': stderr.getvalue().strip()}


def heights(triangles, points):
    """Independent upward-face barycentric readback at saved float32 world goals."""
    tri = triangles.astype(np.float64)
    normal_z = np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0])[:, 2]
    tri = tri[normal_z > 1e-10]
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    u, v = b[:, :2]-a[:, :2], c[:, :2]-a[:, :2]
    determinant = u[:, 0]*v[:, 1]-u[:, 1]*v[:, 0]
    result = []
    for point in points:
        diff = point-a[:, :2]
        s = (diff[:, 0]*v[:, 1]-diff[:, 1]*v[:, 0])/determinant
        t = (u[:, 0]*diff[:, 1]-u[:, 1]*diff[:, 0])/determinant
        hit = (s >= -1e-7) & (t >= -1e-7) & (s+t <= 1+1e-7)
        z = a[:, 2]+s*(b[:, 2]-a[:, 2])+t*(c[:, 2]-a[:, 2])
        assert hit.any(), 'flag falls outside the actual support'
        result.append(float(z[hit].max()))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mesh-dir', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--consumer-ref', default='7f222a3a606eafe600bdb6fe8820ce0134d34a0c')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    proof = verify_annotation(args.mesh_dir)
    source = Path(proof['folder'])
    manifest = json.loads((args.mesh_dir/'terrain_manifest.json').read_text())
    plan = EX42Plan.load(args.plan)
    plan.validate_terrain_manifest(manifest)
    code = subprocess.check_output(['git', 'show',
        args.consumer_ref+':foothold_s2/eval/ex42_flag_eval.py'], text=True)
    old_mesh, new_mesh = preflight(source), preflight(args.mesh_dir)
    table = [dict(family=f, kind=k) for f, k in zip(new_mesh['column_family'], new_mesh['columns'])]
    with np.load(new_mesh['mesh_npz']) as z:
        origins, flags = z['origins'], z['flags']
        triangles = z['vertices'][z['faces']]
    centres = triangles[:, :, :2].mean(axis=1)
    receipt = json.loads((args.mesh_dir/'mesh_manifest.json').read_text())
    cells = []
    for kind in ('stepping_stones_low', 'balance_beams', 'gaps'):
        rejected, accepted = guard(code, old_mesh, kind), guard(code, new_mesh, kind)
        assert rejected['rc'] == 2 and 'named kind flags missing' in rejected['stderr']
        assert accepted['rc'] == 0
        levels, types = kind_assignment(64, 10, table, 'A', kind, 0)
        terrain = SimpleNamespace(terrain_levels=torch.from_numpy(levels),
            terrain_types=torch.from_numpy(types), env_origins=torch.from_numpy(origins[levels, types]))
        actual = MeshFlagProvider(load_flag_table(new_mesh['mesh_npz'], 10, 76))(
            terrain, torch.arange(64), 4).numpy()
        assert np.array_equal(actual, flags[levels, types, :4])
        targets = []
        for col in sorted(set(types.tolist())):
            meta = next(c for c in receipt['flag_provenance']['cells'] if c['row'] == 0 and c['column'] == col)
            offset = np.array(meta['tile_offset_m'][:2])
            offset[1] += receipt['offsets_m']['A']
            selected = ((centres >= offset) & (centres < offset+8.)).all(axis=1)
            support = heights(triangles[selected], flags[0, col])
            assert np.allclose(support, meta['support_z_m'], atol=1e-6, rtol=0)
            assert np.all(np.diff(flags[0, col, :, 0]) > 0)
            targets.append({'column': col, 'origin_world_m': origins[0, col].tolist(),
                'four_flags_world_xy_m': flags[0, col].tolist(), 'support_z_m': support})
        cells.append({'family': 'A', 'kind': kind, 'level': 0,
                      'old_prekit_guard': rejected, 'new_prekit_guard': accepted,
                      'cpu_command_provider_equal_envs': 64, 'columns': targets})
    result = {'format': 'foothold-ex42-e2-flags-readback/1',
        'gpu_or_kit_run': False, 'training_started': False,
        'consumer_ref': args.consumer_ref, 'consumer_source_sha256': hashlib.sha256(code.encode()).hexdigest(),
        'consumer_scope': 'exact AST of pre-Kit named-kind guard, not full CLI or Kit attachment',
        'proof': proof, 'manifest_validator': 'PASS', 'kind_rows': len(manifest['kinds']),
        'terrain_manifest': str((args.mesh_dir/'terrain_manifest.json').resolve()),
        'terrain_manifest_sha256': sha(args.mesh_dir/'terrain_manifest.json'), 'cells': cells}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'output': str(args.out), 'sha256': sha(args.out),
                      'validator': result['manifest_validator'], 'kind_cells': len(cells)}))


if __name__ == '__main__':
    main()
