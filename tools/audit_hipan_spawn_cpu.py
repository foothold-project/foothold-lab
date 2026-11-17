"""Read-only D-family spawn audit: analytic reset envelope + actual mesh rays."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from foothold_s2.terrains import hipan_posture as hp


def top_heights(triangles, points):
    """Vertical line intersection, return the highest hit or NaN on a missing ray."""
    a = triangles[:, 0]
    u, v = triangles[:, 1, :2]-a[:, :2], triangles[:, 2, :2]-a[:, :2]
    det = u[:, 0]*v[:, 1]-u[:, 1]*v[:, 0]
    keep = abs(det) > 1e-12
    a, u, v, det, triangles = (x[keep] for x in (a, u, v, det, triangles))
    output = []
    for xy in points:
        q = xy-a[:, :2]
        s = (q[:, 0]*v[:, 1]-q[:, 1]*v[:, 0])/det
        t = (u[:, 0]*q[:, 1]-u[:, 1]*q[:, 0])/det
        hit = (s >= -1e-7) & (t >= -1e-7) & (s+t <= 1+1e-7)
        z = a[:, 2]+s*(triangles[:, 1, 2]-a[:, 2])+t*(triangles[:, 2, 2]-a[:, 2])
        output.append(float(z[hit].max()) if hit.any() else float('nan'))
    return np.asarray(output)


def envelope_check(tile, extent):
    """Exact box bounds, no random samples. Covers the whole XY reset envelope."""
    low, high = tile.origin[:2]-extent, tile.origin[:2]+extent
    floor = tile.boxes[0]
    floor_margin = float(min(low[0]-floor[0], floor[1]-high[0], low[1]-floor[2], floor[3]-high[1]))
    obstacles = []
    for b in tile.boxes[1:]:
        overlap = (high[0] >= b[0] and low[0] <= b[1]
                   and high[1] >= b[2] and low[1] <= b[3])
        obstacles.append({'overlap_xy': bool(overlap), 'entry_x_margin_m': float(b[0]-high[0])})
    return {'floor_margin_m': floor_margin, 'obstacles': obstacles,
            'support_available': floor_margin >= 0 and not any(r['overlap_xy'] for r in obstacles),
            'xy_min_m': low.tolist(), 'xy_max_m': high.tolist()}


def known_answers():
    triangle = np.array([[[0.,0.,0.], [1.,0.,1.], [0.,1.,2.]]])
    np.testing.assert_allclose(top_heights(triangle, [[.2,.3]]), [.8])
    assert np.isnan(top_heights(triangle, [[2.,2.]])).all()
    tile = hp.build_tile('crawl', 9, seed=42)
    assert envelope_check(tile, np.array([.35,.25]))['support_available']
    assert not envelope_check(tile, np.array([1.1,.25]))['support_available']


def audit(mesh_path, manifest_path, mount_path):
    known_answers()
    manifest = json.loads(manifest_path.read_text())
    mount = json.loads(mount_path.read_text())
    if manifest['mesh_sha256'] != mount['mesh_sha256']:
        raise ValueError('manifest does not identify the reported mount mesh')
    with np.load(mesh_path, allow_pickle=False) as archive:
        vertices, faces = archive['vertices'], archive['faces']
        origins, families = archive['origins'], archive['column_family'].astype(str)
    columns = np.flatnonzero(families == 'D')
    if len(columns) != 3 or origins.shape[0] != 10:
        raise ValueError('expected D 3 columns x 10 storage rows')
    half = np.array([.35, .25])
    radius = math.hypot(*half)
    swept = np.full(2, .5+radius)  # circumscribed disk covers every yaw continuously
    tri = vertices[faces].astype(np.float64)
    tri_low, tri_high = tri[:, :, :2].min(1), tri[:, :, :2].max(1)
    results = []
    for row in range(10):
        for column, kind in zip(columns, hp.KINDS):
            tile = hp.build_tile(kind, min(row, hp.LEVEL_COUNTS[kind]-1), seed=42,
                                 wall_height_m=hp.WALL_HEIGHT_M, corridor_width_m=hp.CORRIDOR_WIDTH_M)
            world_origin = origins[row, column]
            shift = world_origin-tile.origin
            if not np.isclose(shift[2], 0., atol=1e-6):
                raise ValueError('D origin z changed in the mounted artifact')
            # Only the swept footprint is relevant, so select actual triangles by
            # XY bbox. Do not trust a mesh reconstructed from our box definitions.
            hit = np.all(tri_high >= world_origin[:2]-swept, axis=1) & np.all(
                tri_low <= world_origin[:2]+swept, axis=1)
            local = tri[hit]-shift
            if not len(local):
                raise ValueError(f'no actual mesh near D row={row} column={column}')
            records = {}
            for mode, extent in [('nominal', half), ('reset_swept', swept)]:
                check = envelope_check(tile, extent)
                xx, yy = np.meshgrid(np.linspace(-extent[0],extent[0],11),
                                     np.linspace(-extent[1],extent[1],11))
                heights = top_heights(local, tile.origin[:2]+np.c_[xx.ravel(),yy.ravel()])
                check.update(ray_count=len(heights), no_hit=int(np.isnan(heights).sum()),
                             support_min_m=float(np.nanmin(heights)), support_max_m=float(np.nanmax(heights)),
                             actual_mesh_support_zero=bool(np.isfinite(heights).all() and np.max(abs(heights))<1e-6))
                records[mode] = check
            results.append({'row': row, 'physical_level': tile.level, 'column': int(column), 'kind': kind,
                            'world_origin': world_origin.tolist(), **records})
    return {'schema': 'hipan-D-spawn-audit/1', 'cpu_only': True, 'geometry_changed': False,
            'mount_mesh_identity': manifest['mesh_sha256'], 'mount_state': mount['state'],
            'mesh_file': str(mesh_path), 'mesh_file_sha256': hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
            'mount_file': str(mount_path), 'mount_file_sha256': hashlib.sha256(mount_path.read_bytes()).hexdigest(),
            'generator_sha256': hashlib.sha256(Path(hp.__file__).read_bytes()).hexdigest(),
            'half_footprint_m': half.tolist(), 'yaw_bound_rad': [-3.14,3.14],
            'xy_jitter_bound_m': [-.5,.5], 'all_yaw_radius_m': radius,
            'swept_half_extent_m': swept.tolist(), 'stored_tiles': len(results),
            'ray_count': sum(r[m]['ray_count'] for r in results for m in ('nominal','reset_swept')),
            'unsupported': [{'row':r['row'],'kind':r['kind'],'mode':m} for r in results
                            for m in ('nominal','reset_swept') if not (r[m]['support_available'] and r[m]['actual_mesh_support_zero'])],
            'rows': results}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mesh', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--mount', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    report = audit(a.mesh,a.manifest,a.mount)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}))
    return 1 if report['unsupported'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
