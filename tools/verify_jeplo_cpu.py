"""Read-only external-source oracle. No JEPLO implementation is vendored.

Load original numerical functions and actual config literals in a CPU namespace;
replace only Isaac config containers, not geometry. Reject a different revision.
"""
from __future__ import annotations
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
from scipy import interpolate

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from foothold_s2.terrains.jeplo_preset import KINDS, build_heightfield, mesh_arrays

REVISION = '460e2272907af053d6e66b57fec71fdbe6ca1774'


class Config:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def load_definitions(path, namespace, types):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    body = [ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)]
    for node in tree.body:
        if isinstance(node, types):
            if hasattr(node, 'decorator_list'):
                node.decorator_list = []
            body.append(node)
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(path), 'exec'), namespace)


def load_oracle(root):
    rev = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if rev != REVISION:
        raise ValueError(f'expected external source {REVISION}, got {rev}')
    folder = root / 'training/go2_parkour/go2_parkour/terrain'
    paths = [folder / n for n in ('parkour_terrain_generator_cfg.py', 'parkour_sub_terrains_cfg.py',
                                  'parkour_terrains_cfg.py', 'parkour_sub_terrians.py', 'utils.py')]
    for path in paths:
        relative = path.relative_to(root).as_posix()
        committed = subprocess.check_output(['git', '-C', str(root), 'show', f'{REVISION}:{relative}'])
        if path.read_bytes().replace(b'\r\n', b'\n') != committed.replace(b'\r\n', b'\n'):
            raise ValueError(f'external source has uncommitted changes: {relative}')
    geometry = {'np': np, 'interpolate': interpolate, 'random': random}
    load_definitions(paths[3], geometry, (ast.FunctionDef,))
    config = {'HfTerrainBaseCfg': Config, 'TerrainGeneratorCfg': Config}
    load_definitions(paths[0], config, (ast.ClassDef,))
    config['parkour_terrians'] = SimpleNamespace(**geometry)
    load_definitions(paths[1], config, (ast.ClassDef,))
    load_definitions(paths[2], config, (ast.Assign,))
    mesh = {'np': np}
    load_definitions(paths[4], mesh, (ast.FunctionDef,))
    return config['PARKOUR_TERRAINS_CFG'], geometry, mesh['convert_height_field_to_mesh'], paths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    preset, geometry, triangulate, paths = load_oracle(args.source)
    names = {'gap': 'gap', 'flat': 'hurdle', 'box': 'box', 'discrete_obstacles': 'discrete_obstacles',
             'discrete_grid': 'discrete_obstacles', 'pyramid_stairs': 'pyramid_stairs',
             'inverted_pyramid_stairs': 'pyramid_stairs'}
    rows = []
    for kind in KINDS:
        for level in range(10):
            for seed in (0, 42, 2026):
                for rough in (False, True):
                    cfg = copy.deepcopy(preset.sub_terrains['parkour_'+kind])
                    cfg.border_width = preset.sub_terrain_border_width
                    cfg.horizontal_scale, cfg.vertical_scale = preset.horizontal_scale, preset.vertical_scale
                    cfg.slope_threshold = preset.slope_threshold
                    count = int(preset.size[0]/cfg.horizontal_scale)+1
                    border = int(cfg.border_width/cfg.horizontal_scale)+1
                    cfg.size = ((count-2*border)*cfg.horizontal_scale,)*2
                    cfg.apply_roughness = rough
                    np.random.seed(seed)
                    raw = geometry['parkour_'+names[kind]+'_terrain'](level/9, cfg, 8)[0]
                    original = np.pad(raw, border)
                    tile = build_heightfield(kind, level, seed, roughness=rough)
                    difference = tile.height_units.astype(int) - original.astype(int)
                    expected_v, expected_f = triangulate(original, cfg.horizontal_scale, cfg.vertical_scale,
                                                        cfg.slope_threshold, terrain_size=preset.size)
                    vertices, faces = mesh_arrays(tile)
                    rows.append(dict(kind=kind, level=level, seed=seed, roughness=rough,
                                     mismatched_cells=int(np.count_nonzero(difference)),
                                     maximum_height_error_m=float(abs(difference).max()*cfg.vertical_scale),
                                     mesh_max_error_m=float(abs(vertices-expected_v).max()),
                                     triangles_equal=bool(np.array_equal(faces, expected_f))))
    failures = [r for r in rows if r['mismatched_cells'] or r['mesh_max_error_m'] or not r['triangles_equal']]
    report = dict(source_revision=REVISION, source_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                  cpu_only=True, cases=len(rows), failures=len(failures), results=rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(cases=len(rows), failures=len(failures), first_failures=failures[:10]), indent=2))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
