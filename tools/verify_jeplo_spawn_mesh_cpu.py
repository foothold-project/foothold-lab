"""Replay C spawn selection against a combined mesh, never launch Kit/GPU."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from foothold_s2.terrains import jeplo_preset as jp
from foothold_s2.tests.test_jeplo_spawn_cpu import vertical_hits, test_known_triangle_intersection


def audit(path):
    test_known_triangle_intersection()  # establish the independent query's answer first
    with np.load(path, allow_pickle=False) as archive:
        vertices, faces = archive['vertices'], archive['faces']
        origins, family = archive['origins'], archive['column_family'].astype(str)
    c_columns = np.flatnonzero(family == 'C')
    if len(c_columns) != len(jp.KINDS) or origins.shape[0] != 10:
        raise ValueError('expected seven C columns and ten levels, no column guessing')
    centres = vertices[faces].mean(axis=1)
    results = []
    dx, dy = np.meshgrid(np.linspace(-.35, .35, 7), np.linspace(-.25, .25, 7))
    footprint = np.c_[dx.ravel(), dy.ravel()]
    for level in range(10):
        for column, kind in zip(c_columns, jp.KINDS):
            if kind not in jp.WAYPOINT_KINDS:
                continue
            old = origins[level, column]
            # Input is the old centre-origin artifact. Reject already-shifted origins.
            if not np.isclose((old[0]+45) % 9, 4.5, atol=1e-5):
                raise ValueError('audit input must retain the old C centre origins')
            shift = np.r_[old[:2]-4.5, 0.]
            mask = np.all(centres[:, :2] > shift[:2], axis=1) & np.all(
                centres[:, :2] < shift[:2]+9., axis=1)
            points = (vertices[faces[mask]].astype(float)-shift).reshape(-1, 3)
            local_faces = np.arange(len(points)).reshape(-1, 3)
            tile = jp.HeightTile(kind, level, 0, np.zeros((113, 113), dtype=np.int16), level/9)
            new = jp.spawn_origin(tile, vertices=points, faces=local_faces)
            hits = vertical_hits(points, local_faces, new[:2]+footprint)
            if not (np.isfinite(hits).all() and hits.min() >= -.1-1e-7
                    and hits.max() <= .15+1e-7 and np.ptp(hits) <= .15+1e-7):
                raise ValueError(f'support failed: level={level} column={column}')
            results.append({'level': level, 'column': int(column), 'kind': kind,
                            'old_origin_world': old.tolist(),
                            'new_origin_world': (new+shift).tolist(),
                            'new_origin_local': new.tolist(), 'support_probes': len(hits),
                            'support_min_m': float(hits.min()), 'support_max_m': float(hits.max()),
                            'support_relief_m': float(np.ptp(hits))})
    if len(results) != 30:
        raise ValueError(f'incomplete C support audit: {len(results)}')
    return {'schema': 'jeplo-spawn-cpu-replay/1', 'cpu_only': True, 'kit_contact_verified': False,
            'input_mesh': str(path.resolve()), 'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'reset_xy_yaw_range': [0., 0.], 'footprint_xy_half_extent_m': [.35, .25],
            'cases': len(results), 'surface_probes': sum(r['support_probes'] for r in results),
            'max_relief_m': max(r['support_relief_m'] for r in results), 'rows': results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mesh', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.mesh)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
