"""Audit existing EX-42 mesh A entry patches with CPU triangle intersections."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from foothold_s2.terrains import columns, start_go2_v2 as go2
from foothold_s2.tests.test_start_go2_spawn_cpu import (
    test_ray_oracle_known_sloping_triangle, vertical_hits,
)


def audit(mesh_path, mount_path):
    test_ray_oracle_known_sloping_triangle()
    mount = json.loads(mount_path.read_text())
    with np.load(mesh_path, allow_pickle=False) as data:
        vertices, faces = data['vertices'], data['faces']
        origins, family = data['origins'], data['column_family'].astype(str)
    geometry_sha = hashlib.sha256(vertices.tobytes() + faces.tobytes()).hexdigest()
    if geometry_sha != mount['mesh_sha256']:
        raise ValueError('mount receipt and mesh geometry SHA disagree')
    a_columns = np.flatnonzero(family == 'A')
    if len(a_columns) != 50 or origins.shape[0] != 10:
        raise ValueError('expected actual A 50 columns x 10 levels')
    kinds = dict(zip(a_columns.tolist(), columns.column_types(columns.FULL, 50)))
    for failure in mount['per_column']['failed']:
        if failure['family'] == 'A' and kinds[failure['column']] != failure['kind']:
            raise ValueError('raw kind order differs from the generator contract')

    # Keep all triangles intersecting any of the requested world-space patches.
    # Pre-filter along y first; include triangle bounds, not only centroids.
    tri = vertices[faces]
    ymin, ymax = tri[:, :, 1].min(1), tri[:, :, 1].max(1)
    keep = np.zeros(len(tri), dtype=bool)
    selected = [c for c in a_columns if kinds[c] in go2.RESET_RANGES]
    for c in selected:
        y = origins[0, c, 1]
        keep |= (ymax >= y-.25) & (ymin <= y+.25)
    tri = tri[keep].astype(float)
    lower, upper = tri[:, :, :2].min(1), tri[:, :, :2].max(1)
    dx, dy = np.meshgrid(np.linspace(-.35, .35, 15), np.linspace(-.25, .25, 11))
    footprint = np.c_[dx.ravel(), dy.ravel()]
    rows = []
    for level in range(10):
        for column in selected:
            origin = origins[level, column].astype(float)
            hit = np.all(upper >= origin[:2]-(.35, .25), axis=1) & np.all(
                lower <= origin[:2]+(.35, .25), axis=1)
            v = tri[hit].reshape(-1, 3)
            f = np.arange(len(v)).reshape(-1, 3)
            tile = SimpleNamespace(kind=kinds[column], level=level, origin=origin)
            checked = go2.spawn_origin(tile, meshes=[SimpleNamespace(vertices=v, faces=f)])
            z = vertical_hits(v, f, checked[:2] + footprint)
            if not np.allclose(z, checked[2], atol=1e-7, rtol=0):
                raise ValueError(f'height mismatch: level={level}, column={column}')
            rows.append({'level': level, 'column': int(column), 'kind': kinds[column],
                         'origin_world': checked.tolist(), 'rays': len(z),
                         'z_min': float(z.min()), 'z_max': float(z.max())})
    if len(rows) != 250:  # 22 previous columns + 3 gaps, all ten levels
        raise ValueError('incomplete A support audit')
    return {'schema': 'start-go2-spawn-cpu/1', 'cpu_only': True, 'kit_reset_verified': False,
            'mesh_path': str(mesh_path), 'mesh_file_sha256': hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
            'mount_file_sha256': hashlib.sha256(mount_path.read_bytes()).hexdigest(),
            'geometry_sha256': geometry_sha, 'footprint_m': [.70, .50],
            'reset_ranges': go2.RESET_RANGES, 'cases': len(rows),
            'surface_probes': sum(r['rays'] for r in rows),
            'max_abs_z': max(abs(r[k]) for r in rows for k in ('z_min', 'z_max')), 'rows': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mesh', type=Path, required=True)
    parser.add_argument('--mount', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.mesh, args.mount)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}))
