"""PLY 스플랫을 world_to_mesh_4x4 로 메시 프레임(Z 업 · 미터)에 굽는다 (위치 · 회전 · log 축척 · SH 회전).

분류: 실험
작성: 오흥재 지시 Codex · 2026-09-16 21:08
근거: WORKER-07-nurec.md 1절 2) · _out/mesh/ground_stats.json · 3DGRUT threedgrut/export/sh_rotation.py
요지: 검증 (a)(b)(c) 를 transform_audit.json 에 남기고 헤더 · 속성 순서를 보존한 splat_mesh_frame.ply 를 쓴다.
"""
import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '_out/tools/3dgrut'))
import numpy as np
import torch
from plyfile import PlyData
from scipy.spatial.transform import Rotation
from threedgrut.export.sh_rotation import rotate_specular


def read_images(path):
    images = []
    with path.open(encoding='utf-8') as stream:
        while True:
            line = stream.readline()
            if not line:
                break
            if not line.strip() or line.startswith('#'):
                continue
            fields = line.split()
            q = np.array(fields[1:5], dtype=float)
            rwc = Rotation.from_quat(q[[1, 2, 3, 0]]).as_matrix()
            t = np.array(fields[5:8], dtype=float)
            images.append(dict(id=int(fields[0]), name=fields[9], camera_id=int(fields[8]),
                               center=-rwc.T @ t, rwc=rwc))
            stream.readline()  # COLMAP observations, possibly empty
    return images


def main():
    out = ROOT / '_out/nurec'
    stats = json.loads((ROOT / '_out/mesh/ground_stats.json').read_text(encoding='utf-8'))
    m = np.array(stats['transform']['world_to_mesh_4x4'])
    scale = stats['scale']['meters_per_scene_unit']
    r = m[:3, :3] / scale
    assert np.allclose(r.T @ r, np.eye(3)) and np.linalg.det(r) > 0
    qr = Rotation.from_matrix(r).as_quat()[[3, 0, 1, 2]]
    source = ROOT / '_out/splat/splat.ply'
    target = out / 'splat_mesh_frame.ply'
    # Copy-on-write mapping preserves the input and avoids per-property Python I/O.
    ply = PlyData.read(source, mmap='c')
    print('PLY mapped', flush=True)
    data = ply['vertex'].data
    names = data.dtype.names
    n = len(data)
    assert n == 2270126 and len(names) == 59
    for start in range(0, n, 100000):
        block = data[start:start + 100000]
        xyz = np.column_stack([block[k] for k in ('x', 'y', 'z')]).astype(float)
        xyz = xyz @ m[:3, :3].T + m[:3, 3]
        for i, key in enumerate(('x', 'y', 'z')):
            block[key] = xyz[:, i]
        q = np.column_stack([block[f'rot_{i}'] for i in range(4)]).astype(float)
        w, v = q[:, :1], q[:, 1:]
        qp = np.column_stack([qr[0] * w[:, 0] - v @ qr[1:],
                              qr[0] * v + w * qr[1:] + np.cross(qr[1:], v)])
        for i in range(4):
            block[f'rot_{i}'] = qp[:, i]
        for i in range(3):
            block[f'scale_{i}'] += math.log(scale)
        spec = np.column_stack([block[f'f_rest_{i}'] for i in range(45)])
        spec = spec.reshape(-1, 3, 15).transpose(0, 2, 1).reshape(-1, 45).copy()
        rotated = rotate_specular(torch.from_numpy(spec), torch.from_numpy(r), 3).numpy()
        rotated = rotated.reshape(-1, 15, 3).transpose(0, 2, 1).reshape(-1, 45)
        for i in range(45):
            block[f'f_rest_{i}'] = rotated[:, i]
        print(f'transformed {min(start + 100000, n)}/{n}', flush=True)
    ply.write(target)
    plane = np.load(ROOT / '_out/mesh/plane_audit.npz')
    points = plane['candidates_units'][plane['inlier_mask']]
    z = (points @ m[:3, :3].T + m[:3, 3])[:, 2]
    images = read_images(ROOT / '_out/colmap/undistorted/sparse_txt/images.txt')
    by_name = {item['name']: item for item in images}
    centers = np.array([by_name[name]['center'] for name in stats['cameras']['image_names']])
    transformed = centers @ m[:3, :3].T + m[:3, 3]
    camera_error = float(np.abs(transformed - np.array(stats['cameras']['centers_m'])).max())
    reread = PlyData.read(target)
    def header(path):
        with path.open('rb') as f:
            chunks = []
            while True:
                line = f.readline()
                chunks.append(line)
                if line.strip() == b'end_header':
                    return b''.join(chunks)
    result = dict(world_to_mesh_4x4=m.tolist(), scale=scale, rotation_wxyz=qr.tolist(),
                  inliers=len(z), plane_z_median_m=float(np.median(z)), plane_z_rms_m=float(np.sqrt(np.mean(z*z))),
                  cameras=len(images), camera_max_abs_error_m=camera_error,
                  count_before=n, count_after=len(reread['vertex'].data),
                  properties_before=len(names), properties_after=len(reread['vertex'].properties),
                  header_identical=header(source) == header(target),
                  property_order_identical=names == reread['vertex'].data.dtype.names)
    result['passed'] = bool(abs(result['plane_z_median_m']) < .02 and camera_error < .001
                            and result['count_after'] == n and result['properties_after'] == len(names)
                            and result['header_identical'] and result['property_order_identical'])
    (out / 'transform_audit.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)
    assert result['passed']


if __name__ == '__main__':
    main()
